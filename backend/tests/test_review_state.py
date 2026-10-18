import asyncio

import pytest
from fastapi import HTTPException

from siteline import api, approvals, events, store
from siteline.demo import demo_bytes


@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()


def _decision(outcome, override=None, approval=None):
    return {"outcome": outcome, "override": override, "approval": approval or {"state": "none"}, "confirmation": None}


def _override(outcome):
    return {"outcome": outcome, "reason": "needs a person", "at": 0}


def test_an_override_to_human_review_still_needs_a_decision():
    d = _decision("accept", override=_override("human_review"))
    assert store.is_waiting(d) and not store.is_confirmed(d)
    resolved = _decision("human_review", override=_override("accept"))
    assert not store.is_waiting(resolved) and store.is_confirmed(resolved)
    escalated = _decision("human_review", override=_override("escalate"), approval={"state": "sent", "sentAt": 0})
    assert store.is_waiting(escalated)  # waits for the approver's reply


def _triage_demo():
    from siteline.extraction import SEED_CACHE
    from siteline.pipeline import TriageOptions, triage

    if not SEED_CACHE.exists():
        from siteline.demo_cache import write_seed

        write_seed()

    async def go():
        await triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx", TriageOptions(local_parser=True, use_cache=True))
        approvals.cancel_all()

    asyncio.run(go())


def test_an_unresolved_override_keeps_the_agreement_open(fresh_state):
    _triage_demo()
    decisions = store.get_decisions("site-07")
    for d in decisions:
        if d["outcome"] == "escalate":
            asyncio.run(approvals.record_reply(d["id"], 1, "imessage"))
        elif d["outcome"] == "human_review":
            store.update_decision(d["id"], override=_override("accept"))
    held = next(d for d in decisions if d["outcome"] == "accept")
    store.update_decision(held["id"], override=_override("human_review"))
    asyncio.run(api.confirm_all("site-07"))
    for d in store.get_decisions("site-07"):
        if not store.is_waiting(d) and not store.is_confirmed(d):
            asyncio.run(api.confirm_decision(d["id"]))

    assert store.get_agreement("site-07")["status"] == "awaiting_approval"  # not "ready to export"
    with pytest.raises(HTTPException) as e:
        asyncio.run(api.complete_agreement("site-07"))
    assert e.value.status_code == 409


def test_the_extract_step_credits_openai(fresh_state, monkeypatch):
    steps = []
    real = events.publish
    monkeypatch.setattr(events, "publish", lambda name, data: (steps.append(data) if name == "triage.step" else None, real(name, data)))
    _triage_demo()
    assert {s["sponsor"] for s in steps if s["step"] == "extract"} == {"OpenAI"}
