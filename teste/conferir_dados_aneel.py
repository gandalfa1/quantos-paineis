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
conferir_dados_aneel.py - confere os dois arquivos que o
atualizar_dados_aneel.py grava, SEM internet.

POR QUE ESTE PROGRAMA EXISTE (fase 2, item 2.8 C, 02/10/2026). A aluna pediu
o Fio B automatico: "depois de tal dia, Fio B vai valer tal". A parte que
torna isso possivel e uma tarefa agendada no GitHub (arquivo
.github/workflows/atualizar-fio-b.yml) que roda o atualizar_dados_aneel.py
sozinha e publica o resultado. Sem ninguem olhando, alguem precisa conferir
o que vai ao ar - e e este programa. Ele tambem serve para a rodada feita a
mao, no PC: rodar logo depois do atualizar_dados_aneel.py.

O atualizar_dados_aneel.py ja tem tres travas ANTES de gravar (27 capitais,
95% dos municipios, variacao de no maximo 50%). Este programa olha DEPOIS de
gravar, e pelo lado do motor:

  PARTE 1 - O ARQUIVO DO FIO B (fio_b_por_distribuidora.csv): cabecalho
            certo; CNPJ de 14 digitos, sem repeticao; valor positivo; datas
            de vigencia validas e VIGENTES no dia da conferencia.
  PARTE 2 - O MAPA (static/distribuidoras_por_municipio.json): formato
            certo; cobre pelo menos 95% dos municipios da lista do IBGE; os
            nomes batem com o arquivo do Fio B.
  PARTE 3 - O MOTOR LE OS ARQUIVOS: o calculo.py carrega os dois arquivos (e
            nao cai no plano B); para CADA UM dos 5.571 municipios o
            fio_b_do_municipio() devolve um valor positivo; e pelo menos 95%
            deles tem o Fio B tirado do arquivo, nao do plano B do estado
            (mesmo criterio da trava 2).
  PARTE 4 - O QUE MUDOU EM RELACAO A VERSAO ANTERIOR: lista cada
            distribuidora que mudou. REGRA: o valor de uma distribuidora so
            pode mudar junto com uma VIGENCIA NOVA (nova homologacao da
            ANEEL). Valor diferente com a mesma vigencia nao e reajuste - e
            erro de dado ou mudanca de criterio, e o programa reprova.
            E o equivalente automatico de "so pode mudar o Fio B das
            distribuidoras reajustadas" (prompt da fase 2).
  PARTE 5 - OS 5 CASOS DE VALIDACAO: mostra o Fio B que cada um passa a usar
            e se mudou. Nao reprova: o Fio B de uma cidade pode mudar
            legitimamente num reajuste.

A VERSAO ANTERIOR (para a parte 4): por padrao, os arquivos .bak que o
atualizar_dados_aneel.py deixa ao gravar. Na tarefa do GitHub ela vem da
ultima versao publicada (git show). Sem versao anterior, a parte 4 e pulada
e o programa avisa.

COMO RODAR, dentro da pasta da plataforma:
    python teste/conferir_dados_aneel.py
