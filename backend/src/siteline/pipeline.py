"""Upload → parse (Daytona or local) → Claude extraction → quote check → rules → decisions."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass

from siteline import events, precedent, priority, store
from siteline.config import settings
from siteline.extraction import extract_all, extract_document
from siteline.playbook import load_playbook, owner_for
from siteline.rules import WIDENED_CLAUSES, Verdict, decide
from siteline.sandbox import SandboxError, parse_in_daytona, parse_local
from siteline.verify import verify_value


@dataclass
class TriageOptions:
    local_parser: bool = False
    use_cache: bool = True


SECTION_HINTS = [
    ("indemnif", "indemnification"),
    ("injury", "subject_injury"),
    ("publication", "publication"),
    ("publish", "publication"),
    ("patent", "publication"),
    ("confidential", "confidentiality"),
    ("intellectual", "intellectual_property"),
    ("invention", "intellectual_property"),
    ("ip", "intellectual_property"),
    ("hipaa", "data_privacy"),
    ("data", "data_privacy"),
    ("privacy", "data_privacy"),
    ("payment", "payment_terms"),
    ("fee", "payment_terms"),
    ("invoice", "payment_terms"),
    ("terminat", "termination"),
    ("law", "governing_law"),
    ("venue", "governing_law"),
]


def guess_clause(section: str) -> str:
    s = section.lower()
    for hint, clause in SECTION_HINTS:
        if re.search(rf"\b{hint}", s):
            return clause
    return "governing_law"


def site_meta(parsed: dict, file_name: str) -> dict:
    text = "\n".join("".join(s["text"] for s in p["segments"] if s["type"] != "del") for p in parsed["paragraphs"][:15])
    number = re.search(r"Site\s*(?:Number|No\.?|#)?\s*:?\s*(\d{1,3})", text, re.I) or re.search(r"Site\s*0?(\d{1,3})", file_name, re.I)
    inst = re.search(r"Institution:\s*([^,\n]+)(?:,\s*([^\n]+))?", text)
    site_number = number.group(1).zfill(2) if number else ""
    return {
        "siteNumber": site_number or "—",
        "siteName": inst.group(1).strip() if inst else re.sub(r"[_-]+", " ", file_name.rsplit(".", 1)[0]),
        "city": (inst.group(2) or "").strip() if inst else "",
        "agreementId": f"site-{site_number}" if site_number else f"agr-{uuid.uuid4().hex[:6]}",
    }


def preamble(parsed: dict) -> str:
    lines = []
    for p in parsed["paragraphs"][:12]:
        t = "".join(s["text"] for s in p["segments"] if s["type"] != "del").strip()
        if t:
            lines.append(t)
    return "\n".join(lines)


class Job:
    def __init__(self, agreement_id: str, file_name: str) -> None:
        self.id = uuid.uuid4().hex[:10]
        self.agreement_id = agreement_id
        self.file_name = file_name
        self.started = time.perf_counter()
        self.log_lines: list[str] = []

    def step(self, step: str, state: str, detail: str = "", sponsor: str | None = None) -> None:
        events.publish(
            "triage.step",
            {
                "jobId": self.id,
                "agreementId": self.agreement_id,
                "step": step,
                "state": state,
                "detail": detail,
                "sponsor": sponsor,
                "elapsedMs": round((time.perf_counter() - self.started) * 1000),
            },
        )

    def log(self, line: str) -> None:
        self.log_lines.append(line)
        events.publish("triage.log", {"jobId": self.id, "line": line})


def _verdict(change: dict, ex: dict, values: list[dict], clause: str, site_name: str, agreement_id: str,
             history: list[dict], lenient: dict | None) -> tuple[Verdict, dict | None]:
    quotes_ok = all(v["verified"] for v in values)
    verdict = decide(change, ex, quotes_ok, lenient)
    # After the rules and their fail-safes: has this site been granted this before? Always checked,
    # including widened accepts, so the reviewer sees the precedent next to the suggestion.
    return precedent.review(verdict, clause, {v["field"]: v["value"] for v in values}, site_name, agreement_id, history,
                            ex.get("novel_issue"))


def build_decisions(agreement_id: str, parsed: dict, extractions: list[dict], site_name: str = "",
                    lenient: dict | None = None) -> list[dict]:
    rules = load_playbook()
    context = preamble(parsed)
    prefix = agreement_id.replace("site-", "s")
    history = store.precedents_for_site(site_name)  # one lookup per upload, not one per change
    out = []
    for change, ex in zip(parsed["changes"], extractions, strict=True):
        values = []
        for v in ex.get("values", []) if not ex.get("error") else []:
            values.append({**v, "verified": verify_value(v, change, context)})
        quotes_ok = all(v["verified"] for v in values)
        clause = ex.get("clause_type") or guess_clause(change["section"])
        verdict, prec = _verdict(change, ex, values, clause, site_name, agreement_id, history, lenient)
        primary = next((v for v in values if not v["verified"]), values[0] if values else None)
        out.append(
            {
                "id": f"{prefix}-c{change['index']:02d}",
                "index": change["index"],
                "paragraph": change["paragraph"],
                "kind": change["kind"],
                "section": change["section"] or "Unnumbered section",
                "clauseType": clause,
                "extractedClauseType": ex.get("clause_type"),
                "original": change["original"],
                "revised": change["revised"],
                "segments": change["segments"],
                "siteComment": change.get("siteComment"),
                "author": change["author"] or "Site",
                "extracted": values,
                "quote": primary["quote"] if primary else "",
                "quoteVerified": quotes_ok and bool(values),
                "confidence": float(ex.get("confidence") or 0),
                "rationale": ex.get("rationale"),
                "novelIssue": ex.get("novel_issue"),
                "extractionError": ex.get("error"),
                "cached": bool(ex.get("cached")),
                "model": ex.get("model"),
                "outcome": verdict.outcome,
                "ruleId": verdict.rule_id,
                "ruleText": verdict.rule_text,
                "owner": owner_for(clause, rules),
                "counterText": verdict.counter_text,
                "fallbackText": verdict.fallback_text,
                "precedent": prec,
                "leniency": lenient,
                "approval": {"state": "none"},
                "confirmation": None,
            }
        )
    return out


def redecide_open(agreement_id: str, lenient: dict, dry_run: bool = False) -> list[dict]:
    """Re-run the rules on suggestions nobody has acted on yet (no confirmation, override or
    approval) in the widened clauses, with new leniency. Returns the outcomes that change;
    with dry_run nothing is saved (the settings preview)."""
    a = store.state()["agreements"].get(agreement_id, {})
    history = store.precedents_for_site(a.get("siteName", ""))
    changed = []
    for d in store.get_decisions(agreement_id):
        if d.get("confirmation") or d.get("override") or d["approval"]["state"] != "none":
            continue
        if "extractedClauseType" not in d or d["extractedClauseType"] not in WIDENED_CLAUSES:
            continue
        ex = {"clause_type": d["extractedClauseType"], "values": [{k: v[k] for k in ("field", "value", "quote")} for v in d["extracted"]],
              "confidence": d["confidence"], "novel_issue": d["novelIssue"], "error": d["extractionError"], "rationale": d["rationale"]}
        verdict, prec = _verdict(d, ex, d["extracted"], d["clauseType"], a.get("siteName", ""), agreement_id, history, lenient)
        if verdict.rule_id != d["ruleId"]:
            changed.append({"agreementId": agreement_id, "changeId": d["id"], "section": d["section"],
                            "from": {"outcome": d["outcome"], "ruleId": d["ruleId"]},
                            "to": {"outcome": verdict.outcome, "ruleId": verdict.rule_id}})
        if dry_run:
            continue
        store.update_decision(d["id"], outcome=verdict.outcome, ruleId=verdict.rule_id, ruleText=verdict.rule_text,
                              counterText=verdict.counter_text, fallbackText=verdict.fallback_text, precedent=prec, leniency=lenient)
    return changed


def leniency_now(agreement: dict, cfg: dict | None = None) -> dict:
    """Leniency from the agreement's priority (current config) and days its redline has waited."""
    cfg = cfg or priority.load_config()
    prio = priority.assess(agreement.get("priorityInputs"), cfg)
    return priority.leniency_for(prio, priority.days_since(agreement.get("redlineReceivedAt")), cfg)


