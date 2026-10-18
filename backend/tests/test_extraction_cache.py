"""Cache regressions with temporary files and no model or network calls."""

import asyncio
import copy
import dataclasses
import json

import pytest

from siteline import extraction


CHANGE = {
    "section": "Payments",
    "kind": "replacement",
    "original": "Company pays each invoice within 45 days.",
    "revised": "Company pays each invoice within 30 days.",
    "segments": [{"type": "del", "text": "45"}, {"type": "ins", "text": "30"}],
}
CONTEXT = "Company is the contractual Sponsor; Institution conducts the trial."


def reading(label):
    return {
        "clause_type": "payment_terms",
        "values": [{"field": "net_days", "value": "30", "quote": "within 30 days"}],
        "novel_issue": None,
        "confidence": 0.95,
        "rationale": label,
        "model": label,
        "latencyMs": 0,
    }


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(extraction, "SEED_CACHE", tmp_path / "seed.json")
    monkeypatch.setattr(extraction, "LIVE_CACHE", tmp_path / "live.json")
    monkeypatch.setattr(
        extraction,
        "settings",
        dataclasses.replace(extraction.settings, openai_api_key="", claude_backend="api"),
    )

    async def no_model(*args, **kwargs):
        pytest.fail("cache tests must never call a model")

    monkeypatch.setattr(extraction, "complete_json", no_model)


def write_seed(entries):
    # Deliberate formatting makes an accidental seed rewrite observable.
    raw = (json.dumps(entries, indent=4) + "\n\n").encode("utf-8")
    extraction.SEED_CACHE.write_bytes(raw)
    return raw


def test_legacy_live_clause_is_not_reused():
    extraction.store_cache({extraction.cache_key(CHANGE): reading("old live prompt")})

    assert extraction.lookup_cache(CHANGE, CONTEXT) is None
    result = asyncio.run(extraction.extract_all([CHANGE], CONTEXT, use_cache=True))[0]
    assert "error" in result


def test_legacy_live_clause_cannot_shadow_a_seed():
    seed = reading("seed fixture")
    raw = write_seed({extraction.cache_key(CHANGE): seed})
    extraction.store_cache({extraction.cache_key(CHANGE): reading("stale live")})

    assert extraction.lookup_cache(CHANGE, CONTEXT) == seed
    result = asyncio.run(extraction.extract_all([CHANGE], CONTEXT, use_cache=True))[0]
    assert result == {**seed, "cached": True}
    assert extraction.SEED_CACHE.read_bytes() == raw


def test_current_live_clause_wins_over_legacy_seed_and_live():
    write_seed({extraction.cache_key(CHANGE): reading("seed fixture")})
    current = reading("current prompt")
    extraction.store_cache({
        extraction.cache_key(CHANGE): reading("stale live"),
        extraction._live_cache_key(CHANGE, CONTEXT): current,
    })

    assert extraction.lookup_cache(CHANGE, CONTEXT) == current
    result = asyncio.run(extraction.extract_all([CHANGE], CONTEXT, use_cache=True))[0]
    assert result == {**current, "cached": True}


@pytest.mark.parametrize("current_live", [False, True], ids=["legacy-seed", "seed-and-current-live"])
def test_bypass_runs_live_and_preserves_seed_bytes(monkeypatch, current_live):
    legacy_key = extraction.cache_key(CHANGE)
    live_key = extraction._live_cache_key(CHANGE, CONTEXT)
    seed = reading("seed fixture")
    raw = write_seed({legacy_key: seed})
    entries = {legacy_key: reading("stale live")}
    if current_live:
        entries[live_key] = reading("previous current live")
    extraction.store_cache(entries)
    monkeypatch.setattr(
        extraction,
        "settings",
        dataclasses.replace(extraction.settings, openai_api_key="test"),
    )
    calls = []
    fresh = reading("fresh live")

    async def extract_live(change, context):
        calls.append((change, context))
        return fresh

    monkeypatch.setattr(extraction, "extract_live", extract_live)
    result = asyncio.run(extraction.extract_all([CHANGE], CONTEXT, use_cache=False))[0]

    assert calls == [(CHANGE, CONTEXT)]
    assert result == {**fresh, "cached": False}
    assert extraction.SEED_CACHE.read_bytes() == raw
    saved = json.loads(extraction.LIVE_CACHE.read_text())
    assert saved[live_key] == fresh
    assert saved[legacy_key] == entries[legacy_key]
    assert json.loads(extraction.SEED_CACHE.read_text()) == {legacy_key: seed}


