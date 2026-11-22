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
conferir_curva_dinheiro.py - confere a tabela de 25 anos que alimenta o
grafico "O seu dinheiro, ano a ano" (FASE 4, 22/11/2026).

O motor devolve saldo_por_ano (e saldo_por_ano_pior, o pior caso de 2029):
uma linha por ano civil ate os 25 anos, com o saldo = economia somada -
manutencao - preco do sistema. O template so desenha esses numeros. Este
teste confere, em 10 cidades x consumos de 60 a 3.000 kWh x 3 tarifas:

  1. as linhas ate o ano do retorno sao as mesmas de retorno_por_ano;
  2. a tabela vai ate o mes 300 (25 anos) e a soma dos meses e 300;
  3. a soma da tabela (economia - manutencao) bate com o total de 25 anos
     (longo_prazo) e o ultimo saldo e o resultado de 25 anos (lucro);
  4. saldo = acumulado - preco do sistema em toda linha;
  5. a curva cruza o zero no MES DO RETORNO: o mes do retorno cai dentro da
     linha do ano do retorno, e dali em diante o saldo nunca fica negativo;
  6. pior caso: igual a conta principal antes de 2029, ultimo saldo = lucro
     do pior caso, e o mesmo cruzamento no mes do retorno dele.

Depois PLANTA 4 erros (saldo errado, tabela curta, economia de um ano
mudada, retorno em outro ano) e exige que todos sejam pegos.

Uso: python3 teste/conferir_curva_dinheiro.py   (sem rede, ~20 s)
Sai com 0 quando tudo confere e 1 quando algo falha.
"""
import copy
import math
import os
import socket
import sys
from datetime import date

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA)
os.chdir(PASTA)
os.environ.pop("DATABASE_URL", None)
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(OSError("sem rede"))

import calculo  # noqa: E402
calculo.data_de_hoje = lambda: date(2026, 11, 19)
import simulacao  # noqa: E402

CIDADES = ["Manaus - AM", "Belém - PA", "Bom Jesus da Lapa - BA", "Teresina - PI", "Cuiabá - MT",
           "Campo Grande - MS", "Campinas - SP", "Rio de Janeiro - RJ", "Guaíra - PR", "Curitiba - PR"]
TARIFAS = (0.45, 0.75, 1.60)
CAMPOS = ("ano", "meses", "percentual_fio_b", "economia", "custos", "acumulado", "economia_por_mes")


def _cruza_no_mes(linhas, payback):
    """Indice da linha que contem o mes do retorno, ou None."""
    for i, l in enumerate(linhas):
        if l["mes_fim"] - l["meses"] < math.ceil(payback) <= l["mes_fim"]:
            return i
    return None


def erros_da_curva(r):
    """Lista de problemas da tabela de 25 anos de um resultado do motor."""
    erros = []
    sa, ret, custo, lp = r["saldo_por_ano"], r["retorno_por_ano"], r["custo_total_sistema"], r["longo_prazo"]
    n = len(ret)
    if len(sa) < n:
        erros.append("menos linhas que retorno_por_ano")
    for a, b in zip(sa[:n], ret):
        for k in CAMPOS:
            if abs(a[k] - b[k]) > 1e-9:
                erros.append(f"linha {a['ano']}: {k} difere de retorno_por_ano")
    if sa[-1]["mes_fim"] != 300 or sum(l["meses"] for l in sa) != 300:
        erros.append("a tabela nao vai ate o mes 300")
    if abs(sum(l["economia"] - l["custos"] for l in sa) - (lp["economia"] - lp["custos"])) > 1e-6:
        erros.append("soma da tabela diferente do total de 25 anos")
    if abs(sa[-1]["saldo"] - lp["lucro"]) > 1e-6:
        erros.append("ultimo saldo diferente do resultado de 25 anos")
    if any(abs(l["saldo"] - (l["acumulado"] - custo)) > 1e-9 for l in sa):
        erros.append("saldo diferente de acumulado - preco do sistema")
    i = _cruza_no_mes(sa, r["payback_meses"])
    if i != n - 1:
        erros.append("o mes do retorno nao cai na linha do ano do retorno")
    elif any(l["saldo"] < -1e-6 for l in sa[i:]):
        erros.append("saldo negativo depois do retorno")
    sp, lpp = r["saldo_por_ano_pior"], r["longo_prazo_pior"]
    if (sp is None) != (lpp is None):
        erros.append("pior caso: tabela e totais nao combinam")
    if sp:
        for a, b in zip(sp, sa):
            if a["ano"] < 2029 and abs(a["saldo"] - b["saldo"]) > 1e-9:
                erros.append("pior caso diferente da conta principal antes de 2029")
                break
        if abs(sp[-1]["saldo"] - lpp["lucro"]) > 1e-6:
            erros.append("pior caso: ultimo saldo diferente do resultado de 25 anos")
        if lpp["payback_meses"] <= 300:
            j = _cruza_no_mes(sp, lpp["payback_meses"])
            if j is None or any(l["saldo"] < -1e-6 for l in sp[j:]) or \
                    (j > 0 and min(l["saldo"] for l in sp[:j]) >= 0):
                erros.append("pior caso: nao cruza o zero no mes do retorno")
        elif sp[-1]["saldo"] >= 0:
            erros.append("pior caso: nao se paga, mas termina positivo")
    return erros


def main():
    resultados, falhas = [], 0
    for c in CIDADES:
        for k in range(60, 3001, 40):
            for t in TARIFAS:
                r = simulacao.simular(c, float(k), k * t)
                if "saldo_por_ano" not in r:
                    continue  # nao se paga em 25 anos: o bloco nao aparece
                resultados.append(r)
                e = erros_da_curva(r)
                if e:
                    falhas += 1
                    print(f"  FALHA {c} {k} kWh tarifa {t}: {e[:3]}")
    print(f"=== 1: {len(resultados)} simulacoes com curva conferidas; falhas: {falhas}")

    plantados = []
    r = copy.deepcopy(resultados[0]); r["saldo_por_ano"][5]["saldo"] += 50
    plantados.append(("saldo errado num ano", r))
    r = copy.deepcopy(resultados[1]); r["saldo_por_ano"].pop()
    plantados.append(("tabela parando antes dos 25 anos", r))
    r = copy.deepcopy(resultados[2]); r["saldo_por_ano"][3]["economia"] *= 1.01
    plantados.append(("economia de um ano mudada", r))
    r = copy.deepcopy(resultados[3]); r["payback_meses"] += 13
    plantados.append(("retorno em outro ano", r))
    pegos = 0
    print("=== 2: erros plantados")
    for nome, r in plantados:
        ok = bool(erros_da_curva(r))
        pegos += ok
        print(f"  {'DETECTADO' if ok else 'NAO DETECTADO'}: {nome}")
    print(f"Erros plantados detectados: {pegos} de {len(plantados)}")
    tudo_ok = falhas == 0 and pegos == len(plantados) and len(resultados) > 0
    print("\nRESULTADO:", "OK" if tudo_ok else "FALHOU")
    return 0 if tudo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
