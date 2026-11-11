# Quantos Painéis

Plataforma web gratuita que estima o sistema de energia solar de uma unidade consumidora residencial ligada à rede (on-grid). A pessoa informa o consumo de energia, o valor e o consumo de uma conta de luz e o município. A plataforma devolve o número de painéis, a potência do sistema, o inversor, a geração de cada mês, a economia na conta e o tempo de retorno do investimento.

A plataforma nasceu do Trabalho de Conclusão de Curso de Engenharia Elétrica **"Dimensionamento fotovoltaico residencial na web"** (Centro Universitário Internacional Uninter, 2026), de Brenda Morel Bueno Ferreira. Não tem cadastro, não pede dado pessoal e não vende nada.

> **Aviso:** a plataforma é uma simulação educativa. Ela não substitui o projeto de um profissional habilitado.

## Duas versões neste repositório

O repositório guarda duas versões, e cada uma tem um papel diferente.

**A versão do TCC** está na tag [`v1.0-tcc`](../../tree/v1.0-tcc). É exatamente o código descrito no artigo do TCC e avaliado pela banca. Ela não muda mais. Quem quiser conferir o artigo do TCC deve usar essa versão.

**A versão do site** está no ramo `main`. É a que roda na internet. O dimensionamento é o mesmo do TCC: os cinco casos de validação dão o mesmo número de módulos, o mesmo inversor e a mesma geração. O que mudou foi o resto, para o site ficar mais completo e mais fácil de entender:

- **Município numa lista oficial.** A cidade passou a ser escolhida numa lista dos 5.571 municípios do IBGE, e o estado vem da lista. Antes era digitada livremente.
- **Fio B da distribuidora do município.** Antes o valor era o da distribuidora da capital do estado. Agora cada município usa o da sua própria distribuidora (dados abertos da ANEEL). A tela mostra até quando o valor vale.
- **Retorno mês a mês.** No TCC, o tempo de retorno é a conta simples (investimento dividido pela economia do primeiro ano, Equação 11). No site, ele é calculado mês a mês, com o Fio B subindo ano a ano como manda a Lei 14.300/2022 e com um desgaste dos módulos de 0,5% ao ano. Por isso o retorno do site é um pouco mais longo que o do TCC. A conta simples continua no motor (`payback_meses()`) e é conferida pelo teste.
- **Cobranças que não são energia.** Há um campo opcional para a iluminação pública e outras cobranças da conta, que não somem com a energia solar.
- **Inversor de 1,0 kW.** O sistema de dois painéis de 600 Wp passou a usar o Growatt MIC 1000TL-X no lugar do MIC 1500TL-X. Com o de 1,5 kW, o inversor ficava maior que os painéis. Painéis, geração, custo e retorno não mudam.
- **Inversores com o nome do registro no Inmetro.** Nos degraus de 7,0, 7,5 e 8,0 kW, o site mostrava nomes que não estão no registro do Inmetro. Passaram a ser os modelos registrados: Growatt MIN 7000TL-X(E), MIN 7500TL-X2 e MIN 8000TL-X2 (consulta de 10/11/2026). Os limites elétricos usados continuam os de antes, iguais ou mais apertados que os das folhas desses modelos. Painéis, geração, custo e retorno não mudam.
- **Inversores trifásicos de 12 a 25 kW.** Antes, acima de 10 kW (a partir de cerca de 21 painéis) o site não indicava inversor. Agora indica um inversor trifásico de 12, 15, 20 ou 25 kW, com um modelo para rede de 127/220 V e outro para rede de 220/380 V (Growatt e Deye, com registro ativo no Inmetro); os painéis precisam servir nos dois. A verificação elétrica passou a somar a corrente de duas fileiras ligadas na mesma entrada do inversor. Nesse porte a conta usa a ligação trifásica (mínimo de 100 kWh), e a tela avisa quando a casa precisa trocar de ligação. Acima de 25 kW, o sistema sai do porte residencial e o site não dimensiona. Nada muda até 10 kW.
- **Energia usada na hora.** Uma pergunta opcional diz em que horário a casa mais usa energia. A parte da geração usada no mesmo instante (10%, 30% ou 39%, pelo lado baixo das medições da ANEEL, da EPE e de Dilli e Brito, 2025) economiza a tarifa inteira, sem o Fio B. Muda só a economia e o retorno; painéis, inversor e custo não mudam. Sem resposta, a conta é a de antes (0%).
- **Manutenção, 25 anos e poupança.** O retorno passou a descontar a manutenção (1% do preço por ano) e uma troca do inversor depois de 10 anos (15% do preço), valores da EPE (Nota Técnica EPE-DEA-SEE 014/2022). O mesmo fluxo vai até 25 anos e dá a economia e os gastos do período, a taxa interna de retorno real ("rende cerca de X% ao ano") comparada com a poupança dos últimos 12 meses descontada a inflação (Banco Central, séries 196 e 433), o VPL e o retorno descontado. A tela mostra também o pior caso para 2029: a cobrança máxima que a Lei 14.300/2022 (art. 17) permite sobre a energia compensada, pelos dados abertos da ANEEL, sem desconto pelos benefícios. A conta principal continua com 100% do Fio B depois de 2028. Painéis, inversor, geração, custo e economia de hoje não mudam.
- **Nove páginas de explicação.** Como funciona, economia, equipamentos e preços, precisão, metodologia, limitações, sobre, contato e apoie.
- **Atualização automática do Fio B** e **contador de acessos sem dado pessoal**, explicados mais abaixo.

