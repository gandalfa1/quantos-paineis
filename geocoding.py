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
geocoding.py - cidade -> coordenadas e estado
Transforma a cidade escolhida pelo usuario em coordenadas geograficas
(latitude e longitude) - que e o que a API da NASA POWER (nasa_power.py)
precisa para buscar o HSP daquele lugar - e informa o ESTADO, que define o
Fio B (calculo.fio_b_do_estado).

Usa o servico gratuito Nominatim (projeto OpenStreetMap). Nao precisa de
cadastro nem senha - so precisa de internet.

FASE 1 POS-TCC, PASSO 4 (30/09/2026) - TENTATIVAS E FALHAS DO NOMINATIM
A escolha da coordenada NAO mudou: cidade guardada no cache e consulta que
da certo seguem exatamente o mesmo caminho de antes. Mudou so o que
acontece quando o Nominatim FALHA (antes: a excecao subia na primeira
falha, sem nova tentativa):
  a) demora, falta de conexao ou erro do servidor (HTTP 500, 502, 503,
     504) -> tenta de novo, no maximo 3 vezes, dentro de 20 s no total
     (mesmo esquema do nasa_power.py);
  b) HTTP 429 ou 403 -> NAO tenta de novo, e o site para de consultar o
     Nominatim por 10 minutos. Motivo, com fonte: o mantenedor do
     Nominatim escreveu que o servidor "will send 429 as a warning before
     blocking you completely for a period of time" (lonvia,
     github.com/osm-search/Nominatim/discussions/2819, 19/09/2022), e a
     politica diz "Clients sending repeatedly the same query may be
     classified as faulty and blocked" (operations.osmfoundation.org/
     policies/nominatim/, lida em 30/09/2026). Insistir depois do aviso e
     o que leva ao bloqueio. Os 10 minutos sao um CRITERIO ADOTADO: as
     fontes nao dao numero;
  c) coordenada guardada com regra de escolha antiga (VERSAO_DA_REGRA) NAO
     e usada como plano B: foi uma regra antiga que aceitou o povoado
     errado de Agua Branca/PI, a 282 km da cidade certa;
  d) se nada der certo, levanta ErroNominatim com o motivo de cada
     tentativa (em ULTIMAS_TENTATIVAS, para auditoria). A mensagem amigavel
     na tela depende do simulacao.py, que esta congelado - fica para o
     passo em que o motor for aberto (junto com a da NASA POWER).

FASE 2 POS-TCC (03/10/2026) - MEMORIA TAMBEM NO BANCO (itens 2.3 e 2.7)
No Render gratis o disco e apagado quando o site dorme; a memoria em cache/
sumiria. Quando o banco esta configurado (armazenamento.py, variavel
DATABASE_URL), a ficha de cada municipio tambem e guardada la. A ORDEM DE
PROCURA passa a ser: arquivo -> banco -> Nominatim. A ficha que vem do banco
e a MESMA que iria para o arquivo e passa pela MESMA conferencia de versao
(VERSAO_DA_REGRA). A escolha da coordenada (escolher_resultado) nao mudou.
Sem banco configurado (PC da aluna, testes), o caminho e exatamente o de
antes. Banco fora do ar: o armazenamento.py devolve "nao achei" e o caminho
segue para o Nominatim, como antes.

Para rodar o teste do fim do arquivo: dentro da pasta do projeto, no terminal:
    py geocoding.py       (Windows)
    python3 geocoding.py  (Mac/Linux)
