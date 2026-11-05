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
montar_tabela_sol.py - B1 da fase 4 (05/11/2026): TABELA DE SOL DOS MUNICIPIOS

O QUE FAZ: monta, de uma vez, os 12 valores mensais de irradiacao (HSP) dos
5.571 municipios da lista static/municipios.json, para o site nao precisar
consultar o OpenStreetMap nem a NASA na hora da simulacao.

COMO:
 1. Le a SEDE de cada municipio na Base Cartografica Continua do IBGE
    (BC250, camada lml_cidade_p, coluna geocodigo = codigo IBGE). Citacao
    pedida pelo IBGE: "Fonte: IBGE/DGC. Base Cartografica Continua do Brasil,
    escala 1:250.000 - BC250". As coordenadas do IBGE NAO vao para a tabela
    (duvida da licenca para republicar; decisao da aluna em 05/11/2026): elas
    so servem para escolher o quadrado da NASA.
 2. A irradiacao da NASA POWER (fonte SYN1DEG) vem em quadrados de 1 grau,
    com as bordas nos graus inteiros (conferido em 05/11/2026: o ponto de
    Guaira devolve exatamente o valor do quadrado de centro -24,5 / -54,5).
    Cada sede cai num quadrado; o programa pergunta a NASA uma vez por
    quadrado, no CENTRO dele.
 3. CONFERENCIA DA REGRA DOS QUADRADOS: para uma amostra de sedes (metade perto
    de uma borda), pergunta tambem no ponto exato da sede e exige valores
    IGUAIS aos do quadrado. Qualquer diferenca reprova e nada e entregue.
 4. Grava sol_municipios.csv (codigo, nome, UF, centro do quadrado da NASA,
    12 meses e a media anual da NASA) e sol_municipios_info.json (versao da
    API, periodo, fontes, data, arquivo e sha256 da BC250 usada).

