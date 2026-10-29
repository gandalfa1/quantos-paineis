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
atualizar_dados_aneel.py - busca na ANEEL os dados que envelhecem sozinhos
e grava os arquivos que a plataforma usa.

POR QUE ESTE PROGRAMA EXISTE (pedido da aluna, 01/10/2026): "a gente tem que
deixar o negocio do Fio B programado, para ir mudando conforme a data mudar".
Cada distribuidora reajusta a tarifa UMA VEZ POR ANO, em data propria. A
tabela do Fio B dentro do calculo.py e um retrato: em 22/09/2026 ela estava
certa, em 22/10/2026 ja tem dois estados vencidos (DF e GO). Ate aqui a unica
saida era corrigir na mao.

O QUE ELE GRAVA (dois arquivos, na pasta da plataforma):
  1. fio_b_por_distribuidora.csv - o Fio B (R$/kWh) de cada distribuidora,
     com CNPJ, vigencia e resolucao homologatoria.
  2. static/distribuidoras_por_municipio.json - para cada municipio (codigo
     IBGE), quais distribuidoras o atendem. E o que permite a plataforma usar
     o Fio B da distribuidora DA PESSOA, e nao o da capital do estado.

O QUE ELE NUNCA FAZ: gravar dado pela metade. Ver "AS TRAVAS", mais abaixo.

COMO RODAR (dentro da pasta da plataforma, com internet):
    python atualizar_dados_aneel.py --conferir     (so mostra o que mudaria)
    python atualizar_dados_aneel.py                (confere e grava)

DEPOIS DE RODAR A MAO, confira o resultado (sem internet):
    python teste/conferir_dados_aneel.py
Ele compara com as copias .bak e reprova se o valor de alguma distribuidora
mudou SEM uma vigencia nova.

TAREFA AUTOMATICA (fase 2, item 2.8 C, 02/10/2026): depois que o repositorio
for publicado, o arquivo .github/workflows/atualizar-fio-b.yml faz o GitHub
rodar este programa sozinho duas vezes por semana, conferir e gravar a versao
nova. Para isso o programa so regrava um arquivo quando o CONTEUDO mudou
(sem isso, a data "gerado_em" do mapa geraria uma versao nova toda semana).

PRECISA DA BIBLIOTECA pyarrow, para ler os arquivos .parquet da ANEEL:
    pip install pyarrow
O programa avisa com esse comando se ela faltar, e nao grava nada.

=======================================================================
POR QUE ARQUIVOS .parquet, E NAO A API DE CONSULTA (versao 2, 01/10/2026)
=======================================================================
A primeira versao deste programa consultava a API (datastore_search) pagina a
pagina. Rodada no PC da aluna em 01/10/2026, deu dois problemas, e os dois
estao resolvidos nesta versao:

 1. A API DEVOLVEU DADO INCOMPLETO. O arquivo de tarifas de 2025 voltou com
    1 linha (de 2.993.205). Pela API, 9 capitais simplesmente nao existiriam -
    DF, GO, RS, PI, PA, AC, RO, AP e CE. Os arquivos .parquet do MESMO
    conjunto vem completos.
 2. A CONEXAO CAIU NO MEIO. Foram mais de 150 requisicoes seguidas, e o
    servidor da ANEEL derrubou uma delas ("SSL: UNEXPECTED_EOF_WHILE_READING").
    Agora sao 4 downloads de arquivo, com RETOMADA: se a conexao cair, a
    proxima tentativa continua de onde parou, em vez de recomecar.

Os arquivos ficam guardados em cache_aneel/ e sao reaproveitados enquanto
estiverem do mesmo tamanho no servidor; apagar essa pasta nao estraga nada,
so faz o proximo download ser inteiro de novo.

