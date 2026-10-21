"""HTML extraction for manually reviewed snapshots, never a browser or crawler."""
from html.parser import HTMLParser
import re


class ExtractionError(ValueError):
    pass


class _ArticleParser(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "form", "aside", "template",
            "noscript", "svg", "iframe", "button", "select", "textarea"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    BLOCK = {"p", "div", "section", "article", "main", "h1", "h2", "h3", "h4", "li", "tr"}

    def __init__(self, content_tag):
        super().__init__(convert_charrefs=True)
        self.content_tag = content_tag
        self.stack = []
        self.parts = []
        self.roots = 0
        self.password = False
        self.noindex = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("type", "").lower() == "password":
            self.password = True
        if tag == "meta" and attrs.get("name", "").lower() in ("robots", "hamarkommuneagent"):
            directives = {d.strip() for d in attrs.get("content", "").lower().split(",")}
            if directives & {"noindex", "none"}:
                self.noindex = True
        active = any(t == self.content_tag for t, _ in self.stack)
        blocked = any(b for _, b in self.stack) or tag in self.SKIP or "hidden" in attrs or attrs.get("aria-hidden", "").lower() == "true"
        if tag == self.content_tag and not blocked:
            self.roots += 1
        if active and tag in self.BLOCK | {"br"} and not blocked:
            self.parts.append("\n")
        if tag not in self.VOID:
            self.stack.append((tag, blocked))

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.parts.append("\n")
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if any(t == self.content_tag for t, _ in self.stack) and not any(b for _, b in self.stack):
            self.parts.append(data)


def extract_html(html: str, *, content_tag: str = "main") -> tuple[str, ...]:
    if content_tag not in ("main", "article"):
        raise ExtractionError("Choose a reviewed main or article extraction boundary")
    if not isinstance(html, str) or len(html.encode("utf-8")) > 512 * 1024:
        raise ExtractionError("HTML exceeds extraction limits")
    parser = _ArticleParser(content_tag)
    parser.feed(html)
    parser.close()
    if parser.password or parser.noindex:
        raise ExtractionError("Login or noindex content is not eligible")
    if parser.roots != 1:
        raise ExtractionError("Expected exactly one reviewed content boundary")
    paragraphs = tuple(p for line in "".join(parser.parts).splitlines() if (p := " ".join(line.split())))
    if not paragraphs:
        raise ExtractionError("No eligible article text")
    # Defense in depth only; absence of these patterns is not a privacy guarantee.
    text = " ".join(paragraphs)
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\d)\d[\d ()+-]{6,}\d(?!\d)", text):
        raise ExtractionError("Possible personal/contact data; manual review required")
    return paragraphs


class _ServiceParser(_ArticleParser):
    # Retain textual service paragraphs only, never image captions or contacts.
    SKIP = _ArticleParser.SKIP | {"figcaption", "address"}


def service_candidates(html: str, *, content_tag: str = "main") -> tuple[str, ...]:
    """Transient review candidates, not an automatic privacy approval.

    Callers may retain only individually reviewed paragraph hashes. Unselected
    names and contacts must not enter the catalog, prompts, results or logs.
    """
    if content_tag not in ("main", "article") or not isinstance(html, str) or len(html.encode("utf-8")) > 512 * 1024:
        raise ExtractionError("Invalid reviewed extraction boundary or size")
    parser = _ServiceParser(content_tag)
    parser.feed(html); parser.close()
    if parser.password or parser.noindex or parser.roots != 1:
        raise ExtractionError("Login, noindex or ambiguous extraction boundary")
    paragraphs = tuple(dict.fromkeys(" ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip()))
    if not paragraphs:
        raise ExtractionError("No service paragraphs")
    return paragraphs


def privacy_check(text: str) -> None:
    """Conservative signals, supplemented by exact manually reviewed hashes.

    Ordinary prices/dates and time ranges are not mistaken for telephone
    numbers. This is defense in depth, not general named-entity detection.
    """
    patterns = (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
                r"(?i)\b(?:foto(?:graf)?|kontaktperson|saksbehandler|telefon|mobil|e-post|tlf)\s*[:.]",
                r"(?<!\d)(?:\+47\s*)?(?:\d{8}|\d{3} \d{2} \d{3}|\d{2} \d{2} \d{2} \d{2}|\d{11})(?!\d)")
    if any(re.search(pattern, text) for pattern in patterns):
        raise ExtractionError("Reviewed excerpt contains possible personal/contact information")


def extract_service_excerpts(html: str, reviewed_hashes, *, content_tag="main") -> tuple[str, ...]:
    """Exact allowlist of whole reviewed paragraphs; never auto-retain text."""
    import hashlib
    if not isinstance(reviewed_hashes, (tuple, list)) or not reviewed_hashes or len(reviewed_hashes) > 80:
        raise ExtractionError("Explicit reviewed paragraph hashes required")
    if any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in reviewed_hashes) or len(set(reviewed_hashes)) != len(reviewed_hashes):
        raise ExtractionError("Invalid or duplicate reviewed paragraph hash")
    candidates = {hashlib.sha256(text.encode("utf-8")).hexdigest(): text for text in service_candidates(html, content_tag=content_tag)}
    if any(digest not in candidates for digest in reviewed_hashes):
        raise ExtractionError("Reviewed excerpt changed or disappeared; renewed review required")
    paragraphs = tuple(candidates[digest] for digest in reviewed_hashes)
    for paragraph in paragraphs:
        privacy_check(paragraph)
    return paragraphs