## O que tem aqui

| Pasta ou arquivo | O que é |
|---|---|
| `calculo.py` | O motor de cálculo: as equações, a verificação elétrica e o catálogo de módulos e inversores |
| `simulacao.py` | Junta tudo numa função só, `simular()` |
| `geocoding.py` | Acha o município na lista; se a tabela de sol faltar, busca as coordenadas (Nominatim/OpenStreetMap) |
| `nasa_power.py` | Busca a irradiação solar de cada mês na NASA POWER, se a tabela de sol faltar |
| `sol_municipios.csv`, `sol_municipios_info.json` | A tabela de sol: 12 médias mensais da NASA POWER (2001-2025) para cada um dos 5.571 municípios, e de onde ela veio |
| `sol_municipios.py` | Lê e confere a tabela de sol; com qualquer defeito, a tabela fica desligada e o site volta a consultar o Nominatim e a NASA |
| `montar_tabela_sol.py` | Monta a tabela de sol: escolhe o quadrado de 1 grau da NASA de cada município pela maioria entre três fontes de localização da sede (IBGE, municipios-brasileiros e Wikidata) |
| `app.py`, `templates/`, `static/` | O site (Flask): o formulário, a tela de resultado e as páginas de explicação |
| `armazenamento.py`, `contador.py` | O banco opcional: memória de municípios e de sol, e o contador de acessos |
| `atualizar_dados_aneel.py` | Baixa os dados abertos da ANEEL e refaz os dois arquivos abaixo |
| `fio_b_por_distribuidora.csv` | Fio B de cada distribuidora, com vigência e resolução da ANEEL |
| `static/distribuidoras_por_municipio.json` | A distribuidora de cada município |
| `static/municipios.json` | A lista dos 5.571 municípios (origem em `static/municipios-LICENCA.txt`) |
| `fio_b_aneel_vigente_22-09-2026.csv`, `fio_b_aneel_conferencia_01-10-2026.csv` | Retratos do Fio B usados no TCC e numa conferência |
| `recalculo_fio_b.py` | Conferência feita para o TCC: o efeito, nos cinco casos, da troca do Fio B de R$ 0,20 pelo da ANEEL |
| `.github/workflows/atualizar-fio-b.yml` | A tarefa automática do Fio B |
| `.github/workflows/renovar-tabela-sol.yml`, `teste/comparar_tabela_sol.py` | A renovação da tabela de sol e a comparação da tabela nova com a atual |
| `teste/` | Os programas de conferência e os resultados deles |
| `resultados/plataforma/` | A tela de resultado dos cinco casos de validação do TCC, em PDF |
| `resultados/pvsyst/` | Os relatórios das simulações no PVsyst 8.1.5, com todos os parâmetros |
| `resultados/pvsyst_artigo_rbens/` | Os relatórios dos dez casos de validação do artigo enviado à Revista Brasileira de Energia Solar, simulados no PVsyst 8.1.7 em 16/10/2026 |

