import asyncio
import copy

import pytest
from fastapi.testclient import TestClient

from siteline import approvals, priority, store
from siteline.demo import demo_bytes
from siteline.demo_cache import SEED
from siteline.rules import BANDS, decide

CHANGE = {"original": "the old text", "revised": "the new text", "kind": "replacement", "segments": []}


def figures(target="48", months="18", usd="18200", verified=True, confidence=0.97) -> dict:
    return {"source": "contract", "error": None, "confidence": confidence, "figures": [
        {"field": "enrollment_target_subjects", "value": target, "quote": "q", "verified": verified},
        {"field": "enrollment_period_months", "value": months, "quote": "q", "verified": True},
        {"field": "per_patient_amount_usd", "value": usd, "quote": "q", "verified": True},
    ]}


def lenient(level: str, days: int = 0) -> dict:
    return priority.leniency_for({"level": level, "moneyAtRiskPerWeek": 11200}, days)


# ---- money at risk and level -------------------------------------------------------


def test_site07_figures_give_high_priority():
    p = priority.assess(figures())
    assert p["level"] == "high"
    assert p["moneyAtRiskPerWeek"] == 11200  # 48 subjects / (18 × 52/12 weeks) × $18,200
    assert p["shareOfPlanned"] == pytest.approx(48 / 340, abs=0.001)
    assert "≈$11,200/week at risk" in p["reason"]


def test_levels_follow_the_thresholds():
    assert priority.assess(figures("30", "24", "16000"))["level"] == "elevated"  # ≈$4,615
    assert priority.assess(figures("20", "24", "12000"))["level"] == "standard"  # ≈$2,308
    cfg = {**priority.load_config(), "thresholds": {"high": 2000, "elevated": 1000}}
    assert priority.assess(figures("20", "24", "12000"), cfg)["level"] == "high"


@pytest.mark.parametrize("inputs", [
    None,
    {"source": "contract", "figures": [], "error": "Claude unavailable", "confidence": 0},
    figures(verified=False),
    figures(confidence=0.5),
    figures(months="0"),
    {**figures(), "figures": figures()["figures"][:2]},
])
def test_missing_or_unverified_figures_are_unknown(inputs):
    p = priority.assess(inputs)
    assert p["level"] == "unknown" and p["moneyAtRiskPerWeek"] is None
    assert priority.leniency_for(p, 0)["share"] == 0  # unknown is treated as standard


def test_leniency_grows_with_days_waiting():
    assert [lenient("standard", d)["share"] for d in (0, 45, 120)] == [0, 0, 0.25]
    assert [lenient("high", d)["share"] for d in (0, 45, 120)] == [0.5, 0.5, 0.75]


# ---- rules: widened accept lines, fixed escalate floors ------------------------------


def _ex(clause: str, **values) -> dict:
    return {"clause_type": clause, "confidence": 0.95, "novel_issue": None, "rationale": "",
            "values": [{"field": k, "value": str(v), "quote": "q"} for k, v in values.items() if v is not None]}


def _band_cases():
    for fee in [x / 2 for x in range(0, 81)]:
        for refundable in (None, "true", "false"):
            yield _ex("payment_terms", start_up_fee_pct=fee, start_up_fee_refundable=refundable)
    for years in [x / 2 for x in range(0, 21)]:
        for perpetual in (None, "false"):
            yield _ex("confidentiality", survival_years=years, trade_secrets_perpetual=perpetual)
    for days in range(0, 125, 5):
        for open_ended in (None, "true"):
            for patent in (None, "retained", "removed"):
                yield _ex("publication", review_days=days, review_window_open_ended=open_ended, patent_delay=patent)


def test_no_leniency_ever_lifts_an_escalation():
    widest = {"level": "high", "share": priority.MAX_SHARE, "days": 365, "bucket": "x", "moneyAtRiskPerWeek": 99999}
    for ex in _band_cases():
        base = decide(CHANGE, ex, True)
        wide = decide(CHANGE, ex, True, widest)
        if base.outcome == "escalate":
            assert wide.outcome == "escalate" and wide.rule_id == base.rule_id, ex
        elif base.rule_id != wide.rule_id:  # the only allowed move: counter → widened accept
            assert (base.outcome, wide.outcome) == ("fallback", "accept") and wide.rule_id.endswith("P"), ex


def test_same_redline_differs_for_high_and_standard_sites():
    fee, conf = SEED[1], SEED[2]  # demo §6.3: 15% non-refundable fee; §11: 4-year survival
    assert decide(CHANGE, fee, True, lenient("standard")).rule_id == "PAY-F2"
    high = decide(CHANGE, fee, True, lenient("high"))
    assert high.outcome == "accept" and high.rule_id == "PAY-A3P"
    assert "high priority ($11,200/week at risk), 0 days waiting → 50% of the gap" in high.rule_text.lower()
    assert decide(CHANGE, conf, True, lenient("standard")).rule_id == "CONF-F1"
    assert decide(CHANGE, conf, True, lenient("high")).rule_id == "CONF-A2P"
    assert decide(CHANGE, _ex("publication", review_days=45), True, lenient("high")).rule_id == "PUB-A2P"
    assert decide(CHANGE, _ex("publication", review_days=40), True, lenient("high")).rule_id == "PUB-F1"


