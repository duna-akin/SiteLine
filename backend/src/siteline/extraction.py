"""Clause extraction with OpenAI: clause type, typed values, one verbatim quote per value.

The model only reads and labels. It never decides the outcome; the rules engine does that
from the extracted values (see rules.py). Results are cached per change text so the demo
file can run without a network call ("Cached extraction" flag).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

import openai

from siteline.config import DATA_DIR, RUNTIME_DIR, settings
from siteline.playbook import CLAUSE_TYPES, playbook_text
from siteline.priority import FIGURES

# field name -> (clause type, value format the model must use)
FIELDS: dict[str, tuple[str, str]] = {
    "net_days": ("payment_terms", "integer days to pay an invoice, e.g. 30"),
    "start_up_fee_pct": ("payment_terms", "start-up fee as a percent of the study budget, number only, e.g. 15"),
    "start_up_fee_refundable": ("payment_terms", "true or false"),
    "survival_years": ("confidentiality", "years confidentiality survives after study close, number"),
    "trade_secrets_perpetual": ("confidentiality", "true or false: trade secrets stay protected with no end date"),
    "carve_out_standard": ("indemnification", "negligence | gross_negligence_or_willful_misconduct | none"),
    "adjudication_required": ("indemnification", "true or false: carve-out applies only once finally adjudicated"),
    "mutual_indemnity": ("indemnification", "true or false: site's indemnity becomes mutual / sponsor must be indemnified in turn"),
    "covers_lost_wages": ("subject_injury", "true or false"),
    "covers_pain_and_suffering": ("subject_injury", "true or false"),
    "covers_travel": ("subject_injury", "true or false"),
    "reimbursement_cap": ("subject_injury", "capped | uncapped"),
    "coordination_with_insurance": ("subject_injury", "net_of_insurance | sponsor_pays_first"),
    "review_days": ("publication", "integer days the sponsor has to review a publication"),
    "review_window_open_ended": ("publication", "true or false: a qualifier like 'or as otherwise agreed' makes the window open-ended"),
    "patent_delay": ("publication", "retained | removed"),
    "patent_delay_days": ("publication", "integer days of extra delay for patent filings"),
    "invention_ownership": ("intellectual_property", "sponsor | joint | institution"),
    "site_research_license": ("intellectual_property", "true or false: site keeps a non-exclusive research license"),
    "background_ip_retained": ("intellectual_property", "true or false: each party keeps its background IP"),
    "requires_baa": ("data_privacy", "true or false: sponsor must sign a business associate agreement"),
    "blocks_secondary_research": ("data_privacy", "true or false: sponsor may not use data for secondary research"),
    "data_use_addendum": ("data_privacy", "true or false: sponsor signs a limited data-use addendum"),
    "ml_training_restriction": ("data_privacy", "true or false: limits on using study data to train AI/ML models"),
    "site_notice_days": ("termination", "integer days' notice the institution must give to terminate"),
    "sponsor_notice_days": ("termination", "integer days' notice the sponsor must give to terminate"),
    "termination_for_convenience": ("termination", "true or false: site may terminate for convenience"),
    "pays_noncancellable_costs": ("termination", "true or false: sponsor still pays non-cancellable costs on termination"),
    "governing_law_state": ("governing_law", "the state or country whose law governs, e.g. Wisconsin"),
    "venue": ("governing_law", "sponsor_courts | silent | site_courts_exclusive | site_courts_nonexclusive | other"),
    "arbitration_abroad": ("governing_law", "true or false: mandatory arbitration outside the US"),
    "sovereign_immunity_waiver_required": ("governing_law", "true or false: sponsor must waive or accept the site's sovereign immunity terms"),
    "institution_is_public": ("governing_law", "true or false: the institution is a public (state) institution"),
    "no_substantive_change": ("any", "true when the edit only fixes typos, formatting or numbering and does not change any right or obligation"),
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "clause_type": {"type": "string", "enum": CLAUSE_TYPES},
        "values": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(FIELDS)},
                    "value": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["field", "value", "quote"],
                "additionalProperties": False,
            },
        },
        "novel_issue": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": ["clause_type", "values", "novel_issue", "confidence", "rationale"],
    "additionalProperties": False,
}


def _system_prompt() -> str:
    fields = "\n".join(f"- {name} ({ct}): {fmt}" for name, (ct, fmt) in FIELDS.items())
    return f"""You read one tracked change from a site's redline of a clinical trial agreement and record what it says, as structured data. A rules engine decides the outcome from your values, so report facts, not judgments.

