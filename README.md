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
- **Nove páginas de explicação.** Como funciona, economia, equipamentos e preços, precisão, metodologia, limitações, sobre, contato e apoie.
- **Atualização automática do Fio B** e **contador de acessos sem dado pessoal**, explicados mais abaixo.

## O que tem aqui

| Pasta ou arquivo | O que é |
|---|---|
| `calculo.py` | O motor de cálculo: as equações, a verificação elétrica e o catálogo de módulos e inversores |
| `simulacao.py` | Junta tudo numa função só, `simular()` |
| `geocoding.py` | Busca as coordenadas do município (Nominatim/OpenStreetMap) |
| `nasa_power.py` | Busca a irradiação solar de cada mês (NASA POWER) |
| `app.py`, `templates/`, `static/` | O site (Flask): o formulário, a tela de resultado e as páginas de explicação |
| `armazenamento.py`, `contador.py` | O banco opcional: memória de municípios e de sol, e o contador de acessos |
| `atualizar_dados_aneel.py` | Baixa os dados abertos da ANEEL e refaz os dois arquivos abaixo |
| `fio_b_por_distribuidora.csv` | Fio B de cada distribuidora, com vigência e resolução da ANEEL |
| `static/distribuidoras_por_municipio.json` | A distribuidora de cada município |
| `static/municipios.json` | A lista dos 5.571 municípios (origem em `static/municipios-LICENCA.txt`) |
| `fio_b_aneel_vigente_22-09-2026.csv`, `fio_b_aneel_conferencia_01-10-2026.csv` | Retratos do Fio B usados no TCC e numa conferência |
| `recalculo_fio_b.py` | Conferência feita para o TCC: o efeito, nos cinco casos, da troca do Fio B de R$ 0,20 pelo da ANEEL |
| `.github/workflows/atualizar-fio-b.yml` | A tarefa automática do Fio B |
| `teste/` | Os programas de conferência e os resultados deles |
| `resultados/plataforma/` | A tela de resultado dos cinco casos de validação do TCC, em PDF |
| `resultados/pvsyst/` | Os relatórios das simulações no PVsyst 8.1.5, com todos os parâmetros |

## Como rodar no computador

É preciso ter o Python instalado (a plataforma foi feita com o Python 3.14) e internet, porque as coordenadas e a irradiação são buscadas na hora.

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

## Banco opcional e contador de acessos

Sem configuração nenhuma, o site funciona sozinho. Quando existe a variável de ambiente `DATABASE_URL`, com o endereço de um banco Postgres, ele passa a usar o banco para duas coisas:

- **Memória** das coordenadas e do sol de cada município já consultado, para não repetir a consulta ao Nominatim e à NASA. Essa memória é privada e não é publicada.
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
| (só no site) – Retorno mês a mês | – | `retorno_mes_a_mes()` |
| 12 – Correção pela temperatura | (verificação elétrica) | `voc_na_temperatura_minima()`, `vmp_na_temperatura_maxima()`, `isc_na_temperatura_maxima()` |

## Dados e créditos

- **Irradiação solar:** The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division.
- **Coordenadas:** Nominatim, com dados © OpenStreetMap contributors, disponíveis sob a Open Database License (ODbL): https://www.openstreetmap.org/copyright
- **Fio B e distribuidora de cada município:** ANEEL, Portal de Dados Abertos (conjuntos "Componentes Tarifárias", "IndQual Município" e "Indicadores Coletivos de Continuidade"), sob a Open Database License (ODbL) 1.0. Valores sem impostos. Os arquivos que vêm desses dados e a licença deles estão em `dados-ANEEL-LICENCA.txt`.
- **Lista de municípios:** códigos e nomes conferidos com a lista oficial do IBGE. Origem e licença em `static/municipios-LICENCA.txt`.
- **Preços:** Greener, Estudo Estratégico – Mercado Fotovoltaico, março de 2026 (preços de janeiro de 2026).
- **Módulos e inversores:** folhas de dados dos fabricantes.
- **Fontes tipográficas:** Inter e Sora, sob a SIL Open Font License (`static/fonts/`).

## Licença

Copyright © 2026 Brenda Morel Bueno Ferreira

O código é software livre: você pode redistribuí-lo e modificá-lo sob os termos da GNU Affero General Public License, versão 3 ou (a seu critério) qualquer versão posterior, conforme publicada pela Free Software Foundation. O texto completo está no arquivo LICENSE. Os arquivos de dados da ANEEL listados em `dados-ANEEL-LICENCA.txt` continuam sob a ODbL 1.0.

Este programa é distribuído na esperança de ser útil, mas SEM NENHUMA GARANTIA, nem mesmo a garantia implícita de COMERCIABILIDADE ou de ADEQUAÇÃO A UM DETERMINADO FIM.
