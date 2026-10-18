import asyncio
import io
import zipfile

import pytest

from siteline import store
from siteline.demo import demo_bytes
from siteline.demo_cache import SEED
from siteline.docx_redline import parse_docx
from siteline.evals.dataset import load_dataset
from siteline.evals.harness import parse_shards, score
from siteline.export import diff_segments
from siteline.rules import decide
from siteline.verify import verify_quote


@pytest.fixture(scope="module")
def parsed():
    return parse_docx(demo_bytes())


def test_parser_reads_every_tracked_change(parsed):
    assert parsed["counts"] == {"insertion": 4, "replacement": 7, "deletion": 2, "comment": 1}
    c4 = parsed["changes"][3]
    assert c4["kind"] == "insertion" and c4["original"] == "" and c4["siteComment"].startswith("Our counsel")
    c10 = parsed["changes"][9]
    assert c10["kind"] == "deletion" and c10["revised"] == "" and "patent filings" in c10["original"]
    assert parsed["changes"][0]["section"] == "§6.3 Start-up Fee"


def test_seed_extraction_gives_the_demo_mix(parsed):
    from siteline.pipeline import preamble

    ctx = preamble(parsed)
    outcomes = []
    for ch in parsed["changes"]:
        ex = SEED[ch["index"]]
        ok = all(verify_quote(v["quote"], ch, ctx) for v in ex["values"])
        outcomes.append(decide(ch, ex, ok).outcome)
    assert outcomes.count("accept") == 3
    assert outcomes.count("counter") == 4
    assert outcomes.count("escalate") == 4
    assert outcomes.count("human_review") == 3  # incl. change 8, a term no playbook rule covers
    assert outcomes[11] == "human_review"  # change 12's quote is not in the redline


def test_quote_verification_forgives_only_typography():
    ch = {"original": "", "revised": "Sponsor’s  review lasts sixty (60) days.", "segments": []}
    assert verify_quote("Sponsor's review lasts sixty (60) days", ch)
    assert not verify_quote("Sponsor review lasts sixty days", ch)


def test_rules_escalate_and_fail_safe():
    ch = {"kind": "replacement", "original": "Net forty-five (45) days", "revised": "Net ten (10) days"}
    ex = {"clause_type": "payment_terms", "confidence": 0.95, "values": [{"field": "net_days", "value": "10", "quote": "ten (10)"}]}
    assert decide(ch, ex, True).outcome == "escalate"
    assert decide(ch, {**ex, "confidence": 0.5}, True).outcome == "human_review"
    assert decide(ch, {"error": "no key"}, True).outcome == "human_review"


def test_payment_checks_the_fee_even_when_net_days_are_fine():
    ch = {"kind": "replacement", "original": "Net forty-five (45) days; 10% start-up fee",
          "revised": "Net forty-five (45) days; a non-refundable 25% start-up fee"}
    vals = [{"field": "net_days", "value": "45", "quote": "forty-five (45)"},
            {"field": "start_up_fee_pct", "value": "25", "quote": "25%"},
            {"field": "start_up_fee_refundable", "value": "false", "quote": "non-refundable"}]
    v = decide(ch, {"clause_type": "payment_terms", "confidence": 0.95, "values": vals}, True)
    assert (v.outcome, v.rule_id) == ("escalate", "PAY-E2")
    v = decide(ch, {"clause_type": "payment_terms", "confidence": 0.95, "values": vals[:1]}, True)
    assert (v.outcome, v.rule_id) == ("accept", "PAY-A1")


def test_governing_law_needs_a_governing_law_fact():
    ch = {"kind": "replacement", "original": "New Jersey law governs.", "revised": "New Jersey law governs this Agreement."}
    ex = {"clause_type": "governing_law", "confidence": 0.9, "values": []}
    assert decide(ch, ex, True).rule_id == "SYS-NORULE"
    public_only = {**ex, "values": [{"field": "institution_is_public", "value": "false", "quote": "Institution"}]}
    assert decide(ch, public_only, True).rule_id == "SYS-NORULE"
    home = {**ex, "values": [{"field": "governing_law_state", "value": "New Jersey", "quote": "New Jersey"}]}
    assert decide(ch, home, True).rule_id == "GOV-A1"