=======================================================================
AS FONTES (todas do Portal de Dados Abertos da ANEEL)
=======================================================================
 (a) "Componentes Tarifarias" -> o valor do Fio B. Filtro: componente
     TUSD_FioB, subgrupo B1, modalidade Convencional, subclasse Residencial,
     base "Tarifa de Aplicacao", detalhe SCEE. Valores SEM impostos, em
     R$/MWh (aqui divididos por 1.000). Os dois ultimos anos sao lidos,
     porque a tarifa vigente hoje pode ter sido homologada no ano passado.
 (b) "IndQual Municipio" -> liga o codigo IBGE do municipio ao "conjunto de
     unidades consumidoras" da ANEEL.
 (c) "Indicadores Coletivos de Continuidade (DEC e FEC)" -> liga cada
     conjunto a distribuidora que o atende, com CNPJ.
 O encontro de (a) com (c) e feito por CNPJ, numero contra numero - nao por
 nome escrito, que varia de um conjunto para outro.

 LICENCA: os TRES conjuntos, (a), (b) e (c), sao publicados sob a Open Data
 Commons Open Database License (ODbL) 1.0, a mesma do OpenStreetMap
 (conferido no portal em 02/10/2026). Os dois arquivos que este programa
 grava sao "bases derivadas" e continuam sob a ODbL; a tela leva o credito a
 ANEEL com a licenca. Detalhes em dados-ANEEL-LICENCA.txt.

=======================================================================
AS TRAVAS (o motivo de cada uma esta datado)
=======================================================================
 1. CAPITAIS COMPLETAS: o arquivo do Fio B so e gravado se vier valor vigente
    para as 27 capitais. Ver o problema 1 acima: sem esta trava, a tabela boa
    seria substituida por uma com 9 buracos.
 2. COBERTURA DOS MUNICIPIOS: o mapa so e gravado se cobrir pelo menos 95%
    dos municipios do pais.
 3. VARIACAO BRUSCA: se o Fio B de alguma distribuidora mudar mais de 50% de
    uma vez, o programa PARA e mostra o caso. Reajuste anual dessa ordem nao
    existe; se acontecer, e erro de dado ou mudanca de criterio, e quem decide
    e uma pessoa.
 4. Nada e gravado por cima sem copia: o arquivo anterior vira .bak.