The sponsor's playbook (for context on which facts matter):
{playbook_text()}

Fields you may report (value formats):
{fields}

How to answer:
- clause_type: the playbook clause type the change belongs to.
- values: the fields this change sets or alters, as they stand after the site's edit. Include a field only when the text supports it. When the site deletes a provision, report the resulting state (for example patent_delay = removed, coordination_with_insurance = sponsor_pays_first). For a comment on unchanged text, report the facts of that text.
- quote: copy the exact words from the change text that support the value, character for character, including punctuation and curly quotes. Quote from the revised text for added or kept language and from the original text for deleted language. Keep each quote short (a clause, not a paragraph). Never paraphrase, join separate passages, or fill gaps.
- novel_issue: if the change adds an obligation, restriction or right that no playbook clause addresses (for example, limits on training AI models), describe it in one sentence. Otherwise null.
- confidence: 0 to 1. Use below 0.8 when the wording is ambiguous, open-ended (for example "or as otherwise agreed"), internally inconsistent, or you are unsure which field applies.
- rationale: one sentence."""


def _user_prompt(change: dict, context: str) -> str:
    spans = []
    for seg in change.get("segments", []):
        if seg["type"] == "ins":
            spans.append(f"INSERTED by {seg.get('author', 'site')}: {seg['text']}")
        elif seg["type"] == "del":
            spans.append(f"DELETED by {seg.get('author', 'site')}: {seg['text']}")
    parts = [
        f"Agreement context:\n{context}" if context else "",
        f"Section: {change.get('section') or 'unknown'}",
        f"Change type: {change['kind']}",
        f"Original text:\n{change.get('original') or '(none: new text)'}",
        f"Revised text:\n{change.get('revised') or '(deleted)'}",
        "Tracked edits:\n" + ("\n".join(spans) if spans else "(none)"),
        f"Site comment: {change['siteComment']}" if change.get("siteComment") else "",
    ]
    return "\n\n".join(p for p in parts if p)


def cache_key(change: dict) -> str:
    raw = json.dumps(
        [change.get("section"), change.get("original"), change.get("revised"), change.get("siteComment")],
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


SEED_CACHE = DATA_DIR / "extraction_cache.json"
LIVE_CACHE = RUNTIME_DIR / "extraction_cache.json"


def _load_cache() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in (SEED_CACHE, LIVE_CACHE):
        if path.exists():
            out.update(json.loads(path.read_text()))
    return out


def lookup_cache(change: dict) -> dict | None:
    return _load_cache().get(cache_key(change))


def store_cache(entries: dict[str, dict], seed: bool = False) -> None:
    path = SEED_CACHE if seed else LIVE_CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update(entries)
    path.write_text(json.dumps(current, indent=1, ensure_ascii=False))


class ExtractionError(Exception):
    pass


_client: openai.AsyncOpenAI | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def client() -> openai.AsyncOpenAI:
    """One client per event loop: its connection pool belongs to the loop that made it, and
    chalk_eval.py runs every call in a fresh asyncio.run loop."""
    global _client, _client_loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _client is None or _client_loop is not loop:
        _client = openai.AsyncOpenAI(max_retries=2, timeout=settings.openai_timeout)
        _client_loop = loop
    return _client


async def complete_json(system: str, user: str, schema: dict, name: str, max_tokens: int,
                        model: str | None = None, effort: str | None = None) -> tuple[dict, str]:
    """One structured-output chat completion, checked. Returns the parsed answer and the model name;
    any failure, from the API or in the answer, raises ExtractionError with the reason.
    `model` and `effort` default to the configured extraction model and effort."""
    effort = effort or settings.claude_effort
    reasoning = {} if effort.lower() == "off" else {"reasoning_effort": effort}
    try:
        response = await client().chat.completions.create(
            model=model or settings.claude_model,
            max_completion_tokens=max_tokens,
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **reasoning,
        )
    except openai.AuthenticationError as e:
        raise ExtractionError("OpenAI rejected the API key") from e
    except openai.RateLimitError as e:
        raise ExtractionError("OpenAI rate limit reached") from e
    except openai.APIStatusError as e:
        raise ExtractionError(f"OpenAI API error {e.status_code}: {e.message}") from e
    except openai.APITimeoutError as e:  # a subclass of APIConnectionError, so it comes first
        raise ExtractionError("OpenAI request timed out") from e
    except openai.APIConnectionError as e:
        raise ExtractionError("Could not reach the OpenAI API") from e

    choice = response.choices[0]
    if choice.message.refusal:
        raise ExtractionError("The model declined to answer")
    if choice.finish_reason == "length":
        raise ExtractionError("The model's answer was cut off")
    if choice.finish_reason == "content_filter":
        raise ExtractionError("OpenAI's content filter blocked the answer")
    if choice.finish_reason != "stop":
        raise ExtractionError(f"The model stopped early ({choice.finish_reason})")
    if not choice.message.content:
        raise ExtractionError("The model returned an empty answer")
    try:
        data = json.loads(choice.message.content)
    except json.JSONDecodeError as e:
        raise ExtractionError("The model returned invalid JSON") from e
    if not isinstance(data, dict):
        raise ExtractionError("The model returned invalid JSON")
    return data, response.model


async def extract_live(change: dict, context: str = "", model: str | None = None, effort: str | None = None) -> dict:
    started = time.perf_counter()
    data, model = await complete_json(_system_prompt(), _user_prompt(change, context), SCHEMA, "extraction", 16000, model, effort)
    data["model"] = model
    data["latencyMs"] = round((time.perf_counter() - started) * 1000)
    return data


async def extract_all(changes: list[dict], context: str, use_cache: bool) -> list[dict]:
    """One extraction per change, in parallel. Failures come back as {"error": ...}."""

    async def one(change: dict) -> dict:
        if use_cache:
            hit = lookup_cache(change)
            if hit:
                return {**hit, "cached": True}
        if not settings.claude_enabled:
            return {"error": "No OPENAI_API_KEY and no cached extraction for this change"}
        try:
            result = await extract_live(change, context)
        except ExtractionError as e:
            return {"error": str(e)}
        store_cache({cache_key(change): result})
        return {**result, "cached": False}

    return await asyncio.gather(*(one(c) for c in changes))


# ---- whole-agreement figures for site priority (priority.py does the arithmetic) -------

DOC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(FIGURES)},
                    "value": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["field", "value", "quote"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": ["figures", "confidence", "rationale"],
    "additionalProperties": False,
}

DOC_SYSTEM = (
    "You read a clinical trial agreement as it stands after the site's edits and record three figures about "
    "this institution, as structured data. Code computes the site's priority from your values, so report facts "
    "the text states, never estimates.\n\nFields (value formats):\n"
    + "\n".join(f"- {name}: {fmt}" for name, fmt in FIGURES.items())
    + "\n\nHow to answer:\n"
    "- figures: include a field only when the agreement states it. Never compute, convert or infer a missing figure.\n"
    "- quote: copy the exact words that state the value, character for character. Keep it short.\n"
    "- confidence: 0 to 1. Use below 0.8 when a figure is ambiguous or stated more than once with different values.\n"
    "- rationale: one sentence."
)


def doc_cache_key(text: str) -> str:
    return "doc-" + hashlib.sha256(text.encode()).hexdigest()[:24]


async def extract_document(text: str, use_cache: bool) -> dict:
    """Enrollment target, enrollment period and per-patient amount, each with a quote.
    Failures come back as {"error": ...}, which priority.assess treats as unknown."""
    key = doc_cache_key(text)
    if use_cache and (hit := _load_cache().get(key)):
        return {**hit, "cached": True}
    if not settings.claude_enabled:
        return {"error": "No OPENAI_API_KEY and no cached reading of this agreement's figures"}
    started = time.perf_counter()
    try:
        data, model = await complete_json(DOC_SYSTEM, f"Agreement text:\n\n{text[:60000]}", DOC_SCHEMA, "figures", 8000)
    except Exception as e:  # noqa: BLE001 - a failed reading means unknown priority, never a failed upload
        return {"error": f"Could not read the agreement's figures: {e}"}
    data["model"] = model
    data["latencyMs"] = round((time.perf_counter() - started) * 1000)
    store_cache({key: data})
    return {**data, "cached": False}
