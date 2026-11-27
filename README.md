# Trampo com IA

Hub em português de vagas remotas para treinar e avaliar modelos de IA (Mercor, micro1), atualizado todo dia
por um coletor em Python. Feito para quem sente a IA mudando o próprio trabalho e quer ser pago para ensinar a IA.

- **Site estático** (`site/`): filtros por área, plataforma, valor e "aceita o Brasil"; guias de seleção; sem backend.
- **Coletor** (`hub/`): lê o sitemap público de cada plataforma e o bloco JSON-LD `JobPosting` de cada vaga, o mesmo
  dado estruturado que o Google usa. Uma requisição por segundo, só baixa vagas novas, respeita o `robots.txt`
  e não usa API interna nem login. Vagas que saem do sitemap ou vencem são retiradas.
- **Classificação**: área por palavras-chave (o título pesa 5x) e país normalizado para o selo "Aceita o Brasil".
- **Sem dependências** além da biblioteca padrão; testes com `pytest`.

## Uso

```bash
python -m hub coletar            # atualiza site/vagas.json (e traduz)
python -m hub paginas            # gera as páginas de vaga e o sitemap
python -m pytest -q              # testes
python -m http.server -d site    # abre o site em http://localhost:8000
```

`rotina.cmd` faz a coleta e envia as vagas ao GitHub (agendado no Windows todo dia às 7h30; roda no PC porque a
micro1 bloqueia os servidores do GitHub). A cada push, o GitHub Actions roda os testes e publica o site no Pages.

## Páginas geradas na publicação

`python -m hub paginas` (roda no GitHub Actions) cria uma página por vaga em `site/vaga/` (resumo em português,
texto original, países, botão de candidatura e vagas parecidas), o `sitemap.xml` e o `robots.txt`. Esses arquivos não
ficam no repositório. O endereço de cada vaga usa o título original + 8 caracteres do id, então não muda entre coletas.

## Newsletter

Caixa "Receba as vagas novas no seu e-mail" na home e em cada vaga. A inscrição vai para um Google Apps Script
(`apps-script/`) que guarda os e-mails numa planilha privada e faz a dupla confirmação. Depois da coleta, o PC roda
`python -m hub newsletter`: busca quem confirmou, monta um e-mail com as vagas novas que não são fechadas para o
Brasil (filtrando pelas áreas que cada pessoa escolheu) e manda um por pessoa pelo Gmail, com link de descadastro.
Nenhum e-mail de inscrito fica no repositório; `dados/newsletter-estado.json` guarda só os ids já anunciados.
Para ligar, veja `apps-script/LEIA.md`. Sem isso, a caixa fica escondida.

```bash
python -m hub newsletter --simular            # mostra o que seria enviado
python -m hub newsletter --teste voce@x.com   # manda o e-mail de hoje só para você
```

## Links de indicação

`site/indicacoes.json` guarda o código de indicação de cada plataforma. Com o código vazio, o botão leva à vaga
normal. O site deixa claro, no rodapé e em "Como funciona", que alguns links são de indicação e que ele é um guia
independente, sem vínculo com as plataformas.

## Nova plataforma

Acrescente uma `Plataforma` em `hub/coleta.py` com o sitemap e o padrão das URLs de vaga. Se as páginas trazem
`JobPosting` em JSON-LD (comum, por causa do Google for Jobs), o resto funciona sozinho.