def reprioritize_all(cfg: dict | None = None, dry_run: bool = False) -> list[dict]:
    """Re-decide open suggestions on every live agreement under `cfg` (default: the saved config)."""
    out: list[dict] = []
    for agreement_id in list(store.state()["decisions"]):
        a = store.state()["agreements"].get(agreement_id)
        if a and a.get("status") not in ("sent_to_site", "executed"):
            out += redecide_open(agreement_id, leniency_now(a, cfg), dry_run)
    return out


async def triage(data: bytes, file_name: str, options: TriageOptions, source: str = "upload", job: Job | None = None,
                 received_at: str | None = None) -> dict:
    """Run the full pipeline and store the agreement. Returns the agreement summary.
    `received_at` is when the redline arrived (an email's timestamp); days waiting count from it."""
    from siteline import approvals  # circular: approvals reads decisions

    job = job or Job("pending", file_name)
    job.step("upload", "done", f"{file_name} · {max(1, len(data) // 1024)} KB")

    use_daytona = settings.daytona_enabled and not options.local_parser
    sandbox_id = None
    if use_daytona:
        job.step("sandbox", "active", "Starting a fresh sandbox for this file", "Daytona")
        try:
            parsed, sandbox_id = await parse_in_daytona(data, job.log, label=job.id)
            job.step("sandbox", "done", f"Sandbox {sandbox_id} · network blocked", "Daytona")
        except SandboxError as e:
            job.log(f"Daytona failed: {e}. Falling back to the local parser.")
            job.step("sandbox", "failed", f"{e} · fell back to local parser", "Daytona")
            parsed = parse_local(data)
            use_daytona = False
    else:
        reason = "Local parser flag is on" if options.local_parser else "No DAYTONA_API_KEY; local parser"
        job.step("sandbox", "skipped", reason)
        parsed = parse_local(data)

    counts = parsed["counts"]
    parse_detail = " · ".join(
        f"{n} {k}{'' if n == 1 else 's'}" for k, n in counts.items()
    ) + " → JSON" + ("" if use_daytona else " (local parser)")
    job.step("parse", "done", parse_detail, "Daytona" if use_daytona else None)
    if not parsed["changes"]:
        raise ValueError("No tracked changes or comments found in this file.")

    meta = site_meta(parsed, file_name)
    job.agreement_id = meta["agreementId"]

    job.step("extract", "active", f"{len(parsed['changes'])} changes in parallel", "Anthropic Claude")
    text = priority.document_text(parsed)
    extractions, figures = await asyncio.gather(
        extract_all(parsed["changes"], preamble(parsed), options.use_cache),
        extract_document(text, options.use_cache),
    )
    cached = sum(1 for e in extractions if e.get("cached"))
    failed = sum(1 for e in extractions if e.get("error"))
    detail = "JSON-schema output, one verbatim quote per value"
    if cached:
        detail += f" · {cached} from cache"
    if failed:
        detail += f" · {failed} failed → human review"
    job.step("extract", "done", detail, "Anthropic Claude")

    existing = store.state()["agreements"].get(meta["agreementId"], {})
    inputs = priority.inputs_from_extraction(figures, text)
    if priority.assess(inputs)["level"] == "unknown" and (existing.get("priorityInputs") or {}).get("source") == "study plan":
        inputs = existing["priorityInputs"]  # the contract is silent: keep the study-plan figures on file
    prio_agreement = {"priorityInputs": inputs, "redlineReceivedAt": received_at or store.iso_now()}
    lenient = leniency_now(prio_agreement)
    prio = priority.assess(inputs)
    job.log(f"Priority: {prio['level']} · {prio['reason']} Leniency: {lenient['share']:.0%} of the gap ({lenient['bucket']} waiting).")

    decisions = build_decisions(meta["agreementId"], parsed, extractions, meta["siteName"], lenient)
    bad = sum(1 for d in decisions if not d["quoteVerified"] and not d["extractionError"])
    total_q = sum(len(d["extracted"]) for d in decisions)
    ok_q = sum(1 for d in decisions for v in d["extracted"] if v["verified"])
    job.step("verify", "done", f"{ok_q} of {total_q} quotes found verbatim" + (f"; {bad} change(s) sent to human review" if bad else ""))
    mix = {o: sum(1 for d in decisions if d["outcome"] == o) for o in store.OUTCOMES}
    job.step("rules", "done", "One outcome per change, rule logged · " + ", ".join(f"{n} {o.replace('_', ' ')}" for o, n in mix.items() if n))
    by_prec = sum(1 for d in decisions if d["precedent"] and d["precedent"]["downgraded"])
    if by_prec:
        job.log(f"Precedent: {by_prec} escalation(s) accepted because {meta['siteName']} was granted the same terms before")
    job.step("teardown", "done" if use_daytona else "skipped", "Only JSON left the sandbox" if use_daytona else "No sandbox to delete", "Daytona" if use_daytona else None)

    seconds = round(time.perf_counter() - job.started, 1)
    agreement = {
        "id": meta["agreementId"],
        "siteNumber": meta["siteNumber"],
        "siteName": meta["siteName"],
        "city": meta["city"],
        "status": "awaiting_approval",
        "daysOpen": existing.get("daysOpen", 0),
        "changes": len(decisions),
        "stuckClauses": [],
        "outcomeMix": mix,
        "source": source,
        "receivedAt": existing.get("receivedAt") or store.iso_now(),
        "fileName": file_name,
        "triageSeconds": seconds,
        "sandboxId": sandbox_id,
        "parser": "daytona" if use_daytona else "local",
        "log": job.log_lines,
        **prio_agreement,
    }
    approvals.cancel_for_agreement(meta["agreementId"])
    store.put_document(meta["agreementId"], parsed)
    store.set_decisions(meta["agreementId"], decisions)
    store.put_agreement(agreement)
    summary = store.get_agreement(meta["agreementId"])
    events.publish("triage.done", {"jobId": job.id, "agreement": summary, "triageSeconds": seconds})
    await approvals.start_for_agreement(meta["agreementId"])
    return summary
