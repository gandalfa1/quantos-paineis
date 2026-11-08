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
comparar_tabela_sol.py - B1 da fase 4 (08/11/2026): TABELA DE SOL ANTIGA x NOVA

Usado pela tarefa .github/workflows/renovar-tabela-sol.yml depois de remontar
a tabela, e por qualquer pessoa que queira conferir uma tabela nova.

O QUE FAZ:
 1. Abre a tabela NOVA com o mesmo leitor do site (sol_municipios._carregar).
    Se o site a desligaria (a tabela desliga calada, so com uma linha no
    registro), REPROVA.
 2. Exige os mesmos municipios (codigo, nome e UF) nas duas tabelas.
 3. Compara: versao e periodo da NASA, regra da maioria, municipios que
    mudaram de quadrado e quanto o sol mudou.
 4. Roda o motor do site nos 10 casos do artigo (a), sem internet, uma vez com
    cada tabela, e compara paineis, inversor e geracao.

COMO TERMINA (a tarefa decide por isto):
   codigo 0 = nada mudou no que o site usa (CSV igual byte a byte e mesma
              versao/periodo da NASA); nada a gravar.
   codigo 2 = algo mudou; o relatorio diz o que. A tarefa grava num RAMO NOVO,
              que so vai ao site depois da revisao completa e do "pode" da aluna.
   codigo 1 = REPROVADO (ou qualquer erro do programa); nada a gravar.

Uso: python teste/comparar_tabela_sol.py <csv antigo> <info antigo>
                                         <csv novo> <info novo>
