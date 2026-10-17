"""Run the Siteline vs baseline comparison on Chalk Agent Evals (PRD P2).

Two evaluations over the same pinned dataset revision, in one suite:
  - task `siteline_triage`: Claude extraction → quote check → rules engine
  - task `baseline_triage`: Claude picks the outcome directly from the playbook
Scorers: exact match on the outcome, and "safe" (0 when a labeled escalation was
accepted or countered, so 1 - mean(safe) is the unsafe accept rate).

Needs Evaluations enabled on the Chalk environment, `chalk login`, and OPENAI_API_KEY in
your shell (uploaded as a Chalk secret at deploy time). Run from backend/:

    uv run --extra chalk python -m siteline.evals.chalk_eval

Importing this module deploys the functions, so everything with side effects sits under
`if __name__ == "__main__":`.
"""

from __future__ import annotations

import asyncio
import json

import chalkcompute

IMAGE = (
    chalkcompute.Image.debian_slim("3.12")
    .pip_install(["openai>=1.100", "python-dotenv", "httpx", "pydantic"])
    .add_local_python_source("siteline")
    .add_local_dir("data", "/app/data")
    .env({"SITELINE_DATA_DIR": "/app/data", "SITELINE_RUNTIME_DIR": "/tmp/siteline"})
)
SECRETS = [chalkcompute.Secret.from_local_env("OPENAI_API_KEY")]


@chalkcompute.function(image=IMAGE, secrets=SECRETS, concurrency=8, cpu="500m", memory="1Gi")
def siteline_triage(change: str, context: str) -> str:
    from siteline.extraction import ExtractionError, extract_live
    from siteline.rules import decide
    from siteline.verify import verify_quote

    ch = json.loads(change)
    try:
        ex = asyncio.run(extract_live(ch, context))
    except ExtractionError as e:
        ex = {"error": str(e)}
    quotes = [verify_quote(v["quote"], ch, context) for v in ex.get("values", [])]
    return decide(ch, ex, all(quotes)).outcome


@chalkcompute.function(image=IMAGE, secrets=SECRETS, concurrency=8, cpu="500m", memory="1Gi")
def baseline_triage(change: str, context: str) -> str:
    from siteline.evals.harness import baseline

    result = asyncio.run(baseline(json.loads(change), context))
    return result.get("outcome") or "human_review"


outcome_match = chalkcompute.scorers.exact_match(name="outcome-match")
safe = chalkcompute.scorers.sql(
    "safe",
    '''CASE WHEN "expected" = 'escalate' AND "output" IN ('accept', 'fallback') THEN 0.0 ELSE 1.0 END''',
)


def dataset_rows() -> list[dict]:
    from siteline.evals.dataset import load_dataset
    from siteline.evals.harness import parse_shards

    items = load_dataset()
    changes, _ = asyncio.run(parse_shards(items, sandboxes=0, log=print))
    return [
        {"item_id": it["id"], "change": json.dumps(ch, ensure_ascii=False), "context": it["context"], "expected": it["gold"], "note": it["note"]}
        for it, ch in zip(items, changes, strict=True)
    ]


if __name__ == "__main__":
    import pyarrow.compute as pc

    dataset = chalkcompute.DatasetClient().upload("siteline-cta-redlines", dataset_rows())
    suite = next((s for s in chalkcompute.EvaluationSuite.list_all() if s.name == "Siteline safety"), None) or (
        chalkcompute.EvaluationSuite.create("Siteline safety")
    )
    for name, task in (("siteline", siteline_triage), ("llm-only-baseline", baseline_triage)):
        evaluation = chalkcompute.Evaluation.create(
            f"cta-triage-{name}",
            dataset=dataset,
            task=task,
            scorers=[outcome_match, safe],
            metadata={"project": "siteline"},
            suite_id=suite.id,
        )
        run = evaluation.run().wait(timeout=1800.0, raise_on_failure=True)
        table = chalkcompute.DatasetClient().read(run.result_dataset)
        errors = sum(1 for e in table["output_error"].to_pylist() if e)
        print(
            f"{name}: accuracy {pc.mean(table['outcome-match_value']).as_py():.3f}, "
            f"unsafe accept rate (over all rows) {1 - pc.mean(table['safe_value']).as_py():.3f}, task errors {errors}"
        )
