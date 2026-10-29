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

import math

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for
from simulacao import simular

app = Flask(__name__)

# Ordem dos meses, igual a usada no simulacao.py. Os campos do modo
# avancado no index.html se chamam consumo_jan, consumo_fev, etc.
NOMES_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
               "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


# =====================================================================
# ITEM 41 DO BACKLOG (07/10/2026) - LEITURA SEGURA DOS CAMPOS NUMERICOS
# =====================================================================
# O PROBLEMA, MEDIDO (157 envios do formulario com valores estranhos, por
# fora do navegador): 22 derrubavam o site com erro 500 e 4 recebiam a
# pagina "Bad Request" do Flask, em ingles. Exemplos: letras, vazio ou
# virgula no valor da conta (float() direto); "nan" e "inf", que o
# float() do Python aceita como numero e que estouravam no math.ceil do
# calculo.py; numero gigante (1e308), que vira infinito no meio da conta.
# Outros nao caiam mas mostravam coisa errada: "inf" e "nan" no lugar dos
# numeros do resultado, ou um motivo falso ("nao chega a se pagar").
# Pelo navegador nada disso acontece (campos numericos e obrigatorios), mas
# publicado o site recebe robo, e cada erro 500 gravava o valor no log.
#
# A CORRECAO: uma funcao so, usada por TODOS os campos numericos. Para
# qualquer valor que o codigo antigo ja aceitava (finito e ate o limite
# abaixo), o numero lido e EXATAMENTE o mesmo de antes - a conversao
# continua sendo float() com a virgula trocada por ponto. Provado por teste
# diferencial (claude/item41_rascunho/diferencial.py): os mesmos argumentos
# chegam ao simular(). O calculo.py e o simulacao.py NAO foram tocados.
#
# LIMITE TECNICO de 1 milhao (decisao da aluna, 07/10/2026): NAO e limite de
# engenharia nem tem fonte - nenhuma conta de casa chega perto, em R$ ou em
# kWh, e acima de ~1.600 kWh/mes o proprio motor ja avisa que o sistema sai
# da faixa residencial. Ele so impede que um numero absurdo estoure a conta.
LIMITE_TECNICO = 1_000_000


def ler_numero(bruto):
    """
    Le um campo numerico do formulario. Devolve (valor, problema):
    problema e None quando deu certo, ou "vazio", "invalido" ou "grande".
    Aceita virgula ou ponto como separador decimal, como os outros campos ja
    aceitavam. Recusa nan e infinito. O sinal NAO e conferido aqui: cada
    campo diz a sua regra (maior que zero; nao negativo).
    """
    texto = (bruto or "").strip()
    if texto == "":
        return None, "vazio"
    try:
        valor = float(texto.replace(",", "."))
    except ValueError:
        return None, "invalido"
    if not math.isfinite(valor):
        return None, "invalido"
    if valor > LIMITE_TECNICO:
        return None, "grande"
    return valor, None


def _tela_de_erro(mensagem):
    """A mesma tela de erro que o resto deste arquivo ja usa."""
    return render_template("resultado.html", resultado=None, erro=mensagem)


def ler_consumo_mensal(formulario):
    """
    Le os 12 campos opcionais do modo avancado (historico da fatura).

    Regra: ou os doze, ou nenhum. Meio preenchido nao serve - a media
    sairia errada e o grafico mes a mes mentiria. Devolve (dicionario, erro):
    o dicionario e None quando a pessoa nao usou o modo avancado.
    """
    valores = {}
    vazios = []

    for mes in NOMES_MESES:
        # item 41 (07/10/2026): ler_numero() no lugar do float() direto -
        # "nan", "inf" e 1e308 derrubavam o site com erro 500.
        valor, problema = ler_numero(formulario.get("consumo_" + mes.lower()))
        if problema == "vazio":
            vazios.append(mes)
            continue
        if problema == "invalido":
            # 01/10/2026 (passo 6): as mensagens que a PESSOA LE passaram a
            # ter acentuacao correta (decisao da aluna). Os comentarios e os
            # nomes de variavel do codigo seguem sem acento, como no resto
            # do projeto - mexer neles nao melhora nada e muda muito arquivo.
            return None, "O consumo de " + mes + " não parece um número válido."
        if problema == "grande":
            return None, ("O consumo de " + mes + " parece grande demais para uma "
                          "casa. Confira se digitou certo.")
        if valor <= 0:
            return None, "O consumo de " + mes + " precisa ser maior que zero."
        valores[mes] = valor

    if len(vazios) == 12:
        return None, None          # modo media, o padrao
    if vazios:
        return None, ("Para usar o consumo mês a mês, preencha os 12 meses. "
                      "Faltou: " + ", ".join(vazios) + ". Se preferir, apague "
                      "todos e informe apenas o consumo médio.")
    return valores, None


