"""Conservative robots policy: specific rules override broad Allow directives."""
import math
import re
from urllib.parse import urlsplit


def _octets(value):
    # RFC 9309: decode unreserved percent octets, preserve reserved encodings.
    def encoded(match):
        byte = int(match.group(1), 16)
        return chr(byte) if chr(byte) in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~" else "%" + match.group(1).upper()
    value = re.sub(r"%([0-9a-fA-F]{2})", encoded, value)
    return "".join(char if ord(char) < 128 else "".join("%%%02X" % byte for byte in char.encode("utf-8")) for char in value)


def robots_interval(raw: bytes, url: str, agent: str) -> float:
    """Refuse disallowed paths; combine equally specific groups and rate limits.

    Empty Disallow has no effect. Longest matching rule wins; Allow wins ties.
    Missing or malformed policy is never treated as permission by the caller.
    """
    text = raw.decode("utf-8-sig", errors="strict")
    groups, names, directives = [], [], []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError("Malformed robots directive; review required")
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if directives:
                groups.append((names, directives)); names, directives = [], []
            if not value or not re.fullmatch(r"[A-Za-z0-9_.*-]+", value):
                raise ValueError("Invalid robots agent")
            names.append(value.lower())
        elif names:
            directives.append((key, value))
    if names:
        groups.append((names, directives))
    product = agent.split("/", 1)[0].lower()
    selected, specificity = [], -1
    for names, directives in groups:
        score = max((0 if name == "*" else len(name) for name in names if name == "*" or name in product), default=-1)
        if score > specificity:
            selected, specificity = [], score
        if score >= 0 and score == specificity:
            selected.extend(directives)
    path = _octets(urlsplit(url).path or "/")
    matches, interval = [], 2.0
    for key, value in selected:
        if key in ("allow", "disallow"):
            if not value:
                continue
            if not value.startswith("/"):
                raise ValueError("Unsupported robots path; review required")
            rule = _octets(value)
            anchored = rule.endswith("$")
            if anchored:
                rule = rule[:-1]
            expression = "^" + ".*".join(re.escape(part) for part in rule.split("*")) + ("$" if anchored else "")
            if re.search(expression, path):
                matches.append((len(rule.replace("*", "")), key == "allow"))
        elif key == "crawl-delay":
            try:
                delay = float(value)
            except ValueError:
                raise ValueError("Invalid robots delay") from None
            if not math.isfinite(delay) or delay < 0:
                raise ValueError("Invalid robots delay")
            interval = max(interval, delay)
        elif key == "request-rate":
            if not re.fullmatch(r"[1-9][0-9]*/[1-9][0-9]*", value):
                raise ValueError("Unsupported robots request rate")
            requests, seconds = map(int, value.split("/"))
            interval = max(interval, seconds / requests)
    if matches and not max(matches)[1]:
        raise ValueError("robots.txt disallows this source")
    if interval > 60:
        raise ValueError("Robots rate policy requires a separate scheduling decision")
    return interval
