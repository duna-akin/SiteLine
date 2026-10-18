"""Inbound email (P2): a site emails its redline; Siteline triages the .docx attachment.

With IMAP_* set, a poller checks the mailbox every 30 s for unread mail with a .docx.
The two seeded inbox emails get generated fictional redlines so they can be triaged too.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import json
import logging
import random
import uuid
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from siteline import events, store
from siteline.config import RUNTIME_DIR, settings
from siteline.cta_base import ARTICLES, PRIVATE, Site, agreement_blocks
from siteline.demo import build_redline

log = logging.getLogger("siteline.inbound")
INBOX_DIR = RUNTIME_DIR / "inbox"
# "§6", "§8", ...: the articles of the form agreement a seeded change can sit in
FORM_ARTICLES = {f"§{a.split()[1].rstrip('.')}" for a, _ in ARTICLES}


def attachment_path(email_id: str):
    return INBOX_DIR / f"{email_id}.docx"


def seed_attachment(e: dict) -> bytes:
    """A fictional redline for a seeded email: the form agreement (cta_base) with labeled eval
    changes on twelve of its sections, at most one per section."""
    from siteline.evals.dataset import load_dataset

    rng = random.Random(e["id"])
    pool = [it for it in load_dataset() if it["note"] != "no playbook rule" and it["section"].split(".")[0] in FORM_ARTICLES]
    rng.shuffle(pool)
    picked: dict[str, dict] = {}
    for it in pool:
        picked.setdefault(it["section"].split()[0], it)
        if len(picked) == 12:
            break
    fig = e.get("enrollment") or {}
    site = Site(e.get("siteNumber", ""), e["siteName"], e.get("city", ""), e.get("status", PRIVATE),
                fig.get("targetSubjects"), fig.get("months"), fig.get("perPatientUsd"))
    edits = [
        (it["section"],
         [{**s, "author": e["siteName"]} if s["type"] != "text" else s for s in it["segments"]],
         (e["siteName"], it["comment"]) if it.get("comment") else None,
         (it["mark"], e["siteName"]) if it.get("mark") else None)
        for it in picked.values()
    ]
    return build_redline(agreement_blocks(site, edits, "This document is fictional and was generated for the Siteline demo."),
                         e["attachment"])


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


def _fetch_unseen() -> list[dict]:
    """Unread emails with a .docx attachment, each with its IMAP uid. They are read with
    BODY.PEEK so they stay unread until poll_once has recorded them; an email without a .docx
    is marked read here."""
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
            found = None
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
                        found = {
                            "uid": uid.decode(),
                            "from": sender[1],
                            "siteName": sender[0] or sender[1].split("@")[-1],
                            "subject": _decode(msg.get("Subject")),
                            "attachment": name,
                            "receivedAt": received,
                            "data": payload,
                        }
                        break
            if found:
                out.append(found)
            else:
                imap.uid("store", uid, "+FLAGS", "\\Seen")
    return out


def _mark_seen(uid: str) -> None:
    with _connect() as imap:
        imap.uid("store", uid, "+FLAGS", "\\Seen")


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


async def poll_once() -> None:
    """Record and triage each unread redline. Each email is marked read once it is recorded, and
    one that fails (say, a .docx with no tracked changes) never stops the rest of the batch."""
    try:
        batch = await asyncio.to_thread(_fetch_unseen)
    except (imaplib.IMAP4.error, OSError) as e:
        log.warning("IMAP poll failed: %s", e)
        return
    for msg in batch:
        uid, data = msg.pop("uid"), msg.pop("data")
        try:
            record = await receive(msg, data, triage_now=False)
        except Exception:  # noqa: BLE001 - left unread, so the next poll tries it again
            log.exception("Could not record inbound email %r", msg.get("subject"))
            continue
        try:
            await asyncio.to_thread(_mark_seen, uid)
        except (imaplib.IMAP4.error, OSError) as e:
            log.warning("Could not mark email %s read: %s", uid, e)
        try:
            await triage_email(record["id"])
        except Exception:  # noqa: BLE001 - it stays in the inbox, untriaged, for a person to look at
            log.exception("Inbound email triage failed for %s", record["id"])


async def poll_forever(interval: float = 30) -> None:
    while True:
        await poll_once()
        await asyncio.sleep(interval)