@app.route("/")
def pagina_inicial():
    return render_template("index.html")


@app.route("/simular", methods=["POST"])
def rota_simular():
    # item 41 (07/10/2026): .get() no lugar de [] - campo ausente dava a
    # pagina "Bad Request" do Flask, em ingles - e ler_numero() no lugar do
    # float() direto, que dava erro 500 com letras, vazio ou virgula.
    cidade = (request.form.get("cidade") or "").strip()
    if not cidade:
        return _tela_de_erro("Falta dizer a cidade. Digite o nome e escolha a "
                             "sua cidade na lista.")
    fatura, problema = ler_numero(request.form.get("fatura"))
    if problema == "vazio":
        return _tela_de_erro("Falta o valor total da conta de luz, em reais.")
    if problema == "invalido":
        return _tela_de_erro("O valor da conta não parece um número válido. Informe "
                             "apenas o valor em reais, por exemplo 225,50.")
    if problema == "grande":
        return _tela_de_erro("O valor da conta parece grande demais para uma conta "
                             "de casa. Confira se digitou certo.")
    if fatura <= 0:
        return _tela_de_erro("O valor da conta precisa ser maior que zero.")
    # kWh da MESMA conta de onde veio o valor em R$. E o par que define a
    # tarifa (Equacao 6). Antes a tarifa saia de "R$ de um mes qualquer
    # dividido pela media do ano", o que produzia um erro igual ao quanto
    # aquele mes fugiu da media - e sempre na direcao otimista quando a
    # pessoa pegava uma conta de mes caro.
    # item 41 (07/10/2026): em branco continua valendo None, como antes (o
    # motor usa a media). Zero ou negativo, que antes era IGNORADO CALADO (o
    # motor usava a media sem avisar), passou a ter mensagem - decisao da
    # aluna. Pelo navegador nao chega aqui: o campo exige valor maior que 0.
    consumo_da_fatura, problema = ler_numero(request.form.get("consumo_fatura"))
    if problema == "invalido":
        return _tela_de_erro("O consumo desta conta não parece um número válido.")
    if problema == "grande":
        return _tela_de_erro("O consumo desta conta parece grande demais para uma "
                             "casa. Confira se digitou certo.")
    if consumo_da_fatura is not None and consumo_da_fatura <= 0:
        return _tela_de_erro("O consumo desta conta precisa ser maior que zero.")
    # CORRECAO T15/T12 (15/09/2026): o campo "painel" deixou de ser lido
    # aqui. A plataforma passou a ESCOLHER o modulo, porque a verificacao
    # eletrica do T15 mostrou que essa nao e uma escolha de preferencia: os
    # modulos de celula 210 mm reprovam na verificacao de seguranca com o
    # inversor de corrente baixa em qualquer porte, e so passam a ter par
    # valido acima de cerca de 450 kWh/mes. Oferecer ao leigo uma opcao que
    # a norma reprova e oferecer escolha falsa - o mesmo defeito que o T5
    # removeu do seletor de inversor.
    # Mesma ordem de passos do T5: o back-end para de LER o campo primeiro,
    # e so depois o campo sai do index.html. Ao contrario do "inversor", o
    # "painel" era lido com colchete, entao tirar da tela antes derrubaria
    # o site com erro 400 na primeira simulacao.
    # CORRECAO T5 (14/09/2026): o campo "inversor" deixou de ser lido aqui e
    # de ser repassado ao motor. Ele era um seletor morto desde o T1: com o
    # custo vindo da curva Greener por porte, o preco por kW do inversor
    # deixou de ser usado, e escolher Economico/Intermediario/Premium
    # devolvia resultado identico. A POTENCIA do inversor continua sendo
    # calculada (kWp x FDI 0,80) e encaixada na grade comercial (T4) - o que
    # saiu foi a escolha falsa pedida ao usuario, nao o calculo.

    # Tipo de ligacao da casa (correcao T7, 14/09/2026). E o que define o
    # custo de disponibilidade: o minimo que a distribuidora fatura todo
    # mes mesmo de quem tem paineis (art. 291 da REN ANEEL 1.000/2021).
    # Usamos .get() e nao [] de proposito: o campo e OPCIONAL. Quando vier
    # vazio, ou com a opcao "nao sei", o motor aplica a premissa bifasica
    # e devolve tipo_ligacao_informado=False, para a tela declarar que
    # aquele resultado nasceu de uma premissa e nao de um dado da pessoa.
    tipo_ligacao = (request.form.get("ligacao") or "").strip()

    # Cobrancas da conta que NAO sao energia (passo 6, 01/10/2026). Campo
    # OPCIONAL: iluminacao publica, taxa de lixo, multa, juros e
    # parcelamento. Em branco, o calculo e o mesmo de antes. O motor desconta
    # esse valor antes de dividir pelo consumo (Equacao 6) - a explicacao
    # completa, com as fontes, esta no simulacao.py.
    # item 41 (07/10/2026): ler_numero() - "nan" passava e virava um motivo
    # falso na tela; "inf" e 1e308 apareciam como numero na mensagem.
    cobrancas_nao_energia, problema = ler_numero(request.form.get("cobrancas"))
    if problema != "vazio":
        # mesma regra dos outros campos: o formulario manda numero com
        # ponto (input type="number"), e a virgula e aceita por garantia
        if problema == "invalido":
            return render_template(
                "resultado.html", resultado=None,
                erro=("O valor das cobranças que não são energia não parece um "
                      "número válido. Informe apenas o valor em reais, por "
                      "exemplo 12,50 — ou deixe o campo em branco."))
        if problema == "grande":
            return _tela_de_erro("O valor das cobranças que não são energia parece "
                                 "grande demais para uma conta de casa. Confira se "
                                 "digitou certo.")
        if cobrancas_nao_energia < 0:
            return render_template(
                "resultado.html", resultado=None,
                erro="O valor das cobranças que não são energia não pode ser negativo.")

    # Modo avancado (opcional): historico de 12 meses e mes da fatura.
    consumo_por_mes, erro_consumo = ler_consumo_mensal(request.form)
    if erro_consumo:
        return render_template("resultado.html", erro=erro_consumo, resultado=None)

    # Dois caminhos validos para o consumo, e a pessoa escolhe um:
    # (a) digitar a media mensal; (b) preencher os 12 meses do historico e
    # deixar a plataforma calcular a media. O campo da media NAO e
    # obrigatorio - exigir os dois seria pedir a mesma informacao duas vezes.
    # item 41 (07/10/2026): ler_numero() - "nan", "inf" e 1e308 davam erro 500.
    consumo_lido, problema = ler_numero(request.form.get("consumo"))
    if consumo_por_mes:
        consumo = sum(consumo_por_mes.values()) / 12
    elif problema != "vazio":
        if problema == "invalido":
            return render_template("resultado.html", resultado=None,
                                   erro="O consumo médio não parece um número válido.")
        if problema == "grande":
            return _tela_de_erro("O consumo médio parece grande demais para uma "
                                 "casa. Confira se digitou certo.")
        consumo = consumo_lido
        if consumo <= 0:
            return render_template("resultado.html", resultado=None,
                                   erro="O consumo médio precisa ser maior que zero.")
    else:
        return render_template("resultado.html", resultado=None,
                               erro=("Falta dizer quanto você consome. Informe o consumo "
                                     "médio mensal, ou preencha os 12 meses do histórico "
                                     "da sua conta e nós calculamos a média para você."))

    # Distribuidora escolhida pela pessoa (passo 7, 02/10/2026). Campo
    # OPCIONAL: a tela so o mostra quando o municipio tem mais de uma
    # distribuidora, e com a opcao "nao sei". Vem o CNPJ, que e a chave do
    # Fio B; vazio ou desconhecido, o motor aplica a regra do municipio.
    distribuidora_cnpj = (request.form.get("distribuidora") or "").strip()

    resultado = simular(
        cidade=cidade,
        consumo_medio_kwh=consumo,
        valor_fatura_reais=fatura,
        consumo_da_fatura_kwh=consumo_da_fatura,
        consumo_por_mes_kwh=consumo_por_mes,
        tipo_ligacao=tipo_ligacao,
        cobrancas_nao_energia_reais=cobrancas_nao_energia,
        distribuidora_cnpj=distribuidora_cnpj,
    )

    if "erro" in resultado:
        # PASSO 6 (01/10/2026): dois campos novos, que SO aparecem quando um
        # servico de fora (OpenStreetMap ou NASA POWER) nao respondeu:
        # servico_indisponivel troca o titulo da tela (nao e uma conclusao
        # sobre o sistema, e uma indisponibilidade temporaria) e
        # detalhe_tecnico e a linha discreta de auditoria. Nos outros erros
        # os dois vem vazios e a tela fica exatamente como era.
        return render_template("resultado.html", erro=resultado["erro"],
                               servico_indisponivel=resultado.get("erro_servico_indisponivel", False),
                               # (revisao geral, parte 3, 07/10/2026) o motor ja marca "inviavel"
                               # quando os dados estao certos mas o sistema nao e recomendado; o
                               # titulo da tela passa a separar isso de erro de digitacao.
                               inviavel=resultado.get("inviavel", False),
                               detalhe_tecnico=resultado.get("erro_detalhe_tecnico"),
                               resultado=None)

    return render_template(
        "resultado.html",
        resultado=resultado,
        erro=None,
        fatura_informada=fatura,
    )


