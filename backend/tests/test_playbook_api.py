"""Editing the playbook previews, then re-decides open suggestions, like Priority settings."""

import asyncio
import copy

import pytest
from fastapi.testclient import TestClient

from siteline import approvals, playbook, store
from siteline.demo import demo_bytes
from siteline.playbook import default_playbook, load_playbook, playbook_log


def _position(pb, pid):
    return next(p for c in pb["clauses"] for p in c["positions"] if p["id"] == pid)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(playbook, "SAVED_PATH", tmp_path / "playbook.json")
    monkeypatch.setattr(playbook, "LOG_PATH", tmp_path / "playbook_log.json")
    store.reset()
    from siteline.pipeline import TriageOptions, triage

    async def go():
        await triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx", TriageOptions(local_parser=True, use_cache=True))
        approvals.cancel_all()

    asyncio.run(go())
    from siteline.api import app

    yield TestClient(app)
    approvals.cancel_all()


def _decision(rule_id):
    return next(d for d in store.get_decisions("site-07") if d["ruleId"] == rule_id)


def test_get_returns_templates_and_text(client):
    body = client.get("/api/playbook").json()
    fee = _position(body["playbook"], "start_up_fee")
    assert "{standard}" in fee["standard"] and "10%" in fee["standardText"]
    assert body["log"] == []


def test_preview_lists_changes_without_saving(client):
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["standard"]["value"] = 5
    changes = client.post("/api/playbook/preview", json={"playbook": pb}).json()["changes"]
    fee = next(c for c in changes if c["section"] == "§6.3 Start-up Fee")
    assert fee["from"]["ruleId"] == "PAY-A3P" and fee["to"]["ruleId"] == "PAY-C2"
    assert load_playbook() == default_playbook() and _decision("PAY-A3P")


def test_put_redecides_only_unconfirmed(client):
    fee = _decision("PAY-A3P")
    client.post(f"/api/decisions/{fee['id']}/confirm")
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["standard"]["value"] = 5
    _position(pb, "survival")["limits"]["accept_min"]["value"] = 6
    r = client.put("/api/playbook", json={"playbook": pb, "by": "Test reviewer"})
    assert r.status_code == 200
    assert [c["to"]["ruleId"] for c in r.json()["changes"]] == ["CONF-C1"]
    assert store.find_decision(fee["id"])[1]["ruleId"] == "PAY-A3P"  # confirmed: left alone
    assert len(playbook_log()) == 1 and playbook_log()[0]["by"] == "Test reviewer"


def test_put_accepts_rendered_text_and_stores_templates(client):
    rendered = client.get("/api/playbook").json()["playbook"]
    assert client.put("/api/playbook", json={"playbook": rendered, "by": "Test"}).status_code == 200
    assert "standardText" not in _position(load_playbook(), "start_up_fee")


def test_put_rejects_invalid(client):
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["escalate_above"]["value"] = 5
    r = client.put("/api/playbook", json={"playbook": pb, "by": "Test"})
    assert r.status_code == 422 and r.json()["errors"]
    assert load_playbook() == default_playbook() and playbook_log() == []


def test_delete_resets(client):
    pb = copy.deepcopy(default_playbook())
    _position(pb, "overhead")["limits"]["standard"]["value"] = 27
    client.put("/api/playbook", json={"playbook": pb, "by": "Test"})
    r = client.delete("/api/playbook", params={"by": "Test"})
    assert r.status_code == 200 and load_playbook() == default_playbook()
    assert len(r.json()["log"]) == 2


def test_rename_is_not_a_change(client):
    counter = _decision("IND-C1")
    store.update_decision(counter["id"], ruleId="IND-F1")
    changes = client.post("/api/playbook/preview", json={"playbook": default_playbook()}).json()["changes"]
    assert all(c["changeId"] != counter["id"] for c in changes)


def test_newly_escalated_suggestion_texts_its_approver(client):
    pb = copy.deepcopy(default_playbook())
    term = _position(pb, "site_notice")
    term["limits"]["escalate_below"]["value"], term["limits"]["standard"]["value"], term["limits"]["accept_max"]["value"] = 90, 90, 90
    r = client.put("/api/playbook", json={"playbook": pb, "by": "Test"})
    notice = next(c for c in r.json()["changes"] if c["to"]["ruleId"] == "TERM-E2")
    d = store.find_decision(notice["changeId"])[1]
    assert d["outcome"] == "escalate" and d["approval"]["state"] == "sent"


def test_save_texts_only_the_escalations_it_creates(client):
    old = next(d for d in store.get_decisions("site-07") if d["outcome"] == "escalate")
    store.update_decision(old["id"], approval={"state": "none"})  # never texted at triage (e.g. a failed send)
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["standard"]["value"] = 5  # re-decides §6.3 on the same agreement
    r = client.put("/api/playbook", json={"playbook": pb, "by": "Test"})
    assert r.json()["changes"] and all(c["changeId"] != old["id"] for c in r.json()["changes"])
    assert store.find_decision(old["id"])[1]["approval"]["state"] == "none"


def test_reset_can_be_previewed(client):
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["standard"]["value"] = 5
    client.put("/api/playbook", json={"playbook": pb, "by": "Test"})
    changes = client.post("/api/playbook/preview", json={"reset": True}).json()["changes"]
    assert [c["to"]["ruleId"] for c in changes] == ["PAY-A3P"]  # back to the widened accept
    assert _position(load_playbook(), "start_up_fee")["limits"]["standard"]["value"] == 5  # nothing saved


def test_log_records_how_many_decisions_moved(client):
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["standard"]["value"] = 5
    client.put("/api/playbook", json={"playbook": pb, "by": "Test"})
    client.delete("/api/playbook", params={"by": "Test"})
    assert [e["moved"] for e in playbook_log()] == [1, 1]


def test_agreement_mid_triage_is_not_redecided(client, monkeypatch):
    from siteline import pipeline

    monkeypatch.setattr(pipeline, "IN_FLIGHT", {"site-07"})  # a new redline from Site 07 is being triaged
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["standard"]["value"] = 5
    assert client.post("/api/playbook/preview", json={"playbook": pb}).json()["changes"] == []


def test_save_response_log_carries_the_moved_count(client):
    pb = copy.deepcopy(default_playbook())
    _position(pb, "start_up_fee")["limits"]["standard"]["value"] = 5
    assert client.put("/api/playbook", json={"playbook": pb, "by": "Test"}).json()["log"][-1]["moved"] == 1
    assert client.delete("/api/playbook", params={"by": "Test"}).json()["log"][-1]["moved"] == 1
