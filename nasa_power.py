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
nasa_power.py - Passo 3 do prototipo
Busca os 12 valores medios mensais de HSP (Horas de Sol Pleno) para uma
coordenada geografica, usando a API publica e gratuita NASA POWER.
Nao precisa de chave nem cadastro - so precisa de internet. Usamos o
"endpoint de climatologia", que devolve a MEDIA historica de varios anos
para cada mes - exatamente o que precisamos (nao precisamos escolher um
ano especifico).

FASE 1 POS-TCC, PASSO 2 (30/09/2026) - CACHE E TENTATIVAS
A conta NAO mudou: a funcao buscar_hsp_mensal continua recebendo a mesma
coordenada e devolvendo os mesmos 12 numeros que a NASA devolve. Mudou
so o CAMINHO ate eles:
  a) CACHE: a resposta fica guardada em cache/nasa_power.json, uma entrada
     por coordenada EXATA (sem arredondar - arredondar poderia cair em
     outro quadrado da grade da NASA e mudar o sol). Mesmo esquema do
     geocoding.py: arquivo JSON, gravacao atomica, data da consulta.
  b) RENOVACAO ANUAL (decisao da aluna, 30/09): a resposta guardada e
     consultada de novo quando tiver mais de 365 dias. A media historica
     quase nao muda, mas a NASA atualiza a base de vez em quando.
  c) TENTATIVAS: HTTP 429 (excesso de pedidos), erro do servidor da NASA
     ou demora -> espera um pouco e tenta de novo, no maximo 3 vezes,
     dentro de um tempo TOTAL maximo (antes nao havia limite nenhum).
  d) RESPOSTA INVALIDA E RECUSADA: se faltar mes, vier texto, numero
     negativo ou o codigo -999 da NASA ("sem dado"), a resposta nao entra
     no calculo nem no cache. Antes, um -999 entraria direto na conta.
  e) PLANO B: se a NASA falhar e existir uma resposta guardada, mesmo com
     mais de 1 ano, ela e usada (e o mesmo sol historico, so mais antigo).
     Se nao existir nenhuma, a funcao levanta ErroNasaPower. A mensagem
     amigavel na tela depende do simulacao.py, que esta congelado - fica
     para o passo em que o motor for aberto (item 25).

FASE 2 POS-TCC (03/10/2026) - MEMORIA TAMBEM NO BANCO (itens 2.3 e 2.7)
Mesmo esquema do geocoding.py: com o banco configurado (armazenamento.py,
variavel DATABASE_URL), a resposta guardada tambem vai para o banco, que nao
some quando o Render dorme. ORDEM DE PROCURA: arquivo -> banco -> NASA. O
banco so e consultado quando o arquivo NAO tem uma resposta dentro da
validade de 1 ano; a ficha do banco passa pela MESMA conferencia
(_registro_utilizavel: versao, data e os 12 meses sem -999) e so substitui a
do arquivo se for mais nova. Dai em diante tudo segue como antes - inclusive
o plano B do "cache vencido". Sem banco configurado, o caminho e exatamente
o de antes.

Por que o tempo total e curto (20 s): no servidor, o gunicorn atende UM
pedido de cada vez por processo e mata o processo que passa de 30 s sem
responder (padrao dele). Uma espera longa aqui travaria o site para todo
mundo e acabaria em erro do mesmo jeito. Fontes: gunicorn.org/design/ e
docs.gunicorn.org/en/latest/settings.html (timeout = 30 s), 30/09/2026.

Para rodar o teste do fim do arquivo:
    py nasa_power.py        (Windows)
    python3 nasa_power.py   (Mac/Linux)
