"""Approval loop: one text per escalation, reply 1/2/3, a call if no reply in time.

Delivery is real (Photon, Twilio) when configured and the approver's phone is real;
otherwise the message is "simulated" and the on-screen phone in the UI answers it.
"""

from __future__ import annotations

import asyncio
import logging
import re

from siteline import events, photon, store, voice
from siteline.config import is_fictional_phone, settings
from siteline.playbook import SPONSOR, approvers

log = logging.getLogger("siteline.approvals")

REPLY_MEANING = {
    1: "Approve the site’s language",
    2: "Counter with the playbook fallback",
    3: "Reject and hold the standard",
}

_timers: dict[str, asyncio.Task] = {}


def _code(d: dict) -> str:
    return f"C{d['index']:02d}"


def _site_label(agreement_id: str) -> str:
    a = store.state()["agreements"].get(agreement_id, {})
    return f"Site {a.get('siteNumber', '?')} ({a.get('siteName', 'site')})"


def _short(text: str, n: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def message_text(agreement_id: str, d: dict) -> str:
    changed = d["revised"] or f"deletes: {d['original']}"
    prec = d.get("precedent")
    return (
        f"Siteline · {SPONSOR['protocol']} {_site_label(agreement_id)}\n"
        f"{_code(d)} · {d['section']}\n"
        f"Site’s edit: “{_short(changed)}”\n"
        f"Rule {d['ruleId']}: {d['ruleText']}\n"
        + (f"Precedent: {prec['summary']}\n" if prec else "")
        + "\n"
        f"Reply 1 = approve the site’s language, 2 = counter with the playbook fallback, 3 = reject and hold the standard."
        f" (Several open? Reply “{_code(d)} 1”.)"
    )


def call_script(agreement_id: str, d: dict) -> str:
    a = store.state()["agreements"].get(agreement_id, {})
    return (
        f"This is Siteline for {SPONSOR['name']}. You have an escalation on site {a.get('siteNumber', '')}, "
        f"change {d['index']}, {d['section'].replace('§', 'section ')}. {d['ruleText'].replace('→', '.')} "
        "Press 1 to approve the site's language. Press 2 to counter with the playbook fallback. "
        "Press 3 to reject and hold the standard."
    )


def _real_phone(owner: str) -> str | None:
    phone = approvers()[owner]["phone"]
    return None if is_fictional_phone(phone) else phone


def _publish(agreement_id: str, d: dict) -> None:
    events.publish("decision.updated", {"agreementId": agreement_id, "decision": d})
    events.publish("agreement.updated", {"agreement": store.get_agreement(agreement_id)})


def _arm_timer(change_id: str, delay: float) -> None:
    old = _timers.pop(change_id, None)
    if old:
        old.cancel()

    async def fire() -> None:
        await asyncio.sleep(max(0.0, delay))
        _timers.pop(change_id, None)
        hit = store.find_decision(change_id)
        if hit and hit[1]["approval"]["state"] == "sent":
            await place_call(change_id)

    _timers[change_id] = asyncio.create_task(fire())


def _cancel_timer(change_id: str) -> None:
    t = _timers.pop(change_id, None)
    if t:
        t.cancel()


async def send_text(change_id: str) -> dict:
    hit = store.find_decision(change_id)
    if not hit:
        raise KeyError(change_id)
    agreement_id, d = hit
    if d["approval"]["state"] not in ("none",):
        return d
    phone = _real_phone(d["owner"])
    delivery, error, message_id = "simulated", None, None
    text = message_text(agreement_id, d)
    if settings.photon_enabled and phone:
        try:
            sent = await photon.send_text(phone, text)
            delivery, message_id = "photon", sent["messageId"]
        except photon.PhotonError as e:
            error = str(e)
            log.warning("Photon send failed for %s: %s", change_id, e)
    approval = {
        "state": "sent",
        "sentAt": store.now_ms(),
        "channel": "imessage",
        "delivery": delivery,
        "messageId": message_id,
        "text": text,
        "error": error,
    }
    d = store.update_decision(change_id, approval=approval) or d
    _arm_timer(change_id, settings.no_reply_seconds)
    _publish(agreement_id, d)
    return d


async def place_call(change_id: str) -> dict:
    hit = store.find_decision(change_id)
    if not hit:
        raise KeyError(change_id)
    agreement_id, d = hit
    a = d["approval"]
    if a["state"] != "sent":
        return d
    _cancel_timer(change_id)
    phone = _real_phone(d["owner"])
    delivery, call_sid, error = "simulated", None, None
    if settings.voice_enabled and phone:
        try:
            call_sid = await voice.place_call(phone, change_id, call_script(agreement_id, d))
            delivery = "twilio+photon-sip" if settings.photon_sip_server else "twilio"
            store.calls()[call_sid] = {"changeId": change_id}
        except voice.VoiceError as e:
            error = str(e)
            log.warning("Call failed for %s: %s", change_id, e)
    approval = {**a, "state": "calling", "callStartedAt": store.now_ms(), "callDelivery": delivery, "callSid": call_sid, "callError": error}
    d = store.update_decision(change_id, approval=approval) or d
    _publish(agreement_id, d)
    return d


async def record_reply(change_id: str, reply: int, channel: str) -> dict:
    if reply not in REPLY_MEANING:
        raise ValueError("Reply must be 1, 2 or 3")
    hit = store.find_decision(change_id)
    if not hit:
        raise KeyError(change_id)
    agreement_id, d = hit
    a = d["approval"]
    if a["state"] not in ("sent", "calling"):
        return d
    _cancel_timer(change_id)
    approval = {**a, "state": "answered", "reply": reply, "channel": channel, "answeredAt": store.now_ms()}
    d = store.update_decision(change_id, approval=approval) or d
    _publish(agreement_id, d)
    phone = _real_phone(d["owner"])
    if channel == "imessage" and a.get("delivery") == "photon" and phone:
        try:
            await photon.send_text(phone, f"Recorded {_code(d)}: {REPLY_MEANING[reply]}. Thank you.")
        except photon.PhotonError as e:
            log.warning("Photon confirmation failed: %s", e)
    return d


async def handle_inbound_text(handle: str | None, space_id: str | None, text: str) -> dict | None:
    """Match an approver's text to their oldest open escalation (or the one they name)."""
    if not handle and space_id:
        handle = photon.handle_for_space(space_id)
    owner = None
    for o, info in approvers().items():
        if handle and photon.e164(info["phone"]) == photon.e164(handle):
            owner = o
    if owner is None:
        log.info("Inbound text from unknown sender %s", handle)
        return None
    open_items = store.pending_escalations(owner)
    if not open_items:
        return None
    m = re.search(r"\bC?0*(\d{1,3})\s*[:\-\s]\s*([123])\b", text, re.I)
    target, reply = None, None
    if m and len(open_items) > 1:
        idx = int(m.group(1))
        target = next((d for d in open_items if d["index"] == idx), None)
        reply = int(m.group(2))
    if target is None:
        digit = re.search(r"\b([123])\b", text.strip())
        if not digit:
            return None
        target, reply = open_items[0], int(digit.group(1))
    return await record_reply(target["id"], reply, "imessage")


async def handle_call_digit(change_id: str, digit: str) -> str:
    if digit not in ("1", "2", "3"):
        return "Sorry, that key is not an option."
    d = await record_reply(change_id, int(digit), "voice")
    if d["approval"].get("reply") == int(digit):
        return f"Recorded: {REPLY_MEANING[int(digit)]}. Thank you. Goodbye."
    return "This escalation was already answered. Goodbye."


async def start_for_agreement(agreement_id: str) -> None:
    for d in store.get_decisions(agreement_id):
        if store.effective_outcome(d) == "escalate" and d["approval"]["state"] == "none":
            await send_text(d["id"])


def rearm_timers() -> None:
    """After a restart, resume the no-reply countdown for texts still waiting."""
    for d in store.pending_escalations():
        if d["approval"]["state"] == "sent":
            elapsed = (store.now_ms() - d["approval"]["sentAt"]) / 1000
            _arm_timer(d["id"], settings.no_reply_seconds - elapsed)


def cancel_for_agreement(agreement_id: str) -> None:
    for d in store.get_decisions(agreement_id):
        _cancel_timer(d["id"])


def cancel_all() -> None:
    for t in _timers.values():
        t.cancel()
    _timers.clear()
