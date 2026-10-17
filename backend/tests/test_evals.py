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
