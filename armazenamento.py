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
armazenamento.py - banco Postgres OPCIONAL (Neon), para a memoria e o contador
Fase 2 pos-TCC, itens 2.3 e 2.7 (decisao da aluna em 03/10/2026).

PARA QUE SERVE
No Render gratis o disco e apagado quando o site "dorme" (15 min sem acesso),
reinicia ou e republicado (render.com/docs/free). Com isso, a memoria de
cidades (geocoding.py) e de sol (nasa_power.py), que hoje fica em cache/,
recomecaria vazia a cada vez - e a politica do Nominatim pede "Results must be
cached on your side". Este modulo guarda a mesma memoria num banco de dados
de fora (Postgres gratis do Neon), que nao some, e guarda tambem o CONTADOR
de acessos (contador.py).

QUANDO ELE LIGA
So quando existe a variavel de ambiente DATABASE_URL (o "endereco do banco",
guardado como segredo no painel do Render - NUNCA no codigo nem no GitHub).
Sem ela (no PC da aluna e nos testes), nada aqui faz nada, e a plataforma
funciona EXATAMENTE como antes: memoria em arquivo, contador desligado.

REGRA DE OURO: O BANCO NUNCA DERRUBA NEM SEGURA O SITE
  - cada operacao tem no maximo ~7 s (4 s para conectar + 3 s de comando);
  - na primeira falha, o site para de tentar o banco por PAUSA_APOS_FALHA_S
    (mesma ideia da pausa do Nominatim depois de um aviso 429). Motivo, com
    conta: o gunicorn no Render roda com --timeout 60. O pior caso de uma
    simulacao ja e 20 s (Nominatim) + 20 s (NASA POWER). Sem a pausa, quatro
    operacoes lentas no banco (ler e gravar, cidade e sol) somariam mais
    4 x 7 s = 28 s e estourariam o limite; com a pausa, no maximo uma operacao
    espera (20 + 20 + 7 = 47 s);
  - nao ha trava entre as operacoes: cada uma tem a sua conexao, entao a
    gravacao do contador (em segundo plano) nunca faz uma simulacao esperar;
  - qualquer falha devolve "nao achei" / "nao gravei", e quem chamou segue
    pelo caminho de sempre (arquivo, Nominatim, NASA POWER).

O QUE O BANCO GUARDA (e o que NAO guarda)
  memoria:  as MESMAS fichas que vao para cache/geocodificacao.json e
            cache/nasa_power.json, gravadas como texto JSON identico. As
            regras de uso (versao da regra de escolha da cidade, validade de
            1 ano do sol, recusa do -999) continuam nos modulos de origem -
            aqui e so outro lugar para a mesma ficha. Privado: nao e
            publicado (o .gitignore ja deixa cache/ de fora; o banco nem esta
            no repositorio).
  contagem: por DIA, quantas vezes cada pagina abriu, quantas simulacoes
            foram pedidas por ESTADO (com e sem resultado) e quantos acessos
            de robos (por nome do robo). NUNCA: IP, cidade, valores digitados,
            o texto do navegador, cookie. Ver contador.py.

UMA CONEXAO POR OPERACAO (de proposito)
O Neon desliga o banco depois de 5 minutos sem uso, e uma conexao guardada
morreria junto. Como o banco so e usado quando a memoria do arquivo nao tem a
cidade/o sol, e o contador grava de 10 em 10 minutos, abrir uma conexao nova
a cada vez e simples e barato. Acordar o banco "typically takes a few hundred
milliseconds" (neon.com/docs/connect/connection-latency, lida em 03/10/2026).
Use o endereco SEM pooler ("direct connection") do painel do Neon.

Tabelas (criadas sozinhas na primeira conexao, se nao existirem):
  memoria(tipo, chave, registro, gravado_em)
  contagem(dia, categoria, nome, total)
