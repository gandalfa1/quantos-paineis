# Quantos Painéis — dimensionamento de sistemas fotovoltaicos residenciais
# Copyright (C) 2026 Brenda Morel Bueno Ferreira
#
# Este programa é software livre: você pode redistribuí-lo e/ou modificá-lo
# nos termos da GNU Affero General Public License, versão 3 ou (a seu critério)
# qualquer versão posterior, publicada pela Free Software Foundation. Ele é
# distribuído SEM NENHUMA GARANTIA. O texto oficial, em inglês, vale sobre este
# resumo e está logo abaixo; a licença completa está no arquivo LICENSE do
# repositório.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
contador.py - contador de acessos SEM cookie e SEM dado pessoal
Fase 2 pos-TCC, item 2.3 (decisoes da aluna em 03/10/2026).

O QUE CONTA, por dia (horario de Brasilia):
  categoria "pagina"                   -> nome da pagina aberta: "inicial"
                                          (a do formulario) e as 9 de
                                          explicacao (metodologia, sobre...)
  categoria "simulacao_com_resultado"  -> sigla do estado (PR, SP...)
  categoria "simulacao_sem_resultado"  -> sigla do estado, ou "??" quando a
                                          cidade nao foi reconhecida. Inclui
                                          campo invalido e servico de fora
                                          (NASA/OSM) que nao respondeu
  categoria "robo"                     -> nome do robo (Google, Bing...),
                                          contado A PARTE, nunca como pessoa

O QUE NAO CONTA NEM GUARDA: IP, cidade, valores digitados, cookie, e o texto
que o navegador manda para se identificar (User-Agent). O User-Agent e LIDO
so para decidir "e robo? qual?" e descartado na hora - o que vai para o banco
e so o rotulo da lista ROBOS abaixo.

LIMITE DECLARADO: o robo e reconhecido pelo nome que ele mesmo declara. Robo
que se disfarca de navegador comum entra como pessoa - por isso o numero de
pessoas e APROXIMADO (dizer assim na pagina Sobre).

O CONTADOR NUNCA TRAVA O SITE: contar() so soma num dicionario na memoria
(instantaneo). Uma tarefa em segundo plano grava a soma no banco de 10 em 10
minutos (decisao da aluna, 03/10), e tambem quando o servidor desliga. Motivo
dos 10 minutos: o Neon gratis da 100 CU-horas por mes (neon.com/docs/
introduction/plans, lida em 03/10) - no tamanho minimo, 0,25 CU, cerca de
400 horas acordado - e dorme depois de 5 minutos sem uso. Gravando de 10 em
10 minutos, o banco fica acordado no maximo metade do tempo (~360 h/mes).
Custo aceito: se o servidor cair de repente, perdem-se os ultimos minutos de
contagem. Se o banco falhar, a soma fica guardada e vai na proxima vez.

SEM O BANCO (DATABASE_URL vazio - o PC da aluna e os testes) o contador nao
faz nada.

COMO ENTRA NO SITE: app.py chama contador.ligar(app, PAGINAS) uma vez, no fim
do arquivo. O contador usa dois "ganchos" do Flask, FORA das funcoes do
calculo (ler_consumo_mensal, pagina_inicial, rota_simular ficam identicas):
  - after_request: depois de cada resposta, ve se foi uma pagina aberta;
  - template_rendered: quando a tela de resultado e montada, ve se a
    simulacao deu resultado ou erro (o mesmo aviso que o Flask da para
    quem testa o site; flask.palletsprojects.com, "Signals").
