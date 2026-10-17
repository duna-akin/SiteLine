"""Quote verification: every extracted value's quote must appear verbatim in the change."""

from __future__ import annotations

import re
import unicodedata

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "‑": "-", "–": "-", "—": "-", " ": " "})


def normalize(text: str) -> str:
    """Forgive only typography: curly vs straight quotes, dashes, and runs of whitespace."""
    text = unicodedata.normalize("NFC", text).translate(_QUOTES)
    return re.sub(r"\s+", " ", text).strip()


def sources(change: dict, context: str = "") -> list[str]:
    """The change's own text, its tracked spans and comment, plus the agreement preamble
    (party names and status are often quoted from there)."""
    out = [change.get("original") or "", change.get("revised") or "", change.get("siteComment") or "", context]
    out += [s["text"] for s in change.get("segments", []) if s.get("type") in ("ins", "del")]
    return [normalize(s) for s in out if s]


def verify_quote(quote: str, change: dict, context: str = "") -> bool:
    q = normalize(quote)
    if len(q) < 3:
        return False
    return any(q in s for s in sources(change, context))