"""

import argparse
import csv
import io
import json
import os
import time
from datetime import date

try:
    import requests
except ImportError:
    print("Este programa precisa da biblioteca 'requests', a mesma que a "
          "plataforma ja usa. Instale com:\n    pip install requests")
    raise SystemExit(1)


PASTA = os.path.dirname(os.path.abspath(__file__))
API = "https://dadosabertos.aneel.gov.br/api/3/action"
PASTA_CACHE = os.path.join(PASTA, "cache_aneel")

TENTATIVAS = 4
ESPERAS_S = [3, 10, 30]
TEMPO_LIMITE_S = 120

# Identificacao da aplicacao, como pedem as boas praticas de uso de API
# publica. Igual ao User-Agent do geocoding.py: nome definitivo desde
# 03/10/2026 (fase 2, item 2.1); a forma de contato definitiva entra no fim
# da fase 2 (item 2.6).
CABECALHO = {"User-Agent": "quantos-paineis/1.1 "
                           "(+https://github.com/gandalfa1/dimensionamento-fotovoltaico)"}

ARQUIVO_FIO_B = os.path.join(PASTA, "fio_b_por_distribuidora.csv")
ARQUIVO_MAPA = os.path.join(PASTA, "static", "distribuidoras_por_municipio.json")
ARQUIVO_MUNICIPIOS = os.path.join(PASTA, "static", "municipios.json")

CONJUNTO_TARIFAS = "componentes-tarifarias"
CONJUNTO_MUNICIPIOS = "indqual-municipio"
CONJUNTO_CONTINUIDADE = "indicadores-coletivos-de-continuidade-dec-e-fec"

FILTRO_FIO_B = {
    "DscComponenteTarifario": "TUSD_FioB",
    "DscSubGrupoTarifario": "B1",
    "DscModalidadeTarifaria": "Convencional",
    "DscSubClasseConsumidor": "Residencial",
    "DscBaseTarifaria": "Tarifa de Aplicação",
    "DscDetalheConsumidor": "SCEE",
}
COLUNAS_FIO_B = ["SigNomeAgente", "NumCPFCNPJ", "VlrComponenteTarifario",
                 "DatInicioVigencia", "DatFimVigencia", "DscResolucaoHomologatoria",
                 "DscComponenteTarifario", "DscSubGrupoTarifario",
                 "DscModalidadeTarifaria", "DscSubClasseConsumidor",
                 "DscBaseTarifaria", "DscDetalheConsumidor"]
COLUNAS_CONTINUIDADE = ["IdeConjUndConsumidoras", "NumCNPJ", "SigAgente"]

# Sobras da revisao geral (08/10/2026): a ANEEL publica alguns agentes com a sigla em branco
# ("Nao Informado"), e o seletor de distribuidora mostrava isso como se fosse uma opcao. Nome tirado do
# proprio conjunto de dados da ANEEL: no Indicadores Coletivos de Continuidade, o conjunto de unidades
# consumidoras desse CNPJ se chama "CRERAL" (DscConjUndConsumidoras), cooperativa da regiao de Erechim (RS),
# 39 municipios. Se aparecer OUTRO agente sem nome, o programa avisa (e grava o nome como veio).
NOMES_QUE_A_ANEEL_NAO_INFORMA = {"89435598000155": "CRERAL"}


def _nome_da_distribuidora(sigla, cnpj):
    nome = str(sigla or "").strip()
    if nome.lower() in ("", "não informado", "nao informado"):
        if cnpj in NOMES_QUE_A_ANEEL_NAO_INFORMA:
            return NOMES_QUE_A_ANEEL_NAO_INFORMA[cnpj]
        print(f"    (aviso: a ANEEL nao informa o nome da distribuidora de CNPJ {cnpj}; "
              f"ela vai aparecer como \"{nome or 'sem nome'}\" no seletor - ver NOMES_QUE_A_ANEEL_NAO_INFORMA)")
    return nome

UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO"]

VARIACAO_MAXIMA_ACEITAVEL = 0.50      # trava 3
COBERTURA_MINIMA_MUNICIPIOS = 0.95    # trava 2


# ---------------------------------------------------------------------
# Download com retomada
# ---------------------------------------------------------------------
def _tentar(funcao, descricao):
    """Repete uma operacao de rede ate TENTATIVAS vezes, com espera crescente."""
    for numero in range(TENTATIVAS):
        try:
            return funcao()
        except requests.RequestException as falha:
            if numero == TENTATIVAS - 1:
                raise
            espera = ESPERAS_S[min(numero, len(ESPERAS_S) - 1)]
            print(f"    {descricao}: {type(falha).__name__} - tentando de novo "
                  f"em {espera}s ({numero + 2}ª tentativa de {TENTATIVAS})")
            time.sleep(espera)


def baixar_arquivo(url, nome):
    """
    Baixa um arquivo para cache_aneel/, continuando de onde parou se a
    conexao cair. Se o arquivo ja estiver completo, nao baixa de novo.
    """
    os.makedirs(PASTA_CACHE, exist_ok=True)
    destino = os.path.join(PASTA_CACHE, nome)
    parcial = destino + ".parte"

    cabeca = _tentar(lambda: requests.head(url, headers=CABECALHO,
                                           timeout=TEMPO_LIMITE_S, allow_redirects=True),
                     f"tamanho de {nome}")
    tamanho = int(cabeca.headers.get("content-length") or 0)

    if os.path.exists(destino) and tamanho and os.path.getsize(destino) == tamanho:
        print(f"    {nome}: ja estava baixado ({tamanho/1048576:.1f} MB)")
        return destino

    while True:
        ja_tem = os.path.getsize(parcial) if os.path.exists(parcial) else 0
        if tamanho and ja_tem >= tamanho:
            break
        cabecalhos = dict(CABECALHO)
        if ja_tem:
            cabecalhos["Range"] = f"bytes={ja_tem}-"
            print(f"    {nome}: continuando de {ja_tem/1048576:.1f} MB")

        def pedaco():
            resposta = requests.get(url, headers=cabecalhos, stream=True,
                                    timeout=TEMPO_LIMITE_S)
            resposta.raise_for_status()
            modo = "ab" if ja_tem and resposta.status_code == 206 else "wb"
            with open(parcial, modo) as arquivo:
                for bloco in resposta.iter_content(chunk_size=1024 * 256):
                    arquivo.write(bloco)
                    if tamanho:
                        feito = os.path.getsize(parcial)
                        print(f"    {nome}: {feito/1048576:5.1f} de "
                              f"{tamanho/1048576:.1f} MB", end="\r", flush=True)
            return True

        try:
            _tentar(pedaco, nome)
        except requests.RequestException:
            raise
        if not tamanho:
            break
    print(f"    {nome}: {os.path.getsize(parcial)/1048576:5.1f} MB  pronto   ")
    os.replace(parcial, destino)
    return destino


def _pegar_json(url, **parametros):
    def consulta():
        resposta = requests.get(url, params=parametros, headers=CABECALHO,
                                timeout=TEMPO_LIMITE_S)
        resposta.raise_for_status()
        return resposta.json()
    dados = _tentar(consulta, "consulta ao catalogo")
    if not dados.get("success"):
        raise RuntimeError(f"a ANEEL recusou a consulta: {dados.get('error')}")
    return dados["result"]


def recursos_do_conjunto(nome):
    return _pegar_json(f"{API}/package_show", id=nome)["resources"]


def ler_texto(caminho):
    """
    Le um arquivo de texto da ANEEL sem saber de antemao como ele foi escrito.

    O CSV do IndQual Municipio vem em WINDOWS-1252 (conferido em 01/10/2026:
    "São Gonçalo dos Campos" so sai certo nessa tabela), enquanto outros
    arquivos do mesmo portal vem em UTF-8. Abrir com o errado nao da um texto
    torto: da erro na hora, e foi o que aconteceu na primeira rodada da versao
    2 no PC da aluna (UnicodeDecodeError). Por isso aqui se tenta uma lista, na
    ordem, e vale a primeira que ler o arquivo inteiro sem erro. A ultima,
    latin-1, aceita qualquer byte e existe so para o programa nunca parar por
    causa disso.
    """
    with open(caminho, "rb") as arquivo:
        dados = arquivo.read()
    for codificacao in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = dados.decode(codificacao)
            if codificacao != "utf-8-sig":
                print(f"    (arquivo lido como {codificacao})")
            return texto
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"nao consegui ler {os.path.basename(caminho)}")


def ler_parquet(caminho, colunas):
    """Le um .parquet e devolve uma lista de dicionarios, so com as colunas
    pedidas. Usa pyarrow, que nao vem com o Python - ver o cabecalho."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("\nEste programa precisa da biblioteca 'pyarrow' para ler os "
              "arquivos da ANEEL. Instale com:\n    pip install pyarrow\n"
              "Nada foi gravado.")
        raise SystemExit(1)
    tabela = pq.read_table(caminho, columns=colunas)
    return tabela.to_pylist()


