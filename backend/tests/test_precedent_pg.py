"""Precedent storage on a real Postgres. Runs only when SITELINE_TEST_DATABASE_URL points at a
throwaway local database (the table is dropped around each test), e.g.

    createdb siteline_test
    SITELINE_TEST_DATABASE_URL=postgresql://localhost/siteline_test uv run pytest
"""

import asyncio
import os

import pytest

from siteline import approvals, db, store
from siteline.demo import demo_bytes

URL = os.environ.get("SITELINE_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="SITELINE_TEST_DATABASE_URL not set")


def rec(id, values, site="Larkspur Cancer Institute", agreement="larkspur-nso311", clause="data_privacy"):
    return {"id": id, "siteName": site, "agreementId": agreement, "siteNumber": "04", "protocol": "NSO-311", "clauseType": clause,
            "values": values, "via": "executed", "reply": None, "decidedAt": "2025-11-20T16:00:00Z", "label": "test",
            "sourceKey": f"{agreement}/final.docx", "sourceSection": "§11.3 HIPAA", "sourceQuote": "Business Associate Agreement"}


@pytest.fixture
def pg(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "url", lambda: URL)
    monkeypatch.setattr(db, "enabled", lambda: True)
    monkeypatch.setattr(db, "_ready", False)
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    with db.connect() as conn:
        conn.execute("drop table if exists precedents")
    store.reset()
    yield
    with db.connect() as conn:
        conn.execute("drop table if exists precedents")


def test_post_then_get_by_site_name(pg):
    store.post_completed([rec("a", {"net_days": "20"}, clause="payment_terms"), rec("b", {"requires_baa": "true"}),
                          rec("c", {"requires_baa": "true"}, site="Cedar Hollow Cancer Center", agreement="site-02")])
    got = {r["id"]: r for r in store.precedents_for_site("LARKSPUR Cancer Institute.")}
    assert sorted(got) == ["a", "b"]  # only this institution, matched on the normalized name
    assert got["a"]["values"] == {"net_days": "20"} and got["a"]["decidedAt"] == "2025-11-20T16:00:00Z"
    assert got["b"]["sourceKey"] == "larkspur-nso311/final.docx" and got["b"]["sourceSection"] == "§11.3 HIPAA"
    store.post_completed([rec("b", {"requires_baa": "true"})])  # posting again changes nothing
    assert len(store.precedents_for_site("Larkspur Cancer Institute")) == 2
    assert store.state()["precedents"] == []  # nothing went to the JSON file


def test_demo_reads_precedent_from_postgres(pg):
    from siteline.pipeline import TriageOptions, triage

    store.post_completed([rec("baa", {"requires_baa": "true"})])

    async def go():
        await triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx", TriageOptions(local_parser=True, use_cache=True))
        approvals.cancel_all()

    asyncio.run(go())
    c07 = next(d for d in store.get_decisions("site-07") if d["index"] == 7)
    assert (c07["outcome"], c07["ruleId"]) == ("accept", "PREC-A1")
    assert c07["precedent"]["sameSite"][0]["sourceKey"] == "larkspur-nso311/final.docx"


def test_reset_leaves_postgres_precedents_alone(pg):
    store.post_completed([rec("keep", {"requires_baa": "true"})])
    store.reset()
    assert [r["id"] for r in store.precedents_for_site("Larkspur Cancer Institute")] == ["keep"]
