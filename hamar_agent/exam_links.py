"""Explicit offline navigation only; never an alternative source approval.

Run with ``python -m hamar_agent.exam_links``. This module does not load the
municipal catalog, retrieve pages, accept questions, or generate model answers.
Topic labels are project-authored navigation, not copied municipal passages.
"""
import json


_BASE = "https://www.hamar.kommune.no/"
_LINKS = (
    ("hamar-sfo", "SFO", "skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/"),
    ("hamar-byggesak", "Byggesak", "byggesak/bygge-uten-a-soke/"),
    ("hamar-folkehelse", "Folkehelse", "folkehelse-kunnskapsgrunnlag/"),
    ("hamar-bibliotek", "Bibliotek", "kultur-og-aktivitet/hamar-bibliotek/"),
    ("hamar-kommuneplan", "Kommuneplan", "kommuneplan/kommuneplanens-samfunnsdel/"),
    ("hamar-drikkevann", "Drikkevann", "drikkevann/"),
    ("hamar-parkering", "Parkering", "parkering/parkeringsplasser-og-betaling/"),
    ("hamar-luftkvalitet", "Luftkvalitet", "klima/luftkvalitet-i-hamar/"),
)


def navigation():
    """Return reference links, without asserting approval or current facts."""
    return {
        "schema_version": 1,
        "mode": "exam_links_only",
        "source_approval": "not_asserted",
        "municipal_content_loaded": False,
        "model_used": False,
        "notice": "Lenker til offisielle sider. Ingen kildeaktivering, faktasvar eller AI-behandling. Les gjeldende informasjon hos kommunen.",
        "links": [{"source_id": sid, "topic": topic, "url": _BASE + path}
                  for sid, topic, path in _LINKS],
    }


def main():
    print(json.dumps(navigation(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
