"""Counter-proposal export: a Word file with the sponsor's edits as tracked changes and one
comment per decision.

Accepted site edits are folded in as plain text. Counters and holds show as the sponsor's
tracked changes against the site's version. Undecided changes keep the site's own tracked
changes and get a "pending" comment.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from siteline import store
from siteline.approvals import REPLY_MEANING
from siteline.docx_writer import DocxWriter
from siteline.playbook import SPONSOR, approvers

SPONSOR_AUTHOR = f"{SPONSOR['name']} (via Siteline)"
OUTCOME_LABEL = {"accept": "Accept", "fallback": "Fallback", "escalate": "Escalate", "human_review": "Human review", "novel": "Novel"}


def final_text(d: dict) -> tuple[str, str | None]:
    """(status, text) where status is accepted | countered | held | pending."""
    o = store.effective_outcome(d)
    hold = d.get("counterText")
    if o == "accept":
        return "accepted", d["revised"]
    if o == "fallback":
        if hold is None:
            return "held", d["original"]
        return "countered", hold
    if o == "escalate":
        a = d["approval"]
        if a["state"] != "answered":
            return "pending", None
        if a["reply"] == 1:
            return "accepted", d["revised"]
        if a["reply"] == 2:
            fb = d.get("fallbackText")
            return ("countered", fb) if fb is not None else ("held", d["original"] if hold is None else hold)
        return "held", d["original"] if hold is None else hold
    return "pending", None


def _tokens(text: str) -> list[str]:
    return re.findall(r"\s+|[^\s]+", text)


def diff_segments(base: str, final: str, author: str, date: str) -> list[dict]:
    """Word-level prefix/suffix diff: shared text plain, the changed middle as del + ins."""
    a, b = _tokens(base), _tokens(final)
    p = 0
    while p < len(a) and p < len(b) and a[p] == b[p]:
        p += 1
    s = 0
    while s < len(a) - p and s < len(b) - p and a[-1 - s] == b[-1 - s]:
        s += 1
    segs = []
    if p:
        segs.append({"type": "text", "text": "".join(a[:p])})
    removed = "".join(a[p : len(a) - s])
    added = "".join(b[p : len(b) - s])
    if removed:
        segs.append({"type": "del", "text": removed, "author": author, "date": date})
    if added:
        segs.append({"type": "ins", "text": added, "author": author, "date": date})
    if s:
        segs.append({"type": "text", "text": "".join(a[len(a) - s :])})
    return segs


def _comment(d: dict, status: str) -> str:
    o = store.effective_outcome(d)
    who = approvers()[d["owner"]]
    lines = [f"Siteline · C{d['index']:02d} · {OUTCOME_LABEL[o]} · owner {who['name']} ({d['owner'].title()})"]
    lines.append(f"Rule {d['ruleId']}: {d['ruleText']}")
    if d.get("quote"):
        lines.append(f"Quote{'' if d.get('quoteVerified') else ' (failed verification)'}: “{d['quote']}”")
    ov = d.get("override")
    if ov:
        lines.append(f"Overridden from {OUTCOME_LABEL[d['outcome']]} to {OUTCOME_LABEL[ov['outcome']]}: {ov['reason']}")
    a = d["approval"]
    if a["state"] == "answered":
        secs = round((a["answeredAt"] - a["sentAt"]) / 1000)
        via = "iMessage" if a["channel"] == "imessage" else "voice call"
        lines.append(f"{who['name']} replied {a['reply']} ({REPLY_MEANING[a['reply']]}) via {via} in {secs} s.")
    if status == "pending":
        lines.append("Pending: no decision yet. The site's tracked change is left as received.")
    elif status == "accepted":
        lines.append("Sponsor accepts the site's language.")
    elif status == "countered":
        lines.append("Sponsor counters with the playbook fallback (tracked).")
    elif status == "held":
        lines.append("Sponsor holds the standard language (tracked).")
    if d.get("siteComment"):
        lines.append(f"Site comment: {d['siteComment']}")
    return "\n".join(lines)


def file_name(agreement_id: str) -> str:
    a = store.state()["agreements"].get(agreement_id, {})
    return f"{SPONSOR['protocol']}_CTA_Site{a.get('siteNumber', agreement_id)}_counter-proposal.docx"


def build_export(agreement_id: str) -> tuple[bytes, dict]:
    doc = store.get_document(agreement_id)
    decisions = store.get_decisions(agreement_id)
    if not doc or not decisions:
        raise KeyError(agreement_id)
    a = store.state()["agreements"][agreement_id]
    by_par = {d["paragraph"]: d for d in decisions}
    date = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    w = DocxWriter(title=f"{SPONSOR['protocol']} CTA Site {a['siteNumber']} counter-proposal")
    stats = {"accepted": 0, "countered": 0, "held": 0, "pending": 0}

    w.paragraph(
        f"Counter-proposal from {SPONSOR['name']} to {a['siteName']} (Site {a['siteNumber']}), "
        f"prepared with Siteline on {datetime.now(UTC):%B %d, %Y}. Sponsor edits are tracked; each decision has a comment.",
        style="",
    )

    for p in doc["paragraphs"]:
        d = by_par.get(p["index"])
        if d is None:
            text = "".join(s["text"] for s in p["segments"] if s["type"] != "del")
            if text or p["style"]:
                w.paragraph(text, style=p["style"])
            continue
        status, final = final_text(d)
        stats[status] += 1
        cid = w.add_comment(SPONSOR_AUTHOR, _comment(d, status), date)
        if status == "pending":
            mark = None
            if d["kind"] == "insertion" and not d["original"]:
                mark = ("ins", d["author"], date)
            elif d["kind"] == "deletion" and not d["revised"]:
                mark = ("del", d["author"], date)
            w.paragraph(p["segments"], style=p["style"], comment_ids=[cid], mark=mark)
            continue
        base = d["revised"]
        final = final or ""
        if final == base:
            w.paragraph(base or "", style=p["style"], comment_ids=[cid])
        elif not final:
            w.paragraph([{"type": "del", "text": base, "author": SPONSOR_AUTHOR, "date": date}], style=p["style"], comment_ids=[cid], mark=("del", SPONSOR_AUTHOR, date))
        elif not base:
            w.paragraph([{"type": "ins", "text": final, "author": SPONSOR_AUTHOR, "date": date}], style=p["style"], comment_ids=[cid], mark=("ins", SPONSOR_AUTHOR, date))
        else:
            w.paragraph(diff_segments(base, final, SPONSOR_AUTHOR, date), style=p["style"], comment_ids=[cid])
    return w.to_bytes(), {"fileName": file_name(agreement_id), "decisions": len(decisions), **stats}
