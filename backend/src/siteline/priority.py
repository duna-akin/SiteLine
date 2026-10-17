"""Site priority: money at risk per week of delay, and how much leniency it buys.

Claude extracts three figures from the whole agreement (extraction.extract_document), each
with a verbatim quote. Everything here is arithmetic on those figures and the editable
config (data/priority_config.json; edits from the UI go to var/priority_config.json).
Leniency is a share of the gap between a playbook standard and its escalate floor
(rules.BANDS), capped at MAX_SHARE, so no setting can move an escalate floor.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import Any

from siteline.config import DATA_DIR, RUNTIME_DIR
from siteline.verify import normalize

WEEKS_PER_MONTH = 52 / 12
MAX_SHARE = 0.75
MIN_CONFIDENCE = 0.80
LEVELS = ("high", "elevated", "standard")
FIGURES = {
    "enrollment_target_subjects": "integer number of subjects this institution is expected to enroll",
    "enrollment_period_months": "integer months over which this institution enrolls",
    "per_patient_amount_usd": "number: US dollars the sponsor pays per enrolled subject, e.g. 18200",
}

DEFAULT_PATH = DATA_DIR / "priority_config.json"
SAVED_PATH = RUNTIME_DIR / "priority_config.json"
LOG_PATH = RUNTIME_DIR / "priority_config_log.json"


# ---- config -------------------------------------------------------------------------


def load_config() -> dict:
    path = SAVED_PATH if SAVED_PATH.exists() else DEFAULT_PATH
    return json.loads(path.read_text())


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def validate_config(cfg: Any) -> list[str]:
    if not isinstance(cfg, dict):
        return ["Config must be an object"]
    errors: list[str] = []
    extra = set(cfg) - {"plannedEnrollment", "thresholds", "daysBuckets", "leniency"}
    if extra:
        errors.append("Unknown keys: " + ", ".join(sorted(extra)))
    planned = cfg.get("plannedEnrollment")
    if not isinstance(planned, int) or isinstance(planned, bool) or not 1 <= planned <= 100_000:
        errors.append("plannedEnrollment must be a whole number from 1 to 100,000")
    t = cfg.get("thresholds")
    if not isinstance(t, dict) or set(t) != {"high", "elevated"} or not all(_is_num(v) for v in t.values()):
        errors.append("thresholds must have numeric high and elevated values")
    elif not 0 < t["elevated"] < t["high"] <= 10_000_000:
        errors.append("thresholds: need 0 < elevated < high ≤ 10,000,000 dollars per week")
    b = cfg.get("daysBuckets")
    if not isinstance(b, list) or len(b) != 2 or not all(isinstance(x, int) and not isinstance(x, bool) for x in b):
        errors.append("daysBuckets must be two whole numbers of days")
    elif not 0 < b[0] < b[1] <= 3650:
        errors.append("daysBuckets: need 0 < first < second ≤ 3650")
    rows = cfg.get("leniency")
    if not isinstance(rows, dict) or set(rows) != set(LEVELS):
        errors.append("leniency needs exactly the rows high, elevated and standard")
    else:
        for level in LEVELS:
            row = rows[level]
            if not isinstance(row, list) or len(row) != 3 or not all(_is_num(x) for x in row):
                errors.append(f"leniency.{level} must be three numbers, one per days-waiting bucket")
            elif not all(0 <= x <= MAX_SHARE for x in row):
                errors.append(f"leniency.{level}: each share must be between 0 and {MAX_SHARE}")
    return errors


def config_log() -> list[dict]:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else []


def save_config(cfg: dict, by: str) -> dict:
    """Save a validated config and log the change (old → new)."""
    old = load_config()
    SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAVED_PATH.write_text(json.dumps(cfg, indent=2))
    entry = {"at": int(time.time() * 1000), "by": by, "old": old, "new": cfg}
    LOG_PATH.write_text(json.dumps([*config_log(), entry], indent=1))
    return entry


# ---- figures → priority -------------------------------------------------------------


def _num(v: Any) -> float | None:
    """'18,200' / '$18,200.00' / 'forty-eight (48)' → the first number in the value."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(v or ""))
    return float(m.group().replace(",", "")) if m else None


def money(v: float) -> str:
    return f"${v:,.0f}"


def document_text(parsed: dict) -> str:
    """The agreement as it reads after the site's edits (deleted text left out)."""
    lines = ("".join(s["text"] for s in p["segments"] if s["type"] != "del").strip() for p in parsed["paragraphs"])
    return "\n".join(t for t in lines if t)