def test_conflicting_values_go_to_human_review():
    ch = {"kind": "replacement", "original": "a fee of ten percent (10%)", "revised": "a fee of twenty-five percent (25%)"}
    vals = [{"field": "start_up_fee_pct", "value": "25", "quote": "twenty-five percent (25%)"},
            {"field": "start_up_fee_pct", "value": "10", "quote": "ten percent (10%)"}]
    v = decide(ch, {"clause_type": "payment_terms", "confidence": 0.95, "values": vals}, True)
    assert (v.outcome, v.rule_id) == ("human_review", "SYS-CONFLICT")


def test_numeric_value_must_be_stated_in_its_quote():
    from siteline.verify import verify_value

    ch = {"original": "", "revised": "a non-refundable start-up fee of twenty-five percent (25%)", "segments": []}
    assert verify_value({"field": "start_up_fee_pct", "value": "25", "quote": "twenty-five percent (25%)"}, ch)
    assert verify_value({"field": "start_up_fee_pct", "value": "25", "quote": "twenty-five percent"}, ch)
    assert not verify_value({"field": "start_up_fee_pct", "value": "8", "quote": "twenty-five percent (25%)"}, ch)
    assert not verify_value({"field": "start_up_fee_pct", "value": "5", "quote": "twenty-five percent"}, ch)
    # Non-numeric fields only need the verbatim quote
    assert verify_value({"field": "start_up_fee_refundable", "value": "false", "quote": "non-refundable"}, ch)


def test_export_diff_tracks_only_the_changed_words():
    segs = diff_segments("survive for four (4) years", "survive for five (5) years", "S", "2026-01-01T00:00:00Z")
    assert [s["type"] for s in segs] == ["text", "del", "ins", "text"]
    assert segs[1]["text"] == "four (4)" and segs[2]["text"] == "five (5)"


def test_labeled_set_round_trips_through_word():
    items = load_dataset()
    assert len(items) == 243
    changes, _ = asyncio.run(parse_shards(items, sandboxes=0, log=lambda _: None))
    assert [c["section"] for c in changes] == [it["section"] for it in items]


def test_unsafe_accept_metric():
    rows = [
        {"gold": "escalate", "siteline": "escalate", "baseline": "accept", "siteline_quotes": [True], "baseline_quote_ok": True, "siteline_ms": 1000, "baseline_ms": 1000},
        {"gold": "escalate", "siteline": "human_review", "baseline": "counter", "siteline_quotes": [True], "baseline_quote_ok": False, "siteline_ms": 1000, "baseline_ms": 1000},
    ]
    m = {x["key"]: x for x in score(rows)["metrics"]}
    assert m["unsafe"]["siteline"] == 0 and m["unsafe"]["baseline"] == 100
    assert m["recall"]["siteline"] == 50


def test_export_is_a_valid_word_file(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()
    from siteline.extraction import SEED_CACHE
    from siteline.pipeline import TriageOptions, triage
    from siteline.export import build_export

    if not SEED_CACHE.exists():
        from siteline.demo_cache import write_seed

        write_seed()

    async def go():
        await triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx", TriageOptions(local_parser=True, use_cache=True))
        from siteline import approvals

        approvals.cancel_all()

    asyncio.run(go())
    data, meta = build_export("site-07")
    assert meta["decisions"] == 14 and meta["pending"] == 7
    z = zipfile.ZipFile(io.BytesIO(data))
    assert "word/comments.xml" in z.namelist()
    reparsed = parse_docx(data)
    assert reparsed["counts"]["comment"] + reparsed["counts"]["replacement"] + reparsed["counts"]["insertion"] + reparsed["counts"]["deletion"] >= 14
