#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpa_yahoo.py
--------------
Programa interativo para ajudar a excluir emails de uma conta Yahoo via IMAP.

IMPORTANTE (leia antes de usar):
  1. O Yahoo NAO aceita a senha normal da conta para acesso IMAP.
     Voce precisa gerar uma "App Password" (senha de aplicativo):
       Yahoo -> Account Info -> Account Security -> Generate app password
  2. Este script usa apenas a biblioteca padrao do Python (imaplib, email).
  3. Por seguranca, ele SEMPRE mostra os emails encontrados e pede
     confirmacao antes de mover qualquer coisa para a Lixeira.

Como funciona a exclusao no IMAP:
  - "Excluir" marca a mensagem com a flag \\Deleted e depois faz EXPUNGE.
  - No Yahoo, o mais seguro e mover os emails para a pasta Lixeira
    ("Trash"), que e o comportamento padrao deste script.
"""

import email
from email.header import decode_header
import sys

import provedor

# Nome da pasta de Lixeira do provedor ativo. Definido em main() apos conectar.
TRASH_FOLDER = "Trash"


def decodificar(texto):
    """Decodifica cabecalhos MIME (assunto/remetente) para texto legivel."""
    if texto is None:
        return ""
    partes = decode_header(texto)
    resultado = []
    for conteudo, charset in partes:
        if isinstance(conteudo, bytes):
            try:
                resultado.append(conteudo.decode(charset or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                resultado.append(conteudo.decode("utf-8", errors="replace"))
        else:
            resultado.append(conteudo)
    return "".join(resultado)


def montar_criterio():
    """Monta o criterio de busca IMAP a partir das escolhas do usuario."""
    print("Buscar emails por:")
    print("  1) Remetente (FROM)")
    print("  2) Assunto (SUBJECT)")
    print("  3) Antes de uma data (BEFORE)")
    print("  4) Todos os emails da pasta (CUIDADO)")
    opcao = input("Escolha [1-4]: ").strip()

    if opcao == "1":
        valor = input("Remetente contem: ").strip()
        return ["FROM", valor]
    elif opcao == "2":
        valor = input("Assunto contem: ").strip()
        return ["SUBJECT", valor]
    elif opcao == "3":
        # Formato exigido pelo IMAP: DD-Mon-YYYY, ex: 01-Jan-2024
        valor = input("Emails antes da data (DD-Mon-YYYY, ex 01-Jan-2024): ").strip()
        return ["BEFORE", valor]
    elif opcao == "4":
        confirma = input("Isso lista TODOS os emails. Continuar? (s/N): ").strip().lower()
        if confirma == "s":
            return ["ALL"]
        return None
    else:
        print("Opcao invalida.")
        return None


def listar_pastas(conexao):
    """Mostra as pastas disponiveis na conta."""
    print("\nPastas disponiveis:")
    status, pastas = conexao.list()
    if status == "OK":
        for p in pastas:
            print("  ", p.decode(errors="replace"))
    print()


def buscar_e_excluir(conexao):
    """Fluxo principal: escolhe pasta, busca, revisa e move para lixeira."""
    pasta = input("Pasta para buscar (Enter = INBOX): ").strip() or "INBOX"
    status, _ = conexao.select(pasta)
    if status != "OK":
        print(f"[ERRO] Nao foi possivel abrir a pasta '{pasta}'.")
        return

    criterio = montar_criterio()
    if not criterio:
        return

    status, dados = conexao.search(None, *criterio)
    if status != "OK":
        print("[ERRO] Falha na busca.")
        return

    ids = dados[0].split()
    if not ids:
        print("\nNenhum email encontrado com esse criterio.\n")
        return

    print(f"\nEncontrados {len(ids)} email(s). Mostrando detalhes:\n")
    for num in ids:
        status, msg_data = conexao.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if status != "OK":
            continue
        mensagem = email.message_from_bytes(msg_data[0][1])
        de = decodificar(mensagem.get("From"))
        assunto = decodificar(mensagem.get("Subject"))
        data = mensagem.get("Date", "")
        print(f"  [{num.decode()}] De: {de}")
        print(f"       Assunto: {assunto}")
        print(f"       Data: {data}")
        print("  " + "-" * 50)

    print()
    confirma = input(
        f"Mover esses {len(ids)} email(s) para a Lixeira? (s/N): "
    ).strip().lower()
    if confirma != "s":
        print("Operacao cancelada. Nada foi excluido.\n")
        return

    mover_para_lixeira(conexao, ids)


def mover_para_lixeira(conexao, ids):
    """Move as mensagens para a pasta Lixeira e faz expunge."""
    id_lista = b",".join(ids)

    # Tenta copiar para a Lixeira antes de marcar como deletado.
    status, _ = conexao.copy(id_lista, TRASH_FOLDER)
    if status == "OK":
        conexao.store(id_lista, "+FLAGS", "\\Deleted")
        conexao.expunge()
        print(f"\n[OK] {len(ids)} email(s) movido(s) para a Lixeira.\n")
    else:
        print(
            f"\n[AVISO] Nao consegui copiar para '{TRASH_FOLDER}'. "
            "A pasta pode ter outro nome nesta conta."
        )
        alt = input(
            "Marcar como \\Deleted diretamente (apaga sem passar pela lixeira)? (s/N): "
        ).strip().lower()
        if alt == "s":
            conexao.store(id_lista, "+FLAGS", "\\Deleted")
            conexao.expunge()
            print(f"\n[OK] {len(ids)} email(s) excluido(s).\n")
        else:
            print("Operacao cancelada.\n")


def main():
    global TRASH_FOLDER
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    print("=" * 60)
    print(" Limpa emails - exclusao via IMAP")
    print("=" * 60)
    conexao, _nome, cfg = provedor.conectar(flags)
    TRASH_FOLDER = cfg["trash"]
    try:
        while True:
            print("Menu:")
            print("  1) Listar pastas da conta")
            print("  2) Buscar e excluir emails")
            print("  3) Sair")
            escolha = input("Escolha [1-3]: ").strip()

            if escolha == "1":
                listar_pastas(conexao)
            elif escolha == "2":
                buscar_e_excluir(conexao)
            elif escolha == "3":
                break
            else:
                print("Opcao invalida.\n")
    finally:
        try:
            conexao.close()
        except Exception:
            pass
        conexao.logout()
        print("Desconectado. Ate mais!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario. Saindo.")
