"""Siteline vs an LLM-only baseline on the labeled set.

1. Pack the labeled changes into Word redlines (one per shard) and parse every shard in its
   own Daytona sandbox, in parallel (local parser when Daytona is off).
2. Siteline: Claude extraction → quote verification → rules engine → precedent (for items
   that carry a site history).
   Baseline: the same Claude model reads the playbook and picks the outcome directly.
3. Score: unsafe accept rate, escalation recall, triage accuracy, quote pass rate, latency.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any

import openai

from siteline import events, precedent
from siteline.config import DATA_DIR, settings
from siteline.demo import build_redline
from siteline.docx_redline import parse_docx
from siteline.evals.dataset import load_dataset
from siteline.extraction import ExtractionError, complete_json, extract_live
from siteline.playbook import playbook_text
from siteline.priority import MAX_SHARE
from siteline.rules import decide
from siteline.sandbox import SandboxError, parse_in_daytona
from siteline.verify import verify_quote, verify_value

OUTCOMES = ["accept", "fallback", "escalate", "human_review", "novel"]
# Both tiers: every row is also decided for a high-priority site at the widest allowed leniency
HIGH_TIER = {"level": "high", "share": MAX_SHARE, "days": 120, "bucket": "eval", "moneyAtRiskPerWeek": 25000}
RESULTS_DIR = DATA_DIR / "evals"
LATEST = RESULTS_DIR / "latest.json"

BASELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "outcome": {"type": "string", "enum": OUTCOMES},
        "quote": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["outcome", "quote", "rationale"],
    "additionalProperties": False,
}


def _baseline_system() -> str:
    return f"""You triage one tracked change from a site's redline of a clinical trial agreement against the sponsor's playbook.

Playbook:
{playbook_text()}