def inputs_from_extraction(ex: dict, text: str) -> dict:
    """What triage stores on the agreement: the figures, each with its quote checked verbatim."""
    if ex.get("error"):
        return {"source": "contract", "figures": [], "error": ex["error"], "confidence": 0.0}
    doc = normalize(text)
    figures = []
    for f in ex.get("figures", []):
        q = normalize(f.get("quote") or "")
        figures.append({**f, "verified": len(q) >= 3 and q in doc})
    return {"source": "contract", "figures": figures, "error": None, "confidence": float(ex.get("confidence") or 0)}


def _unknown(inputs: dict | None, reason: str) -> dict:
    return {"level": "unknown", "moneyAtRiskPerWeek": None, "reason": reason,
            "source": (inputs or {}).get("source"), "figures": (inputs or {}).get("figures", [])}


def assess(inputs: dict | None, cfg: dict | None = None) -> dict:
    """Priority from stored figures under the current config. Missing or unverified
    figures give level "unknown", which is treated as standard everywhere."""
    cfg = cfg or load_config()
    if not inputs or inputs.get("error"):
        return _unknown(inputs, "No enrollment figures read from the contract → treated as standard.")
    if inputs.get("source") == "contract" and inputs.get("confidence", 0) < MIN_CONFIDENCE:
        return _unknown(inputs, "Enrollment figures were read with low confidence → treated as standard.")
    by_field = {f["field"]: f for f in inputs.get("figures", [])}
    missing = [name for name in FIGURES if name not in by_field]
    if missing:
        return _unknown(inputs, "Contract does not state " + ", ".join(m.replace("_", " ") for m in missing) + " → treated as standard.")
    if not all(by_field[name].get("verified") for name in FIGURES):
        return _unknown(inputs, "A figure's quote was not found verbatim in the contract → treated as standard.")
    target, months, per_patient = (_num(by_field[name]["value"]) for name in FIGURES)
    if not target or not months or not per_patient or target <= 0 or months <= 0 or per_patient <= 0:
        return _unknown(inputs, "Enrollment figures are not usable numbers → treated as standard.")
    per_week = target / (months * WEEKS_PER_MONTH)
    at_risk = per_week * per_patient
    t = cfg["thresholds"]
    level = "high" if at_risk >= t["high"] else "elevated" if at_risk >= t["elevated"] else "standard"
    share = target / cfg["plannedEnrollment"]
    return {
        "level": level,
        "moneyAtRiskPerWeek": round(at_risk),
        "patientsPerWeek": round(per_week, 2),
        "shareOfPlanned": round(share, 3),
        "targetSubjects": target,
        "enrollmentMonths": months,
        "perPatientUsd": per_patient,
        "reason": (
            f"≈{money(at_risk)}/week at risk: {target:g} subjects over {months:g} months × "
            f"{money(per_patient)} per patient ({share:.0%} of planned enrollment)."
        ),
        "source": inputs.get("source"),
        "figures": inputs.get("figures", []),
    }


# ---- priority + days waiting → leniency ---------------------------------------------


def days_since(iso: str | None) -> int:
    if not iso:
        return 0
    at = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, (datetime.now(UTC) - (at if at.tzinfo else at.replace(tzinfo=UTC))).days)


def bucket_index(days: int, cfg: dict) -> int:
    first, second = cfg["daysBuckets"]
    return 0 if days <= first else 1 if days <= second else 2


def bucket_label(i: int, cfg: dict) -> str:
    first, second = cfg["daysBuckets"]
    return (f"0–{first} days", f"{first + 1}–{second} days", f"over {second} days")[i]


def leniency_for(prio: dict, days: int, cfg: dict | None = None) -> dict:
    """The share of each widened band's gap this site gets, recorded with its inputs so the
    rule text can explain itself."""
    cfg = cfg or load_config()
    level = prio["level"] if prio["level"] in LEVELS else "standard"
    i = bucket_index(days, cfg)
    return {
        "level": prio["level"],
        "share": min(MAX_SHARE, float(cfg["leniency"][level][i])),
        "days": days,
        "bucket": bucket_label(i, cfg),
        "moneyAtRiskPerWeek": prio.get("moneyAtRiskPerWeek"),
    }


def describe(lenient: dict) -> str:
    """'high priority ($11,200/week at risk), 0 days waiting → 50% of the gap'"""
    at_risk = lenient.get("moneyAtRiskPerWeek")
    risk = f" ({money(at_risk)}/week at risk)" if at_risk is not None else ""
    return f"{lenient['level']} priority{risk}, {lenient['days']} days waiting → {lenient['share']:.0%} of the gap"
