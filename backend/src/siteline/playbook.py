"""The sponsor playbook: 9 clause types, owners and approvers.

The default playbook (fictional) ships in data/playbook.json. Edits from the playbook
editor are saved to var/playbook.json and take precedence.
"""

from __future__ import annotations

import json
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


def approvers() -> dict[str, dict]:
    return {k: {**v, "phone": settings.approver_phones[k]} for k, v in APPROVERS.items()}


def load_playbook() -> list[dict]:
    path = SAVED_PATH if SAVED_PATH.exists() else DEFAULT_PATH
    return json.loads(path.read_text())


def validate_playbook(rules: list[dict]) -> list[str]:
    errors: list[str] = []
    seen = set()
    for i, r in enumerate(rules):
        ct = r.get("clauseType")
        if ct not in CLAUSE_TYPES:
            errors.append(f"Row {i + 1}: unknown clause type {ct!r}")
        if ct in seen:
            errors.append(f"Row {i + 1}: duplicate clause type {ct!r}")
        seen.add(ct)
        if r.get("owner") not in OWNERS:
            errors.append(f"Row {i + 1}: owner must be legal, finance or privacy")
        for key in ("label", "standard", "fallback", "escalateWhen"):
            if not str(r.get(key, "")).strip():
                errors.append(f"Row {i + 1}: {key} is empty")
    missing = set(CLAUSE_TYPES) - seen
    if missing:
        errors.append("Missing clause types: " + ", ".join(sorted(missing)))
    return errors


def save_playbook(rules: list[dict]) -> None:
    SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAVED_PATH.write_text(json.dumps(rules, indent=2, ensure_ascii=False))


def owner_for(clause_type: str, rules: list[dict] | None = None) -> str:
    for r in rules or load_playbook():
        if r["clauseType"] == clause_type:
            return r["owner"]
    return "legal"


def playbook_text(rules: list[dict] | None = None) -> str:
    lines = []
    for r in rules or load_playbook():
        lines.append(
            f"- {r['clauseType']} ({r['label']}, owner: {r['owner']})\n"
            f"  standard: {r['standard']}\n  pre-approved fallback: {r['fallback']}\n  escalate when: {r['escalateWhen']}"
        )
    return "\n".join(lines)
