"""Postgres storage for precedent history: one table, two queries.

- precedents_for_site: read at upload time, the accepted terms on record for this institution
- post_completed: written when an agreement is confirmed, one row per accepted term, each
  pointing at the final agreed document (source_key) and where in it the term sits

Set DATABASE_URL to a local Postgres now and to the Supabase connection string later; the
code is the same. Without it, store.py keeps precedents in var/state.json. The table is
created on first use.
"""

from __future__ import annotations

import re
from datetime import UTC

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from siteline.config import settings

SCHEMA = """
create table if not exists precedents (
    id text primary key,
    site_name text not null,
    site_key text not null,
    agreement_id text not null,
    site_number text not null,
    protocol text not null,
    clause_type text not null,
    terms jsonb not null,
    via text not null,
    reply smallint,
    decided_at timestamptz not null,
    label text not null,
    source_key text,
    source_section text,
    source_quote text,
    created_at timestamptz not null default now()
);
create index if not exists precedents_site_key on precedents (site_key);
-- Supabase also serves the public schema over its REST API with the anon key. Row-level
-- security with no policies closes that door; this backend connects as the table owner,
-- which RLS does not restrict.
alter table precedents enable row level security;
"""

_ready = False


def normalize_site(name: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", (name or "").lower())).strip()


def url() -> str:
    return settings.database_url


def enabled() -> bool:
    return bool(url())


def connect() -> psycopg.Connection:
    # prepare_threshold=None: Supabase's transaction pooler does not support prepared statements
    return psycopg.connect(url(), autocommit=True, row_factory=dict_row, prepare_threshold=None, connect_timeout=10)


def _ensure() -> None:
    global _ready
    if not _ready:
        with connect() as conn:
            conn.execute(SCHEMA)
        _ready = True


def _record(row: dict) -> dict:
    return {
        "id": row["id"],
        "siteName": row["site_name"],
        "agreementId": row["agreement_id"],
        "siteNumber": row["site_number"],
        "protocol": row["protocol"],
        "clauseType": row["clause_type"],
        "values": row["terms"],
        "via": row["via"],
        "reply": row["reply"],
        "decidedAt": row["decided_at"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": row["label"],
        "sourceKey": row["source_key"],
        "sourceSection": row["source_section"],
        "sourceQuote": row["source_quote"],
    }


def precedents_for_site(site_name: str) -> list[dict]:
    """Every accepted term on record for this institution, matched on its normalized name."""
    _ensure()
    with connect() as conn:
        rows = conn.execute("select * from precedents where site_key = %s order by decided_at", (normalize_site(site_name),)).fetchall()
    return [_record(r) for r in rows]


def post_completed(records: list[dict]) -> None:
    """Save the accepted terms of a confirmed agreement. Re-posting the same agreement is a no-op."""
    _ensure()
    with connect() as conn, conn.transaction():
        for r in records:
            conn.execute(
                "insert into precedents (id, site_name, site_key, agreement_id, site_number, protocol, clause_type, terms, via, reply,"
                " decided_at, label, source_key, source_section, source_quote)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict (id) do nothing",
                (r["id"], r["siteName"], normalize_site(r["siteName"]), r["agreementId"], r.get("siteNumber", ""), r.get("protocol", ""),
                 r["clauseType"], Jsonb(r["values"]), r["via"], r.get("reply"), r["decidedAt"], r.get("label", ""),
                 r.get("sourceKey"), r.get("sourceSection"), r.get("sourceQuote")),
            )
