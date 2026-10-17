"""Voice fallback: Twilio places the call (through Photon's SIP line when configured) and
collects one keypad digit with <Gather>, posted back to /api/webhooks/twilio/gather."""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import urlencode
from xml.sax.saxutils import escape

import httpx

from siteline.config import settings
from siteline.photon import e164


class VoiceError(Exception):
    pass


def gather_url(change_id: str) -> str:
    return f"{settings.public_base_url}/api/webhooks/twilio/gather?{urlencode({'changeId': change_id})}"


def call_twiml(change_id: str, script: str) -> str:
    say = escape(script)
    action = escape(gather_url(change_id))
    return (
        "<Response>"
        f'<Gather numDigits="1" timeout="8" action="{action}" method="POST">'
        f'<Say voice="Polly.Joanna">{say}</Say>'
        "</Gather>"
        f'<Gather numDigits="1" timeout="8" action="{action}" method="POST">'
        '<Say voice="Polly.Joanna">Press 1, 2 or 3.</Say>'
        "</Gather>"
        '<Say voice="Polly.Joanna">No answer recorded. Siteline will keep the text open. Goodbye.</Say>'
        "</Response>"
    )


def reply_twiml(message: str) -> str:
    return f'<Response><Say voice="Polly.Joanna">{escape(message)}</Say><Hangup/></Response>'


async def place_call(phone: str, change_id: str, script: str) -> str:
    """Start the call. Returns the Twilio call SID."""
    to = e164(phone)
    data = {"Twiml": call_twiml(change_id, script)}
    if settings.photon_sip_server and settings.photon_number:
        # Route through Photon so the approver sees the same Siteline number that texted them.
        data.update(
            {
                "To": f"sip:{to}@{settings.photon_sip_server};transport=tls;secure=true",
                "From": e164(settings.photon_number),
                "SipAuthUsername": settings.photon_sip_username,
                "SipAuthPassword": settings.photon_sip_password,
            }
        )
    else:
        data.update({"To": to, "From": e164(settings.twilio_from_number)})
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls.json"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, data=data, auth=(settings.twilio_account_sid, settings.twilio_auth_token))
    if r.status_code >= 400:
        raise VoiceError(f"Twilio returned {r.status_code}: {r.text[:300]}")
    return r.json()["sid"]


def verify_twilio(url: str, params: dict[str, str], signature: str) -> bool:
    """X-Twilio-Signature: base64(HMAC-SHA1(auth token, url + sorted key/value pairs))."""
    if not settings.twilio_auth_token or not signature:
        return False
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    expected = base64.b64encode(hmac.new(settings.twilio_auth_token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature)
