#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
provedor.py
-----------
Modulo compartilhado pelos scripts do projeto. Centraliza:
  - leitura do .env
  - selecao do provedor (yahoo ou gmail)
  - servidor IMAP e nomes de pastas (Lixeira/Spam) de cada provedor
  - login IMAP

Selecao do provedor, em ordem de prioridade:
  1) argumento --provedor=yahoo|gmail
  2) variavel PROVEDOR no .env
  3) padrao: yahoo
"""

import getpass
import imaplib
import os
import sys

# Configuracao por provedor: servidor IMAP, porta e nomes de pastas.
PROVEDORES = {
    "yahoo": {
        "servidor": "imap.mail.yahoo.com",
        "porta": 993,
        "trash": "Trash",
        "spam": "Bulk Mail",
        "prefixo_env": "YAHOO",
    },
    "gmail": {
        "servidor": "imap.gmail.com",
        "porta": 993,
        # No Gmail as pastas ficam sob [Gmail].
        "trash": "[Gmail]/Trash",
        "spam": "[Gmail]/Spam",
        "prefixo_env": "GMAIL",
    },
}


def carregar_env(caminho=".env"):
    """Le um .env simples (CHAVE=VALOR) sem dependencias externas."""
    valores = {}
    if not os.path.exists(caminho):
        return valores
    with open(caminho, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def resolver_provedor(flags=None, env=None):
    """
    Decide o provedor com prioridade:
      1) --provedor=yahoo|gmail nas flags
      2) PROVEDOR no .env
      3) 'yahoo'
    Retorna (nome_provedor, origem).
    """
    flags = flags or []
    env = env if env is not None else carregar_env()

    for arg in flags:
        if arg.startswith("--provedor="):
            nome = arg.split("=", 1)[1].strip().lower()
            if nome in PROVEDORES:
                return nome, "argumento --provedor"
            print(f"[AVISO] Provedor invalido ('{nome}'). Valores: yahoo, gmail.")

    nome_env = (env.get("PROVEDOR") or "").strip().lower()
    if nome_env in PROVEDORES:
        return nome_env, ".env (PROVEDOR)"

    return "yahoo", "padrao"


def config_provedor(nome):
    """Retorna o dicionario de configuracao do provedor."""
    return PROVEDORES[nome]


def obter_credenciais(nome, env):
    """
    Le email e app password do provedor a partir do .env / ambiente.
    Faz fallback para prompt se algo estiver faltando.
    """
    prefixo = PROVEDORES[nome]["prefixo_env"]
    email_usuario = (
        env.get(f"{prefixo}_EMAIL")
        or os.environ.get(f"{prefixo}_EMAIL", "")
    )
    senha = (
        env.get(f"{prefixo}_APP_PASSWORD")
        or os.environ.get(f"{prefixo}_APP_PASSWORD", "")
    )

    if not email_usuario:
        email_usuario = input(f"Email {nome}: ").strip()
    if not senha:
        print("App Password (nao a senha normal da conta).")
        senha = getpass.getpass("App Password: ").strip()

    return email_usuario, senha


def _entre_aspas(nome):
    """Coloca o nome da pasta entre aspas se contiver espacos ou colchetes."""
    if any(c in nome for c in ' []'):
        return '"' + nome + '"'
    return nome


def detectar_pasta_por_flag(conexao, flag):
    """
    Procura entre as pastas da conta a que tem a flag especial informada
    (ex: '\\Trash', '\\Junk', '\\All'). Retorna o nome da pasta ou None.

    Isso torna a deteccao independente do idioma da conta: no Gmail em
    portugues a Lixeira e '[Gmail]/Lixeira', mas a flag \\Trash e sempre
    a mesma.
    """
    typ, pastas = conexao.list()
    if typ != "OK" or not pastas:
        return None
    alvo = flag.lower()
    for item in pastas:
        linha = item.decode(errors="replace")
        # Formato: (flags) "sep" "nome-da-pasta"
        if alvo in linha.lower():
            # O nome da pasta e o ultimo campo entre aspas.
            partes = linha.split(' "')
            nome = partes[-1].strip().strip('"')
            if nome:
                return nome
    return None


def buscar_uids(conexao, criterio):
    """
    Executa uma busca por UID e retorna a lista de UIDs (bytes).
    'criterio' e uma lista de argumentos IMAP, ex: ["FROM", "x@y.com"].
    Trabalhar por UID (e nao por numero de sequencia) garante que o move
    depois afete exatamente as mesmas mensagens.
    """
    typ, dados = conexao.uid("SEARCH", None, *criterio)
    if typ != "OK":
        return None
    return dados[0].split()


def mover_para_pasta(conexao, uids, pasta_destino):
    """
    Move mensagens (lista de UIDs em bytes) para 'pasta_destino'.

    Estrategia:
      1) UID MOVE  -> ideal para Gmail e servidores modernos (extensao MOVE).
      2) fallback: UID COPY + UID STORE \\Deleted + EXPUNGE -> funciona no Yahoo.

    Como tudo e feito por UID, os mesmos UIDs da busca sao os movidos, sem
    risco de afetar a mensagem errada.

    Retorna (ok: bool, metodo: str, erro: str).
    """
    if not uids:
        return False, "vazio", ""

    uid_lista = b",".join(uids).decode()
    destino = _entre_aspas(pasta_destino)
    erros = []

    # 1) Tenta UID MOVE (API publica do imaplib: conexao.uid("MOVE", ...)).
    try:
        typ, dados = conexao.uid("MOVE", uid_lista, destino)
        if typ == "OK":
            return True, "MOVE", ""
        erros.append(f"MOVE={typ}:{dados}")
    except (imaplib.IMAP4.error, imaplib.IMAP4.abort) as e:
        erros.append(f"MOVE erro: {e}")

    # 2) Fallback: UID COPY + marca \Deleted + EXPUNGE.
    try:
        typ, dados = conexao.uid("COPY", uid_lista, destino)
        if typ == "OK":
            conexao.uid("STORE", uid_lista, "+FLAGS", "(\\Deleted)")
            conexao.expunge()
            return True, "COPY", ""
        erros.append(f"COPY={typ}:{dados}")
    except (imaplib.IMAP4.error, imaplib.IMAP4.abort) as e:
        erros.append(f"COPY erro: {e}")

    return False, "falhou", " | ".join(erros)


def conectar(flags=None):
    """
    Resolve o provedor, faz login IMAP e retorna (conexao, nome_provedor, config).
    Encerra o programa em caso de falha de login.
    """
    env = carregar_env()
    nome, origem = resolver_provedor(flags, env)
    cfg = dict(config_provedor(nome))  # copia, para nao mutar o global
    email_usuario, senha = obter_credenciais(nome, env)

    print(f"Provedor: {nome} (origem: {origem}) - {cfg['servidor']}")
    try:
        conexao = imaplib.IMAP4_SSL(cfg["servidor"], cfg["porta"])
        conexao.login(email_usuario, senha)
        print(f"[OK] Conectado como {email_usuario}.")

        # Detecta as pastas reais pela flag especial (independe do idioma).
        # Ex: no Gmail em portugues a Lixeira e '[Gmail]/Lixeira', mas a
        # flag \\Trash e sempre a mesma.
        trash_detectada = detectar_pasta_por_flag(conexao, "\\Trash")
        if trash_detectada:
            cfg["trash"] = trash_detectada
        spam_detectada = detectar_pasta_por_flag(conexao, "\\Junk")
        if spam_detectada:
            cfg["spam"] = spam_detectada
        print(f"Lixeira: {cfg['trash']}\n")

        return conexao, nome, cfg
    except imaplib.IMAP4.error as erro:
        print(f"[ERRO] Falha no login: {erro}")
        print("Dicas:")
        print("  - Use uma App Password, nao a senha normal.")
        if nome == "gmail":
            print("  - No Gmail: ative a verificacao em 2 etapas e habilite o IMAP.")
        sys.exit(1)