# =====================================================================
# FASE 1, PASSO 8 (02/10/2026) - ENDERECOS LIMPOS DAS PAGINAS DE EXPLICACAO
# =====================================================================
# Decisao da aluna: a pagina de metodologia abre em /metodologia, e nao em
# /static/metodologia.html. Os arquivos CONTINUAM em static/ (nada mudou de
# nome); so o endereco que a pessoa ve e que ficou limpo. Feito ANTES de
# publicar de proposito: depois que o site estiver no ar e os enderecos
# estiverem em links e no artigo, trocar quebraria tudo o que ja foi citado.
#
# ESTE BLOCO NAO PASSA PELO CALCULO: nao chama simular() nem nada do
# calculo.py, e a rota /simular, acima, nao foi tocada.
#
# A LISTA E FECHADA: so estes nove nomes viram pagina. Qualquer outro
# endereco (/qualquercoisa) responde "pagina nao encontrada" (404), como
# antes - a rota nunca serve um arquivo que nao esteja nesta lista.
PAGINAS = ("entenda", "economia", "equipamentos", "precisao", "metodologia",
           "limitacoes", "sobre", "contato", "apoie")


@app.route("/<nome>")
def pagina(nome):
    if nome not in PAGINAS:
        abort(404)
    return send_from_directory(app.static_folder, nome + ".html")


