"""Site priority: value lost per week a site's contract is held up, and how much leniency it buys.

The model extracts the site's enrollment figures from the whole agreement
(extraction.extract_document), each with a verbatim quote. Everything here is arithmetic on
those figures and the editable config (data/priority_config.json; edits from the UI go to
var/priority_config.json).

Value lost per week of site delay (risk-adjusted NPV of the trial delay it causes):

    trial delay per site-week  = 7 days × site enrollment rate / study enrollment rate
    value of one trial day     = p × sales per day / (1 + r)^L  +  direct trial cost per day
    money at risk per week     = trial delay per site-week × value of one trial day

Enrollment is the trial's critical path: the study ends when planned enrollment is reached,
so a week without this site's patients pushes the end out by the time the rest of the study
takes to enroll them. A later end with a fixed patent expiry removes that many days of sales
at launch, L years away; they are discounted at r and weighted by p, the chance the drug is
approved at all. Direct trial costs are paid now, so they are neither discounted nor weighted.
Defaults and their sources are in COST_SOURCES and the backend README.

Leniency is a share of the gap between a playbook standard and its escalate floor
(rules.bands(), from the playbook's limits), capped at MAX_SHARE, so no setting can move an escalate floor.
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
COST_OF_DELAY = {
    "trialEnrollmentMonths": "months the whole study plans to enroll over",
    "salesPerDayUsd": "sales per day once on the market",
    "probabilityOfApproval": "chance the drug is approved, from its current phase",
    "yearsToLaunch": "years from now until launch",
    "discountRate": "annual discount rate (cost of capital)",
    "trialCostPerDayUsd": "direct cost of running the trial for a day",
}
COST_SOURCES = {
    "salesPerDayUsd": "Tufts CSDD 2024 (Smith, DiMasi, Getz): median oncology sales per day, $840,000 (2023 US$)",
    "probabilityOfApproval": "BIO/Informa/QLS 2021: likelihood of approval from Phase II, solid tumors, 9.3%",
    "yearsToLaunch": "BIO/Informa/QLS 2021: oncology Phase II 3.7 + Phase III 3.1 + review 0.8 = 7.6 years",
    "discountRate": "DiMasi, Grabowski, Hansen 2016: 10.5% real cost of capital",
    "trialCostPerDayUsd": "Tufts CSDD 2024: Phase II direct trial cost per day, $23,737 (2023 US$)",
    "trialEnrollmentMonths": "Study plan (fictional NSO-417): 340 patients over 24 months",
}
# Bounds for each cost-of-delay input: (low, high, low is exclusive)
COST_BOUNDS = {
    "trialEnrollmentMonths": (0, 240, True),
    "salesPerDayUsd": (0, 100_000_000, False),
    "probabilityOfApproval": (0, 1, True),
    "yearsToLaunch": (0, 30, False),
    "discountRate": (0, 1, False),
    "trialCostPerDayUsd": (0, 10_000_000, False),
}
# Figures the money-at-risk formula needs; the per-patient amount is read and shown, not used
REQUIRED = ("enrollment_target_subjects", "enrollment_period_months")
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
    """The saved config, with any key it predates (e.g. costOfDelay) filled from the defaults."""
    default = json.loads(DEFAULT_PATH.read_text())
    if not SAVED_PATH.exists():
        return default
    return {**default, **json.loads(SAVED_PATH.read_text())}


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def validate_config(cfg: Any) -> list[str]:
    if not isinstance(cfg, dict):
        return ["Config must be an object"]
    errors: list[str] = []
    extra = set(cfg) - {"plannedEnrollment", "thresholds", "daysBuckets", "leniency", "costOfDelay"}
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
    c = cfg.get("costOfDelay")
    if not isinstance(c, dict) or set(c) != set(COST_OF_DELAY):
        errors.append("costOfDelay needs exactly " + ", ".join(COST_OF_DELAY))
    else:
        for key, (low, high, open_low) in COST_BOUNDS.items():
            v = c[key]
            if not _is_num(v) or not (low < v if open_low else low <= v) or v > high:
                errors.append(f"costOfDelay.{key} must be a number {'above' if open_low else 'from'} {low:g} {'and at most' if open_low else 'to'} {high:g}")
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
    missing = [name for name in REQUIRED if name not in by_field]
    if missing:
        return _unknown(inputs, "Contract does not state " + ", ".join(m.replace("_", " ") for m in missing) + " → treated as standard.")
    if not all(by_field[name].get("verified") for name in REQUIRED):
        return _unknown(inputs, "A figure's quote was not found verbatim in the contract → treated as standard.")
    target, months = (_num(by_field[name]["value"]) for name in REQUIRED)
    if not target or not months or target <= 0 or months <= 0:
        return _unknown(inputs, "Enrollment figures are not usable numbers → treated as standard.")
    c = cfg["costOfDelay"]
    site_rate = target / months  # patients a month
    study_rate = cfg["plannedEnrollment"] / c["trialEnrollmentMonths"]
    rate_share = min(1.0, site_rate / study_rate)
    delay_days = 7 * rate_share  # trial days lost per week this site is held up
    lost_sales = c["probabilityOfApproval"] * c["salesPerDayUsd"] / (1 + c["discountRate"]) ** c["yearsToLaunch"]
    day_value = lost_sales + c["trialCostPerDayUsd"]
    at_risk = delay_days * day_value
    t = cfg["thresholds"]
    level = "high" if at_risk >= t["high"] else "elevated" if at_risk >= t["elevated"] else "standard"
    share = target / cfg["plannedEnrollment"]
    per_patient = _num(by_field.get("per_patient_amount_usd", {}).get("value")) if by_field.get("per_patient_amount_usd", {}).get("verified") else None
    return {
        "level": level,
        "moneyAtRiskPerWeek": round(at_risk),
        "patientsPerWeek": round(site_rate / WEEKS_PER_MONTH, 2),
        "shareOfPlanned": round(share, 3),
        "shareOfEnrollmentRate": round(rate_share, 4),
        "trialDelayDaysPerWeek": round(delay_days, 2),
        "trialDayValueUsd": round(day_value),
        "lostSalesPerTrialDayUsd": round(lost_sales),
        "trialCostPerDayUsd": round(c["trialCostPerDayUsd"]),
        "targetSubjects": target,
        "enrollmentMonths": months,
        "perPatientUsd": per_patient,
        "reason": (
            f"≈{money(at_risk)}/week at risk: {target:g} subjects over {months:g} months is {rate_share:.0%} of the study's "
            f"enrollment rate, so each week this site waits delays the trial ≈{delay_days:.1f} days. A trial day is worth "
            f"≈{money(day_value)}: {money(lost_sales)} in risk-adjusted, discounted sales plus {money(c['trialCostPerDayUsd'])} in trial costs."
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
    """'high priority ($79,473/week at risk), 0 days waiting → 50% of the gap'"""
    at_risk = lenient.get("moneyAtRiskPerWeek")
    risk = f" ({money(at_risk)}/week at risk)" if at_risk is not None else ""
    return f"{lenient['level']} priority{risk}, {lenient['days']} days waiting → {lenient['share']:.0%} of the gap"
