"""Hamar service navigation, referenced from /meny/; not source approvals."""
from dataclasses import dataclass

OFFICIAL_HOME = "https://www.hamar.kommune.no/"
MENU_REFERENCE = "https://www.hamar.kommune.no/meny/"


@dataclass(frozen=True)
class Category:
    id: str
    title: str
    description: str


CATEGORIES = (
    Category("oppvekst", "Barnehage og skole", "Barnehage, skole og opplæring"),
    Category("bolig", "Bolig, eiendom og utbygging", "Byggesak, bolig og arealplaner"),
    Category("miljo", "By, miljø og næring", "Miljø, byutvikling og arbeidsliv"),
    Category("helse", "Helse, sosial og familie", "Helse, omsorg og sosiale tjenester"),
    Category("kultur", "Kultur og aktivitet", "Bibliotek, fritid og kulturtilbud"),
    Category("teknisk", "Parkering, veg og vann", "Parkering, veg, vann og avløp"),
    Category("politikk", "Politikk og administrasjon", "Lokaldemokrati, planer og kommunale tjenester"),
)
CATEGORY_IDS = frozenset(c.id for c in CATEGORIES)
