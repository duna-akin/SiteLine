"""Approval loop: one text per escalation, reply 1/2/3, a call if no reply in time.

Delivery is real (Photon, Twilio) when configured and the approver's phone is real;
otherwise the message is "simulated" and the on-screen phone in the UI answers it.
"""

from __future__ import annotations

import asyncio
import logging
import re

from siteline import events, photon, priority, store, voice
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


def priority_line(agreement_id: str) -> str:
    """'Site 07 = high priority, ≈$79,473/week at risk (14% of planned enrollment).' or ''."""
    a = store.state()["agreements"].get(agreement_id, {})
    prio = priority.assess(a.get("priorityInputs"))
    if prio["moneyAtRiskPerWeek"] is None:
        return ""
    return (f"Site {a.get('siteNumber', '?')} = {prio['level']} priority, ≈{priority.money(prio['moneyAtRiskPerWeek'])}/week at risk"
            f" ({prio['shareOfPlanned']:.0%} of planned enrollment).")


def message_text(agreement_id: str, d: dict) -> str:
    changed = d["revised"] or f"deletes: {d['original']}"
    prec = d.get("precedent")
    stakes = priority_line(agreement_id)
    return (
        f"Siteline · {SPONSOR['protocol']} {_site_label(agreement_id)}\n"
        + (f"{stakes}\n" if stakes else "")
        + f"{_code(d)} · {d['section']}\n"
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
        f"change {d['index']}, {d['section'].replace('§', 'section ')}. {priority_line(agreement_id).replace('≈', 'about ')} "
        f"{d['ruleText'].replace('→', '.')} "
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
        if hit and hit[1]["approval"]["state"] == "sent" and store.effective_outcome(hit[1]) == "escalate":
            try:
                await place_call(change_id)
            except Exception:  # noqa: BLE001 - a background task: log it rather than lose it silently
                log.exception("No-reply call for %s failed", change_id)

    _timers[change_id] = asyncio.create_task(fire())


def _cancel_timer(change_id: str) -> None:
    t = _timers.pop(change_id, None)
    if t:
        t.cancel()


def sync_timer(change_id: str) -> None:
    """After an override changes: keep the no-reply countdown only while the change is still an
    escalation waiting on its text (resuming it with the time left), cancel it otherwise."""
    hit = store.find_decision(change_id)
    if not hit:
        return
    d = hit[1]
    if store.effective_outcome(d) == "escalate" and d["approval"]["state"] == "sent":
        if change_id not in _timers:
            elapsed = (store.now_ms() - d["approval"].get("sentAt", 0)) / 1000
            _arm_timer(change_id, settings.no_reply_seconds - elapsed)
    else:
        _cancel_timer(change_id)


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
    if a["state"] != "sent" or store.effective_outcome(d) != "escalate":
        return d
    _cancel_timer(change_id)
    # Claim the call before waiting on Twilio, so the timer and "Call now" never both place one
    claimed = {**a, "state": "calling", "callStartedAt": store.now_ms(), "callDelivery": "simulated", "callSid": None, "callError": None}
    d = store.update_decision(change_id, approval=claimed) or d
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
    # Read the decision again: a reply may have been recorded while the call was being placed
    hit = store.find_decision(change_id)
    if not hit or hit[1]["approval"]["state"] != "calling":
        return hit[1] if hit else d
    d = store.update_decision(change_id, approval={**hit[1]["approval"], "callDelivery": delivery, "callSid": call_sid, "callError": error}) or d
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


_NAMED = re.compile(r"(?:\bsite\s*0*(\d{1,3})\D{0,3})?\bC?0*(\d{1,3})\s*[:\-\s]\s*([123])\b", re.I)


def _site_number(d: dict) -> str:
    hit = store.find_decision(d["id"])
    a = store.state()["agreements"].get(hit[0], {}) if hit else {}
    return str(a.get("siteNumber") or "?")


async def _clarify(owners: list[str], open_items: list[dict]) -> None:
    """Ask which escalation a reply meant instead of guessing."""
    phone = next((p for p in (_real_phone(o) for o in owners) if p), None)
    if not (settings.photon_enabled and phone):
        return
    codes = ", ".join(f"Site {_site_number(d)} {_code(d)}" for d in open_items)
    text = (f"Siteline could not tell which escalation that reply was for, so nothing was recorded. Open: {codes}. "
            f"Reply with the site and code, e.g. “Site {_site_number(open_items[0])} {_code(open_items[0])} 1”.")
    try:
        await photon.send_text(phone, text)
    except photon.PhotonError as e:
        log.warning("Photon clarification failed: %s", e)


async def handle_inbound_text(handle: str | None, space_id: str | None, text: str) -> dict | None:
    """Match an approver's text to the escalation it names, or (a bare 1, 2 or 3) to their oldest
    open one. A named code that matches no open item, or more than one across sites, is never
    applied to another escalation: the approver is asked which one they meant."""
    if not handle and space_id:
        handle = photon.handle_for_space(space_id)
    # Approvers may share a number (a demo with one phone): their open items are answered together
    owners = [o for o, info in approvers().items() if handle and photon.e164(info["phone"]) == photon.e164(handle)]
    if not owners:
        log.info("Inbound text from unknown sender %s", handle)
        return None
    open_items = [d for d in store.pending_escalations() if d["owner"] in owners]
    if not open_items:
        return None
    if m := _NAMED.search(text):
        site, idx, reply = m.group(1), int(m.group(2)), int(m.group(3))
        named = [d for d in open_items if d["index"] == idx and (site is None or _site_number(d) == site.zfill(2))]
        if len(named) == 1:
            return await record_reply(named[0]["id"], reply, "imessage")
        log.info("Inbound reply %r names no single open escalation for %s", text, owners)
        await _clarify(owners, open_items)
        return None
    digit = re.search(r"\b([123])\b", text.strip())
    if not digit:
        return None
    return await record_reply(open_items[0]["id"], int(digit.group(1)), "imessage")


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
