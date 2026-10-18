from pathlib import Path

from siteline.evals.dataset import load_dataset
from siteline.evals.harness import siteline_verdict

CHALK_EVAL = Path(__file__).resolve().parents[1] / "src" / "siteline" / "evals" / "chalk_eval.py"


def test_siteline_verdict_applies_the_items_site_history():
    it = next(x for x in load_dataset() if x.get("precedents") and x["ask"] == {"requires_baa": "true"} and x["gold"] == "accept")
    text = next(s["text"] for s in it["segments"] if s["type"] == "ins")
    change = {"kind": "insertion", "original": "", "revised": text, "segments": it["segments"]}
    ex = {"clause_type": "data_privacy", "confidence": 0.95, "values": [{"field": "requires_baa", "value": "true", "quote": text}]}
    verdict, quotes = siteline_verdict(change, ex, it["context"], it)
    assert (verdict.outcome, verdict.rule_id, quotes) == ("accept", "PREC-A1", [True])
    no_history = {k: v for k, v in it.items() if k != "precedents"}
    assert siteline_verdict(change, ex, it["context"], no_history)[0].rule_id == "DP-E1"


def test_chalk_eval_matches_the_local_harness():
    # Importing chalk_eval deploys its functions, so read its source instead
    src = CHALK_EVAL.read_text()
    assert '"psycopg[binary]' in src  # the tasks import precedent/store, which load psycopg
    assert "siteline_verdict(" in src and '"item": item_column(it)' in src  # same precedent step as the harness
    assert '''CASE WHEN "output" IS NULL OR "output" = '' THEN 0.0''' in src  # a failed task never scores as safe


def test_unchanged_rows_replay_stored_answers(tmp_path, monkeypatch):
    import asyncio
    import dataclasses

    from siteline.evals import harness

    calls = {"n": 0}

    async def fake_extract(change, context=""):
        calls["n"] += 1
        return {"clause_type": "payment_terms", "values": [], "novel_issue": None, "confidence": 0.9,
                "rationale": f"call {calls['n']}", "latencyMs": 5}

    async def fake_baseline(change, context):
        calls["n"] += 1
        if "fail" in calls:
            return {"error": "OpenAI rate limit reached", "latencyMs": 0}
        return {"outcome": "accept", "quote": "", "rationale": "ok", "latencyMs": 5}

    monkeypatch.setattr(harness, "settings", dataclasses.replace(harness.settings, openai_api_key="test"))
    monkeypatch.setattr(harness, "extract_live", fake_extract)
    monkeypatch.setattr(harness, "baseline", fake_baseline)
    monkeypatch.setattr(harness, "ANSWERS", tmp_path / "answers.json")
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path / "evals")
    monkeypatch.setattr(harness, "LATEST", tmp_path / "evals" / "latest.json")
    run = lambda **kw: asyncio.run(harness.run_eval(limit=4, sandboxes=0, **kw))  # noqa: E731

    first = run()
    assert (first["liveCalls"], first["replayedRows"], calls["n"]) == (8, 0, 8)
    second = run()
    assert (second["liveCalls"], second["replayedRows"], calls["n"]) == (0, 4, 8)
    assert second["metrics"] == first["metrics"] and second["confusion"] == first["confusion"]
    calls["fail"] = True
    fresh = run(fresh=True)  # asks again; a failed answer is never stored
    assert (fresh["liveCalls"], fresh["replayedRows"]) == (8, 0)
    after = run()  # the failed answers never replaced the good ones stored before
    assert (after["liveCalls"], after["replayedRows"]) == (0, 4) and after["metrics"] == first["metrics"]
