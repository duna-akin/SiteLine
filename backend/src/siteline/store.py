"""Agreements, decisions, approvals and inbound email, kept in memory and saved to var/state.json.
Precedents go to Postgres instead when DATABASE_URL is set."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

import psycopg

from siteline import db, priority
from siteline.config import DATA_DIR, RUNTIME_DIR

log = logging.getLogger("siteline.store")

STATE_PATH = RUNTIME_DIR / "state.json"
SEED_PATH = DATA_DIR / "seed_portfolio.json"
OUTCOMES = ("accept", "fallback", "escalate", "human_review", "novel")

_lock = threading.RLock()
_state: dict[str, Any] = {}


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _seed() -> dict[str, Any]:
    seed = json.loads(SEED_PATH.read_text())
    return {
        "agreements": {a["id"]: a for a in seed["agreements"]},
        "decisions": {},
        "documents": {},
        "emails": seed["emails"],
        "precedents": seed.get("precedents", []),
        "photon": {"users": {}, "spaces": {}},
        "calls": {},
    }


def load() -> None:
    global _state
    with _lock:
        if STATE_PATH.exists():
            _state = json.loads(STATE_PATH.read_text())
            # State saved before precedents existed: start from the seeded history
            if "precedents" not in _state:
                _state["precedents"] = json.loads(SEED_PATH.read_text()).get("precedents", [])
        else:
            _state = _seed()


def save() -> None:
    with _lock:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(_state, ensure_ascii=False))
        tmp.replace(STATE_PATH)


def reset() -> None:
    global _state
    with _lock:
        _state = _seed()
        save()


def state() -> dict[str, Any]:
    return _state


# ---- agreements ---------------------------------------------------------------------


def list_agreements() -> list[dict]:
    with _lock:
        items = [summarize(a) for a in _state["agreements"].values()]
    return sorted(items, key=lambda a: a["receivedAt"], reverse=True)


def get_agreement(agreement_id: str) -> dict | None:
    with _lock:
        a = _state["agreements"].get(agreement_id)
        return summarize(a) if a else None


def put_agreement(agreement: dict) -> None:
    with _lock:
        _state["agreements"][agreement["id"]] = agreement
        save()


def put_document(agreement_id: str, parsed: dict) -> None:
    with _lock:
        _state["documents"][agreement_id] = parsed
        save()


def get_document(agreement_id: str) -> dict | None:
    return _state["documents"].get(agreement_id)


def effective_outcome(d: dict) -> str:
    return (d.get("override") or {}).get("outcome") or d["outcome"]


def is_waiting(d: dict) -> bool:
    """Blocked on an approver's reply or a reviewer's decision."""
    o = effective_outcome(d)
    return (o == "escalate" and d["approval"]["state"] != "answered") or (o in ("human_review", "novel") and not d.get("override"))


def is_confirmed(d: dict) -> bool:
    """A person has signed off: confirmed the suggestion, overridden it, or answered its escalation."""
    if d.get("confirmation") or d.get("override"):
        return True
    return effective_outcome(d) == "escalate" and d["approval"]["state"] == "answered"


def unconfirmed(agreement_id: str) -> int:
    """Suggestions (accept or fallback) still waiting for a person to confirm them."""
    return sum(1 for d in get_decisions(agreement_id) if not is_waiting(d) and not is_confirmed(d))


def summarize(a: dict) -> dict:
    """Live agreements derive status, mix and stuck clauses from their decisions; every agreement
    gets its priority under the current config."""
    out = dict(a)
    out["priority"] = priority.assess(a.get("priorityInputs"))
    out["daysWaiting"] = priority.days_since(a.get("redlineReceivedAt") or a.get("receivedAt"))
    decisions = _state["decisions"].get(a["id"])
    if decisions is None:
        return out
    mix = {o: 0 for o in OUTCOMES}
    stuck: list[str] = []
    pending = False
    for d in decisions:
        mix[effective_outcome(d)] += 1
        if is_waiting(d):
            pending = True
            if d["clauseType"] not in stuck:
                stuck.append(d["clauseType"])
    out["outcomeMix"] = mix
    out["changes"] = len(decisions)
    out["stuckClauses"] = stuck
    out["confirmed"] = sum(1 for d in decisions if is_confirmed(d))
    out["toConfirm"] = sum(1 for d in decisions if not is_waiting(d) and not is_confirmed(d))
    if a.get("status") in ("triaging", "sent_to_site", "executed"):
        return out
    out["status"] = "awaiting_approval" if pending or out["toConfirm"] else "ready_to_export"
    received = datetime.fromisoformat(a["receivedAt"].replace("Z", "+00:00"))
    if received.tzinfo is None:
        received = received.replace(tzinfo=UTC)
    out["daysOpen"] = max(a.get("daysOpen", 0), (datetime.now(UTC) - received).days)
    return out


# ---- decisions ----------------------------------------------------------------------


def set_decisions(agreement_id: str, decisions: list[dict]) -> None:
    with _lock:
        _state["decisions"][agreement_id] = decisions
        save()


def get_decisions(agreement_id: str) -> list[dict]:
    return _state["decisions"].get(agreement_id, [])


def find_decision(change_id: str) -> tuple[str, dict] | None:
    for agreement_id, decisions in _state["decisions"].items():
        for d in decisions:
            if d["id"] == change_id:
                return agreement_id, d
    return None


def update_decision(change_id: str, **fields: Any) -> dict | None:
    with _lock:
        hit = find_decision(change_id)
        if not hit:
            return None
        _, d = hit
        d.update(fields)
        save()
        return d


def pending_escalations(owner: str | None = None) -> list[dict]:
    out = []
    for decisions in _state["decisions"].values():
        for d in decisions:
            if effective_outcome(d) == "escalate" and d["approval"]["state"] in ("sent", "calling"):
                if owner is None or d["owner"] == owner:
                    out.append(d)
    return sorted(out, key=lambda d: d["approval"].get("sentAt", 0))


def escalation_queue() -> list[dict]:
    """Every unanswered escalation, highest money at risk first, then oldest. For display only:
    reply matching (pending_escalations) stays oldest-first so a bare "1" answers the first text."""
    rows = []
    for agreement_id, decisions in _state["decisions"].items():
        a = _state["agreements"].get(agreement_id, {})
        prio = priority.assess(a.get("priorityInputs"))
        for d in decisions:
            if effective_outcome(d) == "escalate" and d["approval"]["state"] != "answered":
                rows.append({"agreementId": agreement_id, "siteNumber": a.get("siteNumber"), "siteName": a.get("siteName"),
                             "priority": {k: prio.get(k) for k in ("level", "moneyAtRiskPerWeek", "reason")}, "decision": d})
    return sorted(rows, key=lambda r: (-(r["priority"]["moneyAtRiskPerWeek"] or 0), r["decision"]["approval"].get("sentAt") or 0))


# ---- precedent ----------------------------------------------------------------------
# Postgres when DATABASE_URL is set (db.py), otherwise this state file. Reset never touches
# Postgres, so learned precedent survives demo resets.


def precedents_for_site(site_name: str) -> list[dict]:
    if db.enabled():
        try:
            return db.precedents_for_site(site_name)
        except psycopg.Error as e:  # no precedent is the safe answer: escalations stay escalated
            log.warning("Precedent lookup failed, continuing without precedent: %s", e)
            return []
    key = db.normalize_site(site_name)
    return [r for r in _state.get("precedents", []) if db.normalize_site(r["siteName"]) == key]


def post_completed(records: list[dict]) -> None:
    if db.enabled():
        try:
            db.post_completed(records)
        except psycopg.Error as e:
            log.error("Could not save %d precedents: %s", len(records), e)
        return
    with _lock:
        known = {r["id"] for r in _state.setdefault("precedents", [])}
        _state["precedents"].extend(r for r in records if r["id"] not in known)
        save()


# ---- inbound email ------------------------------------------------------------------


def list_emails() -> list[dict]:
    return sorted(_state["emails"], key=lambda e: e["receivedAt"], reverse=True)


def add_email(email: dict) -> None:
    with _lock:
        _state["emails"].append(email)
        save()


def update_email(email_id: str, **fields: Any) -> None:
    with _lock:
        for e in _state["emails"]:
            if e["id"] == email_id:
                e.update(fields)
        save()


# ---- integration bookkeeping ---------------------------------------------------------


def photon_map() -> dict[str, dict]:
    return _state.setdefault("photon", {"users": {}, "spaces": {}})


def calls() -> dict[str, dict]:
    return _state.setdefault("calls", {})