Uso:  python3 montar_tabela_sol.py <arquivo.gpkg da BC250> <pasta de saida>
"""
import csv
import hashlib
import json
import math
import os
import random
import struct
import sqlite3
import sys
import time
from datetime import date

import requests

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_MUNICIPIOS = os.path.join(PASTA, "static", "municipios.json")

URL_NASA = "https://power.larc.nasa.gov/api/temporal/climatology/point"
PARAMETRO = "ALLSKY_SFC_SW_DWN"
MESES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
CABECALHO = {"User-Agent": "quantos-paineis/1.1 "
                           "(+https://quantospaineis.com.br/contato)"}
INTERVALO_S = 2.0          # mesmo intervalo minimo do nasa_power.py
TENTATIVAS = 4
AMOSTRA_PERTO_DA_BORDA = 50
AMOSTRA_LONGE_DA_BORDA = 50
BORDA_GRAUS = 0.05


# ---------------------------------------------------------------------------
# 1. Sedes do IBGE (GeoPackage = SQLite; o ponto vem em WKB depois do
#    cabecalho "GP" e do envelope)
# ---------------------------------------------------------------------------
def ponto_do_geopackage(blob):
    blob = bytes(blob)
    if blob[:2] != b"GP":
        raise ValueError("geometria sem o cabecalho GP")
    flags = blob[3]
    tam_envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 7]
    wkb = blob[8 + tam_envelope:]
    ordem = "<" if wkb[0] == 1 else ">"
    tipo = struct.unpack(ordem + "I", wkb[1:5])[0]
    if tipo % 1000 != 1 and (tipo & 0xFF) != 1:
        raise ValueError(f"geometria nao e ponto (tipo {tipo})")
    x, y = struct.unpack(ordem + "dd", wkb[5:21])
    return y, x            # latitude, longitude


def sedes_do_ibge(arquivo_gpkg, codigos):
    con = sqlite3.connect(arquivo_gpkg)
    srs = con.execute("select s.organization, s.organization_coordsys_id "
                      "from gpkg_contents c join gpkg_spatial_ref_sys s "
                      "on s.srs_id = c.srs_id where c.table_name = 'lml_cidade_p'"
                      ).fetchone()
    if tuple(srs) != ("EPSG", 4674):
        raise SystemExit(f"REPROVADO: sistema de referencia inesperado {srs}")
    sedes = {}
    for cod, geom in con.execute("select geocodigo, geom from lml_cidade_p"):
        if cod is None:
            continue                     # capitais de outros paises
        if cod in sedes:
            raise SystemExit(f"REPROVADO: codigo {cod} repetido na lml_cidade_p")
        sedes[cod] = ponto_do_geopackage(geom)
    faltam = [c for c in codigos if c not in sedes]
    if faltam:
        raise SystemExit(f"REPROVADO: {len(faltam)} municipios sem sede: {faltam[:10]}")
    return {c: sedes[c] for c in codigos}


def quadrado(lat, lon):
    """Centro do quadrado de 1 grau da NASA que contem o ponto."""
    return math.floor(lat) + 0.5, math.floor(lon) + 0.5


def distancia_da_borda(lat, lon):
    return min(lat - math.floor(lat), math.ceil(lat) - lat,
               lon - math.floor(lon), math.ceil(lon) - lon)


# ---------------------------------------------------------------------------
# 2. NASA POWER
# ---------------------------------------------------------------------------
_ultima = 0.0


def consultar_nasa(lat, lon):
    global _ultima
    for tentativa in range(TENTATIVAS):
        espera = INTERVALO_S - (time.monotonic() - _ultima)
        if espera > 0:
            time.sleep(espera)
        try:
            r = requests.get(URL_NASA, headers=CABECALHO, timeout=60, params={
                "parameters": PARAMETRO, "community": "RE",
                "latitude": lat, "longitude": lon, "format": "JSON"})
        except requests.RequestException as erro:
            print(f"  sem resposta ({type(erro).__name__}), tentativa {tentativa + 1}")
            _ultima = time.monotonic()
            time.sleep(5 * (tentativa + 1))
            continue
        _ultima = time.monotonic()
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  HTTP {r.status_code}, tentativa {tentativa + 1}")
            time.sleep(10 * (tentativa + 1))
            continue
        r.raise_for_status()
        dados = r.json()
        valores = dados["properties"]["parameter"][PARAMETRO]
        cab = dados.get("header") or {}
        sem_dado = cab.get("fill_value", -999)
        for m in MESES + ["ANN"]:
            v = valores.get(m)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v == sem_dado or v < 0:
                raise SystemExit(f"REPROVADO: NASA devolveu {m} = {v!r}")
        return {m: valores[m] for m in MESES + ["ANN"]}, cab
    raise SystemExit("REPROVADO: a NASA nao respondeu depois de varias tentativas")


# ---------------------------------------------------------------------------
# 3. Montagem e conferencias
# ---------------------------------------------------------------------------
def principal(arquivo_gpkg, pasta_saida):
    municipios = json.load(open(ARQUIVO_MUNICIPIOS, encoding="utf-8"))
    codigos = [str(m["ibge"]) for m in municipios]
    if len(set(codigos)) != len(codigos):
        raise SystemExit("REPROVADO: codigo repetido em static/municipios.json")
    sedes = sedes_do_ibge(arquivo_gpkg, codigos)
    print(f"{len(sedes)} sedes lidas da BC250")

    quadrados = sorted({quadrado(*p) for p in sedes.values()})
    print(f"{len(quadrados)} quadrados de 1 grau da NASA")

    sol, cabecalhos = {}, []
    for i, (la, lo) in enumerate(quadrados, 1):
        sol[(la, lo)], cab = consultar_nasa(la, lo)
        cabecalhos.append(json.dumps({k: cab.get(k) for k in
                                      ("api", "sources", "range", "start", "end")},
                                     sort_keys=True))
        if i % 50 == 0 or i == len(quadrados):
            print(f"  NASA: {i}/{len(quadrados)} quadrados")
    if len(set(cabecalhos)) != 1:
        raise SystemExit(f"REPROVADO: a NASA mudou a versao/periodo no meio: {set(cabecalhos)}")
    cab_nasa = json.loads(cabecalhos[0])

    # Conferencia da regra dos quadrados no ponto exato das sedes
    random.seed(20261105)
    perto = [c for c in codigos if distancia_da_borda(*sedes[c]) < BORDA_GRAUS]
    longe = [c for c in codigos if distancia_da_borda(*sedes[c]) >= BORDA_GRAUS]
    amostra = (random.sample(perto, min(AMOSTRA_PERTO_DA_BORDA, len(perto)))
               + random.sample(longe, min(AMOSTRA_LONGE_DA_BORDA, len(longe))))
    diferentes = []
    for c in amostra:
        no_ponto, _ = consultar_nasa(*sedes[c])
        if no_ponto != sol[quadrado(*sedes[c])]:
            diferentes.append(c)
    print(f"Conferencia da regra dos quadrados: {len(amostra)} sedes "
          f"({len(perto)} estao perto de uma borda), {len(diferentes)} diferentes")
    if diferentes:
        raise SystemExit(f"REPROVADO: ponto da sede diferente do quadrado em {diferentes}")

    os.makedirs(pasta_saida, exist_ok=True)
    arq_csv = os.path.join(pasta_saida, "sol_municipios.csv")
    with open(arq_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["codigo_ibge", "municipio", "uf", "nasa_lat", "nasa_lon"]
                   + [m.lower() for m in MESES] + ["anual_nasa"])
        for m in municipios:
            q = quadrado(*sedes[str(m["ibge"])])
            v = sol[q]
            w.writerow([m["ibge"], m["nome"], m["uf"], q[0], q[1]]
                       + [v[x] for x in MESES] + [v["ANN"]])

    h = hashlib.sha256()
    with open(arquivo_gpkg, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    info = {
        "data_da_montagem": date.today().isoformat(),
        "municipios": len(municipios),
        "quadrados_nasa": len(quadrados),
        "nasa_power": {"endpoint": URL_NASA, "parametro": PARAMETRO,
                       "comunidade": "RE", **cab_nasa,
                       "licenca": "CC BY 4.0"},
        "sedes": {"fonte": "IBGE/DGC, Base Cartografica Continua do Brasil, "
                           "escala 1:250.000 - BC250, camada lml_cidade_p",
                  "arquivo": os.path.basename(arquivo_gpkg),
                  "sha256_gpkg": h.hexdigest(),
                  "observacao": "coordenadas usadas so para escolher o quadrado; "
                                "nao publicadas"},
        "conferencia_quadrados": {"amostra": len(amostra),
                                  "perto_da_borda_no_pais": len(perto),
                                  "diferentes": 0},
    }
    with open(os.path.join(pasta_saida, "sol_municipios_info.json"), "w",
              encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False, indent=1))
    print("OK")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    principal(sys.argv[1], sys.argv[2])