"""
import json
import os
import threading
import time
import unicodedata
from datetime import date

import requests

import armazenamento

# =======================================================================
# MUDANCA DA FASE 1 POS-TCC (29/09/2026) - item 24 do backlog
# =======================================================================
# O QUE ERA: a pessoa digitava a cidade como texto livre, o navegador pedia
# sugestoes direto ao Nominatim a cada pausa na digitacao, e o servidor
# mandava o texto inteiro ao Nominatim na hora de simular.
#
# POR QUE MUDOU (tres motivos, todos conferidos):
#  1. A politica de uso do Nominatim PROIBE autocompletar: "you must not
#     implement such a service on the client side using the API"
#     (operations.osmfoundation.org/policies/nominatim/, 29/09/2026).
#  2. A mesma politica EXIGE cache: "Results must be cached on your side".
#  3. Texto livre pode cair no lugar errado. Medido nos casos de validacao:
#     em Bom Jesus da Lapa/BA o Nominatim devolveu "Residencial Bom Jesus da
#     Lapa" (um loteamento), e nao a cidade. E ha 232 nomes de municipio que
#     se repetem em mais de um estado (505 municipios, 9% do pais, com os
#     nomes oficiais do IBGE) - "Guaira"
#     existe no PR e em SP. Cidade errada muda o sol (HSP) e o Fio B.
#
# O QUE E AGORA (caminho C, decidido pela aluna em 29/09/2026):
#  a) a pessoa ESCOLHE o municipio numa lista local (static/municipios.json,
#     5.571 registros com codigo IBGE, nome e UF). Nao ha mais texto livre;
#  b) o ESTADO vem da lista, com certeza - nao e mais deduzido do texto que
#     o Nominatim devolve. O Fio B passa a nao depender de adivinhacao;
#  c) as COORDENADAS continuam vindo do Nominatim/OpenStreetMap (fonte
#     documentada, licenca ODbL), agora por busca ESTRUTURADA (cidade,
#     estado e pais em campos separados), e o resultado so e aceito se
#     estiver no estado escolhido e tiver o nome do municipio;
#  d) cada municipio e consultado UMA vez e guardado em cache/ (no disco do
#     servidor). Como sao 5.571 municipios, com o tempo quase nenhuma
#     consulta nova sai para o Nominatim;
#  e) no maximo 1 consulta por segundo, e a aplicacao se identifica pelo
#     User-Agent, como a politica pede.
#
# O que NAO mudou: a funcao continua se chamando buscar_coordenadas(cidade)
# e devolvendo o mesmo dicionario (latitude, longitude, nome_encontrado, uf)
# - por isso simulacao.py, app.py e calculo.py nao foram tocados.
#
# As coordenadas da lista original (kelvins/municipios-brasileiros) NAO sao
# usadas: o conjunto nao informa a origem delas. Ver
# static/municipios-LICENCA.txt.

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_MUNICIPIOS = os.path.join(PASTA, "static", "municipios.json")
PASTA_CACHE = os.path.join(PASTA, "cache")
ARQUIVO_CACHE = os.path.join(PASTA_CACHE, "geocodificacao.json")

URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"

# Identificacao da aplicacao, exigida pela politica do Nominatim ("stock
# User-Agents as set by http libraries will not do"). A politica pede
# identificacao, nao e-mail: o contato e o endereco do repositorio.
# 03/10/2026 (fase 2, item 2.1): nome definitivo da plataforma, "Quantos
# Paineis" (antes "dimensionamento-fotovoltaico", provisorio). A forma de
# contato definitiva (e-mail da plataforma) entra no fim da fase 2 (item 2.6).
USER_AGENT = ("quantos-paineis/1.1 "
              "(+https://github.com/gandalfa1/dimensionamento-fotovoltaico)")

INTERVALO_MINIMO_S = 1.1   # politica: maximo de 1 consulta por segundo
TEMPO_LIMITE_S = 20        # sem isso, um Nominatim lento travava a pagina
                           # (o teste/conferir_cidades.py tambem usa)

# Tentativas (passo 4, 30/09/2026) - ver o cabecalho do arquivo.
TENTATIVAS_MAXIMAS = 3
ESPERAS_S = [2, 5]              # antes da 2a e da 3a tentativa
TEMPO_LIMITE_TENTATIVA_S = 15
TEMPO_TOTAL_MAXIMO_S = 20       # o mesmo teto de antes (TEMPO_LIMITE_S)
CODIGOS_QUE_VALEM_REPETIR = {500, 502, 503, 504}
CODIGOS_DE_AVISO = {429, 403}   # nao repetir; pausar as consultas
PAUSA_APOS_AVISO_S = 600        # 10 minutos - criterio adotado


class ErroNominatim(Exception):
    """O Nominatim nao respondeu (ou pediu para parar) e a cidade nao esta
    no cache."""

# CORRECAO T19 (22/09/2026): nomes dos estados, para ler o estado dentro da
# resposta do Nominatim. Desde 29/09 serve tambem no sentido contrario
# (sigla -> nome), para a busca estruturada.
NOME_PARA_UF = {
    "acre": "AC", "alagoas": "AL", "amapá": "AP", "amazonas": "AM",
    "bahia": "BA", "ceará": "CE", "distrito federal": "DF",
    "espírito santo": "ES", "goiás": "GO", "maranhão": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG",
    "pará": "PA", "paraíba": "PB", "paraná": "PR", "pernambuco": "PE",
    "piauí": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondônia": "RO", "roraima": "RR",
    "santa catarina": "SC", "são paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}
UF_PARA_NOME = {uf: nome.title().replace(" Do ", " do ").replace(" De ", " de ")
                for nome, uf in NOME_PARA_UF.items()}


# =======================================================================
# 1. A LISTA LOCAL DE MUNICIPIOS
# =======================================================================
def normalizar(texto):
    """Minusculas, sem acento, sem apostrofo/hifen, espacos simples.
    "Santa Bárbara d'Oeste" e "santa barbara d oeste" ficam iguais."""
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower().replace("'", " ").replace("’", " ").replace("-", " ")
    return " ".join(texto.split())


def rotulo(municipio):
    """O texto que aparece na lista e vai no formulario: "Guaíra - PR"."""
    return f"{municipio['nome']} - {municipio['uf']}"


def _carregar_municipios():
    with open(ARQUIVO_MUNICIPIOS, encoding="utf-8") as arq:
        lista = json.load(arq)
    por_rotulo = {}
    por_nome_uf = {}
    por_nome = {}
    for m in lista:
        por_rotulo[normalizar(rotulo(m))] = m
        por_nome_uf[(normalizar(m["nome"]), m["uf"])] = m
        por_nome.setdefault(normalizar(m["nome"]), []).append(m)
    return lista, por_rotulo, por_nome_uf, por_nome


MUNICIPIOS, _POR_ROTULO, _POR_NOME_UF, _POR_NOME = _carregar_municipios()


def encontrar_municipio(cidade):
    """
    Acha o municipio da lista a partir do texto do formulario.

    Aceita o rotulo da lista ("Guaíra - PR") e, por tolerancia, as formas
    "Guaíra, PR", "Guaíra/PR", "Guaíra (PR)", "Guaira, PR, Brasil" e o nome
    do estado por extenso. Sem estado, so aceita se o nome for UNICO no
    pais ("Manaus" sim; "Guaíra" nao, porque existe no PR e em SP).

    Devolve o dicionario do municipio ou None - nunca adivinha.
    """
    texto = (cidade or "").strip()
    if not texto:
        return None
    # Primeiro, o rotulo exato da lista. Cobre os dois nomes que tem
    # parenteses, como "Augusto Severo (Campo Grande) - RN".
    exato = _POR_ROTULO.get(normalizar(texto))
    if exato:
        return exato
    for sep in ("(", ")", "/", " - ", " – "):
        texto = texto.replace(sep, ",")
    partes = [p.strip() for p in texto.split(",") if p.strip()]
    if partes and normalizar(partes[-1]) in ("brasil", "brazil"):
        partes = partes[:-1]
    if not partes:
        return None

    if len(partes) >= 2:
        nome = normalizar(",".join(partes[:-1]))
        estado = partes[-1].strip()
        uf = estado.upper() if len(estado) == 2 else NOME_PARA_UF.get(estado.lower())
        if uf is None:  # nome do estado sem acento ("Parana")
            uf = {normalizar(n): s for n, s in NOME_PARA_UF.items()}.get(normalizar(estado))
        return _POR_NOME_UF.get((nome, uf))

    candidatos = _POR_NOME.get(normalizar(partes[0]), [])
    return candidatos[0] if len(candidatos) == 1 else None


# =======================================================================
# 2. O CACHE (politica do Nominatim: "Results must be cached on your side")
# =======================================================================
# Fica num arquivo JSON dentro de cache/, uma entrada por codigo IBGE.
# ATENCAO: a pasta cache/ NAO vai para o GitHub (.gitignore). Publicar os
# resultados de geocodificacao seria redistribuir dados do Nominatim, e o
# projeto decidiu nao fazer isso (estrategia pos-TCC, lista O QUE NAO FAZER).
_trava = threading.Lock()
_cache = None
_ultima_consulta = 0.0


def _ler_cache():
    global _cache
    if _cache is None:
        try:
            with open(ARQUIVO_CACHE, encoding="utf-8") as arq:
                _cache = json.load(arq)
        except (OSError, ValueError):
            _cache = {}          # sem arquivo, ou arquivo corrompido: recomeca
    return _cache


def _gravar_cache():
    try:
        os.makedirs(PASTA_CACHE, exist_ok=True)
        temporario = ARQUIVO_CACHE + ".tmp"
        with open(temporario, "w", encoding="utf-8") as arq:
            json.dump(_cache, arq, ensure_ascii=False, indent=1)
        os.replace(temporario, ARQUIVO_CACHE)   # troca de uma vez so
    except OSError:
        pass   # sem disco para gravar: o cache continua valendo na memoria


# =======================================================================
# 3. A CONSULTA AO NOMINATIM
# =======================================================================
def _uf_do_resultado(resultado):
    """Sigla do estado a partir de um resultado do Nominatim, ou None.
    (T19, 22/09/2026 - desde 29/09 serve so para CONFERIR o estado.)"""
    endereco = resultado.get("address") or {}
    iso = endereco.get("ISO3166-2-lvl4") or ""
    if iso.startswith("BR-") and len(iso) == 5:
        return iso[3:]
    for parte in reversed(resultado.get("display_name", "").split(",")):
        uf = NOME_PARA_UF.get(parte.strip().lower())
        if uf:
            return uf
    estado = (endereco.get("state") or "").strip().lower()
    return NOME_PARA_UF.get(estado)


# Tipos de resultado que representam a CIDADE, na ordem de preferencia:
# primeiro o PONTO da cidade (a sede, onde as casas estao); so depois o
# limite administrativo do municipio. O motivo e fisico: para um limite, o
# Nominatim pode devolver um ponto no meio do territorio, que num municipio
# grande fica longe da cidade (medido em 30/09/2026: Bom Jesus da Lapa/BA,
# 25 km). Bairro, loteamento ("residential"), rua etc. sao recusados.
#
# CORRECAO DE 30/09/2026 (achada pelo teste/conferir_cidades.py no
# notebook): um PONTO so vale se for a sede do PROPRIO municipio. A primeira
# versao aceitou, para "Agua Branca - PI", o povoado "Agua Branca, Manoel
# Emidio, Piaui" - mesmo nome, mesmo estado, mas dentro de OUTRO municipio,
# a 282 km da cidade certa. Agora, se o endereco do ponto diz que ele fica
# dentro de outro municipio, ele e recusado (ver _dentro_de_outro_municipio).
TIPOS_ACEITOS = [("place", "city"), ("place", "town"), ("place", "village"),
                 ("boundary", "administrative"), ("place", "municipality")]

# Quando esta regra de escolha mudar, este numero sobe, e o que estiver no
# cache com numero antigo e consultado de novo (sem isso, o erro de Agua
# Branca continuaria guardado no cache).
VERSAO_DA_REGRA = 2

# Campos do endereco do Nominatim que dizem "de qual cidade" um lugar e.
CAMPOS_DE_MUNICIPIO = ("municipality", "city", "town", "village", "county")


def _dentro_de_outro_municipio(r, nome):
    """True quando o endereco do resultado aponta um municipio com outro
    nome - ou seja, o ponto e um povoado ou bairro de outra cidade."""
    endereco = r.get("address") or {}
    # O campo com o tipo do proprio lugar ("village" num povoado) e ele
    # mesmo; o que interessa sao os OUTROS, que dizem onde ele fica.
    municipios = {normalizar(endereco[c]) for c in CAMPOS_DE_MUNICIPIO
                  if endereco.get(c) and c != r.get("type")}
    return bool(municipios) and nome not in municipios


def _categoria(r):
    """Classe do resultado. ATENCAO (correcao de 30/09/2026): no formato
    "jsonv2", que a busca usa, o campo "class" do formato "json" se chama
    "category" (nominatim.org/release-docs/latest/api/Output/). A primeira
    versao deste arquivo lia "class" e recusava TODOS os resultados - foi o
    que o teste/conferir_cidades.py mostrou no notebook (0 de 67)."""
    return r.get("category") or r.get("class")


def _nomes_do_resultado(r):
    """Todos os nomes que o OpenStreetMap guarda para o lugar (nome principal,
    nome oficial, nome em portugues, nomes antigos...), normalizados. Com
    isso, grafias diferentes da do IBGE ("Assú"/"Açu") nao derrubam a busca."""
    nomes = {normalizar(r.get("name") or r.get("display_name", "").split(",")[0])}
    for valor in (r.get("namedetails") or {}).values():
        for parte in str(valor).split(";"):
            nomes.add(normalizar(parte))
    return nomes


# Para auditoria: o que aconteceu com cada resposta da ultima busca. O
# teste/conferir_cidades.py mostra isto quando uma cidade e recusada.
ULTIMO_DIAGNOSTICO = []


def escolher_resultado(resultados, municipio):
    """Entre as respostas do Nominatim, fica com a que (1) esta no estado
    escolhido, (2) tem o nome do municipio e (3) e do tipo cidade.
    Se nenhuma servir, devolve None - melhor avisar do que usar outro lugar."""
    nome = normalizar(municipio["nome"])
    validos = []
    ULTIMO_DIAGNOSTICO.clear()
    for r in resultados:
        tipo = (_categoria(r), r.get("type"))
        uf = _uf_do_resultado(r)
        if uf != municipio["uf"]:
            motivo = f"estado {uf}"
        elif nome not in _nomes_do_resultado(r):
            motivo = "nome diferente"
        elif tipo not in TIPOS_ACEITOS:
            motivo = "nao e cidade"
        elif tipo[0] == "place" and _dentro_de_outro_municipio(r, nome):
            motivo = "fica dentro de outro municipio"
        else:
            motivo = "aceito"
            validos.append((TIPOS_ACEITOS.index(tipo), r))
        ULTIMO_DIAGNOSTICO.append(f"{r.get('name')} [{tipo[0]}/{tipo[1]}, {uf}]: {motivo}")
    if not validos:
        return None
    validos.sort(key=lambda par: par[0])
    return validos[0][1]


# Para auditoria: o que aconteceu em cada tentativa da ultima consulta ao
# Nominatim (vazio quando a cidade veio do cache).
ULTIMAS_TENTATIVAS = []

# Ate quando (relogio time.monotonic) o site fica sem consultar o
# Nominatim, depois de um HTTP 429 ou 403.
_pausado_ate = 0.0


def _consultar_nominatim(municipio, tempo_limite=TEMPO_LIMITE_S):
    """Uma consulta. Devolve a lista de resultados ou levanta excecao."""
    global _ultima_consulta
    espera = INTERVALO_MINIMO_S - (time.monotonic() - _ultima_consulta)
    if espera > 0:
        time.sleep(espera)
    parametros = {
        "city": municipio["nome"],
        "state": UF_PARA_NOME[municipio["uf"]],
        "country": "Brasil",
        "countrycodes": "br",
        "format": "jsonv2",
        "addressdetails": 1,
        "namedetails": 1,
        "limit": 5,
    }
    try:
        resposta = requests.get(URL_NOMINATIM, params=parametros,
                                headers={"User-Agent": USER_AGENT},
                                timeout=tempo_limite)
    finally:
        _ultima_consulta = time.monotonic()
    ULTIMAS_TENTATIVAS.append(f"HTTP {resposta.status_code}")
    resposta.raise_for_status()
    return resposta.json()


def _buscar_no_nominatim(municipio):
    """
    Ate TENTATIVAS_MAXIMAS consultas, dentro de TEMPO_TOTAL_MAXIMO_S.
    Devolve a lista de resultados do Nominatim (que ainda passa pela
    escolher_resultado, como antes) ou levanta ErroNominatim.
    """
    global _pausado_ate
    ULTIMAS_TENTATIVAS.clear()
    agora = time.monotonic()
    if agora < _pausado_ate:
        raise ErroNominatim(
            f"consultas ao Nominatim pausadas por mais {_pausado_ate - agora:.0f} s "
            f"depois de um aviso (HTTP 429 ou 403)")
    inicio = agora
    for numero in range(TENTATIVAS_MAXIMAS):
        if numero > 0:
            espera = ESPERAS_S[min(numero - 1, len(ESPERAS_S) - 1)]
            restante = TEMPO_TOTAL_MAXIMO_S - (time.monotonic() - inicio)
            if restante < espera + 3:     # sem tempo para esperar e consultar
                ULTIMAS_TENTATIVAS.append("tempo total esgotado")
                break
            time.sleep(espera)
        # a tentativa nunca passa do que sobra do tempo total
        restante = TEMPO_TOTAL_MAXIMO_S - (time.monotonic() - inicio)
        tempo_limite = min(TEMPO_LIMITE_TENTATIVA_S, restante)
        try:
            return _consultar_nominatim(municipio, tempo_limite)
        except requests.HTTPError as erro:
            codigo = erro.response.status_code if erro.response is not None else None
            if codigo in CODIGOS_DE_AVISO:
                _pausado_ate = time.monotonic() + PAUSA_APOS_AVISO_S
                ULTIMAS_TENTATIVAS.append(
                    f"aviso do Nominatim - consultas pausadas por {PAUSA_APOS_AVISO_S} s")
                break
            if codigo in CODIGOS_QUE_VALEM_REPETIR:
                continue
            break                           # outro erro: repetir nao adianta
        except (requests.Timeout, requests.ConnectionError) as erro:
            ULTIMAS_TENTATIVAS.append(f"sem resposta ({type(erro).__name__})")
            continue
        except ValueError as erro:          # resposta que nao e JSON
            ULTIMAS_TENTATIVAS.append(f"resposta em formato inesperado ({type(erro).__name__})")
            break
        except requests.RequestException as erro:   # qualquer outra falha
            ULTIMAS_TENTATIVAS.append(f"falha na consulta ({type(erro).__name__})")
            break
    raise ErroNominatim("consulta ao Nominatim sem sucesso: " + "; ".join(ULTIMAS_TENTATIVAS))


def buscar_coordenadas(cidade):
    """
    Recebe a cidade escolhida na lista, ex: "Guaíra - PR".
    Devolve um dicionario com latitude, longitude, o nome encontrado e o
    estado ("uf") - ou None, se a cidade nao estiver na lista (ou for
    ambigua) ou se o Nominatim nao tiver um resultado confiavel para ela.

    Campos a mais, para auditoria: municipio, codigo_ibge, osm_tipo, osm_id,
    fonte_coordenadas ("cache" ou "nominatim") e data_consulta.

    Levanta ErroNominatim se a cidade nao estiver no cache e o Nominatim nao
    responder (ou tiver pedido para parar) - ver o cabecalho do arquivo.
    """
    municipio = encontrar_municipio(cidade)
    if municipio is None:
        return None
    chave = str(municipio["ibge"])

    with _trava:
        cache = _ler_cache()
        if not (chave in cache and cache[chave].get("versao_regra") == VERSAO_DA_REGRA):
            # FASE 2 (03/10/2026): antes de ir ao Nominatim, procura no banco
            # (so quando ele esta configurado). Ficha de versao antiga e
            # ignorada, como no arquivo. A que serve passa a valer tambem no
            # arquivo (memoria local) - o mesmo dado, sem nova consulta.
            do_banco = armazenamento.ler_memoria("cidade", chave)
            if do_banco is not None and do_banco.get("versao_regra") == VERSAO_DA_REGRA:
                cache[chave] = do_banco
                _gravar_cache()
        if chave in cache and cache[chave].get("versao_regra") == VERSAO_DA_REGRA:
            registro = dict(cache[chave])
            origem = "cache"
            ULTIMAS_TENTATIVAS.clear()
        else:
            resultado = escolher_resultado(_buscar_no_nominatim(municipio), municipio)
            if resultado is None:
                return None
            registro = {
                "latitude": float(resultado["lat"]),
                "longitude": float(resultado["lon"]),
                "osm_tipo": resultado.get("osm_type"),
                "osm_id": resultado.get("osm_id"),
                "classe": f"{_categoria(resultado)}/{resultado.get('type')}",
                "nome_osm": resultado.get("display_name"),
                "data_consulta": date.today().isoformat(),
                "versao_regra": VERSAO_DA_REGRA,
            }
            cache[chave] = registro
            _gravar_cache()
            armazenamento.gravar_memoria("cidade", chave, registro)   # fase 2
            origem = "nominatim"

    return {
        "latitude": registro["latitude"],
        "longitude": registro["longitude"],
        "nome_encontrado": (f"{municipio['nome']} ({UF_PARA_NOME[municipio['uf']]})"
                            f" - código IBGE {municipio['ibge']}"),
        "uf": municipio["uf"],
        "municipio": municipio["nome"],
        "codigo_ibge": municipio["ibge"],
        "osm_tipo": registro.get("osm_tipo"),
        "osm_id": registro.get("osm_id"),
        "fonte_coordenadas": origem,
        "data_consulta": registro.get("data_consulta"),
    }


# =======================================================================
# TESTE
# =======================================================================
if __name__ == "__main__":
    cidade_teste = "Guaíra - PR"
    print(f"Buscando coordenadas para: {cidade_teste}...\n")
    try:
        resultado = buscar_coordenadas(cidade_teste)
    except ErroNominatim as erro:
        print(f"Falha: {erro}")
        raise SystemExit(1)
    if resultado:
        print(f"Encontrado: {resultado['nome_encontrado']}")
        print(f"Latitude:   {resultado['latitude']}")
        print(f"Longitude:  {resultado['longitude']}")
        print(f"Estado:     {resultado['uf']}")
        print(f"Origem:     {resultado['fonte_coordenadas']} "
              f"({resultado['osm_tipo']} {resultado['osm_id']})")
    else:
        print("Cidade nao encontrada na lista, ou sem resultado confiavel.")
