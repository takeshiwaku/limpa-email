#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
descobrir_remetentes.py
-----------------------
Vasculha uma pasta da conta Yahoo, agrupa os emails por remetente,
conta quantos emails cada remetente enviou e ATUALIZA o arquivo
lista-email-excluir.txt adicionando esses remetentes (com a quantidade).

- Somente leitura na conta (nao apaga nada).
- Preserva os remetentes que ja estavam no arquivo.
- Cada linha fica no formato:  email@dominio.com   # 12 email(s)
  O '#' e a quantidade sao comentario; o limpeza_lista.py ignora comentarios
  e extrai apenas o endereco, entao o formato continua compativel.

Credenciais vem do .env (YAHOO_EMAIL, YAHOO_APP_PASSWORD) ou do prompt.

Uso:
    python descobrir_remetentes.py [pasta] [arquivo-saida]
        [--lote=N] [--provedor=yahoo|gmail]
        [--contatos=arq1.csv,arq2.csv] [--sem-contatos]

Padroes: pasta = INBOX, arquivo-saida = lista-email-excluir.txt
Provedor: definido no .env (PROVEDOR) ou por --provedor. Padrao yahoo.

Protecao (contatos + lista pessoal):
  Remetentes protegidos NAO sao adicionados ao arquivo de exclusao.
  Fontes de protecao:
    - Contatos: todos os '*_contacts.csv' da pasta (ex: gmail_contacts.csv,
      yahoo_contacts.csv). --contatos=a.csv,b.csv escolhe; --sem-contatos desativa.
    - Lista pessoal: 'lista_pessoal.txt' (um email por linha). --pessoal=arq.txt
      escolhe outro arquivo; --sem-pessoal desativa.

Tamanho do lote (emails por chamada IMAP), em ordem de prioridade:
    1) argumento --lote=N
    2) variavel LOTE no .env
    3) padrao (500)
