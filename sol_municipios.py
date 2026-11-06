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
sol_municipios.py - B1 da fase 4 (06/11/2026): LEITURA DA TABELA DE SOL

A tabela sol_municipios.csv traz, para cada um dos 5.571 municipios da lista
static/municipios.json, os 12 valores mensais de irradiacao no plano
horizontal da NASA POWER (ALLSKY_SFC_SW_DWN, kWh/m2/dia = HSP), ja escolhidos
pelo quadrado de 1 grau onde o municipio fica. Ela e montada de uma vez pelo
montar_tabela_sol.py (regra da maioria entre 3 fontes de coordenada; ver o
cabecalho dele e o sol_municipios_info.json). Com ela, a simulacao nao
precisa consultar o OpenStreetMap nem a NASA.

Este modulo SO LE e CONFERE a tabela. Se o arquivo faltar ou vier com
qualquer defeito, a tabela inteira fica desligada (TABELA vazia) e a
simulacao segue o caminho antigo (Nominatim + NASA POWER), exatamente como
antes do B1 - nunca usa uma tabela pela metade.
"""
import csv
import json
import os
import re
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_TABELA = os.path.join(PASTA, "sol_municipios.csv")
ARQUIVO_INFO = os.path.join(PASTA, "sol_municipios_info.json")

MESES = ["jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"]
COLUNAS = (["codigo_ibge", "municipio", "uf", "nasa_lat", "nasa_lon",
            "fontes_do_quadrado"] + MESES + ["anual_nasa"])
# Faixa de conferencia: a HSP mensal no Brasil fica entre ~2 e ~7,5 h/dia
# (na tabela de 06/11/2026: 2,28 a 7,02). Fora de 0,5-12 so por defeito.
HSP_MIN, HSP_MAX = 0.5, 12.0
MINIMO_DE_MUNICIPIOS = 5000


def _carregar(arquivo_tabela=ARQUIVO_TABELA, arquivo_info=ARQUIVO_INFO):
    """Devolve (tabela, info, motivo). tabela: codigo IBGE (texto) ->
    dicionario; vazia se houver qualquer defeito, e motivo diz qual."""
    try:
        with open(arquivo_tabela, encoding="utf-8", newline="") as f:
            leitor = csv.DictReader(f)
            if leitor.fieldnames != COLUNAS:
                return {}, {}, f"colunas inesperadas: {leitor.fieldnames}"
            tabela = {}
            for linha in leitor:
                codigo = linha["codigo_ibge"]
                if not re.fullmatch(r"\d{7}", codigo or ""):
                    return {}, {}, f"codigo IBGE invalido: {codigo!r}"
                if codigo in tabela:
                    return {}, {}, f"codigo IBGE repetido: {codigo}"
                hsp = [float(linha[m]) for m in MESES]
                if not all(HSP_MIN <= h <= HSP_MAX for h in hsp):
                    return {}, {}, f"HSP fora da faixa em {codigo}: {hsp}"
                tabela[codigo] = {
                    "hsp": hsp,
                    "quadrado_nasa": (float(linha["nasa_lat"]), float(linha["nasa_lon"])),
                    "fontes_do_quadrado": linha["fontes_do_quadrado"],
                }
        with open(arquivo_info, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError, KeyError, TypeError) as erro:
        return {}, {}, f"{type(erro).__name__}: {erro}"
    if len(tabela) < MINIMO_DE_MUNICIPIOS or info.get("municipios") != len(tabela):
        return {}, {}, (f"{len(tabela)} municipios na tabela, "
                        f"{info.get('municipios')} no arquivo de informacoes")
    return tabela, info, None


TABELA, INFO, MOTIVO_DESLIGADA = _carregar()
if MOTIVO_DESLIGADA:
    print(f"[sol_municipios] tabela de sol DESLIGADA ({MOTIVO_DESLIGADA}); "
          "a simulacao usa o Nominatim e a NASA POWER", file=sys.stderr)


def sol_do_municipio(codigo_ibge):
    """Os dados de sol do municipio (dicionario com "hsp" = 12 valores, de
    janeiro a dezembro; "quadrado_nasa"; "fontes_do_quadrado"), ou None se a
    tabela estiver desligada ou nao tiver esse codigo."""
    registro = TABELA.get(str(codigo_ibge))
    if registro is None:
        return None
    return {"hsp": list(registro["hsp"]),
            "quadrado_nasa": registro["quadrado_nasa"],
            "fontes_do_quadrado": registro["fontes_do_quadrado"]}


def periodo_da_tabela():
    """Texto do periodo da climatologia da NASA usado na tabela (para os
    creditos e a auditoria), ou None."""
    return (INFO.get("nasa_power") or {}).get("range")
