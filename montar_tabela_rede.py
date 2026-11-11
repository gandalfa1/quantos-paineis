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
montar_tabela_rede.py - fase 4, rede por cidade (11/11/2026): TABELA DA REDE
TRIFASICA DOS MUNICIPIOS (127/220 V ou 220/380 V)

PARA QUE SERVE: acima de 10 kW o inversor e trifasico, e ha dois tipos de rede
trifasica no Brasil. O site mostra um modelo para cada uma; esta tabela diz
qual e a rede mais comum em cada municipio, para o site mostrar esse modelo
primeiro. Ela NAO muda numero de paineis, custo nem retorno.

DE ONDE VEM: da Base de Dados Geografica da Distribuidora (BDGD) que a ANEEL
publica para cada distribuidora (dados de 31 de dezembro de cada ano). Para
cada unidade consumidora de baixa tensao, a BDGD diz o municipio e o
transformador que a atende; para cada transformador, a tensao de linha do
secundario (220 V na rede 127/220; 380 V na rede 220/380). A leitura dos
arquivos da ANEEL (um por distribuidora, de ate ~1,5 GB) e feita pela tarefa
do GitHub; ela entrega, por distribuidora, uma tabela compacta com as
contagens (mun;ten;fs3;res;nfas;multi;pos;ativo;n - ver
teste/rede_bdgd_teste.py), e este script aplica a regra.

A REGRA (aprovada pela aluna em 11/11/2026):
 1. Contam as unidades RESIDENCIAIS (subclasse que comeca com "RE"), de
    qualquer numero de fases, ativas ou nao, ligadas a transformador com
    secundario TRIFASICO que atende 2 ou mais unidades (rede da rua, nao um
    transformador particular). A rede de uma casa e a do transformador dela,
    mesmo que a casa seja monofasica. Nao se filtra unidade ativa porque uma
    distribuidora (Equatorial GO, BDGD 2025) marcou 99,6% das unidades como
    desativadas, e a rede da rua existe do mesmo jeito.
 2. Tensao de linha 220 V -> rede 127/220. Algumas distribuidoras anotam a
    tensao de fase (127 V) num transformador trifasico: tambem 127/220.
    380 V -> rede 220/380. As outras (120/240 em triangulo, 120/208, 125/216,
    230/400, monofasicas a 3 fios) ficam fora da conta.
 3. Somam-se todas as distribuidoras do municipio.
 4. Uma rede so quando pelo menos 95% das casas contadas estao nela e ha pelo
    menos 30 casas na conta; senao, "as duas" (o site mostra os dois modelos,
    como sempre fez). Os dois numeros sao conservadores: o erro possivel e
    mostrar dois modelos quando bastava um.
 5. Onde a distribuidora publica a lista da rede de cada municipio (por
    enquanto a Neoenergia Coelba, Bahia) e a lista DISCORDA da BDGD, o
    municipio fica com "as duas".

CONFERENCIAS (qualquer uma reprova e nada e gravado): o numero de
distribuidoras lidas e o do manifesto; nenhuma tabela vazia de forma
inesperada; todas as linhas da lista da Coelba lidas e casadas com um
municipio do IBGE; o total da tabela e o da lista static/municipios.json; a
classificacao de cada municipio e refeita de outro jeito e tem de bater.

USO:
  python montar_tabela_rede.py --tabelas <pasta com <distribuidora>.csv>
         --coelba <pdf da lista da Coelba> [--manifesto <json>]
         [--data-bdgd AAAA-MM-DD] [--saida <pasta>]
