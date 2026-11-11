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
contar_bdgd_rede.py - fase 4, rede por cidade (11/11/2026): CONTAGEM DE UMA
DISTRIBUIDORA NA BDGD. Usado pela tarefa .github/workflows/renovar-tabela-rede.yml
(uma distribuidora por tarefa); a regra fica em montar_tabela_rede.py.

Le a BDGD de UMA distribuidora (pasta .gdb ja descompactada) e conta, por
municipio (codigo IBGE), as unidades consumidoras de baixa tensao pela tensao
de linha do secundario do transformador que as atende (UNTRMT.TEN_LIN_SE).
Nao mexe no site: so escreve uma tabela compacta (CSV separado por ";") no
arquivo de saida. Mesma contagem do teste de 11/11/2026 (execucao 42952780473).

Cada linha da tabela: mun;ten;fs3;res;nfas;multi;pos;ativo;n
  ten   tensao de linha do secundario em volts (220 = rede 127/220,
        380 = rede 220/380; outras = monofasicas a 3 fios etc.; ? = sem dado)
  fs3   1 se o secundario do transformador tem as 3 fases (A, B e C)
  res   1 se a classe/subclasse da unidade e residencial (CLAS_SUB comeca com RE)
  nfas  numero de fases da ligacao da unidade (0 a 3, por FAS_CON)
  multi 1 se o transformador atende 2 ou mais unidades de baixa tensao
  pos   posse do transformador (UNTRMT.POS, como vem)
  ativo 1 se a unidade esta ativa (SIT_ATIV = AT)

Uso: python contar_bdgd_rede.py <pasta.gdb> <arquivo de saida .csv>
"""
import sys

import pandas as pd
import pyogrio


def achar_camada(camadas, *nomes):
    for nome in nomes:
        for c in camadas:
            if c.upper() == nome.upper():
                return c
    return None


def ler(gdb, camada, colunas):
    campos = list(pyogrio.read_info(gdb, layer=camada)["fields"])
    faltam = [c for c in colunas if c not in campos]
    usar = [c for c in colunas if c in campos]
    df = pyogrio.read_dataframe(gdb, layer=camada, read_geometry=False, columns=usar)
    for c in faltam:
        df[c] = None
    if faltam:
        print(f"AVISO: {camada} sem os campos {faltam}")
    return df


def n_fases(serie):
    s = serie.fillna("").astype(str).str.upper()
    return (s.str.contains("A").astype(int) + s.str.contains("B").astype(int)
            + s.str.contains("C").astype(int))


def volts(serie):
    v = pd.to_numeric(serie, errors="coerce")
    v = v.where(v >= 100, v * 1000)  # kV -> V (BT em 0,22/0,38; MT em 13,8 etc.)
    return v.round().astype("Int64").astype(str).replace("<NA>", "?")


def main():
    gdb, saida = sys.argv[1], sys.argv[2]
    camadas = [c[0] for c in pyogrio.list_layers(gdb)]
    lay_uc = achar_camada(camadas, "UCBT_tab", "UCBT")
    lay_un = achar_camada(camadas, "UNTRMT")
    print("CAMADAS USADAS:", lay_uc, lay_un)

    uc = ler(gdb, lay_uc, ["MUN", "FAS_CON", "UNI_TR_MT", "CLAS_SUB", "SIT_ATIV"])
    un = ler(gdb, lay_un, ["COD_ID", "TEN_LIN_SE", "FAS_CON_S", "POS"])
    print(f"UC lidas: {len(uc)}; transformadores lidos: {len(un)}")
    print("CLAS_SUB:", uc["CLAS_SUB"].astype(str).value_counts().head(25).to_dict())
    print("SIT_ATIV:", uc["SIT_ATIV"].astype(str).value_counts().to_dict())
    print("POS:", un["POS"].astype(str).value_counts().to_dict())
    print("TEN_LIN_SE (bruto):", un["TEN_LIN_SE"].astype(str).value_counts().head(15).to_dict())

    uc["UNI_TR_MT"] = uc["UNI_TR_MT"].astype(str)
    un["COD_ID"] = un["COD_ID"].astype(str)
    un = un.drop_duplicates("COD_ID")
    por_trafo = uc.groupby("UNI_TR_MT").size().rename("n_uc_trafo")

    un["ten"] = volts(un["TEN_LIN_SE"])
    un["fs3"] = (n_fases(un["FAS_CON_S"]) == 3).astype(int)
    un["pos"] = un["POS"].fillna("?").astype(str)
    df = uc.merge(un[["COD_ID", "ten", "fs3", "pos"]], how="left",
                  left_on="UNI_TR_MT", right_on="COD_ID")
    sem = df["ten"].isna().sum()
    print(f"UC sem transformador achado: {sem} ({100 * sem / max(len(df), 1):.2f}%)")
    df["ten"] = df["ten"].fillna("?")
    df["fs3"] = df["fs3"].fillna(0).astype(int)
    df["pos"] = df["pos"].fillna("?")
    df = df.join(por_trafo, on="UNI_TR_MT")
    df["multi"] = (df["n_uc_trafo"].fillna(0) >= 2).astype(int)
    df["res"] = df["CLAS_SUB"].fillna("").astype(str).str.upper().str.startswith("RE").astype(int)
    df["nfas"] = n_fases(df["FAS_CON"])
    df["ativo"] = (df["SIT_ATIV"].fillna("").astype(str).str.upper() == "AT").astype(int)
    df["mun"] = df["MUN"].fillna("?").astype(str).str.replace(r"\.0$", "", regex=True)

    chave = ["mun", "ten", "fs3", "res", "nfas", "multi", "pos", "ativo"]
    tab = df.groupby(chave, dropna=False).size().reset_index(name="n")
    print("Tensao de linha (V) -> UC:", tab.groupby("ten")["n"].sum().sort_values(ascending=False).head(10).to_dict())
    alvo = tab[(tab.res == 1) & (tab.nfas >= 2) & (tab.fs3 == 1) & (tab.multi == 1) & (tab.ativo == 1)]
    print("Residenciais bi/tri ativas em trafo trifasico com 2+ UC, por tensao:",
          alvo.groupby("ten")["n"].sum().sort_values(ascending=False).head(6).to_dict())
    print(f"Municipios: {tab['mun'].nunique()}; linhas da tabela: {len(tab)}")

    texto = "mun;ten;fs3;res;nfas;multi;pos;ativo;n\n" + "\n".join(
        ";".join(str(x) for x in r) for r in tab[chave + ["n"]].itertuples(index=False)) + "\n"
    with open(saida, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"gravado: {saida} ({len(tab)} linhas)")


if __name__ == "__main__":
    main()
