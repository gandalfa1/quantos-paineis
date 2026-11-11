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
conferir_equacoes_3_3.py - confere o motor da plataforma contra as equacoes
escritas na secao 3.3 do artigo (Equacoes 1 a 11).

ITENS 28 E 11 (06/10/2026): o retorno que a plataforma mostra passou a ser
MES A MES, com a escalada do Fio B (Lei 14.300/2022, art. 27) e a degradacao
dos modulos (0,5% ao ano). A Equacao 11 do artigo (custo / economia de um
mes) continua conferida, contra o campo payback_simples_meses do motor; a
conta nova e programada aqui a partir do TEXTO do bloco "Retorno MES A MES"
do calculo.py (eq11_mes_a_mes, abaixo), sem chamar a funcao do motor, e
conferida contra payback_meses e retorno_por_ano. A data e FIXADA em
06/10/2026 (DATA_DA_CONFERENCIA): o resultado nao muda com o dia em que a
conferencia roda, e o percentual de 2026 das Equacoes 3 e 4 continua valendo.

COMO FOI FEITO: as equacoes abaixo foram programadas A PARTIR DO TEXTO do
artigo, sem chamar nenhuma funcao do calculo.py. Depois o motor real
(simulacao.simular) e rodado com as mesmas entradas e os dois resultados sao
comparados numero a numero.