@app.before_request
def endereco_antigo_das_paginas():
    # Quem abrir o endereco antigo (/static/metodologia.html) e levado ao
    # novo (/metodologia), com o codigo 301 ("mudou de endereco para
    # sempre"). Assim cada pagina tem UM endereco so. Para os outros
    # arquivos de static/ (CSS, fontes, listas .json) nada muda.
    caminho = request.path
    if caminho.startswith("/static/") and caminho.endswith(".html"):
        nome = caminho[len("/static/"):-len(".html")]
        if nome in PAGINAS:
            return redirect(url_for("pagina", nome=nome), code=301)
    return None


# =====================================================================
# FASE 2, ITEM 2.3 (03/10/2026) - CONTADOR DE ACESSOS
# =====================================================================
# Conta, por dia, paginas abertas, simulacoes por ESTADO (com e sem
# resultado) e acessos de robos - sem cookie, sem IP, sem cidade, sem
# valores. So liga quando o banco esta configurado (DATABASE_URL); sem ele,
# esta linha nao faz nada. Detalhes em contador.py.
# ESTE BLOCO NAO PASSA PELO CALCULO: os ganchos ficam FORA de
# ler_consumo_mensal, pagina_inicial e rota_simular, que nao foram tocadas.
import contador  # noqa: E402 (fica aqui embaixo, junto do que ele usa)

contador.ligar(app, PAGINAS)


if __name__ == "__main__":
    app.run(debug=True)
