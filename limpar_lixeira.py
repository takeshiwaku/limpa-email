#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpar_lixeira.py
-----------------
Esvazia a Lixeira (Trash) ou o Spam (Junk) da conta (Yahoo ou Gmail) via IMAP.

ATENCAO: isso apaga os emails DEFINITIVAMENTE (nao ha recuperacao).
Por isso o script mostra a quantidade e pede confirmacao dupla.

Credenciais e provedor vem do .env (ver provedor.py).

Uso:
    python limpar_lixeira.py [nome-da-pasta] [--pasta=lixeira|spam|ambos] [--provedor=yahoo|gmail]

Por padrao (sem --pasta) esvazia AS DUAS: Lixeira e Spam.
--pasta=lixeira ou --pasta=spam limita a apenas uma.
A pasta e detectada automaticamente pela flag \\Trash / \\Junk (funciona em
qualquer idioma; ex: [Gmail]/Lixeira e [Gmail]/Spam em conta em portugues).
Voce pode sobrescrever passando o nome exato de uma pasta como argumento.
Cada pasta pede confirmacao dupla separadamente.
Provedor: definido no .env (PROVEDOR) ou por --provedor. Padrao yahoo.
"""

import sys

import provedor


def resolver_alvos(flags):
    """
    Le --pasta= das flags. Retorna a lista de alvos a esvaziar.
    Padrao (sem flag): ['lixeira', 'spam'] (esvazia as duas).
    Valores aceitos: lixeira|trash, spam|junk, ambos|todos.
    """
    for arg in flags:
        if arg.startswith("--pasta="):
            valor = arg.split("=", 1)[1].strip().lower()
            if valor in ("lixeira", "trash"):
                return ["lixeira"]
            if valor in ("spam", "junk"):
                return ["spam"]
            if valor in ("ambos", "todos", "all"):
                return ["lixeira", "spam"]
            print(f"[AVISO] Valor de --pasta invalido ('{valor}'). Esvaziando ambos.")
    return ["lixeira", "spam"]


def esvaziar_pasta(conexao, pasta, rotulo):
    """
    Esvazia uma pasta especifica (apaga definitivamente), com dupla
    confirmacao. Retorna o numero de emails apagados (0 se nada foi feito).
    """
    print("-" * 60)
    print(f"Alvo: {rotulo}  (pasta '{pasta}')")

    # Seleciona a pasta (nao read-only, pois vamos apagar).
    status, _ = conexao.select(pasta)
    if status != "OK":
        print(f"[ERRO] Nao foi possivel abrir a pasta '{pasta}'. Pulando.")
        return 0

    uids = provedor.buscar_uids(conexao, ["ALL"])
    if uids is None:
        print(f"[ERRO] Falha ao listar mensagens de '{rotulo}'. Pulando.")
        return 0

    total = len(uids)
    if total == 0:
        print(f"A pasta {rotulo} ja esta vazia. Nada a fazer.")
        return 0

    print(f"A pasta {rotulo} contem {total} email(s).")
    c1 = input(f"Apagar TUDO de '{rotulo}' definitivamente? (s/N): ").strip().lower()
    if c1 != "s":
        print("  Pulado.")
        return 0
    c2 = input("Confirma? Isso NAO pode ser desfeito. Digite 'APAGAR': ").strip()
    if c2 != "APAGAR":
        print("  Confirmacao incorreta. Pulado.")
        return 0

    # Estando DENTRO da pasta, marcar \Deleted + EXPUNGE apaga de vez
    # (vale para Yahoo e Gmail). Feito por UID para consistencia.
    uid_lista = b",".join(uids).decode()
    typ, dados = conexao.uid("STORE", uid_lista, "+FLAGS", "(\\Deleted)")
    if typ != "OK":
        print(f"[ERRO] Falha ao marcar como deletado: {dados}")
        return 0
    conexao.expunge()
    print(f"[OK] {total} email(s) apagado(s) definitivamente de '{rotulo}'.")
    return total


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    posicionais = [a for a in sys.argv[1:] if not a.startswith("--")]

    alvos = resolver_alvos(flags)

    print("=" * 60)
    print(" Esvaziar Lixeira / Spam")
    print("=" * 60)
    print("ATENCAO: os emails serao apagados DEFINITIVAMENTE.")
    print(f"Alvos: {', '.join(alvos)}\n")

    conexao, _nome, cfg = provedor.conectar(flags)
    try:
        # Se o usuario passou um nome de pasta explicito, esvazia so ela.
        if len(posicionais) > 0:
            esvaziar_pasta(conexao, posicionais[0], posicionais[0])
            return

        total_geral = 0
        for alvo in alvos:
            pasta = cfg["trash"] if alvo == "lixeira" else cfg["spam"]
            rotulo = "Lixeira" if alvo == "lixeira" else "Spam"
            total_geral += esvaziar_pasta(conexao, pasta, rotulo)

        print("-" * 60)
        print(f"Concluido. Total apagado: {total_geral} email(s).")
    finally:
        try:
            conexao.close()
        except Exception:
            pass
        conexao.logout()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")
