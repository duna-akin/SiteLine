"""Siteline backend: triage a site's CTA redline against the sponsor playbook."""

from __future__ import annotations

import argparse
import asyncio
import json


def main() -> None:
    parser = argparse.ArgumentParser(prog="siteline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="Run the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    sub.add_parser("make-demo", help="Write the Site 07 demo redline, the clean form agreement and the seed extraction cache")
    sub.add_parser("cache-demo", help="Extract the demo file with OpenAI and save it as the seed cache")
    sub.add_parser("make-samples", help="Write the nine per-clause sample redlines and their seed extractions")
    parse = sub.add_parser("parse", help="Print the tracked changes in a .docx as JSON")
    parse.add_argument("file")
    sub.add_parser("reset", help="Clear agreements, decisions and approvals back to the seeded inbound emails")
    ev = sub.add_parser("eval", help="Run Siteline vs the LLM-only baseline on the labeled set")
    ev.add_argument("--limit", type=int, default=0, help="Only the first N labeled changes")
    ev.add_argument("--sandboxes", type=int, default=12, help="Parallel Daytona sandboxes for parsing (0 = local)")
    ev.add_argument("--concurrency", type=int, default=32, help="Model calls in flight at once")
    ev.add_argument("--fresh", action="store_true", help="Ask the model again instead of replaying stored answers")
    sub.add_parser("make-dataset", help="Write the labeled eval set (data/evals/labeled_changes.jsonl)")
    args = parser.parse_args()

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run(
            "siteline.api:app", host=args.host, port=args.port, reload=args.reload,
            timeout_graceful_shutdown=3,  # the browser's /api/events stream never closes on its own
        )
    elif args.cmd == "make-demo":
        from siteline.demo import write_demo, write_template
        from siteline.demo_cache import write_seed

        print(write_demo())
        print(write_template())
        print(f"seed cache: {write_seed()} entries")
    elif args.cmd == "make-samples":
        from siteline.samples import write_samples

        print("\n".join(write_samples()))
    elif args.cmd == "cache-demo":
        from siteline.demo import demo_bytes
        from siteline.docx_redline import parse_docx
        from siteline.extraction import cache_key, extract_live, store_cache
        from siteline.pipeline import preamble

        async def run() -> None:
            parsed = parse_docx(demo_bytes())
            results = await asyncio.gather(*(extract_live(c, preamble(parsed)) for c in parsed["changes"]))
            store_cache({cache_key(c): r for c, r in zip(parsed["changes"], results, strict=True)}, seed=True)
            print(f"cached {len(results)} live extractions as the demo seed")

        asyncio.run(run())
    elif args.cmd == "parse":
        from siteline.docx_redline import parse_docx

        print(json.dumps(parse_docx(args.file), indent=1, ensure_ascii=False))
    elif args.cmd == "reset":
        from siteline import store

        store.reset()
        print("state reset to the seeded inbound emails")
    elif args.cmd == "make-dataset":
        from siteline.evals.dataset import write_dataset

        print(write_dataset())
    elif args.cmd == "eval":
        from siteline.evals.harness import run_eval

        result = asyncio.run(run_eval(limit=args.limit, sandboxes=args.sandboxes, concurrency=args.concurrency, fresh=args.fresh))
        print(json.dumps({m["key"]: (m["siteline"], m["baseline"]) for m in result["metrics"]}, indent=1))
