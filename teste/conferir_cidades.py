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
conferir_cidades.py - confere a troca da busca de cidade (fase 1 pos-TCC,
29/09/2026, item 24 do backlog).

A troca: a cidade deixou de ser texto livre (com sugestoes pedidas ao
Nominatim, o que a politica dele proibe) e passou a ser escolhida numa lista
local de municipios. As coordenadas continuam vindo do Nominatim, por busca
estruturada, e ficam guardadas em cache.

A PERGUNTA QUE ESTE PROGRAMA RESPONDE: a troca mudou algum resultado de
dimensionamento? Ela nao mexe em calculo.py, simulacao.py nem app.py, mas
pode mudar a COORDENADA que entra na NASA POWER - e coordenada diferente
pode dar sol (HSP) diferente.

Quatro partes:
  1. A LISTA (sem internet): 5.571 municipios, codigos unicos, todo rotulo
     da lista e reconhecido pelo servidor, nomes repetidos entre estados.
  2. A LISTA CONTRA O IBGE: compara codigo, nome e estado com a lista
     oficial (API de Localidades do IBGE).
  3. OS CINCO CASOS DE VALIDACAO: roda a plataforma de verdade (Nominatim e
     NASA POWER reais) e compara com os numeros da tela de 23/09/2026, os
     mesmos que estao no artigo e em resultados/plataforma/. Mostra tambem a
     coordenada antiga (reproduzida) e a nova, e o sol de cada uma.
  4. AMOSTRA DO PAIS: as 27 capitais, 40 municipios sorteados e 5 casos
     dificeis (homonimos e nomes corrigidos). Confere se o
     Nominatim acha cada um, e a distancia ate a coordenada da lista
     original (kelvins), que serve so de conferencia independente.

Precisa de internet. Leva uns 4 minutos, porque o Nominatim aceita no maximo
1 consulta por segundo. Vai mostrando o progresso.

Uso, dentro da pasta da plataforma:
    python teste/conferir_cidades.py

O resultado completo tambem e gravado em teste/resultado_conferencia_cidades.txt

Desde o passo 2 da fase 1 (30/09/2026) a Parte 3 mostra tambem de onde veio o
sol de cada caso: "nasa" (consulta nova) ou "cache" (resposta guardada em
cache/nasa_power.json). Rodando duas vezes, a segunda tem de dar "cache" e os
MESMOS numeros.