Grava rede_municipios.csv e rede_municipios_info.json na pasta de saida
(padrao: a pasta deste arquivo).
"""
import argparse
import csv
import datetime
import glob
import hashlib
import json
import os
import re
import sys
import unicodedata

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_MUNICIPIOS = os.path.join(PASTA, "static", "municipios.json")

LIMIAR = 0.95
MINIMO_CASAS = 30
REDE_DA_TENSAO = {"127": "127/220", "220": "127/220", "380": "220/380"}
CAMPOS_TABELA = ["mun", "ten", "fs3", "res", "nfas", "multi", "pos", "ativo", "n"]

# Lista da Coelba: nomes que nao estao escritos como no IBGE (conferido em
# 11/11/2026). Chave = nome na lista; valor = (nome no IBGE, UF).
NOMES_COELBA = {
    "Muquém de São Francisco": ("Muquém do São Francisco", "BA"),
    "Santa Teresinha": ("Santa Terezinha", "BA"),
    "Delmiro Gouveia": ("Delmiro Gouveia", "AL"),
}
REDE_DA_LISTA = {"220/127": "127/220", "127/220": "127/220",
                 "380/220": "220/380", "220/380": "220/380"}


def reprovar(motivo):
    raise SystemExit("REPROVADO: " + motivo)


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def chave_nome(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def ler_municipios():
    with open(ARQUIVO_MUNICIPIOS, encoding="utf-8") as f:
        lista = json.load(f)
    muns = {}
    for m in lista:
        codigo = str(m["ibge"])
        if codigo in muns:
            reprovar(f"codigo repetido em static/municipios.json: {codigo}")
        muns[codigo] = {"municipio": m["nome"], "uf": m["uf"]}
    return muns


def ler_tabelas(pasta, muns):
    """Soma, por municipio, as casas contadas em cada rede (regra, itens 1-3)."""
    arquivos = sorted(glob.glob(os.path.join(pasta, "*.csv")))
    if not arquivos:
        reprovar(f"nenhuma tabela em {pasta}")
    casas = {}          # codigo -> {"127/220": n, "220/380": n}
    por_dist = {}
    fora_da_lista = 0
    for arq in arquivos:
        rotulo = os.path.basename(arq)[:-4]
        with open(arq, encoding="utf-8") as f:
            leitor = csv.reader(f, delimiter=";")
            cab = next(leitor, None)
            if cab != CAMPOS_TABELA:
                reprovar(f"cabecalho inesperado em {rotulo}: {cab}")
            linhas = contadas = 0
            for campos in leitor:
                if not campos:
                    continue
                if len(campos) != len(CAMPOS_TABELA):
                    reprovar(f"linha malformada em {rotulo}: {campos}")
                mun, ten, fs3, res, nfas, multi, pos, ativo, n = campos
                linhas += 1
                rede = REDE_DA_TENSAO.get(ten)
                if rede is None or fs3 != "1" or res != "1" or multi != "1":
                    continue
                n = int(n)
                if mun not in muns:
                    fora_da_lista += n
                    continue
                casas.setdefault(mun, {"127/220": 0, "220/380": 0})[rede] += n
                contadas += n
        por_dist[rotulo] = {"linhas": linhas, "casas_contadas": contadas}
    return casas, por_dist, fora_da_lista


def ler_lista_coelba(caminho, muns):
    """Le o PDF "MUNICIPIOS X TENSAO" da Neoenergia Coelba -> {codigo: rede}."""
    import pypdf  # so aqui: o site nao precisa desta biblioteca

    texto = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(caminho).pages)
    por_chave = {}
    for codigo, m in muns.items():
        por_chave.setdefault((chave_nome(m["municipio"]), m["uf"]), []).append(codigo)
    lista = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.upper().startswith("MUNICIPIOS"):
            continue
        achado = re.match(r"^(.+?)\s+(\d{3}/\d{3})$", linha)
        if not achado or achado.group(2) not in REDE_DA_LISTA:
            reprovar(f"linha da lista da Coelba nao lida: {linha!r}")
        nome, tensao = achado.group(1).strip(), achado.group(2)
        nome_ibge, uf = NOMES_COELBA.get(nome, (nome, "BA"))
        codigos = por_chave.get((chave_nome(nome_ibge), uf), [])
        if len(codigos) != 1:
            reprovar(f"municipio da lista da Coelba sem par unico no IBGE: {nome!r}")
        if codigos[0] in lista:
            reprovar(f"municipio repetido na lista da Coelba: {nome!r}")
        lista[codigos[0]] = REDE_DA_LISTA[tensao]
    if len(lista) < 400:
        reprovar(f"lista da Coelba com so {len(lista)} municipios (esperado ~418)")
    return lista


def classificar(c127, c380):
    total = c127 + c380
    if total == 0:
        return "as duas", "sem_dado"
    if total < MINIMO_CASAS:
        return "as duas", "poucas_casas"
    if c127 >= LIMIAR * total:
        return "127/220", "bdgd"
    if c380 >= LIMIAR * total:
        return "220/380", "bdgd"
    return "as duas", "bdgd_mista"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tabelas", required=True)
    ap.add_argument("--coelba", required=True)
    ap.add_argument("--manifesto")
    ap.add_argument("--data-bdgd", default="2025-12-31")
    ap.add_argument("--saida", default=PASTA)
    args = ap.parse_args()

    muns = ler_municipios()
    casas, por_dist, fora = ler_tabelas(args.tabelas, muns)

    manifesto = None
    if args.manifesto:
        with open(args.manifesto, encoding="utf-8") as f:
            manifesto = json.load(f)
        esperados = {item["rotulo"] for item in manifesto}
        if esperados != set(por_dist):
            reprovar("distribuidoras lidas diferentes do manifesto: faltam "
                     f"{sorted(esperados - set(por_dist))}, sobram {sorted(set(por_dist) - esperados)}")
    vazias = [d for d, v in por_dist.items() if v["casas_contadas"] == 0]
    # BDGD 2025: so a Coopera (SC) veio sem nenhuma unidade de baixa tensao
    # (seus municipios tem outras distribuidoras). Mais de 3 vazias = algo errado.
    if len(vazias) > 3:
        reprovar(f"distribuidoras sem nenhuma casa contada: {vazias}")

    lista_coelba = ler_lista_coelba(args.coelba, muns)

    linhas = []
    contagem = {"127/220": 0, "220/380": 0, "as duas": 0}
    motivos = {}
    for codigo in sorted(muns, key=int):
        c = casas.get(codigo, {"127/220": 0, "220/380": 0})
        rede, motivo = classificar(c["127/220"], c["220/380"])
        da_lista = lista_coelba.get(codigo)
        if da_lista and rede != "as duas" and rede != da_lista:
            rede, motivo = "as duas", "lista_da_distribuidora_discorda"
        contagem[rede] += 1
        motivos[motivo] = motivos.get(motivo, 0) + 1
        linhas.append({"codigo_ibge": codigo, "municipio": muns[codigo]["municipio"],
                       "uf": muns[codigo]["uf"], "rede": rede,
                       "casas_127_220": c["127/220"], "casas_220_380": c["220/380"],
                       "motivo": motivo})

    # Conferencia: refaz a classificacao por outro caminho (fracao e regra
    # escrita de outra forma) e exige o mesmo resultado em todos.
    for l in linhas:
        a, b = l["casas_127_220"], l["casas_220_380"]
        t = a + b
        esperado = "as duas"
        if t >= MINIMO_CASAS and not (l["codigo_ibge"] in lista_coelba
                                      and lista_coelba[l["codigo_ibge"]] != ("127/220" if a > b else "220/380")):
            if a / t >= LIMIAR:
                esperado = "127/220"
            elif b / t >= LIMIAR:
                esperado = "220/380"
        if esperado != l["rede"]:
            reprovar(f"conferencia da regra falhou em {l['codigo_ibge']}: {l['rede']} x {esperado}")
    if sum(contagem.values()) != len(muns):
        reprovar("total da tabela diferente da lista de municipios")

    os.makedirs(args.saida, exist_ok=True)
    arq_csv = os.path.join(args.saida, "rede_municipios.csv")
    with open(arq_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)

    concordam = sum(1 for cod, r in lista_coelba.items()
                    if classificar(casas.get(cod, {"127/220": 0, "220/380": 0})["127/220"],
                                   casas.get(cod, {"127/220": 0, "220/380": 0})["220/380"])[0] == r)
    info = {
        "o_que_e": "Rede trifasica mais comum em cada municipio (127/220 V ou 220/380 V). "
                   "Nao muda paineis, custo nem retorno: so a ordem dos dois modelos de inversor acima de 10 kW.",
        "fonte": "ANEEL, Base de Dados Geografica da Distribuidora (BDGD), dados de " + args.data_bdgd
                 + "; Neoenergia Coelba, lista MUNICIPIOS X TENSAO.",
        "data_bdgd": args.data_bdgd,
        "regra": {"limiar": LIMIAR, "minimo_casas": MINIMO_CASAS,
                  "conta": "unidades residenciais (CLAS_SUB RE*), qualquer numero de fases, ativas ou nao, "
                           "em transformador com secundario trifasico que atende 2 ou mais unidades",
                  "tensoes": REDE_DA_TENSAO,
                  "lista_da_distribuidora": "se discorda da BDGD, o municipio fica com as duas"},
        "contagem": contagem,
        "motivos": dict(sorted(motivos.items())),
        "distribuidoras_lidas": len(por_dist),
        "distribuidoras_sem_casa_contada": vazias,
        "casas_com_municipio_fora_da_lista": fora,
        "lista_coelba": {"sha256": sha256(args.coelba), "municipios": len(lista_coelba),
                         "concordam_com_a_bdgd": concordam},
        "manifesto": manifesto,
        "csv_sha256": sha256(arq_csv),
        "montada_em": datetime.date.today().isoformat(),
    }
    with open(os.path.join(args.saida, "rede_municipios_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print("contagem:", contagem)
    print("motivos:", info["motivos"])
    print("distribuidoras lidas:", len(por_dist), "| sem casa contada:", vazias,
          "| casas com municipio fora da lista:", fora)
    print("lista da Coelba:", len(lista_coelba), "municipios; concordam com a BDGD:", concordam)


if __name__ == "__main__":
    sys.exit(main())
