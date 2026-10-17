"""Run the Siteline vs baseline comparison on Chalk Agent Evals (PRD P2).

Two evaluations over the same pinned dataset revision, in one suite:
  - task `siteline_triage`: OpenAI extraction → quote check → rules engine → precedent
  - task `baseline_triage`: the same model picks the outcome directly from the playbook
Scorers: exact match on the outcome, and "safe" (0 when a labeled escalation was
accepted or countered, and 0 for a row with no output, so a failed task never looks safe;
1 - mean(safe) is the unsafe accept rate).

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
    # psycopg: the precedent and store modules the tasks import load it at import time
    .pip_install(["openai>=1.100", "python-dotenv", "httpx", "pydantic", "psycopg[binary]>=3.3"])
    .add_local_python_source("siteline")
    .add_local_dir("data", "/app/data")
    .env({"SITELINE_DATA_DIR": "/app/data", "SITELINE_RUNTIME_DIR": "/tmp/siteline"})
)
SECRETS = [chalkcompute.Secret.from_local_env("OPENAI_API_KEY")]


@chalkcompute.function(image=IMAGE, secrets=SECRETS, concurrency=8, cpu="500m", memory="1Gi")
def siteline_triage(change: str, context: str, item: str) -> str:
    from siteline.evals.harness import siteline_verdict
    from siteline.extraction import ExtractionError, extract_live

    ch = json.loads(change)
    try:
        ex = asyncio.run(extract_live(ch, context))
    except ExtractionError as e:
        ex = {"error": str(e)}
    return siteline_verdict(ch, ex, context, json.loads(item))[0].outcome


@chalkcompute.function(image=IMAGE, secrets=SECRETS, concurrency=8, cpu="500m", memory="1Gi")
def baseline_triage(change: str, context: str) -> str:
    from siteline.evals.harness import baseline

    result = asyncio.run(baseline(json.loads(change), context))
    return result.get("outcome") or "human_review"


outcome_match = chalkcompute.scorers.exact_match(name="outcome-match")
safe = chalkcompute.scorers.sql(
    "safe",
    '''CASE WHEN "output" IS NULL OR "output" = '' THEN 0.0
          WHEN "expected" = 'escalate' AND "output" IN ('accept', 'fallback') THEN 0.0 ELSE 1.0 END''',
)


def item_column(it: dict) -> str:
    """What siteline_triage needs from a labeled item beyond the change: its site history."""
    return json.dumps({k: it.get(k) for k in ("clause_type", "siteName", "agreementId", "precedents")}, ensure_ascii=False)


def dataset_rows() -> list[dict]:
    from siteline.evals.dataset import load_dataset
    from siteline.evals.harness import parse_shards

    items = load_dataset()
    changes, _ = asyncio.run(parse_shards(items, sandboxes=0, log=print))
    return [
        {"item_id": it["id"], "change": json.dumps(ch, ensure_ascii=False), "context": it["context"], "item": item_column(it),
         "expected": it["gold"], "note": it["note"]}
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
