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
Motor de calculo - plataforma web de dimensionamento fotovoltaico
residencial (TCC de Engenharia Eletrica, Uninter, 2026).

Este arquivo contem a logica de calculo: as Equacoes 1 a 11 da secao 3.3
do artigo, a verificacao eletrica da secao 3.4 (Equacao 12 e Quadro 1) e o
catalogo de modulos e inversores. Ele nao busca dados na internet: isso e
feito pelo geocoding.py (cidade -> coordenadas e estado) e pelo
nasa_power.py (HSP de cada mes). A tela fica no app.py e na pasta
templates.

NUMERACAO DAS EQUACOES: os comentarios deste arquivo usam a numeracao do
desenvolvimento, anterior ao artigo. Cada cabecalho de equacao indica o
numero correspondente no artigo, e o README.md traz a tabela completa.

COMENTARIOS HISTORICOS: muitos comentarios registram as correcoes feitas
durante o desenvolvimento (T1 a T20) e os numeros medidos na epoca, com a
data. Os numeros oficiais sao os do artigo; um numero datado aqui pode ser
de uma versao anterior do motor.

Cada "def" abaixo e uma FUNCAO: um pedacinho de codigo com nome, que recebe
uns valores de entrada (entre parenteses) e devolve 1 resultado (return).
Pensa nela como uma calculadora: voce aperta os botoes (entrada) e ela
devolve o numero (saida) - sem voce precisar saber o que ela fez por dentro
toda vez que for usar.

Para rodar: salve este arquivo numa pasta e, no terminal (dentro dessa
pasta), digite:
    python calculo.py        (Windows)
    python3 calculo.py       (Mac/Linux)
