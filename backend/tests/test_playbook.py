"""The playbook: clauses → positions with limits, rendered, validated and saved."""

import copy
import json

import pytest

from siteline import playbook
from siteline.playbook import Playbook, default_playbook, load_playbook, playbook_log, render, reset_playbook, save_playbook, validate_playbook


@pytest.fixture(autouse=True)
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(playbook, "SAVED_PATH", tmp_path / "playbook.json")
    monkeypatch.setattr(playbook, "LOG_PATH", tmp_path / "playbook_log.json")


def _ids(pb):
    return {r["id"] for c in pb["clauses"] for p in c["positions"] for r in p["rules"]}


def _position(pb, clause, position):
    c = next(c for c in pb["clauses"] if c["clauseType"] == clause)
    return next(p for p in c["positions"] if p["id"] == position)


def test_default_is_valid():
    assert validate_playbook(default_playbook()) == []


def test_render_fills_placeholders():
    rendered = render(default_playbook())
    assert "10%" in _position(rendered, "payment_terms", "start_up_fee")["standardText"]
    texts = [p[k] for c in rendered["clauses"] for p in c["positions"] for k in ("standardText", "counterText", "escalateText")]
    texts += [r["whenText"] for c in rendered["clauses"] for p in c["positions"] for r in p["rules"]]
    assert texts and not [t for t in texts if "{" in t]


def test_validate_rejects_inverted_limits():
    pb = default_playbook()
    _position(pb, "payment_terms", "start_up_fee")["limits"]["escalate_above"]["value"] = 5
    errors = validate_playbook(pb)
    assert any("payment_terms" in e and "start_up_fee" in e for e in errors), errors


def test_validate_rejects_unknown_placeholder():
    pb = default_playbook()
    _position(pb, "payment_terms", "start_up_fee")["standard"] = "Up to {nope}"
    assert any("{nope}" in e for e in validate_playbook(pb))


def test_validate_requires_exact_rule_ids():
    pb = default_playbook()
    pos = _position(pb, "payment_terms", "start_up_fee")
    pos["rules"] = [r for r in pos["rules"] if r["id"] != "PAY-C2"]
    assert any("PAY-C2" in e for e in validate_playbook(pb))
    pb = default_playbook()
    _position(pb, "payment_terms", "start_up_fee")["rules"].append({"id": "PAY-Z9", "outcome": "accept", "when": "Never."})
    assert any("PAY-Z9" in e for e in validate_playbook(pb))


def test_old_saved_playbook_migrates_owners():
    old = [{"clauseType": c["clauseType"], "label": c["label"], "owner": c["owner"], "standard": "s", "fallback": "f", "escalateWhen": "e"}
           for c in default_playbook()["clauses"]]
    next(r for r in old if r["clauseType"] == "payment_terms")["owner"] = "legal"
    playbook.SAVED_PATH.write_text(json.dumps(old))
    pb = load_playbook()
    assert isinstance(pb, dict) and pb["clauses"]
    assert Playbook(pb).owner("payment_terms") == "legal"


def test_save_and_reset_log():
    pb = copy.deepcopy(default_playbook())
    _position(pb, "payment_terms", "overhead")["limits"]["standard"]["value"] = 27
    save_playbook(pb, "Test reviewer")
    assert Playbook(load_playbook()).limit("payment_terms", "overhead", "standard") == 27
    reset_playbook("Test reviewer")
    log = playbook_log()
    assert len(log) == 2 and all(e["by"] == "Test reviewer" and e["summary"] for e in log)
    assert load_playbook() == default_playbook()


def _engine_ok(pb):
    return validate_playbook(pb)


def test_validate_rejects_non_finite_limits():
    pb = default_playbook()
    _position(pb, "payment_terms", "overhead")["limits"]["standard"]["value"] = float("nan")
    assert any("overhead" in e for e in _engine_ok(pb))
    pb = default_playbook()
    _position(pb, "payment_terms", "overhead")["limits"]["escalate_above"]["value"] = float("inf")
    assert any("overhead" in e for e in _engine_ok(pb))


@pytest.mark.parametrize("break_it,needle", [
    (lambda pb: _position(pb, "payment_terms", "overhead")["limits"].update(cap=_position(pb, "payment_terms", "overhead")["limits"].pop("escalate_above")), "escalate_above"),
    (lambda pb: _position(pb, "payment_terms", "overhead")["limits"]["standard"].pop("unit"), "unit"),
    (lambda pb: _position(pb, "confidentiality", "survival").update(id="term"), "survival"),
    (lambda pb: _position(pb, "payment_terms", "overhead").update(id="indirect"), "overhead"),
])
def test_validate_rejects_playbooks_the_engine_cannot_run(break_it, needle):
    pb = default_playbook()
    break_it(pb)
    assert any(needle in e for e in _engine_ok(pb))


def test_validate_rejects_rules_moved_between_positions():
    pb = default_playbook()
    fee, overhead = _position(pb, "payment_terms", "start_up_fee"), _position(pb, "payment_terms", "overhead")
    moved = next(r for r in fee["rules"] if r["id"] == "PAY-C2")
    fee["rules"].remove(moved)
    overhead["rules"].append(moved)
    assert any("PAY-C2" in e for e in _engine_ok(pb))


def test_validate_reports_malformed_shapes_instead_of_crashing():
    assert validate_playbook({"clauses": [1]})
    pb = default_playbook()
    pb["clauses"][0]["positions"][0]["limits"] = "ten"
    assert validate_playbook(pb)


def test_numbers_render_the_same_way_as_the_browser():
    from siteline.playbook import _fmt

    assert (_fmt(0.333), _fmt(0.5), _fmt(10), _fmt(1000000), _fmt(12.5)) == ("0.333", "0.5", "10", "1000000", "12.5")
