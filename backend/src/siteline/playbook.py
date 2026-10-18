"""The sponsor playbook: 9 clause types, each a set of negotiable positions, plus owners and approvers.

The default playbook (fictional) ships in data/playbook.json. Each position has the form's
standard, a counter (fallback position) and an escalation trigger as text with {placeholders},
the numeric `limits` those placeholders and the rules engine read, and the rule IDs that
enforce it. Edits from the playbook editor are saved to var/playbook.json and take precedence.
"""

from __future__ import annotations

import copy
import json
import math
import re
import time
from typing import Literal

from siteline.config import DATA_DIR, RUNTIME_DIR, settings

ClauseType = Literal[
    "indemnification",
    "subject_injury",
    "publication",
    "confidentiality",
    "intellectual_property",
    "data_privacy",
    "payment_terms",
    "termination",
    "governing_law",
]
CLAUSE_TYPES: list[str] = list(ClauseType.__args__)  # type: ignore[attr-defined]
OWNERS = ("legal", "finance", "privacy")

SPONSOR = {
    "name": "Northstar Oncology",
    "protocol": "NSO-417",
    "study": "Phase II study of NSO-417 in relapsed solid tumors",
    "homeState": "New Jersey",
}

APPROVERS = {
    "legal": {"owner": "legal", "name": "Tuna Akin", "role": "Contracts counsel"},
    "finance": {"owner": "finance", "name": "Brian Soon", "role": "Clinical finance"},
    "privacy": {"owner": "privacy", "name": "Michael Boneta", "role": "Privacy officer"},
}

DEFAULT_PATH = DATA_DIR / "playbook.json"
SAVED_PATH = RUNTIME_DIR / "playbook.json"
LOG_PATH = RUNTIME_DIR / "playbook_log.json"

TEXT_FIELDS = ("standard", "counter", "escalate")
OUTCOME_LETTER = {"accept": "A", "counter": "C", "escalate": "E"}
# Limit pairs that must stay in order (lower, higher) when a position defines both
ORDER = [("accept_min", "standard"), ("standard", "escalate_above"), ("escalate_below", "accept_min"),
         ("escalate_below", "standard"), ("standard", "accept_max")]
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def approvers() -> dict[str, dict]:
    return {k: {**v, "phone": settings.approver_phones[k]} for k, v in APPROVERS.items()}


def default_playbook() -> dict:
    return json.loads(DEFAULT_PATH.read_text())


def migrate(old: list[dict]) -> dict:
    """A playbook saved in the old flat format (one row per clause): the default, with its owners."""
    pb = default_playbook()
    owners = {r.get("clauseType"): r.get("owner") for r in old if isinstance(r, dict)}
    for c in pb["clauses"]:
        if owners.get(c["clauseType"]) in OWNERS:
            c["owner"] = owners[c["clauseType"]]
    return pb


def load_playbook() -> dict:
    if not SAVED_PATH.exists():
        return default_playbook()
    saved = json.loads(SAVED_PATH.read_text())
    return migrate(saved) if isinstance(saved, list) else saved


def playbook_log() -> list[dict]:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else []


def _log(by: str, summary: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps([*playbook_log(), {"at": int(time.time() * 1000), "by": by, "summary": summary}], indent=1))


def record_moved(n: int) -> None:
    """How many open suggestions the last save or reset re-decided, on its log entry."""
    log = playbook_log()
    if log:
        log[-1]["moved"] = n
        LOG_PATH.write_text(json.dumps(log, indent=1))


def _changes(old: dict, new: dict) -> str:
    """One line naming what an edit changed: limits (old → new), owners, and positions whose text moved."""
    out: list[str] = []
    olds = {c["clauseType"]: c for c in old["clauses"]}
    for c in new["clauses"]:
        oc = olds.get(c["clauseType"], {})
        if oc.get("owner") != c["owner"]:
            out.append(f"{c['label']} owner {oc.get('owner')} → {c['owner']}")
        oldpos = {p["id"]: p for p in oc.get("positions", [])}
        for p in c["positions"]:
            op = oldpos.get(p["id"], {})
            for k, lim in p["limits"].items():
                was = op.get("limits", {}).get(k, {}).get("value")
                if was != lim["value"]:
                    out.append(f"{p['issue']} {lim['label'].lower()} {_fmt(was) if was is not None else '—'} → {_fmt(lim['value'])}")
            if any(op.get(k) != p.get(k) for k in (*TEXT_FIELDS, "rationale", "talkingPoints")):
                out.append(f"{p['issue']} wording")
    return "; ".join(out) or "No changes"