## Como rodar no computador

É preciso ter o Python instalado (a plataforma foi feita com o Python 3.14). O sol dos municípios já vem na tabela `sol_municipios.csv`; a internet só é usada se ela faltar.

```
pip install -r requirements.txt
python app.py
```

Depois, abra `http://127.0.0.1:5000` no navegador. As páginas de explicação ficam em endereços curtos, como `http://127.0.0.1:5000/metodologia`.

## Como conferir

**As equações.** Este programa roda sem internet:

```
python teste/conferir_equacoes_3_3.py
```

Ele programa as equações de novo a partir do texto, sem chamar o motor, e compara os dois em 31.488 simulações, em toda a faixa residencial de consumo. Depois introduz 14 erros de propósito no motor, um de cada vez, para provar que a conferência percebe cada um. O resultado esperado é **0 divergências** e **14 de 14 erros detectados**. A saída está em `teste/resultado_da_conferencia.txt`.

**Os dados da ANEEL.** Depois de cada atualização, `python teste/conferir_dados_aneel.py` confere os dois arquivos e reprova valor que mudou sem vigência nova.

**Os municípios.** `python teste/conferir_cidades.py` compara a lista com a do IBGE e roda os cinco casos de validação com o Nominatim e a NASA POWER de verdade. Precisa de internet e leva alguns minutos.

## Atualização automática do Fio B

O Fio B muda quando a ANEEL aprova o reajuste de cada distribuidora, e a ANEEL só publica o valor novo poucos dias antes de ele valer. Por isso não dá para saber o valor com antecedência. O que dá para fazer é buscar logo depois que ele sai.

Duas vezes por semana, a tarefa `.github/workflows/atualizar-fio-b.yml` roda o `atualizar_dados_aneel.py` num computador do GitHub. Se algum valor mudou e todas as conferências passaram, ela grava os arquivos novos no repositório, e o site é republicado sozinho. Se alguma coisa der errado, nada é gravado e o site continua com os valores anteriores. A tela de resultado avisa quando a vigência de um valor terminou.

## Renovação da tabela de sol

A NASA atualiza de tempos em tempos o período das médias de sol (em 2026 passou de 2001-2020 para 2001-2025). Uma vez por ano (1º de março), ou a qualquer hora pelo botão "Run workflow" da aba Actions, a tarefa `.github/workflows/renovar-tabela-sol.yml` monta a tabela de novo e a compara com a atual (`teste/comparar_tabela_sol.py`). Se nada mudou, nada é gravado. Se algo mudou, a tabela nova vai para um ramo separado e a tarefa abre um aviso no repositório: como a tabela muda o número de painéis, ela só chega ao site depois da conferência completa do motor e da atualização dos textos que citam o período.

## Banco opcional e contador de acessos

Sem configuração nenhuma, o site funciona sozinho. Quando existe a variável de ambiente `DATABASE_URL`, com o endereço de um banco Postgres, ele passa a usar o banco para duas coisas:

- **Memória** das coordenadas e do sol de cada município já consultado, para não repetir a consulta ao Nominatim e à NASA (só usada se a tabela de sol faltar). Essa memória é privada e não é publicada.
- **Contador de acessos**: quantas vezes cada página foi aberta por dia, e quantas simulações foram feitas em cada estado. Não guarda endereço IP, cookie, navegador, município nem os valores digitados. Conta acessos, não pessoas, e o número é aproximado.

No servidor, o site roda com `gunicorn app:app --workers 1 --timeout 60`, com o registro de acessos do gunicorn desligado.

