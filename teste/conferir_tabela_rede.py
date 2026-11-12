"""Confere o leitor da tabela de rede (rede_municipios.py) - fase 4, rede por cidade, 11/11/2026.

Uso: python teste/conferir_tabela_rede.py
1. A tabela do repositorio carrega inteira e da as redes esperadas nas 10 cidades do artigo (a).
2. Defeitos plantados (cada um numa copia) DESLIGAM a tabela inteira: nenhuma resposta pela metade.
Codigo de saida 0 = tudo certo; 1 = algo falhou.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rede_municipios as rm  # noqa: E402

ESPERADO_10_CASOS = {  # rede da tabela (None = "as duas": o site mostra os dois, como antes)
    "1302603": "127/220",  # Manaus
    "1501402": "127/220",  # Belem
    "2903904": None,       # Bom Jesus da Lapa (87,7% em 127/220 -> as duas)
    "2211001": "220/380",  # Teresina
    "5103403": "127/220",  # Cuiaba
    "5002704": "127/220",  # Campo Grande
    "3509502": "127/220",  # Campinas
    "3304557": "127/220",  # Rio de Janeiro
    "4108809": "127/220",  # Guaira
    "4106902": "127/220",  # Curitiba
}
falhas = []


def checar(cond, texto):
    print(("OK    " if cond else "FALHA ") + texto)
    if not cond:
        falhas.append(texto)


checar(rm.MOTIVO_DESLIGADA is None and len(rm.TABELA) == 5571,
       f"tabela do repositorio ligada com 5571 municipios (motivo: {rm.MOTIVO_DESLIGADA})")
for codigo, rede in ESPERADO_10_CASOS.items():
    checar(rm.rede_do_municipio(codigo) == rede, f"{codigo}: {rm.rede_do_municipio(codigo)} (esperado {rede})")
checar(rm.rede_do_municipio("0000000") is None and rm.rede_do_municipio(None) is None,
       "codigo inexistente ou vazio -> None")


def com_defeito(nome, mexer, acertar_sha=True):
    """Copia a tabela, aplica o defeito e confere que o leitor a DESLIGA."""
    pasta = tempfile.mkdtemp()
    csv_arq, info_arq = os.path.join(pasta, "t.csv"), os.path.join(pasta, "i.json")
    shutil.copy(rm.ARQUIVO_TABELA, csv_arq)
    shutil.copy(rm.ARQUIVO_INFO, info_arq)
    with open(csv_arq, encoding="utf-8") as f:
        linhas = f.read().split("\n")
    info = json.load(open(info_arq, encoding="utf-8"))
    linhas, info = mexer(linhas, info)
    if linhas is None:
        os.remove(csv_arq)
    else:
        with open(csv_arq, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas))
        if acertar_sha:  # o defeito mais dificil: quem mexeu tambem atualizou o sha256
            info["csv_sha256"] = hashlib.sha256(open(csv_arq, "rb").read()).hexdigest()
    with open(info_arq, "w", encoding="utf-8") as f:
        json.dump(info, f)
    tabela, _, motivo = rm._carregar(csv_arq, info_arq)
    checar(tabela == {} and motivo, f"defeito '{nome}' desliga a tabela ({motivo})")
    shutil.rmtree(pasta)


def troca_linha(alvo, novo):
    def mexer(linhas, info):
        return [l.replace(alvo, novo, 1) if l.startswith(alvo.split(",")[0] + ",") else l for l in linhas], info
    return mexer


com_defeito("sem o CSV", lambda l, i: (None, i))
com_defeito("linha mudada sem atualizar o sha256",
            troca_linha("4108809,Guaíra,PR,127/220", "4108809,Guaíra,PR,220/380"), acertar_sha=False)
com_defeito("rede trocada contra as contagens (Guaira 220/380)",
            troca_linha("4108809,Guaíra,PR,127/220", "4108809,Guaíra,PR,220/380"))
com_defeito("rede inexistente", troca_linha("4108809,Guaíra,PR,127/220", "4108809,Guaíra,PR,380/220"))
com_defeito("codigo IBGE repetido", lambda l, i: (l[:2] + [l[1]] + l[2:], i))
com_defeito("codigo IBGE invalido", lambda l, i: ([l[0], "41088," + l[1].split(",", 1)[1]] + l[2:], i))
com_defeito("tabela cortada pela metade", lambda l, i: (l[:2800], i))
com_defeito("coluna renomeada", lambda l, i: ([l[0].replace("rede", "tensao", 1)] + l[1:], i))
com_defeito("contagem do info diferente", lambda l, i: (l, {**i, "contagem": {"127/220": 1}}))
com_defeito("contagem negativa", troca_linha("4108809,Guaíra,PR,127/220,", "4108809,Guaíra,PR,127/220,-"))

print()
print("TUDO CERTO" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