"""
import json
import os
import threading
import time
from datetime import date

import requests

import armazenamento

# Ordem dos meses como a NASA POWER devolve (em ingles, 3 letras)
MESES_NASA = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]
NOMES_MESES_PT = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]

URL_NASA = "https://power.larc.nasa.gov/api/temporal/climatology/point"
PARAMETRO = "ALLSKY_SFC_SW_DWN"   # irradiacao solar = equivale ao HSP

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_CACHE = os.path.join(PASTA, "cache")
ARQUIVO_CACHE = os.path.join(PASTA_CACHE, "nasa_power.json")

# Mudar este numero faz todas as respostas guardadas serem consultadas de
# novo (o mesmo papel do VERSAO_DA_REGRA do geocoding.py).
VERSAO_DO_CACHE = 1
VALIDADE_DIAS = 365             # b) renovacao anual

# c) tentativas. A documentacao oficial lista o HTTP 429 mas nao publica o
# limite. A unica indicacao achada e de 30 pedidos por minuto no endpoint
# de climatologia, numa resposta da equipe da NASA POWER copiada por um
# usuario (github.com/ropensci/nasapower/issues/57, por volta de 2021) -
# fonte indireta. Por isso o intervalo minimo de 2 s entre consultas.
TENTATIVAS_MAXIMAS = 3
ESPERAS_S = [2, 5]              # antes da 2a e da 3a tentativa
ESPERA_MAXIMA_PEDIDA_S = 5      # se a NASA pedir mais (Retry-After), desiste
TEMPO_LIMITE_TENTATIVA_S = 15
TEMPO_TOTAL_MAXIMO_S = 20
INTERVALO_MINIMO_S = 2.0
CODIGOS_QUE_VALEM_REPETIR = {429, 500, 502, 503, 504}

# Codigo que a NASA POWER usa para "sem dado" (vem tambem no cabecalho da
# resposta, campo fill_value; os dois sao conferidos)
VALOR_SEM_DADO = -999


class ErroNasaPower(Exception):
    """A NASA POWER nao respondeu direito e nao ha resposta guardada."""


_trava = threading.Lock()
_cache = None
_ultima_consulta = 0.0

# Para auditoria e para o teste: de onde veio o ultimo sol entregue
# ("cache", "nasa" ou "cache vencido") e o que aconteceu em cada tentativa.
ULTIMO_DIAGNOSTICO = {}


# =======================================================================
# 1. O CACHE
# =======================================================================
# A pasta cache/ NAO vai para o GitHub (.gitignore), igual a do
# geocoding.py. No Render gratis o disco e apagado quando o servico
# reinicia ou "dorme" (15 min sem acesso) - ver fase1_registro.txt.
def _ler_cache():
    global _cache
    if _cache is None:
        try:
            with open(ARQUIVO_CACHE, encoding="utf-8") as arq:
                _cache = json.load(arq)
            if not isinstance(_cache, dict):
                _cache = {}
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


def _chave(latitude, longitude):
    # repr devolve o numero com todas as casas, sem arredondar
    return f"{float(latitude)!r},{float(longitude)!r}"


def _idade_em_dias(registro):
    try:
        return (date.today() - date.fromisoformat(registro["data_consulta"])).days
    except (KeyError, TypeError, ValueError):
        return None


def _registro_utilizavel(registro):
    """Entrada do cache que pode ser usada (esteja vencida ou nao)."""
    return (isinstance(registro, dict)
            and registro.get("versao_cache") == VERSAO_DO_CACHE
            and _idade_em_dias(registro) is not None
            and _valores_validos(registro.get("valores"), VALOR_SEM_DADO) is None)


# =======================================================================
# 2. A CONFERENCIA DA RESPOSTA
# =======================================================================
def _valores_validos(valores, valor_sem_dado):
    """None se os 12 meses estao certos; senao, o motivo da recusa."""
    if not isinstance(valores, dict):
        return "resposta sem os valores mensais"
    for mes in MESES_NASA:
        v = valores.get(mes)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return f"mes {mes} sem numero ({v!r})"
        if v == VALOR_SEM_DADO or v == valor_sem_dado:
            return f"mes {mes} com o codigo de 'sem dado' da NASA ({v})"
        if v < 0:
            return f"mes {mes} negativo ({v})"
    return None


# =======================================================================
# 3. A CONSULTA A NASA POWER
# =======================================================================
def _consultar_nasa(latitude, longitude, tentativas, tempo_limite):
    """
    Uma consulta. Devolve (valores, cabecalho) ou levanta excecao.
    Anota em 'tentativas' o que aconteceu.
    """
    global _ultima_consulta
    espera = INTERVALO_MINIMO_S - (time.monotonic() - _ultima_consulta)
    if espera > 0:
        time.sleep(espera)
    parametros = {
        "parameters": PARAMETRO,
        "community": "RE",                  # RE = Renewable Energy
        "longitude": longitude,
        "latitude": latitude,
        "format": "JSON",
    }
    try:
        resposta = requests.get(URL_NASA, params=parametros,
                                timeout=tempo_limite)
    finally:
        _ultima_consulta = time.monotonic()
    tentativas.append(f"HTTP {resposta.status_code}")
    resposta.raise_for_status()
    dados = resposta.json()
    # a resposta vem "aninhada" dentro de varias gavetinhas - aqui a gente
    # entra em cada uma ate achar os 12 valores mensais
    valores = dados["properties"]["parameter"][PARAMETRO]
    cabecalho = dados.get("header") or {}
    return valores, cabecalho


def _buscar_na_nasa(latitude, longitude):
    """
    Ate TENTATIVAS_MAXIMAS consultas, dentro de TEMPO_TOTAL_MAXIMO_S.
    Devolve (valores, cabecalho, lista_de_tentativas) ou
    (None, None, lista_de_tentativas) se nao deu.
    """
    inicio = time.monotonic()
    tentativas = []
    pedida = None       # espera pedida pela NASA (cabecalho Retry-After)
    for numero in range(TENTATIVAS_MAXIMAS):
        if numero > 0:
            espera = ESPERAS_S[min(numero - 1, len(ESPERAS_S) - 1)]
            if pedida is not None:
                if pedida > ESPERA_MAXIMA_PEDIDA_S:
                    tentativas.append(f"NASA pediu {pedida:g} s de espera - desistiu")
                    break
                espera = max(espera, pedida)
            restante = TEMPO_TOTAL_MAXIMO_S - (time.monotonic() - inicio)
            if restante < espera + 3:     # sem tempo para esperar e consultar
                tentativas.append("tempo total esgotado")
                break
            time.sleep(espera)
        pedida = None
        # a tentativa nunca passa do que sobra do tempo total (achado no
        # teste da nuvem: sem isso, 15 s + 2 s + 15 s = 32 s)
        restante = TEMPO_TOTAL_MAXIMO_S - (time.monotonic() - inicio)
        tempo_limite = min(TEMPO_LIMITE_TENTATIVA_S, restante)
        try:
            valores, cabecalho = _consultar_nasa(latitude, longitude, tentativas,
                                                 tempo_limite)
        except requests.HTTPError as erro:
            codigo = erro.response.status_code if erro.response is not None else None
            if codigo in CODIGOS_QUE_VALEM_REPETIR:
                pedida = _espera_pedida(erro.response)
                continue
            break                           # outro erro: repetir nao adianta
        except (requests.Timeout, requests.ConnectionError) as erro:
            tentativas.append(f"sem resposta ({type(erro).__name__})")
            continue
        except (ValueError, KeyError, TypeError) as erro:
            tentativas.append(f"resposta em formato inesperado ({type(erro).__name__})")
            break
        motivo = _valores_validos(valores, cabecalho.get("fill_value", VALOR_SEM_DADO))
        if motivo:
            tentativas.append(f"resposta recusada: {motivo}")
            break
        return valores, cabecalho, tentativas
    return None, None, tentativas


def _espera_pedida(resposta):
    """Segundos do cabecalho Retry-After, se vier em segundos."""
    try:
        return float(resposta.headers.get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        return None


# =======================================================================
# 4. A FUNCAO QUE O RESTO DA PLATAFORMA USA (mesma de antes)
# =======================================================================
def buscar_hsp_mensal(latitude, longitude):
    """
    Recebe latitude e longitude e devolve uma lista com 12 numeros de HSP
    (kWh/m2/dia - numericamente igual as Horas de Sol Pleno), um para cada
    mes do ano, na ordem: Janeiro, Fevereiro, ..., Dezembro.

    Levanta ErroNasaPower se a NASA nao responder direito e nao houver
    nenhuma resposta guardada para essa coordenada.
    """
    global ULTIMO_DIAGNOSTICO
    chave = _chave(latitude, longitude)

    with _trava:
        cache = _ler_cache()
        guardado = cache.get(chave)
        if not _registro_utilizavel(guardado):
            guardado = None

        # FASE 2 (03/10/2026): sem resposta valida no arquivo, procura no
        # banco (so quando ele esta configurado). Entra so se passar na mesma
        # conferencia e for mais nova que a do arquivo.
        if guardado is None or _idade_em_dias(guardado) > VALIDADE_DIAS:
            do_banco = armazenamento.ler_memoria("sol", chave)
            if _registro_utilizavel(do_banco) and (
                    guardado is None or _idade_em_dias(do_banco) < _idade_em_dias(guardado)):
                cache[chave] = do_banco
                _gravar_cache()
                guardado = do_banco

        if guardado is not None and _idade_em_dias(guardado) <= VALIDADE_DIAS:
            valores, fonte, tentativas = guardado["valores"], "cache", []
        else:
            valores, cabecalho, tentativas = _buscar_na_nasa(latitude, longitude)
            if valores is not None:
                cache[chave] = {
                    "valores": {mes: valores[mes] for mes in MESES_NASA},
                    "data_consulta": date.today().isoformat(),
                    "versao_cache": VERSAO_DO_CACHE,
                    # guardado para auditoria: periodo da climatologia,
                    # fontes e versao da API que a NASA informou
                    "cabecalho_nasa": cabecalho,
                }
                _gravar_cache()
                armazenamento.gravar_memoria("sol", chave, cache[chave])   # fase 2
                fonte = "nasa"
            elif guardado is not None:
                valores, fonte = guardado["valores"], "cache vencido"   # e) plano B
            else:
                ULTIMO_DIAGNOSTICO = {"fonte": None, "tentativas": tentativas}
                raise ErroNasaPower(
                    "A NASA POWER nao respondeu para a coordenada "
                    f"{latitude}, {longitude}: " + "; ".join(tentativas))

        ULTIMO_DIAGNOSTICO = {
            "fonte": fonte,
            "tentativas": tentativas,
            "data_consulta": cache[chave]["data_consulta"] if chave in cache else None,
        }

    # monta a lista final, na ordem certa (Jan a Dez)
    return [valores[mes] for mes in MESES_NASA]


# =======================================================================
# TESTE - usa as coordenadas de Guaira/PR que ja encontramos no Passo 2
# =======================================================================
if __name__ == "__main__":
    from calculo import hsp_medio_anual   # so leitura; o motor nao muda

    lat_teste = -24.0851924
    lon_teste = -54.2567519
    print(f"Buscando HSP para lat={lat_teste}, lon={lon_teste}...\n")
    hsp = buscar_hsp_mensal(lat_teste, lon_teste)
    for nome_mes, valor in zip(NOMES_MESES_PT, hsp):
        print(f"{nome_mes}: {valor:.2f} HSP")
    print(f"\nDe onde veio: {ULTIMO_DIAGNOSTICO['fonte']} "
          f"(consulta de {ULTIMO_DIAGNOSTICO['data_consulta']})")
    # A Equacao 1 do artigo e a media PONDERADA pelos dias do mes, a que o
    # calculo usa. A media simples fica so para comparacao.
    print(f"Media anual ponderada pelos dias do mes (Equacao 1): "
          f"{hsp_medio_anual(hsp):.2f} HSP")
    print(f"Media simples dos 12 meses (so conferencia, nao entra no calculo): "
          f"{sum(hsp) / len(hsp):.2f} HSP")