def save_playbook(pb: dict, by: str) -> None:
    summary = _changes(load_playbook(), pb)
    SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAVED_PATH.write_text(json.dumps(pb, indent=2, ensure_ascii=False))
    _log(by, summary)


def reset_playbook(by: str) -> None:
    summary = _changes(load_playbook(), default_playbook())
    SAVED_PATH.unlink(missing_ok=True)
    _log(by, f"Reset to the default playbook ({summary})")


def _fmt(v: float) -> str:
    """A limit as the Playbook page writes it (lib/playbook.ts formatNumber): no exponent, up to 4 decimals."""
    return str(int(v)) if float(v).is_integer() else f"{v:.4f}".rstrip("0").rstrip(".")


def _fill(text: str, limits: dict) -> str:
    return PLACEHOLDER.sub(lambda m: f"{_fmt(limits[m.group(1)]['value'])}{limits[m.group(1)]['unit']}"
                           if m.group(1) in limits else m.group(0), text)


def render(pb: dict) -> dict:
    """A copy with every text also rendered (standardText, counterText, escalateText, rationaleText,
    talkingPointsText, rules[].whenText): placeholders filled from the position's limits."""
    out = copy.deepcopy(pb)
    for c in out["clauses"]:
        for p in c["positions"]:
            for k in (*TEXT_FIELDS, "rationale"):
                p[f"{k}Text"] = _fill(p[k], p["limits"])
            p["talkingPointsText"] = [_fill(t, p["limits"]) for t in p["talkingPoints"]]
            for r in p["rules"]:
                r["whenText"] = _fill(r["when"], p["limits"])
    return out


def strip_rendered(pb: dict) -> dict:
    """The templates only (what PUT and Load JSON accept): drops the *Text keys render() adds."""
    out = copy.deepcopy(pb)
    for c in out.get("clauses", []):
        for p in c.get("positions", []):
            for k in [k for k in p if k.endswith("Text")]:
                del p[k]
            for r in p.get("rules", []):
                r.pop("whenText", None)
    return out


class Playbook:
    """Read access to one playbook: limits, owners and positions by clause."""

    def __init__(self, pb: dict | None = None) -> None:
        self.pb = pb if pb is not None else load_playbook()
        self._clauses = {c["clauseType"]: c for c in self.pb["clauses"]}

    def positions(self, clause: str) -> list[dict]:
        return self._clauses[clause]["positions"]

    def owner(self, clause: str) -> str:
        return self._clauses.get(clause, {}).get("owner", "legal")

    def limit(self, clause: str, position: str, key: str) -> float:
        p = next(p for p in self.positions(clause) if p["id"] == position)
        return float(p["limits"][key]["value"])

    def rule_position(self) -> dict[str, tuple[str, str]]:
        """Rule ID → (clause type, position id)."""
        return {r["id"]: (c["clauseType"], p["id"]) for c in self.pb["clauses"] for p in c["positions"] for r in p["rules"]}


