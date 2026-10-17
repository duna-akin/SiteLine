"""Runtime files saved before site priority existed must not leave priority unknown."""

import asyncio
import json

from siteline import approvals, inbound_email, store
from siteline.demo import build_redline


def _old_state(tmp_path, monkeypatch):
    """var/state.json as it was saved before site priority: seed rows without the new fields."""
    seed = json.loads(store.SEED_PATH.read_text())
    for a in seed["agreements"]:
        a.pop("priorityInputs", None)
        a.pop("redlineReceivedAt", None)
    for e in seed["emails"]:
        e.pop("enrollment", None)
    path = tmp_path / "state.json"
    path.write_text(json.dumps({**seed, "agreements": {a["id"]: a for a in seed["agreements"]},
                                "decisions": {}, "documents": {}, "photon": {"users": {}, "spaces": {}}, "calls": {}}))
    monkeypatch.setattr(store, "STATE_PATH", path)
    store.load()


def test_old_state_gets_the_seeded_priority_figures(tmp_path, monkeypatch):
    _old_state(tmp_path, monkeypatch)
    a = store.get_agreement("site-03")
    assert a["priority"]["level"] == "high" and a["priority"]["moneyAtRiskPerWeek"] == 10731
    assert store.get_agreement("site-09")["priority"]["level"] == "unknown"  # no figures on file, by design
    assert next(e for e in store.list_emails() if e["id"] == "em-1")["enrollment"]["targetSubjects"] == 20


def test_stale_seeded_attachment_is_rebuilt_and_triages_with_priority(tmp_path, monkeypatch):
    _old_state(tmp_path, monkeypatch)
    monkeypatch.setattr(inbound_email, "INBOX_DIR", tmp_path / "inbox")
    (tmp_path / "inbox").mkdir()
    e = next(x for x in store.list_emails() if x["id"] == "em-1")
    stale = build_redline([("", [{"type": "text", "text": "Site Number: 12"}], None, None)], e["attachment"])
    inbound_email.attachment_path("em-1").write_bytes(stale)  # an attachment written before the figures existed

    inbound_email.ensure_seed_attachments()

    async def go():
        agreement = await inbound_email.triage_email("em-1")
        approvals.cancel_all()
        return agreement

    agreement = asyncio.run(go())
    assert agreement["priority"]["level"] == "standard"
    assert agreement["priority"]["moneyAtRiskPerWeek"] == 2308  # 20 subjects / 24 months × $12,000
