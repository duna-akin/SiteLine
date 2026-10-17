import asyncio
import dataclasses
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from siteline import extraction
from siteline.evals import harness


def _response(content, finish="stop", refusal=None):
    msg = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)], model="gpt-test")


class FakeClient:
    """Stands in for AsyncOpenAI: records each request and answers with `result` (or raises it)."""

    def __init__(self, result):
        self.result, self.calls = result, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(extraction, "settings", dataclasses.replace(extraction.settings, openai_api_key="test"))
    monkeypatch.setattr(extraction, "LIVE_CACHE", tmp_path / "extraction_cache.json")

    def use(result):
        client = FakeClient(result)
        monkeypatch.setattr(extraction, "client", lambda: client)
        return client

    return use


def test_extract_document_uses_the_openai_client(fake):
    figures = {"figures": [{"field": "enrollment_target", "value": "40", "quote": "forty (40) subjects"}], "confidence": 0.9, "rationale": "r"}
    client = fake(_response(json.dumps(figures)))
    out = asyncio.run(extraction.extract_document("Agreement text", use_cache=False))
    assert out["figures"] == figures["figures"] and out["model"] == "gpt-test" and not out["cached"]
    assert client.calls[0]["response_format"]["json_schema"]["schema"] is extraction.DOC_SCHEMA


def test_extract_document_returns_an_error_instead_of_raising(fake):
    for result in (RuntimeError("boom"), _response(None, finish="content_filter"), _response("not json")):
        fake(result)
        out = asyncio.run(extraction.extract_document(f"Agreement {result!r}", use_cache=False))
        assert out["error"].startswith("Could not read the agreement's figures")


@pytest.mark.parametrize(("response", "reason"), [
    (_response(None, finish="content_filter"), "content filter"),
    (_response(None), "empty answer"),
    (_response('{"a": 1', finish="length"), "cut off"),
    (_response(None, refusal="no"), "declined"),
    (_response("[1, 2]"), "invalid JSON"),
])
def test_complete_json_names_the_real_reason(fake, response, reason):
    fake(response)
    with pytest.raises(extraction.ExtractionError, match=reason):
        asyncio.run(extraction.complete_json("s", "u", {}, "n", 10))


