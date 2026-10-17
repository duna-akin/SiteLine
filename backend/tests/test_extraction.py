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