def test_fail_safes_win_over_leniency():
    ex = copy.deepcopy(SEED[1])
    assert decide(CHANGE, ex, False, lenient("high")).rule_id == "SYS-QUOTE"
    ex["confidence"] = 0.5
    assert decide(CHANGE, ex, True, lenient("high")).rule_id == "SYS-LOWCONF"


def test_band_table_matches_the_rules():
    assert {f: (b["standard"], b["floor"]) for f, b in BANDS.items()} == {
        "start_up_fee_pct": (10, 20), "survival_years": (5, 3), "review_days": (60, 30)}


# ---- config ---------------------------------------------------------------------------


def test_config_bounds_are_enforced():
    ok = priority.load_config()
    assert priority.validate_config(ok) == []
    too_lenient = {**ok, "leniency": {**ok["leniency"], "high": [0.5, 0.5, 0.8]}}
    assert any("between 0 and 0.75" in e for e in priority.validate_config(too_lenient))
    assert priority.validate_config({**ok, "thresholds": {"high": 100, "elevated": 500}})
    assert priority.validate_config({**ok, "daysBuckets": [90, 30]})
    assert priority.validate_config({**ok, "escalateFloor": 99})


# ---- pipeline + API: Site 07 end to end ----------------------------------------------


@pytest.fixture
def site07(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()
    from siteline.extraction import SEED_CACHE
    from siteline.pipeline import TriageOptions, triage

    if not SEED_CACHE.exists():
        from siteline.demo_cache import write_seed

        write_seed()

    async def go():
        await triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx", TriageOptions(local_parser=True, use_cache=True))
        approvals.cancel_all()

    asyncio.run(go())
    from siteline.api import app

    return TestClient(app)


def test_site07_triages_to_high_priority_with_widened_rules(site07):
    a = store.get_agreement("site-07")
    assert a["priority"]["level"] == "high" and a["priority"]["moneyAtRiskPerWeek"] == 11200
    rules = {d["ruleId"] for d in store.get_decisions("site-07")}
    assert {"PAY-A3P", "CONF-A2P"} <= rules
    assert all(d["precedent"] is None or d["precedent"]["sameSite"] for d in store.get_decisions("site-07"))


def test_nothing_exports_until_a_person_confirms(site07):
    a = store.get_agreement("site-07")
    assert a["toConfirm"] > 0 and a["status"] == "awaiting_approval"
    assert site07.get("/api/agreements/site-07/export.docx").status_code == 409
    waiting = next(d for d in store.get_decisions("site-07") if store.is_waiting(d))
    assert site07.post(f"/api/decisions/{waiting['id']}/confirm").status_code == 409
    r = site07.post("/api/agreements/site-07/confirm-all", json={"by": "Test reviewer"})
    assert r.status_code == 200 and r.json()["confirmed"] == a["toConfirm"]
    assert store.unconfirmed("site-07") == 0
    assert all(d["confirmation"]["by"] == "Test reviewer" for d in store.get_decisions("site-07") if not store.is_waiting(d))
    assert site07.get("/api/agreements/site-07/export.docx").status_code == 200
    assert site07.post("/api/agreements/site-07/complete").status_code == 409  # escalations still unanswered


def test_saving_config_redecides_only_open_suggestions(site07):
    fee = next(d for d in store.get_decisions("site-07") if d["ruleId"] == "PAY-A3P")
    site07.post(f"/api/decisions/{fee['id']}/confirm")
    cfg = priority.load_config()
    strict = {**cfg, "leniency": {"standard": [0, 0, 0], "elevated": [0, 0, 0], "high": [0, 0, 0]}}
    preview = site07.post("/api/priority-config/preview", json={"config": strict}).json()["changes"]
    assert [c["to"]["ruleId"] for c in preview] == ["CONF-F1"]  # the confirmed fee is left alone
    assert store.get_agreement("site-07")  # preview saved nothing
    assert any(d["ruleId"] == "CONF-A2P" for d in store.get_decisions("site-07"))
    r = site07.put("/api/priority-config", json={"config": strict, "by": "Test"})
    assert r.status_code == 200 and r.json()["log"][0]["by"] == "Test"
    rules = {d["ruleId"] for d in store.get_decisions("site-07")}
    assert "PAY-A3P" in rules and "CONF-F1" in rules and "CONF-A2P" not in rules
    bad = site07.put("/api/priority-config", json={"config": {**cfg, "leniency": {**cfg["leniency"], "high": [1, 1, 1]}}})
    assert bad.status_code == 422


def test_approver_text_carries_the_stakes(site07):
    d = next(d for d in store.get_decisions("site-07") if d["outcome"] == "escalate")
    text = approvals.message_text("site-07", d)
    assert "Site 07 = high priority, ≈$11,200/week at risk (14% of planned enrollment)." in text


def test_escalation_queue_puts_money_at_risk_first(site07, monkeypatch):
    queue = site07.get("/api/escalations").json()
    assert queue and all(r["agreementId"] == "site-07" for r in queue)
    money = [r["priority"]["moneyAtRiskPerWeek"] or 0 for r in queue]
    assert money == sorted(money, reverse=True)