def test_timeouts_are_not_reported_as_unreachable(fake):
    fake(openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")))
    with pytest.raises(extraction.ExtractionError, match="timed out"):
        asyncio.run(extraction.complete_json("s", "u", {}, "n", 10))


def test_baseline_turns_an_empty_answer_into_a_row_error(fake):
    fake(_response(None, finish="content_filter"))
    change = {"kind": "insertion", "section": "§1", "original": "", "revised": "x", "segments": []}
    out = asyncio.run(harness.baseline(change, ""))
    assert "content filter" in out["error"]


def test_reasoning_effort_can_be_left_out(fake, monkeypatch):
    client = fake(_response("{}"))
    asyncio.run(extraction.complete_json("s", "u", {}, "n", 10))
    assert client.calls[0]["reasoning_effort"] == extraction.settings.claude_effort
    monkeypatch.setattr(extraction, "settings", dataclasses.replace(extraction.settings, claude_effort="off"))
    asyncio.run(extraction.complete_json("s", "u", {}, "n", 10))
    assert "reasoning_effort" not in client.calls[1]


def test_client_is_rebuilt_for_each_event_loop(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(extraction, "_client", None)

    async def two():
        return extraction.client(), extraction.client()

    a1, a2 = asyncio.run(two())
    b1, _ = asyncio.run(two())
    assert a1 is a2 and b1 is not a1


# ---- claude -p backend (SITELINE_CLAUDE_BACKEND=cli, no OPENAI_API_KEY) ---------------

CHANGE = {"kind": "replacement", "original": "Net forty-five (45) days", "revised": "Net ten (10) days", "segments": []}


def _cli_output(structured=None, **overrides):
    out = {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(structured),
           "structured_output": structured, "modelUsage": {"claude-test": {}}}
    return json.dumps({**out, **overrides}).encode()


@pytest.fixture
def cli(monkeypatch, tmp_path):
    """Extraction with SITELINE_CLAUDE_BACKEND=cli and no OpenAI key; `claude -p` answers with `stdout`."""
    from siteline import claude_cli

    cli_settings = dataclasses.replace(extraction.settings, openai_api_key="", claude_backend="cli")
    monkeypatch.setattr(extraction, "settings", cli_settings)
    monkeypatch.setattr(claude_cli, "settings", cli_settings)
    monkeypatch.setattr(extraction, "LIVE_CACHE", tmp_path / "extraction_cache.json")
    monkeypatch.setattr(extraction, "client", lambda: pytest.fail("the cli backend must not call OpenAI"))

    def use(stdout):
        calls = []

        async def run(system, user, schema):
            calls.append({"system": system, "user": user, "schema": schema})
            return stdout

        monkeypatch.setattr(claude_cli, "run", run)
        return calls

    return use


def test_cli_backend_runs_only_without_an_openai_key():
    base = extraction.settings
    assert dataclasses.replace(base, openai_api_key="", claude_backend="cli").claude_enabled
    assert not dataclasses.replace(base, openai_api_key="sk", claude_backend="cli").claude_cli
    assert not dataclasses.replace(base, openai_api_key="", claude_backend="api").claude_enabled


def test_cli_command_asks_for_the_schema_without_tools():
    from siteline import claude_cli

    cmd = claude_cli.command("system text", extraction.SCHEMA)
    assert cmd[:2] == ["claude", "-p"]
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == extraction.SCHEMA
    assert cmd[cmd.index("--tools") + 1] == "" and cmd[cmd.index("--system-prompt") + 1] == "system text"


def test_cli_extraction_has_the_api_output_shape(cli):
    answer = {"clause_type": "payment_terms", "values": [{"field": "net_days", "value": "10", "quote": "ten (10)"}],
              "novel_issue": None, "confidence": 0.95, "rationale": "r"}
    calls = cli(_cli_output(answer))
    out = asyncio.run(extraction.extract_all([CHANGE], "", use_cache=False))[0]
    assert {k: out[k] for k in answer} == answer and out["model"] == "claude-test" and not out["cached"]
    assert calls[0]["schema"] is extraction.SCHEMA and "Net ten (10) days" in calls[0]["user"]


@pytest.mark.parametrize("stdout", [
    b"not json",
    b"[]",
    _cli_output(None),
    _cli_output({"clause_type": "x"}, is_error=True, subtype="error_during_execution", result="usage limit reached"),
    _cli_output({"clause_type": "x"}, subtype="error_max_structured_output_retries"),
])
def test_malformed_cli_answer_goes_to_human_review(cli, stdout):
    from siteline.rules import decide

    cli(stdout)
    out = asyncio.run(extraction.extract_all([CHANGE], "", use_cache=False))[0]
    assert out["error"].startswith("Claude Code")
    verdict = decide(CHANGE, out, True)
    assert (verdict.outcome, verdict.rule_id) == ("human_review", "SYS-ERROR")


def test_cli_triage_end_to_end_sends_bad_answers_to_human_review(cli, monkeypatch, tmp_path):
    from siteline import approvals, store
    from siteline.demo import demo_bytes
    from siteline.pipeline import TriageOptions, triage

    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()
    calls = cli(b'{"truncated": ')

    async def go():
        summary = await triage(demo_bytes(), "NSO-417_CTA_Site07_redline.docx", TriageOptions(local_parser=True, use_cache=False))
        approvals.cancel_all()
        return summary

    decisions = store.get_decisions(asyncio.run(go())["id"])
    assert calls and decisions
    assert all(d["outcome"] == "human_review" and d["ruleId"] == "SYS-ERROR" for d in decisions)
