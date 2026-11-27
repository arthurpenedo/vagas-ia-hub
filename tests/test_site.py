import json
from datetime import date

from hub import newsletter, paginas


def vaga(i, **kw):
    v = {"id": f"micro1:{i}", "plataforma": "micro1", "titulo": f"Data Analyst {i}", "url": f"https://jobs.micro1.ai/post/{i}",
         "area": "Programação", "valorMin": 40, "valorMax": 60, "moeda": "USD", "unidade": "hora", "paises": ["Brasil"],
         "brasil": "sim", "habilidades": ["SQL"], "resumo": "Analyze data.", "resumoPt": "Analisar dados.",
         "tituloPt": f"Analista de Dados {i}", "publicada": "2026-11-27"}
    v.update(kw)
    return v


INDIC = {"micro1": {"codigo": "abc", "modelo": "{url}{sep}referralCode={codigo}"}}


def test_slug_estavel_e_sem_acento():
    a = paginas.slug(vaga(1, titulo="Médico <Sênior> / Brasil"))
    assert a == paginas.slug(vaga(1, titulo="Médico <Sênior> / Brasil", tituloPt="outra tradução"))
    assert a.startswith("medico-senior-brasil-") and len(a.rsplit("-", 1)[1]) == 8
    assert paginas.slug(vaga(1)) != paginas.slug(vaga(2))


def test_gerar_paginas_sitemap_e_escapa_html(tmp_path):
    vs = [vaga(1, tituloPt='Analista <script>alert(1)</script>'), vaga(2), vaga(3, dup=True)]
    (tmp_path / "vagas.json").write_text(json.dumps({"plataformas": {"micro1": "micro1"}, "vagas": vs}), encoding="utf-8")
    (tmp_path / "indicacoes.json").write_text(json.dumps(INDIC), encoding="utf-8")
    assert paginas.gerar(tmp_path) == 2
    pg = (tmp_path / "vaga" / f"{paginas.slug(vs[0])}.html").read_text(encoding="utf-8")
    assert "<script>alert" not in pg and "&lt;script&gt;" in pg
    assert "referralCode=abc" in pg and 'rel="noopener sponsored"' in pg
    assert paginas.slug(vs[1]) + ".html" in pg  # vaga parecida
    mapa = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert mapa.count("/vaga/") == 2 and "privacidade.html" in mapa


def test_novas_vagas_primeira_rodada_e_seguintes():
    vs = [vaga(1, publicada="2026-11-27"), vaga(2, publicada="2026-10-01"), vaga(3, brasil="nao"), vaga(4, dup=True)]
    assert [v["id"] for v in newsletter.novas_vagas(vs, {}, date(2026, 11, 27))] == ["micro1:1"]
    estado = {"anunciadas": ["micro1:1"]}
    assert [v["id"] for v in newsletter.novas_vagas(vs, estado, date(2026, 11, 27))] == ["micro1:2"]


def test_para_inscrito_filtra_areas():
    vs = [vaga(1), vaga(2, area="Saúde")]
    assert len(newsletter.para_inscrito(vs, "")) == 2
    assert [v["id"] for v in newsletter.para_inscrito(vs, "Saúde|Direito")] == ["micro1:2"]


def test_montar_tem_descadastro_e_escapa():
    assunto, texto, html = newsletter.montar([vaga(1, tituloPt="A & <b>B</b>")], INDIC, {"micro1": "micro1"}, "https://x/sair?t=1", 10)
    assert assunto.startswith("1 vaga nova") and "US$ 40–60/h" in assunto
    assert "https://x/sair?t=1" in texto and "https://x/sair?t=1" in html
    assert "<b>B</b>" not in html and "&lt;b&gt;" in html
    assert "referralCode=abc" in html


def test_rodar_envia_uma_vez_por_dia(tmp_path, monkeypatch):
    site = tmp_path / "site"
    site.mkdir()
    (site / "vagas.json").write_text(json.dumps({"plataformas": {"micro1": "micro1"},
                                                 "vagas": [vaga(1, publicada=date.today().isoformat()), vaga(2, area="Saúde", publicada=date.today().isoformat())]}), encoding="utf-8")
    (site / "indicacoes.json").write_text(json.dumps(INDIC), encoding="utf-8")
    monkeypatch.setattr(newsletter, "VAGAS", site / "vagas.json")
    monkeypatch.setattr(newsletter, "INDIC", site / "indicacoes.json")
    monkeypatch.setattr(newsletter, "ESTADO", tmp_path / "estado.json")
    monkeypatch.setattr(newsletter, "CONFIG", tmp_path / "cfg.json")

    assert "não configurada" in newsletter.rodar()
    (tmp_path / "cfg.json").write_text(json.dumps({"endpoint": "https://script.google.com/macros/s/x/exec", "chave": "k"}))

    enviadas = []
    inscritos = [{"email": "a@ex.com", "token": "t1", "areas": ""}, {"email": "b@ex.com", "token": "t2", "areas": "Direito"},
                 {"email": "c@ex.com", "token": "t3", "areas": "Saúde"}]
    r = newsletter.rodar(enviar=enviadas.append, inscritos=inscritos)
    assert "2 e-mails enviados" in r
    assert [m["To"] for m in enviadas] == ["a@ex.com", "c@ex.com"]
    assert "acao=sair&t=t1" in enviadas[0]["List-Unsubscribe"]
    assert "já enviada hoje" in newsletter.rodar(enviar=enviadas.append, inscritos=inscritos)
    estado = json.loads((tmp_path / "estado.json").read_text())
    assert estado["anunciadas"] == ["micro1:1", "micro1:2"] and "a@ex.com" not in json.dumps(estado)


def test_ligar_valida_e_grava(tmp_path, monkeypatch):
    monkeypatch.setattr(newsletter, "CONFIG", tmp_path / "cfg.json")
    monkeypatch.setattr(newsletter, "buscar_inscritos", lambda cfg: [])
    site_json = tmp_path / "newsletter.json"
    site_json.write_text('{"endpoint": ""}', encoding="utf-8")
    assert "precisa ser" in newsletter.ligar("https://exemplo.com/x", "k" * 40, site_json)
    url = "https://script.google.com/macros/s/ABC/exec"
    assert "ligada" in newsletter.ligar(url, "k" * 64, site_json)
    assert json.loads(site_json.read_text())["endpoint"] == url
    assert json.loads((tmp_path / "cfg.json").read_text())["chave"] == "k" * 64