# ---------------------------------------------------------------------
# (a) O Fio B de cada distribuidora
# ---------------------------------------------------------------------
def _cnpj(valor):
    """O CNPJ vem ora texto, ora numero; aqui vira sempre texto de 14 digitos."""
    return str(valor).strip().replace(".", "").replace("/", "").replace("-", "").zfill(14)


def _data(valor):
    """A data vem "2026-06-24" ou como data mesmo; fica so a parte do dia."""
    return str(valor)[:10]


def _numero(valor):
    return float(str(valor).replace(",", "."))


def buscar_fio_b(hoje):
    """
    Devolve {cnpj: {...}} com o Fio B vigente hoje de cada distribuidora.

    Quando a mesma distribuidora tem mais de uma tarifa vigente (acontece: em
    01/10/2026 Rondonia tinha duas, de resolucoes diferentes), fica a de
    INICIO DE VIGENCIA MAIS RECENTE.
    """
    print("  Fio B (Componentes Tarifarias)...")
    recursos = [r for r in recursos_do_conjunto(CONJUNTO_TARIFAS)
                if r.get("format", "").upper() == "PARQUET"]
    recursos = sorted(recursos, key=lambda r: r["name"])[-2:]
    if len(recursos) < 2:
        raise RuntimeError("nao achei os arquivos .parquet das componentes "
                           "tarifarias no portal da ANEEL")

    vigentes = {}
    for recurso in recursos:
        caminho = baixar_arquivo(recurso["url"], recurso["name"])
        for reg in ler_parquet(caminho, COLUNAS_FIO_B):
            if any(str(reg.get(campo)) != valor for campo, valor in FILTRO_FIO_B.items()):
                continue
            inicio, fim = _data(reg["DatInicioVigencia"]), _data(reg["DatFimVigencia"])
            if not (inicio <= hoje <= fim):
                continue
            chave = _cnpj(reg["NumCPFCNPJ"])
            novo = {
                "distribuidora": _nome_da_distribuidora(reg["SigNomeAgente"], chave),
                "cnpj": chave,
                "fio_b": _numero(reg["VlrComponenteTarifario"]) / 1000.0,
                "inicio_vigencia": inicio,
                "fim_vigencia": fim,
                "resolucao": str(reg.get("DscResolucaoHomologatoria") or "").strip(),
            }
            if chave not in vigentes or novo["inicio_vigencia"] > vigentes[chave]["inicio_vigencia"]:
                vigentes[chave] = novo
    return vigentes


