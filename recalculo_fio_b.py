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
Recalculo da sensibilidade financeira dos 5 casos de validacao, apos a
correcao do Fio B (T19, 22/09/2026): de 0,20 R$/kWh (sem fonte, igual
para o pais inteiro) para o Fio B da distribuidora da capital de cada
estado (ANEEL, Dados Abertos, ver FIO_B_POR_UF em calculo.py).

Usa as funcoes REAIS do motor (nao uma conta paralela), com os valores
de energia compensavel e custo total exatamente como aparecem nos
PDFs "Resultado da Simulacao" gerados em 16/09/2026 (fio_b=0.20 antigo).
Geracao, energia compensavel e custo do sistema nao dependem do Fio B -
so a Equacao 7 (valor economizado por kWh) muda.

NAO faz parte da plataforma. E so a conferencia.
"""
from calculo import (
    valor_economizado_por_kwh,
    percentual_fio_b_vigente,
    economia_anual_estimada,
    payback_meses,
    fio_b_do_estado,
)

TARIFA_TESTE = 0.75
FIO_B_ANTIGO = 0.20
PERCENTUAL_2026 = percentual_fio_b_vigente(2026)  # 0.60

# (caso, estado, energia_compensavel_anual_kwh, custo_total_sistema_reais,
#  payback_antigo_meses_exibido_no_pdf)
CASOS = [
    ("1 Bom Jesus da Lapa/BA", "BA", 3000, 6590.80, 41.8),
    ("2 Guaira/PR",            "PR", 3000, 7881.60, 50.0),
    ("3 Manaus/AM",            "AM", 6000, 12336.00, 39.2),
    ("4 Campinas/SP",          "SP", 1560, 5660.80, 69.1),
    ("5 Cuiaba/MT",            "MT", 3000, 7881.60, 50.0),
]

economia_kwh_antigo = valor_economizado_por_kwh(TARIFA_TESTE, FIO_B_ANTIGO, PERCENTUAL_2026)

print(f"Tarifa de teste R$ {TARIFA_TESTE:.2f}/kWh, {PERCENTUAL_2026*100:.0f}% de Fio B em 2026.")
print(f"Antes: Fio B de R$ {FIO_B_ANTIGO:.2f}/kWh em todos os casos "
      f"-> valor economizado R$ {economia_kwh_antigo:.4f}/kWh\n")

print(f"{'Caso':24s} {'Distribuidora':16s} {'Fio B':>7s} {'Econ./mes':>10s} {'Econ./mes':>10s} "
      f"{'Payback':>8s} {'Payback':>8s} {'Payback':>8s}")
print(f"{'':24s} {'(capital)':16s} {'R$/kWh':>7s} {'antes':>10s} {'agora':>10s} "
      f"{'antes':>8s} {'agora':>8s} {'agora':>8s}")
print(f"{'':24s} {'':16s} {'':>7s} {'(R$)':>10s} {'(R$)':>10s} "
      f"{'(meses)':>8s} {'(meses)':>8s} {'(anos)':>8s}")

for nome, uf, energia_compensavel, custo_total, payback_pdf_meses in CASOS:
    ref = fio_b_do_estado(uf)

    economia_mensal_antiga = economia_anual_estimada(energia_compensavel, economia_kwh_antigo) / 12
    payback_antigo_recalculado = payback_meses(custo_total, economia_mensal_antiga)
    # conferencia: o recalculo com o valor antigo tem que bater com o PDF
    assert abs(payback_antigo_recalculado - payback_pdf_meses) < 0.05, nome

    economia_kwh_novo = valor_economizado_por_kwh(TARIFA_TESTE, ref["fio_b"], PERCENTUAL_2026)
    economia_mensal_nova = economia_anual_estimada(energia_compensavel, economia_kwh_novo) / 12
    payback_novo = payback_meses(custo_total, economia_mensal_nova)

    print(f"{nome:24s} {ref['distribuidora']:16s} {ref['fio_b']:>7.4f} "
          f"{economia_mensal_antiga:>10.2f} {economia_mensal_nova:>10.2f} "
          f"{payback_pdf_meses:>8.1f} {payback_novo:>8.1f} {payback_novo/12:>8.2f}")

print("\nConferencia OK: com fio_b=0.20, o payback recalculado bate com o dos "
      "PDFs (diferenca < 0,05 mes nos 5 casos).")
# ATUALIZADO NO PASSO 7 (02/10/2026). Ate aqui esta linha anunciava uma
# limitacao: "Campinas e atendida pela CPFL Paulista, mas a plataforma usa a
# distribuidora da capital de SP". Essa limitacao ACABOU - o motor passou a
# escolher a distribuidora pelo municipio (fio_b_do_municipio, no calculo.py).
# A tabela FIO_B_POR_UF, que este programa usa acima, continua sendo o criterio
# da capital porque ele existe para reproduzir a correcao T19 como ela foi
# feita em 22/09/2026; os numeros aqui sao historicos, de proposito.
print("Observacao: a coluna 'agora' usa a tabela por ESTADO (criterio da "
      "capital), que e o que a correcao T19 adotou em 22/09/2026. Desde o "
      "passo 7 (02/10/2026) a plataforma escolhe pela distribuidora do "
      "MUNICIPIO: Campinas, por exemplo, passou a usar a CPFL Paulista "
      "(R$ 0,2005/kWh) no lugar da distribuidora da capital de SP "
      "(R$ 0,2121/kWh).")
