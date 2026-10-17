"""Past confirmed agreements, seeded as precedent for demos.

Each one is an earlier agreement between Northstar and an institution that also appears in the
demo or the samples, on a fictional earlier protocol (NSO-212). It accepted a few of the terms the
institution asks for again in its NSO-417 redline, so those escalations turn into PREC-A1 accepts
while the rest still go to approvers. For the Site 07 demo: subject injury and the BAA come back
as precedent; indemnification and the patent delay still text Legal.

The terms are taken from the demo and sample seeds, so they cover the asks exactly (precedent.py
matches field by field). Records are written the way a confirmed agreement writes them, each
citing a final document stored first, so no precedent cites a missing file.

All text is written for this project. It is not real contract language and comes from no real
sponsor, site or agreement (PRD clean-room rule).

Run `uv run siteline seed-precedents`. Re-running is safe: the records keep their IDs.
"""

from __future__ import annotations

from dataclasses import dataclass

from siteline import db, demo, samples, storage, store
from siteline.demo import Block, T
from siteline.demo_cache import SEED
from siteline.playbook import SPONSOR
from siteline.precedent import label_for

PROTOCOL = "NSO-212"
STUDY = "Phase I study of NSO-212 in advanced solid tumors"


@dataclass
class Term:
    clause: str
    values: list[tuple[str, str, str]]  # (field, value, verbatim quote), as in the seeds


@dataclass
class Past:
    site_number: str
    site_name: str
    decided_at: str
    blocks: list[Block]  # the institution's NSO-417 redline, where the accepted wording comes from
    terms: list[Term]

    @property
    def agreement_id(self) -> str:
        return f"nso212-site{self.site_number}"

    @property
    def source_key(self) -> str:
        return f"{self.agreement_id}/{PROTOCOL}_CTA_Site{self.site_number}_final.docx"


def _seed_term(n: int) -> Term:
    s = SEED[n]
    return Term(s["clause_type"], [(v["field"], v["value"], v["quote"]) for v in s["values"]])


def _sample_term(number: str, section: str) -> Term:
    s = next(s for s in samples.SAMPLES if s.number == number)
    ch = next(c for c in s.changes if c.section == section)
    return Term(ch.clause, ch.values)


def _sample(number: str) -> samples.Sample:
    return next(s for s in samples.SAMPLES if s.number == number)


def pasts() -> list[Past]:
    return [
        Past("07", demo.SITE["siteName"], "2025-06-12T16:00:00Z", demo.blocks(), [_seed_term(5), _seed_term(7)]),
        Past("22", _sample("22").name, "2025-03-04T15:30:00Z", samples.blocks(_sample("22")),
             [_sample_term("22", "§8.4 Term of Confidentiality")]),
        Past("25", _sample("25").name, "2025-08-21T14:00:00Z", samples.blocks(_sample("25")),
             [_sample_term("25", "§12.1 Sponsor Review")]),
        Past("27", _sample("27").name, "2025-11-10T17:15:00Z", samples.blocks(_sample("27")),
             [_sample_term("27", "§11.3 Business Associate Agreement")]),
    ]


def _accepted(segs: list[dict]) -> str:
    return "".join(s["text"] for s in segs if s["type"] != "del")


def clause(blocks: list[Block], quote: str) -> tuple[str, str]:
    """(section heading, accepted paragraph text) of the paragraph whose accepted wording holds
    `quote`. Raises ValueError when no paragraph does, so a reworded seed fails loudly."""
    section = ""
    for style, segs, _, mark in blocks:
        if style == "Heading2":
            section = _accepted(segs)
        elif not (mark and mark[0] == "del") and quote in (text := _accepted(segs)):
            return section, text
    raise ValueError(f"No paragraph holds {quote!r}")


def final_bytes(p: Past) -> bytes:
    b: list[Block] = [
        ("Title", [T("Clinical Trial Agreement")], None, None),
        ("", [T(f"Protocol {PROTOCOL}: {STUDY}. Final agreed text.")], None, None),
        ("", [T(f"This Clinical Trial Agreement is between {SPONSOR['name']} (“Sponsor”) and "
                f"{p.site_name} (“Institution”). This document is fictional and was written for Siteline demos.")], None, None),
    ]
    for t in p.terms:
        section, text = clause(p.blocks, t.values[0][2])
        b += [("Heading2", [T(section)], None, None), ("", [T(text)], None, None)]
    b.append(("", [T(f"Executed by both parties on {p.decided_at[:10]}.")], None, None))
    return demo.build_redline(b, f"{PROTOCOL} CTA, Site {p.site_number} final")


def records(p: Past) -> list[dict]:
    out = []
    for t in p.terms:
        values = {f: v for f, v, _ in t.values}
        section, _ = clause(p.blocks, t.values[0][2])
        out.append({
            "id": f"{p.agreement_id}:{t.clause}:{'+'.join(values)}",
            "siteName": p.site_name,
            "agreementId": p.agreement_id,
            "siteNumber": p.site_number,
            "protocol": PROTOCOL,
            "clauseType": t.clause,
            "values": values,
            "via": "executed",
            "reply": 1,  # the escalation an approver answered "1" (approve) before signing
            "decidedAt": p.decided_at,
            "label": label_for(values),
            "sourceKey": p.source_key,
            "sourceSection": section,
            "sourceQuote": t.values[0][2],
        })
    return out


def seed() -> dict:
    """Store each past agreement's final document, then save its precedents (Postgres when
    DATABASE_URL is set, else the state file). Raises storage.StorageError or
    store.PrecedentStoreError, before any precedent is written when the document upload fails."""
    store.state()
    ps = pasts()
    for p in ps:
        storage.put(p.source_key, final_bytes(p))
    recs = [r for p in ps for r in records(p)]
    store.post_completed(recs)
    return {"agreements": len(ps), "precedents": len(recs), "store": "postgres" if db.enabled() else "state file",
            "documents": "s3" if storage.enabled() else "local disk"}
