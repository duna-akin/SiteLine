"""Inbound email (P2): a site emails its redline; Siteline triages the .docx attachment.

With IMAP_* set, a poller checks the mailbox every 30 s. It accepts an email only when it carries
exactly one attachment and that attachment is a .docx; any other email is blocked: marked read,
logged, and never recorded. An accepted email waits in the inbox, untriaged, until a person
triages it. The two seeded inbox emails get generated fictional
redlines so they can be triaged too.
"""

from __future__ import annotations

import asyncio
import email
import email.message
import imaplib
import json
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
    """Write the seeded emails' generated redlines. They are rebuilt every time, so a file left
    in var/inbox by an older version (without the enrollment figures) never goes stale."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    seeded = {e["id"] for e in json.loads(store.SEED_PATH.read_text())["emails"]}
    for e in store.list_emails():
        path = attachment_path(e["id"])
        if e["id"] in seeded:
            path.write_bytes(seed_attachment(e))
        elif not path.exists() and e["id"].startswith("em-"):
            path.write_bytes(seed_attachment(e))


def _decode(value: str | None) -> str:
    return str(make_header(decode_header(value))) if value else ""


def _connect() -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(settings.imap_host)
    imap.login(settings.imap_user, settings.imap_password)
    imap.select(settings.imap_folder)
    return imap


def _attachments(msg: email.message.Message) -> list[email.message.Message]:
    """Parts that are attached files. Inline images (signature logos) don't count; an inline part
    with a file name that isn't an image does, since some mail clients attach that way."""
    out = []
    for part in msg.walk():
        if part.is_multipart() or not part.get_filename():
            continue
        if part.get_content_disposition() == "inline" and part.get_content_maintype() == "image":
            continue
        out.append(part)
    return out


def screen(msg: email.message.Message) -> tuple[dict | None, str]:
    """The redline in this email, or None and why it's blocked. Only an email with exactly one
    attachment, a non-empty .docx, gets through."""
    parts = _attachments(msg)
    if not parts:
        return None, "no attachment"
    if len(parts) > 1:
        return None, f"{len(parts)} attachments"
    name = _decode(parts[0].get_filename())
    if not name.lower().endswith(".docx"):
        return None, f"attachment is not a .docx ({name})"
    payload = parts[0].get_payload(decode=True)
    if not payload:
        return None, "empty attachment"
    sender = parseaddr(msg.get("From", ""))
    try:
        received = parsedate_to_datetime(msg.get("Date")).isoformat()
    except (TypeError, ValueError):
        received = store.iso_now()
    return {
        "from": sender[1],
        "siteName": sender[0] or sender[1].split("@")[-1],
        "subject": _decode(msg.get("Subject")),
        "attachment": name,
        "receivedAt": received,
        "data": payload,
    }, ""


def _fetch_unseen() -> list[dict]:
    """Unread emails that pass screen(), each with its IMAP uid. They are read with BODY.PEEK so
    they stay unread until poll_once has recorded them; a blocked email is marked read here."""
    out = []
    with _connect() as imap:
        status, data = imap.uid("search", None, "UNSEEN")
        if status != "OK":
            return out
        for uid in data[0].split():
            status, msg_data = imap.uid("fetch", uid, "(BODY.PEEK[])")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            found, reason = screen(msg)
            if found:
                out.append({"uid": uid.decode()} | found)
            else:
                log.info("Blocked inbound email %r from %s: %s", _decode(msg.get("Subject")), parseaddr(msg.get("From", ""))[1], reason)
                imap.uid("store", uid, "+FLAGS", "\\Seen")
    return out


def _mark_seen(uid: str) -> None:
    with _connect() as imap:
        imap.uid("store", uid, "+FLAGS", "\\Seen")


async def receive(meta: dict, data: bytes) -> dict:
    """Record one inbound email with its .docx. It waits in the inbox until a person triages it."""
    email_id = f"em-{uuid.uuid4().hex[:8]}"
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    attachment_path(email_id).write_bytes(data)
    record = {k: v for k, v in meta.items() if k != "data"} | {"id": email_id, "triaged": False}
    store.add_email(record)
    events.publish("email.received", {"email": record})
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


async def poll_once() -> None:
    """Record each unread redline in the inbox, untriaged, for a person to triage. Each email is
    marked read once it is recorded, and one that fails to record never stops the rest of the batch."""
    try:
        batch = await asyncio.to_thread(_fetch_unseen)
    except (imaplib.IMAP4.error, OSError) as e:
        log.warning("IMAP poll failed: %s", e)
        return
    for msg in batch:
        uid, data = msg.pop("uid"), msg.pop("data")
        try:
            await receive(msg, data)
        except Exception:  # noqa: BLE001 - left unread, so the next poll tries it again
            log.exception("Could not record inbound email %r", msg.get("subject"))
            continue
        try:
            await asyncio.to_thread(_mark_seen, uid)
        except (imaplib.IMAP4.error, OSError) as e:
            log.warning("Could not mark email %s read: %s", uid, e)


async def poll_forever(interval: float = 30) -> None:
    while True:
        await poll_once()
        await asyncio.sleep(interval)