"""
import json
import os
import time

# O endereco do banco. Lido uma vez, quando o modulo e carregado.
URL_BANCO = (os.environ.get("DATABASE_URL") or "").strip()

TEMPO_LIMITE_CONEXAO_S = 4  # para abrir a conexao (acordar o Neon leva
                            # "a few hundred milliseconds")
TEMPO_LIMITE_COMANDO_S = 3  # para cada comando, cancelado pelo proprio banco
PAUSA_APOS_FALHA_S = 300    # 5 minutos sem tentar o banco depois de uma falha

TABELAS_SQL = """
CREATE TABLE IF NOT EXISTS memoria (
    tipo        text        NOT NULL,   -- 'cidade' ou 'sol'
    chave       text        NOT NULL,   -- codigo IBGE / "latitude,longitude"
    registro    text        NOT NULL,   -- a ficha, em JSON, igual a do arquivo
    gravado_em  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tipo, chave)
);
CREATE TABLE IF NOT EXISTS contagem (
    dia        date    NOT NULL,        -- dia no horario de Brasilia
    categoria  text    NOT NULL,        -- ver contador.py
    nome       text    NOT NULL,        -- pagina, sigla do estado ou robo
    total      integer NOT NULL,
    PRIMARY KEY (dia, categoria, nome)
);
"""

_tabelas_conferidas = False
_pausado_ate = 0.0

# Para auditoria e para a prova: o que aconteceu na ultima falha.
ULTIMA_FALHA = None


def ligado():
    """True quando existe o endereco do banco (DATABASE_URL)."""
    return bool(URL_BANCO)


def disponivel():
    """Ligado e fora da pausa de 5 minutos."""
    return ligado() and time.monotonic() >= _pausado_ate


def _registrar_falha(erro):
    global _pausado_ate, ULTIMA_FALHA
    _pausado_ate = time.monotonic() + PAUSA_APOS_FALHA_S
    ULTIMA_FALHA = f"{type(erro).__name__}: {erro}"[:300]


def _executar(funcao):
    """
    Abre uma conexao, roda funcao(cursor) e fecha. Devolve (True, resultado)
    ou (False, None) - nunca levanta excecao para quem chamou.
    """
    global _tabelas_conferidas
    if not disponivel():
        return False, None
    try:
        import psycopg      # so precisa estar instalado onde o banco liga
        with psycopg.connect(
            URL_BANCO,
            connect_timeout=TEMPO_LIMITE_CONEXAO_S,
            autocommit=True,
            application_name="quantos-paineis",
            # se a rede travar no meio, o sistema desiste em poucos segundos
            # em vez de esperar indefinidamente
            tcp_user_timeout=TEMPO_LIMITE_COMANDO_S * 1000,
            keepalives=1, keepalives_idle=TEMPO_LIMITE_COMANDO_S,
            keepalives_interval=1, keepalives_count=2,
        ) as conexao:
            with conexao.cursor() as cursor:
                # o proprio banco cancela comando que passar do limite
                cursor.execute(f"SET statement_timeout = {TEMPO_LIMITE_COMANDO_S * 1000}")
                if not _tabelas_conferidas:
                    cursor.execute(TABELAS_SQL)
                    _tabelas_conferidas = True
                return True, funcao(cursor)
    except Exception as erro:       # qualquer falha: o site segue sem o banco
        _registrar_falha(erro)
        return False, None


# =======================================================================
# MEMORIA (usada pelo geocoding.py e pelo nasa_power.py)
# =======================================================================
def ler_memoria(tipo, chave):
    """A ficha guardada (dicionario) ou None - se nao houver, se o banco
    estiver desligado, em pausa ou falhar."""
    def ler(cursor):
        cursor.execute("SELECT registro FROM memoria WHERE tipo = %s AND chave = %s",
                       (tipo, str(chave)))
        linha = cursor.fetchone()
        return linha[0] if linha else None
    ok, texto = _executar(ler)
    if not ok or texto is None:
        return None
    try:
        registro = json.loads(texto)
    except ValueError:
        return None
    return registro if isinstance(registro, dict) else None


def gravar_memoria(tipo, chave, registro):
    """Grava (ou troca) a ficha. Devolve True se gravou."""
    texto = json.dumps(registro, ensure_ascii=False)

    def gravar(cursor):
        cursor.execute(
            "INSERT INTO memoria (tipo, chave, registro) VALUES (%s, %s, %s) "
            "ON CONFLICT (tipo, chave) DO UPDATE "
            "SET registro = EXCLUDED.registro, gravado_em = now()",
            (tipo, str(chave), texto))
        return True
    ok, _ = _executar(gravar)
    return ok


# =======================================================================
# CONTAGEM (usada pelo contador.py)
# =======================================================================
def somar_contagens(linhas):
    """
    linhas: lista de (dia, categoria, nome, quantidade). Soma tudo de uma
    vez, numa conexao so. Devolve True se gravou.
    """
    if not linhas:
        return True

    def somar(cursor):
        # tudo ou nada: se cair no meio, nada foi somado, e o contador.py
        # manda de novo na proxima vez sem contar nada em dobro
        with cursor.connection.transaction():
            cursor.executemany(
                "INSERT INTO contagem (dia, categoria, nome, total) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (dia, categoria, nome) DO UPDATE "
                "SET total = contagem.total + EXCLUDED.total",
                linhas)
        return True
    ok, _ = _executar(somar)
    return ok
