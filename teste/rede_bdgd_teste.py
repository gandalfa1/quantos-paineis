"""Teste da BDGD (fase 4, rede por cidade, 10/11/2026) - SO NO RAMO DE TESTE.

Le a BDGD de UMA distribuidora (arquivo .gdb ja descompactado) e conta, por
municipio (codigo IBGE), as unidades consumidoras de baixa tensao pela tensao
SECUNDARIA do transformador que as atende. Nao mexe no site: so escreve um
resumo no registro da tarefa do GitHub (gzip + base64 entre marcadores).

Uso: python teste/rede_bdgd_teste.py <pasta.gdb> <nome curto>
"""
import base64
import collections
import glob
import gzip
import io
import sys

import pyogrio

# Codigos da tabela TTEN da BDGD (em volts) usados na baixa tensao.
TTEN = {"0": 0, "1": 110, "2": 115, "3": 120, "4": 121, "5": 125, "6": 127,
        "7": 208, "8": 216, "9": 216.5, "10": 220, "11": 230, "12": 231,
        "13": 240, "14": 254, "15": 380, "16": 400, "17": 440, "18": 480}


def achar_camada(camadas, nome):
    for c in camadas:
        if c.upper() == nome.upper():
            return c
    return None


def main():
    gdb, nome = sys.argv[1], sys.argv[2]
    camadas = [c[0] for c in pyogrio.list_layers(gdb)]
    print("CAMADAS:", ", ".join(sorted(camadas)))
    for alvo in ("UCBT_tab", "UCBT", "EQTRMT", "UNTRMT", "TTEN"):
        c = achar_camada(camadas, alvo)
        if c:
            info = pyogrio.read_info(gdb, layer=c)
            print(f"CAMPOS {c} ({info['features']} linhas):", ", ".join(info["fields"]))

    lay_uc = achar_camada(camadas, "UCBT_tab") or achar_camada(camadas, "UCBT")
    lay_eq = achar_camada(camadas, "EQTRMT")
    uc = pyogrio.read_dataframe(gdb, layer=lay_uc, read_geometry=False,
                                columns=["MUN", "FAS_CON", "TEN_FORN", "UNI_TR_MT"])
    eq = pyogrio.read_dataframe(gdb, layer=lay_eq, read_geometry=False,
                                columns=["UNI_TR_MT", "TEN_PRI", "TEN_SEC", "FAS_CON_P", "FAS_CON_S"])
    print(f"UC lidas: {len(uc)}; EQTRMT lidos: {len(eq)}")

    # Um transformador (UNTRMT) pode ter mais de um equipamento (banco).
    sec = {}
    conflito = 0
    for u, t in zip(eq["UNI_TR_MT"].astype(str), eq["TEN_SEC"].astype(str)):
        if u in sec and sec[u] != t:
            conflito += 1
        sec.setdefault(u, t)
    print(f"Transformadores distintos: {len(sec)}; com TEN_SEC diferente entre equipamentos: {conflito}")

    cont = collections.Counter()
    sem_trafo = 0
    for mun, fas, tf, tr in zip(uc["MUN"].astype(str), uc["FAS_CON"].astype(str),
                                uc["TEN_FORN"].astype(str), uc["UNI_TR_MT"].astype(str)):
        ts = sec.get(tr)
        if ts is None:
            sem_trafo += 1
            ts = "?"
        cont[(mun, fas, tf, ts)] += 1
    print(f"UC sem transformador achado: {sem_trafo}")

    # Resumo geral dos codigos
    geral_sec = collections.Counter()
    geral_forn = collections.Counter()
    for (mun, fas, tf, ts), n in cont.items():
        geral_sec[ts] += n
        geral_forn[tf] += n
    print("TEN_SEC (tensao secundaria do transformador) ->", {k: (TTEN.get(k, k), v) for k, v in geral_sec.most_common()})
    print("TEN_FORN (tensao de fornecimento da UC) ->", {k: (TTEN.get(k, k), v) for k, v in geral_forn.most_common()})

    # Por municipio: unidades TRIFASICAS (3 fases) pela tensao do transformador
    tri = collections.defaultdict(collections.Counter)
    for (mun, fas, tf, ts), n in cont.items():
        letras = set(fas.upper()) & {"A", "B", "C"}
        if len(letras) == 3:
            tri[mun][ts] += n
    print("\nPOR MUNICIPIO (so UC trifasicas; tensao secundaria do transformador):")
    for mun in sorted(tri):
        partes = ", ".join(f"{TTEN.get(k, k)} V: {v}" for k, v in tri[mun].most_common())
        print(f"  {mun}: {partes}")

    # Tudo, compactado, para ler pela nuvem
    buf = io.StringIO()
    buf.write("mun;fas_con;ten_forn;ten_sec;n\n")
    for (mun, fas, tf, ts), n in sorted(cont.items()):
        buf.write(f"{mun};{fas};{tf};{ts};{n}\n")
    dado = base64.b64encode(gzip.compress(buf.getvalue().encode("utf-8"))).decode()
    print(f"=====INICIO_REDE_{nome}=====")
    for i in range(0, len(dado), 100):
        print(dado[i:i + 100])
    print(f"=====FIM_REDE_{nome}=====")


if __name__ == "__main__":
    main()
