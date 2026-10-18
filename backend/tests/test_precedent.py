import asyncio

import pytest

from siteline import approvals, precedent, storage, store
from siteline.demo import demo_bytes
from siteline.evals.dataset import load_dataset
from siteline.rules import Verdict

SITE = "Larkspur Cancer Institute"
ESC = Verdict("escalate", "DP-E1", "Site requires a Business Associate Agreement → escalate to Privacy.")


def rec(values, site=SITE, agreement="larkspur-nso311", clause="data_privacy", reply=None, id="p1"):
    return {"id": id, "siteName": site, "agreementId": agreement, "siteNumber": "04", "protocol": "NSO-311", "clauseType": clause,
            "values": values, "via": "executed" if reply is None else "approver_reply", "reply": reply,
            "decidedAt": "2025-11-20T16:00:00Z", "label": "test"}


@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()


def test_comparator_respects_each_fields_direction():
    assert precedent._value_ok("net_days", "45", "30")
    assert not precedent._value_ok("net_days", "20", "30")
    assert precedent._value_ok("start_up_fee_pct", "8", "10")
    assert not precedent._value_ok("start_up_fee_pct", "15", "10")
    # Not monotonic: more than 60 days is countered, so only the same value counts
    assert not precedent._value_ok("site_notice_days", "90", "60")
    assert precedent._value_ok("requires_baa", "True", "yes")
    assert not precedent._value_ok("invention_ownership", "joint", "sponsor")


def test_same_site_acceptance_downgrades_with_audit_trail():
    v, p = precedent.review(ESC, "data_privacy", {"requires_baa": "true"}, "Larkspur Cancer Institute.", "site-07",
                            [rec({"requires_baa": "true"})])
    assert (v.outcome, v.rule_id) == ("accept", "PREC-A1")
    assert p["downgraded"] and p["originalRuleId"] == "DP-E1" and "Larkspur" in p["summary"]


def test_other_site_acceptance_is_ignored():
    other = rec({"requires_baa": "true"}, site="Cedar Hollow Cancer Center")
    assert precedent.review(ESC, "data_privacy", {"requires_baa": "true"}, SITE, "site-07", [other]) == (ESC, None)


def test_worse_ask_or_same_agreement_never_counts():
    pay = Verdict("escalate", "PAY-E1", "Net 10 is under 30 days → escalate to Finance.")
    granted = rec({"net_days": "20"}, clause="payment_terms")
    assert precedent.review(pay, "payment_terms", {"net_days": "10"}, SITE, "site-07", [granted])[1] is None
    own = rec({"requires_baa": "true"}, agreement="site-07", reply=1)
    assert precedent.review(ESC, "data_privacy", {"requires_baa": "true"}, SITE, "site-07", [own]) == (ESC, None)


def test_fail_safes_are_untouched():
    hr = Verdict("human_review", "SYS-QUOTE", "A quote was not found verbatim in the redline → human review.")
    novel = Verdict("human_review", "SYS-NOVEL", "New term no playbook rule covers → human review.")
    for v in (hr, novel):
        assert precedent.review(v, "data_privacy", {"requires_baa": "true"}, SITE, "site-07", [rec({"requires_baa": "true"})]) == (v, None)


def _decision(i, outcome, values, approval=None, verified=True, counter=None):
    return {"id": f"s20-c0{i}", "index": i, "clauseType": "data_privacy", "owner": "privacy", "section": f"§11.{i}", "quote": "q",
            "quoteVerified": verified, "outcome": outcome, "original": "old", "revised": "new", "counterText": counter,
            "extracted": [{"field": f, "value": v, "quote": "q", "verified": verified} for f, v in values.items()],
            "approval": approval or {"state": "none"}}


def test_replies_do_not_write_precedent(fresh_state):
    store.put_agreement({"id": "site-20", "siteNumber": "20", "siteName": "Test Site", "status": "awaiting_approval", "receivedAt": "2026-10-01T00:00:00Z"})
    store.set_decisions("site-20", [_decision(1, "escalate", {"requires_baa": "true"}, {"state": "sent", "sentAt": 0})])
    asyncio.run(approvals.record_reply("s20-c01", 1, "imessage"))
    assert store.precedents_for_site("Test Site") == []


def test_completed_records_keep_only_accepted_terms_with_their_source(fresh_state):
    store.put_agreement({"id": "site-20", "siteNumber": "20", "siteName": "Test Site", "status": "awaiting_approval", "receivedAt": "2026-10-01T00:00:00Z"})
    answered = lambda r: {"state": "answered", "sentAt": 0, "answeredAt": 1, "reply": r, "channel": "imessage"}  # noqa: E731
    store.set_decisions("site-20", [
        _decision(1, "accept", {"data_use_addendum": "true"}),
        _decision(2, "escalate", {"requires_baa": "true"}, answered(1)),
        _decision(3, "escalate", {"blocks_secondary_research": "true"}, answered(3)),
        _decision(4, "fallback", {"requires_baa": "true"}, counter="countered text"),
        _decision(5, "accept", {"data_use_addendum": "true"}, verified=False),
    ])
    records = precedent.completed_records("site-20", "site-20/final.docx")
    assert [r["id"] for r in records] == ["site-20:s20-c01", "site-20:s20-c02"]
    assert records[1]["sourceKey"] == "site-20/final.docx" and records[1]["sourceSection"] == "§11.2" and records[1]["reply"] == 1
    store.post_completed(records)
    store.post_completed(records)  # confirming twice adds nothing
    assert [r["id"] for r in store.precedents_for_site("TEST SITE.")] == ["site-20:s20-c01", "site-20:s20-c02"]
    assert store.precedents_for_site("Cedar Hollow Cancer Center") == []


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