Se o Yahoo reclamar de resposta grande, reduza para 200 ou 100.
"""

import email
import os
import re
import sys
import time
from email.header import decode_header
from email.utils import parseaddr

import protegidos
import provedor
from provedor import carregar_env

# Quantos emails buscar por chamada IMAP (lote) por padrao.
# Pode ser sobrescrito por --lote=N ou pela variavel LOTE no .env.
LOTE_PADRAO = 500

PADRAO_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def resolver_lote(args, env):
    """
    Decide o tamanho do lote com prioridade:
      1) argumento --lote=N (em args)
      2) variavel LOTE no .env (em env)
      3) LOTE_PADRAO
    Retorna um inteiro >= 1.
    """
    valor = None
    origem = "padrao"

    # 1) argumento --lote=N
    for arg in args:
        if arg.startswith("--lote="):
            valor = arg.split("=", 1)[1]
            origem = "argumento --lote"
            break

    # 2) .env
    if valor is None and env.get("LOTE"):
        valor = env.get("LOTE")
        origem = ".env (LOTE)"

    if valor is None:
        return LOTE_PADRAO, "padrao"

    try:
        numero = int(valor)
        if numero < 1:
            raise ValueError
        return numero, origem
    except ValueError:
        print(f"[AVISO] Valor de lote invalido ('{valor}'). Usando padrao {LOTE_PADRAO}.")
        return LOTE_PADRAO, "padrao"


def formatar_tempo(segundos):
    """Formata segundos em algo legivel (ex: 1m 05s)."""
    if segundos < 0:
        segundos = 0
    segundos = int(segundos)
    minutos, seg = divmod(segundos, 60)
    if minutos:
        return f"{minutos}m {seg:02d}s"
    return f"{seg}s"


def barra_progresso(atual, total, inicio, largura=30):
    """
    Desenha/atualiza uma barra de progresso na mesma linha do terminal,
    mostrando porcentagem, contagem, velocidade (emails/s) e ETA.
    """
    if total <= 0:
        return
    fracao = atual / total
    preenchido = int(largura * fracao)
    barra = "#" * preenchido + "-" * (largura - preenchido)

    decorrido = time.monotonic() - inicio
    velocidade = atual / decorrido if decorrido > 0 else 0
    restantes = total - atual
    eta = restantes / velocidade if velocidade > 0 else 0

    linha = (
        f"\r  [{barra}] {fracao*100:5.1f}%  "
        f"{atual}/{total}  "
        f"{velocidade:4.0f}/s  ETA {formatar_tempo(eta)}"
    )
    sys.stdout.write(linha)
    sys.stdout.flush()
    if atual >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()


def extrair_endereco(cabecalho_from):
    """Extrai o endereco de email limpo de um cabecalho 'From'."""
    if not cabecalho_from:
        return ""
    # Decodifica MIME, se necessario.
    partes = decode_header(cabecalho_from)
    texto = ""
    for conteudo, charset in partes:
        if isinstance(conteudo, bytes):
            texto += conteudo.decode(charset or "utf-8", errors="replace")
        else:
            texto += conteudo
    _, endereco = parseaddr(texto)
    endereco = endereco.strip().lower()
    # Valida o formato; se falhar, tenta achar via regex.
    if PADRAO_EMAIL.fullmatch(endereco):
        return endereco
    achado = PADRAO_EMAIL.search(texto)
    return achado.group(0).lower() if achado else ""


def contar_remetentes(conexao, pasta, tamanho_lote=LOTE_PADRAO):
    """Retorna dict {email: quantidade} da pasta informada (somente leitura)."""
    status, _ = conexao.select(pasta, readonly=True)
    if status != "OK":
        print(f"[ERRO] Nao foi possivel abrir a pasta '{pasta}'.")
        return None

    status, dados = conexao.search(None, "ALL")
    if status != "OK":
        print("[ERRO] Falha ao listar as mensagens.")
        return None

    ids = dados[0].split()
    total = len(ids)
    print(f"A pasta '{pasta}' tem {total} email(s). Lendo remetentes...\n")

    contagem = {}
    processados = 0
    inicio = time.monotonic()

    # Busca os cabecalhos From em LOTES (uma chamada IMAP por bloco),
    # em vez de um fetch por mensagem. Bem mais rapido em caixas grandes.
    for comeco in range(0, total, tamanho_lote):
        bloco = ids[comeco:comeco + tamanho_lote]
        conjunto = b",".join(bloco)
        status, msg_data = conexao.fetch(conjunto, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
        if status == "OK" and msg_data:
            # O fetch em lote retorna varios itens; os cabecalhos vem
            # nas tuplas (bytes). Filtramos as partes que sao tuplas.
            for parte in msg_data:
                if not isinstance(parte, tuple) or len(parte) < 2:
                    continue
                mensagem = email.message_from_bytes(parte[1])
                endereco = extrair_endereco(mensagem.get("From"))
                if endereco:
                    contagem[endereco] = contagem.get(endereco, 0) + 1

        processados = min(comeco + len(bloco), total)
        barra_progresso(processados, total, inicio)

    # Garante que a barra termine em 100%.
    if processados < total:
        barra_progresso(total, total, inicio)

    decorrido = time.monotonic() - inicio
    print(f"  Concluido em {formatar_tempo(decorrido)}.\n")
    return contagem


def ler_existentes(caminho):
    """Le os emails ja presentes no arquivo (ignora comentarios)."""
    existentes = set()
    if not os.path.exists(caminho):
        return existentes
    with open(caminho, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            sem_comentario = linha.split("#", 1)[0]
            for email_encontrado in PADRAO_EMAIL.findall(sem_comentario):
                existentes.add(email_encontrado.lower())
    return existentes


def main():
    # Separa flags (--algo) dos argumentos posicionais (pasta, arquivo).
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    posicionais = [a for a in sys.argv[1:] if not a.startswith("--")]

    pasta = posicionais[0] if len(posicionais) > 0 else "INBOX"
    arquivo = posicionais[1] if len(posicionais) > 1 else "lista-email-excluir.txt"

    env = carregar_env()
    tamanho_lote, origem_lote = resolver_lote(flags, env)

    # Contatos + lista pessoal = emails protegidos (nunca vao para o arquivo).
    prot = protegidos.carregar_protegidos(flags)
    protegidos_emails = prot["emails"]

    print("=" * 60)
    print(" Descobrir remetentes e montar lista de exclusao")
    print("=" * 60)
    print(f"Pasta:    {pasta}")
    print(f"Arquivo:  {arquivo}")
    print(f"Lote:     {tamanho_lote} (origem: {origem_lote})")
    print(f"Protegidos: {protegidos.resumo(prot)} (serao poupados)")
    print()

    conexao, _nome, _cfg = provedor.conectar(flags)
    try:
        contagem = contar_remetentes(conexao, pasta, tamanho_lote)
        if contagem is None:
            return
        if not contagem:
            print("Nenhum remetente encontrado.")
            return

        # Ordena por quantidade (desc) e depois pelo email.
        ordenado = sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))

        print(f"\n{len(ordenado)} remetente(s) distinto(s) encontrado(s):\n")
        largura = max(len(e) for e, _ in ordenado)
        for endereco, qtd in ordenado:
            marca = "  [PROTEGIDO]" if endereco in protegidos_emails else ""
            print(f"  {endereco.ljust(largura)}  {qtd} email(s){marca}")

        existentes = ler_existentes(arquivo)

        # Remetentes protegidos (contato ou lista pessoal): nao entram no arquivo.
        poupados = [(e, q) for e, q in ordenado if e in protegidos_emails]
        # Novos = nao estao no arquivo E nao sao protegidos.
        novos = [
            (e, q) for e, q in ordenado
            if e not in existentes and e not in protegidos_emails
        ]

        if poupados:
            print(f"\n{len(poupados)} remetente(s) protegido(s) (contato/lista "
                  "pessoal) foram poupados (nao serao adicionados).")

        if not novos:
            print("\nNenhum remetente novo para adicionar (ja estavam no arquivo "
                  "ou sao protegidos).")
            return

        print(f"\n{len(novos)} novo(s) remetente(s) sera(ao) adicionado(s) a '{arquivo}'.")
        resp = input("Confirmar e escrever no arquivo? (s/N): ").strip().lower()
        if resp != "s":
            print("Cancelado. O arquivo nao foi alterado.")
            return

        # Garante que o arquivo termina com quebra de linha antes de anexar.
        precisa_quebra = False
        if os.path.exists(arquivo) and os.path.getsize(arquivo) > 0:
            with open(arquivo, "rb") as f:
                f.seek(-1, os.SEEK_END)
                precisa_quebra = f.read(1) != b"\n"

        with open(arquivo, "a", encoding="utf-8") as f:
            if precisa_quebra:
                f.write("\n")
            f.write(f"# --- remetentes descobertos na pasta '{pasta}' ---\n")
            for endereco, qtd in novos:
                f.write(f"{endereco}   # {qtd} email(s)\n")

        print(f"\n[OK] {len(novos)} remetente(s) adicionado(s) a '{arquivo}'.")
        print("Agora voce pode revisar o arquivo e rodar: python limpeza_lista.py")
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