"""

import csv
import itertools
import json
import math
import os
import statistics
from datetime import date


# ---------------------------------------------------------------------
# Calendario do ano (correcao T17, 14/09/2026)
# ---------------------------------------------------------------------
# POR QUE ESTA TABELA VEIO PARAR AQUI. Ela morava so no simulacao.py, e
# era usada apenas pela Equacao 5 (geracao mes a mes). Enquanto isso a
# Equacao 1 tirava a media do HSP dividindo por 12, e a Equacao 2 dividia
# o consumo por 30. Ou seja: TRES equacoes do mesmo motor trabalhavam com
# tres calendarios diferentes - um de 365 dias, um sem calendario nenhum
# e um de 360 dias.
#
# Era o Achado B da auditoria de 14/09/2026: o sistema era dimensionado
# para um ano de 360 dias e avaliado num ano de 365, o que produzia
# um excesso sistematico de +1,39% em QUALQUER cidade - e
# +1,39% nao depende de clima nem de latitude, e so calendario.
#
# A tabela mora AQUI, no motor, pelo mesmo motivo da tabela do Fio B (T3a)
# e da tabela do piso de disponibilidade (T7): quando uma grandeza tem
# duas definicoes no mesmo programa, elas divergem. O simulacao.py passou
# a importar daqui em vez de manter a propria copia.
#
# Ano civil de 365 dias, sem bissexto. O ano bissexto acrescentaria 0,27%
# a geracao de 1 ano em 4, efeito menor que o arredondamento de um painel
# inteiro, e adotar 365 fixo mantem o resultado reproduzivel - que e o que
# o trabalho precisa. Limitacao declarada.
DIAS_NO_MES = {
    "Jan": 31, "Fev": 28, "Mar": 31, "Abr": 30, "Mai": 31, "Jun": 30,
    "Jul": 31, "Ago": 31, "Set": 30, "Out": 31, "Nov": 30, "Dez": 31,
}
NOMES_MESES = list(DIAS_NO_MES.keys())
DIAS_NO_ANO = sum(DIAS_NO_MES.values())          # 365


def _lista_de_dias(hsp_mensais):
    """
    Devolve os dias de cada mes na MESMA ordem dos valores recebidos.

    Aceita tanto uma lista de 12 numeros (ordem Jan..Dez, que e como a
    NASA POWER devolve) quanto um dicionario com os meses como chave.
    """
    if isinstance(hsp_mensais, dict):
        return [DIAS_NO_MES[mes] for mes in hsp_mensais], list(hsp_mensais.values())
    return [DIAS_NO_MES[mes] for mes in NOMES_MESES[:len(hsp_mensais)]], list(hsp_mensais)


# ---------------------------------------------------------------------
# Equacao 1 - HSP medio anual (no artigo: Equacao 1)
# ---------------------------------------------------------------------
# CORRECAO T17 (14/09/2026), Achado C da auditoria: a media deixou de ser
# simples e passou a ser PONDERADA pelos dias de cada mes.
#
# O ERRO: somar os 12 valores e dividir por 12 faz fevereiro, com 28 dias,
# pesar exatamente igual a janeiro, com 31. Mas a Equacao 5 multiplica o
# HSP de cada mes pelos dias REAIS daquele mes na hora de calcular a
# geracao. As duas equacoes discordavam sobre quanto vale um mes.
#
# O QUE DECIDE O TAMANHO E O SINAL DO ERRO, em qualquer cidade do mundo:
# a diferenca entre as duas medias e uma soma de pesos fixos que da zero,
# e o peso de fevereiro e 4,14 vezes o de um mes de 31 dias. Na pratica o
# erro inteiro depende de UMA pergunta: o HSP de fevereiro esta acima ou
# abaixo da media anual daquela cidade? Acima, a media simples
# superestima; abaixo, subestima.
#
# MAGNITUDE MEDIDA, varrendo o espaco de perfis em vez de uma amostra de
# cidades (por isso vale para qualquer cidade, nao so para as testadas):
#   - qualquer perfil sazonal, amplitude ate 40%, todas as fases:
#     erro entre -0,23% e +0,23%
#   - 200.000 perfis totalmente aleatorios, sem forma sazonal:
#     erro entre -0,89% e +1,07%
#   - limite matematico absoluto, HSP de 2,0 a 7,5 h/dia:
#     erro entre -1,17% e +1,45%
# As duas ultimas faixas sao fisicamente impossiveis (exigiriam fevereiro
# no teto e todos os meses de 31 dias no chao) e servem so para provar que
# o erro nao passa de 1,5% nem forcando.
#
# CUIDADO AO ESCREVER O ARTIGO: esta correcao muda o HSP medio EXIBIDO na
# tela e o valor citado como Equacao 1. A plataforma passou a devolver os
# dois numeros (ver simulacao.py), para o texto poder mostrar a diferenca.
def hsp_medio_anual(hsp_mensais):
    """
    HSP medio anual em h/dia, ponderado pelos dias de cada mes.

    Recebe os 12 valores mensais (lista na ordem Jan..Dez, como a NASA
    POWER devolve, ou dicionario com os meses como chave).

    A ponderacao usa o MESMO calendario da Equacao 5. E isso que garante
    que a potencia calculada na Equacao 3 e a geracao calculada na
    Equacao 5 falem do mesmo ano.
    """
    dias, valores = _lista_de_dias(hsp_mensais)
    return sum(v * d for v, d in zip(valores, dias)) / sum(dias)


def hsp_medio_anual_simples(hsp_mensais):
    """
    Media SIMPLES dos 12 valores - o que a plataforma fazia ate o T17.

    Nao alimenta calculo nenhum. Fica no arquivo por dois motivos: o
    artigo descreve a evolucao do motor, e a tela precisa poder mostrar
    de quanto foi a diferenca entre o modelo antigo e o corrigido.
    """
    _, valores = _lista_de_dias(hsp_mensais)
    return sum(valores) / len(valores)


# ---------------------------------------------------------------------
# Equacao 2 - Energia diaria necessaria (no artigo: Equacao 5, 1a parte)
# ---------------------------------------------------------------------
# CORRECAO T16 (14/09/2026): mudou O QUE ENTRA aqui.
# Ate aqui esta funcao recebia o consumo medio mensal CHEIO. Agora ela
# recebe o consumo COMPENSAVEL, ou seja, ja descontada a parte que o
# custo de disponibilidade impede de abater. Esse numero sai de
# consumo_alvo_dimensionamento(), mais abaixo neste arquivo, onde o
# motivo esta escrito por extenso.
#
# Em uma linha: dimensionar para o consumo cheio manda comprar painel que
# gera energia que a propria plataforma declara incompensavel na mesma
# tela - ou seja, painel com retorno financeiro garantidamente zero.
#
# CORRECAO T17 (14/09/2026), Achado B: mudou a CONTA.
# Era "consumo mensal / 30". Doze meses de 30 dias dao 360, mas a
# Equacao 5 soma a geracao sobre 365. O sistema era dimensionado para um
# ano de 360 dias e avaliado num ano de 365, o que dava um excesso de
# +1,3889% - numero identico em qualquer cidade, porque e so calendario.
# Agora a entrada e o consumo compensavel do ANO, dividido pelos 365 dias
# do mesmo calendario que a Equacao 5 usa.
def energia_diaria(consumo_compensavel_anual_kwh):
    """
    Energia que o sistema precisa entregar por dia, em kWh/dia.

    Recebe o consumo COMPENSAVEL DO ANO (Equacao 2a) e divide pelos dias
    do ano, usando o mesmo calendario da Equacao 5.

    POR QUE ISSO FECHA O MOTOR. Com esta correcao a cadeia inteira passa
    a usar um calendario so, e com isso nasce uma garantia que antes era
    folga acidental: a geracao anual do sistema dimensionado NUNCA fica
    abaixo do consumo compensavel. A demonstracao cabe em tres linhas.
    Na potencia teorica exata, geracao = P x TD x soma(HSP_mes x dias) =
    P x TD x HSP_ponderado x 365, que por construcao da exatamente o
    consumo compensavel do ano. Como a Equacao 4 arredonda os paineis
    sempre para CIMA, a potencia instalada e sempre maior ou igual a
    teorica, logo a geracao e sempre maior ou igual ao alvo. Vale para
    qualquer cidade e qualquer perfil de HSP, sem depender de medicao.
    """
    return consumo_compensavel_anual_kwh / DIAS_NO_ANO


# ---------------------------------------------------------------------
# Equacao 3 - Potencia do sistema (teorica, ainda continua/fracionada)
# (no artigo: Equacao 5, 2a parte)
# ---------------------------------------------------------------------
def potencia_sistema_teorica(energia_diaria_kwh, hsp_medio, td=0.80):
    """
    Potencia (kWp) necessaria, antes de arredondar para paineis inteiros.

    A conta nao mudou no T16 - o que mudou foi o alvo que chega nela pela
    Equacao 2. Antes esta equacao dimensionava o sistema para o consumo
    cheio; agora dimensiona para a parcela do consumo que de fato pode
    ser abatida pela compensacao.
    """
    return energia_diaria_kwh / (hsp_medio * td)


# ---------------------------------------------------------------------
# Equacao 4 - Numero de paineis (arredondado para cima) (no artigo: Equacao 6)
# ---------------------------------------------------------------------
def numero_paineis(potencia_sistema_kwp, potencia_painel_wp):
    """
    potencia_painel_wp = potencia de 1 painel, em Wp (ex: 550).
    Usa math.ceil (arredondar para CIMA) porque nao existe "meio painel".
    """
    potencia_painel_kwp = potencia_painel_wp / 1000
    return math.ceil(potencia_sistema_kwp / potencia_painel_kwp)


# ---------------------------------------------------------------------
# Potencia REAL instalada (depois de arredondar os paineis)
# ---------------------------------------------------------------------
def potencia_instalada(n_paineis, potencia_painel_wp):
    """
    Como so da pra instalar paineis inteiros, a potencia REAL do sistema
    e (numero de paineis x potencia de 1 painel) - normalmente um pouco
    MAIOR que a potencia teorica da Equacao 3. E essa potencia real que
    usamos daqui pra frente (geracao, custo, etc), nao a teorica.
    """
    return n_paineis * (potencia_painel_wp / 1000)


# ---------------------------------------------------------------------
# Equacao 5 - Geracao estimada em um periodo (mes ou ano) (no artigo: Equacao 8)
# ---------------------------------------------------------------------
def geracao_estimada(potencia_instalada_kwp, hsp, td, dias):
    """Serve tanto pra 1 mes (dias=~30) quanto pro ano (dias=365)."""
    return potencia_instalada_kwp * hsp * td * dias


# ---------------------------------------------------------------------
# Equacao 6 - Tarifa total da concessionaria (no artigo: Equacao 2)
# ---------------------------------------------------------------------
def tarifa_total(valor_fatura_reais, consumo_do_mes_kwh):
    return valor_fatura_reais / consumo_do_mes_kwh


# ---------------------------------------------------------------------
# O consumo que a conta de fato COBROU (revisao geral, parte 1, 07/10/2026)
# ---------------------------------------------------------------------
# A Equacao 6 divide o valor da conta pelo consumo da mesma conta. Isso so
# vale quando o consumo daquele mes ficou acima do custo de disponibilidade:
# sem paineis, a distribuidora fatura o MAIOR entre o consumo medido e o
# minimo (art. 290, caput, e art. 291 da REN ANEEL 1.000/2021 - a mesma
# regra que faturas_mensais_com_creditos(), abaixo, usa para a conta sem
# paineis). Num mes de ferias com 20 kWh numa casa bifasica, a conta cobra
# 50 kWh; dividir por 20 infla a tarifa 2,5 vezes, e com ela a economia - e,
# pelo art. 655-I, ate o numero de paineis muda (Guaira, 300 kWh/mes: 4 em
# vez de 5). Por isso o divisor da Equacao 6 passa por esta funcao.
def consumo_faturado_da_conta(consumo_da_conta_kwh, piso_disponibilidade_kwh=0.0):
    """
    kWh que a conta cobrou: o maior entre o consumo medido e o minimo da
    ligacao (30, 50 ou 100 kWh). Acima do minimo, devolve o proprio consumo,
    e a Equacao 6 fica exatamente como antes.
    """
    return max(consumo_da_conta_kwh, piso_disponibilidade_kwh or 0.0)


# ---------------------------------------------------------------------
# Percentual do Fio B cobrado sobre a energia compensada
# (Lei 14.300/2022 - entra na Equacao 7, logo abaixo)
# ---------------------------------------------------------------------
# CORRECAO T3a (13/09/2026): ate aqui o percentual era um numero escrito a
# mao (0,60, referente a 2026), tanto no teste deste arquivo quanto no
# valor padrao de simular(), no simulacao.py. A Lei 14.300/2022 estabelece
# uma escalada ANUAL da cobranca do Fio B sobre a energia compensada, para
# sistemas conectados a partir de 07/01/2023. Com o numero fixo, a
# plataforma nao ficaria apenas imprecisa em 2027: ficaria ERRADA,
# prometendo uma economia maior do que a pessoa de fato teria.
#
# A tabela mora AQUI, no motor, e em nenhum outro lugar. O simulacao.py
# apenas consulta - ele nao precisa saber nada sobre a lei.
#
# LIMITACAO DECLARADA (vai para o artigo): de 2029 em diante a Lei manda
# aplicar a regra do art. 17, que cobra TODAS as componentes tarifarias
# nao associadas ao custo da energia (nao so o Fio B), abatidos beneficios
# ainda a serem valorados pelo CNPE e pela ANEEL. Os 100% do Fio B
# adotados aqui sao uma PREMISSA PROVISORIA, e NAO conservadora: a
# cobranca real tende a ser maior. Nao afeta 2026 (60%, art. 27, IV).
# Correcao de comentario feita na auditoria de 23/09/2026; o texto
# anterior chamava a premissa de conservadora, o que estava errado.
TABELA_PERCENTUAL_FIO_B = {
    2023: 0.15,
    2024: 0.30,
    2025: 0.45,
    2026: 0.60,
    2027: 0.75,
    2028: 0.90,
}
PERCENTUAL_FIO_B_A_PARTIR_DE_2029 = 1.00


def data_de_hoje():
    """
    Devolve a data de hoje.

    Fica isolada numa funcao de proposito: e o UNICO ponto do sistema que
    consulta o relogio. Assim o simulacao.py nao precisa saber de datas, e
    quem quiser reproduzir um resultado antigo passa a data na mao para as
    funcoes que aceitam (fio_b_do_estado) ou o ano (percentual_fio_b_vigente).
    Antes de 01/10/2026 esta funcao era o ano_referencia_fio_b() abaixo, que
    so devolvia o ano; a vigencia da tarifa precisa do dia e do mes tambem.
    """
    return date.today()


def ano_referencia_fio_b():
    """
    Ano usado como referencia regulatoria quando ninguem informa um.
    """
    return data_de_hoje().year


def percentual_fio_b_vigente(ano=None):
    """
    Devolve o percentual do Fio B cobrado no ano informado (0,60 = 60%).

    Sem argumento, usa o ano corrente - e por isso que a plataforma deixa
    de envelhecer em silencio. Informar o ano na mao continua valendo, e e
    o que mantem os 5 casos de validacao reproduziveis depois da virada do
    ano: basta chamar com ano=2026 para reproduzir os resultados do TCC.
    """
    if ano is None:
        ano = ano_referencia_fio_b()
    if ano in TABELA_PERCENTUAL_FIO_B:
        return TABELA_PERCENTUAL_FIO_B[ano]
    primeiro_ano = min(TABELA_PERCENTUAL_FIO_B)
    if ano < primeiro_ano:
        # Antes de 2023 nao havia cobranca escalonada; devolver o primeiro
        # degrau evita que uma data errada de maquina zere o Fio B e
        # produza uma economia otimista demais.
        return TABELA_PERCENTUAL_FIO_B[primeiro_ano]
    return PERCENTUAL_FIO_B_A_PARTIR_DE_2029


# ---------------------------------------------------------------------
# Valor do Fio B por kWh, POR ESTADO (correcao T19, 22/09/2026)
# ---------------------------------------------------------------------
# ATE AQUI o valor em R$/kWh do Fio B era um numero escrito a mao (0.20)
# direto na assinatura de simular(), no simulacao.py, sem fonte nenhuma.
# So o PERCENTUAL cobrado sobre ele (tabela acima) tinha base legal; o
# valor em si nao tinha - era a pendencia C17 do roteiro do artigo.
#
# POR QUE NAO EXISTE "O" FIO B DO BRASIL. O Fio B (componente TUSD_FioB
# da estrutura tarifaria) e homologado pela ANEEL para CADA distribuidora,
# em resolucao propria. Nas 98 distribuidoras com tarifa residencial
# vigente em 22/09/2026 ele vai de R$ 0,02 a R$ 0,61/kWh.
#
# FONTE (primaria): ANEEL, Portal de Dados Abertos, conjunto "Componentes
# Tarifarias", arquivos 2025 e 2026 (gerados em 17/09/2026). Filtro:
# DscComponenteTarifario = TUSD_FioB, subgrupo B1, modalidade
# Convencional, subclasse Residencial, "Tarifa de Aplicacao", tarifa
# vigente em 22/09/2026. O conjunto publica em R$/MWh; aqui esta em R$/kWh
# (dividido por 1.000). Valores SEM impostos.
#
# O CRITERIO: a plataforma ja sabe o ESTADO do usuario, porque a
# geocodificacao da cidade o devolve (geocoding.py). Para cada estado,
# adota-se o Fio B da concessionaria que atende a CAPITAL. E um criterio
# objetivo, verificavel e sem escolha arbitraria: toda capital tem uma
# distribuidora so.
#
# POR QUE ESTADO E NAO MACRORREGIAO, e isto foi MEDIDO nas 45
# concessionarias com tarifa vigente, antes de decidir (erro = diferenca
# entre o Fio B real da concessionaria e o valor que o modelo usaria):
#
#                                erro medio      pior caso
#   valor nacional unico         R$ 0,066/kWh    R$ 0,171/kWh
#   mediana da macrorregiao      R$ 0,043/kWh    R$ 0,213/kWh
#   distribuidora da capital     R$ 0,017/kWh    R$ 0,136/kWh
#
# A macrorregiao melhora a media mas PIORA o pior caso: o Norte vai de
# R$ 0,17 (Amazonas) a R$ 0,44 (Tocantins), e Manaus - um dos cinco casos
# de validacao - receberia R$ 0,39 contra R$ 0,17 reais. O estado reduz o
# erro medio a cerca de um quarto do valor nacional.
#
# LIMITACOES DECLARADAS (vao para o artigo, secao 3.5):
#  (a) nos estados atendidos por mais de uma concessionaria, quem mora
#      fora da area da capital recebe o valor da capital. Os maiores
#      desvios medidos sao no RJ (Enel RJ, R$ 0,361, contra Light,
#      R$ 0,225) e no RS (RGE, R$ 0,300, contra CEEE, R$ 0,187). As
#      cooperativas (permissionarias) ficam fora da tabela;
#  (b) os valores da ANEEL sao SEM impostos, enquanto a tarifa da
#      Equacao 6 sai da fatura, COM impostos. Subtrair um Fio B sem
#      imposto de uma tarifa com imposto subestima um pouco a cobranca e
#      deixa a economia levemente otimista. O ICMS muda de estado para
#      estado, por isso a correcao nao e modelada - e declarada;
#  (c) a tabela e um retrato de 22/09/2026: cada distribuidora reajusta
#      a tarifa uma vez por ano, em datas diferentes.
#
# Quem passar fio_b na chamada de simular() continua mandando, do mesmo
# jeito que o percentual e o piso de disponibilidade - e assim que os 5
# casos de validacao antigos seguem reproduziveis (fio_b=0.20).
#
# CONFERENCIA DE 01/10/2026 (item 25 do backlog). A tabela foi conferida
# contra os arquivos "componentes-tarifarias-2025" e "-2026" dos Dados
# Abertos da ANEEL GERADOS EM 27/09/2026, dez dias mais novos que os de
# 17/09/2026 que a montaram: os 27 valores e as 27 vigencias sao IGUAIS.
# Nenhuma distribuidora de capital foi reajustada no intervalo, por isso
# nada mudou aqui. Duas observacoes da conferencia:
#  (a) a API de consulta (CKAN datastore) do conjunto estava INCOMPLETA
#      naquele dia: devolvia 5.560 das 2.993.205 linhas do arquivo de 2025,
#      de uma unica distribuidora. Quem conferir por ela vai achar que 9
#      capitais (DF, GO, RS, PI, PA, AC, RO, AP e CE) desapareceram. A
#      conferencia foi feita nos arquivos completos (formato Parquet);
#  (b) Rondonia tem duas tarifas vigentes ao mesmo tempo no conjunto
#      (R$ 0,321813/kWh, REH n. 3.560/2025, e R$ 0,404016/kWh, REH
#      n. 3.320/2026, as duas terminando em 12/12/2026). A tabela usa a de
#      inicio de vigencia mais recente, que e a segunda.
# PROXIMOS VENCIMENTOS: DF e GO em 21/10/2026; RS em 21/11; PI em 01/12;
# AC e RO em 12/12; PA em 31/12/2026.
DATA_REFERENCIA_FIO_B = "22/09/2026"
DATA_ULTIMA_CONFERENCIA_FIO_B = "01/10/2026"
FONTE_FIO_B = ("ANEEL, Dados Abertos, Componentes Tarifarias 2025 e 2026 "
               "(TUSD_FioB, B1 residencial convencional)")

FIO_B_POR_UF = {
    "AC": {"distribuidora": "EAC", "capital": "Rio Branco", "fio_b": 0.367630,
           "resolucao": "REH n. 3.318/2026", "vigencia": "2026-08-26 a 2026-12-12"},
    "AL": {"distribuidora": "EQUATORIAL AL", "capital": "Maceió", "fio_b": 0.311333,
           "resolucao": "REH n. 3.584/2026", "vigencia": "2026-05-03 a 2027-05-02"},
    "AP": {"distribuidora": "CEA", "capital": "Macapá", "fio_b": 0.388855,
           "resolucao": "resolucao nao informada no conjunto", "vigencia": "2026-04-13 a 2027-05-24"},
    "AM": {"distribuidora": "Âmbar Amazonas", "capital": "Manaus", "fio_b": 0.172760,
           "resolucao": "REH n. 3.588/2026", "vigencia": "2026-05-26 a 2027-05-25"},
    "BA": {"distribuidora": "COELBA", "capital": "Salvador", "fio_b": 0.349535,
           "resolucao": "REH n. 3.578/2026", "vigencia": "2026-04-22 a 2027-04-21"},
    "CE": {"distribuidora": "ENEL CE", "capital": "Fortaleza", "fio_b": 0.283714,
           "resolucao": "REH n. 3.324/2026", "vigencia": "2026-08-26 a 2027-04-21"},
    "DF": {"distribuidora": "Neoenergia Brasília", "capital": "Brasília", "fio_b": 0.133270,
           "resolucao": "REH n. 3.542/2025", "vigencia": "2026-01-01 a 2026-10-21"},
    "ES": {"distribuidora": "EDP ES", "capital": "Vitória", "fio_b": 0.209152,
           "resolucao": "REH n. 3.600/2026", "vigencia": "2026-08-07 a 2027-08-06"},
    "GO": {"distribuidora": "EQUATORIAL GO", "capital": "Goiânia", "fio_b": 0.291858,
           "resolucao": "REH n. 3.544/2025", "vigencia": "2026-01-01 a 2026-10-21"},
    "MA": {"distribuidora": "EQUATORIAL MA", "capital": "São Luís", "fio_b": 0.325144,
           "resolucao": "REH n. 3.604/2026", "vigencia": "2026-08-28 a 2027-08-27"},
    "MT": {"distribuidora": "EMT", "capital": "Cuiabá", "fio_b": 0.315104,
           "resolucao": "REH n. 3.581/2026", "vigencia": "2026-04-08 a 2027-04-07"},
    "MS": {"distribuidora": "EMS", "capital": "Campo Grande", "fio_b": 0.346126,
           "resolucao": "REH n. 3.582/2026", "vigencia": "2026-04-22 a 2027-04-21"},
    "MG": {"distribuidora": "CEMIG-D", "capital": "Belo Horizonte", "fio_b": 0.268193,
           "resolucao": "REH n. 3.589/2026", "vigencia": "2026-05-28 a 2027-05-27"},
    "PA": {"distribuidora": "EQUATORIAL PA", "capital": "Belém", "fio_b": 0.385824,
           "resolucao": "REH n. 3.507/2025", "vigencia": "2026-01-01 a 2026-12-31"},
    "PB": {"distribuidora": "EPB", "capital": "João Pessoa", "fio_b": 0.236108,
           "resolucao": "REH n. 3.603/2026", "vigencia": "2026-08-28 a 2027-08-27"},
    "PR": {"distribuidora": "COPEL-DIS", "capital": "Curitiba", "fio_b": 0.214536,
           "resolucao": "REH n. 3.592/2026", "vigencia": "2026-06-24 a 2027-06-23"},
    "PE": {"distribuidora": "Neoenergia PE", "capital": "Recife", "fio_b": 0.260678,
           "resolucao": "REH n. 3.583/2026", "vigencia": "2026-04-29 a 2027-04-28"},
    "PI": {"distribuidora": "EQUATORIAL PI", "capital": "Teresina", "fio_b": 0.364877,
           "resolucao": "REH n. 3.555/2025", "vigencia": "2026-01-01 a 2026-12-01"},
    "RJ": {"distribuidora": "LIGHT SESA", "capital": "Rio de Janeiro", "fio_b": 0.225346,
           "resolucao": "REH n. 3.571/2026", "vigencia": "2026-03-15 a 2027-03-14"},
    "RN": {"distribuidora": "COSERN", "capital": "Natal", "fio_b": 0.266996,
           "resolucao": "REH n. 3.573/2026", "vigencia": "2026-04-22 a 2027-04-21"},
    "RS": {"distribuidora": "CEEE-D", "capital": "Porto Alegre", "fio_b": 0.187301,
           "resolucao": "REH n. 3.547/2025", "vigencia": "2026-01-01 a 2026-11-21"},
    "RO": {"distribuidora": "ERO", "capital": "Porto Velho", "fio_b": 0.404016,
           "resolucao": "REH n. 3.320/2026", "vigencia": "2026-08-26 a 2026-12-12"},
    "RR": {"distribuidora": "ÂMBAR ENERGIA RR", "capital": "Boa Vista", "fio_b": 0.200130,
           "resolucao": "REH n. 3.565/2026", "vigencia": "2026-01-25 a 2027-01-24"},
    "SC": {"distribuidora": "CELESC", "capital": "Florianópolis", "fio_b": 0.132790,
           "resolucao": "REH n. 3.602/2026", "vigencia": "2026-08-22 a 2027-08-21"},
    "SP": {"distribuidora": "ELETROPAULO", "capital": "São Paulo", "fio_b": 0.212077,
           "resolucao": "REH n. 3.596/2026", "vigencia": "2026-07-04 a 2027-07-03"},
    "SE": {"distribuidora": "ESE", "capital": "Aracaju", "fio_b": 0.254991,
           "resolucao": "REH n. 3.575/2026", "vigencia": "2026-04-22 a 2027-04-21"},
    "TO": {"distribuidora": "ETO", "capital": "Palmas", "fio_b": 0.441478,
           "resolucao": "REH n. 3.323/2026", "vigencia": "2026-08-26 a 2027-08-25"},
}

# Quando o estado nao e identificado, usa-se a MEDIANA dos 27 valores
# estaduais da tabela acima. Com 27 valores a mediana e um valor real da
# tabela (hoje, o de Minas Gerais), e a mediana nao se deixa puxar pelos
# extremos (Santa Catarina e Distrito Federal embaixo, Tocantins em cima).
FIO_B_PADRAO_REAIS_POR_KWH = statistics.median(
    d["fio_b"] for d in FIO_B_POR_UF.values())


def _partes_da_vigencia(texto):
    """
    Quebra "2026-06-24 a 2027-06-23" nas duas datas, em ISO.

    Devolve (inicio, fim) como texto, ou (None, None) se o formato nao for
    o esperado - um campo mal digitado na tabela nao pode derrubar o
    calculo, so deixa de mostrar a vigencia na tela.
    """
    partes = [p.strip() for p in (texto or "").split(" a ")]
    if len(partes) != 2 or not all(len(p) == 10 for p in partes):
        return None, None
    return partes[0], partes[1]


def _data_br(iso):
    """Converte "2027-06-23" em "23/06/2027" (None continua None)."""
    if not iso:
        return None
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def vigencia_expirada(fim_iso, hoje=None):
    """
    Diz se a tarifa ja passou do fim da vigencia homologada pela ANEEL.

    Acrescentado em 01/10/2026 (passo 6). Cada distribuidora reajusta a
    tarifa uma vez por ano, em data propria: a tabela FIO_B_POR_UF e um
    retrato, e quando a vigencia vence o valor envelhece em silencio. Com
    este campo a tela avisa, em vez de apresentar um numero velho como se
    fosse o atual. Os reajustes sobem o Fio B na maioria dos casos, ou
    seja, a economia mostrada tende a ficar um pouco OTIMISTA.

    Sem fim de vigencia (campo vazio), devolve False: nao da para afirmar
    que venceu, e inventar aviso tambem engana.
    """
    if not fim_iso:
        return False
    if hoje is None:
        hoje = data_de_hoje()
    return hoje.isoformat() > fim_iso


def fio_b_do_estado(uf=None, hoje=None):
    """
    Devolve o Fio B (R$/kWh) que a plataforma usa para o estado informado.

    Recebe a sigla do estado ("PR", "BA"...) e, opcionalmente, a data a usar
    como "hoje" (para reproduzir um resultado antigo). Devolve:
      fio_b              - o valor em R$/kWh
      uf                 - a sigla usada, ou None
      distribuidora      - a concessionaria de referencia, ou None
      resolucao          - a resolucao homologatoria da ANEEL, ou None
      vigencia_inicio    - inicio da vigencia, "2026-06-24", ou None
      vigencia_fim       - fim da vigencia, "2027-06-23", ou None
      vigencia_inicio_br - a mesma data em "24/06/2026", para a tela
      vigencia_fim_br    - idem
      vigencia_expirada  - True quando hoje ja passou do fim da vigencia
      estado_identificado- False quando a sigla veio vazia ou desconhecida
                           e a mediana nacional foi aplicada

    O campo estado_identificado existe pelo mesmo motivo do tipo de ligacao
    (T7): quando e False, o resultado nasceu de uma premissa e a tela
    precisa dizer isso. Os campos de vigencia (01/10/2026, passo 6) existem
    pelo mesmo motivo: a tela mostra ATE QUANDO o valor usado vale.

    NA MEDIANA (estado nao identificado) nao existe uma vigencia unica: o
    valor sai das 27 tarifas da tabela, cada uma com a sua. Nesse caso as
    datas vem None e vigencia_expirada e True se QUALQUER tarifa da tabela
    ja venceu - porque basta uma para a mediana poder estar velha.
    """
    chave = (uf or "").strip().upper()
    if chave in FIO_B_POR_UF:
        ref = FIO_B_POR_UF[chave]
        inicio, fim = _partes_da_vigencia(ref["vigencia"])
        return {"fio_b": ref["fio_b"], "uf": chave,
                "distribuidora": ref["distribuidora"],
                "resolucao": ref["resolucao"],
                "vigencia_inicio": inicio,
                "vigencia_fim": fim,
                "vigencia_inicio_br": _data_br(inicio),
                "vigencia_fim_br": _data_br(fim),
                "vigencia_expirada": vigencia_expirada(fim, hoje),
                "estado_identificado": True}
    alguma_venceu = any(
        vigencia_expirada(_partes_da_vigencia(d["vigencia"])[1], hoje)
        for d in FIO_B_POR_UF.values())
    return {"fio_b": FIO_B_PADRAO_REAIS_POR_KWH, "uf": None,
            "distribuidora": None, "resolucao": None,
            "vigencia_inicio": None, "vigencia_fim": None,
            "vigencia_inicio_br": None, "vigencia_fim_br": None,
            "vigencia_expirada": alguma_venceu,
            "estado_identificado": False}


# ---------------------------------------------------------------------
# Fio B pela distribuidora do MUNICIPIO (passo 7, 02/10/2026)
# ---------------------------------------------------------------------
# POR QUE ISTO EXISTE. A tabela FIO_B_POR_UF acima adota, para cada estado, o
# Fio B da distribuidora que atende a CAPITAL. E um criterio objetivo, mas
# erra em todo municipio atendido por outra empresa - e o proprio
# recalculo_fio_b.py ja declarava o caso de Campinas, atendida pela CPFL
# Paulista e nao pela distribuidora da capital de SP.
#
# MEDIDO EM 01/10/2026, cruzando os dados abertos da ANEEL: dos 5.571
# municipios, 4.247 ficariam com o MESMO valor de hoje, 823 passariam a usar o
# valor da distribuidora que de fato os atende, e 501 caem nas regras de
# desempate abaixo.
#
# DE ONDE VEM O DADO: dos dois arquivos que o atualizar_dados_aneel.py grava -
# fio_b_por_distribuidora.csv (o Fio B de cada CNPJ) e
# static/distribuidoras_por_municipio.json (quem atende cada codigo IBGE). Os
# dois sao reconstruidos a partir do Portal de Dados Abertos da ANEEL. Se
# faltarem, estiverem corrompidos ou vierem vazios, NADA QUEBRA: o motor volta
# para a tabela embutida acima, e a tela declara qual das duas esta em uso.
#
# A ORDEM DE ESCOLHA (decisoes da aluna, 01 e 02/10/2026):
#   1. a distribuidora que a PESSOA escolheu na tela, quando ela escolheu;
#   2. a unica que atende o municipio, quando so ha uma (91% dos casos);
#   3. quando ha mais de uma e a pessoa nao sabe qual e a dela: a de MAIOR
#      Fio B entre as que atendem aquele municipio. E a escolha conservadora -
#      maior Fio B significa menor economia -, e usa so valores de empresas que
#      realmente atendem a cidade. ISTO FOI MEDIDO: em 74% dos 481 municipios
#      com mais de uma distribuidora, a empresa da capital do estado NEM
#      ATENDE o municipio (Araruama-RJ, por exemplo, tem ENEL RJ e CERAL
#      Araruama; a Light, da capital, nao passa la). Por isso cair no valor do
#      estado seria pior do que parece;
#   4. municipio sem nenhuma distribuidora com tarifa vigente (14 casos em
#      01/10/2026, cooperativas de SC cuja vigencia venceu em 29/09): volta
#      para a tabela do estado, declarada na tela.
_ARQUIVO_FIO_B_DISTRIBUIDORAS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fio_b_por_distribuidora.csv")
_ARQUIVO_MAPA_DISTRIBUIDORAS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static",
    "distribuidoras_por_municipio.json")


# FASE 4, N2 (04/11/2026): guardada a parte, para nao mudar os dicionarios do
# Fio B que a tela ja usa. {cnpj: R$/kWh ou None}.
COBRANCA_MAXIMA_POR_DISTRIBUIDORA = {}


def _carregar_fio_b_por_distribuidora():
    """
    Le fio_b_por_distribuidora.csv. Devolve {cnpj: {...}} ou {} se nao der.

    Nunca levanta excecao: arquivo que falta, linha torta ou numero invalido
    apenas reduzem a tabela - no limite, para vazia, e o motor usa a embutida.
    """
    tabela = {}
    try:
        with open(_ARQUIVO_FIO_B_DISTRIBUIDORAS, encoding="utf-8-sig", newline="") as f:
            for linha in csv.DictReader(f, delimiter=";"):
                try:
                    cnpj = str(linha["cnpj"]).strip().zfill(14)
                    valor = float(str(linha["fio_b_reais_por_kwh"]).replace(",", "."))
                except (KeyError, ValueError, AttributeError):
                    continue
                if not cnpj or valor <= 0:
                    continue
                inicio = str(linha.get("inicio_vigencia") or "").strip() or None
                fim = str(linha.get("fim_vigencia") or "").strip() or None
                # FASE 4, N2 (04/11/2026): cobranca maxima (TUSD + TE do SCEE),
                # coluna nova e opcional; em branco ou torta = None.
                try:
                    maxima = float(str(linha.get("cobranca_maxima_reais_por_kwh")
                                       or "").replace(",", "."))
                    maxima = maxima if maxima > valor else None
                except ValueError:
                    maxima = None
                COBRANCA_MAXIMA_POR_DISTRIBUIDORA[cnpj] = maxima
                tabela[cnpj] = {
                    "cnpj": cnpj,
                    "distribuidora": str(linha.get("distribuidora") or "").strip(),
                    "fio_b": valor,
                    "vigencia_inicio": inicio,
                    "vigencia_fim": fim,
                    "resolucao": str(linha.get("resolucao_homologatoria") or "").strip(),
                }
    except (OSError, csv.Error):
        return {}
    return tabela


def _carregar_mapa_distribuidoras():
    """
    Le static/distribuidoras_por_municipio.json. Devolve {ibge: [cnpj, ...]}
    ou {} se nao der. Tambem nunca levanta excecao.
    """
    try:
        with open(_ARQUIVO_MAPA_DISTRIBUIDORAS, encoding="utf-8") as f:
            conteudo = json.load(f)
        municipios = conteudo.get("municipios") or {}
        if not isinstance(municipios, dict):
            return {}
        return {str(ibge): [str(c).strip().zfill(14) for c in lista]
                for ibge, lista in municipios.items() if isinstance(lista, list)}
    except (OSError, ValueError, AttributeError):
        return {}


FIO_B_POR_DISTRIBUIDORA = _carregar_fio_b_por_distribuidora()
DISTRIBUIDORAS_POR_MUNICIPIO = _carregar_mapa_distribuidoras()
# True quando os dois arquivos vieram utilizaveis; False = motor na tabela
# embutida (plano B). A tela mostra isso.
TABELA_FIO_B_DE_ARQUIVO = bool(FIO_B_POR_DISTRIBUIDORA and DISTRIBUIDORAS_POR_MUNICIPIO)


def distribuidoras_do_municipio(codigo_ibge):
    """
    Lista as distribuidoras com Fio B vigente que atendem um municipio.

    Devolve uma lista de dicionarios (cnpj, distribuidora, fio_b...), do menor
    para o maior Fio B. Lista vazia quando o municipio nao esta no mapa ou
    nenhuma das suas distribuidoras tem tarifa vigente.
    """
    if not TABELA_FIO_B_DE_ARQUIVO or codigo_ibge in (None, ""):
        return []
    cnpjs = DISTRIBUIDORAS_POR_MUNICIPIO.get(str(codigo_ibge), [])
    achadas = [FIO_B_POR_DISTRIBUIDORA[c] for c in cnpjs if c in FIO_B_POR_DISTRIBUIDORA]
    return sorted(achadas, key=lambda d: (d["fio_b"], d["distribuidora"]))


def fio_b_do_municipio(codigo_ibge=None, uf=None, cnpj_escolhido=None, hoje=None):
    """
    Devolve o Fio B (R$/kWh) que a plataforma usa para um municipio.

    Recebe o codigo IBGE do municipio (que a geocodificacao ja devolve), a
    sigla do estado, e opcionalmente o CNPJ da distribuidora que a pessoa
    escolheu na tela. Devolve os mesmos campos de fio_b_do_estado(), mais:
      cnpj                - o CNPJ da distribuidora usada, ou None
      origem              - "informada", "unica", "maior", "estado"
      opcoes              - as distribuidoras do municipio (para a tela)
      tabela_de_arquivo   - False quando foi usada a tabela embutida

    A ordem de escolha esta explicada no comentario acima.
    """
    opcoes = distribuidoras_do_municipio(codigo_ibge)

    escolhida, origem = None, None
    if opcoes:
        chave = (cnpj_escolhido or "").strip().zfill(14) if cnpj_escolhido else None
        por_cnpj = {d["cnpj"]: d for d in opcoes}
        if chave and chave in por_cnpj:
            escolhida, origem = por_cnpj[chave], "informada"
        elif len(opcoes) == 1:
            escolhida, origem = opcoes[0], "unica"
        else:
            # regra 3: a de MAIOR Fio B entre as que atendem o municipio
            escolhida, origem = opcoes[-1], "maior"

    if escolhida is None:
        # regra 4 (ou tabela embutida): volta para o criterio do estado
        referencia = fio_b_do_estado(uf, hoje)
        referencia.update({"cnpj": None, "origem": "estado", "opcoes": opcoes,
                           "tabela_de_arquivo": TABELA_FIO_B_DE_ARQUIVO})
        return referencia

    inicio, fim = escolhida["vigencia_inicio"], escolhida["vigencia_fim"]
    return {
        "fio_b": escolhida["fio_b"],
        "uf": (uf or "").strip().upper() or None,
        "distribuidora": escolhida["distribuidora"],
        "cnpj": escolhida["cnpj"],
        "resolucao": escolhida["resolucao"],
        "vigencia_inicio": inicio,
        "vigencia_fim": fim,
        "vigencia_inicio_br": _data_br(inicio),
        "vigencia_fim_br": _data_br(fim),
        "vigencia_expirada": vigencia_expirada(fim, hoje),
        "estado_identificado": True,
        "origem": origem,
        "opcoes": opcoes,
        "tabela_de_arquivo": True,
    }


# ---------------------------------------------------------------------
# FASE 4, N2 (04/11/2026) - COBRANCA MAXIMA DEPOIS DE 2029 (o "pior caso")
# ---------------------------------------------------------------------
# A Lei 14.300/2022 (art. 27) fixa o Fio B cobrado sobre a energia compensada
# ate 2028 (90%). De 2029 em diante vale o art. 17: cobrar "todas as
# componentes tarifarias nao associadas ao custo da energia", abatidos os
# beneficios que a ANEEL ainda vai calcular - a regra NAO existe em
# 04/11/2026 (Tomada de Subsidios ANEEL 23/2025; regulamentacao prevista para
# 2027). O motor continua usando 100% do Fio B como premissa provisoria (o
# caso de cima) e calcula tambem o TETO que a lei permite: a tarifa do SCEE
# inteira sem nenhum beneficio abatido, TUSD + TE do detalhe SCEE dos dados
# abertos da ANEEL (as "tarifas TUSD e TE aplicaveis ao SCEE" da REN
# 1.000/2021, art. 655-I, par. 1o, II, b; a TE do SCEE ja vem sem as parcelas
# de energia). Mesma definicao do artigo (d). Valor SEM impostos, como o Fio B
# (e subtraido da tarifa da conta do mesmo jeito que o Fio B ja e).
#
# QUANDO A DISTRIBUIDORA NAO TEM O VALOR (coluna em branco, ou Fio B vindo da
# tabela do estado): estimado como Fio B x a MEDIANA da razao cobranca
# maxima / Fio B das distribuidoras do arquivo, e a tela diz que e
# estimativa. Sem nenhum valor no arquivo, nao ha pior caso (None).
def _mediana(valores):
    v = sorted(valores)
    if not v:
        return None
    meio = len(v) // 2
    return v[meio] if len(v) % 2 else (v[meio - 1] + v[meio]) / 2


RAZAO_COBRANCA_MAXIMA_MEDIANA = _mediana(
    m / FIO_B_POR_DISTRIBUIDORA[c]["fio_b"]
    for c, m in COBRANCA_MAXIMA_POR_DISTRIBUIDORA.items()
    if m is not None and c in FIO_B_POR_DISTRIBUIDORA)


def cobranca_maxima_pos_2029(referencia_fio_b):
    """
    Teto da cobranca sobre a energia compensada depois de 2029 (R$/kWh) para a
    referencia de Fio B que o motor usou (o dicionario de fio_b_do_municipio).

    Devolve (valor, estimada): estimada = False quando o valor e o da propria
    distribuidora; True quando saiu da mediana (ver o bloco acima). (None, None)
    quando nao ha como calcular.
    """
    cnpj = (referencia_fio_b or {}).get("cnpj")
    fio_b = (referencia_fio_b or {}).get("fio_b")
    if cnpj and COBRANCA_MAXIMA_POR_DISTRIBUIDORA.get(cnpj):
        return COBRANCA_MAXIMA_POR_DISTRIBUIDORA[cnpj], False
    if fio_b and fio_b > 0 and RAZAO_COBRANCA_MAXIMA_MEDIANA:
        return fio_b * RAZAO_COBRANCA_MAXIMA_MEDIANA, True
    return None, None


# ---------------------------------------------------------------------
# Equacao 7 - Valor economizado por kWh (no artigo: Equacao 3)
# ---------------------------------------------------------------------
def valor_economizado_por_kwh(tarifa, valor_fio_b, percentual_fio_b):
    return tarifa - (valor_fio_b * percentual_fio_b)


# ---------------------------------------------------------------------
# Equacao 8 - Economia mensal estimada (fora do calculo desde o T2; nao
# esta no artigo)
# ---------------------------------------------------------------------
# ATENCAO (correcao T2, 12/09/2026): esta funcao NAO deve mais ser usada
# para alimentar o payback. Ela multiplica a geracao do mes pelo valor
# economizado por kWh SEM nenhum teto, e por isso monetiza o excedente de
# geracao que vem do arredondamento de paineis inteiros - excedente que,
# no mundo real, vira credito e expira em 60 meses sem virar dinheiro.
# Ela continua aqui porque serve para exibir a economia de UM mes
# especifico na tela (grafico mes a mes). Para o calculo financeiro que
# vale, usar energia_compensavel_anual() + economia_anual_estimada().
def economia_mensal(geracao_do_mes_kwh, valor_economizado_kwh):
    return geracao_do_mes_kwh * valor_economizado_kwh


# ---------------------------------------------------------------------
# Custo de disponibilidade por tipo de ligacao (correcao T7, 14/09/2026)
# ---------------------------------------------------------------------
# O art. 291 da REN ANEEL 1.000/2021 estabelece um MINIMO FATURAVEL para o
# consumidor de baixa tensao: mesmo que a compensacao zere o consumo, a
# distribuidora fatura esta quantidade de energia. Ela paga a existencia da
# rede disponivel (poste, medidor, manutencao) e NAO desaparece com os
# paineis - foi o erro E4 da auditoria de 11/09/2026.
#
# A tabela mora AQUI, no motor, pelo mesmo motivo da tabela do Fio B (T3a):
# e regra da norma, e o motor e o unico ponto do sistema que precisa
# conhecer a lei. O simulacao.py apenas consulta.
#
# NOTA TECNICA sobre a bifasica: o art. 291 distingue "bifasico a dois
# condutores" (30 kWh) de "bifasico a tres condutores" (50 kWh). A ligacao
# bifasica residencial tipica e a de tres condutores, dai os 50 kWh. Essa
# distincao NAO e apresentada ao usuario - seria jargao inutil para leigo.
PISO_DISPONIBILIDADE_KWH = {
    "monofasica": 30.0,
    "bifasica": 50.0,
    "trifasica": 100.0,
}

# PREMISSA DECLARADA (nao e dado): quando a pessoa nao sabe o tipo de
# ligacao da casa dela, adota-se BIFASICA. E um criterio adotado pelo
# trabalho: NAO foi encontrada estatistica nacional de distribuicao entre
# mono, bi e trifasica (procurada na ANEEL e no Anuario da EPE).
# Numa casa monofasica o minimo e menor (30 kWh), entao, para ela, a
# premissa deixa a estimativa pessimista.
# A tela precisa declarar isso sempre que o tipo nao for informado - e para
# isso que piso_disponibilidade() devolve "tipo_informado".
TIPO_LIGACAO_PRESUMIDO = "bifasica"

# Escritas alternativas aceitas, para o motor nao depender de o formulario
# mandar exatamente a chave da tabela (com ou sem acento, abreviada).
ALIASES_TIPO_LIGACAO = {
    "mono": "monofasica", "monofasica": "monofasica",
    "monofásica": "monofasica", "monofasico": "monofasica",
    "monofásico": "monofasica",
    "bi": "bifasica", "bifasica": "bifasica",
    "bifásica": "bifasica", "bifasico": "bifasica",
    "bifásico": "bifasica",
    "tri": "trifasica", "trifasica": "trifasica",
    "trifásica": "trifasica", "trifasico": "trifasica",
    "trifásico": "trifasica",
}


def piso_disponibilidade(tipo_ligacao=None):
    """
    Traduz o tipo de ligacao da casa no piso mensal em kWh do art. 291.

    Devolve um dicionario com tres campos:
      tipo_ligacao    - o tipo que foi de fato usado no calculo
      piso_kwh        - o minimo faturavel mensal correspondente
      tipo_informado  - False quando o tipo veio vazio ou irreconhecivel e
                        a premissa bifasica foi aplicada

    O campo tipo_informado existe para a tela poder ser honesta: quando ele
    e False, o resultado nasceu de uma premissa deste trabalho, nao de um
    dado da pessoa, e isso precisa estar escrito na tela.
    """
    chave = (tipo_ligacao or "").strip().lower()
    chave = ALIASES_TIPO_LIGACAO.get(chave, chave)

    informado = chave in PISO_DISPONIBILIDADE_KWH
    if not informado:
        chave = TIPO_LIGACAO_PRESUMIDO

    return {
        "tipo_ligacao": chave,
        "piso_kwh": PISO_DISPONIBILIDADE_KWH[chave],
        "tipo_informado": informado,
    }


# ---------------------------------------------------------------------
# Custo de disponibilidade para quem tem painel (correcao T20, 23/09/2026)
# ---------------------------------------------------------------------
# O ERRO QUE ESTA CORRECAO DESFAZ. Desde o T7 (14/09/2026) o motor tratava
# o custo de disponibilidade como uma quantidade de ENERGIA que nenhum
# credito abate: 30, 50 ou 100 kWh descontados do consumo todo mes, e o
# Fio B cobrado ainda por cima sobre o resto. Isso reproduz a regra do
# consumidor COMUM (art. 290, caput, da REN ANEEL 1.000/2021: paga-se o
# maior valor entre o consumo e o custo de disponibilidade), mas o § 5º do
# mesmo art. 290 (incluido pela REN 1.059/2023) diz que essa regra NAO se
# aplica a quem participa do Sistema de Compensacao (SCEE): para esses,
# vale o art. 655-I. Conferido no texto oficial da ANEEL em 23/09/2026.
#
# O QUE DIZ O ART. 655-I (grupo B, participante do SCEE):
#   § 1º a parcela da energia consumida da rede e o MAIOR valor entre
#        I  - o custo de disponibilidade do art. 291 (em reais); e
#        II - o faturamento da energia consumida da rede: a parte NAO
#             compensada pela tarifa cheia, MAIS o faturamento da energia
#             compensada pelas tarifas do SCEE (na GD II, a parcela do Fio B
#             que a Lei 14.300/2022 manda cobrar - art. 27).
#   § 2º a energia compensada: I - vai ate o limite em que esse faturamento
#        continue maior ou igual ao custo de disponibilidade; e II - nunca
#        passa do consumo do ciclo.
# Em palavras simples: o minimo continua existindo, mas e comparado EM
# REAIS com a conta inteira, e o Fio B que a pessoa ja paga sobre a energia
# compensada CONTA para atingi-lo. As duas cobrancas nao se somam.
#
# DIVERGENCIA DECLARADA ENTRE A LEI E A RESOLUCAO (auditoria de 23/09/2026):
# a Lei 14.300/2022, art. 16, § 1º, diz que, para os sistemas novos, o
# valor minimo faturavel so se aplica SE o consumo medido for inferior ao
# minimo. Lida ao pe da letra, com consumo acima do minimo a conta poderia
# cair abaixo dele. A REN 1.000, art. 655-I, aplica o maior valor SEMPRE.
# As duas leituras so diferem quando o Fio B cobrado sobre o consumo inteiro
# fica abaixo do valor do minimo (consumo baixo ou Fio B baixo - dos cinco
# casos de validacao, so Campinas). O motor segue a REN, por ser a regra
# pela qual a distribuidora de fato fatura e por ser a leitura mais
# conservadora para a economia. Declarado no artigo.
#
# A CONTA QUE SAI DAI, para um mes com consumo C (kWh), tarifa T (R$/kWh),
# piso P (kWh) e f = Fio B x percentual do ano (R$/kWh):
#   conta com compensacao E = (C - E) x T + E x f  >= P x T
#   =>  E <= (C - P) x T / (T - f)        (e, pelo § 2º, II, E <= C)
#   compensavel do mes = min( C ; max(C - P ; 0) x T / (T - f) )
# Note que T - f e exatamente o valor economizado por kWh da Equacao 7.
#
# EFEITO, medido em 23/09/2026 com os HSP dos cinco casos: com consumo
# medio ou alto o limite nao chega a agir (em Guaira, 300 kWh/mes: o Fio B
# sobre os 300 kWh compensados da R$ 38,61, acima do minimo de R$ 37,50), e
# o sistema passa a ser dimensionado para o consumo inteiro. Em consumo
# baixo, ou onde o Fio B e baixo, o minimo ainda limita (Campinas, 180
# kWh/mes: 156,6 kWh/mes compensaveis, contra 130 antes). Quatro dos cinco
# casos de validacao mudaram de tamanho; so Cuiaba manteve o sistema.
#
# LIMITACOES DECLARADAS (vao para o artigo): (a) o modelo nao tem fator de
# simultaneidade, entao trata o consumo inteiro como "consumido da rede";
# (b) a regra da baixa renda (art. 655-I, § 5º, e art. 291, III e paragrafo
# unico) nao e modelada; (c) o valor do Fio B vem sem impostos e a tarifa
# da fatura, com impostos (limitacao ja declarada no T19).
def compensavel_do_mes(consumo_mes_kwh, piso_disponibilidade_kwh=0.0,
                       tarifa=None, parcela_fio_b_por_kwh=0.0):
    """
    Quanto do consumo de UM mes pode ser abatido pela compensacao, pela
    regra do art. 655-I da REN ANEEL 1.000/2021 (correcao T20).

    parcela_fio_b_por_kwh e o que continua sendo cobrado sobre cada kWh
    compensado (Fio B x percentual do ano, em R$/kWh). Sem piso, o mes
    inteiro e compensavel.

    A TARIFA E OBRIGATORIA quando ha piso: o limite do art. 655-I e em
    reais. Nao existe caminho silencioso para a regra antiga - chamar sem
    tarifa e erro de programa, e o programa para (a mesma licao do T2b:
    duas definicoes da mesma grandeza acabam divergindo).
    Tarifa que nao supera o Fio B cobrado so acontece com fatura digitada
    errada (a compensacao nao economizaria nada); nesse caso fica o piso
    inteiro, em energia, de fora, e a economia sai zero ou negativa, o que
    as guardas do simulacao.py ja tratam.
    """
    consumo = max(consumo_mes_kwh, 0.0)
    if not piso_disponibilidade_kwh:
        return consumo
    if tarifa is None:
        raise ValueError("compensavel_do_mes: a tarifa e obrigatoria quando ha "
                         "custo de disponibilidade (art. 655-I, limite em reais)")
    acima_do_piso = max(consumo - piso_disponibilidade_kwh, 0.0)
    if tarifa <= parcela_fio_b_por_kwh:
        return acima_do_piso
    return min(consumo, acima_do_piso * tarifa / (tarifa - parcela_fio_b_por_kwh))


def _consumos_do_ano(consumo_anual_kwh, consumo_por_mes_kwh):
    """Os 12 consumos mensais; sem o historico, a media repetida 12 vezes."""
    if consumo_por_mes_kwh:
        if isinstance(consumo_por_mes_kwh, dict):
            return list(consumo_por_mes_kwh.values())
        return list(consumo_por_mes_kwh)
    return [consumo_anual_kwh / 12] * 12


def consumo_compensavel_do_ano(consumo_anual_kwh, piso_disponibilidade_kwh=0.0,
                               consumo_por_mes_kwh=None, tarifa=None,
                               parcela_fio_b_por_kwh=0.0):
    """
    Soma, mes a mes, o consumo que pode ser abatido (compensavel_do_mes).

    E a UNICA definicao do teto compensavel do ano, usada pelo
    dimensionamento (Equacao 2a) e pela economia (Equacao 8a) - a mesma
    regra do T16 de ter uma conta so, num lugar so.
    """
    return sum(compensavel_do_mes(c, piso_disponibilidade_kwh, tarifa,
                                  parcela_fio_b_por_kwh)
               for c in _consumos_do_ano(consumo_anual_kwh, consumo_por_mes_kwh))


def piso_anual_efetivo(piso_disponibilidade_kwh, consumo_por_mes_kwh=None,
                       tarifa=None, parcela_fio_b_por_kwh=0.0):
    """
    kWh do ano que o custo de disponibilidade IMPEDE de abater.

    CORRECAO T20 (23/09/2026): deixou de ser "min(consumo do mes; piso)"
    somado nos 12 meses e passou a ser o consumo do ano menos o que a regra
    do art. 655-I deixa compensar. Na maior parte da faixa residencial o
    resultado e ZERO: o Fio B cobrado sobre a energia compensada ja atinge
    o minimo. Continua existindo para a tela poder mostrar, quando nao for
    zero, quanto o minimo tirou da economia.
    """
    if not piso_disponibilidade_kwh:
        return 0.0
    if not consumo_por_mes_kwh:
        raise ValueError("piso_anual_efetivo: desde o T20 o consumo mes a mes "
                         "e obrigatorio (a regra do art. 655-I e aplicada por mes)")
    consumos = _consumos_do_ano(0.0, consumo_por_mes_kwh)
    anual = sum(consumos)
    return anual - consumo_compensavel_do_ano(anual, piso_disponibilidade_kwh,
                                              consumos, tarifa, parcela_fio_b_por_kwh)


# ---------------------------------------------------------------------
# Equacao 2a (NOVA - correcao T16, 14/09/2026; regra do minimo corrigida
# no T20, 23/09/2026) - Alvo de dimensionamento (no artigo: Equacao 4,
# com compensavel_do_mes() e consumo_compensavel_do_ano())
# ---------------------------------------------------------------------
def consumo_alvo_dimensionamento(consumo_anual_kwh,
                                 piso_disponibilidade_kwh=0.0,
                                 consumo_por_mes_kwh=None,
                                 tarifa=None,
                                 parcela_fio_b_por_kwh=0.0):
    """
    Quanto do consumo o sistema precisa cobrir: o consumo que PODE ser
    abatido pela compensacao (T16), e nao o que a casa consome e depois a
    distribuidora cobra de qualquer forma.

    CORRECAO T20 (23/09/2026): o que pode ser abatido segue o art. 655-I da
    REN ANEEL 1.000/2021 (ver compensavel_do_mes). Na maior parte da faixa
    residencial o alvo passa a ser o consumo inteiro. O principio do T16
    continua valendo: painel dimensionado para energia que a conta nao
    deixa abater seria painel sem retorno - so que, pela regra correta,
    essa energia e muito menor do que o T7 supunha.

    Por isso a tarifa e o Fio B passaram a entrar AQUI: o limite do art.
    655-I e em reais, e depende dos dois. O simulacao.py calcula os dois
    antes do dimensionamento (nenhum deles depende do tamanho do sistema).

    Devolve um dicionario com tres campos:
      piso_anual_kwh                 - kWh do ano que o minimo impede de abater
      consumo_compensavel_anual_kwh  - consumo do ano que PODE ser abatido
      alvo_mensal_kwh                - o anterior dividido por 12, para a tela
    """
    consumos = _consumos_do_ano(consumo_anual_kwh, consumo_por_mes_kwh)
    compensavel_anual = consumo_compensavel_do_ano(
        consumo_anual_kwh, piso_disponibilidade_kwh, consumos, tarifa,
        parcela_fio_b_por_kwh)
    compensavel_anual = max(compensavel_anual, 0.0)

    return {
        "piso_anual_kwh": max(sum(consumos) - compensavel_anual, 0.0),
        "consumo_compensavel_anual_kwh": compensavel_anual,
        "alvo_mensal_kwh": compensavel_anual / 12,
    }


# ---------------------------------------------------------------------
# Equacao 8a (NOVA - correcao T2; regra do minimo corrigida no T20) -
# Energia compensavel no ano (no artigo: Equacao 9, 1a parte)
# ---------------------------------------------------------------------
def energia_compensavel_anual(geracao_anual_kwh, consumo_anual_kwh,
                              piso_disponibilidade_kwh=0.0,
                              consumo_por_mes_kwh=None,
                              tarifa=None,
                              parcela_fio_b_por_kwh=0.0):
    """
    Quanta energia gerada de fato ABATE a conta de luz ao longo de 1 ano:
    o menor valor entre a geracao do ano e o teto compensavel do ano.

    Por que o corte e ANUAL e nunca mensal: o excedente de um mes farto
    abate legitimamente um mes fraco - e para isso que o credito de 60
    meses serve (Lei 14.300/2022, art. 13). O corte anual elimina apenas o
    excedente ESTRUTURAL, o que nunca encontra consumo nenhum.

    O teto compensavel vem de consumo_compensavel_do_ano(), a mesma funcao
    do dimensionamento (Equacao 2a). CORRECAO T20: o teto segue o art.
    655-I da REN ANEEL 1.000/2021 - ver compensavel_do_mes().
    """
    teto = consumo_compensavel_do_ano(consumo_anual_kwh, piso_disponibilidade_kwh,
                                      consumo_por_mes_kwh, tarifa,
                                      parcela_fio_b_por_kwh)
    compensavel = min(geracao_anual_kwh, teto)
    # Nunca pode ficar negativa.
    return max(compensavel, 0.0)


# ---------------------------------------------------------------------
# Equacao 8b (NOVA - correcao T2) - Economia anual estimada (no artigo:
# Equacao 9, 2a parte)
# ---------------------------------------------------------------------
def economia_anual_estimada(energia_compensavel_anual_kwh, valor_economizado_kwh):
    """
    Economia de 1 ano = energia que de fato abate a conta (Equacao 8a)
    multiplicada pelo valor economizado por kWh (Equacao 7).

    Observacao tecnica: como agora a base e a energia COMPENSAVEL e nao a
    geracao bruta, o Fio B passa a incidir sobre a energia compensada -
    que e exatamente sobre o que a lei manda incidir. O modelo continua
    sem considerar o autoconsumo instantaneo (limitacao E5 declarada),
    mas ficou um passo mais proximo da regra real.
    """
    return energia_compensavel_anual_kwh * valor_economizado_kwh


# ---------------------------------------------------------------------
# ENERGIA USADA NA HORA (fase 4, item N1, 03-04/11/2026) - "fator de
# simultaneidade"
# ---------------------------------------------------------------------
# O QUE MUDA. Ate aqui o motor supunha que TODA a energia gerada ia para a
# rede e voltava como credito, pagando a parcela do Fio B (Lei 14.300/2022,
# art. 27). Na pratica, parte dela e usada pela casa no mesmo instante em que
# e gerada (geladeira, ar-condicionado, chuveiro de dia): essa parte nem passa
# pelo medidor, e por isso economiza a tarifa INTEIRA, sem Fio B. A ANEEL diz
# isso com todas as letras: a energia gerada simultaneamente ao consumo "se
# traduz como uma simples reducao do consumo" e e valorada por todas as
# componentes da tarifa (Relatorio de AIR n. 0004/2018-SRD/SCG/SMA/ANEEL, de
# 06/12/2018, fl. 20, item 60).
#
# A PERGUNTA DA TELA E OPCIONAL. Em branco ("nao sei") vale 0%, que e
# exatamente a conta de antes deste item - o lado conservador. Quem responde
# escolhe uma rotina em palavras, e cada rotina vira uma fracao da GERACAO
# usada na hora, sempre pelo lado baixo das medicoes publicadas (decisao da
# aluna, 03/11/2026: "otimismo nao pode entrar"):
#   "noite"  10% - grupo "noturno" de Dilli e Brito (2025): media 20%, minimo
#                  medido 8%; programa Bonus Fotovoltaico da Celesc (1.250
#                  casas, Renewable Energy v. 187, 2022): abaixo de 20%.
#   "igual"  30% - grupo "integral" de Dilli e Brito (2025): minimo 29%, media
#                  39%; EPE, NT DEA-SEE 009/2023 (596 casas): media 34%.
#   "dia"    39% - media MEDIDA pela ANEEL no P&D Telhados Solares
#                  Unicamp-CPFL (231 sistemas, 1 ano): 38,92% (AIR 0004/2018,
#                  Tab. 6, fl. 30); grupo "diurno" de Dilli e Brito (2025):
#                  minimo 44%, media 60%.
# DILLI, M. A.; BRITO, B. H. Analise do fator de simultaneidade em sistemas
# fotovoltaicos para prossumidores com diferentes padroes de consumo. Revista
# Sitio Novo, Palmas, v. 9, e1578, 2025. DOI 10.47236/2594-7036.2025.v9.1578
# (86 sistemas no Tocantins, perfil declarado pelo dono, como na nossa tela).
# Teto de coerencia: a CEMIG mediu 47% a 55% do consumo residencial entre 6h e
# 18h (Metodologia MicroGD, 2024): ninguem usa na hora mais do que consome
# enquanto ha sol, e as tres fracoes ficam abaixo disso.
#
# O QUE NAO MUDA: o numero de paineis, a potencia e o inversor. A fracao entra
# so na economia, na fatura mes a mes e no retorno. Medido em 03/11/2026
# (claude/n1_medicao/medir_fs.py no Project): com 39%, em ~5% dos casos o
# ultimo painel quase nao rende no 1o ano, mas rende em 25 anos (minimo de
# ~R$ 800, mediana ~R$ 7 mil), porque a cobranca do Fio B sobe ate 2029. E uma
# resposta aproximada nao deve encolher o sistema: quem errar para mais ficaria
# com sistema pequeno de forma permanente.
#
# A REGRA DO MINIMO CONTINUA VALENDO MES A MES (art. 655-I da REN ANEEL
# 1.000/2021): a energia usada na hora reduz o consumo puxado da rede, e e
# sobre ESSE consumo que valem o minimo e o teto compensavel. Quando ela
# derruba o consumo da rede para baixo do minimo, o minimo absorve o ganho -
# a conta nunca fica abaixo dele. (A 1a versao da medicao esqueceu isso e
# inflava os casos de consumo baixo; ver o registro da fase 4.)
SIMULTANEIDADE_POR_PERFIL = {
    "nao_sei": 0.0,
    "noite": 0.10,
    "igual": 0.30,
    "dia": 0.39,
}
PERFIL_SIMULTANEIDADE_PADRAO = "nao_sei"


def simultaneidade_do_perfil(perfil=None):
    """
    Traduz a resposta da tela ("noite", "igual", "dia" ou vazio) na fracao da
    geracao usada na hora. Vazio ou desconhecido vira "nao_sei" (0%).

    Devolve: perfil (o que foi usado), fracao e informado (False quando a
    pessoa nao respondeu - a tela precisa dizer que a conta e a de 0%).
    """
    chave = (perfil or "").strip().lower()
    if chave not in SIMULTANEIDADE_POR_PERFIL:
        chave = PERFIL_SIMULTANEIDADE_PADRAO
    return {
        "perfil": chave,
        "fracao": SIMULTANEIDADE_POR_PERFIL[chave],
        "informado": chave != PERFIL_SIMULTANEIDADE_PADRAO,
    }


def economia_do_ano_com_simultaneidade(geracao_por_mes_kwh, consumo_por_mes_kwh,
                                       piso_disponibilidade_kwh, tarifa,
                                       parcela_fio_b_por_kwh, fracao):
    """
    Economia de 1 ano quando uma fracao da geracao e usada na hora.

    geracao_por_mes_kwh e consumo_por_mes_kwh: listas (ou dicionarios com os
    mesmos meses, na mesma ordem) de 12 valores.

    Para cada mes m:
      U_m  = min(fracao x G_m ; C_m)           usada na hora (tarifa inteira)
      Cr_m = C_m - U_m                         consumo puxado da rede
      teto_m = compensavel_do_mes(Cr_m, ...)   art. 655-I sobre o consumo da rede
    No ano (o credito de 60 meses deixa o excedente de um mes abater outro, o
    mesmo corte ANUAL da Equacao 8a):
      E = min( soma(G_m - U_m) ; soma(teto_m) )   compensada (paga o Fio B)
      e_m = E x teto_m / soma(teto_m)
    Conta de cada mes, sem e com painel (arts. 290 e 655-I):
      sem_m = max(C_m x T ; P x T)
      com_m = max(P x T ; (Cr_m - e_m) x T + e_m x f)
    economia = soma(sem_m - com_m)

    Com fracao 0 o resultado e o da Equacao 8a x Equacao 7 (o motor de antes);
    o simulacao.py nem chama esta funcao nesse caso, para o resultado de quem
    nao responde a pergunta continuar identico bit a bit.
    """
    g = list(geracao_por_mes_kwh.values()) if isinstance(geracao_por_mes_kwh, dict) \
        else list(geracao_por_mes_kwh)
    c = list(consumo_por_mes_kwh.values()) if isinstance(consumo_por_mes_kwh, dict) \
        else list(consumo_por_mes_kwh)
    f = parcela_fio_b_por_kwh
    minimo = piso_disponibilidade_kwh * tarifa
    usada = [min(fracao * gm, max(cm, 0.0)) for gm, cm in zip(g, c)]
    rede = [max(cm, 0.0) - um for cm, um in zip(c, usada)]
    tetos = [compensavel_do_mes(rm, piso_disponibilidade_kwh, tarifa, f) for rm in rede]
    soma_teto = sum(tetos)
    injetada = sum(gm - um for gm, um in zip(g, usada))
    compensada = max(min(injetada, soma_teto), 0.0)
    sem, com = 0.0, 0.0
    for cm, rm, tm in zip(c, rede, tetos):
        em = compensada * tm / soma_teto if soma_teto > 0 else 0.0
        sem += max(cm * tarifa, minimo)
        com += max(minimo, (rm - em) * tarifa + em * f)
    return {
        "economia": sem - com,
        "usada_na_hora_kwh": sum(usada),
        "compensada_kwh": compensada,
        "consumo_da_rede_kwh": sum(rede),
    }


# ---------------------------------------------------------------------
# Equacao 8c (NOVA - correcao T2b) - Fatura mes a mes com saldo de creditos
# (so para a tela; nao altera economia nem payback; nao numerada no artigo)
# ---------------------------------------------------------------------
def faturas_mensais_com_creditos(geracao_por_mes_kwh, consumo_por_mes_kwh, tarifa,
                                 valor_economizado_kwh,
                                 piso_disponibilidade_kwh=0.0, max_ciclos=6,
                                 simultaneidade=0.0):
    """
    Estima quanto a pessoa pagaria de luz em cada mes do ano, simulando o
    SALDO DE CREDITOS do Sistema de Compensacao de Energia Eletrica.

    consumo_por_mes_kwh e um dicionario mes -> kWh. Quando a pessoa informa
    so a media, o app monta esse dicionario repetindo a media nos 12 meses;
    quando ela informa o historico de 12 meses da fatura, entram os valores
    reais dela. A funcao e a mesma nos dois casos - o que muda e a qualidade
    do dado de entrada.

    Por que esta funcao existe:
    ate 12/09/2026 este calculo era feito dentro do template
    (resultado.html), com duas distorcoes. Primeira: a taxa por kWh usada
    la era economia_anual / geracao_anual, o que dilui a economia sobre a
    geracao inteira, inclusive sobre o excedente que nunca abate conta
    nenhuma. Segunda: a fatura de cada mes era travada em R$0, o que joga
    fora o credito do mes farto em vez de guarda-lo para o mes fraco -
    exatamente o corte mensal que a Equacao 8a rejeita, com justificativa
    legal, por ser errado. O resultado era uma pagina que mostrava duas
    economias diferentes para o mesmo sistema.

    Como funciona:
    a energia gerada a mais num mes NAO some - vira credito, que fica
    guardado e e usado quando a geracao nao cobrir o consumo (credito
    valido por 60 meses, art. 13 da Lei 14.300/2022). A fatura do mes e o
    consumo daquele mes cobrado pela tarifa, menos o que a compensacao
    conseguiu abater, e nunca fica abaixo do custo de disponibilidade.

    Por que o ciclo se repete (parametro "max_ciclos"):
    comecar janeiro com saldo zero descreve o PRIMEIRO ano do sistema, que
    e atipicamente ruim - ainda nao existe credito acumulado. Quem tem o
    sistema instalado vive o ano seguinte, ja em regime, com o saldo de
    dezembro entrando em janeiro. O laco repete o ano ate o total
    compensado parar de mudar (convergencia), e devolve esse ciclo estavel.
    Efeito importante: em regime, a soma do que foi compensado no ano fecha
    com min(geracao anual, consumo COMPENSAVEL do ano) - ou seja, este
    resultado e a Equacao 8a mostrada mes a mes, nao um calculo paralelo.
    (Revisao geral de 07/10/2026: o texto dizia "consumo anual", que era
    verdade antes do T20; desde o T20 o teto e o consumo compensavel.)

    piso_disponibilidade_kwh:
    o custo de disponibilidade do art. 291 da REN ANEEL 1.000/2021.
    CORRECAO T20 (23/09/2026): ele deixou de ser descontado em energia e
    passou a ser o piso EM REAIS da conta, como manda o art. 655-I. O quanto
    cada mes pode compensar sai de compensavel_do_mes(), a mesma regra das
    Equacoes 2a e 8a. A parcela do Fio B cobrada por kWh compensado e
    tarifa - valor_economizado_kwh (Equacao 7), por isso nao precisa de
    parametro proprio. Sem a regra, a conta sem painel tambem respeita o
    minimo (art. 290, caput). Valendo 0, a conta pode zerar.
    """
    meses = list(geracao_por_mes_kwh.keys())

    saldo_creditos = 0.0
    total_anterior = None
    faturas = {}
    faturas_sem_solar = {}
    compensado_por_mes = {}
    saldo_por_mes = {}

    for _ciclo in range(max_ciclos):
        faturas = {}
        faturas_sem_solar = {}
        compensado_por_mes = {}
        saldo_por_mes = {}
        total_compensado = 0.0

        for mes in meses:
            consumo_mes = consumo_por_mes_kwh[mes]
            geracao_mes = geracao_por_mes_kwh[mes]
            # FASE 4, N1 (03/11/2026): a parte da geracao usada NA HORA sai
            # do consumo puxado da rede e da energia injetada - e sobre o
            # consumo da rede que valem o minimo e o teto compensavel. Com
            # simultaneidade 0 (quem nao responde), nada aqui muda: o ramo
            # abaixo nem e executado.
            if simultaneidade:
                usada_na_hora = min(simultaneidade * geracao_mes, max(consumo_mes, 0.0))
                consumo_da_rede = max(consumo_mes, 0.0) - usada_na_hora
                geracao_injetada = geracao_mes - usada_na_hora
            else:
                consumo_da_rede = consumo_mes
                geracao_injetada = geracao_mes
            # CORRECAO T20: o quanto o mes pode compensar segue o art. 655-I
            # (a conta com compensacao nao fica abaixo do minimo em reais).
            consumo_compensavel = compensavel_do_mes(
                consumo_da_rede, piso_disponibilidade_kwh, tarifa,
                tarifa - valor_economizado_kwh)

            # O que esta disponivel no mes: o que os paineis geraram AGORA
            # (menos o que a casa usou na hora) mais o credito guardado dos
            # meses anteriores.
            disponivel = geracao_injetada + saldo_creditos
            compensado = min(disponivel, consumo_compensavel)
            saldo_creditos = disponivel - compensado

            # Minimo em reais da conta (custo de disponibilidade x tarifa).
            # Sem painel vale o art. 290, caput: o maior entre consumo e
            # minimo. Com painel, o art. 655-I, § 1º: o maior entre o minimo e
            # a conta com a compensacao.
            minimo_reais = piso_disponibilidade_kwh * tarifa
            fatura_sem_solar = max(consumo_mes * tarifa, minimo_reais)
            fatura = max(consumo_da_rede * tarifa - (compensado * valor_economizado_kwh),
                         minimo_reais)

            faturas_sem_solar[mes] = fatura_sem_solar
            faturas[mes] = max(fatura, 0.0)
            compensado_por_mes[mes] = compensado
            saldo_por_mes[mes] = saldo_creditos
            total_compensado += compensado

        # Convergencia: quando repetir o ano nao muda mais quanto foi
        # compensado, o saldo entrou em regime e podemos parar.
        if total_anterior is not None and abs(total_compensado - total_anterior) < 0.01:
            break
        total_anterior = total_compensado

    return {
        "fatura_por_mes": faturas,
        "fatura_sem_solar_por_mes": faturas_sem_solar,
        "compensado_por_mes": compensado_por_mes,
        "saldo_creditos_por_mes": saldo_por_mes,
    }


# ---------------------------------------------------------------------
# Equacao 9 - Payback simples (no artigo: Equacao 11)
# ---------------------------------------------------------------------
# CORRECAO T18 (14/09/2026), Achado E da auditoria: esta funcao dividia
# por zero e derrubava o site com erro 500.
#
# COMO ACONTECIA: depois do T7 passou a existir um piso de consumo que a
# compensacao nunca abate (art. 291 da REN ANEEL 1.000/2021). Numa casa
# que consome MENOS que esse piso, a energia compensavel e zero, logo a
# economia mensal e zero, logo custo / 0 estoura. Acontecia em qualquer
# consumo ate 30 kWh/mes na ligacao monofasica, 50 na bifasica e 100 na
# trifasica. O T7 mediu o impacto ate 180 kWh/mes e ninguem olhou abaixo
# disso.
#
# A CORRECAO E DE DUAS PARTES, e esta e a primeira: o motor NUNCA quebra.
# Sem economia, o payback e infinito - que e a resposta matematicamente
# correta, nao um erro. Quem decide o que dizer ao usuario e o
# simulacao.py, que tem o contexto para escrever a frase.
def payback_meses(custo_total, economia_mensal_media):
    """
    Meses ate o sistema se pagar.

    Devolve infinito quando nao ha economia nenhuma. Nao levanta excecao:
    um perfil de consumo em que o sistema nao se paga e uma resposta
    legitima da plataforma, nao uma falha de programa.
    """
    if economia_mensal_media <= 0:
        return math.inf
    return custo_total / economia_mensal_media


# ---------------------------------------------------------------------
# Garantia de desempenho dos modulos e criterio de viabilidade (T18)
# ---------------------------------------------------------------------
# A segunda parte da correcao do Achado E: o motor tambem imprimia
# paybacks absurdos sem nenhum aviso. Medido antes da correcao, com a
# premissa bifasica: 55 kWh/mes devolvia 128,8 anos, impresso na tela no
# formato normal, como se fosse um resultado util.
#
# POR QUE 25 ANOS E NAO UM NUMERO ESCOLHIDO A DEDO: e o prazo da GARANTIA
# DE DESEMPENHO dos modulos (rendimento minimo garantido), citado em Pinho
# e Galdino (2014) - secao 3.3 do artigo, Equacao 11. Nao e "vida util":
# o nome da constante abaixo ficou do desenvolvimento e nao foi trocado
# para nao mexer no codigo.
#
# O QUE O CRITERIO SIGNIFICA: se o sistema nao se paga dentro desse prazo,
# a plataforma nao exibe o payback e explica por que.
#
# O modelo nao inclui troca de inversor nem manutencao (limitacao
# declarada no artigo); inclui-las so afastaria o payback.
VIDA_UTIL_MODULOS_ANOS = 25
PAYBACK_MAXIMO_MESES = VIDA_UTIL_MODULOS_ANOS * 12      # 300 meses


def payback_dentro_da_vida_util(payback_em_meses):
    """
    True quando o sistema se paga dentro dos 25 anos da garantia de
    desempenho dos modulos.

    Trata infinito naturalmente: infinito nunca e menor que 300.
    """
    if payback_em_meses is None:
        return False
    return payback_em_meses <= PAYBACK_MAXIMO_MESES


# ---------------------------------------------------------------------
# Retorno MES A MES (itens 28 e 11 do backlog, 06/10/2026). Substitui a
# Equacao 9 do desenvolvimento (Equacao 11 do artigo) no resultado da
# plataforma; a conta antiga continua em payback_meses(), acima, e vai
# para a tela e para quem quiser reproduzir os numeros do TCC.
# ---------------------------------------------------------------------
# O QUE ESTAVA ERRADO NA CONTA SIMPLES. payback_meses() divide o custo pela
# economia de UM mes e supoe que ela se repete igual ate o sistema se pagar.
# Mas a Lei 14.300/2022 (art. 27) sobe a cobranca do Fio B sobre a energia
# compensada todo 1o de janeiro: 60% em 2026, 75% em 2027, 90% em 2028 e,
# de 2029 em diante, a regra do art. 17 (100% e a premissa provisoria ja
# adotada em PERCENTUAL_FIO_B_A_PARTIR_DE_2029). A economia de cada kWh
# compensado cai a cada virada de ano, e o retorno sai otimista. Medido em
# 06/10/2026 com o motor da fase 1, para quem instala em out/2026: Bom
# Jesus da Lapa 4,1 -> 5,1 anos (+25%); na varredura de 1.354 pontos da
# faixa residencial, mediana +9,6% e maximo +29,9% (registro:
# claude/melhorias_site_item28_11_medicao_06-10.txt).
#
# A CONTA NOVA, para cada mes t contado a partir da instalacao:
#   p(t) = percentual do Fio B do ano civil do mes t (tabela acima)
#   f(t) = Fio B x p(t)                                   (R$/kWh)
#   G(t) = geracao do ano x (1 - d)^k, k = anos completos desde a instalacao
#   teto(t) = consumo compensavel do ano com f(t) (consumo_compensavel_do_ano,
#             a MESMA funcao do dimensionamento e da Equacao 8a)
#   economia(t) = min(G(t) ; teto(t)) x (T - f(t)) / 12
#   retorno = o mes em que a soma das economias alcanca o custo, com a
#             fracao do ultimo mes interpolada (como na conta simples, que
#             tambem devolve meses fracionados).
# Com percentual fixo e d = 0 a economia de todo mes e economia_anual/12 e
# o retorno e exatamente custo / economia mensal: a conta simples e o caso
# particular desta.
#
# DEGRADACAO DOS MODULOS (item 11): 0,5% ao ano. Fontes: PINHO e GALDINO
# (2014, Manual de Engenharia para Sistemas Fotovoltaicos, CEPEL/CRESESB,
# p. 132), que registram 0,5% a 1,0% ao ano em campo; e a Nota Tecnica EPE
# DEA-SEE 014/2023, que adota 0,5% ao ano. Usamos o valor de baixo da faixa
# do Manual, o mesmo da EPE. O efeito no retorno e pequeno (no maximo 1,5%
# na varredura de 06/10/2026), porque no ano 1 a geracao costuma ter folga
# sobre o teto compensavel; ele pesa mais em prazos longos.
#
# PREMISSAS DECLARADAS (decisao da aluna, 06/10/2026):
#   - TARIFA CONSTANTE em termos reais: a tarifa acompanha a inflacao e nao
#     sobe acima dela. E o lado conservador. O crescimento real da tarifa
#     anotado no projeto (2,72% ao ano) e de fonte secundaria e nao entra.
#   - O Fio B em R$/kWh fica o de hoje (o da distribuidora do municipio):
#     so o PERCENTUAL cobrado muda com o ano.
#   - O retorno comeca no mes da simulacao (data_de_hoje()), sem supor um
#     prazo de homologacao, que nao tem fonte.
#   - Sem troca de inversor, manutencao nem juros (retorno simples, nao
#     descontado), como antes.
#   - O dimensionamento NAO muda: paineis, kWp, inversor e geracao continuam
#     os do ano 1.
#   - Quem passa o percentual do Fio B na chamada de simular() continua
#     mandando: nesse caso ele vale para todos os meses (percentual_fixo).
DEGRADACAO_ANUAL_MODULOS = 0.005


# ---------------------------------------------------------------------
# FASE 4, N2 (04/11/2026) - MANUTENCAO E TROCA DO INVERSOR (premissas da EPE)
# ---------------------------------------------------------------------
# Ate aqui o retorno nao tinha manutencao nem troca de equipamento (o bloco
# acima dizia: "inclui-las so afastaria o payback"). Para o LONGO PRAZO (o que
# sobra em 25 anos) elas pesam, e o retorno passa a conta-las tambem, para os
# dois numeros sairem da mesma conta. Valores e fonte:
#   EPE, Nota Tecnica EPE-DEA-SEE 014/2022, "Modelo de Mercado da Micro e
#   Minigeracao Distribuida (4MD): Metodologia - Versao PDE 2032", Tabela 2,
#   p. 15: O&M de 1% do investimento inicial por ano (sistemas locais, o caso
#   residencial); custo do inversor no 10o ano = 15% do CAPEX; degradacao de
#   0,5% a.a. (a mesma ja usada acima); vida util de 25 anos. A mesma nota
#   usa payback SIMPLES (sem juros) para o residencial, como este motor.
#   (O pacote de programas da EPE, epe4md, traz os mesmos 15% e chama o
#   momento de "ano 11": e o mesmo instante, depois de 10 anos completos.)
# Em dinheiro de hoje, como a tarifa: a manutencao e 1% do custo por ano,
# dividida igualmente pelos 12 meses, desde o 1o mes; a troca e paga uma vez,
# no mes 120 (o 1o mes depois de 10 anos completos).
# SENTIDO DO EFEITO: as duas so diminuem a economia liquida (lado
# conservador). Em sistema pequeno, 15% pode ficar ABAIXO do preco real de um
# inversor (MIC 3000TL-X: R$ 1.669 a R$ 1.964 em loja, 04/11/2026, contra 15%
# de R$ 9.150 = R$ 1.372) - limitacao declarada na pagina Limitacoes.
OEM_ANUAL_FRACAO = 0.01
TROCA_INVERSOR_FRACAO = 0.15
TROCA_INVERSOR_MES = 120
FONTE_PREMISSAS_EPE = ("EPE, Nota Técnica EPE-DEA-SEE 014/2022 (Modelo 4MD, "
                       "versão PDE 2032), Tabela 2, p. 15")

# O RETORNO QUE VALE, com custos ao longo do tempo: o mes a partir do qual a
# soma (economia - custos) FICA acima do investimento. Sem custos e igual ao
# 1o mes em que a soma passa o custo (a regra de antes). Com a troca do
# inversor pode haver diferenca: medido em 04/11/2026, em 140 de 8.556
# simulacoes o sistema se pagava antes do mes 120 e a troca fazia a soma voltar
# para baixo do investimento; nesses casos o retorno e o mes em que ela passa
# o custo DE NOVO (claude/n2_medicao/registro_n2.txt no Project).


def retorno_mes_a_mes(custo_total, geracao_anual_kwh, consumo_por_mes_kwh,
                      piso_disponibilidade_kwh, tarifa, valor_fio_b,
                      inicio=None, percentual_fixo=None,
                      degradacao_anual=DEGRADACAO_ANUAL_MODULOS,
                      meses_max=PAYBACK_MAXIMO_MESES,
                      simultaneidade=0.0, geracao_por_mes_kwh=None,
                      oem_anual=0.0, troca_inversor=0.0,
                      troca_mes=TROCA_INVERSOR_MES,
                      cobranca_pos_2029=None):
    """
    Retorno do investimento mes a mes, com a escalada do Fio B da Lei
    14.300/2022 e a degradacao dos modulos (ver o bloco acima).

    inicio: (ano, mes) da instalacao; sem ele, o mes de hoje.
    percentual_fixo: quando informado, vale para todos os meses (e assim
    que os casos antigos seguem reproduziveis).

    FASE 4, N2 (04/11/2026), tres parametros novos, todos com padrao que
    reproduz a conta de antes linha por linha:
      oem_anual       - manutencao, fracao do custo por ano (0 = sem);
      troca_inversor  - troca do inversor, fracao do custo, paga no mes
                        troca_mes (0 = sem);
      cobranca_pos_2029 - R$/kWh cobrados sobre a energia compensada de 2029
                        em diante NO LUGAR do Fio B x 100% (o "pior caso", com a
                        cobranca maxima de cobranca_maxima_pos_2029()). Ignorado
                        quando percentual_fixo e informado.

    Devolve um dicionario:
      payback_meses        - meses ate FICAR no lucro (fracionado); infinito se
                             nao se paga dentro de meses_max
      inicio_ano, inicio_mes
      acumulado_no_prazo   - ECONOMIA somada nos meses_max meses, sem custos (so
                             quando nao se paga; senao None) - como antes
      anos                 - uma linha por ANO CIVIL, da instalacao ate o
                             ano em que o sistema se paga (ou ate o fim do
                             prazo): ano, meses, percentual_fio_b, economia (R$
                             no ano, sem custos), custos (manutencao e troca no
                             ano), economia_por_mes e acumulado (soma de
                             economia - custos no fim daquele ano)
      economia_prazo, custos_prazo, lucro_prazo - somas dos meses_max meses
                             (lucro = economia - custos - custo_total)
      fluxo_liquido        - lista mes a mes de economia - custos (para a TIR,
                             o VPL e o payback descontado)
    Nunca levanta excecao por economia zero ou negativa: o retorno sai
    infinito e quem decide o que dizer e o simulacao.py (mesma regra de
    payback_meses).

    simultaneidade (fase 4, N1): fracao da geracao usada na hora. Com ela
    maior que zero, a economia de cada mes sai de
    economia_do_ano_com_simultaneidade() (que precisa da geracao mes a mes,
    geracao_por_mes_kwh, degradada do mesmo jeito que a geracao do ano). Com
    zero, a conta e a de antes, linha por linha.
    """
    if simultaneidade and not geracao_por_mes_kwh:
        raise ValueError("retorno_mes_a_mes: com simultaneidade, a geracao mes a mes "
                         "e obrigatoria (a regra do minimo e aplicada por mes)")
    geracao_mensal = (list(geracao_por_mes_kwh.values())
                      if isinstance(geracao_por_mes_kwh, dict)
                      else list(geracao_por_mes_kwh or []))
    economia_com_simultaneidade = {}   # (f, k) -> economia do ano
    if inicio is None:
        hoje = data_de_hoje()
        inicio = (hoje.year, hoje.month)
    ano0, mes0 = inicio
    consumos = _consumos_do_ano(0.0, consumo_por_mes_kwh)
    consumo_anual = sum(consumos)

    # 1) economia e custos de cada mes (sempre os meses_max meses)
    # (a economia de um mes so depende do ano civil - que da o percentual e a
    # cobranca - e de k, os anos completos desde a instalacao: guardada por par)
    teto_por_cobranca = {}        # o teto so depende de f
    por_par = {}                  # (ano_civil, k) -> (economia do mes, p)
    economias, custos, anos_civis, percentuais = [], [], [], []
    for t in range(meses_max):
        ano_civil = ano0 + (mes0 - 1 + t) // 12
        k = t // 12
        if (ano_civil, k) not in por_par:
            p = (percentual_fixo if percentual_fixo is not None
                 else percentual_fio_b_vigente(ano_civil))
            f = valor_fio_b * p
            if (cobranca_pos_2029 is not None and percentual_fixo is None
                    and ano_civil >= 2029):
                # A cobranca nunca passa da propria tarifa: o art. 17 cobra
                # componentes da tarifa, entao no maximo a tarifa inteira (com
                # f = tarifa a energia compensada nao economiza nada, e nao
                # "custa" mais que a conta sem painel). So acontece com o valor
                # ESTIMADO (Fio B x mediana) e tarifa da conta baixa; com o
                # valor da propria distribuidora, TUSD + TE do SCEE e sempre
                # menor que a tarifa. Achado da conferencia de 04/11/2026: sem
                # este limite a economia do pior caso saia negativa.
                f = min(cobranca_pos_2029, tarifa)
            if f not in teto_por_cobranca:
                teto_por_cobranca[f] = consumo_compensavel_do_ano(
                    consumo_anual, piso_disponibilidade_kwh, consumos, tarifa, f)
            geracao = geracao_anual_kwh * (1 - degradacao_anual) ** k
            if simultaneidade:
                if (f, k) not in economia_com_simultaneidade:
                    fator = (1 - degradacao_anual) ** k
                    economia_com_simultaneidade[(f, k)] = economia_do_ano_com_simultaneidade(
                        [gm * fator for gm in geracao_mensal], consumos,
                        piso_disponibilidade_kwh, tarifa, f, simultaneidade)["economia"]
                economia_par = economia_com_simultaneidade[(f, k)] / 12
            else:
                economia_par = max(min(geracao, teto_por_cobranca[f]), 0.0) * (tarifa - f) / 12
            por_par[(ano_civil, k)] = (economia_par, p)
        economia, p = por_par[(ano_civil, k)]
        custo_mes = custo_total * oem_anual / 12
        if troca_inversor and t == troca_mes:
            custo_mes += custo_total * troca_inversor
        economias.append(economia)
        custos.append(custo_mes)
        anos_civis.append(ano_civil)
        percentuais.append(p)

    # 2) o retorno: o mes a partir do qual a soma liquida FICA acima do custo
    payback = math.inf
    acumulado = 0.0
    for t in range(meses_max):
        liquido = economias[t] - custos[t]
        antes = acumulado
        acumulado += liquido
        if antes < custo_total <= acumulado and liquido > 0:
            payback = t + (custo_total - antes) / liquido
        elif acumulado < custo_total:
            payback = math.inf

    # 3) a tabela por ano civil, ate o ano do retorno (ou ate o fim do prazo)
    # o mes da passagem e o t com payback em (t, t + 1]
    ultimo_ano = (anos_civis[min(math.ceil(payback) - 1, meses_max - 1)]
                  if payback != math.inf else anos_civis[-1])
    anos = []
    acumulado = 0.0
    for t in range(meses_max):
        if anos_civis[t] > ultimo_ano:
            break
        if not anos or anos[-1]["ano"] != anos_civis[t]:
            anos.append({"ano": anos_civis[t], "meses": 0,
                         "percentual_fio_b": percentuais[t],
                         "economia": 0.0, "custos": 0.0, "acumulado": acumulado})
        linha = anos[-1]
        acumulado += economias[t] - custos[t]
        linha["meses"] += 1
        linha["economia"] += economias[t]
        linha["custos"] += custos[t]
        linha["acumulado"] = acumulado
    for l in anos:
        l["economia_por_mes"] = l["economia"] / l["meses"] if l["meses"] else 0.0

    economia_prazo, custos_prazo = sum(economias), sum(custos)
    return {
        "payback_meses": payback,
        "inicio_ano": ano0,
        "inicio_mes": mes0,
        "acumulado_no_prazo": economia_prazo if payback == math.inf else None,
        "anos": anos,
        "economia_prazo": economia_prazo,
        "custos_prazo": custos_prazo,
        "lucro_prazo": economia_prazo - custos_prazo - custo_total,
        "fluxo_liquido": [e - c for e, c in zip(economias, custos)],
    }


# ---------------------------------------------------------------------
# FASE 4, N2 (04/11/2026) - "RENDE MAIS QUE A POUPANCA?" (TIR e VPL)
# ---------------------------------------------------------------------
# Tudo em dinheiro de hoje (a tarifa nao sobe acima da inflacao), entao a
# comparacao tem de ser com o rendimento REAL (acima da inflacao).
# POUPANCA: rendimento dos ultimos 12 meses descontado o IPCA, com as series
# oficiais do Banco Central (SGS 196 - poupanca, depositos a partir de
# 04/05/2012, rentabilidade mensal; SGS 433 - IPCA mensal, do IBGE), baixadas
# em 04/11/2026: out/2025 a set/2026, poupanca 8,31%, IPCA 4,58% ->
# (1,0831 / 1,0458) - 1 = 3,57% ao ano. E a regua MAIS DIFICIL dos ultimos 10
# anos (media de 10 anos: 0,97%; em 2015, 2019, 2020 e 2021 a poupanca perdeu
# da inflacao) - escolha da aluna (04/11/2026), para nao favorecer o sistema.
# A poupanca nao paga imposto, como a economia na conta de luz: comparacao
# justa. Conta refeita por claude/n2_medicao/poupanca_real.py (Project).
# ATUALIZAR A MAO de tempos em tempos (valor, periodo e data).
POUPANCA_REAL_ANUAL = 0.0357
POUPANCA_PERIODO = "outubro de 2025 a setembro de 2026"
FONTE_POUPANCA = ("Banco Central do Brasil, séries 196 (rendimento da poupança) e "
                  "433 (IPCA, do IBGE), consultadas em 04/11/2026")
# Segunda referencia (so na Metodologia): titulo publico atrelado ao IPCA,
# depois da inflacao e do imposto de renda, ~5% real - a mesma do artigo (d)
# e do Ipea (Dantas e Pompermayer, 2018, TD 2388).
TESOURO_REAL_LIQUIDO_ANUAL = 0.05


def _taxa_mensal(taxa_anual):
    return (1 + taxa_anual) ** (1 / 12) - 1


def vpl(fluxo_liquido, custo_total, taxa_anual):
    """Valor presente liquido do fluxo mensal (1o fluxo no fim do 1o mes)."""
    q = 1.0 / (1.0 + _taxa_mensal(taxa_anual))
    total, fator = 0.0, q
    for v in fluxo_liquido:
        total += v * fator
        fator *= q
    return total - custo_total


def payback_descontado(fluxo_liquido, custo_total, taxa_anual):
    """Meses ate a soma DESCONTADA ficar acima do custo (mesma regra do
    retorno: o mes a partir do qual fica); infinito se nao chega."""
    q = 1.0 / (1.0 + _taxa_mensal(taxa_anual))
    payback, acumulado, fator = math.inf, 0.0, 1.0
    for t, v in enumerate(fluxo_liquido):
        fator *= q
        presente = v * fator
        antes = acumulado
        acumulado += presente
        if antes < custo_total <= acumulado and presente > 0:
            payback = t + (custo_total - antes) / presente
        elif acumulado < custo_total:
            payback = math.inf
    return payback


def tir_real_anual(fluxo_liquido, custo_total):
    """
    Taxa interna de retorno, ao ano, do fluxo mensal (em dinheiro de hoje, entao
    e uma taxa REAL). None quando o fluxo nao devolve nem o custo (a TIR seria
    negativa ou nao existiria - a tela diz "nao se paga").

    Newton-Raphson na taxa MENSAL, protegido por um intervalo [0; 1] que
    encolhe a cada passo (se o passo de Newton sair do intervalo, usa o meio
    dele). O VPL cai quando a taxa sobe, porque depois do investimento o fluxo
    e positivo (a troca do inversor nao inverte isso enquanto a soma devolve o
    custo). Para quando a taxa mensal muda menos de 1e-12.
    """
    if sum(fluxo_liquido) <= custo_total:
        return None

    def valor_e_derivada(i):
        q = 1.0 / (1.0 + i)
        valor = derivada = 0.0
        fator = q
        for t, v in enumerate(fluxo_liquido):
            valor += v * fator
            derivada -= (t + 1) * v * fator * q
            fator *= q
        return valor - custo_total, derivada

    baixo, alto, i = 0.0, 1.0, 0.01
    for _ in range(200):
        f, df = valor_e_derivada(i)
        if f > 0:
            baixo = i
        else:
            alto = i
        proximo = i - f / df if df < 0 else (baixo + alto) / 2
        if not (baixo < proximo < alto):
            proximo = (baixo + alto) / 2
        if abs(proximo - i) < 1e-12:
            i = proximo
            break
        i = proximo
    return (1 + i) ** 12 - 1


def indicadores_longo_prazo(retorno, custo_total):
    """
    Resume o fluxo de 25 anos de retorno_mes_a_mes() no que a tela mostra.
    Devolve: economia, custos, lucro (R$ em 25 anos, sem juros), tir (real ao
    ano ou None), vpl_poupanca e vpl_tesouro (R$ "a mais que" cada aplicacao,
    em dinheiro de hoje), payback_descontado_poupanca (meses ou infinito) e
    payback_meses (o retorno sem juros, o mesmo da tabela).
    """
    fluxo = retorno["fluxo_liquido"]
    return {
        "economia": retorno["economia_prazo"],
        "custos": retorno["custos_prazo"],
        "lucro": retorno["lucro_prazo"],
        "tir": tir_real_anual(fluxo, custo_total),
        "vpl_poupanca": vpl(fluxo, custo_total, POUPANCA_REAL_ANUAL),
        "vpl_tesouro": vpl(fluxo, custo_total, TESOURO_REAL_LIQUIDO_ANUAL),
        "payback_descontado_poupanca": payback_descontado(fluxo, custo_total,
                                                          POUPANCA_REAL_ANUAL),
        "payback_meses": retorno["payback_meses"],
    }


# ---------------------------------------------------------------------
# Equacao 10 - Potencia do inversor (valor calculado, continuo) (no artigo:
# Equacao 7, com potencia_inversor_comercial())
# ---------------------------------------------------------------------
def potencia_inversor(potencia_instalada_kwp, fdi=0.80):
    """
    Potencia TEORICA do inversor: kWp x FDI.

    ATENCAO: este valor e continuo e quase nunca existe para comprar
    (ex.: 2,14 kW). Para o que a plataforma mostra ao usuario, passar este
    resultado por potencia_inversor_comercial() - correcao T4.
    """
    return potencia_instalada_kwp * fdi


# ---------------------------------------------------------------------
# Inversor comercial - GRADE INMETRO (correcao T4, 12/09/2026)
# ---------------------------------------------------------------------
# Corrige E7. Ate aqui a plataforma entregava potencias como "2,14 kW",
# que nao existem no mercado. Inversores sao vendidos em degraus.
#
# POR QUE A LISTA INMETRO e nao o catalogo completo do fabricante: a
# Portaria Inmetro n. 140/2022 sujeita os inversores ao registro, e a
# plataforma indica modelos com registro. Os degraus vieram de uma lista
# de distribuidor (rev. 03/2025).
#
# DEGRAU DE 1,0 kW (fase 4, item A1, 03/11/2026). A grade comecava em 1,5
# kW, e o sistema de 2 modulos (1,20 kWp) recebia inversor de 1,5 kW:
# 1,25 vezes a potencia dos modulos, acima do limite de 1,05 do Manual de
# Engenharia FV (CEPEL-CRESESB, 2014, p. 332). O MIC 1000TL-X tem registro
# Inmetro ATIVO (002636/2024, desde 05/03/2024) e entrou na grade. Com
# ele, os 2 modulos passam a ter 1,0 kW (0,83 vez a potencia dos modulos).
# Nada mais muda: o custo (curva da Greener, por kWp) e a geracao (PR
# fixa) nao dependem do inversor. A versao do artigo (a) da RBENS, que
# descreve a grade antiga como limitacao, esta na tag v1.2-artigo-rbens.
#
# POR QUE SEMPRE PARA CIMA: decisao da aluna - "antes sobrar do que
# faltar". Um inversor menor que o necessario corta geracao (clipping);
# um inversor maior apenas opera mais longe da nominal.
#
# EFEITO COLATERAL BOM: arredondar para cima DERRUBA o Pnom ratio (razao
# entre kWp dos modulos e kW do inversor), o que reduz o clipping e tende
# a MELHORAR a aderencia ao PVsyst. Ex.: 2,68 kWp / 2,5 kW = 1,07, contra
# 1,34 antes. O Caso 5b e a prova experimental: com Pnom ratio de 1,20,
# nenhum dos 12 meses superestimou, contra 5 meses antes.
#
# EFEITO COLATERAL A DECLARAR: com Pnom ratio proximo de 1,0 o inversor
# opera longe da potencia nominal na maior parte do tempo, reduzindo a
# eficiencia de conversao. A grade comercial e grossa demais para sistemas
# pequenos e nao ha como otimizar - e limitacao real do mercado.
#
# RESSALVAS A DECLARAR NO ARTIGO:
# (a) a lista veio de distribuidor (rev. 03/2025), nao da consulta oficial
#     ao INMETRO;
# (b) a grade depende da MARCA. Adotou-se a Growatt por ser a marca usada
#     na validacao com o PVsyst.
#
# DEGRAUS TRIFASICOS (fase 4, item 7, 10/11/2026). Acima de 10 kW a grade
# continua em 12, 15, 20 e 25 kW: os degraus que tem modelo com registro
# Inmetro ATIVO nas DUAS tensoes de rede trifasica do Brasil, 127/220 V e
# 220/380 V (consulta oficial de 10/11/2026; registro em
# claude/item7_passo1_10-11.txt). 25 kW e o TETO decidido pela aluna: acima
# disso as distribuidoras pedem estudo de rede e o sistema sai do porte
# residencial. Ate 10 kW nada mudou.
GRADE_INVERSORES_KW = [1.0, 1.5, 2.0, 2.5, 3.0, 4.2, 5.0, 6.0,
                       7.0, 7.5, 8.0, 9.0, 10.0,
                       12.0, 15.0, 20.0, 25.0]

# Ate aqui a grade e de inversores MONOFASICOS (220 V). Acima, os degraus
# sao TRIFASICOS: a casa precisa de ligacao trifasica (ver simulacao.py) e
# cada degrau tem UM modelo de referencia para cada tensao de rede. Nao ha
# regra nacional de "kW por fase" (REN ANEEL 1.000/2021, arts. 24 e 31: quem
# decide e a norma da distribuidora); 10 kW e onde, na pratica, as normas
# lidas passam para a trifasica.
LIMITE_MONOFASICO_KW = 10.0

FABRICANTE_REFERENCIA_INVERSOR = "Growatt (modelos com certificacao INMETRO)"


def potencia_inversor_comercial(potencia_calculada_kw):
    """
    Encaixa a potencia calculada no menor degrau comercial que a atenda.

    Ex.: 2,14 kW calculado -> inversor de 2,5 kW.

    Acima do maior degrau da grade (25 kW desde o item 7 da fase 4; antes,
    10 kW) nao ha modelo de referencia: a funcao devolve a propria potencia
    calculada e marca "fora_da_grade", para a tela avisar que aquele porte
    exige projeto profissional. Isso esta fora do escopo residencial deste
    trabalho.
    """
    for degrau in GRADE_INVERSORES_KW:
        if degrau >= potencia_calculada_kw:
            return {
                "potencia_kw": degrau,
                "potencia_calculada_kw": potencia_calculada_kw,
                "fora_da_grade": False,
            }

    return {
        "potencia_kw": potencia_calculada_kw,
        "potencia_calculada_kw": potencia_calculada_kw,
        "fora_da_grade": True,
    }


def pnom_ratio(potencia_instalada_kwp, potencia_inversor_kw):
    """
    Razao entre a potencia dos modulos e a do inversor.

    E o "sobredimensionamento" no vocabulario do setor - cuidado para nao
    confundir com excedente de geracao (geracao vs. consumo), que e outra
    coisa. Serve para conferir o comportamento do clipping e para replicar
    o sistema no PVsyst.
    """
    if potencia_inversor_kw <= 0:
        return 0.0
    return potencia_instalada_kwp / potencia_inversor_kw


# =====================================================================
# T15 - VERIFICACAO ELETRICA DO ARRANJO (15/09/2026)
# Achado D da auditoria de 14/09/2026
# =====================================================================
#
# O QUE FALTAVA. Ate aqui a plataforma entregava "5 paineis e um inversor
# de 2,5 kW" sem nunca conferir se aqueles paineis CABEM naquele inversor.
# Numero de modulos e potencia do inversor sao metade do dimensionamento;
# a outra metade e eletrica, e e a que decide se o sistema pode ser
# construido. Para um trabalho de engenharia eletrica, entregar so a
# primeira metade e entregar meio dimensionamento.
#
# AS QUATRO VERIFICACOES, E AS DUAS NATUREZAS DELAS. Nao sao quatro
# conferencias iguais: duas sao de SEGURANCA (limite seco, sem tolerancia)
# e duas sao de DESEMPENHO ou OPERACAO (onde passar do limite custa
# geracao, nao equipamento).
#
#   1. Isc do modulo CORRIGIDA PELA TEMPERATURA <= corrente de curto-
#      circuito maxima do MPPT
#      SEGURANCA. Limite absoluto declarado pelo fabricante. E o unico
#      numero de corrente que existe para proteger o equipamento. A
#      correcao por temperatura entrou em 18/09/2026 - ver o bloco
#      "Por que a corrente tambem e corrigida por temperatura".
#   2. Imp do modulo <= 1,10 x corrente maxima UTILIZAVEL de entrada
#      DESEMPENHO. Ver o bloco do limiar de 10%, mais abaixo.
#   3. Tensao maxima a frio <= tensao maxima absoluta do inversor
#      SEGURANCA. E a unica das quatro que pode QUEIMAR o inversor.
#   4. Vmp a quente >= piso da janela de MPPT
#      OPERACAO. Abaixo disso o inversor nao rastreia o ponto de maxima
#      potencia - na pratica, o arranjo nao funciona.
#
# POR QUE A CORRENTE NAO MELHORA COM SISTEMA MAIOR. Numa string em serie a
# corrente do arranjo e a de UM modulo, independente de quantos modulos
# sejam ligados. Por isso as verificacoes 1 e 2 dependem so do par
# modulo+inversor, e nunca do tamanho do sistema. Consequencia medida: um
# modulo de celula 210 mm reprova no inversor de corrente baixa em
# QUALQUER porte - nao e caso de canto, e a regra.
#
# A CORRENTE E GOVERNADA PELO FORMATO DA CELULA, NAO PELA POTENCIA DO
# MODULO. Medido nos tres datasheets: Trina 550 Wp (celula 210 mm) puxa
# 17,40 A e Trina 670 Wp (tambem 210 mm) puxa 17,55 A - praticamente a
# mesma corrente, apesar de 120 Wp de diferenca. O Jinko de 600 Wp, que
# esta no MEIO em potencia mas e de celula 182 mm, puxa 13,62 A. O que
# muda entre 550 e 670 na linha de 210 mm e a TENSAO (31,6 V contra
# 38,2 V), nao a corrente.
#
# DECISAO DE FONTE, e ela importa para a defesa: todo parametro eletrico
# daqui vem de DATASHEET DO FABRICANTE, nunca do PVsyst. Dois motivos.
# Primeiro, a ficha do Growatt MIN 2500TL-X exportada do PVsyst V8.1.5 nao
# tem campo de corrente maxima de entrada - foi por isso que a simulacao
# de 13/09/2026 acusou 0,00% de perda por limitacao de corrente, e foi por
# isso que a incompatibilidade passou despercebida. Segundo, o PVsyst e a
# referencia de VALIDACAO deste trabalho: construir a verificacao a partir
# dele seria circular.


# ---------------------------------------------------------------------
# Premissas declaradas de temperatura
# ---------------------------------------------------------------------
# O nasa_power.py busca apenas irradiacao; a plataforma nao tem serie de
# temperatura. Em vez de abrir uma fonte de dados nova a dez dias da
# entrega, adotam-se duas premissas declaradas, no mesmo espirito da
# inclinacao 0 graus e da TD de 0,80.
#
# TESTADO ANTES DE ADOTAR: com -5 C no lugar de 0 C, o numero maximo de
# modulos por string NAO muda em nenhum dos tres modulos do catalogo. A
# escolha e pouco sensivel, o que e exatamente o que se quer de uma
# premissa - ela nao esta sustentando o resultado sozinha.
TEMP_STC_C = 25.0
TEMP_MINIMA_PROJETO_C = 0.0      # celula no frio (adotada; secao 3.4 do artigo)
TEMP_MAXIMA_CELULA_C = 70.0      # celula, condicao mais quente de operacao


# ---------------------------------------------------------------------
# Limiar de excesso de corrente aceitavel (verificacao 2)
# ---------------------------------------------------------------------
# POR QUE EXISTE UM LIMIAR, em vez de aprova/reprova seco. Os dois campos
# de corrente do datasheet NAO sao a mesma coisa, e tratar os dois como
# limite absoluto reprovaria combinacoes que a industria inteira pratica.
#
#   - Corrente maxima de CURTO-CIRCUITO (Isc): e o limite absoluto.
#     Respeita-lo e obrigatorio. E a verificacao 1, e la nao ha tolerancia.
#   - Corrente maxima UTILIZAVEL de entrada (I DC max): nao e limite
#     absoluto e nao e critico para seguranca. Se a corrente de maxima
#     potencia do arranjo passa dele, nao ha dano ao inversor nem perda de
#     garantia - o inversor simplesmente limita a corrente, e o que se
#     perde e um pouco de geracao.
#
# A distincao esta PROVADA POR FONTE PRIMARIA do mesmo tipo que o trabalho
# ja usa: a folha de dados do SMA Sunny Boy 3.0-6.0 (arquivo
# SB30-60-DS-AU-61, status 10/2023, baixada do site do proprio fabricante)
# escreve, na linha da entrada CC, "Max. usable input current" - corrente
# maxima UTILIZAVEL de entrada. A nota tecnica da SMA sobre o assunto
# (BAARS, 2022) esta nas Referencias do artigo (secao 3.4).
#
# O LIMIAR DE 10% E UM CRITERIO ADOTADO PELO TRABALHO (secao 3.4 do
# artigo), nao uma medicao. A perda por limitacao de corrente dos casos de
# validacao, medida no PVsyst, esta na secao 4.3 do artigo. Neste catalogo
# o valor do limiar nao decide nenhum par: o maior excesso entre os pares
# aprovados na verificacao 1 e de 8,96% (Jinko com a familia MIN).
EXCESSO_CORRENTE_ACEITAVEL = 0.10


# ---------------------------------------------------------------------
# Catalogo de modulos - parametros de datasheet
# ---------------------------------------------------------------------
# Tres modulos, cobrindo os DOIS formatos de celula que existem hoje no
# mercado brasileiro: 182 mm (corrente baixa, ~13,6 A) e 210 mm (corrente
# alta, ~17,5 A). Nao e uma lista de precos nem de marcas preferidas - e o
# conjunto minimo que permite a plataforma responder "este modulo cabe" ou
# "este nao cabe" com numero de fabricante na mao.
#
# O coeficiente de temperatura de Vmp e DERIVADO, nao inventado: nenhum
# dos tres datasheets publica esse coeficiente, mas como P = V x I, o
# coeficiente de Vmp e o de Pmax menos o de Isc. Para o Jinko:
# -0,29 %/C - (+0,045 %/C) = -0,335 %/C. A derivacao vai declarada no
# artigo, porque e passo de calculo do trabalho e nao dado de fabricante.
CATALOGO_MODULOS = {
    "jinko_600": {
        "nome": "Jinko Tiger Neo JKM600N-72HL4-V",
        "fabricante": "Jinko Solar",
        "fonte": "datasheet F5C1-EN, janeiro/2024",
        "formato_celula_mm": 182,
        "potencia_wp": 600,
        "vmp": 44.06, "imp": 13.62, "voc": 52.95, "isc": 14.25,
        "coef_pmax": -0.29, "coef_voc": -0.25, "coef_isc": 0.045,
    },
    "trina_550": {
        "nome": "Trina Vertex TSM-DE19 550 Wp",
        "fabricante": "Trina Solar",
        "fonte": "datasheet 2023",
        "formato_celula_mm": 210,
        "potencia_wp": 550,
        "vmp": 31.6, "imp": 17.40, "voc": 37.9, "isc": 18.52,
        "coef_pmax": -0.34, "coef_voc": -0.25, "coef_isc": 0.04,
    },
    "trina_670": {
        "nome": "Trina Vertex TSM-DE21 670 Wp",
        "fabricante": "Trina Solar",
        "fonte": "datasheet 2021",
        "formato_celula_mm": 210,
        "potencia_wp": 670,
        "vmp": 38.2, "imp": 17.55, "voc": 46.1, "isc": 18.62,
        "coef_pmax": -0.34, "coef_voc": -0.25, "coef_isc": 0.04,
    },
}

for _modulo in CATALOGO_MODULOS.values():
    _modulo["coef_vmp"] = _modulo["coef_pmax"] - _modulo["coef_isc"]


# ---------------------------------------------------------------------
# Catalogo de inversores - parametros de datasheet
# ---------------------------------------------------------------------
# DUAS FAMILIAS, e a razao nao e comercial: e que existem duas CLASSES DE
# CORRENTE no mercado, e com uma familia so a plataforma fica sem resposta
# quando o modulo de 210 mm nao cabe. Com duas, ela responde como um
# projetista responderia - corrente alta pede inversor de corrente alta.
#
# Isso tambem resolve o problema de criterio que estava travado desde o
# T1: enquanto o unico criterio era preco, nao havia como escolher entre
# marcas sem arbitrariedade. Agora existe criterio TECNICO, que e qual
# inversor aceita a corrente do arranjo.
#
# A GRADE DE POTENCIA continua sendo a GRADE_INVERSORES_KW do T4 (lista
# INMETRO). Este catalogo nao cria degrau novo: ele diz QUAL MODELO ocupa
# cada degrau que ja existe, e quais sao os limites eletricos dele.
#
# EDICAO DO DATASHEET DA FAMILIA MIN - ressalva importante. A familia
# Growatt MIN 2500~6000TL-X circula com DOIS pares de numeros:
#   edicao do proprio fabricante (ginverter.com): 12,5 A / 16 A, partida 80 V
#   edicao AU de 13/10/2022:                      13,5 A / 20 A, partida 100 V
# Adotou-se a PRIMEIRA, que e a mais conservadora e a que vem da folha do
# fabricante e nao de uma edicao regional.
# MEDIDO ANTES DE ADOTAR: a escolha nao muda NENHUM veredito em nenhum
# ponto das varreduras. Com 12,5 A o Jinko de 600 Wp fica 8,96% acima; com
# 13,5 A fica 0,89%. Os dois passam no limiar de 10%. Ou seja, da para
# ficar com o numero conservador sem pagar nada por isso.
# OBSERVACAO PARA O ARTIGO: o "curto-circuito maximo" de 16,9 A da faixa
# MIN 7000~10000 e exatamente 1,25 x os 13,5 A de entrada, o que sugere
# que em algumas edicoes esse campo nao e limite de hardware, e sim a
# corrente de entrada multiplicada por 1,25. Os dois campos do datasheet
# nem sempre medem a mesma coisa entre edicoes.
#
# RESSALVA DE CERTIFICACAO, no mesmo padrao da ja declarada no T4: do lado
# Deye, so o registro INMETRO 005560/2024 (SUN-5K-G05P1-EU-AM2, titular
# Deye Brasil Support Center) foi conferido na consulta oficial. Os demais
# degraus da familia constam do datasheet do fabricante e de registros que
# nao foram conferidos um a um.
CATALOGO_INVERSORES = {
    # --- Growatt MIC 750~3300TL-X --------------------------------------
    # datasheet do fabricante (ginverter.com). 1 MPPT, 1 string por MPPT.
    # MIC 1000TL-X (fase 4, 03/11/2026): mesma coluna de limites do MIC
    # 1500TL-X na folha da familia (500 V; MPPT de 50 a 500 V; partida em
    # 50 V; 13 A de entrada e 16 A de curto); potencia FV recomendada ate
    # 1.400 Wp. Registro Inmetro 002636/2024, ATIVO.
    "MIC1000TL-X": {
        "potencia_kw": 1.0, "familia": "Growatt MIC", "classe_corrente": "baixa",
        "mppts": 1, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.0, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 500.0, "mppt_min_v": 50.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 50.0,
    },
    "MIC1500TL-X": {
        "potencia_kw": 1.5, "familia": "Growatt MIC", "classe_corrente": "baixa",
        "mppts": 1, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.0, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 500.0, "mppt_min_v": 50.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 50.0,
    },
    "MIC2000TL-X": {
        "potencia_kw": 2.0, "familia": "Growatt MIC", "classe_corrente": "baixa",
        "mppts": 1, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.0, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 500.0, "mppt_min_v": 50.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 50.0,
    },
    "MIC2500TL-X": {
        "potencia_kw": 2.5, "familia": "Growatt MIC", "classe_corrente": "baixa",
        "mppts": 1, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.0, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 550.0, "mppt_min_v": 65.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 80.0,
    },
    "MIC3000TL-X": {
        "potencia_kw": 3.0, "familia": "Growatt MIC", "classe_corrente": "baixa",
        "mppts": 1, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.0, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 550.0, "mppt_min_v": 65.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 80.0,
    },
    # --- Growatt MIN 2500~6000TL-X -------------------------------------
    # 2 MPPTs, 1 string por MPPT. Numeros da edicao do fabricante.
    "MIN4200TL-X": {
        "potencia_kw": 4.2, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 12.5, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 550.0, "mppt_min_v": 80.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 80.0,
    },
    "MIN5000TL-X": {
        "potencia_kw": 5.0, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 12.5, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 550.0, "mppt_min_v": 80.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 80.0,
    },
    "MIN6000TL-X": {
        "potencia_kw": 6.0, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 12.5, "corrente_max_curto_a": 16.0,
        "tensao_max_v": 550.0, "mppt_min_v": 80.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 80.0,
    },
    # --- Growatt MIN 7000~10000TL-X ------------------------------------
    # 3 MPPTs. CONCLUSAO IMPORTANTE MEDIDA NO DATASHEET: o teto de corrente
    # de 13,5 A e o MESMO de toda a linha MIN, de 2,5 kW a 10 kW. Subir a
    # potencia do inversor NAO compra corrente - por isso a segunda familia
    # e necessaria, e nao apenas um degrau maior da primeira.
    #
    # NOMES DO REGISTRO INMETRO (fase 4, conferencia de 10/11/2026 na
    # consulta oficial, registro.inmetro.gov.br; registro em
    # claude/inmetro_conferencia_10-11.txt). Os degraus de 7,0, 7,5 e 8,0 kW
    # tinham nomes que nao existem no registro ("MIN7000TL-X", "MIN7500TL-X"
    # e "MIN8000TL-X"; a familia X nem tem modelo de 7,5 kW). Passam a ser
    # os modelos registrados:
    #   MIN7000TL-X(E) - 001469/2024 e 002809/2023, ATIVOS. Folha da familia
    #     MIN 7000-10000TL-X (Growatt): 2 MPPTs com 1 e 2 strings; 13,5/27 A
    #     de entrada; 16,9/33,8 A de curto; 600 V; MPPT de 60 a 550 V;
    #     partida em 100 V.
    #   MIN7500TL-X2 - 018116/2024, ATIVO. Folha MIN 7500~10000TL-X2 da
    #     Growatt Brasil (br.growatt.com): 2 MPPTs, 1 string cada; 18 A de
    #     entrada e 24 A de curto por MPPT; 600 V; MPPT de 60 a 550 V;
    #     partida em 80 V.
    #   MIN8000TL-X2 - 004375/2024, ATIVO. Mesma folha: 3 MPPTs, 1 string
    #     cada; 18 A / 24 A; 600 V; 60-550 V; partida em 80 V.
    # REGRA USADA: nenhum limite fica mais folgado do que era. Correntes,
    # tensao maxima e partida continuam os numeros antigos da familia X
    # (13,5 A, 16,9 A, 550 V, 100 V), que sao iguais ou mais apertados que
    # os das folhas acima; o que muda e o numero de MPPTs (2 no (E) e no
    # X2 de 7,5 kW), e a segunda string do MPPT B do (E) nao e usada.
    "MIN7000TL-X(E)": {
        "potencia_kw": 7.0, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.5, "corrente_max_curto_a": 16.9,
        "tensao_max_v": 550.0, "mppt_min_v": 60.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 100.0,
    },
    "MIN7500TL-X2": {
        "potencia_kw": 7.5, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.5, "corrente_max_curto_a": 16.9,
        "tensao_max_v": 550.0, "mppt_min_v": 60.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 100.0,
    },
    "MIN8000TL-X2": {
        "potencia_kw": 8.0, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 3, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.5, "corrente_max_curto_a": 16.9,
        "tensao_max_v": 550.0, "mppt_min_v": 60.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 100.0,
    },
    "MIN9000TL-X": {
        "potencia_kw": 9.0, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 3, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.5, "corrente_max_curto_a": 16.9,
        "tensao_max_v": 550.0, "mppt_min_v": 60.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 100.0,
    },
    "MIN10000TL-X": {
        "potencia_kw": 10.0, "familia": "Growatt MIN", "classe_corrente": "baixa",
        "mppts": 3, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 13.5, "corrente_max_curto_a": 16.9,
        "tensao_max_v": 550.0, "mppt_min_v": 60.0, "mppt_max_v": 550.0,
        "tensao_partida_v": 100.0,
    },
    # --- Deye SUN G05P1-EU-AM2 -----------------------------------------
    # A familia de CORRENTE ALTA. Datasheet do fabricante em portugues,
    # 25/10/2024. 2 MPPTs, 1 string por MPPT.
    # DESCOBERTA QUE VALE PARA O ARTIGO: nao existe inversor monofasico de
    # corrente alta abaixo de 3,6 kW. A serie G05 comeca ai, e o modelo
    # menor da marca no mercado brasileiro (SUN-3K-G) tem 1 MPPT e 13 A,
    # ou seja, e de corrente baixa. Traduzindo para consumo, so a partir
    # de cerca de 450 kWh/mes o modulo de 210 mm passa a ter par valido.
    # Abaixo disso a resposta tecnicamente correta da plataforma e modulo
    # de 182 mm, ponto final - e isso e RESULTADO, com fonte: quem decide
    # o modulo em sistema pequeno e a compatibilidade eletrica, nao o
    # preco nem o payback.
    # Os degraus da Deye (3,6 / 4 / 4,2 / 4,6 / 5 / 5,2 / 6 / 6,2 / 6,6 /
    # 7 / 7,5 kW) NAO batem com a grade INMETRO adotada; coincidem em
    # 4,2 / 5,0 / 6,0 / 7,0 / 7,5, e sao esses que entram aqui.
    "SUN-4.2K-G05": {
        "potencia_kw": 4.2, "familia": "Deye G05", "classe_corrente": "alta",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 18.0, "corrente_max_curto_a": 27.0,
        "tensao_max_v": 550.0, "mppt_min_v": 70.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 80.0,
    },
    "SUN-5K-G05": {
        "potencia_kw": 5.0, "familia": "Deye G05", "classe_corrente": "alta",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 18.0, "corrente_max_curto_a": 27.0,
        "tensao_max_v": 550.0, "mppt_min_v": 70.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 80.0,
    },
    "SUN-6K-G05": {
        "potencia_kw": 6.0, "familia": "Deye G05", "classe_corrente": "alta",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 18.0, "corrente_max_curto_a": 27.0,
        "tensao_max_v": 550.0, "mppt_min_v": 70.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 80.0,
    },
    "SUN-7K-G05": {
        "potencia_kw": 7.0, "familia": "Deye G05", "classe_corrente": "alta",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 18.0, "corrente_max_curto_a": 27.0,
        "tensao_max_v": 550.0, "mppt_min_v": 70.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 80.0,
    },
    "SUN-7.5K-G05": {
        "potencia_kw": 7.5, "familia": "Deye G05", "classe_corrente": "alta",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 18.0, "corrente_max_curto_a": 27.0,
        "tensao_max_v": 550.0, "mppt_min_v": 70.0, "mppt_max_v": 500.0,
        "tensao_partida_v": 80.0,
    },
    # --- TRIFASICOS, acima de 10 kW (fase 4, item 7, 10/11/2026) ---------
    # UM modelo por tensao de rede em cada degrau (decisao da aluna, 10/11):
    # "tensao_rede" diz em qual rede ele liga. Growatt onde ha registro; no
    # degrau de 12 kW em 127/220 V a Growatt nao tem modelo registrado, e
    # entra a Deye. O arranjo so e aprovado se passar nos DOIS modelos do
    # degrau (ver escolher_inversor_compativel): quem instala escolhe o da
    # tensao da casa, e o resultado tem de valer para qualquer um deles.
    #
    # Registros Inmetro ATIVOS (consulta oficial, 10/11/2026) e folhas
    # conferidas pela IMAGEM em 10/11/2026 (claude/item7_passo3a_folhas_10-11.txt).
    # Regra de sempre: nenhum limite mais folgado que a folha - quando duas
    # edicoes oficiais discordam, vale o numero mais apertado.
    #
    # STRINGS EM PARALELO. Estes modelos (menos os MOD) aceitam 2 strings no
    # mesmo MPPT. As duas ficam em paralelo: as correntes SE SOMAM, e as
    # strings precisam ter o mesmo numero de modulos. Ver
    # verificar_compatibilidade_paralelo(). "corrente_max_string_a" e o
    # limite POR STRING que a folha da (so as Growatt MID dao: 16 A).
    #
    # Deye SUN-12K-G02-LV - 005558/2021. Folhas Deye 06/2021 e 04/2023:
    # 800 V; partida 250 V; MPPT 200-700 V; 32+32 A; curto 48+48 A; 2 MPPT;
    # strings por MPPT 2 (2021) ou 3 (2023) -> 2.
    "SUN-12K-G02-LV": {
        "potencia_kw": 12.0, "familia": "Deye G02-LV", "classe_corrente": "alta",
        "tensao_rede": "127/220 V", "registro_inmetro": "005558/2021",
        "mppts": 2, "strings_por_mppt": 2,
        "corrente_max_entrada_a": 32.0, "corrente_max_curto_a": 48.0,
        "tensao_max_v": 800.0, "mppt_min_v": 200.0, "mppt_max_v": 700.0,
        "tensao_partida_v": 250.0,
    },
    # Growatt MOD 12/15KTL3-X2(Pro) - 019288/2024 e 019299/2024. Ficha
    # Growatt Brasil 11/2024: 1100 V; partida 160 V; MPPT 140-1000 V;
    # 2 MPPT x 1 string; 20 A; curto 25 A; 220/380 V.
    "MOD12KTL3-X2(Pro)": {
        "potencia_kw": 12.0, "familia": "Growatt MOD X2", "classe_corrente": "alta",
        "tensao_rede": "220/380 V", "registro_inmetro": "019288/2024",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 20.0, "corrente_max_curto_a": 25.0,
        "tensao_max_v": 1100.0, "mppt_min_v": 140.0, "mppt_max_v": 1000.0,
        "tensao_partida_v": 160.0,
    },
    "MOD15KTL3-X2(Pro)": {
        "potencia_kw": 15.0, "familia": "Growatt MOD X2", "classe_corrente": "alta",
        "tensao_rede": "220/380 V", "registro_inmetro": "019299/2024",
        "mppts": 2, "strings_por_mppt": 1,
        "corrente_max_entrada_a": 20.0, "corrente_max_curto_a": 25.0,
        "tensao_max_v": 1100.0, "mppt_min_v": 140.0, "mppt_max_v": 1000.0,
        "tensao_partida_v": 160.0,
    },
    # Growatt MID 15/20/25KTL3-XL2 - 000700, 000888 e 000896/2025. Ficha
    # Growatt Brasil 06/2025 (sem a linha de tensao maxima) e manual PT
    # 12/2024, secao 17.1: 800 V; partida 200 V; MPP 200-800 V; 4 MPPT x 2
    # strings; 32 A e curto 40 A por MPPT; 127/220 V. Capa: "Ate 16A de
    # corrente de entrada" (por string).
    "MID15KTL3-XL2": {
        "potencia_kw": 15.0, "familia": "Growatt MID XL2", "classe_corrente": "alta",
        "tensao_rede": "127/220 V", "registro_inmetro": "000700/2025",
        "mppts": 4, "strings_por_mppt": 2,
        "corrente_max_entrada_a": 32.0, "corrente_max_curto_a": 40.0,
        "corrente_max_string_a": 16.0,
        "tensao_max_v": 800.0, "mppt_min_v": 200.0, "mppt_max_v": 800.0,
        "tensao_partida_v": 200.0,
    },
    "MID20KTL3-XL2": {
        "potencia_kw": 20.0, "familia": "Growatt MID XL2", "classe_corrente": "alta",
        "tensao_rede": "127/220 V", "registro_inmetro": "000888/2025",
        "mppts": 4, "strings_por_mppt": 2,
        "corrente_max_entrada_a": 32.0, "corrente_max_curto_a": 40.0,
        "corrente_max_string_a": 16.0,
        "tensao_max_v": 800.0, "mppt_min_v": 200.0, "mppt_max_v": 800.0,
        "tensao_partida_v": 200.0,
    },
    "MID25KTL3-XL2": {
        "potencia_kw": 25.0, "familia": "Growatt MID XL2", "classe_corrente": "alta",
        "tensao_rede": "127/220 V", "registro_inmetro": "000896/2025",
        "mppts": 4, "strings_por_mppt": 2,
        "corrente_max_entrada_a": 32.0, "corrente_max_curto_a": 40.0,
        "corrente_max_string_a": 16.0,
        "tensao_max_v": 800.0, "mppt_min_v": 200.0, "mppt_max_v": 800.0,
        "tensao_partida_v": 200.0,
    },
    # Growatt MID 20/25KTL3-X2 - 002241/2025 e 002243/2025. Ficha Growatt
    # Brasil 11/2024: 1100 V; partida 200 V; MPPT 200-1000 V; 2 MPPT x 2
    # strings; 32 A e curto 40 A por MPPT (no de 25 kW, 32/36 A e 40/45 A:
    # vale o menor); 220/380 V. Capa: "Corrente maxima de entrada de string
    # 16A".
    "MID20KTL3-X2": {
        "potencia_kw": 20.0, "familia": "Growatt MID X2", "classe_corrente": "alta",
        "tensao_rede": "220/380 V", "registro_inmetro": "002241/2025",
        "mppts": 2, "strings_por_mppt": 2,
        "corrente_max_entrada_a": 32.0, "corrente_max_curto_a": 40.0,
        "corrente_max_string_a": 16.0,
        "tensao_max_v": 1100.0, "mppt_min_v": 200.0, "mppt_max_v": 1000.0,
        "tensao_partida_v": 200.0,
    },
    "MID25KTL3-X2": {
        "potencia_kw": 25.0, "familia": "Growatt MID X2", "classe_corrente": "alta",
        "tensao_rede": "220/380 V", "registro_inmetro": "002243/2025",
        "mppts": 2, "strings_por_mppt": 2,
        "corrente_max_entrada_a": 32.0, "corrente_max_curto_a": 40.0,
        "corrente_max_string_a": 16.0,
        "tensao_max_v": 1100.0, "mppt_min_v": 200.0, "mppt_max_v": 1000.0,
        "tensao_partida_v": 200.0,
    },
}


# ---------------------------------------------------------------------
# Grandezas do modulo corrigidas por temperatura
# ---------------------------------------------------------------------
def voc_na_temperatura_minima(modulo, temperatura_c=TEMP_MINIMA_PROJETO_C):
    """
    Tensao de circuito aberto de UM modulo na condicao mais fria.

    E o numero que manda na verificacao 3, e a razao e contraintuitiva
    para quem esta comecando: painel fotovoltaico produz MAIS tensao no
    frio, nao no calor. O coeficiente de Voc e negativo, entao abaixar a
    temperatura AUMENTA a tensao. O pior caso para o inversor, portanto,
    e uma manha fria de inverno com o sistema recem-ligado - nao um meio
    -dia de verao.

    Por isso a tensao que o inversor precisa suportar e a Voc corrigida
    para o frio (Equacao 12 e verificacao 3 do Quadro 1, secao 3.4 do
    artigo; Pinho e Galdino, 2014).
    """
    variacao = (modulo["coef_voc"] / 100) * (temperatura_c - TEMP_STC_C)
    return modulo["voc"] * (1 + variacao)


def vmp_na_temperatura_maxima(modulo, temperatura_c=TEMP_MAXIMA_CELULA_C):
    """
    Tensao de maxima potencia de UM modulo na condicao mais quente.

    Espelho da funcao acima: no calor a tensao CAI, e e por isso que a
    condicao quente e a que manda na verificacao 4. Se a tensao do arranjo
    cair abaixo do piso da janela de MPPT, o inversor deixa de rastrear o
    ponto de maxima potencia - o arranjo para de funcionar exatamente no
    dia de mais sol.

    O coeficiente usado aqui e o DERIVADO (ver o catalogo de modulos).
    """
    variacao = (modulo["coef_vmp"] / 100) * (temperatura_c - TEMP_STC_C)
    return modulo["vmp"] * (1 + variacao)


def isc_na_temperatura_maxima(modulo, temperatura_c=TEMP_MAXIMA_CELULA_C):
    """
    Corrente de curto-circuito de UM modulo na condicao mais quente.

    E o numero que manda na verificacao 1. Ao contrario da tensao, a
    corrente tem coeficiente de temperatura POSITIVO: ela SOBE quando a
    celula esquenta. Logo o pior caso para o limite de curto-circuito do
    inversor nao e a manha fria (esse e o caso da tensao), e sim a celula
    quente do meio-dia de verao.

    O principio e o mesmo da tensao maxima: comparar o limite do
    equipamento com a grandeza do arranjo corrigida para a condicao MENOS
    FAVORAVEL, nunca com o valor de catalogo nas STC.

    Numa string em serie a corrente do arranjo e a de um modulo so, entao
    esta funcao nao depende do numero de modulos.
    """
    variacao = (modulo["coef_isc"] / 100) * (temperatura_c - TEMP_STC_C)
    return modulo["isc"] * (1 + variacao)


# ---------------------------------------------------------------------
# Por que a corrente tambem e corrigida por temperatura (18/09/2026)
# ---------------------------------------------------------------------
# O QUE ESTAVA INCONSISTENTE. As verificacoes de tensao (3 e 4) sempre
# usaram a tensao corrigida para a temperatura de pior caso, enquanto a
# verificacao 1 comparava a Isc de catalogo, nas STC, com o limite de
# curto-circuito do inversor. Eram dois criterios diferentes para o mesmo
# tipo de pergunta - "o arranjo cabe no limite absoluto do equipamento?"
# - e a assimetria nao tinha justificativa tecnica.
#
# EFEITO MEDIDO: nenhum caso muda. A 70 C a Isc do Jinko sobe de 14,25 A
# para 14,54 A, ainda 9% abaixo dos 16 A do MPPT; os modulos de 210 mm ja
# reprovavam nas STC e continuam reprovando. A correcao nao foi feita para
# mudar resultado, e sim porque a verificacao passa a perguntar a coisa
# certa.
#
# POR QUE A CORRECAO PARA NA VERIFICACAO 1 E NAO VAI PARA A 2. Sao
# perguntas de natureza diferente:
#
#   - A verificacao 1 pergunta o que o equipamento precisa SUPORTAR, e
#     isso se avalia no pior caso fisico. Corrigir e obrigatorio.
#   - A verificacao 2 compara duas grandezas DE CATALOGO - a corrente de
#     maxima potencia do modulo contra a corrente maxima utilizavel de
#     entrada do inversor - que e exatamente a comparacao que o fabricante
#     faz na propria tabela de exemplos da nota tecnica da SMA. Em cima
#     dessa comparacao ja existe o limiar declarado de 10%, que e a
#     tolerancia onde cabe a variacao de operacao.
#
# TESTADO ANTES DE DECIDIR: aplicar a mesma correcao a Imp levaria o
# excesso do Jinko contra a familia MIN de 12,5 A de 8,96% para 11,17%,
# reprovando um par que o fabricante aprova e trocando o inversor do
# Caso 3. Ou seja, estender a correcao a verificacao 2 nao aumentaria a
# seguranca - mudaria o resultado por causa de uma tolerancia, o que e
# outra discussao.
#
# LIMITE DE ESCOPO DECLARADO. Fatores de seguranca de condutores e
# dispositivos de protecao sao da instalacao CC - cabo e protecao -, que a
# plataforma nao dimensiona (secao 3.5 do artigo), e nao da comparacao com
# o limite declarado do inversor.


# ---------------------------------------------------------------------
# Limites de serie: quantos modulos cabem numa string
# ---------------------------------------------------------------------
def limites_de_modulos_por_string(modulo, inversor):
    """
    Devolve o minimo e o maximo de modulos que podem ser ligados em serie
    numa string, para este par modulo+inversor.

      maximo = tensao maxima do inversor / Voc do modulo a frio  (piso)
      minimo = piso da janela de MPPT / Vmp do modulo a quente   (teto)

    O maximo arredonda para BAIXO e o minimo para CIMA: os dois erram para
    dentro da faixa segura.
    """
    maximo = math.floor(inversor["tensao_max_v"] / voc_na_temperatura_minima(modulo))
    minimo = math.ceil(inversor["mppt_min_v"] / vmp_na_temperatura_maxima(modulo))
    return {"minimo": max(minimo, 1), "maximo": maximo}


def dividir_arranjo_em_strings(n_modulos, modulo, inversor):
    """
    Distribui os modulos entre as entradas do inversor, usando o MENOR
    numero de strings que respeite os limites de serie.

    Devolve uma lista com quantos modulos ficam em cada string, ou None
    quando nao existe divisao valida.

    NOTA DE PROJETO: com MPPTs independentes, strings de tamanhos
    diferentes sao validas e comuns na pratica (6+5, por exemplo). Cada
    MPPT rastreia a sua string separadamente, entao nao e preciso forcar
    strings iguais - forcar so reduziria as combinacoes possiveis sem
    ganho tecnico nenhum.
    """
    limites = limites_de_modulos_por_string(modulo, inversor)
    max_strings = inversor["mppts"] * inversor["strings_por_mppt"]

    for quantidade in range(1, max_strings + 1):
        base, resto = divmod(n_modulos, quantidade)
        if base == 0:
            continue
        menor_string = base
        maior_string = base + (1 if resto else 0)
        if menor_string >= limites["minimo"] and maior_string <= limites["maximo"]:
            return [base + 1] * resto + [base] * (quantidade - resto)

    return None


# ---------------------------------------------------------------------
# As quatro verificacoes
# ---------------------------------------------------------------------
def verificar_compatibilidade(n_modulos, chave_modulo, nome_inversor):
    """
    Roda as quatro verificacoes para um arranjo de n modulos num inversor.

    Devolve um dicionario com o veredito de cada uma, os numeros que
    sustentam o veredito e a configuracao de strings quando ela existe.
    Nada aqui levanta excecao: reprovar e uma resposta legitima, e quem
    decide o que fazer com ela e o simulacao.py.

    O campo "minimo_de_modulos" existe para quem chama poder CORRIGIR o
    arranjo em vez de so reprova-lo - ver dimensionar_arranjo().
    """
    modulo = CATALOGO_MODULOS[chave_modulo]
    inversor = CATALOGO_INVERSORES[nome_inversor]
    # Fase 4, item 7 (10/11/2026): inversor que aceita mais de uma string no
    # mesmo MPPT vai pela conta com strings em paralelo, abaixo. Todos os
    # inversores ate 10 kW tem 1 string por MPPT no catalogo e seguem por
    # este caminho, que nao mudou.
    if inversor["strings_por_mppt"] > 1:
        return verificar_compatibilidade_paralelo(n_modulos, chave_modulo, nome_inversor)
    limites = limites_de_modulos_por_string(modulo, inversor)
    max_strings = inversor["mppts"] * inversor["strings_por_mppt"]

    # --- 1) SEGURANCA: corrente de curto-circuito
    # Nao depende do numero de modulos: numa string em serie a corrente do
    # arranjo e a de um modulo so. A Isc entra corrigida para a celula
    # quente, que e a condicao menos favoravel para esta verificacao.
    isc_quente = isc_na_temperatura_maxima(modulo)
    v1 = isc_quente <= inversor["corrente_max_curto_a"]

    # --- 2) DESEMPENHO: corrente de operacao contra a maxima utilizavel
    excesso = modulo["imp"] / inversor["corrente_max_entrada_a"] - 1
    v2 = excesso <= EXCESSO_CORRENTE_ACEITAVEL

    strings = dividir_arranjo_em_strings(n_modulos, modulo, inversor)

    if strings is None:
        poucos = n_modulos < limites["minimo"]
        return {
            "aprovado": False,
            "strings": None,
            "modulos_por_string": None,
            "verificacao_1_curto_circuito": v1,
            "verificacao_2_corrente_entrada": v2,
            "verificacao_3_tensao_maxima": None,
            "verificacao_4_tensao_minima": None,
            "excesso_corrente": excesso,
            "isc_a_quente_a": isc_quente,
            "tensao_maxima_a_frio_v": None,
            "tensao_mpp_a_quente_v": None,
            "limites_por_string": limites,
            "minimo_de_modulos": limites["minimo"] if poucos else None,
            "maximo_de_modulos": limites["maximo"] * max_strings,
            "motivo": "poucos_modulos" if poucos else "muitos_modulos",
        }

    tensao_frio = max(strings) * voc_na_temperatura_minima(modulo)
    tensao_quente = min(strings) * vmp_na_temperatura_maxima(modulo)

    # --- 3) SEGURANCA: tensao maxima a frio
    v3 = tensao_frio <= inversor["tensao_max_v"]
    # --- 4) OPERACAO: Vmp a quente contra o piso da janela de MPPT
    v4 = tensao_quente >= inversor["mppt_min_v"]

    return {
        "aprovado": bool(v1 and v2 and v3 and v4),
        "strings": len(strings),
        "modulos_por_string": strings,
        "verificacao_1_curto_circuito": v1,
        "verificacao_2_corrente_entrada": v2,
        "verificacao_3_tensao_maxima": v3,
        "verificacao_4_tensao_minima": v4,
        "excesso_corrente": excesso,
        "isc_a_quente_a": isc_quente,
        "tensao_maxima_a_frio_v": tensao_frio,
        "tensao_mpp_a_quente_v": tensao_quente,
        # Informativo: a tensao de partida e o que o arranjo precisa
        # entregar para o inversor ligar de manha. Nao reprova o par (o
        # arranjo parte frio, e frio a tensao e mais alta), mas vai no
        # retorno para nao se perder.
        "acima_da_tensao_de_partida": tensao_quente >= inversor["tensao_partida_v"],
        "limites_por_string": limites,
        "minimo_de_modulos": limites["minimo"],
        "maximo_de_modulos": limites["maximo"] * max_strings,
        "motivo": "",
    }


# ---------------------------------------------------------------------
# STRINGS EM PARALELO NO MESMO MPPT (fase 4, item 7, 10/11/2026)
# ---------------------------------------------------------------------
# Os inversores trifasicos acima de 10 kW aceitam 2 strings em cada MPPT.
# As duas ficam em PARALELO, e isso muda a conta da corrente:
#
#   - a TENSAO do MPPT continua sendo a de UMA string (por isso as strings
#     do mesmo MPPT precisam ter o MESMO numero de modulos: em paralelo,
#     strings de tensoes diferentes se puxariam uma a outra);
#   - a CORRENTE do MPPT passa a ser a SOMA das strings: k strings dao k
#     vezes a corrente de um modulo.
#
# Sem esta conta, o motor compararia a corrente de UMA string com o limite
# do MPPT inteiro e aprovaria arranjos que passam do limite - e a frase
# "a corrente nao melhora com sistema maior", que vale para strings em
# serie, deixaria de ser verdade aqui: com strings em paralelo a corrente
# do MPPT CRESCE com o numero de strings.
#
# AS VERIFICACOES SAO AS MESMAS QUATRO, aplicadas ao MPPT mais carregado:
#   1. k x Isc a quente <= curto-circuito maximo do MPPT (sem tolerancia);
#   2. k x Imp <= 1,10 x corrente maxima de entrada do MPPT, e, quando a
#      folha da um limite por string, Imp <= 1,10 x esse limite (o mesmo
#      criterio de desempenho da verificacao 2 de sempre);
#   3. tensao a frio da string mais longa <= tensao maxima;
#   4. Vmp a quente da string mais curta >= piso do MPPT.
#
# COMO DIVIDE. Como na funcao de sempre, usa o MENOR numero de strings que
# funcione; as strings sao espalhadas pelos MPPTs o mais por igual possivel
# (so poe 2 no mesmo MPPT quando todos ja tem 1), e cada MPPT pode ter um
# comprimento proprio.
def dividir_arranjo_em_mppts(n_modulos, modulo, inversor):
    """
    Divide n modulos em strings, agrupadas por MPPT. Devolve a lista de
    MPPTs usados, cada um como {"strings": k, "modulos_por_string": L}, ou
    None quando nao ha divisao valida.

    So existe para inversores com mais de uma string por MPPT.
    """
    limites = limites_de_modulos_por_string(modulo, inversor)
    k_max = strings_por_mppt_permitidas_pela_corrente(modulo, inversor)
    if k_max == 0:
        return None
    mppts = inversor["mppts"]

    for total in range(1, mppts * k_max + 1):
        q, r = divmod(total, mppts)
        grupos = [g for g in [q + 1] * r + [q] * (mppts - r) if g > 0]
        base = n_modulos // total
        if base == 0:
            continue
        opcoes = [L for L in range(base - 1, base + 3)
                  if limites["minimo"] <= L <= limites["maximo"]]
        melhor = None
        for comprimentos in itertools.product(opcoes, repeat=len(grupos)):
            if sum(k * L for k, L in zip(grupos, comprimentos)) != n_modulos:
                continue
            chave = (max(comprimentos) - min(comprimentos),
                     tuple(-L for L in comprimentos))
            if melhor is None or chave < melhor[0]:
                melhor = (chave, comprimentos)
        if melhor is not None:
            return [{"strings": k, "modulos_por_string": L}
                    for k, L in zip(grupos, melhor[1])]
    return None


def strings_por_mppt_permitidas_pela_corrente(modulo, inversor):
    """
    Quantas strings, no maximo, cabem em paralelo num MPPT sem passar dos
    limites de corrente (verificacoes 1 e 2), ate o que a folha permite.
    Devolve 0 quando nem uma string cabe.
    """
    isc_quente = isc_na_temperatura_maxima(modulo)
    limite_string = inversor.get("corrente_max_string_a")
    if limite_string and modulo["imp"] / limite_string - 1 > EXCESSO_CORRENTE_ACEITAVEL:
        return 0
    k_max = 0
    for k in range(1, inversor["strings_por_mppt"] + 1):
        if (k * isc_quente <= inversor["corrente_max_curto_a"]
                and k * modulo["imp"] / inversor["corrente_max_entrada_a"] - 1
                <= EXCESSO_CORRENTE_ACEITAVEL):
            k_max = k
    return k_max


def verificar_compatibilidade_paralelo(n_modulos, chave_modulo, nome_inversor):
    """
    As quatro verificacoes para inversor com strings em paralelo no mesmo
    MPPT. Devolve o mesmo dicionario de verificar_compatibilidade(), com
    tres campos a mais: "mppts_usados" (strings e comprimento de cada MPPT),
    "corrente_operacao_mppt_a" e "corrente_curto_mppt_a" (as do MPPT mais
    carregado).
    """
    modulo = CATALOGO_MODULOS[chave_modulo]
    inversor = CATALOGO_INVERSORES[nome_inversor]
    limites = limites_de_modulos_por_string(modulo, inversor)
    isc_quente = isc_na_temperatura_maxima(modulo)
    limite_string = inversor.get("corrente_max_string_a")
    k_max = strings_por_mppt_permitidas_pela_corrente(modulo, inversor)
    grupos = dividir_arranjo_em_mppts(n_modulos, modulo, inversor)

    # O MPPT mais carregado. Sem divisao valida, a corrente e avaliada com
    # uma string so, como na funcao de sempre.
    k = max(g["strings"] for g in grupos) if grupos else 1
    corrente_operacao = k * modulo["imp"]
    corrente_curto = k * isc_quente
    excessos = [corrente_operacao / inversor["corrente_max_entrada_a"] - 1]
    if limite_string:
        excessos.append(modulo["imp"] / limite_string - 1)
    excesso = max(excessos)
    v1 = corrente_curto <= inversor["corrente_max_curto_a"]
    v2 = excesso <= EXCESSO_CORRENTE_ACEITAVEL
    maximo = limites["maximo"] * inversor["mppts"] * k_max

    if grupos is None:
        poucos = n_modulos < limites["minimo"]
        return {
            "aprovado": False,
            "strings": None,
            "modulos_por_string": None,
            "mppts_usados": None,
            "verificacao_1_curto_circuito": v1,
            "verificacao_2_corrente_entrada": v2,
            "verificacao_3_tensao_maxima": None,
            "verificacao_4_tensao_minima": None,
            "excesso_corrente": excesso,
            "isc_a_quente_a": isc_quente,
            "corrente_operacao_mppt_a": corrente_operacao,
            "corrente_curto_mppt_a": corrente_curto,
            "tensao_maxima_a_frio_v": None,
            "tensao_mpp_a_quente_v": None,
            "limites_por_string": limites,
            "minimo_de_modulos": limites["minimo"] if poucos else None,
            "maximo_de_modulos": maximo,
            "motivo": "poucos_modulos" if poucos else "muitos_modulos",
        }

    comprimentos = [g["modulos_por_string"] for g in grupos]
    strings = sorted([g["modulos_por_string"] for g in grupos
                      for _ in range(g["strings"])], reverse=True)
    tensao_frio = max(comprimentos) * voc_na_temperatura_minima(modulo)
    tensao_quente = min(comprimentos) * vmp_na_temperatura_maxima(modulo)
    v3 = tensao_frio <= inversor["tensao_max_v"]
    v4 = tensao_quente >= inversor["mppt_min_v"]

    return {
        "aprovado": bool(v1 and v2 and v3 and v4),
        "strings": len(strings),
        "modulos_por_string": strings,
        "mppts_usados": grupos,
        "verificacao_1_curto_circuito": v1,
        "verificacao_2_corrente_entrada": v2,
        "verificacao_3_tensao_maxima": v3,
        "verificacao_4_tensao_minima": v4,
        "excesso_corrente": excesso,
        "isc_a_quente_a": isc_quente,
        "corrente_operacao_mppt_a": corrente_operacao,
        "corrente_curto_mppt_a": corrente_curto,
        "tensao_maxima_a_frio_v": tensao_frio,
        "tensao_mpp_a_quente_v": tensao_quente,
        "acima_da_tensao_de_partida": tensao_quente >= inversor["tensao_partida_v"],
        "limites_por_string": limites,
        "minimo_de_modulos": limites["minimo"],
        "maximo_de_modulos": maximo,
        "motivo": "",
    }


def modelos_no_degrau(potencia_inversor_kw):
    """
    Modelos do catalogo que ocupam aquele degrau da grade INMETRO.

    A ordem e deliberada: Growatt primeiro, Deye depois. A Growatt e a
    marca usada na validacao com o PVsyst, entao ela e a referencia; a
    Deye so entra quando a corrente do modulo nao cabe na Growatt, que e
    exatamente o criterio tecnico que justifica a segunda familia.
    """
    nomes = [nome for nome, inv in CATALOGO_INVERSORES.items()
             if abs(inv["potencia_kw"] - potencia_inversor_kw) < 1e-9]
    nomes.sort(key=lambda n: 0 if CATALOGO_INVERSORES[n]["familia"].startswith("Growatt") else 1)
    return nomes


def escolher_inversor_compativel(n_modulos, chave_modulo, potencia_inversor_kw):
    """
    Primeiro modelo daquele degrau que passa nas quatro verificacoes.

    Devolve sempre um dicionario. Quando nenhum modelo passa, "inversor"
    vem None e "reprovados" traz o laudo de cada candidato, para a tela
    poder dizer POR QUE - que e a diferenca entre uma plataforma que
    ensina e uma que so recusa.

    "minimo_de_modulos_sugerido" e o menor arranjo que algum candidato
    aceitaria. Quando ele existe, a reprovacao tem conserto: basta subir o
    numero de modulos. Quando e None, o par modulo+degrau nao tem conserto
    naquele porte - e o caso do modulo de 210 mm em sistema pequeno.
    """
    if potencia_inversor_kw > LIMITE_MONOFASICO_KW + 1e-9:
        return _escolher_inversor_trifasico(n_modulos, chave_modulo, potencia_inversor_kw)

    reprovados = []
    minimos = []

    for nome in modelos_no_degrau(potencia_inversor_kw):
        laudo = verificar_compatibilidade(n_modulos, chave_modulo, nome)
        if laudo["aprovado"]:
            return {
                "inversor": nome,
                "laudo": laudo,
                "reprovados": reprovados,
                "minimo_de_modulos_sugerido": None,
            }
        reprovados.append((nome, laudo))
        # So vale subir o arranjo quando a corrente passa: subir modulos
        # nao muda corrente nenhuma (eles ficam em SERIE).
        if (laudo["verificacao_1_curto_circuito"]
                and laudo["verificacao_2_corrente_entrada"]
                and laudo["motivo"] == "poucos_modulos"):
            minimos.append(laudo["minimo_de_modulos"])

    return {
        "inversor": None,
        "laudo": None,
        "reprovados": reprovados,
        "minimo_de_modulos_sugerido": min(minimos) if minimos else None,
    }


def _escolher_inversor_trifasico(n_modulos, chave_modulo, potencia_inversor_kw):
    """
    Degraus trifasicos (acima de 10 kW; fase 4, item 7). Cada degrau tem um
    modelo de referencia por tensao de rede, e a tela mostra os dois: o
    instalador escolhe conforme a rede da casa. Por isso o arranjo so e
    aprovado se passar em TODOS os modelos do degrau - vale o limite mais
    apertado entre eles (decisao da aluna, 10/11/2026).

    Devolve o mesmo dicionario de escolher_inversor_compativel(). O
    "inversor" e o modelo de 127/220 V (o primeiro da lista); os dois vem em
    "inversores_por_tensao", cada um com o seu laudo.
    """
    nomes = sorted(modelos_no_degrau(potencia_inversor_kw),
                   key=lambda n: (CATALOGO_INVERSORES[n]["tensao_rede"] != "127/220 V",
                                  not CATALOGO_INVERSORES[n]["familia"].startswith("Growatt")))
    laudos = [(nome, verificar_compatibilidade(n_modulos, chave_modulo, nome)) for nome in nomes]
    reprovados = [(nome, laudo) for nome, laudo in laudos if not laudo["aprovado"]]

    if laudos and not reprovados:
        return {
            "inversor": nomes[0],
            "laudo": laudos[0][1],
            "reprovados": [],
            "minimo_de_modulos_sugerido": None,
            "inversores_por_tensao": [
                {"modelo": nome, "tensao_rede": CATALOGO_INVERSORES[nome]["tensao_rede"],
                 "familia": CATALOGO_INVERSORES[nome]["familia"], "laudo": laudo}
                for nome, laudo in laudos],
        }

    # Tem conserto subindo o numero de modulos so se TODOS os reprovados
    # reprovaram por poucos modulos com a corrente em ordem; o arranjo
    # precisa entao do MAIOR dos minimos, para passar em todos.
    minimos = []
    for _nome, laudo in reprovados:
        if (laudo["verificacao_1_curto_circuito"]
                and laudo["verificacao_2_corrente_entrada"]
                and laudo["motivo"] == "poucos_modulos"):
            minimos.append(laudo["minimo_de_modulos"])
        else:
            minimos = None
            break
    return {
        "inversor": None,
        "laudo": None,
        "reprovados": reprovados,
        "minimo_de_modulos_sugerido": max(minimos) if minimos else None,
    }


# ---------------------------------------------------------------------
# O MINIMO ELETRICO DO ARRANJO - erro novo, encontrado em 15/09/2026
# ---------------------------------------------------------------------
def dimensionar_arranjo(n_modulos_por_energia, chave_modulo, fdi=0.80):
    """
    Fecha o arranjo: parte do numero de modulos que a ENERGIA pede
    (Equacao 4) e devolve o numero que a ELETRICIDADE permite, junto com o
    inversor e a configuracao de strings.

    O ERRO QUE ESTA FUNCAO CORRIGE. Ate 15/09/2026 a plataforma chegava a
    recomendar "1 painel + inversor de 1,5 kW". Um modulo Jinko de 600 Wp
    a 70 C entrega 37,42 V, e a janela de MPPT do MIC1500TL-X comeca em
    50 V: o inversor nao rastreia. O arranjo simplesmente nao funciona.
    Atingia consumos de 60 a 100 kWh/mes na ligacao monofasica, 80 a 120
    na bifasica e 130 a 170 na trifasica - 15 pontos da varredura.

    POR QUE INVERSOR MENOR NAO RESOLVE, e isso importa para a defesa: o
    problema e de TENSAO, nao de potencia. A janela de MPPT nao desce
    junto com o degrau de potencia, porque quem define o piso e a
    topologia - o inversor precisa elevar a tensao continua ate o pico da
    rede de 220 V. Um arranjo de 37 V nao alimenta um inversor de string
    de 220 V, tenha ele 1,5 kW ou 750 W.

    A CORRECAO NAO INVENTA CRITERIO. O minimo sai da mesma conta das
    outras verificacoes: piso da janela de MPPT dividido pela Vmp do
    modulo a quente, arredondado para cima. Para o Jinko com o MIC1500 da
    exatamente 2.

    POR QUE O LACO. Subir o numero de modulos sobe a potencia instalada,
    que pode subir o degrau do inversor, que pode ter outro piso de MPPT e
    portanto outro minimo. O laco resolve essa ida e volta. Ele converge
    depressa (medido: no maximo duas voltas em toda a faixa residencial);
    o teto de 12 tentativas existe so para o programa nunca travar.

    CUSTO DESTA CORRECAO, a ser DECLARADO na tela e no artigo: nessa faixa
    o menor arranjo que funciona eletricamente ja gera mais do que a casa
    consegue compensar. A potencia que a Equacao 3 pede ali vai de 0,250 a
    0,583 kWp, e o minimo eletrico e 1,20 kWp - de 2 a 4,8 vezes. Nao e
    folga de projeto nem escolha: e o menor sistema que existe. Esconder
    isso seria repetir o erro que o T16 corrigiu.

    MEDIDO (15/09/2026, antes do T19 e do T20): aplicar o minimo NAO criou
    nenhum bloqueio novo do T18. Os 15 pontos continuaram se pagando dentro
    dos 25 anos da garantia de desempenho dos modulos, o pior deles em
    299,5 meses contra o limite de 300 - margem apertada. O modelo nao
    inclui troca de inversor (limitacao declarada), que afastaria o
    payback.
    """
    modulo = CATALOGO_MODULOS[chave_modulo]
    n_modulos = max(int(n_modulos_por_energia), 1)
    subiu_pelo_minimo_eletrico = False

    for _tentativa in range(12):
        potencia_kwp = potencia_instalada(n_modulos, modulo["potencia_wp"])
        comercial = potencia_inversor_comercial(potencia_inversor(potencia_kwp, fdi))
        escolha = escolher_inversor_compativel(n_modulos, chave_modulo,
                                               comercial["potencia_kw"])

        if escolha["inversor"] is not None:
            return {
                "aprovado": True,
                "chave_modulo": chave_modulo,
                "numero_modulos": n_modulos,
                "numero_modulos_por_energia": int(n_modulos_por_energia),
                "subiu_pelo_minimo_eletrico": subiu_pelo_minimo_eletrico,
                "potencia_instalada_kwp": potencia_kwp,
                "inversor": escolha["inversor"],
                "inversor_comercial": comercial,
                "laudo": escolha["laudo"],
                "reprovados": escolha["reprovados"],
                # Fase 4, item 7: so nos degraus trifasicos (os dois
                # modelos, um por tensao de rede). None ate 10 kW.
                "inversores_por_tensao": escolha.get("inversores_por_tensao"),
                "motivo": "",
            }

        sugerido = escolha["minimo_de_modulos_sugerido"]
        if sugerido is None or sugerido <= n_modulos:
            # Sem conserto por numero de modulos. E o caso do modulo de
            # corrente alta num degrau em que nao existe inversor de
            # corrente alta, ou do arranjo grande demais para as entradas.
            return {
                "aprovado": False,
                "chave_modulo": chave_modulo,
                "numero_modulos": n_modulos,
                "numero_modulos_por_energia": int(n_modulos_por_energia),
                "subiu_pelo_minimo_eletrico": subiu_pelo_minimo_eletrico,
                "potencia_instalada_kwp": potencia_kwp,
                "inversor": None,
                "inversor_comercial": comercial,
                "laudo": None,
                "reprovados": escolha["reprovados"],
                "motivo": _motivo_da_reprovacao(escolha["reprovados"]),
            }

        n_modulos = sugerido
        subiu_pelo_minimo_eletrico = True

    return {
        "aprovado": False, "chave_modulo": chave_modulo,
        "numero_modulos": n_modulos,
        "numero_modulos_por_energia": int(n_modulos_por_energia),
        "subiu_pelo_minimo_eletrico": subiu_pelo_minimo_eletrico,
        "potencia_instalada_kwp": potencia_instalada(n_modulos, modulo["potencia_wp"]),
        "inversor": None, "inversor_comercial": None, "laudo": None,
        "reprovados": [], "motivo": "nao_convergiu",
    }


def _motivo_da_reprovacao(reprovados):
    """
    Resume POR QUE nenhum candidato passou, para a tela nao precisar ler
    os laudos um a um. Devolve o motivo mais grave encontrado.
    """
    if not reprovados:
        return "sem_modelo_no_degrau"
    for _nome, laudo in reprovados:
        if not laudo["verificacao_1_curto_circuito"]:
            return "corrente_de_curto_acima_do_limite"
    for _nome, laudo in reprovados:
        if not laudo["verificacao_2_corrente_entrada"]:
            return "corrente_de_operacao_acima_do_limite"
    for _nome, laudo in reprovados:
        if laudo["verificacao_3_tensao_maxima"] is False:
            return "tensao_a_frio_acima_do_limite"
    for _nome, laudo in reprovados:
        if laudo["motivo"] == "muitos_modulos":
            return "arranjo_maior_que_as_entradas_do_inversor"
    return "sem_configuracao_valida"


# ---------------------------------------------------------------------
# Custo do sistema - CURVA DE PRECO GREENER (correcao T1, 12/09/2026)
# ---------------------------------------------------------------------
# O que mudou e por que:
# ate aqui o custo era montado peca por peca (paineis + inversor + 35%
# de BOS). A auditoria de 11/09 mostrou que esse BOS de 35% e o maior
# erro do motor (E1): a Greener mede o servico de instalacao entre 69% e
# 105% do valor do equipamento nos portes residenciais, nao 35%. O erro
# cresce conforme o sistema encolhe (de -3% em 5,4 kWp a -31% em 1,8 kWp),
# porque instalar um sistema pequeno nao e proporcionalmente mais barato:
# projeto, ART, deslocamento e homologacao quase nao encolhem.
#
# Agora o custo vem do PRECO DE MERCADO DO SISTEMA PRONTO, medido pela
# Greener junto a milhares de integradores de todo o pais (precos de
# janeiro/2026). E preco ao cliente final, ja incluindo
# equipamento, mao de obra, projeto e homologacao.
#
# FONTE: GREENER. Estudo Estrategico - Solucoes Energeticas Distribuidas,
# Mercado Fotovoltaico. Marco/2026, precos de referencia de janeiro/2026.
# (No artigo: Equacao 10, calculada em custo_sistema_greener().)
CURVA_SISTEMA_GREENER = [(2.0, 3.44), (4.0, 2.66), (8.0, 2.21),
                         (12.0, 2.04), (30.0, 1.91)]

CURVA_KIT_GREENER = [(2.0, 1.68), (4.0, 1.42), (8.0, 1.26),
                     (12.0, 1.21), (30.0, 1.12)]

MENOR_PORTE_MEDIDO_KWP = 2.0
REFERENCIA_PRECOS = "Greener, marco/2026 (precos de janeiro/2026)"


def interpolar_preco_por_wp(potencia_kwp, curva):
    """
    Descobre o preco por Wp de um sistema de qualquer tamanho, a partir
    dos 5 tamanhos que a Greener mediu (2, 4, 8, 12 e 30 kWp).

    Por que INTERPOLAR (ligar os pontos com uma reta) e nao ajustar uma
    curva matematica: a reta passa exatamente por cima de todos os pontos
    medidos, enquanto um ajuste de curva erraria alguns deles. Alem disso,
    como a curva real e convexa (cai rapido e vai achatando), a reta entre
    dois pontos passa LIGEIRAMENTE POR CIMA da curva verdadeira - ou seja,
    erra para o custo um pouco maior, que e a direcao conservadora adotada
    em todo o modelo.

    Acima do maior porte medido (30 kWp) o preco trava no ultimo valor:
    esta fora do escopo residencial deste trabalho.
    """
    if potencia_kwp >= curva[-1][0]:
        return curva[-1][1]

    if potencia_kwp <= curva[0][0]:
        # Abaixo do menor ponto medido: continua a inclinacao do primeiro
        # trecho. So o KIT usa esta extrapolacao (ver custo_sistema_greener).
        (x1, y1), (x2, y2) = curva[0], curva[1]
        inclinacao = (y2 - y1) / (x2 - x1)
        return y1 + inclinacao * (potencia_kwp - x1)

    for (x1, y1), (x2, y2) in zip(curva, curva[1:]):
        if x1 <= potencia_kwp <= x2:
            inclinacao = (y2 - y1) / (x2 - x1)
            return y1 + inclinacao * (potencia_kwp - x1)


def custo_sistema_greener(potencia_instalada_kwp):
    """
    Custo total do sistema instalado, separado em equipamento e servico.

    De 2 kWp para cima: os dois numeros saem direto das curvas medidas
    (a curva do sistema completo e a curva do kit; o servico e a diferenca
    entre as duas, que e como a propria Greener calcula).

    ABAIXO DE 2 kWp a Greener nao mede, e as duas parcelas se comportam de
    formas diferentes:
      - o EQUIPAMENTO encolhe junto com o sistema (menos painel, menos
        estrutura, menos cabo), entao segue a curva do kit;
      - o SERVICO quase nao encolhe: projeto eletrico, ART, deslocamento
        da equipe, homologacao e vistoria custam praticamente o mesmo para
        1 painel ou para 4. Por isso ele TRAVA no valor medido para 2 kWp.
    Isso reproduz, com a razao fisica por tras, o encarecimento por Wp dos
    sistemas muito pequenos - em vez de esticar uma reta no escuro.

    LIMITACAO A DECLARAR NO ARTIGO: abaixo de 2 kWp o valor e criterio
    adotado por este trabalho, nao dado medido. A flag
    "fora_da_faixa_medida" existe para a tela avisar o usuario.
    """
    potencia_wp = potencia_instalada_kwp * 1000

    preco_kit_por_wp = interpolar_preco_por_wp(potencia_instalada_kwp,
                                               CURVA_KIT_GREENER)
    custo_equipamentos = preco_kit_por_wp * potencia_wp

    if potencia_instalada_kwp >= MENOR_PORTE_MEDIDO_KWP:
        preco_sistema_por_wp = interpolar_preco_por_wp(potencia_instalada_kwp,
                                                       CURVA_SISTEMA_GREENER)
        custo_total = preco_sistema_por_wp * potencia_wp
        custo_servico = custo_total - custo_equipamentos
        fora_da_faixa = False
    else:
        preco_sistema_2kwp = interpolar_preco_por_wp(MENOR_PORTE_MEDIDO_KWP,
                                                     CURVA_SISTEMA_GREENER)
        preco_kit_2kwp = interpolar_preco_por_wp(MENOR_PORTE_MEDIDO_KWP,
                                                 CURVA_KIT_GREENER)
        custo_servico = ((preco_sistema_2kwp - preco_kit_2kwp)
                         * MENOR_PORTE_MEDIDO_KWP * 1000)
        custo_total = custo_equipamentos + custo_servico
        fora_da_faixa = True

    return {
        "custo_equipamentos": custo_equipamentos,
        "custo_servico_instalacao": custo_servico,
        "custo_total": custo_total,
        "preco_por_wp": custo_total / potencia_wp,
        "fora_da_faixa_medida": fora_da_faixa,
    }


# ---------------------------------------------------------------------
# Custos por equipamento - MODELO ANTIGO, DESATIVADO EM 13/09/2026 (T1)
# ---------------------------------------------------------------------
# ATENCAO: estas tres funcoes NAO alimentam mais o custo do sistema. Elas
# ficam no arquivo apenas como registro do modelo anterior, porque o
# artigo descreve a evolucao do motor de calculo. O custo agora vem de
# custo_sistema_greener(). O percentual de BOS de 35% usado aqui e o
# erro E1 documentado na auditoria de 11/09/2026.
def custo_paineis(n_paineis, potencia_painel_wp, preco_por_wp):
    potencia_total_wp = n_paineis * potencia_painel_wp
    return potencia_total_wp * preco_por_wp


def custo_inversor(potencia_inversor_kw, preco_por_kw):
    return potencia_inversor_kw * preco_por_kw


def custo_total_sistema(custo_paineis_reais, custo_inversor_reais, percentual_bos=0.35):
    custo_equipamentos = custo_paineis_reais + custo_inversor_reais
    return custo_equipamentos + (custo_equipamentos * percentual_bos)


# =======================================================================
# TESTE - valida a logica com o exemplo numerico que voce ja calculou
# a mao no Tema 2 (350 kWh, painel 550 Wp, TD 0,80, tarifa R$0,75/kWh)
# =======================================================================
if __name__ == "__main__":
    print("=== Teste do motor de calculo ===\n")

    # --- Dados de entrada ---
    consumo = 350            # kWh/mes (media informada pelo usuario)
    valor_fatura = 262.50    # R$ (350 kWh x R$0,75 = 262,50 -> so pra ter uma tarifa de teste)
    hsp_teste = 4.8          # valor DE TESTE - no Passo 2 isso vem da API da NASA POWER
    potencia_painel = 550    # Wp (opcao "Intermediario")
    # (preco_painel_wp e preco_inversor_kw ficaram sem uso no custo total
    #  depois da correcao T1 - o custo agora vem da curva Greener)
    # Correcao T19: o Fio B de teste passa a vir da tabela da ANEEL por
    # estado (ver FIO_B_POR_UF), e nao mais de um 0.20 sem fonte escrito
    # a mao aqui. Sem cidade neste teste, vale a mediana nacional.
    fio_b = FIO_B_PADRAO_REAIS_POR_KWH   # R$/kWh
    # Correcao T3a: o percentual vem da tabela da Lei 14.300/2022 pelo ano
    # corrente, e nao mais de um 0,60 escrito a mao aqui.
    ano_fio_b = ano_referencia_fio_b()
    percentual_fio_b = percentual_fio_b_vigente(ano_fio_b)
    # Correcao T16: o teste passa a declarar o tipo de ligacao, porque o
    # piso de disponibilidade agora entra no DIMENSIONAMENTO e nao so no
    # calculo da economia. Bifasica e a premissa padrao da plataforma.
    piso_mensal = piso_disponibilidade("bifasica")["piso_kwh"]

    # --- Passo a passo do calculo ---
    # Correcao T20: a tarifa e o valor economizado por kWh vem ANTES do
    # dimensionamento, porque o limite do custo de disponibilidade (art.
    # 655-I da REN ANEEL 1.000/2021) e em reais e depende dos dois.
    tarifa = tarifa_total(valor_fatura, consumo)
    economia_kwh = valor_economizado_por_kwh(tarifa, fio_b, percentual_fio_b)
    parcela_fio_b = tarifa - economia_kwh

    # Correcao T16: o alvo da Equacao 3 deixou de ser o consumo cheio e
    # passou a ser a parcela do consumo que a compensacao pode abater.
    consumo_anual = consumo * 12
    alvo = consumo_alvo_dimensionamento(consumo_anual, piso_mensal, None,
                                        tarifa, parcela_fio_b)

    # Correcao T17: quem entra na Equacao 2 e o consumo compensavel do
    # ANO, dividido por 365 - o mesmo calendario da Equacao 5.
    e_diaria = energia_diaria(alvo["consumo_compensavel_anual_kwh"])
    pot_teorica = potencia_sistema_teorica(e_diaria, hsp_teste, td=0.80)
    n_paineis = numero_paineis(pot_teorica, potencia_painel)
    pot_instalada = potencia_instalada(n_paineis, potencia_painel)
    pot_inv = potencia_inversor(pot_instalada, fdi=0.80)

    geracao_anual = geracao_estimada(pot_instalada, hsp_teste, td=0.80, dias=365)

    # Correcao T2: a economia sai da energia COMPENSAVEL (limitada pelo
    # consumo anual), nao da geracao bruta.
    # Correcao T16: o piso e passado tambem AQUI, para o teste medir a
    # economia com a mesma regra usada para dimensionar. Dimensionar com
    # piso e depois medir a economia sem ele produziria um resultado
    # falso - e exatamente a incoerencia entre duas partes do motor que
    # esta correcao existe para eliminar.
    e_compensavel = energia_compensavel_anual(geracao_anual, consumo_anual,
                                              piso_mensal, None,
                                              tarifa, parcela_fio_b)
    economia_anual_estim = economia_anual_estimada(e_compensavel, economia_kwh)
    economia_mensal_estim = economia_anual_estim / 12

    # Correcao T1: o custo vem da curva de preco da Greener (preco de
    # mercado do sistema pronto), e nao mais da soma dos equipamentos com
    # 35% de BOS.
    custos = custo_sistema_greener(pot_instalada)
    custo_total = custos["custo_total"]

    payback = payback_meses(custo_total, economia_mensal_estim)

    # --- Resultado ---
    print(f"Consumo medio informado:        {consumo:.0f} kWh/mes")
    print(f"Piso de disponibilidade:        {piso_mensal:.0f} kWh/mes (bifasica)")
    print(f"Alvo de dimensionamento (T16):  {alvo['alvo_mensal_kwh']:.2f} kWh/mes "
          f"({alvo['consumo_compensavel_anual_kwh']:.0f} kWh/ano)")
    print(f"Energia diaria necessaria:     {e_diaria:.2f} kWh/dia")
    print(f"Potencia teorica do sistema:    {pot_teorica:.2f} kWp")
    print(f"Numero de paineis:              {n_paineis}")
    print(f"Potencia instalada (real):      {pot_instalada:.2f} kWp")
    print(f"Potencia do inversor:           {pot_inv:.2f} kW")
    print(f"Geracao anual estimada:         {geracao_anual:.0f} kWh/ano")
    print(f"Consumo anual:                  {consumo_anual:.0f} kWh/ano")
    print(f"Energia compensavel (T2):       {e_compensavel:.0f} kWh/ano")
    print(f"Tarifa calculada:               R$ {tarifa:.2f}/kWh")
    print(f"Fio B cobrado ({ano_fio_b}):          {percentual_fio_b*100:.0f}% de R$ {fio_b:.2f}/kWh")
    print(f"Equipamentos (kit):             R$ {custos['custo_equipamentos']:.2f}")
    print(f"Instalacao e servicos:          R$ {custos['custo_servico_instalacao']:.2f}")
    print(f"Custo total do sistema:         R$ {custo_total:.2f} "
          f"(R$ {custos['preco_por_wp']:.2f}/Wp)")
    print(f"Economia anual estimada:        R$ {economia_anual_estim:.2f}")
    print(f"Economia mensal estimada:       R$ {economia_mensal_estim:.2f}")
    print(f"Payback:                        {payback:.1f} meses (~{payback/12:.1f} anos)")

    # ===================================================================
    # TESTE DO T15 - verificacao eletrica do arranjo (15/09/2026)
    # ===================================================================
    # Roda sempre junto com o teste acima, de proposito: o arranjo e a
    # parte do dimensionamento que nao aparece na tela, e um erro aqui
    # fica invisivel ate alguem tentar montar o sistema de verdade.
    print()
    print("=== T15: verificacao eletrica do arranjo ===\n")

    print(f"Premissas: {TEMP_MINIMA_PROJETO_C:.0f} C de celula (condicao mais fria) "
          f"e {TEMP_MAXIMA_CELULA_C:.0f} C de celula (mais quente)")
    print(f"Limiar de excesso de corrente adotado: "
          f"{EXCESSO_CORRENTE_ACEITAVEL*100:.0f}%\n")

    print("Modulos do catalogo, corrigidos por temperatura:")
    print(f"  {'modulo':34s} {'celula':>7s} {'coef Vmp':>9s} "
          f"{'Voc frio':>9s} {'Vmp quente':>11s} {'Isc STC':>8s} {'Isc quente':>11s}")
    for chave, mod in CATALOGO_MODULOS.items():
        print(f"  {mod['nome']:34s} {str(mod['formato_celula_mm'])+' mm':>7s} "
              f"{mod['coef_vmp']:>8.3f}% {voc_na_temperatura_minima(mod):>9.2f} "
              f"{vmp_na_temperatura_maxima(mod):>11.2f} {mod['isc']:>8.2f} "
              f"{isc_na_temperatura_maxima(mod):>11.2f}")
    print("  (o coeficiente de Vmp e derivado: coef. de Pmax menos o de Isc)")

    print("\nCorrente - NAO depende do tamanho do sistema:")
    print(f"  {'familia':13s} {'I DC max':>9s} {'Isc max':>8s}  "
          f"{'modulo':30s} {'Isc 70C':>8s} {'excesso':>8s}  resultado")
    vistas = []
    for nome_inv, inv in CATALOGO_INVERSORES.items():
        assinatura = (inv["familia"], inv["corrente_max_entrada_a"],
                      inv["corrente_max_curto_a"])
        if assinatura in vistas:
            continue
        vistas.append(assinatura)
        for chave, mod in CATALOGO_MODULOS.items():
            laudo = verificar_compatibilidade(4, chave, nome_inv)
            v1 = laudo["verificacao_1_curto_circuito"]
            v2 = laudo["verificacao_2_corrente_entrada"]
            estado = "passa" if (v1 and v2) else (
                "REPROVA (curto-circuito)" if not v1 else "REPROVA (corrente)")
            print(f"  {inv['familia']:13s} {inv['corrente_max_entrada_a']:>9.1f} "
                  f"{inv['corrente_max_curto_a']:>8.1f}  {mod['nome'][:30]:30s} "
                  f"{laudo['isc_a_quente_a']:>8.2f} "
                  f"{laudo['excesso_corrente']*100:>7.2f}%  {estado}")

    # HISTORICO (revisao geral, 07/10/2026): os numeros de modulos abaixo sao
    # os de 15/09/2026, antes do T20 - o teste confere a verificacao eletrica
    # desses arranjos, nao os casos de hoje (4, 5, 9, 3 e 4 modulos Jinko,
    # na ordem da lista: Lapa, Guaira, Manaus, Campinas, Cuiaba).
    print("\nOs 5 casos de validacao, com o dimensionamento de 15/09/2026 (antes do T20):")
    print(f"  {'caso':22s} {'mod':>4s} {'kWp':>6s}  {'inversor':14s} "
          f"{'strings':>8s} {'V frio':>8s} {'Vmp 70C':>8s}  laudo")
    casos_t15 = [
        ("1 Bom Jesus da Lapa", 3, "jinko_600"),
        ("2 Guaira",            4, "jinko_600"),
        ("3 Manaus",            8, "jinko_600"),
        ("4 Campinas",          2, "jinko_600"),
        ("5 Cuiaba",            3, "trina_670"),
    ]
    for nome_caso, n_mod, chave in casos_t15:
        arranjo = dimensionar_arranjo(n_mod, chave)
        if arranjo["aprovado"]:
            laudo = arranjo["laudo"]
            arranjo_txt = "+".join(str(x) for x in laudo["modulos_por_string"])
            print(f"  {nome_caso:22s} {arranjo['numero_modulos']:>4d} "
                  f"{arranjo['potencia_instalada_kwp']:>6.2f}  {arranjo['inversor']:14s} "
                  f"{arranjo_txt:>8s} {laudo['tensao_maxima_a_frio_v']:>8.1f} "
                  f"{laudo['tensao_mpp_a_quente_v']:>8.1f}  APROVADO")
        else:
            print(f"  {nome_caso:22s} {arranjo['numero_modulos']:>4d} "
                  f"{arranjo['potencia_instalada_kwp']:>6.2f}  {'-':14s} "
                  f"{'-':>8s} {'-':>8s} {'-':>8s}  REPROVADO: {arranjo['motivo']}")

    print("\nMinimo eletrico do arranjo (erro encontrado em 15/09/2026):")
    arranjo_um = dimensionar_arranjo(1, "jinko_600")
    modulo_jinko = CATALOGO_MODULOS["jinko_600"]
    mic1500 = CATALOGO_INVERSORES["MIC1500TL-X"]
    print(f"  1 modulo Jinko a {TEMP_MAXIMA_CELULA_C:.0f} C entrega "
          f"{vmp_na_temperatura_maxima(modulo_jinko):.2f} V")
    print(f"  a janela de MPPT do MIC1500TL-X comeca em "
          f"{mic1500['mppt_min_v']:.0f} V -> o inversor nao rastreia")
    print(f"  a plataforma corrige para {arranjo_um['numero_modulos']} modulos "
          f"({arranjo_um['potencia_instalada_kwp']:.2f} kWp), "
          f"subiu_pelo_minimo_eletrico={arranjo_um['subiu_pelo_minimo_eletrico']}")