PARTE 5, acrescentada no passo 4 da fase 1 (30/09/2026): CIDADES NOVAS. As
cidades das partes 3 e 4 ja estao todas no cache, entao elas nao chegam a
consultar o Nominatim. A parte 5 sorteia 20 municipios que AINDA NAO estao no
cache e busca cada um de verdade, com o geocoding.py do passo 4 (tentativas e
pausa depois de aviso do Nominatim). Confere: coordenada vinda do Nominatim,
o que aconteceu em cada tentativa, o tempo de cada busca e a distancia ate a
coordenada da lista original. Como o cache cresce a cada rodada, cada rodada
sorteia cidades diferentes (a semente e fixa, mas a lista de candidatas
muda).
"""

import csv
import io
import math
import os
import random
import sys
import time
from datetime import datetime

import requests

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA)

import geocoding     # noqa: E402
import nasa_power    # noqa: E402
import simulacao     # noqa: E402

ARQUIVO_SAIDA = os.path.join(PASTA, "teste", "resultado_conferencia_cidades.txt")
_saida = []


def mostrar(texto=""):
    print(texto, flush=True)
    _saida.append(texto)


def distancia_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Os cinco casos, com os numeros da tela de 23/09/2026 (resultados/plataforma/)
# ---------------------------------------------------------------------------
# "antigo" e o nome que o Nominatim devolveu na tela de 23/09. Serve para
# REPRODUZIR a coordenada antiga, de forma aproximada: o texto que foi
# digitado naquele dia nao ficou registrado.
# "pvsyst" e a coordenada usada no PVsyst (pagina 1 de cada relatorio).
CASOS = [
    {"cidade": "Bom Jesus da Lapa - BA", "uf": "BA", "consumo": 300, "fatura": 225.00,
     "antigo": "Residencial Bom Jesus da Lapa, Bom Jesus da Lapa, Bahia, Região Nordeste, Brasil",
     "pvsyst": (-13.2499, -43.4101),
     "tela": {"paineis": 4, "kwp": 2.40, "inversor": 2.00, "hsp": 6.04,
              "geracao": [394, 350, 360, 331, 309, 291, 319, 362, 385, 396, 351, 387],
              "geracao_ano": 4236, "economia": 162.08, "custo": 7881.60, "payback": 48.6}},
    {"cidade": "Campinas - SP", "uf": "SP", "consumo": 180, "fatura": 135.00,
     "antigo": "Campinas, São Paulo, Região Sudeste, Brasil",
     "pvsyst": (-22.9056, -47.0596),
     "tela": {"paineis": 3, "kwp": 1.80, "inversor": 1.50, "hsp": 5.14,
              "geracao": [253, 236, 244, 213, 180, 163, 180, 216, 229, 258, 260, 271],
              "geracao_ano": 2702, "economia": 97.50, "custo": 6590.80, "payback": 67.6}},
    {"cidade": "Cuiabá - MT", "uf": "MT", "consumo": 300, "fatura": 225.00,
     "antigo": "Cuiabá, Mato Grosso, Região Centro-Oeste, Brasil",
     "pvsyst": (-15.5987, -56.0991),
     "tela": {"paineis": 4, "kwp": 2.40, "inversor": 2.00, "hsp": 5.27,
              "geracao": [328, 294, 326, 300, 275, 263, 292, 322, 300, 325, 330, 337],
              "geracao_ano": 3691, "economia": 168.28, "custo": 7881.60, "payback": 46.8}},
    {"cidade": "Guaíra - PR", "uf": "PR", "consumo": 300, "fatura": 225.00,
     "antigo": "Guaíra, Paraná, Região Sul, 85980-000, Brasil",
     "pvsyst": (-24.0800, -54.2558),
     "tela": {"paineis": 5, "kwp": 3.00, "inversor": 2.50, "hsp": 4.94,
              "geracao": [482, 398, 414, 331, 255, 218, 249, 310, 338, 395, 453, 481],
              "geracao_ano": 4323, "economia": 186.38, "custo": 9150.00, "payback": 49.1}},
    {"cidade": "Manaus - AM", "uf": "AM", "consumo": 550, "fatura": 412.50,
     "antigo": "Manaus, Amazonas, Região Norte, 69000-000, Brasil",
     "pvsyst": (-3.1316, -59.9825),
     "tela": {"paineis": 9, "kwp": 5.40, "inversor": 5.00, "hsp": 4.67,
              "geracao": [591, 529, 583, 556, 567, 604, 678, 713, 696, 677, 604, 571],
              "geracao_ano": 7369, "economia": 355.49, "custo": 13513.50, "payback": 38.0}},
]


def coordenada_antiga(texto):
    """Reproduz o geocoding.py de 27/09 (texto livre, primeiro resultado)."""
    time.sleep(geocoding.INTERVALO_MINIMO_S)
    r = requests.get(geocoding.URL_NOMINATIM,
                     params={"q": texto, "format": "json", "limit": 1},
                     headers={"User-Agent": geocoding.USER_AGENT},
                     timeout=geocoding.TEMPO_LIMITE_S)
    r.raise_for_status()
    dados = r.json()
    return (float(dados[0]["lat"]), float(dados[0]["lon"])) if dados else None


def parte1():
    mostrar("=" * 72)
    mostrar("PARTE 1 - A LISTA DE MUNICIPIOS (sem internet)")
    mostrar("=" * 72)
    lista = geocoding.MUNICIPIOS
    codigos = {m["ibge"] for m in lista}
    mostrar(f"Registros na lista:            {len(lista)}")
    mostrar(f"Codigos IBGE diferentes:       {len(codigos)}")
    voltam = sum(1 for m in lista if geocoding.encontrar_municipio(geocoding.rotulo(m)) is m)
    mostrar(f"Rotulos reconhecidos pelo servidor: {voltam} de {len(lista)}")
    por_nome = {}
    for m in lista:
        por_nome.setdefault(geocoding.normalizar(m["nome"]), []).append(m)
    exatos = {}
    for m in lista:
        exatos.setdefault(m["nome"], []).append(m)
    rep_exatos = {n: ms for n, ms in exatos.items() if len(ms) > 1}
    mostrar(f"Nomes escritos igual em mais de um estado: {len(rep_exatos)} nomes, "
            f"{sum(len(ms) for ms in rep_exatos.values())} municipios")
    repetidos = {n: ms for n, ms in por_nome.items() if len(ms) > 1}
    mostrar(f"Iguais ao ignorar acento e maiuscula:      {len(repetidos)} nomes, "
            f"{sum(len(ms) for ms in repetidos.values())} municipios")
    exemplos = sorted(repetidos.values(), key=lambda ms: -len(ms))[:5]
    for ms in exemplos:
        mostrar(f"    {ms[0]['nome']}: {', '.join(sorted(m['uf'] for m in ms))}")
    mostrar(f"'Guaíra' sem estado e aceito?  {geocoding.encontrar_municipio('Guaíra') is not None}"
            "  (tem de ser False: existe no PR e em SP)")
    return len(lista) == len(codigos) and voltam == len(lista)


def parte2():
    mostrar()
    mostrar("=" * 72)
    mostrar("PARTE 2 - A LISTA CONTRA A LISTA OFICIAL DO IBGE")
    mostrar("=" * 72)
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    mostrar(f"Fonte: {url}")
    try:
        r = requests.get(url, headers={"User-Agent": geocoding.USER_AGENT}, timeout=60)
        r.raise_for_status()
        oficiais = r.json()
    except Exception as erro:          # noqa: BLE001 - registrar e seguir
        mostrar(f"NAO FOI POSSIVEL BAIXAR A LISTA DO IBGE: {erro}")
        return None

    def uf_de(m):
        for caminho in (("microrregiao", "mesorregiao", "UF", "sigla"),
                        ("regiao-imediata", "regiao-intermediaria", "UF", "sigla")):
            v = m
            for chave in caminho:
                v = (v or {}).get(chave) if isinstance(v, dict) else None
            if v:
                return v
        return None

    ibge = {int(m["id"]): (m["nome"], uf_de(m)) for m in oficiais}
    nossa = {m["ibge"]: m for m in geocoding.MUNICIPIOS}
    mostrar(f"Municipios na lista do IBGE:   {len(ibge)}")
    mostrar(f"Municipios na nossa lista:     {len(nossa)}")
    so_nossa = sorted(set(nossa) - set(ibge))
    so_ibge = sorted(set(ibge) - set(nossa))
    nome_dif, uf_dif, acento_dif = [], [], []
    for cod in sorted(set(nossa) & set(ibge)):
        n_ibge, uf_ibge = ibge[cod]
        m = nossa[cod]
        if uf_ibge and uf_ibge != m["uf"]:
            uf_dif.append((cod, m["nome"], m["uf"], uf_ibge))
        if m["nome"] != n_ibge:
            if geocoding.normalizar(m["nome"]) == geocoding.normalizar(n_ibge):
                acento_dif.append((cod, m["nome"], n_ibge))
            else:
                nome_dif.append((cod, m["nome"], n_ibge))
    mostrar(f"So na nossa lista:             {len(so_nossa)}")
    for cod in so_nossa:
        mostrar(f"    {cod} {nossa[cod]['nome']} - {nossa[cod]['uf']}")
    mostrar(f"So na lista do IBGE:           {len(so_ibge)}")
    for cod in so_ibge:
        mostrar(f"    {cod} {ibge[cod][0]} - {ibge[cod][1]}")
    mostrar(f"Estado diferente:              {len(uf_dif)}")
    for item in uf_dif:
        mostrar(f"    {item}")
    mostrar(f"Nome diferente:                {len(nome_dif)}")
    for cod, nosso, dele in nome_dif:
        mostrar(f"    {cod}: nossa lista '{nosso}'  |  IBGE '{dele}'")
    mostrar(f"So acento/maiuscula/apostrofo: {len(acento_dif)}")
    for cod, nosso, dele in acento_dif:
        mostrar(f"    {cod}: nossa lista '{nosso}'  |  IBGE '{dele}'")
    return not (so_nossa or so_ibge or uf_dif or nome_dif)


def parte3():
    mostrar()
    mostrar("=" * 72)
    mostrar("PARTE 3 - OS CINCO CASOS DE VALIDACAO (Nominatim e NASA POWER reais)")
    mostrar("=" * 72)
    mostrar("Comparacao com a tela de 23/09/2026, na precisao que a tela mostra.")
    tudo_igual = True
    for i, caso in enumerate(CASOS, 1):
        mostrar()
        mostrar(f"[{i}/5] {caso['cidade']} ...")
        novo = geocoding.buscar_coordenadas(caso["cidade"])
        if novo is None:
            mostrar("    O NOMINATIM NAO DEVOLVEU RESULTADO CONFIAVEL - CASO NAO CONFERIDO")
            for linha in geocoding.ULTIMO_DIAGNOSTICO or ["(nenhuma resposta)"]:
                mostrar(f"        resposta: {linha}")
            tudo_igual = False
            continue
        antigo = coordenada_antiga(caso["antigo"])
        lat, lon = novo["latitude"], novo["longitude"]
        mostrar(f"    coordenada nova:   {lat:.5f}, {lon:.5f}  "
                f"({novo['fonte_coordenadas']}, OSM {novo['osm_tipo']} {novo['osm_id']})")
        if antigo:
            mostrar(f"    coordenada antiga: {antigo[0]:.5f}, {antigo[1]:.5f}  (reproduzida)"
                    f"  -> {distancia_km(lat, lon, *antigo):.2f} km da nova")
        mostrar(f"    coordenada PVsyst: {caso['pvsyst'][0]:.4f}, {caso['pvsyst'][1]:.4f}"
                f"  -> {distancia_km(lat, lon, *caso['pvsyst']):.2f} km da nova")

        hsp_novo = nasa_power.buscar_hsp_mensal(lat, lon)
        mostrar("    HSP nova (12 meses):   " + " ".join(f"{h:.2f}" for h in hsp_novo))
        # passo 2 da fase 1 (30/09/2026): de onde veio o sol - "nasa" na
        # primeira rodada, "cache" a partir da segunda
        diag = nasa_power.ULTIMO_DIAGNOSTICO
        mostrar(f"    sol veio de: {diag.get('fonte')} (consulta de {diag.get('data_consulta')})")
        if antigo:
            hsp_antigo = nasa_power.buscar_hsp_mensal(*antigo)
            igual = hsp_antigo == hsp_novo
            mostrar("    HSP antiga (12 meses): " + " ".join(f"{h:.2f}" for h in hsp_antigo)
                    + ("   -> IDENTICA" if igual else "   -> DIFERENTE"))

        res = simulacao.simular(cidade=caso["cidade"], consumo_medio_kwh=caso["consumo"],
                                valor_fatura_reais=caso["fatura"],
                                consumo_da_fatura_kwh=caso["consumo"], tipo_ligacao="",
                                percentual_fio_b=0.60)
        if "erro" in res:
            mostrar(f"    ERRO NA SIMULACAO: {res['erro']}")
            tudo_igual = False
            continue
        t = caso["tela"]
        obtido = {
            "paineis": res["numero_paineis"],
            "kwp": round(res["potencia_instalada_kwp"], 2),
            "inversor": round(res["potencia_inversor_kw"], 2),
            "hsp": round(res["hsp_medio_anual"], 2),
            "geracao": [round(g) for g in res["geracao_por_mes_kwh"].values()],
            "geracao_ano": round(res["geracao_anual_kwh"]),
            "economia": round(res["economia_mensal_media"], 2),
            "custo": round(res["custo_total_sistema"], 2),
            "payback": round(res["payback_meses"], 1),
        }
        diferencas = [k for k in t if obtido[k] != t[k]]
        if res.get("fio_b_uf") != caso["uf"]:
            diferencas.append("estado do Fio B")
        for k in t:
            marca = "igual" if obtido[k] == t[k] else "DIFERENTE"
            mostrar(f"    {k:<12} tela {str(t[k]):<55} agora {str(obtido[k]):<55} {marca}")
        mostrar(f"    estado usado no Fio B: {res.get('fio_b_uf')} "
                f"({res.get('fio_b_distribuidora_referencia')})")
        if diferencas:
            tudo_igual = False
            mostrar(f"    >>> RESULTADO MUDOU em: {', '.join(diferencas)}")
        else:
            mostrar("    >>> RESULTADO IDENTICO A TELA DE 23/09")
    return tudo_igual


def parte4():
    mostrar()
    mostrar("=" * 72)
    mostrar("PARTE 4 - AMOSTRA DO PAIS: 27 capitais + 40 sorteados + 5 casos dificeis")
    mostrar("=" * 72)
    url = ("https://raw.githubusercontent.com/kelvins/municipios-brasileiros/"
           "503e2f70bbf1b4b7ec0b1f68b09086ccc38fe861/csv/municipios.csv")
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        linhas = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception as erro:          # noqa: BLE001
        mostrar(f"NAO FOI POSSIVEL BAIXAR A LISTA ORIGINAL: {erro}")
        return None
    coord = {int(l["codigo_ibge"]): (float(l["latitude"]), float(l["longitude"])) for l in linhas}
    capitais = [int(l["codigo_ibge"]) for l in linhas if l["capital"] == "1"]
    outros = [m["ibge"] for m in geocoding.MUNICIPIOS if m["ibge"] not in capitais]
    sorteados = random.Random(2026).sample(outros, 40)   # semente fixa: repetivel
    por_codigo = {m["ibge"]: m for m in geocoding.MUNICIPIOS}
    # Casos dificeis, fixos (30/09/2026): Agua Branca/PI (a 1a versao pegou um
    # povoado homonimo de outro municipio, a 282 km); Bom Jesus da Lapa/BA (o
    # ponto do municipio fica a 25 km da cidade); Guaira/SP (homonimo da de
    # Guaira/PR); Campo Grande/RN e Assu/RN (nomes corrigidos para o IBGE).
    dificeis = [2200202, 2903904, 3517406, 2401305, 2400208]
    amostra = capitais + sorteados + [c for c in dificeis if c not in capitais + sorteados]
    mostrar("Distancia = da coordenada do Nominatim ate a da lista original.")
    mostrar("Acima de 20 km aparece 'CONFERIR' (nao e erro por si so).")
    falhas, longe, distancias = [], [], []
    for i, cod in enumerate(amostra, 1):
        m = por_codigo[cod]
        res = geocoding.buscar_coordenadas(geocoding.rotulo(m))
        if res is None:
            falhas.append(geocoding.rotulo(m))
            mostrar(f"  [{i:>2}/{len(amostra)}] {geocoding.rotulo(m):<40} SEM RESULTADO CONFIAVEL")
            for linha in geocoding.ULTIMO_DIAGNOSTICO or ["(nenhuma resposta)"]:
                mostrar(f"        resposta: {linha}")
            continue
        d = distancia_km(res["latitude"], res["longitude"], *coord[cod])
        distancias.append(d)
        aviso = "  CONFERIR" if d > 20 else ""
        if d > 20:
            longe.append((geocoding.rotulo(m), d))
        mostrar(f"  [{i:>2}/{len(amostra)}] {geocoding.rotulo(m):<40} {d:7.2f} km"
                f"  ({res['fonte_coordenadas']}, {res['osm_tipo']}){aviso}")
        if d > 20:
            for linha in geocoding.ULTIMO_DIAGNOSTICO:
                mostrar(f"        resposta: {linha}")
    mostrar()
    mostrar(f"Achados: {len(amostra) - len(falhas)} de {len(amostra)}")
    if distancias:
        distancias.sort()
        mostrar(f"Distancia: mediana {distancias[len(distancias) // 2]:.2f} km, "
                f"maior {distancias[-1]:.2f} km")
    mostrar(f"Sem resultado: {falhas}")
    mostrar(f"Acima de 20 km: {longe}")
    return not falhas


def parte5():
    mostrar()
    mostrar("=" * 72)
    mostrar("PARTE 5 - CIDADES NOVAS: 20 municipios que ainda NAO estao no cache")
    mostrar("=" * 72)
    url = ("https://raw.githubusercontent.com/kelvins/municipios-brasileiros/"
           "503e2f70bbf1b4b7ec0b1f68b09086ccc38fe861/csv/municipios.csv")
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        linhas = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception as erro:          # noqa: BLE001
        mostrar(f"NAO FOI POSSIVEL BAIXAR A LISTA ORIGINAL: {erro}")
        return None
    coord = {int(l["codigo_ibge"]): (float(l["latitude"]), float(l["longitude"])) for l in linhas}
    ja_guardados = set(geocoding._ler_cache())
    candidatos = [m for m in geocoding.MUNICIPIOS if str(m["ibge"]) not in ja_guardados]
    amostra = random.Random(20260930).sample(candidatos, 20)
    mostrar(f"Cidades no cache antes desta parte: {len(ja_guardados)}. "
            f"Candidatas: {len(candidatos)}.")
    mostrar("Cada linha: distancia ate a lista original | de onde veio a coordenada |"
            " tentativas | tempo da busca.")
    erros, sem_resultado, nao_nominatim, longe, distancias = [], [], [], [], []
    for i, m in enumerate(amostra, 1):
        nome = geocoding.rotulo(m)
        inicio = time.monotonic()
        try:
            res = geocoding.buscar_coordenadas(nome)
        except geocoding.ErroNominatim as erro:
            erros.append(nome)
            mostrar(f"  [{i:>2}/20] {nome:<40} ERRO DE CONSULTA: {erro}")
            continue
        tempo = time.monotonic() - inicio
        tentativas = ", ".join(geocoding.ULTIMAS_TENTATIVAS) or "-"
        if res is None:
            sem_resultado.append(nome)
            mostrar(f"  [{i:>2}/20] {nome:<40} SEM RESULTADO CONFIAVEL"
                    f"  (tentativas: {tentativas}; {tempo:.1f} s)")
            for linha in geocoding.ULTIMO_DIAGNOSTICO or ["(nenhuma resposta)"]:
                mostrar(f"        resposta: {linha}")
            continue
        if res["fonte_coordenadas"] != "nominatim":
            nao_nominatim.append(nome)
        d = distancia_km(res["latitude"], res["longitude"], *coord[m["ibge"]])
        distancias.append(d)
        aviso = "  CONFERIR" if d > 20 else ""
        if d > 20:
            longe.append((nome, round(d, 2)))
        mostrar(f"  [{i:>2}/20] {nome:<40} {d:7.2f} km | {res['fonte_coordenadas']}, "
                f"{res['osm_tipo']} | {tentativas} | {tempo:.1f} s{aviso}")
        if d > 20:
            for linha in geocoding.ULTIMO_DIAGNOSTICO:
                mostrar(f"        resposta: {linha}")
    mostrar()
    mostrar(f"Achados: {len(distancias)} de 20")
    if distancias:
        distancias.sort()
        mostrar(f"Distancia: mediana {distancias[len(distancias) // 2]:.2f} km, "
                f"maior {distancias[-1]:.2f} km")
    mostrar(f"Erro de consulta (Nominatim fora ou aviso): {erros}")
    mostrar(f"Sem resultado confiavel: {sem_resultado}")
    mostrar(f"Nao vieram do Nominatim (deviam vir): {nao_nominatim}")
    mostrar(f"Acima de 20 km: {longe}")
    return not (erros or sem_resultado or nao_nominatim)


if __name__ == "__main__":
    mostrar(f"Conferencia da busca de cidade - {datetime.now():%d/%m/%Y %H:%M}")
    mostrar(f"User-Agent: {geocoding.USER_AGENT}")
    resumo = {"1 lista": parte1(), "2 IBGE": parte2(), "3 casos": parte3(), "4 amostra": parte4(),
              "5 novas": parte5()}
    mostrar()
    mostrar("=" * 72)
    mostrar("RESUMO")
    mostrar("=" * 72)
    for parte, ok in resumo.items():
        estado = "OK" if ok else ("NAO RODOU" if ok is None else "TEM DIFERENCA - VER ACIMA")
        mostrar(f"  Parte {parte:<10} {estado}")
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as arq:
        arq.write("\n".join(_saida) + "\n")
    print(f"\nResultado gravado em {ARQUIVO_SAIDA}")
