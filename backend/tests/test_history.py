"""Seeded past agreements (history.py): their final documents, and the escalations they turn
into PREC-A1 when the demo and sample redlines are triaged."""

import asyncio
import io
import re
import zipfile

import pytest
from fastapi.testclient import TestClient

from siteline import api, approvals, extraction, history, storage, store
from siteline.demo import demo_bytes
from siteline.pipeline import TriageOptions, triage
from siteline.samples import SAMPLES, sample_bytes


@pytest.fixture
def offline(monkeypatch, tmp_path):
    """Fresh state, the committed seed cache, and no model calls."""
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()
    monkeypatch.setattr(extraction, "LIVE_CACHE", tmp_path / "live_cache.json")

    async def no_live_calls(*args, **kwargs):
        raise AssertionError("triage must run from the seed cache, not the model")

    monkeypatch.setattr(extraction, "complete_json", no_live_calls)


def run_triage(data: bytes, name: str) -> None:
    async def go():
        try:
            await triage(data, name, TriageOptions(local_parser=True, use_cache=True))
        finally:
            approvals.cancel_all()

    asyncio.run(go())


def by_section(agreement_id: str) -> dict[str, dict]:
    return {d["section"]: d for d in store.get_decisions(agreement_id)}


def document_text(data: bytes) -> str:
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


@pytest.mark.parametrize("p", history.pasts(), ids=lambda p: f"site{p.site_number}")
def test_each_precedent_quotes_its_own_final_document(p):
    text = document_text(history.final_bytes(p))
    assert p.site_name in text and history.PROTOCOL in text
    for r in history.records(p):
        assert r["sourceQuote"] in text and r["sourceSection"] in text
        assert storage.valid_key(r["sourceKey"])


def test_seed_saves_documents_first_and_is_idempotent(offline):
    first = history.seed()
    assert first == {"agreements": 4, "precedents": 5, "store": "state file", "documents": "local disk"}
    history.seed()
    assert len(store.state()["precedents"]) == 5
    for p in history.pasts():
        assert storage.get(p.source_key) is not None


def test_site07_keeps_two_escalations_for_approvers(offline):
    history.seed()
    run_triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx")
    d = by_section("site-07")
    covered = [s for s, x in d.items() if x["ruleId"] == "PREC-A1"]
    assert sorted(covered) == ["§10.2 Subject Injury Reimbursement", "§11.3 HIPAA"]
    for s in covered:
        assert d[s]["outcome"] == "accept"
        assert d[s]["precedent"]["sameSite"][0]["sourceKey"] == "nso212-site07/NSO-212_CTA_Site07_final.docx"
    assert sorted(s for s, x in d.items() if x["outcome"] == "escalate") == ["§12.3 Patent Delay", "§9.3 Indemnification by Institution"]


@pytest.mark.parametrize("number,section", [("22", "§8.4 Term of Confidentiality"), ("25", "§12.1 Sponsor Review"),
                                            ("27", "§11.3 Business Associate Agreement")])
def test_sample_site_gets_one_escalation_from_precedent(offline, number, section):
    history.seed()
    s = next(s for s in SAMPLES if s.number == number)
    run_triage(sample_bytes(s), s.file_name)
    d = by_section(s.agreement_id)
    for c in s.changes:
        want = ("accept", "PREC-A1") if c.section == section else c.expect
        assert (d[c.section]["outcome"], d[c.section]["ruleId"]) == want, c.section
    assert any(c.expect[0] == "escalate" and c.section != section for c in s.changes), "another escalation still goes out"


def test_untouched_sites_have_no_precedent(offline):
    history.seed()
    s = next(s for s in SAMPLES if s.number == "21")
    run_triage(sample_bytes(s), s.file_name)
    assert not any(d["ruleId"] == "PREC-A1" for d in store.get_decisions(s.agreement_id))


def test_cited_document_opens_from_the_api(offline):
    history.seed()
    r = TestClient(api.app).get("/api/sources", params={"key": "nso212-site07/NSO-212_CTA_Site07_final.docx"})
    assert r.status_code == 200 and "Larkspur Cancer Institute" in document_text(r.content)
