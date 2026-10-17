"""Rules engine: one outcome per change, from extracted values and the playbook.

Order: system checks (failed quote, low confidence, extraction error), then novel terms,
then the clause rules. Every outcome carries the ID and text of the rule that fired.
Counter-proposal text comes from fixed substitutions on the site's own wording; Siteline
does not draft new legal language (PRD non-goal).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from siteline.playbook import SPONSOR

LOW_CONFIDENCE = 0.80


@dataclass
class Verdict:
    outcome: str  # accept | fallback | escalate | human_review | novel
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
    s = str(v).strip().lower()
    if s in ("true", "yes", "1"):
        return True
    if s in ("false", "no", "0"):
        return False
    return None


def _norm(v: str | None) -> str:
    return (v or "").strip().lower().replace(" ", "_").replace("-", "_")


# ---- counter-text substitutions on the site's revised wording -----------------------

_NUMWORD = r"(?:[A-Za-z]+(?:-[A-Za-z]+)?\s+)?\(\d+\)|\d+"


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


def _drop_phrase(text: str, pattern: str) -> str | None:
    new = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)
    return new if new != text else None


# ---- clause rules -------------------------------------------------------------------


def _payment(v: dict, ch: dict) -> Verdict | None:
    net = _num(v.get("net_days"))
    if net is not None:
        if net < 30:
            fb = _replace_quantity(ch["revised"], "days", "thirty (30)")
            return Verdict("escalate", "PAY-E1", f"Net {net:g} is under 30 days → escalate to Finance.", ch["original"], fb)
        if net < 45:
            return Verdict("accept", "PAY-A2", f"Net {net:g} is within the pre-approved Net 30 fallback.")
        return Verdict("accept", "PAY-A1", f"Net {net:g} meets the Net 45 standard.")
    fee = _num(v.get("start_up_fee_pct"))
    if fee is not None:
        refundable = _bool(v.get("start_up_fee_refundable"))
        counter = _replace_percent(ch["revised"], "ten percent (10%)")
        if counter:
            counter = counter.replace("non-refundable ", "").rstrip(".") + ", refundable pro rata if no subject is enrolled."
        if fee > 20 and refundable is not True:
            return Verdict("escalate", "PAY-E2", f"Non-refundable start-up fee of {fee:g}% is above 20% → escalate to Finance.", ch["original"], counter)
        if fee > 10:
            return Verdict("fallback", "PAY-F2", f"Start-up fee of {fee:g}% is above 10% → counter at 10%, refundable pro rata if no subject is enrolled.", counter)
        return Verdict("accept", "PAY-A3", f"Start-up fee of {fee:g}% is within the 10% standard.")
    return None


def _confidentiality(v: dict, ch: dict) -> Verdict | None:
    if _bool(v.get("trade_secrets_perpetual")) is False:
        return Verdict("escalate", "CONF-E2", "Trade secrets lose perpetual protection → escalate to Legal.", ch["original"])
    years = _num(v.get("survival_years"))
    if years is None:
        return None
    if years < 3:
        fb = _replace_quantity(ch["revised"], "years", "five (5)")
        return Verdict("escalate", "CONF-E1", f"Survival of {years:g} years is under 3 → escalate to Legal.", ch["original"], fb)
    if years < 5:
        return Verdict("fallback", "CONF-F1", f"Survival of {years:g} years is between 3 and 5 → counter with the 5-year fallback.", _replace_quantity(ch["revised"], "years", "five (5)"))
    if years < 7:
        return Verdict("accept", "CONF-A2", f"Survival of {years:g} years meets the pre-approved 5-year fallback.")
    return Verdict("accept", "CONF-A1", f"Survival of {years:g} years meets the 7-year standard.")


def _indemnification(v: dict, ch: dict) -> Verdict | None:
    if _bool(v.get("mutual_indemnity")):
        return Verdict("escalate", "IND-E2", "Site adds mutual indemnity → escalate to Legal.", ch["original"])
    carve = _norm(v.get("carve_out_standard"))
    if carve == "none":
        return Verdict("escalate", "IND-E1", "Site removes the negligence carve-out → escalate to Legal.", ch["original"])
    if carve.startswith("gross"):
        if _bool(v.get("adjudication_required")):
            counter = _drop_phrase(ch["revised"], r",?\s*as finally adjudicated")
            return Verdict("fallback", "IND-F1", "Carve-out narrowed to gross negligence → accept the fallback wording and strike “as finally adjudicated”.", counter)
        return Verdict("accept", "IND-A2", "Carve-out narrowed to gross negligence or willful misconduct → matches the pre-approved fallback.")
    if carve == "negligence":
        return Verdict("accept", "IND-A1", "Negligence carve-out kept → matches the standard.")
    return None


def _subject_injury(v: dict, ch: dict) -> Verdict | None:
    if _bool(v.get("covers_lost_wages")) or _bool(v.get("covers_pain_and_suffering")):
        counter = _drop_phrase(ch["revised"], r",?\s*including lost wages[^,.;]*,?") or ch["original"]
        return Verdict("escalate", "SI-E1", "Lost wages or pain and suffering added to subject-injury coverage → escalate to Finance.", ch["original"], counter)
    if _norm(v.get("reimbursement_cap")) == "uncapped":
        return Verdict("escalate", "SI-E2", "Uncapped subject-injury reimbursement → escalate to Finance.", ch["original"])
    coord = _norm(v.get("coordination_with_insurance"))
    if coord == "sponsor_pays_first":
        return Verdict("accept", "SI-A2", "Sponsor pays first without coordinating with insurance → matches the pre-approved fallback.")
    if coord == "net_of_insurance":
        return Verdict("accept", "SI-A1", "Reimbursement net of subject insurance → matches the standard.")
    return None


def _publication(v: dict, ch: dict) -> Verdict | None:
    if _norm(v.get("patent_delay")) == "removed":
        return Verdict("escalate", "PUB-E1", "Patent delay removed → escalate to Legal.", ch["original"])
    days = _num(v.get("review_days"))
    open_ended = _bool(v.get("review_window_open_ended"))
    if days is not None and days < 30:
        fb = _replace_quantity(ch["revised"], "days", "sixty (60)")
        return Verdict("escalate", "PUB-E2", f"Review window of {days:g} days is under 30 → escalate to Legal.", ch["original"], fb)
    if open_ended:
        return Verdict("escalate", "PUB-E3", "Open-ended review window (“or as otherwise agreed”) → escalate to Legal.", ch["original"])
    if days is not None:
        if days < 60:
            counter = _replace_quantity(ch["revised"], "days", "sixty (60)")
            return Verdict("fallback", "PUB-F1", f"Review window of {days:g} days is under the 60-day standard → counter at 60 days.", counter)
        if days <= 75:
            return Verdict("accept", "PUB-A2", f"Review window of {days:g} days is within the 75-day fallback.")
        return Verdict("accept", "PUB-A1", f"Review window of {days:g} days meets the standard.")
    if _norm(v.get("patent_delay")) == "retained":
        return Verdict("accept", "PUB-A3", "Patent delay kept → matches the standard.")
    return None


def _ip(v: dict, ch: dict) -> Verdict | None:
    own = _norm(v.get("invention_ownership"))
    if own in ("joint", "institution"):
        return Verdict("escalate", "IP-E1", f"Site claims {'joint ' if own == 'joint' else ''}ownership of study inventions → escalate to Legal.", ch["original"])
    if _bool(v.get("site_research_license")):
        return Verdict("accept", "IP-A2", "Site keeps a non-exclusive research license → matches the pre-approved fallback.")
    if _bool(v.get("background_ip_retained")):
        return Verdict("accept", "IP-A3", "Background IP stays with its owner → consistent with the standard; reply to the comment.")
    if own == "sponsor":
        return Verdict("accept", "IP-A1", "Study inventions belong to Sponsor → matches the standard.")
    return None


def _privacy(v: dict, ch: dict) -> Verdict | None:
    if _bool(v.get("requires_baa")):
        return Verdict("escalate", "DP-E1", "Site requires a Business Associate Agreement → escalate to Privacy.", ch["original"])
    if _bool(v.get("blocks_secondary_research")):
        return Verdict("escalate", "DP-E2", "Site blocks secondary research use → escalate to Privacy.", ch["original"])
    if _bool(v.get("ml_training_restriction")):
        return Verdict("novel", "NONE", "No playbook rule covers model-training restrictions → flagged as novel.")
    if _bool(v.get("data_use_addendum")):
        return Verdict("accept", "DP-A2", "Limited data-use addendum → matches the pre-approved fallback.")
    return None


def _termination(v: dict, ch: dict) -> Verdict | None:
    if _bool(v.get("termination_for_convenience")) and _bool(v.get("pays_noncancellable_costs")) is not True:
        return Verdict("escalate", "TERM-E1", "Site adds termination for convenience without paying non-cancellable costs → escalate to Legal.", ch["original"])
    days = _num(v.get("site_notice_days"))
    if days is None:
        return None
    if days < 30:
        fb = _replace_quantity(ch["revised"], "days", "thirty (30)")
        return Verdict("escalate", "TERM-E2", f"Site notice of {days:g} days is under 30 → escalate to Legal.", ch["original"], fb)
    if days == 30:
        return Verdict("accept", "TERM-A0", "30 days’ notice → matches the standard.")
    if days <= 60:
        return Verdict("accept", "TERM-A1", f"{days:g} days’ notice for the site → within the pre-approved 60-day fallback.")
    return Verdict("fallback", "TERM-F1", f"{days:g} days’ notice exceeds the 60-day fallback → counter at 60 days.", _replace_quantity(ch["revised"], "days", "sixty (60)"))


def _governing_law(v: dict, ch: dict) -> Verdict | None:
    if _bool(v.get("arbitration_abroad")) or _bool(v.get("sovereign_immunity_waiver_required")):
        return Verdict("escalate", "GOV-E1", "Mandatory arbitration abroad or a sovereign immunity demand → escalate to Legal.", ch["original"])
    state = (v.get("governing_law_state") or "").strip()
    venue = _norm(v.get("venue"))
    public = _bool(v.get("institution_is_public"))
    home = SPONSOR["homeState"].lower()
    law_ok = not state or home in state.lower() or public is True
    if not law_ok:
        return Verdict("escalate", "GOV-E2", f"{state} law for a private institution → escalate to Legal.", ch["original"])
    if venue in ("site_courts_exclusive", "site_courts_nonexclusive", "other"):
        counter = _drop_phrase(ch["revised"], r",?\s*with (?:exclusive |non-exclusive )?venue in [^.;]*")
        rule = "Public institution’s home-state law is allowed; " if state and home not in state.lower() else ""
        return Verdict("fallback", "GOV-F1", f"{rule}a venue clause in the site’s courts is not → counter silent on venue.", counter)
    if state and home not in state.lower():
        return Verdict("accept", "GOV-A2", "Public institution’s home-state law → matches the pre-approved fallback.")
    return Verdict("accept", "GOV-A1", "Sponsor’s home-state law and venue → matches the standard.")


CLAUSE_RULES = {
    "payment_terms": _payment,
    "confidentiality": _confidentiality,
    "indemnification": _indemnification,
    "subject_injury": _subject_injury,
    "publication": _publication,
    "intellectual_property": _ip,
    "data_privacy": _privacy,
    "termination": _termination,
    "governing_law": _governing_law,
}


def decide(change: dict, extraction: dict, quotes_ok: bool) -> Verdict:
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
    values = {v["field"]: v["value"] for v in extraction.get("values", [])}
    if _bool(values.pop("no_substantive_change", None)) and not values and not extraction.get("novel_issue"):
        return Verdict("accept", "SYS-COSMETIC", "Wording or formatting edit with no change to rights or obligations → accept.")
    fn = CLAUSE_RULES.get(extraction.get("clause_type", ""))
    verdict = fn(values, change) if fn else None
    novel = extraction.get("novel_issue")
    if novel and (verdict is None or verdict.outcome in ("accept", "fallback")):
        return Verdict("novel", "NONE", f"No playbook rule covers this → flagged as novel. {novel}")
    if verdict is None:
        if change.get("kind") == "comment" and not values:
            return Verdict("human_review", "SYS-COMMENT", "Site comment with no change to the text → reply by hand.")
        return Verdict("human_review", "SYS-NORULE", "No playbook rule matched the extracted values → human review.")
    return verdict
