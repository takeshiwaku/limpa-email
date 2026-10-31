#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
listar_distintos.py
-------------------
Le um arquivo de texto e lista os enderecos de email DISTINTOS encontrados.

- Extrai emails mesmo que a linha tenha outro texto junto.
- Remove duplicados ignorando maiusculas/minusculas.
- Ordena o resultado.

Uso:
    python listar_distintos.py [arquivo]

Se nenhum arquivo for informado, usa "lista-email-excluir.txt".
"""

import re
import sys

# Regex simples para capturar enderecos de email.
PADRAO_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def contar_distintos(caminho):
    """
    Retorna uma lista de tuplas (email, quantidade) com os enderecos
    distintos (case-insensitive) e quantas vezes cada um aparece no arquivo.
    Ordenado por quantidade (desc) e depois pelo email.
    """
    contagem = {}   # chave minuscula -> quantidade
    originais = {}  # chave minuscula -> forma original (primeira ocorrencia)
    with open(caminho, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            for email in PADRAO_EMAIL.findall(linha):
                chave = email.lower()
                contagem[chave] = contagem.get(chave, 0) + 1
                if chave not in originais:
                    originais[chave] = email
    itens = [(originais[chave], qtd) for chave, qtd in contagem.items()]
    itens.sort(key=lambda item: (-item[1], item[0].lower()))
    return itens


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else "lista-email-excluir.txt"
    try:
        itens = contar_distintos(caminho)
    except FileNotFoundError:
        print(f"[ERRO] Arquivo nao encontrado: {caminho}")
        sys.exit(1)

    if not itens:
        print("Nenhum endereco de email encontrado no arquivo.")
        return

    print(f"{len(itens)} endereco(s) distinto(s) em '{caminho}':\n")
    largura = max(len(email) for email, _ in itens)
    for email, qtd in itens:
        print(f"{email.ljust(largura)}  {qtd}x")


if __name__ == "__main__":
    main()