# ---------------------------------------------------------------------
# (b) e (c) O mapa municipio -> distribuidoras
# ---------------------------------------------------------------------
def buscar_mapa_municipios():
    """
    Devolve {codigo_ibge: [cnpj, ...]} - quem atende cada municipio.

    Caminho: municipio -> conjunto de unidades consumidoras -> distribuidora.
    O arquivo de indicadores usado e o do periodo mais recente (2020-2029):
    conjunto antigo pode ter mudado de dono, e o que interessa e quem atende
    hoje.
    """
    print("  Municipios (IndQual Municipio)...")
    recurso = [r for r in recursos_do_conjunto(CONJUNTO_MUNICIPIOS)
               if r.get("format", "").upper() == "CSV"][0]
    caminho = baixar_arquivo(recurso["url"], "indqual-municipio.csv")
    texto = ler_texto(caminho)
    amostra = texto[:4096]
    separador = ";" if amostra.count(";") > amostra.count(",") else ","
    linhas_municipio = list(csv.DictReader(io.StringIO(texto), delimiter=separador))
    print(f"    {len(linhas_municipio)} linhas de municipio")

    print("  Distribuidora de cada conjunto (DEC e FEC)...")
    recursos = [r for r in recursos_do_conjunto(CONJUNTO_CONTINUIDADE)
                if r.get("format", "").upper() == "PARQUET"
                and "compensacao" not in r["name"]]
    if not recursos:
        raise RuntimeError("nao achei o .parquet dos indicadores de continuidade")
    recurso = sorted(recursos, key=lambda r: r["name"])[-1]
    caminho = baixar_arquivo(recurso["url"], recurso["name"])

    conjunto_para_cnpj = {}
    for reg in ler_parquet(caminho, COLUNAS_CONTINUIDADE):
        conjunto_para_cnpj.setdefault(str(reg["IdeConjUndConsumidoras"]),
                                      _cnpj(reg["NumCNPJ"]))
    print(f"    {len(conjunto_para_cnpj)} conjuntos de unidades consumidoras")

    mapa = {}
    for linha in linhas_municipio:
        ibge = str(linha["CodMunicipio"]).strip()
        cnpj = conjunto_para_cnpj.get(str(linha["IdeConjUnidConsumidoras"]).strip())
        if not cnpj:
            continue
        mapa.setdefault(ibge, [])
        if cnpj not in mapa[ibge]:
            mapa[ibge].append(cnpj)
    return mapa