Tres procedimentos, os mesmos descritos no ultimo paragrafo da secao 3.3:
  1. CASOS RESOLVIDOS A MAO: os cinco casos de validacao, com os numeros
     conferidos na tela da plataforma em 23/09/2026;
  2. VARREDURA: toda a faixa de consumo, os tres tipos de ligacao (e o \"nao
     sei\"), varios estados, tarifas e perfis de sol, no modo media e no modo
     historico, conferindo as equacoes e as propriedades que valem para
     qualquer entrada;
  3. ERROS PLANTADOS: erros conhecidos sao introduzidos no motor, um de cada
     vez, e o programa confirma que os procedimentos 1 e 2 os detectam.

REVISAO GERAL (07/10/2026): a Equacao 2 do site passou a dividir o valor
da conta pelo MAIOR entre o consumo da conta e o custo de disponibilidade
(mes abaixo do minimo e cobrado pelo minimo - REN ANEEL 1.000/2021, arts. 290
e 291). eq2 abaixo segue essa regra; a varredura ganhou contas de mes abaixo
do minimo; e um erro plantado novo (a Equacao 2 sem o minimo) - 14 ao todo.

FASE 4, ITEM 7 (10/11/2026): inversores trifasicos de 12 a 25 kW. O texto
ganhou os degraus novos (DEGRAUS), a regra da ligacao trifasica acima de
10 kW (com a tarifa ainda pela ligacao de hoje), a conferencia da ligacao
eletrica de cada inversor mostrado - com STRINGS EM PARALELO no mesmo MPPT,
pela conta do texto (conferir_arranjo) - e testes diretos com inversores
ficticios (testes_strings_em_paralelo). A varredura vai ate 4.700 kWh/mes.
Erros plantados: 22.

Roda sem internet: a geocodificacao e a NASA POWER sao substituidas por
dubles que devolvem o estado e os 12 valores de HSP informados no teste.

Uso, dentro da pasta da plataforma:
    python teste/conferir_equacoes_3_3.py
"""

import math
import os
import sys
import types

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA)

# ---------------------------------------------------------------------------
# Dubles da geocodificacao e da NASA POWER (sem internet)
# ---------------------------------------------------------------------------
_ENTRADA = {"uf": None, "hsp": None}

geo = types.ModuleType("geocoding")
geo.buscar_coordenadas = lambda cidade: {
    "latitude": 0.0, "longitude": 0.0, "nome_encontrado": cidade, "uf": _ENTRADA["uf"]}
# B1 (fase 4, 06/11/2026): o simulacao.py passou a procurar a cidade numa
# tabela de sol pre-calculada antes de consultar os servicos de fora. Aqui
# o duble diz que a cidade NAO esta na lista: o sol continua vindo de
# _ENTRADA, e esta conferencia testa as equacoes com o sol que ela escolhe.
geo.municipio_da_lista = lambda cidade: None
nasa = types.ModuleType("nasa_power")
nasa.buscar_hsp_mensal = lambda lat, lon: list(_ENTRADA["hsp"])


# PASSO 6 (01/10/2026): o simulacao.py passou a tratar as falhas dos dois
# servicos de fora (mensagem amigavel em vez da pagina de erro do Flask),
# entao ele agora IMPORTA destes dois modulos as classes de excecao e as
# listas de diagnostico. Os dubles precisam te-las, ou o import falha e
# esta conferencia nem comeca. Os dubles nunca levantam as excecoes: aqui
# o sol e o estado vem de _ENTRADA, e o que se confere sao as equacoes.
class ErroNominatim(Exception):
    """Duble da excecao real do geocoding.py."""


class ErroNasaPower(Exception):
    """Duble da excecao real do nasa_power.py."""


geo.ErroNominatim = ErroNominatim
geo.ULTIMAS_TENTATIVAS = []
nasa.ErroNasaPower = ErroNasaPower
nasa.ULTIMO_DIAGNOSTICO = {"fonte": "duble do teste", "tentativas": []}
sys.modules["geocoding"] = geo
sys.modules["nasa_power"] = nasa

import calculo      # noqa: E402  (o motor real)
import simulacao    # noqa: E402
from datetime import date   # noqa: E402

# FASE 4, N2 (04/11/2026): as simulacoes desta conferencia usam o Fio B do
# ESTADO (sem CNPJ), entao o pior caso sai da estimativa "Fio B x mediana da
# razao cobranca maxima / Fio B" do arquivo da ANEEL. Para a conferencia nao
# depender de o arquivo ja ter essa coluna preenchida (sem ela nao ha pior
# caso, e o erro plantado "pior caso calculado com o Fio B" ficaria
# invisivel), a razao fica FIXA aqui em 2,0 - valor de teste, perto da mediana
# real (~2,1), que tambem cria casos com a cobranca acima da tarifa (o limite
# do motor e conferido). O motor de verdade continua lendo o arquivo.
calculo.RAZAO_COBRANCA_MAXIMA_MEDIANA = 2.0

# Itens 28 e 11: o motor le a data em UM ponto so (calculo.data_de_hoje). Fixa-
# la aqui deixa a conferencia reproduzivel em qualquer dia - antes ela passaria
# a divergir sozinha em 01/01/2027, quando o motor trocaria para 75%.
DATA_DA_CONFERENCIA = date(2026, 10, 6)
calculo.data_de_hoje = lambda: DATA_DA_CONFERENCIA

# ---------------------------------------------------------------------------
# AS EQUACOES DA SECAO 3.3, escritas a partir do texto (nao usam o calculo.py)
# ---------------------------------------------------------------------------
DIAS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
TD = 0.80                     # taxa de desempenho (Equacoes 5 e 8)
FDI = 0.80                    # fator de dimensionamento do inversor (Eq. 7)
P_MOD = 0.600                 # kWp, modulo Jinko de 600 Wp (secao 3.2)
DEGRAUS = [1.0, 1.5, 2.0, 2.5, 3.0, 4.2, 5.0, 6.0, 7.0, 7.5, 8.0, 9.0, 10.0,  # 1,0 kW: fase 4, 03/11/2026
           12.0, 15.0, 20.0, 25.0]   # trifasicos: fase 4, item 7, 10/11/2026
LIMITE_MONOFASICO = 10.0      # kW: acima, inversor trifasico e ligacao trifasica (item 7)
C_DISP = {"monofasica": 30.0, "bifasica": 50.0, "trifasica": 100.0}
P_FIO_B_2026 = 0.60           # Lei 14.300/2022, art. 27, IV
SISTEMA = [(2, 3.44), (4, 2.66), (8, 2.21), (12, 2.04), (30, 1.91)]   # R$/Wp
KIT = [(2, 1.68), (4, 1.42)]  # R$/Wp, trecho usado abaixo de 2 kWp
SERVICO_FIXO = 3520.0         # R$ = (3,44 - 1,68) x 2.000 Wp


def eq1(H):
    return sum(h * d for h, d in zip(H, DIAS)) / 365


def eq2(V_fat, C_fat, C_disp=0.0):
    # REVISAO GERAL (07/10/2026): o divisor e o consumo que a conta COBROU, o
    # maior entre o consumo da conta e o custo de disponibilidade (REN ANEEL
    # 1.000/2021, art. 290, caput, e art. 291) - num mes abaixo do minimo a
    # distribuidora cobra o minimo. O artigo do TCC (tag v1.0-tcc) dividia pelo
    # consumo da conta; os dois so diferem quando C_fat < C_disp.
    return V_fat / max(C_fat, C_disp)


def eq3(F_B, p, T):
    f = F_B * p
    return f, T - f


def eq4(C_meses, C_disp, T, f):
    Ccm = [min(C, max(C - C_disp, 0.0) * T / (T - f)) for C in C_meses]
    return Ccm, sum(Ccm)


def eq5(C_comp, H_ano):
    E_d = C_comp / 365
    return E_d, E_d / (H_ano * TD)


def eq6(P_t):
    N = math.ceil(P_t / P_MOD - 1e-12)
    return N, N * P_MOD


def eq7(P_inst):
    for g in DEGRAUS:
        if g >= FDI * P_inst - 1e-12:
            return g
    return None               # acima de 25 kW: nao ha degrau na grade (item 7)


def eq8(P_inst, H):
    G_m = [P_inst * h * TD * d for h, d in zip(H, DIAS)]
    return G_m, sum(G_m)


def eq9(G_ano, C_comp, v):
    E_comp = min(G_ano, C_comp)
    return E_comp, E_comp * v


def _interp(x, pontos):
    (x1, y1), (x2, y2) = pontos[0], pontos[1]
    if x <= x1:
        return y1 + (y2 - y1) / (x2 - x1) * (x - x1)
    for (x1, y1), (x2, y2) in zip(pontos, pontos[1:]):
        if x1 <= x <= x2:
            return y1 + (y2 - y1) / (x2 - x1) * (x - x1)
    return pontos[-1][1]


def eq10(P_inst):
    if P_inst >= 2:
        return 1000 * _interp(P_inst, SISTEMA) * P_inst
    return 1000 * _interp(P_inst, KIT) * P_inst + SERVICO_FIXO


def eq11(I, S_ano):
    return math.inf if S_ano <= 0 else 12 * I / S_ano


# Retorno mes a mes (itens 28 e 11, 06/10/2026), pelo TEXTO do calculo.py:
#   p(t) = percentual do ano civil do mes t; f(t) = Fio B x p(t);
#   G(t) = G_ano x (1 - d)^k, k = anos completos desde a instalacao;
#   teto(t) = Equacao 4 com f(t); economia(t) = min(G(t); teto(t)) x (T - f(t)) / 12;
#   retorno = mes em que a soma alcanca o custo, com a fracao do ultimo mes.
# Ate 300 meses (25 anos); alem disso, infinito.
PERCENTUAL_LEI = {2023: 0.15, 2024: 0.30, 2025: 0.45, 2026: 0.60, 2027: 0.75, 2028: 0.90}
PERCENTUAL_2029_EM_DIANTE = 1.00   # premissa provisoria (art. 17 ainda sem regra)
DEGRADACAO = 0.005                 # PINHO e GALDINO (2014), p. 132; EPE DEA-SEE 014/2023


# FASE 4, N2 (04/11/2026), pelo TEXTO do bloco "MANUTENCAO E TROCA DO
# INVERSOR" do calculo.py (premissas da EPE, NT EPE-DEA-SEE 014/2022, Tab. 2):
#   custo(t) = I x 1% / 12 todo mes + I x 15% no mes 120 (depois de 10 anos);
#   retorno = mes a partir do qual a soma de (economia - custo) FICA acima de I;
#   lucro em 25 anos = soma(economia - custo) - I;
#   pior caso: de 2029 em diante, f = cobranca maxima (no lugar de Fio B x 100%).
# Indicadores (bloco "RENDE MAIS QUE A POUPANCA?"): VPL a taxa real anual,
# convertida para mensal, fluxo no fim de cada mes; TIR pela taxa mensal que
# zera o VPL, anualizada.
OEM = 0.01
TROCA, MES_TROCA = 0.15, 120
POUPANCA = 0.0357


def fluxo_25(I, G_ano, C_meses, C_disp, T, F_B, ano0, mes0, d=DEGRADACAO, X=None):
    """(economia por mes, custos por mes, ano civil de cada mes), 300 meses."""
    eco, cus, anos, tetos, par = [], [], [], {}, {}
    for t in range(300):
        ano = ano0 + (mes0 - 1 + t) // 12
        if (ano, t // 12) not in par:          # igual dentro de (ano civil, k)
            p = PERCENTUAL_LEI.get(ano, PERCENTUAL_2029_EM_DIANTE)
            # pior caso: a cobranca nunca passa da tarifa (texto do calculo.py);
            # com f >= T a energia compensada nao economiza nada
            pior = X is not None and ano >= 2029
            f = min(X, T) if pior else F_B * p
            if pior and f >= T:
                par[(ano, t // 12)] = 0.0
            else:
                if f not in tetos:             # a Equacao 4 so depende de f
                    tetos[f] = eq4(C_meses, C_disp, T, f)[1]
                par[(ano, t // 12)] = max(min(G_ano * (1 - d) ** (t // 12), tetos[f]), 0.0) * (T - f) / 12
        eco.append(par[(ano, t // 12)])
        cus.append(I * OEM / 12 + (I * TROCA if t == MES_TROCA else 0.0))
        anos.append(ano)
    return eco, cus, anos


def retorno_que_fica(I, eco, cus):
    soma, pb = 0.0, math.inf
    for t, (e, c) in enumerate(zip(eco, cus)):
        liq = e - c
        antes, soma = soma, soma + liq
        if antes < I <= soma and liq > 0:
            pb = t + (I - antes) / liq
        elif soma < I:
            pb = math.inf
    return pb


def vpl_texto(I, liq, taxa):
    i = (1 + taxa) ** (1 / 12) - 1
    return -I + sum(v / (1 + i) ** (t + 1) for t, v in enumerate(liq))


def _blocos(liq):
    """Agrupa meses seguidos de fluxo igual: [(1o mes, quantos, valor)]."""
    blocos = []
    for t, v in enumerate(liq):
        if blocos and blocos[-1][2] == v:
            blocos[-1][1] += 1
        else:
            blocos.append([t, 1, v])
    return blocos


def _vpl_mensal(I, blocos, i):
    """VPL pela formula da serie uniforme em cada bloco (outra forma de somar
    que a do motor, de proposito): n parcelas v, a 1a no fim do mes s+1, valem
    v x q^(s+1) x (1 - q^n) / (1 - q), q = 1/(1+i)."""
    q = 1 / (1 + i)
    total = 0.0
    for s0, n, v in blocos:
        total += v * q ** (s0 + 1) * ((1 - q ** n) / (1 - q) if i > 0 else n)
    return total - I


def tir_texto(I, liq):
    """Bissecao pura (outro metodo que o do motor, de proposito): 40 passos
    entre 0% e 100% ao mes deixam a taxa mensal com erro < 1e-12."""
    if sum(liq) <= I:
        return None
    blocos = _blocos(liq)
    a, b = 0.0, 1.0
    for _ in range(40):
        m = (a + b) / 2
        a, b = (m, b) if _vpl_mensal(I, blocos, m) > 0 else (a, m)
    return (1 + (a + b) / 2) ** 12 - 1


def eq11_mes_a_mes(I, G_ano, C_meses, C_disp, T, F_B, ano0, mes0, d=DEGRADACAO,
                   fluxo=None):
    eco, cus, anos_civis = fluxo or fluxo_25(I, G_ano, C_meses, C_disp, T, F_B, ano0, mes0, d)
    pb = retorno_que_fica(I, eco, cus)
    ultimo = anos_civis[min(math.ceil(pb) - 1, 299)] if pb != math.inf else anos_civis[-1]
    anos = {}
    for e, a in zip(eco, anos_civis):
        if a <= ultimo:
            anos[a] = anos.get(a, 0.0) + e
    return pb, anos


# ---------------------------------------------------------------------------
# Fio B da concessionaria da capital: conferido contra a tabela da ANEEL
# ---------------------------------------------------------------------------
CAPITAL = {"AC": "EAC", "AL": "EQUATORIAL AL", "AP": "CEA", "AM": "Âmbar Amazonas",
           "BA": "COELBA", "CE": "ENEL CE", "DF": "Neoenergia Brasília", "ES": "EDP ES",
           "GO": "EQUATORIAL GO", "MA": "EQUATORIAL MA", "MT": "EMT", "MS": "EMS",
           "MG": "CEMIG-D", "PA": "EQUATORIAL PA", "PB": "EPB", "PR": "COPEL-DIS",
           "PE": "Neoenergia PE", "PI": "EQUATORIAL PI", "RJ": "LIGHT SESA",
           "RN": "COSERN", "RS": "CEEE-D", "RO": "ERO", "RR": "ÂMBAR ENERGIA RR",
           "SC": "CELESC", "SP": "ELETROPAULO", "SE": "ESE", "TO": "ETO"}


def fio_b_da_tabela_aneel():
    arq = os.path.join(PASTA, "fio_b_aneel_vigente_22-09-2026.csv")
    tab = {}
    with open(arq, encoding="utf-8-sig") as fh:
        next(fh)
        for linha in fh:
            partes = linha.rstrip("\n").split(";")
            tab[partes[0].strip()] = float(partes[2].replace(",", "."))
    # A tabela da ANEEL publica em R$/MWh; o motor guarda em R$/kWh com 6 casas.
    return {uf: round(tab[nome], 6) for uf, nome in CAPITAL.items()}


# ---------------------------------------------------------------------------
# Uma simulacao pelas equacoes do texto
# ---------------------------------------------------------------------------
def pelas_equacoes(C_meses, V_fat, C_fat, ligacao, uf, H, fio_b_uf, mediana,
                   ligacao_da_conta=None):
    C_disp = C_DISP.get(ligacao, C_DISP["bifasica"])     # sem tipo: bifasica
    # Item 7: com a troca para a trifasica, a conta informada ainda e da
    # ligacao de hoje, e a Equacao 2 usa o minimo dela.
    C_disp_conta = (C_DISP.get(ligacao_da_conta, C_DISP["bifasica"])
                    if ligacao_da_conta is not None else C_disp)
    T = eq2(V_fat, C_fat, C_disp_conta)
    F_B = fio_b_uf.get(uf, mediana)
    f, v = eq3(F_B, P_FIO_B_2026, T)
    H_ano = eq1(H)
    Ccm, C_comp = eq4(C_meses, C_disp, T, f)
    r = {"T": T, "f": f, "v": v, "H_ano": H_ano, "C_comp": C_comp, "Ccm": Ccm,
         "C_disp": C_disp, "C_meses": list(C_meses), "F_B": F_B}
    if C_comp <= 0:
        r["guarda"] = "sem_energia_compensavel"
        return r
    E_d, P_t = eq5(C_comp, H_ano)
    N, P_inst = eq6(P_t)
    r.update(E_d=E_d, P_t=P_t, N=N, P_inst=P_inst)
    return r


def completar(r, N_final, H):
    """Equacoes 7 a 11 com o N final (que a verificacao eletrica pode ter subido)."""
    P_inst = N_final * P_MOD
    P_inv = eq7(P_inst)
    G_m, G_ano = eq8(P_inst, H)
    E_comp, S_ano = eq9(G_ano, r["C_comp"], r["v"])
    I = eq10(P_inst)
    PB = eq11(I, S_ano)
    fluxo = fluxo_25(I, G_ano, r["C_meses"], r["C_disp"], r["T"], r["F_B"],
                     DATA_DA_CONFERENCIA.year, DATA_DA_CONFERENCIA.month)
    PB_mes, eco_anos = eq11_mes_a_mes(I, G_ano, r["C_meses"], r["C_disp"], r["T"], r["F_B"],
                                      DATA_DA_CONFERENCIA.year, DATA_DA_CONFERENCIA.month,
                                      fluxo=fluxo)
    eco, cus, _ = fluxo
    liq = [e - c for e, c in zip(eco, cus)]
    r.update(P_inst_final=P_inst, P_inv=P_inv, G_m=G_m, G_ano=G_ano,
             E_comp=E_comp, S_ano=S_ano, I=I, PB=PB, PB_mes=PB_mes, eco_anos=eco_anos,
             eco_25=sum(eco), custos_25=sum(cus), lucro_25=sum(liq) - I,
             vpl_poup=vpl_texto(I, liq, POUPANCA), tir=tir_texto(I, liq))
    return r


def pior_caso(r, X):
    """Lucro e TIR em 25 anos com a cobranca maxima X de 2029 em diante."""
    eco, cus, _ = fluxo_25(r["I"], r["G_ano"], r["C_meses"], r["C_disp"], r["T"], r["F_B"],
                           DATA_DA_CONFERENCIA.year, DATA_DA_CONFERENCIA.month, X=X)
    liq = [e - c for e, c in zip(eco, cus)]
    return sum(liq) - r["I"], tir_texto(r["I"], liq), retorno_que_fica(r["I"], eco, cus)


def perto(a, b, rel=1e-9, absol=1e-6):
    return abs(a - b) <= max(absol, rel * max(abs(a), abs(b)))


# ---------------------------------------------------------------------------
# FASE 4, ITEM 7 (10/11/2026): a ligacao eletrica do arranjo, pelo texto
# ---------------------------------------------------------------------------
# As quatro verificacoes da secao 3.4, com STRINGS EM PARALELO no mesmo MPPT
# (inversores trifasicos acima de 10 kW): no MPPT com k strings de L modulos,
#   k x Isc a 70 C <= curto maximo do MPPT;   k x Imp <= 1,10 x corrente do MPPT;
#   Imp <= 1,10 x limite por string (quando a folha da);
#   L x Voc a 0 C <= tensao maxima;   L x Vmp a 70 C >= piso do MPPT.
# Os LIMITES vem do catalogo (sao dados de folha); as CONTAS sao as do texto.
def _modulo_pelo_nome(nome):
    return next(m for m in calculo.CATALOGO_MODULOS.values() if m["nome"] == nome)


def arranjo_valido_pelo_texto(n, mod, inv, grupos, corrente_informada=None):
    """Lista de problemas do arranjo (vazia = valido pelo texto)."""
    erros = []
    voc_frio = mod["voc"] * (1 + mod["coef_voc"] / 100 * (0 - 25))
    vmp_quente = mod["vmp"] * (1 + (mod["coef_pmax"] - mod["coef_isc"]) / 100 * (70 - 25))
    isc_quente = mod["isc"] * (1 + mod["coef_isc"] / 100 * (70 - 25))
    if sum(g["strings"] * g["modulos_por_string"] for g in grupos) != n:
        erros.append("strings nao somam o numero de modulos")
    if len(grupos) > inv["mppts"]:
        erros.append("mais MPPTs do que o inversor tem")
    for g in grupos:
        k, L = g["strings"], g["modulos_por_string"]
        if k > inv["strings_por_mppt"]:
            erros.append(f"{k} strings num MPPT que aceita {inv['strings_por_mppt']}")
        if k * isc_quente > inv["corrente_max_curto_a"] + 1e-9:
            erros.append(f"curto do MPPT {k * isc_quente:.2f} A acima de {inv['corrente_max_curto_a']}")
        if k * mod["imp"] / inv["corrente_max_entrada_a"] - 1 > 0.10 + 1e-12:
            erros.append(f"corrente do MPPT {k * mod['imp']:.2f} A acima da tolerancia")
        if inv.get("corrente_max_string_a") and mod["imp"] / inv["corrente_max_string_a"] - 1 > 0.10 + 1e-12:
            erros.append("corrente da string acima do limite por string")
        if L * voc_frio > inv["tensao_max_v"] + 1e-9:
            erros.append(f"tensao a frio {L * voc_frio:.0f} V acima de {inv['tensao_max_v']}")
        if L * vmp_quente < inv["mppt_min_v"] - 1e-9:
            erros.append(f"tensao a quente {L * vmp_quente:.0f} V abaixo do MPPT")
    if corrente_informada is not None and grupos:
        k = max(g["strings"] for g in grupos)
        if not perto(corrente_informada, k * mod["imp"]):
            erros.append(f"corrente do MPPT informada {corrente_informada} != {k} x Imp")
    return erros


def _grupos_do_laudo(laudo):
    return laudo.get("mppts_usados") or [{"strings": 1, "modulos_por_string": L}
                                         for L in laudo["modulos_por_string"]]


def conferir_arranjo(res):
    """Confere, pelo texto, a ligacao de cada inversor mostrado no resultado."""
    erros = []
    if not res.get("arranjo_aprovado") or not res.get("inversor_modelo"):
        return erros
    mod = _modulo_pelo_nome(res["modulo_modelo"])
    trifasico = res["potencia_inversor_kw"] > LIMITE_MONOFASICO
    if trifasico:
        mostrados = res.get("inversores_por_tensao") or []
        tensoes = sorted(x["tensao_rede"] for x in mostrados)
        if tensoes != ["127/220 V", "220/380 V"]:
            erros.append(f"degrau trifasico sem um modelo por tensao: {tensoes}")
        pares = [(x["modelo"], x["laudo"]) for x in mostrados]
    else:
        if res.get("inversores_por_tensao"):
            erros.append("modelos por tensao num degrau monofasico")
        pares = [(res["inversor_modelo"], res["arranjo_laudo"])]
    for nome, laudo in pares:
        inv = calculo.CATALOGO_INVERSORES[nome]
        if abs(inv["potencia_kw"] - res["potencia_inversor_kw"]) > 1e-9:
            erros.append(f"{nome} nao e do degrau de {res['potencia_inversor_kw']} kW")
        erros += [f"{nome}: {e}" for e in arranjo_valido_pelo_texto(
            res["numero_paineis"], mod, inv, _grupos_do_laudo(laudo),
            laudo.get("corrente_operacao_mppt_a"))]
    return erros


# Inversores FICTICIOS, so para o teste (potencia 99 kW: nunca entram num
# degrau da grade). Existem para que os erros plantados das strings em paralelo
# tenham onde aparecer: com o Jinko e os inversores reais, 2 strings em
# paralelo sempre cabem na corrente, e um motor que esquecesse de somar as
# correntes daria o mesmo resultado.
FICTICIOS = {
    "FICTICIO-3-STRINGS": {   # 3 strings de Jinko passam do MPPT; 2 cabem
        "potencia_kw": 99.0, "familia": "teste", "classe_corrente": "alta",
        "tensao_rede": "127/220 V", "mppts": 2, "strings_por_mppt": 3,
        "corrente_max_entrada_a": 32.0, "corrente_max_curto_a": 40.0,
        "tensao_max_v": 800.0, "mppt_min_v": 200.0, "mppt_max_v": 800.0,
        "tensao_partida_v": 200.0},
    "FICTICIO-LIMITE-STRING": {   # 12 A por string: o Jinko (13,62 A) nunca cabe
        "potencia_kw": 99.0, "familia": "teste", "classe_corrente": "alta",
        "tensao_rede": "127/220 V", "mppts": 2, "strings_por_mppt": 2,
        "corrente_max_entrada_a": 40.0, "corrente_max_curto_a": 60.0,
        "corrente_max_string_a": 12.0,
        "tensao_max_v": 800.0, "mppt_min_v": 200.0, "mppt_max_v": 800.0,
        "tensao_partida_v": 200.0},
}
FICTICIO_DEGRAU_12 = {   # um 3o modelo no degrau de 12 kW que NENHUM arranjo aprova
    "potencia_kw": 12.0, "familia": "teste", "classe_corrente": "baixa",
    "tensao_rede": "220/380 V", "mppts": 1, "strings_por_mppt": 1,
    "corrente_max_entrada_a": 5.0, "corrente_max_curto_a": 6.0,
    "tensao_max_v": 1100.0, "mppt_min_v": 140.0, "mppt_max_v": 1000.0,
    "tensao_partida_v": 160.0}


def testes_strings_em_paralelo():
    """Testes diretos da ligacao com strings em paralelo e da regra dos dois
    modelos por degrau trifasico. Devolve a lista de falhas."""
    falhas = []
    cat = calculo.CATALOGO_INVERSORES
    cat.update(FICTICIOS)
    try:
        paralelos = [n for n, inv in cat.items() if inv["strings_por_mppt"] > 1]
        for chave, mod in calculo.CATALOGO_MODULOS.items():
            for nome in paralelos:
                for n in range(1, 81):
                    laudo = calculo.verificar_compatibilidade(n, chave, nome)
                    if laudo["aprovado"]:
                        falhas += [f"paralelo {chave}/{nome}/{n}: {e}" for e in arranjo_valido_pelo_texto(
                            n, mod, cat[nome], _grupos_do_laudo(laudo),
                            laudo.get("corrente_operacao_mppt_a"))]
        # O ficticio de 3 strings precisa aprovar ate 2 x 2 x 14 = 56 Jinko e
        # reprovar acima (a 3a string em paralelo passaria da corrente).
        for n, esperado in ((40, True), (56, True), (57, False), (70, False)):
            if calculo.verificar_compatibilidade(n, "jinko_600", "FICTICIO-3-STRINGS")["aprovado"] != esperado:
                falhas.append(f"FICTICIO-3-STRINGS com {n} Jinko: esperado aprovado={esperado}")
        if any(calculo.verificar_compatibilidade(n, "jinko_600", "FICTICIO-LIMITE-STRING")["aprovado"]
               for n in range(1, 81)):
            falhas.append("FICTICIO-LIMITE-STRING aprovou o Jinko acima do limite por string")
    finally:
        for nome in FICTICIOS:
            cat.pop(nome, None)
    # Degrau trifasico: o arranjo so vale se passar em TODOS os modelos dele
    cat["FICTICIO-12K"] = FICTICIO_DEGRAU_12
    try:
        escolha = calculo.escolher_inversor_compativel(21, "jinko_600", 12.0)
        if escolha["inversor"] is not None:
            falhas.append("degrau de 12 kW aprovado com um modelo do degrau reprovando")
    finally:
        cat.pop("FICTICIO-12K", None)
    escolha = calculo.escolher_inversor_compativel(21, "jinko_600", 12.0)
    if escolha["inversor"] is None or len(escolha.get("inversores_por_tensao") or []) != 2:
        falhas.append("degrau de 12 kW real sem os dois modelos aprovados")
    return falhas


def comparar(entrada, fio_b_uf, mediana, motor=None):
    """Roda o motor e as equacoes; devolve a lista de divergencias."""
    motor = motor or simulacao.simular
    C_meses, V_fat, C_fat, ligacao, uf, H, modo = entrada
    _ENTRADA["uf"], _ENTRADA["hsp"] = uf, H
    media = sum(C_meses) / 12
    kwargs = dict(cidade="teste", consumo_medio_kwh=media, valor_fatura_reais=V_fat,
                  tipo_ligacao=ligacao, consumo_da_fatura_kwh=C_fat)
    if modo == "mensal":
        kwargs["consumo_por_mes_kwh"] = list(C_meses)
    res = motor(**kwargs)
    eq = pelas_equacoes(C_meses, V_fat, C_fat, ligacao, uf, H, fio_b_uf, mediana)
    erros = []
    # FASE 4, ITEM 7 (10/11/2026), pelo texto: acima de 10 kW de inversor a
    # casa precisa de ligacao trifasica, e a conta e feita com o minimo da
    # trifasica (100 kWh), qualquer que seja a ligacao informada.
    trocou = False
    if "P_inst" in eq and ligacao != "trifasica":
        p_inv = eq7(eq["P_inst"])
        if p_inv is None or p_inv > LIMITE_MONOFASICO:
            eq = pelas_equacoes(C_meses, V_fat, C_fat, "trifasica", uf, H, fio_b_uf, mediana,
                                ligacao_da_conta=ligacao or "bifasica")
            trocou = True
    if not res.get("erro") and bool(res.get("ligacao_trocada_para_trifasica")) != trocou:
        erros.append(f"ligacao: motor trocou para trifasica={res.get('ligacao_trocada_para_trifasica')}"
                     f" texto={trocou}")

    def conf(nome, a, b):
        if a is None or b is None or not perto(a, b):
            erros.append(f"{nome}: motor={a} texto={b}")

    if eq.get("guarda") == "sem_energia_compensavel":
        if res.get("motivo_inviabilidade") != "sem_energia_compensavel":
            erros.append("guarda de consumo sem compensacao nao acionada")
        return erros, res, eq
    if res.get("motivo_inviabilidade") == "sem_energia_compensavel":
        erros.append("motor acionou a guarda sem energia compensavel e o texto nao")
        return erros, res, eq

    if res.get("motivo_inviabilidade") == "sem_arranjo_valido":
        # Pelo texto: acima de 10 kW nao ha degrau. O sistema pedido pela
        # energia (Eq. 6) precisa estar acima do maior degrau.
        if eq7(eq["P_inst"]) is not None:
            erros.append(f"guarda acima de 25 kW acionada com P_inst={eq['P_inst']:.2f} kWp, "
                         f"que a grade atende")
        return erros, res, eq

    N_final = res["numero_paineis"]
    if res.get("motivo_inviabilidade") != "payback_acima_da_vida_util":
        if res["modulo_modelo"] != "Jinko Tiger Neo JKM600N-72HL4-V":
            erros.append(f"modulo escolhido: {res['modulo_modelo']}")
        # Equacoes 1 a 6
        conf("T (Eq. 2)", res["tarifa_calculada"], eq["T"])
        conf("v (Eq. 3)", res["valor_economizado_por_kwh"], eq["v"])
        conf("H_ano (Eq. 1)", res["hsp_medio_anual"], eq["H_ano"])
        conf("C_comp (Eq. 4)", res["consumo_compensavel_anual_kwh"], eq["C_comp"])
        conf("P_t (Eqs. 5)", res["potencia_teorica_kwp"], eq["P_t"])
        if N_final != eq["N"] and not (res["arranjo_subiu_pelo_minimo_eletrico"]
                                       and N_final > eq["N"]):
            erros.append(f"N (Eq. 6): motor={N_final} texto={eq['N']}")
        completar(eq, N_final, H)
        conf("P_inst (Eq. 6)", res["potencia_instalada_kwp"], eq["P_inst_final"])
        conf("P_inv (Eq. 7)", res["potencia_inversor_kw"], eq["P_inv"])
        conf("C_disp (minimo da ligacao)", res["piso_disponibilidade_kwh"], eq["C_disp"])
        erros += conferir_arranjo(res)
        for (mes, g_motor), g_txt in zip(res["geracao_por_mes_kwh"].items(), eq["G_m"]):
            conf(f"G_{mes} (Eq. 8)", g_motor, g_txt)
        conf("G_ano (Eq. 8)", res["geracao_anual_kwh"], eq["G_ano"])
        conf("E_comp (Eq. 9)", res["energia_compensavel_anual_kwh"], eq["E_comp"])
        conf("S_ano (Eq. 9)", res["economia_anual"], eq["S_ano"])
        conf("I (Eq. 10)", res["custo_total_sistema"], eq["I"])
        conf("PB simples (Eq. 11)", res["payback_simples_meses"], eq["PB"])
        conf("PB mes a mes", res["payback_meses"], eq["PB_mes"])
        anos_motor = {l["ano"]: l["economia"] for l in res["retorno_por_ano"]}
        if sorted(anos_motor) != sorted(eq["eco_anos"]):
            erros.append(f"anos do retorno: motor={sorted(anos_motor)} texto={sorted(eq['eco_anos'])}")
        else:
            for ano, eco in eq["eco_anos"].items():
                if not perto(anos_motor[ano], eco, rel=1e-9, absol=1e-6):
                    ultimo = ano == max(eq["eco_anos"])   # o texto para no mes do retorno
                    if not (ultimo and anos_motor[ano] >= eco - 1e-6):
                        erros.append(f"economia de {ano}: motor={anos_motor[ano]} texto={eco}")
        # Propriedades que valem para qualquer entrada
        if res["geracao_anual_kwh"] < res["consumo_compensavel_anual_kwh"] - 1e-6:
            erros.append("PROPRIEDADE: geracao anual abaixo do consumo compensavel")
        if not perto(res["energia_compensavel_anual_kwh"], res["consumo_compensavel_anual_kwh"]):
            erros.append("PROPRIEDADE: energia compensada diferente de C_comp")
        minimo = eq["C_disp"] * eq["T"]
        for mes, fat in res["fatura_por_mes_reais"].items():
            if fat < minimo - 1e-6:
                erros.append(f"PROPRIEDADE: fatura de {mes} abaixo do minimo")
        for (mes, comp), ccm in zip(res["compensado_por_mes_kwh"].items(), eq["Ccm"]):
            if comp > ccm + 1e-6:
                erros.append(f"PROPRIEDADE: compensado de {mes} acima do C_comp,m")
        if not perto(sum(res["compensado_por_mes_kwh"].values()),
                     res["energia_compensavel_anual_kwh"], rel=1e-6, absol=0.05):
            erros.append("PROPRIEDADE: serie mensal nao fecha com a Eq. 9")
        if eq["PB_mes"] > 300:
            erros.append("PROPRIEDADE: payback acima de 25 anos exibido")
        # Propriedades do retorno mes a mes (itens 28 e 11)
        if res["payback_meses"] < res["payback_simples_meses"] - 1e-9:
            erros.append("PROPRIEDADE: retorno mes a mes MENOR que o simples "
                         "(com tarifa constante, a economia nunca sobe)")
        linhas = res["retorno_por_ano"]
        if not perto(linhas[0]["economia_por_mes"], res["economia_mensal_media"]):
            erros.append("PROPRIEDADE: 1o ano do retorno diferente da economia de hoje")
        # Fase 4, N2: com a troca do inversor a soma pode passar do custo, cair
        # e passar de novo; a tabela termina no ano civil do mes do retorno.
        mes_ret = math.ceil(res["payback_meses"]) - 1
        ano_ret = res["retorno_inicio_ano"] + (res["retorno_inicio_mes"] - 1 + mes_ret) // 12
        if linhas[-1]["acumulado"] < res["custo_total_sistema"] - 1e-6 or linhas[-1]["ano"] != ano_ret:
            erros.append("PROPRIEDADE: a tabela do retorno nao termina no ano em que se paga")
        soma = 0.0
        for l in linhas:
            soma += l["economia"] - l["custos"]
            if not perto(soma, l["acumulado"], rel=1e-9, absol=1e-6):
                erros.append(f"PROPRIEDADE: acumulado de {l['ano']} nao fecha")
        # FASE 4, N2 (04/11/2026): longo prazo (25 anos) e pior caso
        lp = res["longo_prazo"]
        conf("economia em 25 anos", lp["economia"], eq["eco_25"])
        conf("manutencao e troca em 25 anos", lp["custos"], eq["custos_25"])
        conf("lucro em 25 anos", lp["lucro"], eq["lucro_25"])
        conf("a mais que a poupanca (VPL)", lp["vpl_poupanca"], eq["vpl_poup"])
        if (lp["tir"] is None) != (eq["tir"] is None) or (
                lp["tir"] is not None and not perto(lp["tir"], eq["tir"], rel=1e-6, absol=1e-7)):
            erros.append(f"TIR: motor={lp['tir']} texto={eq['tir']}")
        X = res.get("cobranca_maxima_pos_2029")
        lpp = res.get("longo_prazo_pior")
        if (X is None) != (lpp is None):
            erros.append(f"pior caso: cobranca={X} e resultado={lpp is not None}")
        elif X is not None:
            lucro_p, tir_p, pb_p = pior_caso(eq, X)
            conf("lucro em 25 anos (pior caso)", lpp["lucro"], lucro_p)
            if (lpp["tir"] is None) != (tir_p is None) or (
                    tir_p is not None and not perto(lpp["tir"], tir_p, rel=1e-6, absol=1e-7)):
                erros.append(f"TIR (pior caso): motor={lpp['tir']} texto={tir_p}")
            if not (pb_p == lpp["payback_meses"] == math.inf or perto(pb_p, lpp["payback_meses"])):
                erros.append(f"retorno (pior caso): motor={lpp['payback_meses']} texto={pb_p}")
            if X > eq["F_B"] and lpp["lucro"] > lp["lucro"] + 1e-6:
                erros.append("PROPRIEDADE: pior caso com lucro MAIOR que o caso do Fio B")
    else:
        # Guarda dos 25 anos: o motor devolve so os numeros principais.
        if N_final != eq["N"] and N_final < eq["N"]:
            erros.append(f"N (Eq. 6) na guarda: motor={N_final} texto={eq['N']}")
        completar(eq, N_final, H)
        conf("P_inst (Eq. 6) na guarda", res["potencia_instalada_kwp"], eq["P_inst_final"])
        conf("I (Eq. 10) na guarda", res["custo_total_sistema"], eq["I"])
        conf("S_ano/12 (Eq. 9) na guarda", res["economia_mensal_media"], eq["S_ano"] / 12)
        conf("PB simples (Eq. 11) na guarda", res["payback_simples_meses"], eq["PB"])
        if res["payback_meses"] != math.inf:
            erros.append(f"guarda: retorno do motor deveria ser infinito, veio {res['payback_meses']}")
        conf("economia em 25 anos na guarda", res["economia_25_anos"], sum(eq["eco_anos"].values()))
        if eq["PB_mes"] <= 300:
            erros.append("guarda de 25 anos acionada com retorno mes a mes de "
                         f"{eq['PB_mes']:.1f} meses")
    return erros, res, eq


# ---------------------------------------------------------------------------
# Os casos e a varredura
# ---------------------------------------------------------------------------
# HSP de Guaira extraidos da tela (o_que_falta_fazer, T17). Para as outras
# cidades, perfis sinteticos com a HSP media de cada uma (so o formato muda).
HSP_GUAIRA = [6.49, 5.93, 5.56, 4.60, 3.43, 3.02, 3.34, 4.17, 4.71, 5.31, 6.29, 6.47]


def perfil(media, amplitude, fase=0.0):
    base = [1 + amplitude * math.cos(2 * math.pi * (m - fase) / 12) for m in range(12)]
    k = media * 365 / sum(b * d for b, d in zip(base, DIAS))
    return [k * b for b in base]


PERFIS = {
    "BA": perfil(4236 / (2.4 * 0.8 * 365), 0.10),
    "PR": HSP_GUAIRA,
    "AM": perfil(7369 / (5.4 * 0.8 * 365), 0.05, 6),
    "SP": perfil(2702 / (1.8 * 0.8 * 365), 0.20),
    "MT": perfil(3691 / (2.4 * 0.8 * 365), 0.08, 3),
    "SC": perfil(4.3, 0.30),
    "TO": perfil(5.6, 0.12, 8),
    None: perfil(5.0, 0.15),
}

CASOS_OFICIAIS = [  # (cidade, UF, consumo, economia/mes, custo, payback em meses, modulos, inversor)
    ("Bom Jesus da Lapa", "BA", 300, 162.08, 7881.60, 48.6, 4, 2.0),
    ("Guaira", "PR", 300, 186.38, 9150.00, 49.1, 5, 2.5),
    ("Manaus", "AM", 550, 355.49, 13513.50, 38.0, 9, 5.0),
    ("Campinas", "SP", 180, 97.50, 6590.80, 67.6, 3, 1.5),
    ("Cuiaba", "MT", 300, 168.28, 7881.60, 46.8, 4, 2.0),
]


def varredura():
    ligacoes = [None, "monofasica", "bifasica", "trifasica"]
    for uf in ["BA", "PR", "AM", "SP", "MT", "SC", "TO", None]:
        for lig in ligacoes:
            for tarifa in (0.60, 0.75, 0.95):
                for consumo in range(20, 1660, 20):
                    C = [float(consumo)] * 12
                    yield (C, consumo * tarifa, consumo, lig, uf, PERFIS[uf], "media")
                    # modo historico: sazonalidade de +-35%, fatura de um mes qualquer
                    Cm = [consumo * (1 + 0.35 * math.sin(2 * math.pi * m / 12)) for m in range(12)]
                    yield (Cm, Cm[4] * tarifa, Cm[4], lig, uf, PERFIS[uf], "mensal")
                    # REVISAO GERAL (07/10/2026): conta de um mes ABAIXO do
                    # minimo (ferias), cobrada pelo minimo - a media e outra.
                    piso = C_DISP.get(lig, C_DISP["bifasica"])
                    for c_fat in (10.0, 0.6 * piso):
                        yield (C, max(c_fat, piso) * tarifa, c_fat, lig, uf, PERFIS[uf], "media")
            # FASE 4, ITEM 7 (10/11/2026): de 1.700 a 4.700 kWh/mes, os degraus
            # trifasicos (12 a 25 kW) e o teto de 25 kW. Passo maior, para o
            # tempo da conferencia nao explodir.
            for consumo in range(1700, 4701, 100):
                C = [float(consumo)] * 12
                yield (C, consumo * tarifa, consumo, lig, uf, PERFIS[uf], "media")
                Cm = [consumo * (1 + 0.35 * math.sin(2 * math.pi * m / 12)) for m in range(12)]
                yield (Cm, Cm[4] * tarifa, Cm[4], lig, uf, PERFIS[uf], "mensal")


def rodar(motor=None, mostrar=True, parar_em=None):
    # FASE 4, N2 (04/11/2026): com o longo prazo (fluxo de 25 anos, TIR, pior
    # caso) cada simulacao ficou ~4x mais lenta, e a conferencia inteira passaria
    # de 30 min (o limite da tarefa automatica do GitHub). Nos ERROS PLANTADOS
    # basta saber que o erro aparece: a varredura para depois de parar_em
    # divergencias (a contagem sai como "pelo menos N"). A varredura principal
    # (parte 2) continua inteira.
    fio_b_uf = fio_b_da_tabela_aneel()
    mediana = sorted(fio_b_uf.values())[13]
    falhas, n, guardas = [], 0, {}
    # 0) a tabela do motor e a da ANEEL
    for uf, valor in fio_b_uf.items():
        if not perto(calculo.FIO_B_POR_UF[uf]["fio_b"], valor, rel=1e-5):
            falhas.append(f"Fio B de {uf}: motor={calculo.FIO_B_POR_UF[uf]['fio_b']} ANEEL={valor}")
    if not perto(calculo.FIO_B_PADRAO_REAIS_POR_KWH, mediana, rel=1e-5):
        falhas.append("mediana do Fio B diferente")
    # 0b) item 7: strings em paralelo e os dois modelos por degrau trifasico
    falhas += testes_strings_em_paralelo()
    # 1) casos resolvidos a mao (numeros da tela de 23/09/2026)
    for nome, uf, consumo, eco, custo, pb, n_mod, inv in CASOS_OFICIAIS:
        H = PERFIS[uf]
        eq = pelas_equacoes([float(consumo)] * 12, consumo * 0.75, consumo, "bifasica", uf,
                            H, fio_b_uf, mediana)
        completar(eq, eq["N"], H)
        for rotulo, a, b, tol in (("economia/mes", eq["S_ano"] / 12, eco, 0.005),
                                  ("custo", eq["I"], custo, 0.005),
                                  ("payback", eq["PB"], pb, 0.05)):
            if abs(a - b) > tol:
                falhas.append(f"caso {nome}, {rotulo}: equacoes={a:.2f} tela={b:.2f}")
        if eq["N"] != n_mod or eq["P_inv"] != inv:
            falhas.append(f"caso {nome}: N={eq['N']} P_inv={eq['P_inv']}")
        erros, _, _ = comparar(([float(consumo)] * 12, consumo * 0.75, consumo, "bifasica",
                                uf, H, "media"), fio_b_uf, mediana, motor)
        falhas += [f"caso {nome}: {e}" for e in erros]
    # 2) varredura
    for entrada in varredura():
        n += 1
        erros, res, _ = comparar(entrada, fio_b_uf, mediana, motor)
        chave = res.get("motivo_inviabilidade", "normal")
        guardas[chave] = guardas.get(chave, 0) + 1
        if erros:
            falhas.append(f"{entrada[3]}/{entrada[4]}/{entrada[6]}/"
                          f"{sum(entrada[0])/12:.0f} kWh: " + "; ".join(erros[:3]))
            if parar_em and len(falhas) >= parar_em:
                break
    if mostrar:
        print(f"Simulacoes da varredura: {n}")
        print(f"Resultados: {guardas}")
        print(f"Divergencias: {len(falhas)}")
        for f_ in falhas[:15]:
            print("  ", f_)
    return falhas


# ---------------------------------------------------------------------------
# 3) Erros plantados: cada um precisa ser detectado
# ---------------------------------------------------------------------------
PARAR_EM = 50


def erros_plantados():
    orig = {n: getattr(calculo, n) for n in ("compensavel_do_mes", "hsp_medio_anual",
                                            "energia_diaria", "potencia_inversor_comercial",
                                            "custo_sistema_greener", "payback_meses",
                                            "valor_economizado_por_kwh", "geracao_estimada")}
    orig_ret = simulacao.retorno_mes_a_mes
    orig_pct = calculo.percentual_fio_b_vigente
    orig_sim = {n: getattr(simulacao, n) for n in ("hsp_medio_anual", "energia_diaria",
                                                  "valor_economizado_por_kwh",
                                                  "custo_sistema_greener", "payback_meses",
                                                  "geracao_estimada", "numero_paineis",
                                                  "consumo_faturado_da_conta")}

    def regra_antiga(C, P=0.0, T=None, f=0.0):             # minimo descontado em energia
        return max(C - P, 0.0) if P else max(C, 0.0)

    def sem_minimo(C, P=0.0, T=None, f=0.0):
        return max(C, 0.0)

    orig_par = calculo.verificar_compatibilidade_paralelo
    orig_uma_vez = simulacao._simular_uma_vez

    def _com_inversor_alterado(alterar):
        """Roda a verificacao com strings em paralelo com o inversor alterado."""
        def verificar(n, chave, nome):
            inv = calculo.CATALOGO_INVERSORES[nome]
            guardado = dict(inv)
            alterar(inv)
            try:
                return orig_par(n, chave, nome)
            finally:
                inv.clear()
                inv.update(guardado)
        return verificar

    def _sem_somar(inv):          # corrente do MPPT como se fosse de UMA string
        inv["corrente_max_entrada_a"] *= inv["strings_por_mppt"]
        inv["corrente_max_curto_a"] *= inv["strings_por_mppt"]

    def _sem_limite_string(inv):
        inv.pop("corrente_max_string_a", None)

    def _trifasico_com_um_modelo(n, chave, kw):     # aprova se UM modelo passa
        for nome in calculo.modelos_no_degrau(kw):
            laudo = calculo.verificar_compatibilidade(n, chave, nome)
            if laudo["aprovado"]:
                return {"inversor": nome, "laudo": laudo, "reprovados": [],
                        "minimo_de_modulos_sugerido": None,
                        "inversores_por_tensao": [
                            {"modelo": m, "tensao_rede": calculo.CATALOGO_INVERSORES[m]["tensao_rede"],
                             "familia": "", "laudo": calculo.verificar_compatibilidade(n, chave, m)}
                            for m in calculo.modelos_no_degrau(kw)]}
        return {"inversor": None, "laudo": None, "reprovados": [],
                "minimo_de_modulos_sugerido": None}

    mutacoes = {
        "regra antiga do minimo (em energia)": ("calculo", "compensavel_do_mes", regra_antiga),
        "minimo ignorado": ("calculo", "compensavel_do_mes", sem_minimo),
        "HSP pela media simples": ("simulacao", "hsp_medio_anual",
                                   lambda H: sum(H) / len(H)),
        "ano de 360 dias": ("simulacao", "energia_diaria", lambda c: c / 360),
        "Fio B sem o percentual": ("simulacao", "valor_economizado_por_kwh",
                                   lambda T, fb, p: T - fb),
        "servico fixo esquecido abaixo de 2 kWp": (
            "simulacao", "custo_sistema_greener",
            lambda P: dict(orig["custo_sistema_greener"](P),
                           custo_total=orig["custo_sistema_greener"](P)["custo_total"]
                           - (3520 if P < 2 else 0))),
        "payback em anos no lugar de meses": ("simulacao", "payback_meses",
                                              lambda I, e: I / (e * 12) if e > 0 else math.inf),
        # Itens 28 e 11 (06/10/2026): os erros que a conta nova pode ter
        "retorno com o Fio B de hoje para sempre": (
            "simulacao", "retorno_mes_a_mes",
            lambda *a, **k: orig_ret(*a, **dict(k, percentual_fixo=calculo.percentual_fio_b_vigente()))),
        "retorno sem a degradacao": (
            "simulacao", "retorno_mes_a_mes",
            lambda *a, **k: orig_ret(*a, **dict(k, degradacao_anual=0.0))),
        # Fase 4, N2 (04/11/2026): os erros que o longo prazo pode ter
        "retorno sem a manutencao": (
            "simulacao", "retorno_mes_a_mes",
            lambda *a, **k: orig_ret(*a, **dict(k, oem_anual=0.0))),
        "troca do inversor esquecida": (
            "simulacao", "retorno_mes_a_mes",
            lambda *a, **k: orig_ret(*a, **dict(k, troca_inversor=0.0))),
        "pior caso calculado com o Fio B": (
            "simulacao", "retorno_mes_a_mes",
            lambda *a, **k: orig_ret(*a, **dict(k, cobranca_pos_2029=None))),
        "escalada do Fio B um ano adiantada": (
            "calculo", "percentual_fio_b_vigente",
            lambda ano=None: orig_pct(ano if ano is None else ano + 1)),
        "geracao sem a TD": ("simulacao", "geracao_estimada",
                             lambda P, h, td, d: P * h * d),
        "modulos arredondados para baixo": ("simulacao", "numero_paineis",
                                            lambda pt, wp: max(math.floor(pt / (wp / 1000)), 1)),
        # Revisao geral (07/10/2026): a Equacao 2 sem o minimo da conta
        "tarifa pelo consumo da conta abaixo do minimo": (
            "simulacao", "consumo_faturado_da_conta", lambda c, p=0.0: c),
        "inversor arredondado para baixo": (
            "calculo", "potencia_inversor_comercial",
            lambda kw: (lambda abaixo: {"potencia_kw": abaixo, "potencia_calculada_kw": kw,
                                        "fora_da_grade": False})(
                max([g for g in calculo.GRADE_INVERSORES_KW if g <= kw] or [calculo.GRADE_INVERSORES_KW[0]]))
            if kw <= 10 else orig["potencia_inversor_comercial"](kw)),
        # Fase 4, item 7 (10/11/2026): inversores trifasicos e strings em paralelo
        "strings em paralelo sem somar a corrente": (
            "calculo", "verificar_compatibilidade_paralelo", _com_inversor_alterado(_sem_somar)),
        "limite de corrente por string ignorado": (
            "calculo", "verificar_compatibilidade_paralelo", _com_inversor_alterado(_sem_limite_string)),
        "degrau trifasico aprovado com um modelo so": (
            "calculo", "_escolher_inversor_trifasico", _trifasico_com_um_modelo),
        "ligacao trifasica esquecida acima de 10 kW": (
            "simulacao", "_precisa_de_trifasica", lambda r, f: False),
        # Achado da revisao do item 7 (10/11/2026): com a troca para a
        # trifasica, a tarifa de uma conta abaixo do minimo saia dividida pelo
        # minimo da trifasica (100 kWh), e nao pelo da ligacao de hoje.
        "tarifa da troca pelo minimo da trifasica": (
            "simulacao", "_simular_uma_vez",
            lambda **k: orig_uma_vez(**dict(k, piso_da_conta_kwh=None))),
    }
    detectadas = 0
    for nome, (modulo, funcao, nova) in mutacoes.items():
        if funcao == "percentual_fio_b_vigente":
            # so a escalada FUTURA: o percentual de hoje continua certo
            hoje = DATA_DA_CONFERENCIA.year
            nova = (lambda f: (lambda ano=None: orig_pct(hoje) if ano in (None, hoje) else f(ano)))(nova)
        alvo = calculo if modulo == "calculo" else simulacao
        antiga = getattr(alvo, funcao)
        setattr(alvo, funcao, nova)
        try:
            falhas = rodar(mostrar=False, parar_em=PARAR_EM)
        except Exception as e:                                   # quebra tambem e deteccao
            falhas = [f"excecao: {e}"]
        finally:
            setattr(alvo, funcao, antiga)
        ok = len(falhas) > 0
        detectadas += ok
        conta = (f"pelo menos {len(falhas)}" if len(falhas) >= PARAR_EM else str(len(falhas)))
        print(f"  {'DETECTADO' if ok else 'NAO DETECTADO'}: {nome} ({conta} divergencias)")
    for n_, f_ in orig.items():
        setattr(calculo, n_, f_)
    for n_, f_ in orig_sim.items():
        setattr(simulacao, n_, f_)
    print(f"Erros plantados detectados: {detectadas} de {len(mutacoes)}")
    return detectadas == len(mutacoes)


if __name__ == "__main__":
    print("=== 1 e 2: casos resolvidos a mao e varredura ===")
    falhas = rodar()
    print("\n=== 3: erros plantados ===")
    todos = erros_plantados()
    print("\nRESULTADO:", "OK" if (not falhas and todos) else "HA PROBLEMAS")