def test_confirm_is_refused_while_items_are_pending(fresh_state):
    from fastapi import HTTPException

    from siteline import api

    _triage_demo()
    with pytest.raises(HTTPException) as e:
        asyncio.run(api.complete_agreement("site-07"))
    assert e.value.status_code == 409


def test_confirm_keeps_the_final_document_and_posts_accepted_terms(fresh_state, tmp_path):
    from siteline import api

    _triage_demo()
    for d in store.get_decisions("site-07"):
        if d["outcome"] == "escalate":
            asyncio.run(approvals.record_reply(d["id"], 1, "imessage"))
        elif d["outcome"] == "human_review":
            store.update_decision(d["id"], override={"outcome": "accept", "reason": "resolved in the test", "at": 0})
    asyncio.run(api.confirm_all("site-07"))  # a person signs off on every remaining suggestion
    res = asyncio.run(api.complete_agreement("site-07"))
    assert res["agreement"]["status"] == "executed"
    assert (tmp_path / "documents" / res["finalDocumentKey"]).exists()
    saved = {r["id"]: r for r in store.precedents_for_site("Larkspur Cancer Institute")}
    assert len(saved) == res["precedentsSaved"] and "site-07:s07-c07" in saved  # BAA, approved with a 1
    assert saved["site-07:s07-c07"]["sourceKey"] == res["finalDocumentKey"]
    assert "site-07:s07-c12" not in saved  # its quote failed verification, so it is never precedent
    # The cited document comes back through the sources endpoint, byte for byte
    served = asyncio.run(api.source_document(res["finalDocumentKey"]))
    assert served.body == (tmp_path / "documents" / res["finalDocumentKey"]).read_bytes()
    assert served.media_type == storage.DOCX


def test_storage_round_trip_and_key_rules():
    storage.put("site-20/NSO-417_CTA_Site20_final.docx", b"doc")
    assert storage.get("site-20/NSO-417_CTA_Site20_final.docx") == b"doc"
    assert storage.get("site-20/missing_final.docx") is None
    assert storage.valid_key("site-07/NSO-417_CTA_Site07_final.docx")
    for bad in ("../etc/passwd.docx", "site-07/../x.docx", "site-07/x.pdf", "x.docx", "a/b/c.docx"):
        assert not storage.valid_key(bad), bad


def test_sources_endpoint_rejects_bad_and_missing_keys():
    from fastapi import HTTPException

    from siteline import api

    for key, status in (("../secret.docx", 400), ("site-20/missing_final.docx", 404)):
        with pytest.raises(HTTPException) as e:
            asyncio.run(api.source_document(key))
        assert e.value.status_code == status


def test_demo_applies_stored_precedent(fresh_state):
    from siteline.extraction import SEED_CACHE
    from siteline.pipeline import TriageOptions, triage

    if not SEED_CACHE.exists():
        from siteline.demo_cache import write_seed

        write_seed()
    store.post_completed([rec({"requires_baa": "true"}),
                          rec({"mutual_indemnity": "true"}, site="Ironwood University Medical Center", agreement="site-11",
                              clause="indemnification", id="p2")])

    async def go():
        await triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx", TriageOptions(local_parser=True, use_cache=True))
        approvals.cancel_all()

    asyncio.run(go())
    d = {x["index"]: x for x in store.get_decisions("site-07")}
    assert (d[7]["outcome"], d[7]["ruleId"], d[7]["precedent"]["originalRuleId"]) == ("accept", "PREC-A1", "DP-E1")
    assert d[7]["approval"]["state"] == "none"
    assert d[10]["outcome"] == "escalate" and d[10]["precedent"] is None
    assert d[4]["outcome"] == "escalate" and d[4]["precedent"] is None  # another institution's acceptance is not looked up
    assert d[9]["precedent"] is None  # low-confidence read stays with human review


def test_precedent_eval_cases_hold_and_never_accept_unsafely():
    cases = [it for it in load_dataset() if it.get("precedents")]
    assert sum(it["gold"] == "accept" for it in cases) >= 4 and sum(it["gold"] == "escalate" for it in cases) >= 4
    for it in cases:
        v, _ = precedent.review(Verdict("escalate", "X", "rule"), it["clause_type"], it["ask"], it["siteName"], it["agreementId"], it["precedents"])
        assert v.outcome == it["gold"], it["note"]