"""
import atexit
import re
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import request, template_rendered

import armazenamento

INTERVALO_GRAVACAO_S = 600     # 10 minutos

# Brasil sem horario de verao desde 2019 (Decreto 9.772/2019): Brasilia e
# sempre UTC-3. Hora fixa, para nao depender da tabela de fusos do servidor.
FUSO_BRASILIA = timezone(timedelta(hours=-3))

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO"}

# (padrao no User-Agent, rotulo guardado). A ordem importa: o primeiro que
# casar decide. Nomes conferidos nas paginas dos proprios robos - ex.:
# developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
ROBOS = [
    (r"googlebot|google-inspectiontool|googleother|storebot-google|adsbot-google|"
     r"mediapartners-google|google-extended|feedfetcher-google", "Google"),
    (r"bingbot|bingpreview|msnbot|adidxbot", "Bing"),
    (r"yandex", "Yandex"),
    (r"duckduckbot|duckassistbot", "DuckDuckGo"),
    (r"applebot", "Apple"),
    (r"gptbot|chatgpt-user|oai-searchbot|claudebot|claude-user|claude-searchbot|"
     r"anthropic-ai|perplexitybot|perplexity-user|ccbot|bytespider|amazonbot|"
     r"meta-externalagent", "robos de IA"),
    (r"facebookexternalhit|facebookbot|whatsapp|telegrambot|twitterbot|"
     r"linkedinbot|slackbot|discordbot", "previa de link (redes e mensageiros)"),
    # "bot" so como palavra solta, "...bot/" ou "...bot;" - sem pegar o nome
    # de celular "CUBOT" que aparece no navegador de alguns Android
    (r"\bbot\b|bot/|bot;|robot|crawl|spider|slurp|scrapy|python-requests|python-urllib|"
     r"aiohttp|httpx|curl/|wget/|go-http-client|java/|okhttp|libwww|"
     r"headlesschrome|phantomjs|uptime|monitor|render/", "outros robos"),
]
_ROBOS = [(re.compile(padrao), rotulo) for padrao, rotulo in ROBOS]


def robo(user_agent):
    """Rotulo do robo, ou None se parece uma pessoa. Sem User-Agent nenhum
    tambem conta como robo (navegador de verdade sempre manda um)."""
    texto = (user_agent or "").lower()
    if not texto.strip():
        return "outros robos"
    for padrao, rotulo in _ROBOS:
        if padrao.search(texto):
            return rotulo
    return None


# =======================================================================
# A SOMA NA MEMORIA E A GRAVACAO EM SEGUNDO PLANO
# =======================================================================
_trava = threading.Lock()
_pendente = Counter()          # (dia, categoria, nome) -> quantidade
_tarefa = None


def _hoje():
    return datetime.now(FUSO_BRASILIA).date()


def contar(categoria, nome):
    """Soma 1. Instantaneo; nao fala com o banco."""
    if not armazenamento.ligado():
        return
    with _trava:
        _pendente[(_hoje(), categoria, nome)] += 1
    _garantir_tarefa()


def gravar_agora():
    """Manda o que esta pendente para o banco. Se falhar, devolve a soma para
    a fila (vai na proxima vez). Devolve True se nao ficou nada pendente."""
    with _trava:
        if not _pendente:
            return True
        lote = dict(_pendente)
        _pendente.clear()
    linhas = [(dia, cat, nome, qtd) for (dia, cat, nome), qtd in sorted(lote.items())]
    if armazenamento.somar_contagens(linhas):
        return True
    with _trava:
        _pendente.update(lote)
    return False


def _laco():
    evento = threading.Event()
    while not evento.wait(INTERVALO_GRAVACAO_S):
        gravar_agora()


def _garantir_tarefa():
    global _tarefa
    if _tarefa is None:
        with _trava:
            if _tarefa is None:
                # daemon: nao segura o servidor quando ele for desligado
                _tarefa = threading.Thread(target=_laco, name="contador", daemon=True)
                _tarefa.start()


# Quando o servidor desliga normalmente (o Render manda o sinal de desligar
# ao "dormir" ou republicar, e o gunicorn encerra o processo), grava o que
# ficou pendente.
atexit.register(gravar_agora)


# =======================================================================
# OS GANCHOS NO SITE
# =======================================================================
def _uf_da_cidade(cidade):
    """Sigla do estado escolhido, pela lista local de municipios (a mesma do
    formulario; nenhuma consulta de fora). "??" se nao reconhecer."""
    from geocoding import encontrar_municipio   # leitura da lista local
    municipio = encontrar_municipio(cidade or "")
    uf = municipio["uf"] if municipio else None
    return uf if uf in UFS else "??"


def ligar(app, paginas):
    """Instala os dois ganchos no site. paginas: os nomes das paginas de
    explicacao (a lista PAGINAS do app.py)."""
    if not armazenamento.ligado():
        return                      # sem banco, nada a fazer

    nomes = set(paginas)

    @app.after_request
    def _contar_pagina(resposta):
        try:
            if request.method == "GET" and resposta.status_code == 200:
                caminho = request.path
                nome = "inicial" if caminho == "/" else caminho.lstrip("/")
                if nome == "inicial" or nome in nomes:
                    rotulo = robo(request.headers.get("User-Agent"))
                    if rotulo:
                        contar("robo", rotulo)
                    else:
                        contar("pagina", nome)
            elif request.method == "POST" and request.path == "/simular":
                rotulo = robo(request.headers.get("User-Agent"))
                if rotulo:
                    contar("robo", rotulo)
        except Exception:
            pass                    # o contador nunca atrapalha a resposta
        return resposta

    def _contar_simulacao(remetente, template, context, **extra):
        try:
            if (template.name != "resultado.html" or request.method != "POST"
                    or request.path != "/simular"):
                return
            if robo(request.headers.get("User-Agent")):
                return              # ja contado como robo
            categoria = ("simulacao_com_resultado" if context.get("resultado") is not None
                         else "simulacao_sem_resultado")
            contar(categoria, _uf_da_cidade(request.form.get("cidade")))
        except Exception:
            pass

    template_rendered.connect(_contar_simulacao, app, weak=False)
