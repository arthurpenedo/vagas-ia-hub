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
python -m hub coletar            # atualiza site/vagas.json
python -m pytest -q              # testes
python -m http.server -d site    # abre o site em http://localhost:8000
```

O GitHub Actions (`.github/workflows/site.yml`) roda os testes, faz a coleta todo dia às 7h30 de Brasília,
salva as vagas no repositório e publica o site no GitHub Pages.

## Links de indicação

`site/indicacoes.json` guarda o código de indicação de cada plataforma. Com o código vazio, o botão leva à vaga
normal. O site deixa claro, no rodapé e em "Como funciona", que alguns links são de indicação e que ele é um guia
independente, sem vínculo com as plataformas.

## Nova plataforma

Acrescente uma `Plataforma` em `hub/coleta.py` com o sitemap e o padrão das URLs de vaga. Se as páginas trazem
`JobPosting` em JSON-LD (comum, por causa do Google for Jobs), o resto funciona sozinho.