def _num(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def validate_playbook(pb: object, engine: dict | None = None) -> list[str]:
    """Problems with a playbook as strings (empty when valid). `engine` (default: rules.ENGINE) maps each
    (clause, position) the rules engine runs to the rule IDs it returns and the limits it reads; a valid
    playbook has exactly those positions, rules and limits, so a saved playbook always runs."""
    if engine is None:
        from siteline.rules import ENGINE as engine  # rules imports this module
    if not isinstance(pb, dict) or not isinstance(pb.get("clauses"), list):
        return ["A playbook is an object with a list of clauses"]
    errors: list[str] = []
    seen_clauses: set[str] = set()
    seen_rules: dict[str, str] = {}
    for c in pb["clauses"]:
        if not isinstance(c, dict):
            errors.append("Each clause must be an object")
            continue
        ct = c.get("clauseType")
        where = str(ct)
        if ct not in CLAUSE_TYPES:
            errors.append(f"Unknown clause type {ct!r}")
            continue
        if ct in seen_clauses:
            errors.append(f"Duplicate clause type {ct!r}")
        seen_clauses.add(ct)
        if c.get("owner") not in OWNERS:
            errors.append(f"{where}: owner must be legal, finance or privacy")
        if not str(c.get("label", "")).strip():
            errors.append(f"{where}: label is empty")
        positions = c.get("positions")
        if not isinstance(positions, list):
            errors.append(f"{where}: positions must be a list")
            continue
        ids: set[str] = set()
        for p in positions:
            if not isinstance(p, dict):
                errors.append(f"{where}: each position must be an object")
                continue
            pid = p.get("id")
            at = f"{where} / {pid}"
            if not pid or pid in ids:
                errors.append(f"{at}: position id missing or repeated")
            ids.add(pid)
            need = engine.get((ct, pid))
            if need is None:
                errors.append(f"{at}: the rules engine has no position {pid!r} in {ct}")
            for k in ("issue", *TEXT_FIELDS, "rationale"):
                if not isinstance(p.get(k), str) or not p[k].strip():
                    errors.append(f"{at}: {k} must be non-empty text")
            if not isinstance(p.get("talkingPoints", []), list) or not all(isinstance(t, str) for t in p.get("talkingPoints", [])):
                errors.append(f"{at}: talkingPoints must be a list of text")
            limits = p.get("limits")
            if not isinstance(limits, dict):
                errors.append(f"{at}: limits must be an object")
                limits = {}
            for k, lim in limits.items():
                if not isinstance(lim, dict) or not _num(lim.get("value")) or lim["value"] < 0:
                    errors.append(f"{at}: limit {k} must be a finite number of 0 or more")
                elif not isinstance(lim.get("unit"), str) or not isinstance(lim.get("label"), str):
                    errors.append(f"{at}: limit {k} needs a unit and a label")
            if need is not None and (missing := need["limits"] - set(limits)):
                errors.append(f"{at}: the rules read limits {', '.join(sorted(missing))}")
            vals = {k: lim["value"] for k, lim in limits.items() if isinstance(lim, dict) and _num(lim.get("value"))}
            for lo, hi in ORDER:
                if lo in vals and hi in vals and vals[lo] > vals[hi]:
                    errors.append(f"{at}: {limits[lo].get('label', lo)} ({_fmt(vals[lo])}) must not exceed {limits[hi].get('label', hi)} ({_fmt(vals[hi])})")
            rules = p.get("rules")
            if not isinstance(rules, list) or not rules or not all(isinstance(r, dict) for r in rules):
                errors.append(f"{at}: rules must be a non-empty list")
                rules = []
            texts = [p.get(k, "") for k in (*TEXT_FIELDS, "rationale")] + [t for t in p.get("talkingPoints") or [] if isinstance(t, str)]
            texts += [r.get("when", "") for r in rules]
            for name in {m for t in texts for m in PLACEHOLDER.findall(str(t))} - set(limits):
                errors.append(f"{at}: {{{name}}} names no limit")
            listed = set()
            for r in rules:
                rid = str(r.get("id", ""))
                listed.add(rid)
                if rid in seen_rules:
                    errors.append(f"{at}: rule {rid} is already listed under {seen_rules[rid]}")
                seen_rules[rid] = at
                letter = rid.split("-")[-1][:1] if "-" in rid else ""
                if OUTCOME_LETTER.get(r.get("outcome")) != letter:
                    errors.append(f"{at}: rule {rid} must have outcome {next((o for o, l in OUTCOME_LETTER.items() if l == letter), '?')}")
            if need is not None and listed != need["rules"]:
                if wrong := sorted(listed - need["rules"]):
                    errors.append(f"{at}: the engine does not decide {', '.join(wrong)} in this position")
                if missing := sorted(need["rules"] - listed):
                    errors.append(f"{at}: rules this position enforces are not listed: {', '.join(missing)}")
        for (ect, epid) in engine:
            if ect == ct and epid not in ids:
                errors.append(f"{where}: position {epid} is missing")
    if missing := set(CLAUSE_TYPES) - seen_clauses:
        errors.append("Missing clause types: " + ", ".join(sorted(missing)))
    engine_rules = {r for need in engine.values() for r in need["rules"]}
    if extra := set(seen_rules) - engine_rules:
        errors.append("Rules the playbook lists but the engine does not have: " + ", ".join(sorted(extra)))
    return errors


def owner_for(clause_type: str, pb: dict | None = None) -> str:
    return Playbook(pb).owner(clause_type)


def playbook_text(pb: dict | None = None) -> str:
    """The playbook for prompts: each clause and its positions, with the numbers filled in."""
    lines = []
    for c in render(pb or load_playbook())["clauses"]:
        lines.append(f"- {c['clauseType']} ({c['label']}, owner: {c['owner']})")
        for p in c["positions"]:
            lines.append(f"  * {p['issue']}: standard: {p['standardText']} Counter: {p['counterText']} Escalate: {p['escalateText']}")
    return "\n".join(lines)
