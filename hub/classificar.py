"""Classifica a vaga por área e descobre se ela aceita gente do Brasil."""
from __future__ import annotations

import re

# Palavras-chave em inglês (as vagas são em inglês); casam no começo da palavra.
AREAS: list[tuple[str, list[str]]] = [
    ("Saúde", ["physician", "doctor", "nurse", "medical", "clinical", "pharmac", "dentist", "health",
               "therap", "radiolog", "inpatient", "coder", "coding specialist", "psychiatr", "patholog", "surgeon", "veterinar", "palliative"]),
    ("Direito", ["lawyer", "attorney", "legal", "law ", "paralegal", "compliance", "litigation", "jd "]),
    ("Finanças", ["finance", "financial", "accountant", "accounting", "banking", "investment", "cpa",
                  "audit", "tax ", "actuar", "equity", "trader", "economist", "compensation"]),
    ("Programação", ["software", "engineer", "developer", "python", "javascript", "typescript", "java ",
                     "coding", "react", "backend", "frontend", "devops", "data scien", "machine learning",
                     "sql", "golang", "rust", "c++", "full stack", "full-stack"]),
    ("Segurança e TI", ["security", "soc ", "cyber", "penetration", "network", "sysadmin", "cloud"]),
    ("Exatas", ["math", "physics", "chemist", "biolog", "statistic", "phd", "scientist", "stem "]),
    ("Idiomas e tradução", ["translat", "linguist", "language", "native", "portuguese", "spanish", "bilingual",
                            "localization", "fluent"]),
    ("Escrita e conteúdo", ["writer", "writing", "editor", "content", "copywrit", "journalis", "creative",
                            "author", "screenwrit"]),
    ("Negócios e atendimento", ["customer", "support", "retail", "marketing", "sales", "operations", "shopper",
                                "hospitality", "travel", "category manager", "cx ", "recruit", "talent", "hr ",
                                "product manager", "consultant", "excel"]),
    ("Educação", ["teacher", "tutor", "professor", "education", "instructor", "curriculum"]),
    ("Design e mídia", ["design", "3d", "3-d", "artist", "video", "animation", "photograph", "music", "audio", "voice", "actor"]),
]
OUTRAS = "Outras áreas"


def _pontos(texto: str, chaves: list[str]) -> int:
    return sum(len(re.findall(r"\b" + re.escape(k.strip()), texto)) for k in chaves)


def area_da_vaga(titulo: str, corpo: str = "") -> str:
    """O título pesa 5x o resto. Um empate fica com a área listada antes."""
    t, c = titulo.lower(), corpo.lower()
    melhor, pontos = OUTRAS, 0
    for area, chaves in AREAS:
        n = 5 * _pontos(t, chaves) + _pontos(c, chaves)
        if n > pontos:
            melhor, pontos = area, n
    return melhor


_BRASIL = {"brazil", "brasil", "bra", "br"}
_GLOBAL = {"worldwide", "global", "anywhere", "remote"}
_PAISES = {  # ISO3 e ISO2 que as plataformas usam -> nome em português
    "Estados Unidos": "USA US", "Canadá": "CAN CA", "Reino Unido": "GBR GB UK", "Brasil": "BRA BR",
    "Índia": "IND IN", "México": "MEX MX", "Alemanha": "DEU DE", "França": "FRA FR", "Espanha": "ESP ES",
    "Portugal": "PRT PT", "Austrália": "AUS AU", "Argentina": "ARG AR", "Colômbia": "COL CO", "Chile": "CHL CL",
    "Itália": "ITA IT", "Japão": "JPN JP", "Bolívia": "BOL BO", "Equador": "ECU EC", "Guiana": "GUY GY",
    "Paraguai": "PRY PY", "Peru": "PER PE", "Uruguai": "URY UY", "Irlanda": "IRL IE", "Holanda": "NLD NL",
    "Polônia": "POL PL", "Romênia": "ROU RO", "Bulgária": "BGR BG", "Eslováquia": "SVK SK", "Eslovênia": "SVN SI",
    "Sérvia": "SRB RS", "Estônia": "EST EE", "Turquia": "TUR TR", "Emirados Árabes": "ARE AE", "Egito": "EGY EG",
    "Jordânia": "JOR JO", "Singapura": "SGP SG", "Indonésia": "IDN ID", "Tailândia": "THA TH",
    "Nova Zelândia": "NZL NZ", "Costa Rica": "CRI CR", "Nigéria": "NGA NG", "El Salvador": "SLV SV",
    "Guatemala": "GTM GT", "Panamá": "PAN PA", "Dinamarca": "DNK DK", "Suécia": "SWE SE", "Noruega": "NOR NO",
    "Finlândia": "FIN FI", "Suíça": "CHE CH", "Áustria": "AUT AT", "Bélgica": "BEL BE", "Grécia": "GRC GR",
    "Israel": "ISR IL", "Coreia do Sul": "KOR KR", "China": "CHN CN", "Filipinas": "PHL PH", "Vietnã": "VNM VN",
    "Malásia": "MYS MY", "Paquistão": "PAK PK", "África do Sul": "ZAF ZA", "Quênia": "KEN KE",
    "República Tcheca": "CZE CZ", "Hungria": "HUN HU", "Ucrânia": "UKR UA", "Venezuela": "VEN VE",
    "República Dominicana": "DOM DO", "Porto Rico": "PRI PR", "Taiwan": "TWN TW", "Hong Kong": "HKG HK",
}
_ISO3 = {cod: nome for nome, cods in _PAISES.items() for cod in cods.split()}
_ISO3.update({"BRAZIL": "Brasil", "UNITED STATES": "Estados Unidos", "UNITED KINGDOM": "Reino Unido",
              "GERMANY": "Alemanha", "SPAIN": "Espanha", "FRANCE": "França", "ITALY": "Itália", "JAPAN": "Japão",
              "MEXICO": "México", "INDIA": "Índia", "CANADA": "Canadá"})


def paises_da_vaga(req) -> list[str]:
    if not req:
        return []
    itens = req if isinstance(req, list) else [req]
    out = []
    for it in itens:
        nome = it.get("name", "") if isinstance(it, dict) else str(it)
        nome = nome.strip()
        nome = _ISO3.get(nome.upper(), nome)
        if nome and nome not in out:
            out.append(nome)
    return out


def abre_brasil(paises: list[str]) -> str:
    """'sim' se o Brasil está na lista ou a vaga é global; 'nao' se há lista sem o Brasil;
    '?' se a plataforma não informou países."""
    if not paises:
        return "?"
    nomes = {re.sub(r"\s+", " ", p.lower()) for p in paises}
    if nomes & _BRASIL or nomes & _GLOBAL:
        return "sim"
    return "nao"
