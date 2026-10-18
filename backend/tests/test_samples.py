"""The nine per-clause sample redlines (samples.py), run through the whole app: upload over the
API, parse, cached extraction, quote check, rules, priority, approvals and the Word export."""

import asyncio
import inspect
import io
import json
import re
import zipfile
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from siteline import api, approvals, events, extraction, rules, store
from siteline.docx_redline import parse_docx
from siteline.extraction import SEED_CACHE, cache_key
from siteline.pipeline import preamble
from siteline.playbook import CLAUSE_TYPES, owner_for
from siteline.samples import SAMPLES, matched, sample_bytes, seed_entries
from siteline.verify import verify_value

IDS = [f"site{s.number}-{s.slug}" for s in SAMPLES]
PENDING = ("escalate", "human_review")


@pytest.fixture(scope="module")
def seeds():
    return seed_entries()


@pytest.fixture
def offline(monkeypatch, tmp_path, seeds):
    """Fresh state, an extraction cache holding only the sample seeds, and no model calls."""
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()
    monkeypatch.setattr(extraction, "SEED_CACHE", tmp_path / "seed_cache.json")
    monkeypatch.setattr(extraction, "LIVE_CACHE", tmp_path / "live_cache.json")
    extraction.store_cache(seeds, seed=True)

    async def no_live_calls(*args, **kwargs):
        raise AssertionError("sample triage must run from the seed cache, not the model")

    monkeypatch.setattr(extraction, "complete_json", no_live_calls)


@pytest.fixture
def upload(offline, monkeypatch):
    """POST a sample to /api/agreements/upload and run the triage job it starts; returns the client."""
    jobs, failures = [], []
    monkeypatch.setattr(api, "_spawn", jobs.append)
    publish = events.publish
    monkeypatch.setattr(events, "publish", lambda kind, data: (failures.append(data) if kind == "triage.failed" else None, publish(kind, data)))
    client = TestClient(api.app)

    def go(s):
        r = client.post("/api/agreements/upload", files={"file": (s.file_name, sample_bytes(s), "application/octet-stream")},
                        data={"localParser": "true"})
        assert r.status_code == 200 and r.json()["fileName"] == s.file_name

        async def run():
            try:
                await jobs.pop()
            finally:
                approvals.cancel_all()

        asyncio.run(run())
        assert not failures, failures
        return client

    return go


def test_one_sample_per_clause_each_escalating_its_own_clause():
    assert sorted(s.clause for s in SAMPLES) == sorted(CLAUSE_TYPES)
    assert len({s.number for s in SAMPLES}) == len(SAMPLES)
    for s in SAMPLES:
        assert any(c.clause == s.clause and c.expect[0] == "escalate" for c in s.changes), s.number
        assert len({c.section for c in s.changes}) == len(s.changes), f"Site {s.number}: one change per section"


def test_samples_reach_every_rule_and_outcome():
    ids = set(re.findall(r'"((?:PAY|CONF|IND|SI|PUB|IP|DP|TERM|GOV|SYS)-[A-Z0-9]+)"', inspect.getsource(rules)))
    # Widened bands need high priority (Site 21 has one); an extraction error needs a failed call
    need = {i for i in ids if not i.endswith("P")} - {"SYS-ERROR"}
    got = {c.expect[1] for s in SAMPLES for c in s.changes}
    assert need <= got, f"no sample reaches {sorted(need - got)}"
    assert "PAY-A3P" in got
    assert {c.expect[0] for s in SAMPLES for c in s.changes} == set(store.OUTCOMES)
    assert {s.priority for s in SAMPLES} == {"high", "elevated", "standard"}


@pytest.mark.parametrize("s", SAMPLES, ids=IDS)
def test_sample_parses_to_its_changes(s):
    parsed = parse_docx(sample_bytes(s))
    assert len(parsed["changes"]) == len(s.changes)
    for ch, c in matched(s, parsed):
        assert ch["author"] == s.author
        if c.mark == "ins":
            assert ch["kind"] == "insertion" and ch["original"] == ""
        if c.mark == "del":
            assert ch["kind"] == "deletion" and ch["revised"] == ""
        if c.comment:
            assert ch["siteComment"] == c.comment
        if c.comment and not any(seg["type"] != "text" for seg in c.segments):
            assert ch["kind"] == "comment"


@pytest.mark.parametrize("s", SAMPLES, ids=IDS)
def test_seed_quotes_are_verbatim(s):
    parsed = parse_docx(sample_bytes(s))
    context = preamble(parsed)
    for ch, c in matched(s, parsed):
        ok = [verify_value(v, ch, context) for v in c.seed()["values"]]
        # Site 28 §14.7 paraphrases its quote on purpose
        assert all(ok) == (c.expect[1] != "SYS-QUOTE"), (c.section, ok)