# ---------------------------------------------------------------------
# Quem atende cada capital
# ---------------------------------------------------------------------
def _ler_municipios():
    """A lista local dos 5.571 municipios (static/municipios.json, do IBGE)."""
    if not os.path.exists(ARQUIVO_MUNICIPIOS):
        return []
    with open(ARQUIVO_MUNICIPIOS, encoding="utf-8") as f:
        return json.load(f)


def _sem_acento(texto):
    import unicodedata
    sem = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in sem if not unicodedata.combining(c)).strip().upper()


def _distribuidora_de_cada_capital(mapa, fio_b):
    """
    Devolve {uf: cnpj} - a distribuidora com Fio B vigente que atende a
    capital de cada estado, ou None quando nao houver.

    O NOME de cada capital vem do proprio motor (FIO_B_POR_UF, no calculo.py),
    onde ja esta documentado com fonte; o codigo IBGE vem da lista local de
    municipios. Assim nenhum codigo precisa ser digitado aqui, e a trava 1
    confere exatamente os 27 estados que a tabela de plano B conhece.
    """
    try:
        from calculo import FIO_B_POR_UF
    except ImportError:
        print("    (aviso: nao consegui ler o calculo.py para saber as capitais; "
              "a trava das 27 capitais nao vai rodar)")
        return {}
    por_nome_uf = {}
    for m in _ler_municipios():
        por_nome_uf[(_sem_acento(m["nome"]), m["uf"])] = str(m["ibge"])
    capitais = {}
    for uf, dados in FIO_B_POR_UF.items():
        ibge = por_nome_uf.get((_sem_acento(dados["capital"]), uf))
        atendentes = mapa.get(ibge, []) if ibge else []
        com_tarifa = [c for c in atendentes if c in fio_b]
        capitais[uf] = com_tarifa[0] if com_tarifa else None
    return capitais


