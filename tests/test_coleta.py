from pathlib import Path

from hub.classificar import abre_brasil, area_da_vaga, paises_da_vaga
from hub.coleta import Plataforma, coletar, job_posting, normalizar, texto_limpo, urls_do_sitemap

FIX = Path(__file__).parent / "fixtures"


def test_jobposting_da_mercor_no_script_ldjson():
    jp = job_posting((FIX / "mercor.html").read_text(encoding="utf-8"))
    assert jp["title"] == "Palliative Care Physician - Canada"
    v = normalizar(jp, "https://work.mercor.com/jobs/list_X/a", "mercor", "list_X")
    assert (v["valorMin"], v["moeda"], v["unidade"]) == (175, "USD", "hora")
    assert v["paises"] == ["Canadá"] and v["brasil"] == "nao"
    assert v["area"] == "Saúde"
    assert v["expira"] == "2026-12-26"


def test_jobposting_da_micro1_dentro_do_payload_do_next():
    jp = job_posting((FIX / "micro1.html").read_text(encoding="utf-8"))
    assert jp["title"] == "Hospitality Worker (Toast POS User)"
    v = normalizar(jp, "https://jobs.micro1.ai/post/abc", "micro1", "abc")
    assert v["valorMin"] is None
    assert "Toast POS" in v["habilidades"]
    assert "Bangladesh" in v["paises"]
    assert v["resumo"] and "<" not in v["resumo"]


def test_brasil():
    assert abre_brasil([]) == "?"
    assert abre_brasil(["Brazil", "India"]) == "sim"
    assert abre_brasil(paises_da_vaga([{"name": "BRA"}])) == "sim"
    assert abre_brasil(["Worldwide"]) == "sim"
    assert abre_brasil(["Estados Unidos"]) == "nao"


def test_areas():
    casos = {
        "Senior Software Engineer (Python)": "Programação",
        "Corporate Lawyer - Contracts": "Direito",
        "Registered Nurse": "Saúde",
        "Brazilian Portuguese Language Expert": "Idiomas e tradução",
        "SOC Investigation Specialist": "Segurança e TI",
        "Voice Actor": "Design e mídia",
        "Generalist": "Outras áreas",
    }
    for titulo, area in casos.items():
        assert area_da_vaga(titulo) == area, titulo


def test_texto_limpo_corta_na_palavra():
    t = texto_limpo("<p>" + "palavra " * 100 + "</p>", 50)
    assert len(t) <= 50 and t.endswith("…") and "<" not in t


def test_sitemap_filtra_paginas_de_vaga():
    xml = "<loc>https://x.com/jobs/list_AB1/a</loc><loc>https://x.com/jobs/apply/x</loc><loc>https://x.com/jobs/list_AB1/a</loc>"
    assert urls_do_sitemap(xml, r"/jobs/list_[A-Za-z0-9_-]+") == ["https://x.com/jobs/list_AB1/a"]


def test_coleta_inclui_novas_e_retira_encerradas():
    pagina = (FIX / "mercor.html").read_text(encoding="utf-8")
    sitemap = "<loc>https://w.com/jobs/list_NOVA/x</loc><loc>https://w.com/jobs/list_FICA/y</loc>"
    plat = Plataforma("mercor", "Mercor", "https://w.com/sitemap.xml", r"/jobs/list_",
                      lambda u: u.split("/jobs/")[1].split("/")[0])
    baixadas = []

    def falso(url):
        baixadas.append(url)
        return sitemap if url.endswith("sitemap.xml") else pagina

    atuais = {
        "mercor:list_FICA": {"id": "mercor:list_FICA", "plataforma": "mercor", "expira": ""},
        "mercor:list_SAIU": {"id": "mercor:list_SAIU", "plataforma": "mercor", "expira": ""},
    }
    vagas, r = coletar(atuais, [plat], baixar=falso, pausa=0, log=lambda *_: None)
    assert set(vagas) == {"mercor:list_FICA", "mercor:list_NOVA"}
    assert r["novas"] == ["mercor:list_NOVA"] and r["removidas"] == ["mercor:list_SAIU"]
    assert "https://w.com/jobs/list_FICA/y" not in baixadas      # a que já tínhamos não é baixada de novo


def test_sitemap_fora_do_ar_mantem_as_vagas():
    plat = Plataforma("mercor", "Mercor", "https://w.com/sitemap.xml", r"/jobs/", lambda u: u)

    def quebra(url):
        raise OSError("fora do ar")

    atuais = {"mercor:a": {"id": "mercor:a", "plataforma": "mercor", "expira": ""}}
    vagas, r = coletar(atuais, [plat], baixar=quebra, pausa=0, log=lambda *_: None)
    assert vagas == atuais and r["erros"] == 1


def test_listagem_parcial_reconfere_em_vez_de_remover():
    from hub.coleta import Plataforma
    plat = Plataforma("parcial", "Parcial", listar=lambda b: ["https://a.com/jobs/nova"],
                      extrair=lambda pag, url, nome, id_: None if pag == "fechada" else
                      {"id": f"{nome}:{id_}", "plataforma": nome, "url": url, "expira": ""},
                      lista_completa=False)
    paginas = {"https://a.com/jobs/aberta": "ok", "https://a.com/jobs/fechada": "fechada", "https://a.com/jobs/nova": "ok"}
    atuais = {f"parcial:{k}": {"id": f"parcial:{k}", "plataforma": "parcial", "url": f"https://a.com/jobs/{k}",
                                "expira": "", "conferidaEm": "2000-01-01"} for k in ("aberta", "fechada")}
    vagas, r = coletar(atuais, [plat], baixar=lambda u: paginas[u], pausa=0, log=lambda *_: None)
    assert set(vagas) == {"parcial:aberta", "parcial:nova"}
    assert r["removidas"] == ["parcial:fechada"]
