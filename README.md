# Limpa Yahoo / Gmail

Conjunto de scripts em Python para ajudar a limpar emails de uma conta **Yahoo** ou **Gmail** via IMAP. Usa apenas a biblioteca padrão do Python (sem `pip install`).

## Pré-requisitos

1. **App Password** (a senha normal da conta NÃO funciona no IMAP):
   - Yahoo: Account Info → Account Security → **Generate app password**
   - Gmail: exige verificação em 2 etapas ativada + IMAP habilitado (Configurações → Encaminhamento e POP/IMAP) + **Senha de app** (Conta Google → Segurança → Senhas de app). Use o valor **sem espaços**.
2. Python 3 instalado.

## Provedores (Yahoo e Gmail)

O provedor é escolhido, em ordem de prioridade:
1. flag `--provedor=yahoo|gmail`
2. variável `PROVEDOR` no `.env`
3. padrão: `yahoo`

Servidor e pastas são configurados automaticamente. A pasta de **Lixeira** e **Spam** é detectada pela flag IMAP (`\Trash` / `\Junk`), então funciona em qualquer idioma (ex: no Gmail em português a Lixeira é `[Gmail]/Lixeira`).

## Configuração (.env)

Crie um `.env` na pasta do projeto (use o `.env.example` como modelo):

```
PROVEDOR=yahoo

# Yahoo
YAHOO_EMAIL=voce@yahoo.com
YAHOO_APP_PASSWORD=sua_app_password_aqui

# Gmail
GMAIL_EMAIL=voce@gmail.com
GMAIL_APP_PASSWORD=sua_app_password_do_google

# Opcional (tamanho do lote no descobrir_remetentes.py):
LOTE=500
```

O `.env` está no `.gitignore` e não é commitado. **Nunca coloque a senha no código nem compartilhe o `.env`.** Se não houver `.env`, os scripts aceitam variáveis de ambiente e, por último, pedem a senha no terminal.

## Proteção: contatos + lista pessoal

Para nunca excluir quem você conhece, os scripts poupam emails **protegidos**, vindos de duas fontes:

1. **Contatos** — arquivos `*_contacts.csv` na pasta (ex: `gmail_contacts.csv`, `yahoo_contacts.csv`). Exporte pelo Google Contacts / Yahoo e salve na pasta.
2. **Lista pessoal** — `lista_pessoal.txt`, um email por linha (texto após `#` é comentário).

Efeito:
- `descobrir_remetentes.py`: remetentes protegidos aparecem como `[PROTEGIDO]` e **não são gravados** no arquivo de exclusão.
- `limpeza_lista.py`: mesmo que um email protegido esteja no arquivo de exclusão, ele **não é movido** (segunda camada de segurança).

Flags (valem para os dois scripts):
- `--contatos=a.csv,b.csv` — usa arquivos de contatos específicos
- `--sem-contatos` — desativa a proteção por contatos
- `--pessoal=arquivo.txt` — usa outro arquivo de lista pessoal
- `--sem-pessoal` — desativa a lista pessoal

## Fluxo recomendado

1. **Descobrir remetentes** e montar a lista (contatos/lista pessoal são poupados):
   ```bash
   python descobrir_remetentes.py
   ```
2. **Revisar** o `lista-email-excluir.txt`: apague as linhas de quem quer MANTER; deixe só quem quer excluir.
3. **Limpar por lista** (move para a Lixeira):
   ```bash
   python limpeza_lista.py
   ```
4. **Esvaziar Lixeira e Spam** definitivamente (opcional):
   ```bash
   python limpar_lixeira.py
   ```

## Scripts

### `descobrir_remetentes.py`
Vasculha uma pasta (somente leitura), agrupa por remetente, conta quantos emails cada um enviou e adiciona os remetentes novos ao arquivo de exclusão (com a quantidade em comentário). Barra de progresso com porcentagem, velocidade e ETA. Remetentes protegidos não são gravados.