# ---------------------------------------------------------------------
# As travas
# ---------------------------------------------------------------------
def ler_fio_b_anterior():
    """Le o arquivo gravado da ultima vez, para comparar. Sem ele, devolve {}."""
    if not os.path.exists(ARQUIVO_FIO_B):
        return {}
    anterior = {}
    with open(ARQUIVO_FIO_B, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            anterior[linha["cnpj"]] = _numero(linha["fio_b_reais_por_kwh"])
    return anterior


def conferir(fio_b, mapa, municipios_conhecidos, capitais):
    """Roda as travas. Devolve a lista de problemas (vazia = pode gravar)."""
    problemas = []

    faltando = [uf for uf in UFS if not capitais.get(uf)]
    if faltando:
        problemas.append(
            "TRAVA 1 - faltou o Fio B vigente da distribuidora da capital de: "
            + ", ".join(faltando)
            + ". Ja aconteceu por falha da propria ANEEL (01/10/2026); tente de "
              "novo mais tarde antes de suspeitar do programa.")

    if municipios_conhecidos:
        cobertos = sum(1 for m in municipios_conhecidos if m in mapa)
        fracao = cobertos / len(municipios_conhecidos)
        if fracao < COBERTURA_MINIMA_MUNICIPIOS:
            problemas.append(
                f"TRAVA 2 - o mapa cobriu so {cobertos} dos "
                f"{len(municipios_conhecidos)} municipios ({fracao*100:.1f}%), "
                f"menos que os {COBERTURA_MINIMA_MUNICIPIOS*100:.0f}% exigidos.")

    anterior = ler_fio_b_anterior()
    bruscas = []
    for cnpj, dados in fio_b.items():
        velho = anterior.get(cnpj)
        if velho and velho > 0:
            variacao = (dados["fio_b"] - velho) / velho
            if abs(variacao) > VARIACAO_MAXIMA_ACEITAVEL:
                bruscas.append(f"{dados['distribuidora']} ({cnpj}): "
                               f"R$ {velho:.6f} -> R$ {dados['fio_b']:.6f} "
                               f"({variacao*100:+.0f}%)")
    if bruscas:
        problemas.append("TRAVA 3 - variacao grande demais em:\n      "
                         + "\n      ".join(bruscas)
                         + "\n    Reajuste anual dessa ordem nao existe. Confira no "
                           "portal da ANEEL antes de aceitar.")
    return problemas


# ---------------------------------------------------------------------
# Gravacao
# ---------------------------------------------------------------------
def _guardar_copia(caminho):
    if os.path.exists(caminho):
        with open(caminho, "rb") as origem, open(caminho + ".bak", "wb") as destino:
            destino.write(origem.read())


def texto_fio_b(fio_b):
    """O conteudo exato do fio_b_por_distribuidora.csv, sem gravar nada.

    Separado do gravar_fio_b() em 02/10/2026 (fase 2, item 2.8 C) para o
    main() poder comparar com o arquivo que ja existe e NAO regravar quando
    nada mudou. O texto produzido e o mesmo de antes, byte a byte.
    """
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
    escritor.writerow(["distribuidora", "cnpj", "fio_b_reais_por_kwh",
                       "inicio_vigencia", "fim_vigencia", "resolucao_homologatoria"])
    for dados in sorted(fio_b.values(), key=lambda d: d["distribuidora"]):
        escritor.writerow([dados["distribuidora"], dados["cnpj"],
                           repr(dados["fio_b"]).replace(".", ","),
                           dados["inicio_vigencia"], dados["fim_vigencia"],
                           dados["resolucao"].replace(";", ",")])
    return "\ufeff" + saida.getvalue()


def gravar_fio_b(fio_b):
    _guardar_copia(ARQUIVO_FIO_B)
    with open(ARQUIVO_FIO_B, "w", encoding="utf-8", newline="") as f:
        f.write(texto_fio_b(fio_b))


def fio_b_igual_ao_gravado(fio_b):
    """True quando o arquivo ja existente tem exatamente o conteudo novo."""
    if not os.path.exists(ARQUIVO_FIO_B):
        return False
    with open(ARQUIVO_FIO_B, encoding="utf-8", newline="") as f:
        return f.read() == texto_fio_b(fio_b)


def mapa_igual_ao_gravado(mapa, nomes):
    """
    True quando o JSON ja existente tem o mesmo mapa e os mesmos nomes.

    O campo "gerado_em" fica de fora da comparacao de proposito: ele muda
    todo dia, e regravar so por causa dele faria a tarefa automatica criar
    uma versao nova (e o site reiniciar) toda semana sem nenhum dado novo.
    """
    if not os.path.exists(ARQUIVO_MAPA):
        return False
    try:
        with open(ARQUIVO_MAPA, encoding="utf-8") as f:
            atual = json.load(f)
    except (OSError, ValueError):
        return False
    novo = json.loads(json.dumps({"nomes": nomes, "municipios": mapa}))
    return (atual.get("nomes") == novo["nomes"]
            and atual.get("municipios") == novo["municipios"])


def gravar_mapa(mapa, nomes):
    _guardar_copia(ARQUIVO_MAPA)
    conteudo = {
        "gerado_em": date.today().isoformat(),
        "fonte": ("ANEEL, Dados Abertos: IndQual Municipio e Indicadores "
                  "Coletivos de Continuidade (DEC e FEC), licenca ODbL"),
        "nomes": nomes,
        "municipios": mapa,
    }
    with open(ARQUIVO_MAPA, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------
def main():
    analisador = argparse.ArgumentParser(
        description="Atualiza os dados da ANEEL que a plataforma usa.")
    analisador.add_argument("--conferir", action="store_true",
                            help="so confere e mostra o que mudaria, sem gravar nada")
    argumentos = analisador.parse_args()

    hoje = date.today().isoformat()
    print(f"Atualizacao dos dados da ANEEL - {hoje}")
    print("=" * 70)

    fio_b = buscar_fio_b(hoje)
    print(f"  -> {len(fio_b)} distribuidoras com Fio B vigente hoje\n")

    mapa = buscar_mapa_municipios()
    print(f"  -> {len(mapa)} municipios mapeados\n")

    municipios_conhecidos = [str(m["ibge"]) for m in _ler_municipios()]
    capitais = _distribuidora_de_cada_capital(mapa, fio_b)
    problemas = conferir(fio_b, mapa, municipios_conhecidos, capitais)

    print("=" * 70)
    if problemas:
        print("NADA FOI GRAVADO. Problemas encontrados:\n")
        for p in problemas:
            print("  * " + p + "\n")
        print("Os arquivos que ja estavam na pasta continuam como estavam.")
        raise SystemExit(2)

    anterior = ler_fio_b_anterior()
    mudaram = [d for c, d in fio_b.items()
               if c in anterior and abs(d["fio_b"] - anterior[c]) > 5e-7]
    novas = [d for c, d in fio_b.items() if c not in anterior]
    sumiram = [c for c in anterior if c not in fio_b]

    print("CONFERENCIA OK (as 3 travas passaram).")
    print(f"  Fio B: {len(mudaram)} distribuidoras com valor diferente, "
          f"{len(novas)} novas, {len(sumiram)} sem tarifa vigente agora.")
    for d in sorted(mudaram, key=lambda x: x["distribuidora"])[:20]:
        print(f"    {d['distribuidora']:22s} R$ {anterior[d['cnpj']]:.6f} -> "
              f"R$ {d['fio_b']:.6f}  (ate {d['fim_vigencia']})")
    com_varias = sum(1 for v in mapa.values() if len([c for c in v if c in fio_b]) > 1)
    print(f"  Mapa: {len(mapa)} municipios; {com_varias} com mais de uma "
          f"distribuidora com tarifa vigente.")

    if argumentos.conferir:
        print("\n--conferir: nada foi gravado.")
        return

    nomes = {c: d["distribuidora"] for c, d in fio_b.items()}
    # 02/10/2026 (fase 2, item 2.8 C): cada arquivo so e regravado se o
    # CONTEUDO mudou. Sem isto, a tarefa automatica semanal gravaria uma
    # versao nova toda vez (a data "gerado_em" do mapa muda todo dia).
    fio_b_igual = fio_b_igual_ao_gravado(fio_b)
    mapa_igual = mapa_igual_ao_gravado(mapa, nomes)
    if fio_b_igual and mapa_igual:
        print("\nNada mudou desde a ultima atualizacao: os dois arquivos "
              "ficaram como estavam.")
        return
    gravados = []
    if not fio_b_igual:
        gravar_fio_b(fio_b)
        gravados.append(ARQUIVO_FIO_B)
    if not mapa_igual:
        gravar_mapa(mapa, nomes)
        gravados.append(ARQUIVO_MAPA)
    print("\nGravado:\n  " + "\n  ".join(gravados))
    print("(a versao anterior de cada um ficou com a terminacao .bak)")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as falha:
        print(f"\nNao foi possivel falar com a ANEEL depois de {TENTATIVAS} "
              f"tentativas: {falha}")
        print("Nada foi gravado. O que ja baixou ficou em cache_aneel/ e a "
              "proxima rodada continua de onde parou.")
        raise SystemExit(1)