def test_partial_precedent_never_covers_a_broader_ask():
    pay = Verdict("escalate", "PAY-E2", "Non-refundable start-up fee of 25% is above 20% → escalate to Finance.")
    granted = rec({"start_up_fee_pct": "30", "start_up_fee_refundable": "true"}, clause="payment_terms")
    assert precedent.review(pay, "payment_terms", {"start_up_fee_pct": "25"}, SITE, "site-07", [granted]) == (pay, None)
    term = Verdict("escalate", "TERM-E1", "Termination for convenience without non-cancellable costs → escalate to Legal.")
    granted = rec({"termination_for_convenience": "true", "pays_noncancellable_costs": "true"}, clause="termination")
    assert precedent.review(term, "termination", {"termination_for_convenience": "true"}, SITE, "site-07", [granted]) == (term, None)
    # The same fields, each no worse for the sponsor, still count
    v, _ = precedent.review(pay, "payment_terms", {"start_up_fee_pct": "25", "start_up_fee_refundable": "true"}, SITE, "site-07",
                            [rec({"start_up_fee_pct": "30", "start_up_fee_refundable": "true"}, clause="payment_terms")])
    assert v.rule_id == "PREC-A1"


def test_precedent_never_downgrades_an_escalation_with_a_novel_issue():
    ind = Verdict("escalate", "IND-E2", "Site adds mutual indemnity → escalate to Legal.")
    v, p = precedent.review(ind, "indemnification", {"mutual_indemnity": "true"}, SITE, "site-07",
                            [rec({"mutual_indemnity": "true"}, clause="indemnification")], novel_issue="Bans AI training on study data")
    assert (v.outcome, v.rule_id) == ("escalate", "IND-E2") and not p["downgraded"]


def test_earlier_rounds_with_the_same_site_count_but_the_current_round_does_not():
    started = "2026-10-01T00:00:00Z"
    earlier = rec({"requires_baa": "true"}, agreement="site-07")  # decided 2025-11-20, a signed earlier round
    v, _ = precedent.review(ESC, "data_privacy", {"requires_baa": "true"}, SITE, "site-07", [earlier], round_started=started)
    assert v.rule_id == "PREC-A1"
    current = {**earlier, "decidedAt": "2026-10-02T00:00:00Z"}
    assert precedent.review(ESC, "data_privacy", {"requires_baa": "true"}, SITE, "site-07", [current], round_started=started) == (ESC, None)


def _resolve_and_complete(agreement_id="site-07"):
    from siteline import api

    for d in store.get_decisions(agreement_id):
        if store.effective_outcome(d) == "escalate" and d["approval"]["state"] != "answered":
            asyncio.run(approvals.record_reply(d["id"], 1, "imessage"))
        elif d["outcome"] == "human_review" and not d.get("override"):
            store.update_decision(d["id"], override={"outcome": "accept", "reason": "resolved in the test", "at": 0})
    asyncio.run(api.confirm_all(agreement_id))
    for d in store.get_decisions(agreement_id):  # suggestions resting on a precedent need their own confirm
        if not store.is_waiting(d) and not store.is_confirmed(d):
            asyncio.run(api.confirm_decision(d["id"]))
    return asyncio.run(api.complete_agreement(agreement_id))


def test_a_new_round_with_a_signed_site_keeps_the_signed_round(fresh_state, tmp_path):
    _triage_demo()
    first = _resolve_and_complete()
    _triage_demo()  # the site sends another redline
    a = store.state()["agreements"]["site-07"]
    assert a["status"] == "awaiting_approval" and a["round"] == 2
    assert a["previousRounds"][0]["finalDocumentKey"] == first["finalDocumentKey"] and a["previousRounds"][0]["round"] == 1
    d7 = next(d for d in store.get_decisions("site-07") if d["index"] == 7)
    assert d7["ruleId"] == "PREC-A1"  # round 1's approved BAA now counts for this site
    second = _resolve_and_complete()
    assert second["finalDocumentKey"].endswith("_r2.docx") and second["finalDocumentKey"] != first["finalDocumentKey"]
    assert (tmp_path / "documents" / first["finalDocumentKey"]).exists()
    ids = {r["id"] for r in store.precedents_for_site("Larkspur Cancer Institute")}
    assert "site-07:s07-c07" in ids and "site-07:r2:s07-c07" in ids
    assert len(ids) == first["precedentsSaved"] + second["precedentsSaved"]


def test_a_failed_precedent_save_does_not_mark_the_agreement_executed(fresh_state, monkeypatch):
    import psycopg
    from fastapi import HTTPException

    from siteline import db

    _triage_demo()

    def down(records):
        raise psycopg.OperationalError("pooler down")

    monkeypatch.setattr(db, "enabled", lambda: True)
    monkeypatch.setattr(db, "post_completed", down)
    monkeypatch.setattr(db, "precedents_for_site", lambda site: [])
    with pytest.raises(HTTPException) as e:
        _resolve_and_complete()
    assert e.value.status_code == 503
    assert store.state()["agreements"]["site-07"]["status"] != "executed"
