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
from pathlib import Path
from typing import Any

import openai

from siteline.config import DATA_DIR, RUNTIME_DIR, settings
from siteline.playbook import CLAUSE_TYPES, playbook_text
from siteline.priority import FIGURES

# Preserve the supplied taxonomy in full. Its standalone extraction_prompt uses a
# different output shape; _system_prompt adapts the semantics to our existing schema.
TERMINOLOGY = json.loads(Path(__file__).with_name("cta_terminology.json").read_text(encoding="utf-8"))

# field name -> (clause type, value format the model must use)
FIELDS: dict[str, tuple[str, str]] = {
    "net_days": ("payment_terms", "integer days to pay an invoice, e.g. 30"),
    "start_up_fee_pct": ("payment_terms", "start-up fee as a percent of the study budget, number only, e.g. 15"),
    "start_up_fee_refundable": ("payment_terms", "true or false"),
    "overhead_pct": ("payment_terms", "indirect cost (overhead) rate as a percent of direct costs, number only, e.g. 28"),
    "holdback_pct": ("payment_terms", "percent of each payment withheld until database lock, number; 0 when the holdback is deleted"),
    "screen_failures_per_enrolled": ("payment_terms", "screen failures paid per enrolled subject as a decimal, e.g. 0.33 for one per three enrolled, or uncapped"),
    "survival_years": ("confidentiality", "years confidentiality survives after study close, number"),
    "trade_secrets_perpetual": ("confidentiality", "true or false: trade secrets stay protected with no end date"),
    "discloses_to_affiliates": ("confidentiality", "true or false: the site may share Confidential Information with affiliates or outside collaborators"),
    "marking_required": ("confidentiality", "true or false: only information marked confidential is protected"),
    "public_records_disclosure": ("confidentiality", "true or false: the site may disclose the agreement or information under a public-records law"),
    "public_records_notice": ("confidentiality", "true or false: the site notifies Sponsor before a public-records disclosure"),
    "carve_out_standard": ("indemnification", "negligence | gross_negligence_or_willful_misconduct | none"),
    "adjudication_required": ("indemnification", "true or false: carve-out applies only once finally adjudicated"),
    "mutual_indemnity": ("indemnification", "true or false: site's indemnity becomes mutual / sponsor must be indemnified in turn"),
    "claim_notice_days": ("indemnification", "integer days the site has to notify Sponsor of a claim"),
    "sponsor_controls_defense": ("indemnification", "true or false: Sponsor controls the defense and settlement of indemnified claims"),
    "additional_insured": ("indemnification", "true or false: Sponsor names the site as an additional insured on its policy"),
    "covers_lost_wages": ("subject_injury", "true or false"),
    "covers_pain_and_suffering": ("subject_injury", "true or false"),
    "covers_travel": ("subject_injury", "true or false"),
    "reimbursement_cap": ("subject_injury", "capped | uncapped"),
    "coordination_with_insurance": ("subject_injury", "net_of_insurance | sponsor_pays_first"),
    "removes_injury_exclusions": ("subject_injury", "true or false: the exclusions (underlying disease, standard of care, protocol deviations) are deleted"),
    "review_days": ("publication", "integer days the sponsor has to review a publication"),
    "review_window_open_ended": ("publication", "true or false: a qualifier like 'or as otherwise agreed' makes the window open-ended"),
    "patent_delay": ("publication", "retained | removed"),
    "patent_delay_days": ("publication", "integer days of extra delay for patent filings"),
    "multisite_wait_months": ("publication", "integer months the site waits for the multi-site publication before publishing on its own"),
    "invention_ownership": ("intellectual_property", "sponsor | joint | institution"),
    "site_research_license": ("intellectual_property", "true or false: site keeps a non-exclusive research license"),
    "background_ip_retained": ("intellectual_property", "true or false: each party keeps its background IP"),
    "site_may_file_patents": ("intellectual_property", "true or false: the site may file patents on study inventions in its own name"),
    "requires_baa": ("data_privacy", "true or false: sponsor must sign a business associate agreement"),
    "blocks_secondary_research": ("data_privacy", "true or false: sponsor may not use data for secondary research"),
    "data_use_addendum": ("data_privacy", "true or false: sponsor signs a limited data-use addendum"),
    "ml_training_restriction": ("data_privacy", "true or false: limits on using study data to train AI/ML models"),
    "incident_notice_days": ("data_privacy", "integer business days Sponsor has to notify the site of a security incident"),
    "restricts_data_transfer": ("data_privacy", "true or false: Study data must stay in one state or country"),
    "site_notice_days": ("termination", "integer days' notice the institution must give to terminate"),
    "sponsor_notice_days": ("termination", "integer days' notice the sponsor must give to terminate"),
    "termination_for_convenience": ("termination", "true or false: site may terminate for convenience"),
    "pays_noncancellable_costs": ("termination", "true or false: sponsor still pays non-cancellable costs on termination"),
    "governing_law_state": ("governing_law", "the state or country whose law governs, e.g. Wisconsin"),
    "venue": ("governing_law", "sponsor_courts | silent | site_courts_exclusive | site_courts_nonexclusive | other"),
    "arbitration_abroad": ("governing_law", "true or false: mandatory arbitration outside the US"),
    "arbitration_domestic": ("governing_law", "true or false: disputes go to arbitration in the United States instead of court"),
    "sovereign_immunity_waiver_required": ("governing_law", "true or false: sponsor must waive or accept the site's sovereign immunity terms"),
    "institution_is_public": ("governing_law", "true or false: the institution is a public (state) institution (may be quoted from the agreement context; also used for public-records terms)"),
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
    reference = json.dumps({k: v for k, v in TERMINOLOGY.items() if k != "extraction_prompt"}, ensure_ascii=False)
    return f"""You read one tracked change from a site's redline of a clinical trial agreement and record what it says, as structured data. A rules engine decides the outcome from your values, so report facts, not judgments.

The sponsor's playbook (for context on which facts matter):
{playbook_text()}

Fields you may report (value formats):
{fields}

Canonical terminology reference (vocabulary and semantic examples, not a response schema):
{reference}

How to interpret the reference:
- The supplied reference covers the original 34 canonical fields; the Fields you may report table above is the authoritative live registry, including subsequent playbook fields. The reference does not restrict extraction to that subset. Preserve the live field descriptions, including the expanded institution_is_public context guidance.
- semantic_hints and category_aliases are examples of meaning and candidate retrieval cues, never exact keyword-matching triggers, literal substitutions, or rules for accepting or rejecting changes. Different wording may express the same obligation; identical words may have different consequences in context. The playbook is context only, not evidence that a term is present or acceptable.
- Resolve Sponsor, Institution, Company, Funding Agency, and Sponsor-Investigator from their contractual roles and duties. An Institution may be the Sponsor-Investigator in an investigator-initiated trial; do not automatically equate Company or Funding Agency with Sponsor. Do not put an external funder's rights or notice period in a sponsor field unless the agreement establishes that role for the obligation. If roles cannot be resolved, explain why and use confidence below 0.8.
- Locate relevant language across the supplied headings, schedules, appendices and cross-references. You receive one change and limited agreement context, not necessarily the entire agreement. Do not assume the contents of unseen definitions, schedules, or referenced clauses.
- Interpret obligations, party direction, scope, negations, conditions, exceptions, timing triggers, and compound duties before choosing a value. Do not infer a BAA from HIPAA authorization, perpetual protection from a trade-secret definition, injury benefits from medical costs, a research license from background IP, or a sponsor immunity duty from an institution merely reserving its own immunity.
- The reference's status=not_mentioned/value=null guidance means OMIT that field from values in this pipeline. Never emit null, \"null\", a status, evidence, page, or note for a field. Never turn silence into false, 0, none, removed, uncapped, or silent. An explicit absence supported by the supplied text or a tracked deletion is different from missing information.
- If a field is ambiguous, conditional, split by invention class, or has different notice periods for different termination triggers, omit that field unless one canonical value fully captures the supported obligation. Describe the branches, triggers, and evidence in rationale and use confidence below 0.8 so the existing rules request human review. Never choose one branch arbitrarily or flatten a condition into an unconditional boolean. Clear unrelated fields may still be reported.
- Publication review, patent filing delay, and multi-center embargo are separate timelines. A mutually agreed extension is not automatically an indefinite unilateral veto; assess the actual requirement and flag uncertainty. patent_delay=removed requires an actual comparison showing deletion; a standalone template's silence cannot establish removal. Report an explicitly present patent delay and its length when supported.
- no_substantive_change requires both old and new text and a comparison establishing no change to rights or obligations. Do not report it for a standalone template or for a comment with no comparison. The reference category any is only for that field; clause_type must remain one of the nine playbook clause types.
- Use only the {len(FIELDS)} existing field names in the live registry above and exact enum spellings. The reference's number and boolean types describe meaning; every reported value is still a STRING (for example \"30\" or \"true\"). Follow only the output contract below, not the standalone dictionary's richer output format.

How to answer:
- clause_type: the playbook clause type the change belongs to. Public-records disclosure terms are confidentiality, wherever they sit in the agreement.
- values: the fields this change sets or alters, as they stand after the site's edit. Include a field only when the text supports it. Every value is non-empty: a true-or-false field is exactly true or false. For a public-records or governing-law term, also report institution_is_public from the agreement context. Report termination_for_convenience only when this change gives the site that right; omit it when the original text already allowed it (for example, only the notice period changes). When the site deletes a provision, report the resulting state only if the comparison establishes it (for example patent_delay = removed, coordination_with_insurance = sponsor_pays_first). For a comment on unchanged text, report the facts of that text.
- quote: copy the exact words from the change text that support the value, character for character, including punctuation and curly quotes. Quote from the revised text for added or kept language and from the original text for deleted language. Keep each quote short (a clause, not a paragraph). Never paraphrase, join separate passages, or fill gaps, and never quote this message's own labels (such as "Tracked edits" or "(none)").
- novel_issue: if the change adds an obligation, restriction or right that no playbook rule addresses (for example, limits on training AI models), describe it in one sentence. A concept already covered by any live field, including fields beyond the reference's original 34, is not a new field merely because it lacks a decision rule. For a concept truly outside all supported fields in the live registry, separately identify it here as \"Proposed field: <concept>\" with a brief evidence-based explanation; do not add a field or decision rule. Otherwise null.
- confidence: 0 to 1. Use below 0.8 when the wording is ambiguous, open-ended, internally inconsistent, materially conditional in a way the field cannot represent, or you are unsure which field or party role applies.
- rationale: a brief explanation, including evidence and branches when meaning is unresolved.
Return only the strict JSON object with clause_type, values[{{field,value,quote}}], novel_issue, confidence, and rationale."""


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


def _live_cache_key(change: dict, context: str) -> str:
    """Version live clauses by the actual prompt and context; leave demo keys stable."""
    raw = json.dumps([_system_prompt(), _user_prompt(change, context)], ensure_ascii=False)
    return "clause-v2-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def lookup_cache(change: dict, context: str = "") -> dict | None:
    if hit := _load_cache().get(_live_cache_key(change, context)):
        return hit
    # Only the explicit seed fixtures may bypass prompt versioning. Old live
    # entries must not shadow those fixtures or bypass the expanded instructions.
    if SEED_CACHE.exists():
        return json.loads(SEED_CACHE.read_text()).get(cache_key(change))
    return None


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
        _client = openai.AsyncOpenAI(max_retries=8, timeout=settings.openai_timeout)
        _client_loop = loop
    return _client


async def complete_json(system: str, user: str, schema: dict, name: str, max_tokens: int) -> tuple[dict, str]:
    """One structured-output chat completion, checked. Returns the parsed answer and the model name;
    any failure, from the API or in the answer, raises ExtractionError with the reason."""
    if settings.claude_cli:
        from siteline import claude_cli  # imports ExtractionError from this module

        return await claude_cli.complete_json(system, user, schema)
    effort ={} if settings.claude_effort.lower() == "off" else {"reasoning_effort": settings.claude_effort}
    try:
        response = await client().chat.completions.create(
            model=settings.claude_model,
            max_completion_tokens=max_tokens,
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **effort,
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


async def extract_live(change: dict, context: str = "") -> dict:
    started = time.perf_counter()
    data, model = await complete_json(_system_prompt(), _user_prompt(change, context), SCHEMA, "extraction", 16000)
    data["model"] = model
    data["latencyMs"] = round((time.perf_counter() - started) * 1000)
    return data


async def extract_all(changes: list[dict], context: str, use_cache: bool) -> list[dict]:
    """One extraction per change, in parallel. Failures come back as {"error": ...}."""

    async def one(change: dict) -> dict:
        if use_cache:
            hit = lookup_cache(change, context)
            if hit:
                return {**hit, "cached": True}
        if not settings.claude_enabled:
            return {"error": "No OPENAI_API_KEY and no cached extraction for this change"}
        try:
            result = await extract_live(change, context)
        except ExtractionError as e:
            return {"error": str(e)}
        store_cache({_live_cache_key(change, context): result})
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
