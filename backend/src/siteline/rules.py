"""Rules engine: one outcome per change, from extracted values and the playbook.

Order: system checks (failed quote, low confidence, extraction error, conflicting values), then every
playbook position of the change's clause, then terms no playbook rule covers (SYS-NOVEL, human review,
only where no position escalates). Every number comes from the playbook's limits, and every outcome
carries the ID and text of the rule that fired. Counter-proposal text comes from fixed substitutions on
the site's own wording or the form's text; Siteline does not draft new legal language (PRD non-goal).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from siteline.playbook import SPONSOR, Playbook
from siteline.priority import describe
from siteline.verify import _words

LOW_CONFIDENCE = 0.80

# Every non-system rule ID the engine can return; the playbook lists each exactly once.
RULE_IDS = frozenset({
    "PAY-A1", "PAY-A2", "PAY-E1", "PAY-A3", "PAY-A3P", "PAY-C2", "PAY-E2", "PAY-A4", "PAY-C3", "PAY-E3",
    "PAY-A5", "PAY-C4", "PAY-A6", "PAY-C5", "PAY-E4",
    "CONF-A1", "CONF-A2", "CONF-A2P", "CONF-C1", "CONF-E1", "CONF-A3", "CONF-E2", "CONF-C2", "CONF-C3", "CONF-A4", "CONF-E3",
    "IND-A1", "IND-A2", "IND-C1", "IND-E1", "IND-E2", "IND-A3", "IND-C2", "IND-E3", "IND-A4",
    "SI-A3", "SI-E1", "SI-A1", "SI-A2", "SI-E2", "SI-E3",
    "PUB-A1", "PUB-A2P", "PUB-C1", "PUB-E2", "PUB-E3", "PUB-A3", "PUB-E1", "PUB-A4", "PUB-C2",
    "IP-A1", "IP-E1", "IP-A2", "IP-A3", "IP-C1",
    "DP-E1", "DP-E2", "DP-A2", "DP-A3", "DP-C1", "DP-E3",
    "TERM-A0", "TERM-A1", "TERM-C1", "TERM-E2", "TERM-A2", "TERM-E1", "TERM-A3", "TERM-C2",
    "GOV-A1", "GOV-A2", "GOV-E2", "GOV-C1", "GOV-C2", "GOV-E1",
})
# Rule IDs older decisions may carry, and the rule that replaced each
RULE_ALIASES = {"PAY-F2": "PAY-C2", "CONF-F1": "CONF-C1", "IND-F1": "IND-C1", "PUB-F1": "PUB-C1", "TERM-F1": "TERM-C1",
                "GOV-F1": "GOV-C1", "PUB-A2": "PUB-A1"}

# The bands site priority may widen: (clause, position, accept-line limit, floor limit, label, unit, rule,
# direction). "up" means higher values are worse for Sponsor (a fee); "down" means lower ones are (a
# term). Leniency moves only the accept line, by a share of the gap to the escalate floor (priority.py
# caps it at 0.75); a band whose floor equals its accept line has nothing to widen.
BAND_SOURCES = {
    "start_up_fee_pct": ("payment_terms", "start_up_fee", "standard", "escalate_above", "Start-up fee", "%", "PAY-A3P", "up"),
    "survival_years": ("confidentiality", "survival", "accept_min", "escalate_below", "Confidentiality survival", " years", "CONF-A2P", "down"),
    "review_days": ("publication", "review", "standard", "escalate_below", "Publication review", " days", "PUB-A2P", "down"),
}
WIDENED_CLAUSES = {src[0] for src in BAND_SOURCES.values()}
STRICTNESS = {"accept": 0, "counter": 1, "escalate": 2}
US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire",
    "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia",
}
# Fields where "false" only says a term adverse to Sponsor is absent (unlike, say, a non-refundable fee)
ABSENT_WHEN_FALSE = {
    "discloses_to_affiliates", "marking_required", "public_records_disclosure", "mutual_indemnity", "covers_lost_wages",
    "covers_pain_and_suffering", "covers_travel", "removes_injury_exclusions", "review_window_open_ended",
    "site_may_file_patents", "requires_baa", "blocks_secondary_research", "ml_training_restriction",
    "restricts_data_transfer", "termination_for_convenience", "arbitration_abroad", "arbitration_domestic",
    "sovereign_immunity_waiver_required",
}


@dataclass
class Verdict:
    outcome: str  # accept | counter | escalate | human_review
    rule_id: str
    rule_text: str
    counter_text: str | None = None
    # What the counter-proposal says if an approver answers 2 ("counter with the fallback")
    fallback_text: str | None = None


def _num(v: str | None) -> float | None:
    if v is None:
        return None
    m = re.search(r"-?\d+(\.\d+)?", str(v))
    return float(m.group()) if m else None


def _bool(v: str | None) -> bool | None:
    if v is None:
        return None
    s = re.sub(r"[^a-z0-9]", "", str(v).lower())  # forgive stray punctuation such as ">true"
    if s in ("true", "yes", "1"):
        return True
    if s in ("false", "no", "0"):
        return False
    return None


def _norm(v: str | None) -> str:
    return (v or "").strip().lower().replace(" ", "_").replace("-", "_")


def bands(playbook: dict | None = None) -> dict[str, dict]:
    pb = Playbook(playbook)
    return {field: {"clause": c, "label": label, "unit": unit, "ruleId": rid, "direction": direction,
                    "standard": pb.limit(c, p, line), "floor": pb.limit(c, p, floor)}
            for field, (c, p, line, floor, label, unit, rid, direction) in BAND_SOURCES.items()}


def band_limit(field: str, share: float, playbook: dict | None = None) -> float:
    b = bands(playbook)[field]
    return round(b["standard"] + share * (b["floor"] - b["standard"]), 2)


def _widened(field: str, value: float, lenient: dict | None, pb: Playbook) -> Verdict | None:
    """Accept `value` when site priority widens this band far enough to cover it."""
    if not lenient or lenient["share"] <= 0:
        return None
    b = bands(pb.pb)[field]
    if b["floor"] == b["standard"]:
        return None
    limit = round(b["standard"] + lenient["share"] * (b["floor"] - b["standard"]), 2)
    if not (value <= limit if b["direction"] == "up" else value >= limit):
        return None
    why = describe(lenient)
    return Verdict(
        "accept",
        b["ruleId"],
        f"{why[0].upper()}{why[1:]} → {b['label'].lower()} of {value:g}{b['unit']} is within the widened "
        f"{limit:g}{b['unit']} band (standard {b['standard']:g}{b['unit']}; escalate floor {b['floor']:g}{b['unit']} unchanged).",
    )


# ---- counter-text substitutions on the site's revised wording -----------------------

_NUMWORD = r"(?:[A-Za-z]+(?:-[A-Za-z]+)?\s+)?\(\d+\)|\d+"


def _qty(n: float) -> str:
    """'thirty (30)': how the form writes a number."""
    return f"{_words(int(n))} ({int(n)})" if float(n).is_integer() else f"{n:g}"


def _replace_quantity(text: str, unit: str, new: str) -> str | None:
    """Replace the first '<words> (N) <unit>' / 'N <unit>' with `new <unit>`."""
    pattern = re.compile(rf"({_NUMWORD})(\s+){unit}", re.IGNORECASE)
    if not pattern.search(text):
        return None
    return pattern.sub(lambda m: f"{new}{m.group(2)}{unit}", text, count=1)


def _replace_percent(text: str, new: str) -> str | None:
    pattern = re.compile(r"(?:[A-Za-z]+(?:-[A-Za-z]+)?\s+percent\s+)?\(\d+(?:\.\d+)?%\)|\d+(?:\.\d+)?\s?%", re.IGNORECASE)
    if not pattern.search(text):
        return None
    return pattern.sub(new, text, count=1)


def _pct(n: float) -> str:
    return f"{_words(int(n))} percent ({int(n)}%)" if float(n).is_integer() else f"{n:g}%"


def _drop_phrase(text: str, pattern: str) -> str | None:
    new = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)
    return new if new != text else None


# ---- playbook positions -------------------------------------------------------------------
# One function per position: (values, change, limit) -> Verdict | None, where limit(key) reads the
# position's limit from the playbook in force. `lenient` and the playbook view reach the three
# widened bands through the closure in _decide_clause.

Limit = Callable[[str], float]
PositionRule = Callable[..., "Verdict | None"]
POSITIONS: dict[tuple[str, str], PositionRule] = {}
# What each position's function needs from the playbook: the rule IDs it returns and the limits it
# reads. validate_playbook checks a playbook against this, so a saved playbook always runs.
ENGINE: dict[tuple[str, str], dict[str, frozenset[str]]] = {}


def position(clause: str, pid: str, rules: set[str], limits: set[str] = frozenset()) -> Callable[[PositionRule], PositionRule]:
    def register(fn: PositionRule) -> PositionRule:
        POSITIONS[(clause, pid)] = fn
        ENGINE[(clause, pid)] = {"rules": frozenset(rules), "limits": frozenset(limits)}
        return fn

    return register


@position("payment_terms", "net_days", {"PAY-A1", "PAY-A2", "PAY-E1"}, {"accept_min", "standard"})
def _net_days(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    net = _num(v.get("net_days"))
    if net is None:
        return None
    if net < lim("accept_min"):
        fb = _replace_quantity(ch["revised"], "days", _qty(lim("accept_min")))
        return Verdict("escalate", "PAY-E1", f"Net {net:g} is under {lim('accept_min'):g} days → escalate to Finance.", ch["original"], fb)
    if net < lim("standard"):
        return Verdict("accept", "PAY-A2", f"Net {net:g} is within the pre-approved Net {lim('accept_min'):g} fallback.")
    return Verdict("accept", "PAY-A1", f"Net {net:g} meets the Net {lim('standard'):g} standard.")


@position("payment_terms", "start_up_fee", {"PAY-A3", "PAY-A3P", "PAY-C2", "PAY-E2"}, {"escalate_above", "standard"})
def _start_up_fee(v: dict, ch: dict, lim: Limit, widen: Callable, **_) -> Verdict | None:
    fee = _num(v.get("start_up_fee_pct"))
    if fee is None:
        return None
    std, top = lim("standard"), lim("escalate_above")
    refundable = _bool(v.get("start_up_fee_refundable"))
    counter = _replace_percent(ch["revised"], _pct(std))
    if counter:
        counter = counter.replace("non-refundable ", "").rstrip(".") + ", refundable pro rata if no subject is enrolled."
    if fee > top and refundable is not True:
        return Verdict("escalate", "PAY-E2", f"Non-refundable start-up fee of {fee:g}% is above {top:g}% → escalate to Finance.", ch["original"], counter)
    if fee > std:
        if widened := widen("start_up_fee_pct", fee):
            return widened
        return Verdict("counter", "PAY-C2", f"Start-up fee of {fee:g}% is above {std:g}% → counter at {std:g}%, refundable pro rata if no subject is enrolled.", counter)
    return Verdict("accept", "PAY-A3", f"Start-up fee of {fee:g}% is within the {std:g}% standard.")


@position("payment_terms", "overhead", {"PAY-A4", "PAY-C3", "PAY-E3"}, {"escalate_above", "standard"})
def _overhead(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    rate = _num(v.get("overhead_pct"))
    if rate is None:
        return None
    std, top = lim("standard"), lim("escalate_above")
    counter = _replace_percent(ch["revised"], _pct(std))
    if rate > top:
        return Verdict("escalate", "PAY-E3", f"Overhead of {rate:g}% is above {top:g}% → escalate to Finance.", ch["original"], counter)
    if rate > std:
        return Verdict("counter", "PAY-C3", f"Overhead of {rate:g}% is above the {std:g}% standard → counter at {std:g}%.", counter)
    return Verdict("accept", "PAY-A4", f"Overhead of {rate:g}% is within the {std:g}% standard.")


@position("payment_terms", "holdback", {"PAY-A5", "PAY-C4"}, {"accept_min", "standard"})
def _holdback(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    held = _num(v.get("holdback_pct"))
    if held is None:
        return None
    if held < lim("accept_min"):
        what = "removed" if held == 0 else f"cut to {held:g}%"
        return Verdict("counter", "PAY-C4", f"Holdback {what}, under {lim('accept_min'):g}% → restore the form’s {lim('standard'):g}% holdback.", ch["original"])
    return Verdict("accept", "PAY-A5", f"Holdback of {held:g}% is within the {lim('accept_min'):g}% fallback.")


@position("payment_terms", "screen_failures", {"PAY-A6", "PAY-C5", "PAY-E4"}, {"escalate_above", "standard"})
def _screen_failures(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    raw = v.get("screen_failures_per_enrolled")
    if raw is None:
        return None
    ratio = None if _norm(raw) == "uncapped" else _num(raw)
    std, top = lim("standard"), lim("escalate_above")
    if ratio is None or ratio > top:
        what = "uncapped" if ratio is None else f"{ratio:g} per enrolled subject"
        return Verdict("escalate", "PAY-E4", f"Screen failures paid {what}, above {top:g} → escalate to Finance.", ch["original"], ch["original"])
    if ratio > std:
        return Verdict("counter", "PAY-C5", f"Screen failures paid at {ratio:g} per enrolled subject, above {std:g} → hold the form’s ratio.", ch["original"])
    return Verdict("accept", "PAY-A6", f"Screen failures paid at {ratio:g} per enrolled subject, within {std:g}.")


@position("confidentiality", "survival", {"CONF-A1", "CONF-A2", "CONF-A2P", "CONF-C1", "CONF-E1"}, {"accept_min", "escalate_below", "standard"})
def _survival(v: dict, ch: dict, lim: Limit, widen: Callable, **_) -> Verdict | None:
    years = _num(v.get("survival_years"))
    if years is None:
        return None
    floor, fallback, std = lim("escalate_below"), lim("accept_min"), lim("standard")
    counter = _replace_quantity(ch["revised"], "years", _qty(fallback))
    if years < floor:
        return Verdict("escalate", "CONF-E1", f"Survival of {years:g} years is under {floor:g} → escalate to Legal.", ch["original"], counter)
    if years < fallback:
        if widened := widen("survival_years", years):
            return widened
        return Verdict("counter", "CONF-C1", f"Survival of {years:g} years is between {floor:g} and {fallback:g} → counter with the {fallback:g}-year fallback.", counter)
    if years < std:
        return Verdict("accept", "CONF-A2", f"Survival of {years:g} years meets the pre-approved {fallback:g}-year fallback.")
    return Verdict("accept", "CONF-A1", f"Survival of {years:g} years meets the {std:g}-year standard.")


@position("confidentiality", "trade_secrets", {"CONF-A3", "CONF-E2"})
def _trade_secrets(v: dict, ch: dict, **_) -> Verdict | None:
    kept = _bool(v.get("trade_secrets_perpetual"))
    if kept is False:
        return Verdict("escalate", "CONF-E2", "Trade secrets lose perpetual protection → escalate to Legal.", ch["original"])
    if kept:
        return Verdict("accept", "CONF-A3", "Trade secrets stay protected without end → matches the standard.")
    return None


@position("confidentiality", "affiliates", {"CONF-C2"})
def _affiliates(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("discloses_to_affiliates")):
        return Verdict("counter", "CONF-C2", "Disclosure widened to affiliates or collaborators → restore the form’s need-to-know recipients.", ch["original"])
    return None


@position("confidentiality", "marking", {"CONF-C3"})
def _marking(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("marking_required")):
        return Verdict("counter", "CONF-C3", "Protection limited to marked information → restore the form’s definition.", ch["original"])
    return None


@position("confidentiality", "public_records", {"CONF-A4", "CONF-E3"})
def _public_records(v: dict, ch: dict, **_) -> Verdict | None:
    if not _bool(v.get("public_records_disclosure")):
        return None
    public, notice = _bool(v.get("institution_is_public")), _bool(v.get("public_records_notice"))
    if public is False or notice is False:
        why = "a private institution" if public is False else "no notice to Sponsor before disclosure"
        return Verdict("escalate", "CONF-E3", f"Public-records disclosure with {why} → escalate to Legal.", ch["original"])
    if public and notice:
        return Verdict("accept", "CONF-A4", "A public institution discloses under its public-records law after notice to Sponsor → accept.")
    return None


@position("indemnification", "carve_out", {"IND-A1", "IND-A2", "IND-C1", "IND-E1"})
def _carve_out(v: dict, ch: dict, **_) -> Verdict | None:
    carve = _norm(v.get("carve_out_standard"))
    if carve == "none":
        return Verdict("escalate", "IND-E1", "Site removes the negligence carve-out → escalate to Legal.", ch["original"])
    if carve.startswith("gross"):
        if _bool(v.get("adjudication_required")):
            counter = _drop_phrase(ch["revised"], r",?\s*as finally adjudicated")
            return Verdict("counter", "IND-C1", "Carve-out narrowed to gross negligence → accept the fallback wording and strike “as finally adjudicated”.", counter)
        return Verdict("accept", "IND-A2", "Carve-out narrowed to gross negligence or willful misconduct → matches the pre-approved fallback.")
    if carve == "negligence":
        return Verdict("accept", "IND-A1", "Negligence carve-out kept → matches the standard.")
    return None


@position("indemnification", "mutual", {"IND-E2"})
def _mutual(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("mutual_indemnity")):
        return Verdict("escalate", "IND-E2", "Site adds mutual indemnity → escalate to Legal.", ch["original"])
    return None


@position("indemnification", "claim_notice", {"IND-A3", "IND-C2"}, {"accept_max"})
def _claim_notice(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    days = _num(v.get("claim_notice_days"))
    if days is None:
        return None
    cap = lim("accept_max")
    if days > cap:
        return Verdict("counter", "IND-C2", f"Claim notice within {days:g} days is later than {cap:g} → counter at {cap:g} days.",
                       _replace_quantity(ch["revised"], "days", _qty(cap)))
    return Verdict("accept", "IND-A3", f"Claim notice within {days:g} days is within {cap:g}.")


@position("indemnification", "defense", {"IND-E3"})
def _defense(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("sponsor_controls_defense")) is False:
        return Verdict("escalate", "IND-E3", "Sponsor loses control of the defense or settlement → escalate to Legal.", ch["original"])
    return None


@position("indemnification", "additional_insured", {"IND-A4"})
def _additional_insured(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("additional_insured")):
        return Verdict("accept", "IND-A4", "Site named as additional insured on Sponsor’s policy → accepted.")
    return None


@position("subject_injury", "covered_costs", {"SI-A3", "SI-E1"})
def _covered_costs(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("covers_lost_wages")) or _bool(v.get("covers_pain_and_suffering")):
        counter = _drop_phrase(ch["revised"], r",?\s*including lost wages[^,.;]*,?") or ch["original"]
        return Verdict("escalate", "SI-E1", "Lost wages or pain and suffering added to subject-injury coverage → escalate to Finance.", ch["original"], counter)
    if _bool(v.get("covers_travel")):
        return Verdict("accept", "SI-A3", "Reasonable travel costs to treatment for a Study Injury → accepted.")
    return None


@position("subject_injury", "coordination", {"SI-A1", "SI-A2"})
def _coordination(v: dict, ch: dict, **_) -> Verdict | None:
    coord = _norm(v.get("coordination_with_insurance"))
    if coord == "sponsor_pays_first":
        return Verdict("accept", "SI-A2", "Sponsor pays first without coordinating with insurance → matches the pre-approved fallback.")
    if coord == "net_of_insurance":
        return Verdict("accept", "SI-A1", "Reimbursement net of subject insurance → matches the standard.")
    return None


@position("subject_injury", "cap", {"SI-E2"})
def _cap(v: dict, ch: dict, **_) -> Verdict | None:
    if _norm(v.get("reimbursement_cap")) == "uncapped":
        return Verdict("escalate", "SI-E2", "Uncapped subject-injury reimbursement → escalate to Finance.", ch["original"])
    return None


@position("subject_injury", "exclusions", {"SI-E3"})
def _exclusions(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("removes_injury_exclusions")):
        return Verdict("escalate", "SI-E3", "Subject-injury exclusions deleted → escalate to Finance.", ch["original"], ch["original"])
    return None


@position("publication", "review", {"PUB-A1", "PUB-A2P", "PUB-C1", "PUB-E2", "PUB-E3"}, {"escalate_below", "standard"})
def _review(v: dict, ch: dict, lim: Limit, widen: Callable, **_) -> Verdict | None:
    days = _num(v.get("review_days"))
    floor, std = lim("escalate_below"), lim("standard")
    if days is not None and days < floor:
        fb = _replace_quantity(ch["revised"], "days", _qty(std))
        return Verdict("escalate", "PUB-E2", f"Review window of {days:g} days is under {floor:g} → escalate to Legal.", ch["original"], fb)
    if _bool(v.get("review_window_open_ended")):
        return Verdict("escalate", "PUB-E3", "Open-ended review window (“or as otherwise agreed”) → escalate to Legal.", ch["original"])
    if days is None:
        return None
    if days < std:
        if widened := widen("review_days", days):
            return widened
        counter = _replace_quantity(ch["revised"], "days", _qty(std))
        return Verdict("counter", "PUB-C1", f"Review window of {days:g} days is under the {std:g}-day standard → counter at {std:g} days.", counter)
    return Verdict("accept", "PUB-A1", f"Review window of {days:g} days meets the {std:g}-day standard.")


@position("publication", "patent_delay", {"PUB-A3", "PUB-E1"})
def _patent_delay(v: dict, ch: dict, **_) -> Verdict | None:
    delay = _norm(v.get("patent_delay"))
    if delay == "removed":
        return Verdict("escalate", "PUB-E1", "Patent delay removed → escalate to Legal.", ch["original"])
    if delay == "retained":
        return Verdict("accept", "PUB-A3", "Patent delay kept → matches the standard.")
    return None


@position("publication", "multisite", {"PUB-A4", "PUB-C2"}, {"accept_min", "standard"})
def _multisite(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    months = _num(v.get("multisite_wait_months"))
    if months is None:
        return None
    fallback, std = lim("accept_min"), lim("standard")
    if months < fallback:
        return Verdict("counter", "PUB-C2", f"Multi-site wait of {months:g} months is under {fallback:g} → counter at {std:g} months.",
                       _replace_quantity(ch["revised"], "months", _qty(std)))
    return Verdict("accept", "PUB-A4", f"Multi-site wait of {months:g} months is within the {fallback:g}-month fallback.")


@position("intellectual_property", "inventions", {"IP-A1", "IP-E1"})
def _inventions(v: dict, ch: dict, **_) -> Verdict | None:
    own = _norm(v.get("invention_ownership"))
    if own in ("joint", "institution"):
        return Verdict("escalate", "IP-E1", f"Site claims {'joint ' if own == 'joint' else ''}ownership of study inventions → escalate to Legal.", ch["original"])
    if own == "sponsor":
        return Verdict("accept", "IP-A1", "Study inventions belong to Sponsor → matches the standard.")
    return None


@position("intellectual_property", "research_license", {"IP-A2"})
def _research_license(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("site_research_license")):
        return Verdict("accept", "IP-A2", "Site keeps a non-exclusive research license → matches the pre-approved fallback.")
    return None


@position("intellectual_property", "background_ip", {"IP-A3"})
def _background_ip(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("background_ip_retained")):
        return Verdict("accept", "IP-A3", "Background IP stays with its owner → consistent with the standard; reply to the comment.")
    return None


@position("intellectual_property", "patent_prosecution", {"IP-C1"})
def _patent_prosecution(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("site_may_file_patents")):
        return Verdict("counter", "IP-C1", "Site may file patents in its own name → restore Sponsor’s control of filings.", ch["original"])
    return None


@position("data_privacy", "baa", {"DP-E1"})
def _baa(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("requires_baa")):
        return Verdict("escalate", "DP-E1", "Site requires a Business Associate Agreement → escalate to Privacy.", ch["original"])
    return None


@position("data_privacy", "secondary_research", {"DP-E2"})
def _secondary_research(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("blocks_secondary_research")):
        return Verdict("escalate", "DP-E2", "Site blocks secondary research use → escalate to Privacy.", ch["original"])
    return None


@position("data_privacy", "data_use_addendum", {"DP-A2"})
def _data_use_addendum(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("data_use_addendum")):
        return Verdict("accept", "DP-A2", "Limited data-use addendum → matches the pre-approved fallback.")
    return None


@position("data_privacy", "incident_notice", {"DP-A3", "DP-C1"}, {"accept_min"})
def _incident_notice(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    days = _num(v.get("incident_notice_days"))
    if days is None:
        return None
    floor = lim("accept_min")
    if days < floor:
        return Verdict("counter", "DP-C1", f"Security-incident notice within {days:g} business days is under {floor:g} → counter at {floor:g}.",
                       _replace_quantity(ch["revised"], "business days", _qty(floor)))
    return Verdict("accept", "DP-A3", f"Security-incident notice within {days:g} business days is within {floor:g}.")


@position("data_privacy", "data_transfer", {"DP-E3"})
def _data_transfer(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("restricts_data_transfer")):
        return Verdict("escalate", "DP-E3", "Study Data restricted to one place → escalate to Privacy.", ch["original"])
    return None


@position("termination", "site_notice", {"TERM-A0", "TERM-A1", "TERM-C1", "TERM-E2"}, {"accept_max", "escalate_below", "standard"})
def _site_notice(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    days = _num(v.get("site_notice_days"))
    if days is None:
        return None
    floor, std, cap = lim("escalate_below"), lim("standard"), lim("accept_max")
    if days < floor:
        fb = _replace_quantity(ch["revised"], "days", _qty(std))
        return Verdict("escalate", "TERM-E2", f"Site notice of {days:g} days is under {floor:g} → escalate to Legal.", ch["original"], fb)
    if days == std:
        return Verdict("accept", "TERM-A0", f"{days:g} days’ notice → matches the standard.")
    if days <= cap:
        return Verdict("accept", "TERM-A1", f"{days:g} days’ notice for the site → within the pre-approved {cap:g}-day fallback.")
    return Verdict("counter", "TERM-C1", f"{days:g} days’ notice exceeds the {cap:g}-day fallback → counter at {cap:g} days.",
                   _replace_quantity(ch["revised"], "days", _qty(cap)))


@position("termination", "convenience", {"TERM-A2", "TERM-E1"})
def _convenience(v: dict, ch: dict, **_) -> Verdict | None:
    if not _bool(v.get("termination_for_convenience")):
        return None
    if _bool(v.get("pays_noncancellable_costs")) is True:
        return Verdict("accept", "TERM-A2", "Site may terminate for convenience and Sponsor’s non-cancellable costs are paid → accept.")
    return Verdict("escalate", "TERM-E1", "Site adds termination for convenience without paying non-cancellable costs → escalate to Legal.", ch["original"])


@position("termination", "sponsor_notice", {"TERM-A3", "TERM-C2"}, {"accept_max"})
def _sponsor_notice(v: dict, ch: dict, lim: Limit, **_) -> Verdict | None:
    days = _num(v.get("sponsor_notice_days"))
    if days is None:
        return None
    cap = lim("accept_max")
    if days > cap:
        return Verdict("counter", "TERM-C2", f"Sponsor notice of {days:g} days exceeds {cap:g} → counter at {cap:g} days.",
                       _replace_quantity(ch["revised"], "days", _qty(cap)))
    return Verdict("accept", "TERM-A3", f"Sponsor notice of {days:g} days is within {cap:g}.")


@position("governing_law", "choice_of_law", {"GOV-A1", "GOV-A2", "GOV-E2"})
def _choice_of_law(v: dict, ch: dict, **_) -> Verdict | None:
    state = (v.get("governing_law_state") or "").strip()
    if not state:
        return None  # whether the institution is public only qualifies a choice of law
    if re.sub(r"^(the )?(state|commonwealth) of ", "", state.lower()).strip(" .") not in US_STATES:
        return None  # a deferred, foreign or unnamed jurisdiction: a person reads it
    home = SPONSOR["homeState"].lower()
    if home in state.lower():
        return Verdict("accept", "GOV-A1", "Sponsor’s home-state law → matches the standard.")
    if _bool(v.get("institution_is_public")) is True:
        return Verdict("accept", "GOV-A2", "Public institution’s home-state law → matches the pre-approved fallback.")
    return Verdict("escalate", "GOV-E2", f"{state} law for a private institution → escalate to Legal.", ch["original"])


@position("governing_law", "venue", {"GOV-C1"})
def _venue(v: dict, ch: dict, **_) -> Verdict | None:
    if _norm(v.get("venue")) in ("site_courts_exclusive", "site_courts_nonexclusive", "other"):
        counter = _drop_phrase(ch["revised"], r",?\s*with (?:exclusive |non-exclusive )?venue in [^.;]*")
        return Verdict("counter", "GOV-C1", "A venue clause in the site’s courts → counter silent on venue.", counter)
    return None


@position("governing_law", "arbitration", {"GOV-C2", "GOV-E1"})
def _arbitration(v: dict, ch: dict, **_) -> Verdict | None:
    if _bool(v.get("arbitration_abroad")) or _bool(v.get("sovereign_immunity_waiver_required")):
        return Verdict("escalate", "GOV-E1", "Mandatory arbitration abroad or a sovereign immunity demand → escalate to Legal.", ch["original"])
    if _bool(v.get("arbitration_domestic")):
        return Verdict("counter", "GOV-C2", "Domestic arbitration in place of the courts → restore the form.", ch["original"])
    return None


def _decide_clause(clause: str, values: dict, change: dict, lenient: dict | None, pb: Playbook) -> Verdict | None:
    """Every position of the clause, in playbook order; the strictest verdict wins (ties: the position
    listed first) and names the other positions that fired."""
    fired: list[Verdict] = []
    for p in pb.positions(clause):
        fn = POSITIONS.get((clause, p["id"]))
        if fn is None:
            continue
        verdict = fn(values, change, lim=lambda key, pid=p["id"]: pb.limit(clause, pid, key),
                     widen=lambda field, value: _widened(field, value, lenient, pb))
        if verdict:
            fired.append(verdict)
    if not fired:
        return None
    win = max(fired, key=lambda x: STRICTNESS[x.outcome])
    if others := [f for f in fired if f is not win]:
        win.rule_text += " Also: " + " ".join(f"{f.rule_id} {f.rule_text}" for f in others)
        if sum(f.outcome != "accept" for f in fired) > 1:
            # Two positions object: a counter built for one would concede the other, so hold the form
            win.counter_text = change["original"]
            if win.fallback_text is not None:
                win.fallback_text = change["original"]
    return win


def decide(change: dict, extraction: dict, quotes_ok: bool, lenient: dict | None = None, playbook: dict | None = None) -> Verdict:
    """`lenient` (priority.leniency_for) widens only the three bands' accept lines; every fail-safe runs
    first. `playbook` is the one in force (default: the saved playbook)."""
    if extraction.get("error"):
        return Verdict("human_review", "SYS-ERROR", f"Extraction failed ({extraction['error']}) → human review.")
    if not quotes_ok:
        return Verdict("human_review", "SYS-QUOTE", "A quote was not found verbatim in the redline → human review.")
    confidence = float(extraction.get("confidence") or 0)
    if confidence < LOW_CONFIDENCE:
        return Verdict(
            "human_review",
            "SYS-LOWCONF",
            f"Extraction confidence {confidence:.2f} < {LOW_CONFIDENCE:.2f} → human review. {extraction.get('rationale', '')}".strip(),
        )
    seen: dict[str, set[str]] = {}
    for v in extraction.get("values", []):
        seen.setdefault(v["field"], set()).add(str(v["value"]).strip().lower())
    if conflicts := sorted(f for f, vals in seen.items() if len(vals) > 1):
        return Verdict("human_review", "SYS-CONFLICT", f"The extraction gave conflicting values for {', '.join(conflicts)} → human review.")
    values = {v["field"]: v["value"] for v in extraction.get("values", [])}
    # A cosmetic edit may also note that an adverse term is absent; any other value is a real term
    if (_bool(values.pop("no_substantive_change", None)) and not extraction.get("novel_issue")
            and all(f in ABSENT_WHEN_FALSE and _bool(x) is False for f, x in values.items())):
        return Verdict("accept", "SYS-COSMETIC", "Wording or formatting edit with no change to rights or obligations → accept.")
    clause = extraction.get("clause_type", "")
    pb = Playbook(playbook)
    verdict = _decide_clause(clause, values, change, lenient, pb) if clause in {c["clauseType"] for c in pb.pb["clauses"]} else None
    # A model-training limit is a term the playbook deliberately has no position on
    novel = extraction.get("novel_issue") or ("Limits training AI models on Study data." if _bool(values.get("ml_training_restriction")) else None)
    if novel and (verdict is None or verdict.outcome in ("accept", "counter")):
        return Verdict("human_review", "SYS-NOVEL", f"New term no playbook rule covers → human review. {novel}")
    if verdict is None:
        if change.get("kind") == "comment" and not values:
            return Verdict("human_review", "SYS-COMMENT", "Site comment with no change to the text → reply by hand.")
        return Verdict("human_review", "SYS-NORULE", "No playbook rule matched the extracted values → human review.")
    return verdict
