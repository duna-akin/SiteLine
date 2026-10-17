import asyncio
import base64
import dataclasses
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from siteline import api, approvals, photon, store

LEGAL, FINANCE = "+15550104417", "+15550102290"


@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(approvals, "approvers", lambda: {"legal": {"phone": LEGAL}, "finance": {"phone": FINANCE}})
    store.reset()
    yield
    approvals.cancel_all()


def _esc(agreement_id, index, owner="legal", sent_at=0):
    return {"id": f"{agreement_id}-c{index:02d}", "index": index, "owner": owner, "outcome": "escalate", "section": f"§{index}",
            "clauseType": "indemnification", "original": "o", "revised": "r", "ruleId": "IND-E2", "ruleText": "t",
            "approval": {"state": "sent", "sentAt": sent_at, "channel": "imessage", "delivery": "simulated"}}


def _agreement(agreement_id, number, decisions):
    store.put_agreement({"id": agreement_id, "siteNumber": number, "siteName": f"Site {number}", "status": "awaiting_approval",
                         "receivedAt": "2026-10-01T00:00:00Z"})
    store.set_decisions(agreement_id, decisions)


def _state(change_id):
    return store.find_decision(change_id)[1]["approval"]


def text(sender, body):
    return asyncio.run(approvals.handle_inbound_text(sender, None, body))


def test_a_code_that_is_not_open_is_never_applied_elsewhere(fresh_state):
    _agreement("site-07", "07", [_esc("site-07", 3, sent_at=1), _esc("site-07", 5, sent_at=2)])
    assert text(LEGAL, "C04 2") is None
    assert _state("site-07-c03")["state"] == "sent" and _state("site-07-c05")["state"] == "sent"
    assert text(LEGAL, "C05 2")["id"] == "site-07-c05"
    assert _state("site-07-c05")["reply"] == 2


def test_a_wrong_code_with_one_open_item_is_not_applied(fresh_state):
    _agreement("site-07", "07", [_esc("site-07", 7)])
    assert text(LEGAL, "C04 1") is None
    assert _state("site-07-c07")["state"] == "sent"
    assert text(LEGAL, "1")["id"] == "site-07-c07"  # a bare digit still answers the only open item


def test_the_same_code_on_two_sites_needs_the_site(fresh_state):
    _agreement("site-07", "07", [_esc("site-07", 4, sent_at=1)])
    _agreement("site-12", "12", [_esc("site-12", 4, sent_at=2)])
    assert text(LEGAL, "C04 1") is None
    assert _state("site-07-c04")["state"] == "sent" and _state("site-12-c04")["state"] == "sent"
    assert text(LEGAL, "Site 12 C04 1")["id"] == "site-12-c04"
    assert _state("site-07-c04")["state"] == "sent"


def test_unmatched_codes_ask_the_approver_which_one(fresh_state, monkeypatch):
    sent = []

    async def fake_send(phone, body):
        sent.append((phone, body))
        return {"messageId": "m", "spaceId": "s"}

    monkeypatch.setattr(approvals, "_real_phone", lambda owner: LEGAL)
    monkeypatch.setattr(approvals, "settings", dataclasses.replace(approvals.settings, photon_api_key="k", photon_project_id="p",
                                                                   photon_agent_handle="+15550000000"))
    monkeypatch.setattr(photon, "send_text", fake_send)
    _agreement("site-07", "07", [_esc("site-07", 3)])
    assert text(LEGAL, "C09 1") is None
    assert len(sent) == 1 and "nothing was recorded" in sent[0][1] and "Site 07 C03" in sent[0][1]


def test_approvers_sharing_a_phone_can_answer_every_escalation(fresh_state, monkeypatch):
    monkeypatch.setattr(approvals, "approvers", lambda: {"legal": {"phone": LEGAL}, "finance": {"phone": LEGAL}})
    _agreement("site-07", "07", [_esc("site-07", 2, owner="legal", sent_at=1), _esc("site-07", 6, owner="finance", sent_at=2)])
    assert text(LEGAL, "C06 3")["id"] == "site-07-c06"
    assert text(LEGAL, "C02 1")["id"] == "site-07-c02"


