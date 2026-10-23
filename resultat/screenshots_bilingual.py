"""Tospraklige bildetekster for uendrede nettleserskjermbilder."""
from pathlib import Path
from publish_bilingual import mdtable, write

BASE = Path(__file__).resolve().parent


def main():
    captions = [
        ("desktop.png", "1440×1100", "Forenklet forside før et spørsmål.", "Simplified homepage before a question."),
        ("desktop-answer.png", "1440×1100", "Kildebasert SFO-svar med synlig offisiell kilde.", "Source-grounded SFO answer with a visible official source."),
        ("building-permit-answer.png", "1440×1100", "Byggesakssvar med kildehenvisning.", "Building-service answer with a source reference."),
        ("natural-building-answer.png", "1440×1100", "Svar på det norske spørsmålet om å bygge uten å søke.", "Answer to the Norwegian question about building without an application."),
        ("tablet.png", "820×1180", "Søkeresultat i nettbrettvisning.", "Search result in the tablet viewport."),
        ("mobile.png", "390×844", "Søkeresultat i mobilvisning.", "Search result in the mobile viewport."),
        ("mobile-ai.png", "390×844", "Reelt modellbasert byggesakssvar med offisiell lenke i mobilvisning.", "Actual model-based building answer with an official link in the mobile viewport."),
    ]
    for lang, li in (("norsk", 0), ("english", 1)):
        headers = (["Skjermbilde", "Visningsflate px", "Bildetekst"], ["Screenshot", "Viewport px", "Caption"])[li]
        rows = [[f"[{name}](../logger/browser/{name})", viewport, (no, en)[li]] for name, viewport, no, en in captions]
        title = ("Nettleserevidens og figurtekster", "Browser evidence and figure captions")[li]
        note = (
            "Dato: 2026-10-23. Kilde: logger/browser/browser-check.txt og logger/browser-run.json. Dette er originale automatiserte Chrome-skjermbilder. Appens norske grensesnitt er bevart i begge språkversjonene; ingen skjermbilder er oversatt, retusjert eller konstruert. Visningsflatene er emulert, ikke fysiske enheter. Testen kontrollerer kildevisning, layout og forventede tilstander, ikke menneskelig opplevd brukervennlighet. Figurteksten kan brukes sammen med originalbildet i den engelske rapporten.",
            "Date: 2026-10-23. Source: logger/browser/browser-check.txt and logger/browser-run.json. These are original automated Chrome screenshots. The application's Norwegian interface is preserved in both language versions; screenshots were not translated, retouched or synthesized. Viewports are emulated, not physical devices. The test checks source display, layout and expected states, not human-perceived usability. The English captions can accompany the original images in the English report.")[li]
        write(BASE / lang / "21_browser_evidence.md", "# " + title + "\n\n" + note + "\n\n" + mdtable(headers, rows))
    print("Seven original screenshot captions provided in both languages.")


if __name__ == "__main__":
    main()