```bash
python descobrir_remetentes.py [pasta] [arquivo-saida] \
    [--lote=N] [--provedor=yahoo|gmail] \
    [--contatos=...] [--sem-contatos] [--pessoal=arq.txt] [--sem-pessoal]
```
- Padrões: `pasta = INBOX`, `arquivo-saida = lista-email-excluir.txt`
- **Lote** (emails por chamada IMAP): `--lote=N` > `LOTE` no `.env` > `500`. Reduza para `200`/`100` se o servidor recusar respostas grandes.

Exemplos:
```bash
python descobrir_remetentes.py --provedor=gmail
python descobrir_remetentes.py Bulk --lote=100
python descobrir_remetentes.py INBOX minha-lista.txt --sem-pessoal
```

### `limpeza_lista.py`
Lê os remetentes do arquivo de exclusão e, após confirmação, **move para a Lixeira** os emails desses remetentes. Permite mover todos de uma vez ou decidir remetente por remetente. Poupa emails protegidos.

Por padrão só exclui emails com **mais de 30 dias**. Ajuste com `--dias=N`.

```bash
python limpeza_lista.py [arquivo-de-remetentes] [pasta] \
    [--dias=N] [--provedor=yahoo|gmail] \
    [--contatos=...] [--sem-contatos] [--pessoal=arq.txt] [--sem-pessoal]
```
- Padrões: `arquivo = lista-email-excluir.txt`, `pasta = INBOX`, `dias = 30`
- `--dias=0`: sem filtro de idade (todos os emails dos remetentes).

Exemplos:
```bash
python limpeza_lista.py                        # 30 dias (padrão)
python limpeza_lista.py --dias=0               # todos, sem filtro de idade
python limpeza_lista.py lista.txt INBOX --dias=90 --provedor=gmail
```

### `limpar_lixeira.py`
Esvazia a **Lixeira** e o **Spam** **definitivamente**. Por padrão processa as duas pastas, uma de cada vez, com dupla confirmação separada (é preciso digitar `APAGAR`).

```bash
python limpar_lixeira.py [nome-da-pasta] [--pasta=lixeira|spam|ambos] [--provedor=yahoo|gmail]
```
- Sem `--pasta`: esvazia **Lixeira e Spam**.
- `--pasta=lixeira` ou `--pasta=spam`: limita a uma só.
- A pasta é detectada automaticamente (funciona em qualquer idioma).

### `listar_distintos.py`
Local, só lê o arquivo (não conecta). Lista os endereços distintos e quantas vezes cada um aparece.

```bash
python listar_distintos.py [arquivo]
```

### `limpa_yahoo.py`
Menu interativo: listar pastas, buscar e excluir emails (por remetente, assunto, data ou todos). Move para a Lixeira com confirmação.

```bash
python limpa_yahoo.py
```

## Formato dos arquivos de lista

Um endereço por linha. Texto após `#` é comentário (ignorado). Vale para `lista-email-excluir.txt` e `lista_pessoal.txt`:

```
newsletter@loja.com   # 42 email(s)
promo@banco.com        # 18 email(s)
```

## Módulos internos

- `provedor.py` — servidor/pastas por provedor, login IMAP, detecção de Lixeira/Spam, e o `mover_para_pasta` (usa `UID MOVE` com fallback `COPY`).
- `protegidos.py` — carrega contatos (CSV) + lista pessoal e monta o conjunto de emails protegidos.

## Segurança

- Os scripts que apagam sempre mostram o que será afetado e pedem confirmação.
- `limpeza_lista.py` e `limpa_yahoo.py` **movem para a Lixeira** (recuperável). Só `limpar_lixeira.py` apaga **definitivamente**.
- Contatos e lista pessoal são poupados em duas camadas (ao montar a lista e ao mover).
- Nunca compartilhe sua App Password. Se vazar, revogue e gere outra.

## Detalhes técnicos

- Portas: IMAP `993` (SSL). Servidores: `imap.mail.yahoo.com`, `imap.gmail.com`.
- Datas no IMAP: formato `DD-Mon-YYYY` (ex: `01-Jan-2024`).
- Operações por **UID** (busca e move) para consistência e segurança.