def test_cached_clause_is_not_reused_for_different_party_context():
    original = extraction._live_cache_key(CHANGE, CONTEXT)
    extraction.store_cache({original: reading("company is sponsor")})
    investigator_context = "Institution is Sponsor-Investigator; Company only supplies funding."

    assert extraction._live_cache_key(CHANGE, investigator_context) != original
    assert extraction.lookup_cache(CHANGE, investigator_context) is None


@pytest.mark.parametrize("part", ["semantic_hints", "category_aliases", "guardrails"])
def test_terminology_changes_invalidate_live_clauses(monkeypatch, part):
    original = extraction._live_cache_key(CHANGE, CONTEXT)
    extraction.store_cache({original: reading("previous terminology")})
    terminology = copy.deepcopy(extraction.TERMINOLOGY)
    if part == "semantic_hints":
        terminology["fields"]["net_days"][part].append("invoice settlement interval")
    elif part == "category_aliases":
        terminology[part]["payment_terms"].append("Invoice Settlement")
    else:
        terminology[part].append("An invoice dispute is distinct from its payment deadline.")
    monkeypatch.setattr(extraction, "TERMINOLOGY", terminology)

    assert extraction._live_cache_key(CHANGE, CONTEXT) != original
    assert extraction.lookup_cache(CHANGE, CONTEXT) is None


def test_actual_system_prompt_changes_invalidate_live_clauses(monkeypatch):
    original = extraction._live_cache_key(CHANGE, CONTEXT)
    extraction.store_cache({original: reading("previous prompt")})
    system = extraction._system_prompt()
    monkeypatch.setattr(extraction, "_system_prompt", lambda: system + "\nClarified extraction instructions.")

    assert extraction._live_cache_key(CHANGE, CONTEXT) != original
    assert extraction.lookup_cache(CHANGE, CONTEXT) is None


def test_playbook_text_changes_invalidate_live_clauses(monkeypatch):
    original = extraction._live_cache_key(CHANGE, CONTEXT)
    extraction.store_cache({original: reading("previous playbook")})
    playbook = extraction.playbook_text()
    monkeypatch.setattr(extraction, "playbook_text", lambda: playbook + "\nUpdated payment context.")

    assert extraction._live_cache_key(CHANGE, CONTEXT) != original
    assert extraction.lookup_cache(CHANGE, CONTEXT) is None


@pytest.mark.parametrize("part", ["kind", "segments"], ids=["change-kind", "tracked-edits"])
def test_change_details_omitted_from_legacy_key_invalidate_live_clauses(part):
    original = extraction._live_cache_key(CHANGE, CONTEXT)
    extraction.store_cache({original: reading("previous tracked edit")})
    changed = copy.deepcopy(CHANGE)
    if part == "kind":
        changed[part] = "comment"
    else:
        changed[part][1]["author"] = "Sponsor counsel"

    assert extraction.cache_key(changed) == extraction.cache_key(CHANGE)
    assert extraction._live_cache_key(changed, CONTEXT) != original
    assert extraction.lookup_cache(changed, CONTEXT) is None


@pytest.mark.parametrize("live_override", [False, True], ids=["seed-figures", "live-figures"])
def test_document_figure_cache_keeps_legacy_key_and_precedence(monkeypatch, live_override):
    # Pin the pre-existing content-only document key independently of clause prompts.
    text = "abc"
    key = "doc-ba7816bf8f01cfea414140de"
    seed = {"figures": [], "confidence": 0.9, "rationale": "seed figures"}
    raw = write_seed({key: seed})
    expected = seed
    if live_override:
        expected = {**seed, "rationale": "live figures"}
        extraction.store_cache({key: expected})
    monkeypatch.setattr(extraction, "_system_prompt", lambda: "A changed clause prompt.")

    assert extraction.doc_cache_key(text) == key
    result = asyncio.run(extraction.extract_document(text, use_cache=True))
    assert result == {**expected, "cached": True}
    assert extraction.SEED_CACHE.read_bytes() == raw
