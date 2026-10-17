"""Extraction through Claude Code in headless mode (`claude -p`), for running without an OpenAI key.

Same prompts and JSON schema as the API path; Claude Code checks the answer against the schema
(--json-schema) and returns it as `structured_output`. Calls are slow to start and count against
the subscription's usage limits, so only a few run at once and the extraction cache still applies.
Any failure raises ExtractionError, which sends the change to human review.
"""

from __future__ import annotations

import asyncio
import json
import tempfile

from siteline.config import settings
from siteline.extraction import ExtractionError

_gate: asyncio.Semaphore | None = None
_gate_loop: asyncio.AbstractEventLoop | None = None


def gate() -> asyncio.Semaphore:
    """One semaphore per event loop, like extraction.client(): chalk_eval.py runs every call in a fresh loop."""
    global _gate, _gate_loop
    loop = asyncio.get_running_loop()
    if _gate is None or _gate_loop is not loop:
        _gate = asyncio.Semaphore(max(1, settings.claude_cli_concurrency))
        _gate_loop = loop
    return _gate


def command(system: str, schema: dict) -> list[str]:
    return [
        "claude", "-p",
        "--output-format", "json",
        "--model", settings.claude_cli_model,
        "--system-prompt", system,
        "--json-schema", json.dumps(schema),
        "--tools", "",
        "--setting-sources", "",
        "--no-session-persistence",
    ]


async def run(system: str, user: str, schema: dict) -> bytes:
    """Stdout of one `claude -p` call; the prompt goes in on stdin."""
    try:
        # A neutral cwd, so Claude Code doesn't pick up this repo's CLAUDE.md as context
        proc = await asyncio.create_subprocess_exec(
            *command(system, schema),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=tempfile.gettempdir(),
        )
    except FileNotFoundError as e:
        raise ExtractionError("Claude Code (`claude`) is not installed or not on PATH") from e
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(user.encode()), settings.claude_cli_timeout)
    except TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise ExtractionError("Claude Code timed out") from e
    if proc.returncode and not stdout.strip():
        raise ExtractionError(f"Claude Code exited with code {proc.returncode}")
    return stdout


def parse(stdout: bytes) -> tuple[dict, str]:
    """The structured answer and the model name from `--output-format json` output."""
    try:
        out = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ExtractionError("Claude Code returned invalid JSON") from e
    if not isinstance(out, dict):
        raise ExtractionError("Claude Code returned invalid JSON")
    if out.get("is_error") or out.get("subtype") != "success":
        detail = str(out.get("result") or out.get("subtype") or "unknown error")[:200]
        raise ExtractionError(f"Claude Code failed: {detail}")
    data = out.get("structured_output")
    if not isinstance(data, dict):
        raise ExtractionError("Claude Code returned no structured answer")
    model = next(iter(out.get("modelUsage") or {}), None) or f"claude -p ({settings.claude_cli_model})"
    return data, model


async def complete_json(system: str, user: str, schema: dict) -> tuple[dict, str]:
    async with gate():
        return parse(await run(system, user, schema))
