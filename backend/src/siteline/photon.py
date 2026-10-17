"""Photon REST client: one iMessage per escalation, and verification of inbound webhooks.

API: https://api.photon.codes/v1/projects/{projectId}/{users,spaces,messages}.
Note: each person is assigned one of the project's shared iMessage lines, and a line only
sends to someone who has messaged it since their assignment, so each approver texts their
assigned line once before the demo.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import time
import uuid

import httpx

from siteline import store
from siteline.config import settings


class PhotonError(Exception):
    pass


def e164(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        digits = "1" + digits
    return f"+{digits}" if digits else ""


def _headers(idempotent: bool = False) -> dict[str, str]:
    h = {"Authorization": f"Bearer {settings.photon_api_key}", "Content-Type": "application/json"}
    if idempotent:
        h["Idempotency-Key"] = str(uuid.uuid4())
    return h


def _url(path: str) -> str:
    return f"{settings.photon_api_base}/v1/projects/{settings.photon_project_id}/{path}"


async def _post(client: httpx.AsyncClient, path: str, body: dict, idempotent: bool = False, key: str | None = None) -> dict:
    headers = _headers(idempotent)
    if key:
        headers["Idempotency-Key"] = key
    r = await client.post(_url(path), json=body, headers=headers)
    if r.status_code >= 400:
        detail = r.text[:400]
        raise PhotonError(f"Photon {path} returned {r.status_code}: {detail}")
    return r.json()


async def _user_id(client: httpx.AsyncClient, handle: str) -> str:
    users = store.photon_map()["users"]
    key = f"{settings.photon_platform}:{handle}"
    if key not in users:
        data = await _post(client, "users", {"platform": settings.photon_platform, "handle": handle})
        users[key] = data["id"]
        store.save()
    return users[key]


async def _space_id(client: httpx.AsyncClient, agent_id: str, approver_id: str) -> str:
    spaces = store.photon_map()["spaces"]
    if approver_id not in spaces:
        # Idempotency-Key is required; derive it from the participants so retries converge.
        key = hashlib.sha256(f"{agent_id}:{approver_id}".encode()).hexdigest()[:32]
        data = await _post(
            client,
            "spaces",
            {"platform": settings.photon_platform, "participantIds": [agent_id, approver_id]},
            key=key,
        )
        spaces[approver_id] = data["id"]
        store.save()
    return spaces[approver_id]


async def _line_for(client: httpx.AsyncClient, handle: str) -> str:
    """The shared iMessage line Photon assigned to `handle`; each person can be on a different line."""
    r = await client.get(_url("platforms/imessage/assignments"), headers=_headers())
    if r.status_code < 400:
        for a in r.json().get("assignments", []):
            if a.get("handle") == handle and a.get("assignedPhoneNumber"):
                return a["assignedPhoneNumber"]
    return settings.photon_agent_handle


async def send_text(phone: str, text: str) -> dict:
    """Send `text` to `phone` from the line assigned to it. Returns {"messageId", "spaceId"}.
    Every failure, including network errors and unexpected replies, raises PhotonError."""
    handle = e164(phone)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            agent_id = await _user_id(client, await _line_for(client, handle))
            approver_id = await _user_id(client, handle)
            space_id = await _space_id(client, agent_id, approver_id)
            msg = await _post(
                client,
                "messages",
                {"spaceId": space_id, "senderId": agent_id, "content": {"type": "text", "format": "plain", "text": text}},
                idempotent=True,
            )
    except httpx.HTTPError as e:
        raise PhotonError(f"Could not reach Photon: {e!r}") from e
    except (ValueError, KeyError, TypeError) as e:  # a body that is not the JSON we expect
        raise PhotonError(f"Unexpected Photon response: {e!r}") from e
    return {"messageId": msg.get("id"), "spaceId": space_id}


def handle_for_space(space_id: str) -> str | None:
    """Map a Photon space back to the approver's handle (reverse of _space_id)."""
    spaces = store.photon_map()["spaces"]
    users = store.photon_map()["users"]
    for approver_id, sid in spaces.items():
        if sid == space_id:
            for key, uid in users.items():
                if uid == approver_id:
                    return key.split(":", 1)[1]
    return None


def verify_webhook(body: bytes, headers: dict[str, str], tolerance: int = 300) -> bool:
    """Standard Webhooks signature: base64(HMAC-SHA256(secret, f"{id}.{timestamp}.{body}"))."""
    secret = settings.photon_webhook_secret
    if not secret:
        return False
    msg_id = headers.get("webhook-id", "")
    ts = headers.get("webhook-timestamp", "")
    sigs = headers.get("webhook-signature", "")
    if not (msg_id and ts and sigs):
        return False
    try:
        if abs(time.time() - int(ts)) > tolerance:
            return False
    except ValueError:
        return False
    raw = secret.removeprefix("whsec_")
    try:
        key = base64.b64decode(raw)
    except ValueError:
        key = raw.encode()
    expected = base64.b64encode(hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
    for part in sigs.split():
        _, _, sig = part.partition(",")
        if hmac.compare_digest(sig, expected):
            return True
    return False


def parse_inbound(event: dict) -> dict | None:
    """Pull sender handle, space and text out of a message.received event."""
    if event.get("type") != "message.received":
        return None
    obj = (event.get("data") or {}).get("object") or {}
    content = obj.get("content") or {}
    text = content.get("text") if isinstance(content, dict) else None
    sender = obj.get("sentBy") or obj.get("sender") or {}
    handle = sender.get("handle") if isinstance(sender, dict) else None
    space = obj.get("spaceId") or (obj.get("space") or {}).get("id")
    if not text:
        return None
    return {"handle": handle, "spaceId": space, "text": text}