Pick exactly one outcome:
- accept: the change meets the standard or a pre-approved fallback, or changes nothing of substance.
- fallback: counter the change with the pre-approved fallback.
- escalate: the change hits an escalation trigger; the clause owner must approve.
- human_review: the wording is ambiguous and a person must read it.
- novel: the change adds a term the playbook does not address.
Also give a verbatim quote from the change that supports your answer, and one sentence of rationale."""


async def baseline(change: dict, context: str) -> dict:
    from siteline.extraction import _user_prompt

    started = time.perf_counter()
    try:
        r = await complete_json(_baseline_system(), _user_prompt(change, context), BASELINE_SCHEMA, "baseline", 8000)
    except openai.APIError as e:
        return {"error": str(e), "latencyMs": round((time.perf_counter() - started) * 1000)}
    choice = r.choices[0]
    if choice.message.refusal or choice.finish_reason == "length":
        return {"error": "refusal" if choice.message.refusal else "max_tokens", "latencyMs": round((time.perf_counter() - started) * 1000)}
    data = json.loads(choice.message.content or "")
    data["latencyMs"] = round((time.perf_counter() - started) * 1000)
    return data


def shard_docx(items: list[dict]) -> bytes:
    blocks = [("Title", [{"type": "text", "text": "Eval shard"}], None, None)]
    for it in items:
        blocks.append(("Heading2", [{"type": "text", "text": it["section"]}], None, None))
        comment = ("Site (eval)", it["comment"]) if it.get("comment") else None
        mark = (it["mark"], "Site (eval)") if it.get("mark") else None
        blocks.append(("", it["segments"], comment, mark))
    return build_redline(blocks, "Siteline eval shard")


async def parse_shards(items: list[dict], sandboxes: int, log) -> tuple[list[dict], int]:
    n = max(1, sandboxes) if settings.daytona_enabled and sandboxes > 0 else 1
    size = -(-len(items) // n)
    shards = [items[i : i + size] for i in range(0, len(items), size)]
    use_daytona = settings.daytona_enabled and sandboxes > 0

    async def one(i: int, shard: list[dict]) -> list[dict]:
        data = shard_docx(shard)
        if use_daytona:
            try:
                parsed, _ = await parse_in_daytona(data, log, label=f"eval-shard-{i}")
            except SandboxError as e:
                log(f"shard {i}: Daytona failed ({e}); parsing locally")
                parsed = parse_docx(data)
        else:
            parsed = parse_docx(data)
        changes = parsed["changes"]
        if len(changes) != len(shard):
            raise RuntimeError(f"shard {i}: expected {len(shard)} changes, parsed {len(changes)}")
        return changes

    results = await asyncio.gather(*(one(i, s) for i, s in enumerate(shards)))
    return [c for shard in results for c in shard], (len(shards) if use_daytona else 0)


def _rate(num: int, den: int) -> float:
    return round(100 * num / den, 1) if den else 0.0


def score(rows: list[dict]) -> dict[str, Any]:
    esc = [r for r in rows if r["gold"] == "escalate"]

    def unsafe(key: str) -> float:
        return _rate(sum(1 for r in esc if r[key] in ("accept", "fallback")), len(esc))

    def recall(key: str) -> float:
        return _rate(sum(1 for r in esc if r[key] == "escalate"), len(esc))

    def acc(key: str) -> float:
        return _rate(sum(1 for r in rows if r[key] == r["gold"]), len(rows))

    s_q = [v for r in rows for v in r["siteline_quotes"]]
    b_q = [r["baseline_quote_ok"] for r in rows if r["baseline_quote_ok"] is not None]

    def lat(key: str) -> float:
        vals = [r[key] for r in rows if r[key]]
        return round(sum(vals) / len(vals) / 1000, 1) if vals else 0.0

    def confusion(key: str) -> dict:
        m = {g: {p: 0 for p in OUTCOMES} for g in OUTCOMES}
        for r in rows:
            m[r["gold"]][r[key]] += 1
        return m

    metrics = [
        {"key": "unsafe", "label": "Unsafe accept rate", "description": "Should escalate, but was accepted or countered",
         "siteline": unsafe("siteline"), "baseline": unsafe("baseline"), "unit": "%", "lowerIsBetter": True, "target": "0 for Siteline"},
        {"key": "recall", "label": "Escalation recall", "description": "Labeled escalations that were escalated",
         "siteline": recall("siteline"), "baseline": recall("baseline"), "unit": "%", "lowerIsBetter": False, "target": "As high as possible"},
        {"key": "accuracy", "label": "Triage accuracy", "description": "Outcome matches the label",
         "siteline": acc("siteline"), "baseline": acc("baseline"), "unit": "%", "lowerIsBetter": False, "target": "Report both"},
        {"key": "quotes", "label": "Quote pass rate", "description": "Quotes found verbatim in the redline",
         "siteline": _rate(sum(s_q), len(s_q)), "baseline": _rate(sum(b_q), len(b_q)), "unit": "%", "lowerIsBetter": False, "target": "Near 100%"},
        {"key": "latency", "label": "Latency per change", "description": "Mean Claude call time per change",
         "siteline": lat("siteline_ms"), "baseline": lat("baseline_ms"), "unit": "s", "lowerIsBetter": True},
    ]
    if rows and all("siteline_high" in r for r in rows):
        metrics.insert(1, {
            "key": "unsafeHigh", "label": "Unsafe accept rate, high-priority site",
            "description": f"Same readings decided with the widest leniency ({MAX_SHARE:.0%} of the gap)",
            "siteline": unsafe("siteline_high"), "baseline": unsafe("baseline"), "unit": "%", "lowerIsBetter": True,
            "target": "Equal to the standard-site rate",
        })
    return {"metrics": metrics, "confusion": confusion("siteline"), "baselineConfusion": confusion("baseline"), "shouldEscalate": len(esc)}


async def run_eval(limit: int = 0, sandboxes: int = 12, concurrency: int = 8) -> dict:
    if not settings.claude_enabled:
        raise RuntimeError("The eval needs Claude: set OPENAI_API_KEY in backend/.env")
    items = load_dataset()
    if limit:
        items = items[:limit]
    run_id = f"eval-{datetime.now(UTC):%Y%m%d-%H%M%S}"

    def log(line: str) -> None:
        events.publish("eval.log", {"runId": run_id, "line": line})

    events.publish("eval.started", {"runId": run_id, "total": len(items)})
    changes, used_sandboxes = await parse_shards(items, sandboxes, log)
    log(f"parsed {len(changes)} labeled changes" + (f" in {used_sandboxes} parallel Daytona sandboxes" if used_sandboxes else " locally"))

    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(it: dict, change: dict) -> dict:
        nonlocal done
        async with sem:
            try:
                ex = await extract_live(change, it["context"])
            except ExtractionError as e:
                ex = {"error": str(e), "latencyMs": 0}
            b = await baseline(change, it["context"])
        quotes = [verify_value(v, change, it["context"]) for v in ex.get("values", [])] if not ex.get("error") else []
        verdict = decide(change, ex, all(quotes))
        # The same reading decided for a high-priority site at the widest leniency the config allows
        high = decide(change, ex, all(quotes), HIGH_TIER)
        if it.get("precedents"):
            values = {v["field"]: v["value"] for v in ex.get("values", [])} if not ex.get("error") else {}
            clause = ex.get("clause_type") or it["clause_type"]
            novel = ex.get("novel_issue")
            verdict, _ = precedent.review(verdict, clause, values, it["siteName"], it["agreementId"], it["precedents"], novel)
            high, _ = precedent.review(high, clause, values, it["siteName"], it["agreementId"], it["precedents"], novel)
        b_out = b.get("outcome") if not b.get("error") else "human_review"
        done += 1
        events.publish("eval.progress", {"runId": run_id, "done": done, "total": len(items)})
        return {
            "id": it["id"], "gold": it["gold"], "note": it["note"],
            "siteline": verdict.outcome, "rule": verdict.rule_id, "siteline_quotes": quotes,
            "siteline_high": high.outcome, "rule_high": high.rule_id,
            "siteline_ms": ex.get("latencyMs", 0), "extraction": ex,
            "baseline": b_out, "baseline_quote_ok": verify_quote(b["quote"], change, it["context"]) if b.get("quote") else None,
            "baseline_ms": b.get("latencyMs", 0), "baseline_rationale": b.get("rationale") or b.get("error"),
        }

    rows = await asyncio.gather(*(one(it, ch) for it, ch in zip(items, changes, strict=True)))
    scored = score(rows)
    result = {
        "runId": run_id,
        "harness": "Siteline eval harness",
        "model": settings.claude_model,
        "datasetName": "cta-redlines-labeled-v1",
        "labeledChanges": len(rows),
        "shouldEscalate": scored["shouldEscalate"],
        "parallelSandboxes": used_sandboxes,
        "finishedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "metrics": scored["metrics"],
        "confusion": scored["confusion"],
        "baselineConfusion": scored["baselineConfusion"],
        "placeholder": False,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "runs").mkdir(exist_ok=True)
    (RESULTS_DIR / "runs" / f"{run_id}.json").write_text(json.dumps({**result, "rows": rows}, indent=1, ensure_ascii=False))
    LATEST.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    events.publish("eval.done", {"result": result})
    return result
