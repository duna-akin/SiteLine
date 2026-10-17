"""Runtime settings, read from the environment (and backend/.env when present).

Every external integration is optional. When its credentials are missing, Siteline
falls back to the PRD's fallback for that sponsor: local parser, cached extraction,
on-screen phone, own eval harness.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("SITELINE_DATA_DIR") or BACKEND_DIR / "data")
RUNTIME_DIR = Path(os.environ.get("SITELINE_RUNTIME_DIR") or BACKEND_DIR / "var")

load_dotenv(BACKEND_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    # A blank line in .env (e.g. `APPROVER_FINANCE_PHONE=`) means "unset", not "".
    return os.environ.get(name, "").strip() or default


def _float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    # Anthropic (clause extraction). The SDK also accepts ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile.
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: _env("SITELINE_CLAUDE_MODEL", "claude-opus-5-5"))
    claude_effort: str = field(default_factory=lambda: _env("SITELINE_CLAUDE_EFFORT", "medium"))

    # Daytona (one fresh sandbox per uploaded file)
    daytona_api_key: str = field(default_factory=lambda: _env("DAYTONA_API_KEY"))

    # Photon (approver iMessages + inbound webhooks)
    photon_api_key: str = field(default_factory=lambda: _env("PHOTON_API_KEY"))
    photon_project_id: str = field(default_factory=lambda: _env("PHOTON_PROJECT_ID"))
    photon_agent_handle: str = field(default_factory=lambda: _env("PHOTON_AGENT_HANDLE"))
    photon_platform: str = field(default_factory=lambda: _env("PHOTON_PLATFORM", "imessage"))
    photon_webhook_secret: str = field(default_factory=lambda: _env("PHOTON_WEBHOOK_SECRET"))
    photon_api_base: str = field(default_factory=lambda: _env("PHOTON_API_BASE", "https://api.photon.codes"))

    # Voice fallback: Twilio places the call, through Photon's SIP line when configured
    twilio_account_sid: str = field(default_factory=lambda: _env("TWILIO_ACCOUNT_SID"))
    twilio_auth_token: str = field(default_factory=lambda: _env("TWILIO_AUTH_TOKEN"))
    twilio_from_number: str = field(default_factory=lambda: _env("TWILIO_FROM_NUMBER"))
    photon_sip_server: str = field(default_factory=lambda: _env("PHOTON_SIP_SERVER"))
    photon_sip_username: str = field(default_factory=lambda: _env("PHOTON_SIP_USERNAME"))
    photon_sip_password: str = field(default_factory=lambda: _env("PHOTON_SIP_PASSWORD"))
    photon_number: str = field(default_factory=lambda: _env("PHOTON_NUMBER"))

    # Public URL of this server, for Photon and Twilio callbacks (e.g. a cloudflared tunnel)
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL").rstrip("/"))

    # Approver phones (E.164). The defaults are fictional 555 numbers, which never get real texts.
    approver_phones: dict[str, str] = field(
        default_factory=lambda: {
            "legal": _env("APPROVER_LEGAL_PHONE", "+15550104417"),
            "finance": _env("APPROVER_FINANCE_PHONE", "+15550102290"),
            "privacy": _env("APPROVER_PRIVACY_PHONE", "+15550107731"),
        }
    )
    no_reply_seconds: float = field(default_factory=lambda: _float("SITELINE_NO_REPLY_SECONDS", 45))

    # Inbound email (P2): IMAP mailbox the sites send redlines to
    imap_host: str = field(default_factory=lambda: _env("IMAP_HOST"))
    imap_user: str = field(default_factory=lambda: _env("IMAP_USER"))
    imap_password: str = field(default_factory=lambda: _env("IMAP_PASSWORD"))
    imap_folder: str = field(default_factory=lambda: _env("IMAP_FOLDER", "INBOX"))
    inbound_address: str = field(default_factory=lambda: _env("SITELINE_INBOUND_ADDRESS", "redlines@siteline.demo"))

    # Postgres for precedent history (local now, Supabase later: only the URL changes)
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL"))

    # S3-compatible bucket for final agreed documents (Supabase Storage → S3 Connection)
    s3_endpoint: str = field(default_factory=lambda: _env("S3_ENDPOINT"))
    s3_region: str = field(default_factory=lambda: _env("S3_REGION"))
    s3_access_key_id: str = field(default_factory=lambda: _env("S3_ACCESS_KEY_ID"))
    s3_secret_access_key: str = field(default_factory=lambda: _env("S3_SECRET_ACCESS_KEY"))
    s3_bucket: str = field(default_factory=lambda: _env("S3_BUCKET"))

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key or _env("ANTHROPIC_AUTH_TOKEN") or _env("ANTHROPIC_PROFILE"))

    @property
    def daytona_enabled(self) -> bool:
        return bool(self.daytona_api_key)

    @property
    def photon_enabled(self) -> bool:
        return bool(self.photon_api_key and self.photon_project_id and self.photon_agent_handle)

    @property
    def voice_enabled(self) -> bool:
        has_caller = bool(self.photon_sip_server and self.photon_sip_username and self.photon_sip_password and self.photon_number) or bool(
            self.twilio_from_number
        )
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.public_base_url and has_caller)

    @property
    def imap_enabled(self) -> bool:
        return bool(self.imap_host and self.imap_user and self.imap_password)

    @property
    def s3_enabled(self) -> bool:
        return bool(self.s3_endpoint and self.s3_access_key_id and self.s3_secret_access_key and self.s3_bucket)


settings = Settings()


def is_fictional_phone(phone: str) -> bool:
    """555-01xx numbers are reserved for fiction; never text or call them."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return not digits or digits[-7:-4] == "555" or digits.startswith("1555") or digits.startswith("555")
