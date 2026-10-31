#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
protegidos.py
-------------
Modulo compartilhado que monta o conjunto de emails PROTEGIDOS, ou seja,
que nunca devem entrar na lista de exclusao nem ser movidos/apagados.

Duas fontes de protecao:
  1) Contatos exportados em CSV ('*_contacts.csv' na pasta): Google/Yahoo.
  2) Lista pessoal (por padrao 'lista_pessoal.txt'): um email por linha,
     texto apos '#' e comentario.

Usa apenas a biblioteca padrao.
"""

import csv
import glob
import os
import re

PADRAO_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

LISTA_PESSOAL_PADRAO = "lista_pessoal.txt"


def carregar_contatos(arquivos):
    """
    Le a lista de arquivos de contatos (CSV) informada e retorna
    (conjunto_de_emails_minusculos, lista_de_arquivos_lidos).

    Funciona com o CSV do Google e o do Yahoo: coleta emails das colunas
    cujo nome menciona email e faz fallback por regex em todas as celulas.
    """
    contatos = set()
    lidos = []
    for caminho in arquivos:
        if not os.path.exists(caminho):
            print(f"[AVISO] Arquivo de contatos nao encontrado: {caminho}")
            continue
        lidos.append(caminho)
        try:
            with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
                linhas = list(csv.reader(f))
        except (OSError, UnicodeError):
            with open(caminho, "r", encoding="latin-1", newline="") as f:
                linhas = list(csv.reader(f))

        if not linhas:
            continue

        cabecalho = linhas[0]
        col_email = [
            i for i, nome in enumerate(cabecalho)
            if "email" in nome.lower() or "e-mail" in nome.lower()
        ]
        for linha in linhas[1:]:
            for i in col_email:
                if i < len(linha):
                    for achado in PADRAO_EMAIL.findall(linha[i]):
                        contatos.add(achado.lower())
            for celula in linha:
                for achado in PADRAO_EMAIL.findall(celula):
                    contatos.add(achado.lower())
    return contatos, lidos


def carregar_lista_pessoal(caminho=LISTA_PESSOAL_PADRAO):
    """
    Le um arquivo de emails (um por linha, '#' e comentario) e retorna
    (conjunto_de_emails_minusculos, existe_arquivo).
    """
    pessoais = set()
    if not os.path.exists(caminho):
        return pessoais, False
    with open(caminho, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            sem_comentario = linha.split("#", 1)[0]
            for achado in PADRAO_EMAIL.findall(sem_comentario):
                pessoais.add(achado.lower())
    return pessoais, True


def resolver_arquivos_contatos(flags):
    """
    Decide quais CSVs de contatos ler:
      --contatos=arq1.csv,arq2.csv  -> usa esses arquivos.
      --sem-contatos                -> nao usa contatos.
      sem flag                      -> todos os '*_contacts.csv' da pasta.
    """
    for arg in flags:
        if arg == "--sem-contatos":
            return []
        if arg.startswith("--contatos="):
            valor = arg.split("=", 1)[1]
            return [c.strip() for c in valor.split(",") if c.strip()]
    return sorted(glob.glob("*_contacts.csv"))


def resolver_lista_pessoal(flags):
    """
    Decide qual arquivo de lista pessoal usar:
      --pessoal=arquivo.txt   -> usa esse arquivo.
      --sem-pessoal           -> nao usa lista pessoal.
      sem flag                -> 'lista_pessoal.txt' (se existir).
    """
    for arg in flags:
        if arg == "--sem-pessoal":
            return None
        if arg.startswith("--pessoal="):
            return arg.split("=", 1)[1].strip()
    return LISTA_PESSOAL_PADRAO


def carregar_protegidos(flags):
    """
    Junta contatos + lista pessoal num unico conjunto de emails protegidos.

    Retorna um dicionario com:
      'emails'          -> set de emails protegidos (minusculos)
      'contatos'        -> set so dos contatos
      'pessoais'        -> set so da lista pessoal
      'contatos_lidos'  -> arquivos de contatos lidos
      'pessoal_arquivo' -> caminho da lista pessoal (ou None)
    """
    arquivos_contatos = resolver_arquivos_contatos(flags)
    contatos, contatos_lidos = carregar_contatos(arquivos_contatos)

    pessoal_arquivo = resolver_lista_pessoal(flags)
    pessoais = set()
    if pessoal_arquivo:
        pessoais, existe = carregar_lista_pessoal(pessoal_arquivo)
        if not existe:
            pessoal_arquivo = None  # nao existe: trata como ausente

    return {
        "emails": contatos | pessoais,
        "contatos": contatos,
        "pessoais": pessoais,
        "contatos_lidos": contatos_lidos,
        "pessoal_arquivo": pessoal_arquivo,
    }


def resumo(info):
    """Devolve uma string curta descrevendo o que foi carregado."""
    partes = []
    if info["contatos_lidos"]:
        partes.append(
            f"{len(info['contatos'])} contato(s) de "
            f"{', '.join(info['contatos_lidos'])}"
        )
    else:
        partes.append("nenhum arquivo de contatos")
    if info["pessoal_arquivo"]:
        partes.append(
            f"{len(info['pessoais'])} da lista pessoal "
            f"({info['pessoal_arquivo']})"
        )
    else:
        partes.append("sem lista pessoal")
    return "; ".join(partes)