Saida 0 = tudo certo; 1 = algum problema (a lista sai no fim).
"""

import argparse
import csv
import json
import os
import sys
from datetime import date

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA)

ARQUIVO_FIO_B = os.path.join(PASTA, "fio_b_por_distribuidora.csv")
ARQUIVO_MAPA = os.path.join(PASTA, "static", "distribuidoras_por_municipio.json")
ARQUIVO_MUNICIPIOS = os.path.join(PASTA, "static", "municipios.json")

CABECALHO_FIO_B = ["distribuidora", "cnpj", "fio_b_reais_por_kwh",
                   "inicio_vigencia", "fim_vigencia", "resolucao_homologatoria"]
COBERTURA_MINIMA = 0.95   # o mesmo criterio da trava 2 do atualizar_dados_aneel.py

# Os 5 casos de validacao contra o PVsyst (codigos IBGE da lista local)
CASOS = [("Bom Jesus da Lapa", "BA", "2903904"), ("Campinas", "SP", "3509502"),
         ("Cuiabá", "MT", "5103403"), ("Guaíra", "PR", "4108809"),
         ("Manaus", "AM", "1302603")]

problemas = []


def falha(texto):
    problemas.append(texto)
    print("   PROBLEMA: " + texto)


def _data_valida(texto):
    try:
        return date.fromisoformat(texto).isoformat() == texto
    except (TypeError, ValueError):
        return False


def ler_fio_b(caminho):
    """Le o CSV do Fio B. Devolve (cabecalho, {cnpj: linha}, repetidos)."""
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        linhas = list(leitor)
        cabecalho = leitor.fieldnames
    tabela, repetidos = {}, []
    for linha in linhas:
        cnpj = (linha.get("cnpj") or "").strip()
        if cnpj in tabela:
            repetidos.append(cnpj)
        tabela[cnpj] = linha
    return cabecalho, tabela, repetidos


def _valor(linha):
    return float(str(linha["fio_b_reais_por_kwh"]).replace(",", "."))


def parte1(hoje):
    print("\n=== PARTE 1 - arquivo do Fio B ===")
    if not os.path.exists(ARQUIVO_FIO_B):
        falha("fio_b_por_distribuidora.csv nao existe")
        return {}
    cabecalho, tabela, repetidos = ler_fio_b(ARQUIVO_FIO_B)
    if cabecalho != CABECALHO_FIO_B:
        falha(f"cabecalho diferente do esperado: {cabecalho}")
    for cnpj in repetidos:
        falha(f"CNPJ repetido: {cnpj}")
    vencidas = 0
    for cnpj, linha in tabela.items():
        nome = (linha.get("distribuidora") or "").strip()
        if not (len(cnpj) == 14 and cnpj.isdigit()):
            falha(f"CNPJ invalido: '{cnpj}' ({nome})")
        if not nome:
            falha(f"distribuidora sem nome: {cnpj}")
        try:
            valor = _valor(linha)
            if not valor > 0:
                falha(f"Fio B nao positivo em {nome}: {valor}")
        except (ValueError, TypeError):
            falha(f"Fio B ilegivel em {nome}: {linha.get('fio_b_reais_por_kwh')}")
        inicio, fim = linha.get("inicio_vigencia"), linha.get("fim_vigencia")
        if not (_data_valida(inicio) and _data_valida(fim)):
            falha(f"vigencia com data invalida em {nome}: {inicio} a {fim}")
        elif inicio > fim:
            falha(f"vigencia invertida em {nome}: {inicio} a {fim}")
        elif not (inicio <= hoje <= fim):
            vencidas += 1
            falha(f"{nome}: vigencia {inicio} a {fim} NAO inclui {hoje}")
    print(f"   {len(tabela)} distribuidoras; {vencidas} fora da vigencia em {hoje}")
    return tabela


def parte2(tabela):
    print("\n=== PARTE 2 - mapa municipio -> distribuidoras ===")
    try:
        with open(ARQUIVO_MAPA, encoding="utf-8") as f:
            conteudo = json.load(f)
    except (OSError, ValueError) as erro:
        falha(f"mapa ilegivel: {erro}")
        return {}
    municipios = conteudo.get("municipios")
    nomes = conteudo.get("nomes")
    if not isinstance(municipios, dict) or not isinstance(nomes, dict):
        falha("mapa sem os campos 'municipios' e 'nomes'")
        return {}
    for ibge, lista in municipios.items():
        if not isinstance(lista, list) or not all(
                isinstance(c, str) and len(c) == 14 and c.isdigit() for c in lista):
            falha(f"municipio {ibge}: lista de CNPJ invalida")
            break
    with open(ARQUIVO_MUNICIPIOS, encoding="utf-8") as f:
        lista_ibge = [str(m["ibge"]) for m in json.load(f)]
    cobertos = sum(1 for m in lista_ibge if m in municipios)
    fracao = cobertos / len(lista_ibge)
    print(f"   {len(municipios)} municipios no mapa; cobre {cobertos} de "
          f"{len(lista_ibge)} ({fracao*100:.1f}%)")
    if fracao < COBERTURA_MINIMA:
        falha(f"cobertura de {fracao*100:.1f}%, abaixo de {COBERTURA_MINIMA*100:.0f}%")
    esperado = {c: (l.get("distribuidora") or "").strip() for c, l in tabela.items()}
    if nomes != esperado:
        falha("os nomes do mapa nao batem com o arquivo do Fio B")
    return municipios


def parte3():
    print("\n=== PARTE 3 - o motor le os arquivos ===")
    import calculo
    if not calculo.TABELA_FIO_B_DE_ARQUIVO:
        falha("o calculo.py NAO carregou os arquivos (caiu no plano B)")
        return {}
    with open(ARQUIVO_MUNICIPIOS, encoding="utf-8") as f:
        municipios = json.load(f)
    origens, resultados = {}, {}
    for m in municipios:
        ibge = str(m["ibge"])
        try:
            r = calculo.fio_b_do_municipio(codigo_ibge=ibge, uf=m["uf"])
        except Exception as erro:          # qualquer excecao aqui e problema
            falha(f"fio_b_do_municipio({ibge}) levantou {type(erro).__name__}: {erro}")
            continue
        if not (isinstance(r.get("fio_b"), float) and r["fio_b"] > 0):
            falha(f"municipio {ibge}: Fio B {r.get('fio_b')!r}")
        origens[r["origem"]] = origens.get(r["origem"], 0) + 1
        resultados[ibge] = r
    print(f"   {len(calculo.FIO_B_POR_DISTRIBUIDORA)} distribuidoras carregadas; "
          f"{len(resultados)} municipios calculados")
    print("   origem do Fio B: " + ", ".join(f"{k} {v}" for k, v in sorted(origens.items())))
    do_arquivo = len(resultados) - origens.get("estado", 0)
    if resultados and do_arquivo / len(resultados) < COBERTURA_MINIMA:
        falha(f"so {do_arquivo} municipios com Fio B do arquivo "
              f"({do_arquivo/len(resultados)*100:.1f}%)")
    return resultados


def parte4(tabela, anterior_csv, anterior_json):
    print("\n=== PARTE 4 - o que mudou em relacao a versao anterior ===")
    if not anterior_csv or not os.path.exists(anterior_csv):
        print("   (sem versao anterior do arquivo do Fio B - parte pulada)")
        return {}
    _, antes, _ = ler_fio_b(anterior_csv)
    mudancas = {}
    for cnpj in sorted(set(antes) | set(tabela),
                       key=lambda c: (tabela.get(c) or antes.get(c))["distribuidora"]):
        novo, velho = tabela.get(cnpj), antes.get(cnpj)
        if velho and not novo:
            print(f"   saiu (sem tarifa vigente): {velho['distribuidora']}")
            mudancas[cnpj] = "saiu"
            continue
        if novo and not velho:
            print(f"   entrou: {novo['distribuidora']} R$ {_valor(novo):.6f} "
                  f"({novo['inicio_vigencia']} a {novo['fim_vigencia']})")
            mudancas[cnpj] = "entrou"
            continue
        mesma_vigencia = (novo["inicio_vigencia"] == velho["inicio_vigencia"])
        valor_mudou = abs(_valor(novo) - _valor(velho)) > 5e-7
        if valor_mudou and mesma_vigencia:
            falha(f"{novo['distribuidora']}: valor mudou (R$ {_valor(velho):.6f} -> "
                  f"R$ {_valor(novo):.6f}) SEM vigencia nova "
                  f"({novo['inicio_vigencia']}) - nao e reajuste")
        elif valor_mudou or not mesma_vigencia or novo != velho:
            variacao = (_valor(novo) - _valor(velho)) / _valor(velho) * 100
            print(f"   {novo['distribuidora']}: R$ {_valor(velho):.6f} -> "
                  f"R$ {_valor(novo):.6f} ({variacao:+.1f}%), vigencia "
                  f"{novo['inicio_vigencia']} a {novo['fim_vigencia']} "
                  f"[{novo['resolucao_homologatoria'] or 'resolucao nao informada'}]")
            mudancas[cnpj] = "mudou"
    if not mudancas:
        print("   nenhuma distribuidora mudou")
    if anterior_json and os.path.exists(anterior_json):
        with open(anterior_json, encoding="utf-8") as f:
            mapa_antes = json.load(f).get("municipios", {})
        with open(ARQUIVO_MAPA, encoding="utf-8") as f:
            mapa_agora = json.load(f).get("municipios", {})
        trocados = sorted(m for m in set(mapa_antes) | set(mapa_agora)
                          if mapa_antes.get(m) != mapa_agora.get(m))
        print(f"   mapa: {len(trocados)} municipios com lista de distribuidoras diferente"
              + (f" (ex.: {', '.join(trocados[:10])})" if trocados else ""))
    return mudancas


def parte5(resultados, mudancas):
    print("\n=== PARTE 5 - os 5 casos de validacao ===")
    for nome, uf, ibge in CASOS:
        r = resultados.get(ibge)
        if not r:
            falha(f"{nome}/{uf}: sem resultado")
            continue
        marca = " <- MUDOU" if r.get("cnpj") in mudancas else ""
        print(f"   {nome}/{uf}: {r['distribuidora']} R$ {r['fio_b']:.6f} "
              f"(origem {r['origem']}, ate {r['vigencia_fim_br']}){marca}")


def main():
    analisador = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    analisador.add_argument("--anterior-csv", default=ARQUIVO_FIO_B + ".bak")
    analisador.add_argument("--anterior-json", default=ARQUIVO_MAPA + ".bak")
    analisador.add_argument("--data", default=date.today().isoformat(),
                            help="dia da conferencia, AAAA-MM-DD (padrao: hoje)")
    argumentos = analisador.parse_args()

    print(f"Conferencia dos dados da ANEEL - {argumentos.data}")
    tabela = parte1(argumentos.data)
    parte2(tabela)
    resultados = parte3()
    mudancas = parte4(tabela, argumentos.anterior_csv, argumentos.anterior_json)
    parte5(resultados, mudancas)

    print("\n" + "=" * 70)
    if problemas:
        print(f"RESULTADO: PROBLEMA ({len(problemas)}):")
        for p in problemas:
            print("  * " + p)
        return 1
    print("RESULTADO: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