def _signed(body: bytes, secret_bytes: bytes, msg_id: str) -> dict:
    ts = str(int(time.time()))
    sig = base64.b64encode(hmac.new(secret_bytes, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
    return {"webhook-id": msg_id, "webhook-timestamp": ts, "webhook-signature": f"v1,{sig}"}


def test_a_redelivered_webhook_is_applied_once(fresh_state, monkeypatch):
    secret = b"test-secret-bytes"
    monkeypatch.setattr(photon, "settings", dataclasses.replace(photon.settings, photon_webhook_secret="whsec_" + base64.b64encode(secret).decode()))
    _agreement("site-07", "07", [_esc("site-07", 2, sent_at=1), _esc("site-07", 6, sent_at=2)])
    body = json.dumps({"type": "message.received",
                       "data": {"object": {"content": {"type": "text", "text": "1"}, "sentBy": {"handle": LEGAL}}}}).encode()
    client = TestClient(api.app)
    for _ in range(2):
        r = client.post("/api/webhooks/photon", content=body, headers=_signed(body, secret, "msg_redelivered"))
        assert r.status_code == 204
    assert _state("site-07-c02")["reply"] == 1
    assert _state("site-07-c06")["state"] == "sent"  # the second delivery did not answer the next item


@pytest.fixture
def voice_on(monkeypatch):
    """Calls 'go out' (to a fake Twilio) for every approver; returns the list of placed calls."""
    from siteline import voice

    calls = []
    monkeypatch.setattr(approvals, "_real_phone", lambda owner: LEGAL)
    monkeypatch.setattr(approvals, "settings", dataclasses.replace(
        approvals.settings, twilio_account_sid="AC1", twilio_auth_token="t", public_base_url="https://example.test",
        twilio_from_number="+15550001111", photon_sip_server=""))

    def use(during=None):
        async def fake_call(phone, change_id, script):
            calls.append(change_id)
            await asyncio.sleep(0)
            if during:
                await during(change_id)
            return f"CA{len(calls)}"

        monkeypatch.setattr(voice, "place_call", fake_call)
        return calls

    return use


def test_a_reply_during_call_setup_is_kept(fresh_state, voice_on):
    voice_on(during=lambda change_id: approvals.record_reply(change_id, 3, "imessage"))
    _agreement("site-07", "07", [_esc("site-07", 2)])
    asyncio.run(approvals.place_call("site-07-c02"))
    a = _state("site-07-c02")
    assert (a["state"], a["reply"]) == ("answered", 3)


def test_the_timer_and_call_now_place_one_call(fresh_state, voice_on):
    calls = voice_on()
    _agreement("site-07", "07", [_esc("site-07", 2)])

    async def both():
        await asyncio.gather(approvals.place_call("site-07-c02"), approvals.place_call("site-07-c02"))

    asyncio.run(both())
    assert calls == ["site-07-c02"]
    assert (_state("site-07-c02")["state"], _state("site-07-c02")["callSid"]) == ("calling", "CA1")


def test_overriding_an_escalation_stops_its_no_reply_call(fresh_state, voice_on):
    calls = voice_on()
    _agreement("site-07", "07", [_esc("site-07", 2)])

    async def scenario():
        approvals._arm_timer("site-07-c02", 0.05)
        await api.override("site-07-c02", api.OverrideBody(outcome="accept", reason="Agreed with legal by phone"))
        await asyncio.sleep(0.1)

    asyncio.run(scenario())
    assert calls == [] and _state("site-07-c02")["state"] == "sent"


def test_the_timer_skips_a_change_that_is_no_longer_escalated(fresh_state, voice_on):
    calls = voice_on()
    d = _esc("site-07", 2)
    d["override"] = {"outcome": "accept", "reason": "resolved", "at": 0}
    _agreement("site-07", "07", [d])

    async def scenario():
        approvals._arm_timer("site-07-c02", 0)
        await asyncio.sleep(0.05)

    asyncio.run(scenario())
    assert calls == []


def test_a_failing_call_is_logged_not_lost(fresh_state, monkeypatch, caplog):
    async def boom(change_id):
        raise RuntimeError("twilio exploded")

    monkeypatch.setattr(approvals, "place_call", boom)
    _agreement("site-07", "07", [_esc("site-07", 2)])

    async def scenario():
        approvals._arm_timer("site-07-c02", 0)
        task = approvals._timers["site-07-c02"]
        await task
        return task

    task = asyncio.run(scenario())
    assert task.exception() is None and "No-reply call for site-07-c02 failed" in caplog.text


def _unreachable(monkeypatch, module):
    import httpx

    def handler(request):
        raise httpx.ConnectError("network down", request=request)

    real = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_network_errors_become_photon_and_voice_errors(fresh_state, monkeypatch):
    from siteline import voice

    _unreachable(monkeypatch, photon)
    with pytest.raises(photon.PhotonError, match="Could not reach Photon"):
        asyncio.run(photon.send_text(LEGAL, "hello"))
    with pytest.raises(voice.VoiceError, match="Could not reach Twilio"):
        asyncio.run(voice.place_call(LEGAL, "site-07-c02", "script"))