## Correspondência das equações

A numeração abaixo é a do artigo do TCC. Os comentários do código usam a numeração do desenvolvimento, anterior ao artigo.

| No artigo do TCC | No código | Função |
|---|---|---|
| 1 – HSP média anual | Equação 1 | `hsp_medio_anual()` |
| 2 – Tarifa | Equação 6 | `tarifa_total()` |
| 3 – Parcela do Fio B e valor economizado | Equação 7 | `valor_economizado_por_kwh()` |
| 4 – Consumo compensável | Equação 2a | `compensavel_do_mes()`, `consumo_compensavel_do_ano()`, `consumo_alvo_dimensionamento()` |
| 5 – Energia diária e potência teórica | Equações 2 e 3 | `energia_diaria()`, `potencia_sistema_teorica()` |
| 6 – Número de módulos | Equação 4 | `numero_paineis()`, `potencia_instalada()` |
| 7 – Potência do inversor | Equação 10 | `potencia_inversor()`, `potencia_inversor_comercial()` |
| 8 – Geração | Equação 5 | `geracao_estimada()` |
| 9 – Energia compensada e economia anual | Equações 8a e 8b | `energia_compensavel_anual()`, `economia_anual_estimada()` |
| 10 – Custo | (curva da Greener) | `custo_sistema_greener()` |
| 11 – Payback simples (TCC) | Equação 9 | `payback_meses()` |
| (só no site) – Retorno mês a mês, com manutenção e troca do inversor | – | `retorno_mes_a_mes()` |
| (só no site) – 25 anos, TIR, VPL e pior caso de 2029 | – | `indicadores_longo_prazo()`, `tir_real_anual()`, `cobranca_maxima_pos_2029()` |
| 12 – Correção pela temperatura | (verificação elétrica) | `voc_na_temperatura_minima()`, `vmp_na_temperatura_maxima()`, `isc_na_temperatura_maxima()` |

## Dados e créditos

- **Irradiação solar:** The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division.
- **Localização das sedes, para escolher o quadrado de sol:** Fonte: IBGE/DGC. Base Cartográfica Contínua do Brasil, escala 1:250.000 - BC250 (as coordenadas do IBGE não são publicadas na tabela); municipios-brasileiros (licença MIT); Wikidata (CC0).
- **Coordenadas, se a tabela de sol faltar:** Nominatim, com dados © OpenStreetMap contributors, disponíveis sob a Open Database License (ODbL): https://www.openstreetmap.org/copyright
- **Fio B e distribuidora de cada município:** ANEEL, Portal de Dados Abertos (conjuntos "Componentes Tarifárias", "IndQual Município" e "Indicadores Coletivos de Continuidade"), sob a Open Database License (ODbL) 1.0. Valores sem impostos. Os arquivos que vêm desses dados e a licença deles estão em `dados-ANEEL-LICENCA.txt`.
- **Lista de municípios:** códigos e nomes conferidos com a lista oficial do IBGE. Origem e licença em `static/municipios-LICENCA.txt`.
- **Preços:** Greener, Estudo Estratégico – Mercado Fotovoltaico, março de 2026 (preços de janeiro de 2026).
- **Módulos e inversores:** folhas de dados dos fabricantes.
- **Fontes tipográficas:** Inter e Sora, sob a SIL Open Font License (`static/fonts/`).

## Licença

Copyright © 2026 Brenda Morel Bueno Ferreira

O código é software livre: você pode redistribuí-lo e modificá-lo sob os termos da GNU Affero General Public License, versão 3 ou (a seu critério) qualquer versão posterior, conforme publicada pela Free Software Foundation. O texto completo está no arquivo LICENSE. Os arquivos de dados da ANEEL listados em `dados-ANEEL-LICENCA.txt` continuam sob a ODbL 1.0.

Este programa é distribuído na esperança de ser útil, mas SEM NENHUMA GARANTIA, nem mesmo a garantia implícita de COMERCIABILIDADE ou de ADEQUAÇÃO A UM DETERMINADO FIM.
