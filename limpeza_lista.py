#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpeza_lista.py
----------------
Le os remetentes do arquivo lista-email-excluir.txt e, apos confirmacao,
move para a Lixeira os emails desses remetentes na conta Yahoo.

Por padrao, so exclui emails com MAIS de 30 dias (mais antigos que hoje - 30).
Isso protege mensagens recentes. Ajuste com --dias=N (use --dias=0 para
incluir TODOS os emails, sem filtro de idade).

Voce pode mover todos de uma vez ou decidir remetente por remetente.

Credenciais vem do .env (YAHOO_EMAIL, YAHOO_APP_PASSWORD) ou do prompt.

Uso:
    python limpeza_lista.py [arquivo-de-remetentes] [pasta]
        [--dias=N] [--provedor=yahoo|gmail]
        [--contatos=...] [--sem-contatos] [--pessoal=arq.txt] [--sem-pessoal]

Padroes: arquivo = lista-email-excluir.txt, pasta = INBOX, dias = 30
Provedor: definido no .env (PROVEDOR) ou por --provedor. Padrao yahoo.

Protecao (2a camada): remetentes que estejam nos contatos ('*_contacts.csv')
ou na lista pessoal ('lista_pessoal.txt') NAO sao movidos, mesmo que estejam
no arquivo de exclusao. Desative com --sem-contatos / --sem-pessoal.
"""

import os
import re
import sys
from datetime import datetime, timedelta

import protegidos
import provedor

DIAS_PADRAO = 30

PADRAO_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def ler_remetentes(caminho):
    """Extrai enderecos de email distintos (case-insensitive) do arquivo."""
    vistos = {}
    with open(caminho, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            for email in PADRAO_EMAIL.findall(linha):
                chave = email.lower()
                if chave not in vistos:
                    vistos[chave] = email
    return sorted(vistos.values(), key=str.lower)


def buscar_uids_por_remetente(conexao, remetente, antes_de=None):
    """
    Retorna os UIDs das mensagens do remetente informado (so leitura).
    Se 'antes_de' for informado (formato IMAP DD-Mon-YYYY), so retorna
    mensagens recebidas ANTES dessa data (ou seja, mais antigas).
    Usa busca por UID para casar com o move por UID (seguro).
    """
    criterio = ["FROM", remetente]
    if antes_de:
        criterio += ["BEFORE", antes_de]
    uids = provedor.buscar_uids(conexao, criterio)
    if uids is None:
        print(f"  [AVISO] Busca falhou para {remetente}.")
        return []
    return uids


def resolver_dias(flags):
    """
    Le --dias=N das flags. Retorna um inteiro >= 0.
    0 significa "sem filtro de idade" (inclui todos os emails).
    Se ausente, usa DIAS_PADRAO. Se invalido, avisa e usa o padrao.
    """
    for arg in flags:
        if arg.startswith("--dias="):
            valor = arg.split("=", 1)[1]
            try:
                numero = int(valor)
                if numero < 0:
                    raise ValueError
                return numero
            except ValueError:
                print(f"[AVISO] Valor de --dias invalido ('{valor}'). Usando {DIAS_PADRAO}.")
                return DIAS_PADRAO
    return DIAS_PADRAO


def data_imap_antes(dias):
    """
    Devolve a data-limite no formato IMAP (DD-Mon-YYYY) para o criterio BEFORE,
    correspondente a "hoje - dias". Retorna None se dias == 0 (sem filtro).
    """
    if dias <= 0:
        return None
    limite = datetime.now() - timedelta(days=dias)
    # IMAP exige nome do mes em ingles abreviado (Jan, Feb, ...).
    meses = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{limite.day:02d}-{meses[limite.month - 1]}-{limite.year}"


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    posicionais = [a for a in sys.argv[1:] if not a.startswith("--")]

    caminho = posicionais[0] if len(posicionais) > 0 else "lista-email-excluir.txt"
    pasta = posicionais[1] if len(posicionais) > 1 else "INBOX"
    dias = resolver_dias(flags)
    antes_de = data_imap_antes(dias)

    if not os.path.exists(caminho):
        print(f"[ERRO] Arquivo nao encontrado: {caminho}")
        sys.exit(1)

    remetentes = ler_remetentes(caminho)
    if not remetentes:
        print("Nenhum remetente encontrado no arquivo.")
        return

    # Segunda camada de seguranca: contatos + lista pessoal = protegidos.
    prot = protegidos.carregar_protegidos(flags)
    protegidos_emails = prot["emails"]
    protegidos_na_lista = [r for r in remetentes if r.lower() in protegidos_emails]
    remetentes = [r for r in remetentes if r.lower() not in protegidos_emails]

    print("=" * 60)
    print(" Limpeza por lista de remetentes")
    print("=" * 60)
    print(f"Arquivo: {caminho}")
    print(f"Pasta:   {pasta}")
    print(f"Protegidos: {protegidos.resumo(prot)}")
    if protegidos_na_lista:
        print(f"[PROTECAO] {len(protegidos_na_lista)} remetente(s) da lista sao "
              "protegidos e NAO serao tocados:")
        for r in protegidos_na_lista:
            print(f"    - {r}")
    print(f"Remetentes a processar: {len(remetentes)}")
    if antes_de:
        print(f"Filtro de idade: apenas emails com mais de {dias} dias (antes de {antes_de})")
    else:
        print("Filtro de idade: nenhum (todos os emails dos remetentes)")
    print()

    if not remetentes:
        print("Nada a processar (todos os remetentes da lista sao protegidos).")
        return

    conexao, _nome, cfg = provedor.conectar(flags)
    trash_folder = cfg["trash"]
    try:
        status, _ = conexao.select(pasta)
        if status != "OK":
            print(f"[ERRO] Nao foi possivel abrir a pasta '{pasta}'.")
            return

        modo = input(
            "Como deseja prosseguir?\n"
            "  1) Mover para a Lixeira todos os emails dos remetentes da lista\n"
            "  2) Decidir remetente por remetente\n"
            "  3) Cancelar (nao apagar nada)\n"
            "Escolha [1-3]: "
        ).strip()

        if modo == "3" or modo not in ("1", "2"):
            print("Cancelado. Nada foi excluido.")
            return

        movidos = 0
        for remetente in remetentes:
            if modo == "2":
                resp = input(
                    f"Mover emails de '{remetente}' para a Lixeira? (s/N): "
                ).strip().lower()
                if resp != "s":
                    print("  pulado.")
                    continue

            uids = buscar_uids_por_remetente(conexao, remetente, antes_de)
            if not uids:
                if antes_de:
                    print(f"  '{remetente}': nenhum email com mais de {dias} dias.")
                else:
                    print(f"  '{remetente}': nenhum email encontrado.")
                continue

            ok, metodo, erro = provedor.mover_para_pasta(conexao, uids, trash_folder)
            if ok:
                movidos += len(uids)
                print(f"  [OK] '{remetente}': {len(uids)} email(s) movido(s) para a Lixeira ({metodo}).")
            else:
                print(
                    f"  [AVISO] Nao consegui mover de '{remetente}' "
                    f"para '{trash_folder}'. Detalhe: {erro}"
                )

        print(f"\nConcluido. {movidos} email(s) movido(s) para a Lixeira.")
        print("Eles ainda podem ser recuperados pela Lixeira.")
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