"""
import csv
import json
import os
import socket
import statistics
import sys

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA)

MESES = ["jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"]

# Os 10 casos do artigo (a): cidade, consumo (kWh/mes); fatura = consumo x 0,75
# (com a UF, como a lista do formulario: "Belem" sozinho e ambiguo)
CASOS = [("Manaus - AM", 550), ("Belém - PA", 800), ("Bom Jesus da Lapa - BA", 300),
         ("Teresina - PI", 300), ("Cuiabá - MT", 300), ("Campo Grande - MS", 300),
         ("Campinas - SP", 180), ("Rio de Janeiro - RJ", 450), ("Guaíra - PR", 300),
         ("Curitiba - PR", 150)]
PAINEIS_ESPERADOS = [9, 11, 4, 4, 4, 4, 3, 7, 5, 2]   # com a tabela de 06/11/2026

# Avisos (nao reprovam: o ramo novo passa pela revisao completa de qualquer
# jeito; servem para chamar a atencao no relatorio)
AVISO_FRACAO_QUADRADOS = 0.01      # mais de 1% dos municipios mudou de quadrado
AVISO_SOL_ANUAL = 0.05             # sol anual mudou mais de 5% no mesmo quadrado
LISTA_MAXIMA = 30


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return {linha["codigo_ibge"]: linha for linha in csv.DictReader(f)}


def media_anual(linha):
    return sum(float(linha[m]) for m in MESES) / 12


def porcento(antes, depois):
    return 100.0 * (depois - antes) / antes


def bloquear_rede():
    def sem_rede(*args, **kwargs):
        raise OSError("rede bloqueada pela comparacao da tabela de sol")
    socket.socket.connect = sem_rede


def rodar_casos(sol_municipios, simulacao, tabela, info):
    """Roda os 10 casos com a tabela indicada (trocada na memoria)."""
    sol_municipios.TABELA, sol_municipios.INFO = tabela, info
    saida = {}
    for cidade, consumo in CASOS:
        r = simulacao.simular(cidade, consumo, round(consumo * 0.75, 2))
        if r.get("erro"):
            raise SystemExit(f"REPROVADO: {cidade} {consumo} kWh deu erro: {r['erro']}")
        if r.get("fonte_do_sol") != "tabela":
            raise SystemExit(f"REPROVADO: {cidade} nao usou a tabela "
                             f"(fonte_do_sol = {r.get('fonte_do_sol')!r})")
        saida[cidade] = (r["numero_paineis"], r["potencia_inversor_kw"],
                         r["geracao_anual_kwh"])
    return saida


def principal(csv_antigo, info_antigo, csv_novo, info_novo):
    bloquear_rede()
    import sol_municipios
    import simulacao

    print("=== 1. A TABELA NOVA NO LEITOR DO SITE ===")
    tab_nova, inf_nova, motivo = sol_municipios._carregar(csv_novo, info_novo)
    if motivo:
        raise SystemExit(f"REPROVADO: o site DESLIGARIA a tabela nova ({motivo})")
    tab_antiga, inf_antiga, motivo = sol_municipios._carregar(csv_antigo, info_antigo)
    if motivo:
        raise SystemExit(f"REPROVADO: a tabela antiga nao abre ({motivo})")
    conf = inf_nova.get("conferencia_quadrados") or {}
    if conf.get("diferentes") != 0:
        raise SystemExit(f"REPROVADO: conferencia dos quadrados da tabela nova: {conf}")
    print(f"OK: {len(tab_nova)} municipios; conferencia dos quadrados: "
          f"{conf.get('amostra_sedes')} sedes + {conf.get('trocados_conferidos')} "
          f"trocados, 0 diferentes")

    print("\n=== 2. OS MESMOS MUNICIPIOS ===")
    antiga, nova = ler_csv(csv_antigo), ler_csv(csv_novo)
    if set(antiga) != set(nova):
        raise SystemExit(f"REPROVADO: municipios diferentes (so na antiga: "
                         f"{sorted(set(antiga) - set(nova))[:10]}; so na nova: "
                         f"{sorted(set(nova) - set(antiga))[:10]})")
    nomes = [c for c in antiga if (antiga[c]["municipio"], antiga[c]["uf"])
             != (nova[c]["municipio"], nova[c]["uf"])]
    if nomes:
        raise SystemExit(f"REPROVADO: nome ou UF diferente em {nomes[:10]}")
    print(f"OK: os mesmos {len(nova)} codigos, nomes e UF")

    print("\n=== 3. NASA POWER ===")
    chaves = ("api", "range", "sources", "start", "end")
    nasa_a = {k: (inf_antiga.get("nasa_power") or {}).get(k) for k in chaves}
    nasa_n = {k: (inf_nova.get("nasa_power") or {}).get(k) for k in chaves}
    nasa_mudou = nasa_a != nasa_n
    for k in chaves:
        marca = "" if nasa_a[k] == nasa_n[k] else "   <-- MUDOU"
        print(f"  {k}: {json.dumps(nasa_a[k], ensure_ascii=False)} -> "
              f"{json.dumps(nasa_n[k], ensure_ascii=False)}{marca}")
    if nasa_mudou:
        print("ATENCAO: a NASA mudou a versao ou o periodo. Antes de ir ao site,\n"
              "ATUALIZAR OS TEXTOS que citam o periodo/versao: static/entenda.html,\n"
              "static/metodologia.html, static/limitacoes.html e README.md\n"
              "(static/precisao.html fica: descreve a comparacao do artigo (a)).")

    with open(csv_antigo, "rb") as fa, open(csv_novo, "rb") as fn:
        csv_igual = fa.read() == fn.read()
    if csv_igual and not nasa_mudou:
        print("\nNADA MUDOU: a tabela nova e igual byte a byte a atual e a NASA "
              "esta na mesma versao e periodo. Nada a gravar.")
        return 0

    print("\n=== 4. REGRA DA MAIORIA (quantos municipios em cada caso) ===")
    rot_a = inf_antiga.get("regra_da_maioria") or {}
    rot_n = inf_nova.get("regra_da_maioria") or {}
    for k in sorted(set(rot_a) | set(rot_n)):
        print(f"  {k}: {rot_a.get(k, 0)} -> {rot_n.get(k, 0)}")

    avisos = []
    print("\n=== 5. MUNICIPIOS QUE MUDARAM DE QUADRADO ===")
    mudaram = [c for c in nova if (antiga[c]["nasa_lat"], antiga[c]["nasa_lon"])
               != (nova[c]["nasa_lat"], nova[c]["nasa_lon"])]
    print(f"{len(mudaram)} de {len(nova)}")
    for c in sorted(mudaram, key=lambda c: -abs(porcento(media_anual(antiga[c]),
                                                          media_anual(nova[c]))))[:LISTA_MAXIMA]:
        a, n = antiga[c], nova[c]
        print(f"  {c} {n['municipio']}/{n['uf']}: ({a['nasa_lat']}, {a['nasa_lon']}) "
              f"{a['fontes_do_quadrado']} -> ({n['nasa_lat']}, {n['nasa_lon']}) "
              f"{n['fontes_do_quadrado']}; sol anual "
              f"{porcento(media_anual(a), media_anual(n)):+.2f}%")
    if len(mudaram) > LISTA_MAXIMA:
        print(f"  ... e mais {len(mudaram) - LISTA_MAXIMA} (lista pelos que mais mudam o sol)")
    if len(mudaram) > AVISO_FRACAO_QUADRADOS * len(nova):
        avisos.append(f"{len(mudaram)} municipios mudaram de quadrado "
                      f"(mais de {AVISO_FRACAO_QUADRADOS:.0%})")

    print("\n=== 6. SOL NO MESMO QUADRADO ===")
    mesmos = [c for c in nova if c not in mudaram]
    variacoes = {c: porcento(media_anual(antiga[c]), media_anual(nova[c])) for c in mesmos}
    com_mudanca = [c for c in mesmos if any(antiga[c][m] != nova[c][m] for m in MESES)]
    print(f"Sol diferente em {len(com_mudanca)} de {len(mesmos)} municipios")
    if com_mudanca:
        vs = [variacoes[c] for c in com_mudanca]
        maior_mes = max(abs(float(nova[c][m]) - float(antiga[c][m]))
                        for c in com_mudanca for m in MESES)
        print(f"  sol anual: menor {min(vs):+.2f}% | mediana {statistics.median(vs):+.2f}% "
              f"| maior {max(vs):+.2f}%; maior diferenca num mes: {maior_mes:.3f} h/dia")
        for c in sorted(com_mudanca, key=lambda c: -abs(variacoes[c]))[:5]:
            print(f"  {c} {nova[c]['municipio']}/{nova[c]['uf']}: {variacoes[c]:+.2f}%")
        grandes = [c for c in com_mudanca if abs(variacoes[c]) > 100 * AVISO_SOL_ANUAL]
        if grandes:
            avisos.append(f"sol anual mudou mais de {AVISO_SOL_ANUAL:.0%} no mesmo "
                          f"quadrado em {len(grandes)} municipios")

    print("\n=== 7. OS 10 CASOS DO ARTIGO (a) NO MOTOR, SEM INTERNET ===")
    casos_a = rodar_casos(sol_municipios, simulacao, tab_antiga, inf_antiga)
    casos_n = rodar_casos(sol_municipios, simulacao, tab_nova, inf_nova)
    for cidade, consumo in CASOS:
        (pa, ia, ga), (pn, inn, gn) = casos_a[cidade], casos_n[cidade]
        marca = "" if (pa, ia) == (pn, inn) else "   <-- MUDOU"
        print(f"  {cidade} {consumo} kWh: {pa} paineis, {ia} kW, {ga:.0f} kWh/ano -> "
              f"{pn} paineis, {inn} kW, {gn:.0f} kWh/ano "
              f"({porcento(ga, gn):+.2f}%){marca}")
        if (pa, ia) != (pn, inn):
            avisos.append(f"{cidade} {consumo} kWh: paineis/inversor mudaram")
    for nome, casos in (("atual", casos_a), ("nova", casos_n)):
        paineis = [casos[c][0] for c, _ in CASOS]
        igual = "IGUAL aos" if paineis == PAINEIS_ESPERADOS else "diferente dos"
        print(f"  tabela {nome}: paineis {'/'.join(map(str, paineis))} ({igual} "
              f"{'/'.join(map(str, PAINEIS_ESPERADOS))} da tabela de 06/11/2026)")
    if nasa_mudou:
        avisos.append("a NASA mudou a versao ou o periodo: atualizar os textos")

    print("\n=== RESUMO ===")
    print("ALGO MUDOU. A tabela nova vai para um RAMO NOVO; so vai ao site depois")
    print("da revisao completa (conferir_equacoes_3_3.py, 10 casos, telas) e do")
    print("\"pode\" da aluna.")
    for a in avisos:
        print(f"ATENCAO: {a}")
    if not avisos:
        print("Nenhum aviso.")
    return 2


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    sys.exit(principal(*sys.argv[1:]))