@pytest.mark.parametrize("s", SAMPLES, ids=IDS)
def test_sample_comes_through_the_app(s, upload):
    client = upload(s)
    body = client.get(f"/api/agreements/{s.agreement_id}").json()
    a, decisions = body["agreement"], body["decisions"]
    specs = {c.section: c for c in s.changes}

    # The site, read from the preamble, and its priority from the contract's own figures
    assert (a["siteNumber"], a["siteName"], a["city"]) == (s.number, s.name, s.city)
    assert a["priority"]["level"] == s.priority
    assert all(f["verified"] for f in a["priorityInputs"]["figures"])

    # One decision per change, each with the outcome and rule a contract manager expects
    assert {d["section"]: (d["outcome"], d["ruleId"]) for d in decisions} == {c.section: c.expect for c in s.changes}
    assert a["outcomeMix"] == {o: sum(c.expect[0] == o for c in s.changes) for o in store.OUTCOMES}
    for d in decisions:
        c = specs[d["section"]]
        assert d["cached"] and not d["extractionError"], d["section"]
        assert d["clauseType"] == c.clause and d["owner"] == owner_for(c.clause)
        if c.values:
            assert d["quoteVerified"] == (c.expect[1] != "SYS-QUOTE"), d["section"]
        if d["outcome"] == "fallback":
            assert d["counterText"] and d["counterText"] != d["revised"], d["section"]
        # Escalations text their owner (simulated in tests); nothing else does
        assert d["approval"]["state"] == ("sent" if d["outcome"] == "escalate" else "none"), d["section"]
        if d["outcome"] == "escalate":
            assert d["approval"]["delivery"] == "simulated"

    # Export waits until a person has confirmed every suggestion
    export = f"/api/agreements/{s.agreement_id}/export.docx"
    counts = Counter(c.expect[0] for c in s.changes)
    assert client.get(export).status_code == 409

    # An approver answers one escalation "2" (counter with the fallback), which is their sign-off;
    # a reviewer confirms the accepts and fallbacks
    answered = next((d for d in decisions if d["outcome"] == "escalate" and d["fallbackText"]), None)
    if answered:
        r = client.post(f"/api/approvals/{answered['id']}/reply", json={"reply": 2})
        assert r.json()["approval"]["state"] == "answered"
    r = client.post(f"/api/agreements/{s.agreement_id}/confirm-all", json={"by": "Test reviewer"})
    assert r.json()["confirmed"] == counts["accept"] + counts["fallback"]

    # The counter-proposal: a valid Word file with each counter as the sponsor's tracked change
    r = client.get(export)
    assert r.status_code == 200
    assert "word/comments.xml" in zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    meta = json.loads(r.headers["X-Siteline-Export"])
    assert meta["decisions"] == len(s.changes)
    assert meta["pending"] == sum(counts[o] for o in PENDING) - bool(answered)
    assert meta["countered"] == counts["fallback"] + bool(answered)
    reparsed = parse_docx(r.content)
    assert sum(reparsed["counts"].values()) == len(s.changes)
    revised = {ch["revised"] for ch in reparsed["changes"]}
    for d in decisions:
        if d["outcome"] == "fallback":
            assert d["counterText"] in revised, d["section"]
    if answered:
        assert answered["fallbackText"] in revised


def test_only_high_priority_widens_the_site21_fee(upload):
    upload(SAMPLES[0])
    fee = next(d for d in store.get_decisions("site-21") if d["section"] == "§6.3 Start-up Fee")
    assert (fee["ruleId"], fee["leniency"]["level"], fee["leniency"]["share"]) == ("PAY-A3P", "high", 0.5)
    # The same extraction without leniency is the standard counter at 10%
    v = rules.decide(fee, {"clause_type": "payment_terms", "confidence": fee["confidence"], "values": fee["extracted"]}, True)
    assert (v.outcome, v.rule_id) == ("fallback", "PAY-F2")


def test_whole_document_holds_every_paragraph_and_change(upload):
    s = SAMPLES[0]
    client = upload(s)
    r = client.get(f"/api/agreements/{s.agreement_id}/document")
    assert r.status_code == 200
    paragraphs = r.json()["paragraphs"]
    assert paragraphs == parse_docx(sample_bytes(s))["paragraphs"]
    # Unchanged clauses come along too, and every decision points at a paragraph in it
    assert any(not p["heading"] and all(seg["type"] == "text" for seg in p["segments"]) for p in paragraphs)
    assert {d["paragraph"] for d in store.get_decisions(s.agreement_id)} <= {p["index"] for p in paragraphs}
    assert client.get("/api/agreements/no-such-site/document").status_code == 404


def test_all_samples_share_one_portfolio(upload):
    for s in SAMPLES:
        upload(s)
    ids = {a["id"] for a in store.list_agreements()}
    assert {s.agreement_id for s in SAMPLES} <= ids
    queue = store.pending_escalations()
    want = Counter(owner_for(c.clause) for s in SAMPLES for c in s.changes if c.expect[0] == "escalate")
    assert Counter(d["owner"] for d in queue if d["id"].startswith(tuple(f"s{s.number}-" for s in SAMPLES))) == want


def test_committed_template_is_the_clean_form():
    """data/templates holds the form every redline is built on; run `uv run siteline make-demo` if not."""
    from siteline.demo import TEMPLATE_PATH, template_bytes

    committed = parse_docx(TEMPLATE_PATH.read_bytes())
    assert committed["changes"] == [] and committed["paragraphs"] == parse_docx(template_bytes())["paragraphs"]
    # Every article of the form, with no site's details filled in
    text = "\n".join("".join(seg["text"] for seg in p["segments"]) for p in committed["paragraphs"])
    assert "Article 17. General" in text and "Exhibit B. Budget and Payment Schedule" in text
    assert "Institution: [Institution], [City, State]" in text


@pytest.mark.parametrize("s", SAMPLES, ids=IDS)
def test_committed_samples_are_current(s, seeds):
    """data/samples and the seed cache match samples.py; run `uv run siteline make-samples` if not."""
    assert s.path.exists(), f"missing {s.path.name}"

    def shape(parsed):
        return [(c["section"], c["kind"], c["original"], c["revised"], c["siteComment"]) for c in parsed["changes"]]

    committed = parse_docx(s.path.read_bytes())
    assert shape(committed) == shape(parse_docx(sample_bytes(s)))
    cache = json.loads(SEED_CACHE.read_text())
    for ch in committed["changes"]:
        key = cache_key(ch)
        assert key in cache and cache[key] == seeds[key], ch["section"]
