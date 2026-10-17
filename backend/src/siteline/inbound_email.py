"""Inbound email (P2): a site emails its redline; Siteline triages the .docx attachment.

With IMAP_* set, a poller checks the mailbox every 30 s for unread mail with a .docx.
The two seeded inbox emails get generated fictional redlines so they can be triaged too.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import random
import uuid
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from siteline import events, store
from siteline.config import RUNTIME_DIR, settings
from siteline.demo import build_redline

log = logging.getLogger("siteline.inbound")
INBOX_DIR = RUNTIME_DIR / "inbox"


def attachment_path(email_id: str):
    return INBOX_DIR / f"{email_id}.docx"


def enrollment_sentence(fig: dict) -> str:
    return f"Enrollment: Institution will use reasonable efforts to enroll {fig['targetSubjects']} subjects over an enrollment period of {fig['months']} months."


def payment_sentence(fig: dict) -> str:
    return f"Per-patient payment: Sponsor will pay Institution USD {fig['perPatientUsd']:,} per enrolled subject, as set out in Exhibit B."


def seed_attachment(e: dict) -> bytes:
    """A fictional redline for a seeded email, built from labeled eval changes."""
    from siteline.evals.dataset import load_dataset

    rng = random.Random(e["id"])
    items = rng.sample([it for it in load_dataset() if it["gold"] != "novel"], 12)
    text = lambda t: [{"type": "text", "text": t}]  # noqa: E731
    blocks = [
        ("Title", text("Clinical Trial Agreement"), None, None),
        ("", text("Protocol NSO-417: Phase II study of NSO-417 in relapsed solid tumors"), None, None),
        ("", text("Sponsor: Northstar Oncology, Inc., Princeton, New Jersey"), None, None),
        ("", text(f"Institution: {e['siteName']}, {e.get('city', '')}".rstrip(", ")), None, None),
        ("", text(f"Site Number: {e.get('siteNumber', '')}"), None, None),
        ("", text("This document is fictional and was generated for the Siteline demo."), None, None),
    ]
    if fig := e.get("enrollment"):
        blocks.append(("", text(enrollment_sentence(fig)), None, None))
        blocks.append(("", text(payment_sentence(fig)), None, None))
    for it in sorted(items, key=lambda x: x["section"]):
        blocks.append(("Heading2", text(it["section"]), None, None))
        comment = (e["siteName"], it["comment"]) if it.get("comment") else None
        mark = (it["mark"], e["siteName"]) if it.get("mark") else None
        segs = [{**s, "author": e["siteName"]} if s["type"] != "text" else s for s in it["segments"]]
        blocks.append(("", segs, comment, mark))
    return build_redline(blocks, e["attachment"])


def ensure_seed_attachments() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    for e in store.list_emails():
        path = attachment_path(e["id"])
        if not path.exists() and e["id"].startswith("em-"):
            path.write_bytes(seed_attachment(e))


def _decode(value: str | None) -> str:
    return str(make_header(decode_header(value))) if value else ""


def _fetch_unseen() -> list[dict]:
    out = []
    with imaplib.IMAP4_SSL(settings.imap_host) as imap:
        imap.login(settings.imap_user, settings.imap_password)
        imap.select(settings.imap_folder)
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return out
        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            for part in msg.walk():
                name = _decode(part.get_filename())
                if name.lower().endswith(".docx"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        sender = parseaddr(msg.get("From", ""))
                        try:
                            received = parsedate_to_datetime(msg.get("Date")).isoformat()
                        except (TypeError, ValueError):
                            received = store.iso_now()
                        out.append({
                            "from": sender[1],
                            "siteName": sender[0] or sender[1].split("@")[-1],
                            "subject": _decode(msg.get("Subject")),
                            "attachment": name,
                            "receivedAt": received,
                            "data": payload,
                        })
                        break
            imap.store(num, "+FLAGS", "\\Seen")
    return out


async def receive(meta: dict, data: bytes, triage_now: bool = True) -> dict:
    """Record one inbound email with its .docx and (optionally) triage it."""
    email_id = f"em-{uuid.uuid4().hex[:8]}"
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    attachment_path(email_id).write_bytes(data)
    record = {k: v for k, v in meta.items() if k != "data"} | {"id": email_id, "triaged": False}
    store.add_email(record)
    events.publish("email.received", {"email": record})
    if triage_now:
        await triage_email(email_id)
    return record


async def triage_email(email_id: str) -> dict:
    from siteline.pipeline import TriageOptions, triage

    e = next((x for x in store.list_emails() if x["id"] == email_id), None)
    if e is None:
        raise KeyError(email_id)
    path = attachment_path(email_id)
    if not path.exists():
        ensure_seed_attachments()
    agreement = await triage(path.read_bytes(), e["attachment"], TriageOptions(use_cache=True), source="email", received_at=e.get("receivedAt"))
    store.update_email(email_id, triaged=True, agreementId=agreement["id"])
    events.publish("email.updated", {"email": {**e, "triaged": True, "agreementId": agreement["id"]}})
    return agreement


async def poll_forever(interval: float = 30) -> None:
    while True:
        try:
            for msg in await asyncio.to_thread(_fetch_unseen):
                data = msg.pop("data")
                await receive(msg, data)
        except (imaplib.IMAP4.error, OSError) as e:
            log.warning("IMAP poll failed: %s", e)
        except Exception:  # keep polling after a bad message
            log.exception("Inbound email triage failed")
        await asyncio.sleep(interval)
