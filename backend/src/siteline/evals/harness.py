"""Siteline vs an LLM-only baseline on the labeled set.

1. Pack the labeled changes into Word redlines (one per shard) and parse every shard in its
   own Daytona sandbox, in parallel (local parser when Daytona is off).
2. Siteline: OpenAI extraction → quote verification → rules engine → precedent (for items
   that carry a site history).
   Baseline: the same OpenAI model reads the playbook and picks the outcome directly.
3. Score: unsafe accept rate, escalation recall, triage accuracy, quote pass rate, latency.

Each row's model answers are stored under its id and a hash of everything that shapes them
(model, effort, system prompt with the playbook, the change and its context, the schema) and
replayed on the next run when none of that changed, so an unchanged row costs no API call.
Keyed per row because some rows share a change and differ only in site history, and the
model doesn't answer the same prompt identically twice. Quote checks, the
rules engine and precedent run again on every row. `fresh=True` asks the model again.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any

from siteline import events, precedent
from siteline.config import DATA_DIR, RUNTIME_DIR, settings
from siteline.demo import build_redline
from siteline.docx_redline import parse_docx
from siteline.evals.dataset import load_dataset
from siteline.extraction import SCHEMA, ExtractionError, _system_prompt, _user_prompt, complete_json, extract_live
from siteline.playbook import playbook_text
from siteline.priority import MAX_SHARE
from siteline.rules import Verdict, decide
from siteline.sandbox import SandboxError, parse_in_daytona
from siteline.verify import verify_quote, verify_value

OUTCOMES = ["accept", "counter", "escalate", "human_review"]
# Both tiers: every row is also decided for a high-priority site at the widest allowed leniency
HIGH_TIER = {"level": "high", "share": MAX_SHARE, "days": 120, "bucket": "eval", "moneyAtRiskPerWeek": 25000}
RESULTS_DIR = DATA_DIR / "evals"
LATEST = RESULTS_DIR / "latest.json"
# Model calls in flight at once (each change makes an extraction and a baseline call)
CONCURRENCY = 16
ANSWERS = RUNTIME_DIR / "eval_answers.json"

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
- counter: counter the change with the pre-approved fallback.
- escalate: the change hits an escalation trigger; the clause owner must approve.
- human_review: the wording is ambiguous, or the change adds a term the playbook does not address; a person must read it.
Also give a verbatim quote from the change that supports your answer, and one sentence of rationale."""


async def baseline(change: dict, context: str) -> dict:
    started = time.perf_counter()
    try:
        data, _ = await complete_json(_baseline_system(), _user_prompt(change, context), BASELINE_SCHEMA, "baseline", 8000)
    except ExtractionError as e:
        return {"error": str(e), "latencyMs": round((time.perf_counter() - started) * 1000)}
    data["latencyMs"] = round((time.perf_counter() - started) * 1000)
    return data


def siteline_verdict(change: dict, ex: dict, context: str, item: dict, lenient: dict | None = None) -> tuple[Verdict, list[bool]]:
    """Siteline's outcome for one labeled change: quote check, rules, then the item's site history
    (when it carries one). Shared by this harness and the Chalk evaluation."""
    quotes = [verify_value(v, change, context) for v in ex.get("values", [])] if not ex.get("error") else []
    verdict = decide(change, ex, all(quotes), lenient)
    if item.get("precedents"):
        values = {v["field"]: v["value"] for v in ex.get("values", [])} if not ex.get("error") else {}
        clause = ex.get("clause_type") or item["clause_type"]
        verdict, _ = precedent.review(verdict, clause, values, item["siteName"], item["agreementId"], item["precedents"],
                                      ex.get("novel_issue"))
    return verdict, quotes


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
        return _rate(sum(1 for r in esc if r[key] in ("accept", "counter")), len(esc))

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
        {"key": "latency", "label": "Latency per change", "description": "Mean model call time per change, as measured when each answer was made",
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


def answer_key(kind: str, row_id: str, system: str, user: str, schema: dict) -> str:
    """Changes whenever anything that shapes this row's model answer changes."""
    raw = json.dumps([kind, row_id, settings.extraction_model, settings.claude_effort, system, user, schema], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def load_answers() -> dict[str, dict]:
    try:
        return json.loads(ANSWERS.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


async def run_eval(limit: int = 0, sandboxes: int = 12, concurrency: int = CONCURRENCY, fresh: bool = False) -> dict:
    if not settings.claude_enabled:
        raise RuntimeError("The eval needs OPENAI_API_KEY in backend/.env")
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
    answers = {} if fresh else load_answers()
    stored: dict[str, dict] = {}
    done = live_calls = 0

    async def answer(key: str, call) -> dict:
        """The stored answer for this exact prompt, or a live call (stored when it succeeds)."""
        nonlocal live_calls
        if key in answers:
            return {**answers[key], "replayed": True}
        async with sem:
            live_calls += 1
            result = await call()
        if not result.get("error"):
            stored[key] = result
        return result

    async def one(it: dict, change: dict) -> dict:
        nonlocal done
        async def extract() -> dict:
            try:
                return await extract_live(change, it["context"])
            except ExtractionError as e:
                return {"error": str(e), "latencyMs": 0}

        user = _user_prompt(change, it["context"])
        ex, b = await asyncio.gather(
            answer(answer_key("extraction", it["id"], _system_prompt(), user, SCHEMA), extract),
            answer(answer_key("baseline", it["id"], _baseline_system(), user, BASELINE_SCHEMA), lambda: baseline(change, it["context"])),
        )
        verdict, quotes = siteline_verdict(change, ex, it["context"], it)
        # The same reading decided for a high-priority site at the widest leniency the config allows
        high, _ = siteline_verdict(change, ex, it["context"], it, HIGH_TIER)
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
            "baseline_replayed": bool(b.get("replayed")),
        }

    rows = await asyncio.gather(*(one(it, ch) for it, ch in zip(items, changes, strict=True)))
    if stored:
        ANSWERS.parent.mkdir(parents=True, exist_ok=True)
        ANSWERS.write_text(json.dumps({**load_answers(), **stored}))
    replayed = sum(1 for r in rows if r["extraction"].get("replayed") and r["baseline_replayed"])
    log(f"{replayed} of {len(rows)} rows replayed stored model answers; {live_calls} live model calls")
    scored = score(rows)
    result = {
        "runId": run_id,
        "harness": "Siteline eval harness",
        "model": settings.claude_model,
        "datasetName": "cta-redlines-labeled-v1",
        "labeledChanges": len(rows),
        "shouldEscalate": scored["shouldEscalate"],
        "parallelSandboxes": used_sandboxes,
        "replayedRows": replayed,
        "liveCalls": live_calls,
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
