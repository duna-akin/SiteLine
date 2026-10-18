"""Quote verification: every extracted value's quote must appear verbatim in the change."""

from __future__ import annotations

import re
import unicodedata

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "‑": "-", "–": "-", "—": "-", " ": " "})


def normalize(text: str) -> str:
    """Forgive only typography: curly vs straight quotes, dashes, and runs of whitespace."""
    text = unicodedata.normalize("NFC", text).translate(_QUOTES)
    return re.sub(r"\s+", " ", text).strip()


def unwrap(quote: str) -> str:
    """A normalized quote without the quotation marks the model sometimes wraps it in: “like this”."""
    q = normalize(quote)
    while len(q) >= 2 and q[0] == q[-1] and q[0] in "\"'":
        q = q[1:-1].strip()
    return q


def sources(change: dict, context: str = "") -> list[str]:
    """The change's own text, its tracked spans and comment, plus the agreement preamble
    (party names and status are often quoted from there)."""
    out = [change.get("original") or "", change.get("revised") or "", change.get("siteComment") or "", context]
    out += [s["text"] for s in change.get("segments", []) if s.get("type") in ("ins", "del")]
    return [normalize(s) for s in out if s]


def verify_quote(quote: str, change: dict, context: str = "") -> bool:
    """Verbatim, forgiving only typography and wrapping quotation marks."""
    texts = sources(change, context)
    return any(len(q) >= 3 and any(q in s for s in texts) for q in {normalize(quote), unwrap(quote)})


# Fields whose value is a number; that number must appear in the value's own quote.
NUMERIC_FIELDS = {"net_days", "start_up_fee_pct", "survival_years", "review_days", "site_notice_days", "patent_delay_days"}
_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    rest = n % 100
    return f"{_ONES[n // 100]} hundred" + (f" {_words(rest)}" if rest else "")


def number_in_quote(value: str, quote: str) -> bool:
    """True when the number in `value` appears in `quote`, as digits or spelled out."""
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not m:
        return False
    num = float(m.group())
    q = normalize(quote).lower()
    if any(float(d) == num for d in re.findall(r"\d+(?:\.\d+)?", q)):
        return True
    if num.is_integer() and 0 <= num < 1000:
        return re.search(rf"(?<![a-z-]){re.escape(_words(int(num)))}(?![a-z-])", q) is not None
    return False


def verify_value(v: dict, change: dict, context: str = "") -> bool:
    """The value's quote is verbatim in the change and, for a numeric field, states that number."""
    if not verify_quote(v["quote"], change, context):
        return False
    return v["field"] not in NUMERIC_FIELDS or number_in_quote(v["value"], v["quote"])
