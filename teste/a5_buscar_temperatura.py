# Copyright (C) 2026 Brenda Morel Bueno Ferreira
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# FASE 4, A5 - TESTE (ramo fase4-a5-teste-nasa; NAO vai para o main).
# Busca na NASA POWER, para cada quadrado de 1 grau da tabela de sol
# (sol_municipios.csv), a temperatura do ar (T2M, media, maxima e minima),
# o indice de ceu limpo (ALLSKY_KT), a irradiacao no topo da atmosfera
# (TOA_SW_DWN) e o vento a 2 m (WS2M). Pede tambem ALLSKY_SFC_SW_DWN para
# CONFERIR que e o mesmo quadrado e o mesmo periodo da tabela de sol.
# Saida: a5_clima_quadrados.csv, impresso no registro em gzip+base64
# (a nuvem nao baixa artefatos do Actions).
import base64, csv, gzip, io, json, os, sys, time
import requests

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
PARAMS = ["ALLSKY_SFC_SW_DWN", "T2M", "T2M_MAX", "T2M_MIN", "ALLSKY_KT",
          "TOA_SW_DWN", "WS2M"]
MESES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
CAB = {"User-Agent": "quantos-paineis/1.1 (+https://quantospaineis.com.br/contato)"}
_ultima = 0.0


def consultar(lat, lon):
    global _ultima
    for t in range(5):
        espera = 2.0 - (time.monotonic() - _ultima)
        if espera > 0:
            time.sleep(espera)
        try:
            r = requests.get(URL, headers=CAB, timeout=90, params={
                "parameters": ",".join(PARAMS), "community": "RE",
                "latitude": lat, "longitude": lon, "format": "JSON"})
        except requests.RequestException as e:
            print(f"  sem resposta ({type(e).__name__}), tentativa {t + 1}")
            _ultima = time.monotonic(); time.sleep(5 * (t + 1)); continue
        _ultima = time.monotonic()
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  HTTP {r.status_code}, tentativa {t + 1}")
            time.sleep(10 * (t + 1)); continue
        r.raise_for_status()
        d = r.json()
        p = d["properties"]["parameter"]
        fill = (d.get("header") or {}).get("fill_value", -999)
        for nome in PARAMS:
            for m in MESES + ["ANN"]:
                v = p[nome].get(m)
                if not isinstance(v, (int, float)) or v == fill:
                    raise SystemExit(f"REPROVADO: {nome} {m} = {v!r} em {lat},{lon}")
        return p, d.get("header") or {}
    raise SystemExit("REPROVADO: a NASA nao respondeu")


def main():
    tabela = {}
    with open(os.path.join(PASTA, "sol_municipios.csv"), encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            q = (float(linha["nasa_lat"]), float(linha["nasa_lon"]))
            sol = [float(linha[m.lower()]) for m in MESES]
            if q in tabela and tabela[q] != sol:
                raise SystemExit(f"REPROVADO: dois sois no quadrado {q}")
            tabela[q] = sol
    print(f"{len(tabela)} quadrados")
    saida = io.StringIO()
    w = csv.writer(saida, lineterminator="\n")
    w.writerow(["nasa_lat", "nasa_lon", "parametro"] + MESES + ["ANN"])
    cabecalhos, maior_dif_sol, maior_dif_kt = set(), 0.0, 0.0
    for i, (la, lo) in enumerate(sorted(tabela), 1):
        p, cab = consultar(la, lo)
        cabecalhos.add(json.dumps({k: cab.get(k) for k in ("api", "sources", "start", "end")},
                                  sort_keys=True, default=str))
        for k, m in enumerate(MESES):
            maior_dif_sol = max(maior_dif_sol, abs(p["ALLSKY_SFC_SW_DWN"][m] - tabela[(la, lo)][k]))
            kt = p["ALLSKY_SFC_SW_DWN"][m] / p["TOA_SW_DWN"][m]
            maior_dif_kt = max(maior_dif_kt, abs(kt - p["ALLSKY_KT"][m]))
        for nome in PARAMS:
            w.writerow([la, lo, nome] + [p[nome][m] for m in MESES + ["ANN"]])
        if i % 50 == 0:
            print(f"  {i}/{len(tabela)}")
    print("CABECALHOS NASA:", cabecalhos)
    print(f"CONFERENCIA 1 - maior diferenca do sol para a tabela: {maior_dif_sol:.6f} kWh/m2/dia")
    print(f"CONFERENCIA 2 - maior diferenca KT x sol/topo: {maior_dif_kt:.6f}")
    if maior_dif_sol > 0.0001:
        raise SystemExit("REPROVADO: o sol nao bate com a tabela (quadrado ou periodo diferente)")
    texto = saida.getvalue().encode("utf-8")
    import hashlib
    print("sha256 do csv:", hashlib.sha256(texto).hexdigest(), "linhas:", texto.count(b"\n"))
    b64 = base64.b64encode(gzip.compress(texto, mtime=0)).decode()
    print("=====INICIO_A5_CLIMA=====")
    for k in range(0, len(b64), 1000):
        print(b64[k:k + 1000])
    print("=====FIM_A5_CLIMA=====")


if __name__ == "__main__":
    main()
