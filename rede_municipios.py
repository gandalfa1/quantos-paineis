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
rede_municipios.py - fase 4, rede por cidade (11/11/2026): LEITURA DA TABELA
DE REDE

A tabela rede_municipios.csv diz, para cada um dos 5.571 municipios da lista
static/municipios.json, a rede trifasica mais comum: "127/220", "220/380" ou
"as duas". Ela e montada pela tarefa .github/workflows/renovar-tabela-rede.yml
(BDGD da ANEEL + lista da Neoenergia Coelba; regra no montar_tabela_rede.py).
O site so usa a tabela para a ORDEM dos dois modelos de inversor trifasico
acima de 10 kW: ela nao muda paineis, custo nem retorno.

Este modulo SO LE e CONFERE a tabela. Se o arquivo faltar ou vier com
qualquer defeito (inclusive uma unica linha alterada a mao: o sha256 do CSV
tem de ser o do rede_municipios_info.json), a tabela inteira fica desligada e
o site mostra os dois modelos como antes - nunca usa uma tabela pela metade.
"""
import csv
import hashlib
import json
import os
import re
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_TABELA = os.path.join(PASTA, "rede_municipios.csv")
ARQUIVO_INFO = os.path.join(PASTA, "rede_municipios_info.json")

COLUNAS = ["codigo_ibge", "municipio", "uf", "rede", "casas_127_220",
           "casas_220_380", "motivo"]
REDES = ("127/220", "220/380", "as duas")
MINIMO_DE_MUNICIPIOS = 5000


def _carregar(arquivo_tabela=ARQUIVO_TABELA, arquivo_info=ARQUIVO_INFO):
    """Devolve (tabela, info, motivo). tabela: codigo IBGE (texto) -> rede;
    vazia se houver qualquer defeito, e motivo diz qual."""
    try:
        with open(arquivo_info, encoding="utf-8") as f:
            info = json.load(f)
        with open(arquivo_tabela, "rb") as f:
            bruto = f.read()
        if hashlib.sha256(bruto).hexdigest() != info.get("csv_sha256"):
            return {}, {}, "o CSV nao e o descrito no arquivo de informacoes (sha256)"
        regra = info["regra"]
        limiar, minimo = float(regra["limiar"]), int(regra["minimo_casas"])
        leitor = csv.DictReader(bruto.decode("utf-8").splitlines())
        if leitor.fieldnames != COLUNAS:
            return {}, {}, f"colunas inesperadas: {leitor.fieldnames}"
        tabela = {}
        for linha in leitor:
            codigo, rede = linha["codigo_ibge"], linha["rede"]
            if not re.fullmatch(r"\d{7}", codigo or ""):
                return {}, {}, f"codigo IBGE invalido: {codigo!r}"
            if codigo in tabela:
                return {}, {}, f"codigo IBGE repetido: {codigo}"
            if rede not in REDES:
                return {}, {}, f"rede inesperada em {codigo}: {rede!r}"
            a, b = int(linha["casas_127_220"]), int(linha["casas_220_380"])
            if a < 0 or b < 0:
                return {}, {}, f"contagem negativa em {codigo}"
            # Uma rede so pode vir com a regra cumprida (>= limiar e >= minimo).
            if rede != "as duas":
                propria = a if rede == "127/220" else b
                if a + b < minimo or propria < limiar * (a + b):
                    return {}, {}, f"rede {rede} sem a regra cumprida em {codigo}"
            tabela[codigo] = rede
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError) as erro:
        return {}, {}, f"{type(erro).__name__}: {erro}"
    contagem = {r: sum(1 for v in tabela.values() if v == r) for r in REDES}
    if len(tabela) < MINIMO_DE_MUNICIPIOS or info.get("contagem") != contagem:
        return {}, {}, (f"{len(tabela)} municipios na tabela; contagem {contagem} "
                        f"diferente da do arquivo de informacoes {info.get('contagem')}")
    return tabela, info, None


TABELA, INFO, MOTIVO_DESLIGADA = _carregar()
if MOTIVO_DESLIGADA:
    print(f"[rede_municipios] tabela de rede DESLIGADA ({MOTIVO_DESLIGADA}); "
          "o site mostra os dois modelos de inversor trifasico, como antes", file=sys.stderr)


def rede_do_municipio(codigo_ibge):
    """"127/220" ou "220/380" quando a tabela diz que a rede trifasica do
    municipio e essa; None quando o municipio tem as duas, quando nao ha dado
    ou quando a tabela esta desligada (nesses casos o site mostra os dois
    modelos como antes)."""
    rede = TABELA.get(str(codigo_ibge))
    return rede if rede in ("127/220", "220/380") else None


def data_da_bdgd():
    """Data dos dados da BDGD usada na tabela (texto AAAA-MM-DD), ou None."""
    return INFO.get("data_bdgd")
