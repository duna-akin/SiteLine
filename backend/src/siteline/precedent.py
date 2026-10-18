"""Precedent: has the sponsor agreed this term with this institution before?

Runs after the rules engine, so the fail-safes (quote, confidence, errors) always win. An
acceptance on record for the same institution, of an equal or more sponsor-favourable value,
turns an escalation into an accept (PREC-A1).

Precedents are written only when an agreement is confirmed (completed_records): every term
whose final status is accepted, citing the final agreed document it came from.
"""

from __future__ import annotations

from siteline import store
from siteline.db import normalize_site
from siteline.export import final_text
from siteline.playbook import SPONSOR
from siteline.rules import Verdict, _bool, _norm, _num

HIGHER_IS_BETTER = {"net_days", "survival_years", "review_days", "patent_delay_days"}
LOWER_IS_BETTER = {"start_up_fee_pct"}
# Every other field, including site_notice_days (over 60 days is countered), matches exactly.

KEEP = ("siteName", "agreementId", "siteNumber", "protocol", "label", "via", "reply", "decidedAt",
        "sourceKey", "sourceSection", "sourceQuote")


def _canon(v: str | None) -> str:
    b = _bool(v)
    return str(b).lower() if b is not None else _norm(v)


def _value_ok(field: str, ask: str, past: str) -> bool:
    """True when `ask` is equal or more sponsor-favourable than `past`."""
    if field in HIGHER_IS_BETTER or field in LOWER_IS_BETTER:
        a, p = _num(ask), _num(past)
        if a is None or p is None:
            return False
        return a >= p if field in HIGHER_IS_BETTER else a <= p
    return _canon(ask) == _canon(past)


def _covers(values: dict, record: dict, clause_type: str) -> bool:
    """The record accepted an ask no better for the sponsor than `values`, on every field. Both must
    cover the same fields: a past acceptance that also had, say, a refundable fee says nothing about
    an ask that leaves refundability out."""
    fields = {f for f in values if f != "no_substantive_change"}
    past = {f: v for f, v in record["values"].items() if f != "no_substantive_change"}
    return (bool(fields) and record["clauseType"] == clause_type and fields == set(past)
            and all(_value_ok(f, values[f], past[f]) for f in fields))


def _same_round(r: dict, agreement_id: str, round_started: str | None) -> bool:
    """A record from this agreement's current round (or from this agreement at all, when the round
    start is unknown). Earlier rounds with the same site, already confirmed, count as precedent.
    Strictly later: a round's own records are written when it is confirmed, which is always after
    its triage, so a record in the same second as the round start belongs to the round before."""
    return r["agreementId"] == agreement_id and (round_started is None or r["decidedAt"] > round_started)


def find(clause_type: str, values: dict, site_name: str, agreement_id: str, records: list[dict] | None = None,
         round_started: str | None = None) -> list[dict]:
    """This institution's acceptances that cover this ask, newest first."""
    site = normalize_site(site_name)
    hits = [
        {k: r.get(k) for k in KEEP}
        for r in (store.precedents_for_site(site_name) if records is None else records)
        if normalize_site(r["siteName"]) == site and not _same_round(r, agreement_id, round_started) and _covers(values, r, clause_type)
    ]
    return sorted(hits, key=lambda m: m["decidedAt"], reverse=True)


def _describe(m: dict) -> str:
    how = "confirmed agreement" if m["via"] == "executed" else f"approver reply {m['reply']}"
    return f"{m['siteName']} ({m['label']}, {m['protocol']}, {how})"


def review(verdict: Verdict, clause_type: str, values: dict, site_name: str, agreement_id: str,
           records: list[dict] | None = None, novel_issue: str | None = None,
           round_started: str | None = None) -> tuple[Verdict, dict | None]:
    """Return the (possibly downgraded) verdict and the precedent shown with it. An escalation that
    also carries a novel issue is never downgraded: the precedent covers the term, not the new issue."""
    if verdict.outcome not in ("accept", "counter", "escalate"):
        return verdict, None
    matches = find(clause_type, values, site_name, agreement_id, records, round_started)
    if not matches:
        return verdict, None
    downgrade = verdict.outcome == "escalate" and not novel_issue
    precedent = {
        "sameSite": matches,
        "downgraded": downgrade,
        "originalRuleId": verdict.rule_id if downgrade else None,
        "originalRuleText": verdict.rule_text if downgrade else None,
        "summary": "Accepted before: " + "; ".join(_describe(m) for m in matches),
    }
    if downgrade:
        verdict = Verdict(
            "accept",
            "PREC-A1",
            f"Agreed with {matches[0]['siteName']} before ({_describe(matches[0])}) → accept. Playbook rule {verdict.rule_id} would escalate.",
        )
    return verdict, precedent


def label_for(values: dict) -> str:
    parts = []
    for f, v in values.items():
        words = f.replace("_", " ")
        b = _bool(v)
        parts.append(words if b is True else f"no {words}" if b is False else f"{words} {v}")
    return ", ".join(parts)


def completed_records(agreement_id: str, source_key: str) -> list[dict]:
    """The precedents a confirmed agreement contributes: each term whose final status is
    accepted and whose quotes were verified, citing the final document under `source_key`."""
    a = store.state()["agreements"][agreement_id]
    decided = store.iso_now()
    rnd = a.get("round", 1)
    prefix = f"{agreement_id}:" if rnd == 1 else f"{agreement_id}:r{rnd}:"  # round 1 keeps its original IDs
    out = []
    for d in store.get_decisions(agreement_id):
        values = {v["field"]: v["value"] for v in d.get("extracted", []) if v["field"] != "no_substantive_change"}
        if not values or not d.get("quoteVerified") or final_text(d)[0] != "accepted":
            continue
        out.append({
            "id": f"{prefix}{d['id']}",
            "siteName": a.get("siteName", ""),
            "agreementId": agreement_id,
            "siteNumber": a.get("siteNumber", ""),
            "protocol": SPONSOR["protocol"],
            "clauseType": d["clauseType"],
            "values": values,
            "via": "executed",
            "reply": d["approval"].get("reply"),
            "decidedAt": decided,
            "label": label_for(values),
            "sourceKey": source_key,
            "sourceSection": d["section"],
            "sourceQuote": d.get("quote") or None,
        })
    return out
