"""Compara a tabela de rede nova com a do repositorio (fase 4, rede por cidade, 11/11/2026).

Uso: python teste/comparar_tabela_rede.py <rede_municipios.csv atual> <rede_municipios.csv nova>
Codigo de saida: 0 = a rede de nenhum municipio mudou (e as contagens sao iguais);
                 2 = algo mudou (ou ainda nao havia tabela) -> ramo novo para revisar;
                 1 = a tabela nova esta com defeito (reprovado).
"""
import csv
import os
import sys

CAMPOS = ["codigo_ibge", "municipio", "uf", "rede", "casas_127_220", "casas_220_380", "motivo"]
REDES = {"127/220", "220/380", "as duas"}


def ler(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        leitor = csv.DictReader(f)
        if leitor.fieldnames != CAMPOS:
            raise ValueError(f"colunas inesperadas: {leitor.fieldnames}")
        linhas = {l["codigo_ibge"]: l for l in leitor}
    for l in linhas.values():
        if l["rede"] not in REDES:
            raise ValueError(f"rede inesperada em {l['codigo_ibge']}: {l['rede']}")
    return linhas


def main():
    atual_arq, nova_arq = sys.argv[1], sys.argv[2]
    try:
        nova = ler(nova_arq)
    except Exception as erro:  # noqa: BLE001
        print("REPROVADO: tabela nova com defeito:", erro)
        return 1
    if not (5500 <= len(nova) <= 5700):
        print(f"REPROVADO: tabela nova com {len(nova)} municipios")
        return 1
    contagem = {r: sum(1 for l in nova.values() if l["rede"] == r) for r in sorted(REDES)}
    print("tabela nova:", len(nova), "municipios;", contagem)
    if not os.path.exists(atual_arq):
        print("NAO HAVIA TABELA no repositorio: a nova vai para revisao.")
        return 2
    atual = ler(atual_arq)
    if set(atual) != set(nova):
        print("A LISTA DE MUNICIPIOS MUDOU:", len(set(nova) - set(atual)), "novos,",
              len(set(atual) - set(nova)), "a menos")
        return 2
    mudou_rede = [c for c in nova if nova[c]["rede"] != atual[c]["rede"]]
    mudou_conta = [c for c in nova if nova[c] != atual[c]]
    print(f"municipios com a REDE diferente: {len(mudou_rede)}; com alguma contagem diferente: {len(mudou_conta)}")
    for c in mudou_rede[:40]:
        print(f"  {c} {nova[c]['municipio']}-{nova[c]['uf']}: {atual[c]['rede']} -> {nova[c]['rede']} ({nova[c]['motivo']})")
    if len(mudou_rede) > 40:
        print(f"  ... e mais {len(mudou_rede) - 40}")
    return 2 if mudou_conta else 0


if __name__ == "__main__":
    sys.exit(main())
