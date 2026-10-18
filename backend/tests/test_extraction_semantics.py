"""Offline contract tests for terminology, prompt delivery, and the existing rule interface.

The semantic cases SCRIPT the extractor's answer. They check supported evidence and
downstream decisions, not whether a live LLM can interpret these phrasings correctly.
That interpretation still requires a separate live-model evaluation.
"""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from siteline import extraction
from siteline.playbook import CLAUSE_TYPES
from siteline.rules import decide
from siteline.verify import verify_value


# Preserve the supplied dictionary's original 34-field contract independently of
# later playbook additions. The live registry includes both sets of fields.
CANONICAL_FIELDS = {
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
PLAYBOOK_FIELDS = {
    "overhead_pct": ("payment_terms", "indirect cost (overhead) rate as a percent of direct costs, number only, e.g. 28"),
    "holdback_pct": ("payment_terms", "percent of each payment withheld until database lock, number; 0 when the holdback is deleted"),
    "screen_failures_per_enrolled": ("payment_terms", "screen failures paid per enrolled subject as a decimal, e.g. 0.33 for one per three enrolled, or uncapped"),
    "discloses_to_affiliates": ("confidentiality", "true or false: the site may share Confidential Information with affiliates or outside collaborators"),
    "marking_required": ("confidentiality", "true or false: only information marked confidential is protected"),
    "public_records_disclosure": ("confidentiality", "true or false: the site may disclose the agreement or information under a public-records law"),
    "public_records_notice": ("confidentiality", "true or false: the site notifies Sponsor before a public-records disclosure"),
    "claim_notice_days": ("indemnification", "integer days the site has to notify Sponsor of a claim"),
    "sponsor_controls_defense": ("indemnification", "true or false: Sponsor controls the defense and settlement of indemnified claims"),
    "additional_insured": ("indemnification", "true or false: Sponsor names the site as an additional insured on its policy"),
    "removes_injury_exclusions": ("subject_injury", "true or false: the exclusions (underlying disease, standard of care, protocol deviations) are deleted"),
    "multisite_wait_months": ("publication", "integer months the site waits for the multi-site publication before publishing on its own"),
    "site_may_file_patents": ("intellectual_property", "true or false: the site may file patents on study inventions in its own name"),
    "incident_notice_days": ("data_privacy", "integer business days Sponsor has to notify the site of a security incident"),
    "restricts_data_transfer": ("data_privacy", "true or false: Study data must stay in one state or country"),
    "arbitration_domestic": ("governing_law", "true or false: disputes go to arbitration in the United States instead of court"),
}
# Pin the complete merged registry, including the expanded public-institution
# guidance, without changing the canonical dictionary's original description.
_LIVE_FIELDS = {**CANONICAL_FIELDS, **PLAYBOOK_FIELDS,
    "institution_is_public": ("governing_law", "true or false: the institution is a public (state) institution (may be quoted from the agreement context; also used for public-records terms)"),
}
EXPECTED_FIELDS = {name: _LIVE_FIELDS[name] for name in (
    "net_days", "start_up_fee_pct", "start_up_fee_refundable", "overhead_pct", "holdback_pct", "screen_failures_per_enrolled",
    "survival_years", "trade_secrets_perpetual", "discloses_to_affiliates", "marking_required", "public_records_disclosure", "public_records_notice",
    "carve_out_standard", "adjudication_required", "mutual_indemnity", "claim_notice_days", "sponsor_controls_defense", "additional_insured",
    "covers_lost_wages", "covers_pain_and_suffering", "covers_travel", "reimbursement_cap", "coordination_with_insurance", "removes_injury_exclusions",
    "review_days", "review_window_open_ended", "patent_delay", "patent_delay_days", "multisite_wait_months",
    "invention_ownership", "site_research_license", "background_ip_retained", "site_may_file_patents",
    "requires_baa", "blocks_secondary_research", "data_use_addendum", "ml_training_restriction", "incident_notice_days", "restricts_data_transfer",
    "site_notice_days", "sponsor_notice_days", "termination_for_convenience", "pays_noncancellable_costs",
    "governing_law_state", "venue", "arbitration_abroad", "arbitration_domestic", "sovereign_immunity_waiver_required", "institution_is_public", "no_substantive_change",
)}
EXPECTED_CLAUSE_TYPES = [
    "indemnification", "subject_injury", "publication", "confidentiality",
    "intellectual_property", "data_privacy", "payment_terms", "termination", "governing_law",
]
ANSWER_KEYS = {"clause_type", "values", "novel_issue", "confidence", "rationale"}


def _change(text, section="Clinical terms"):
    return {"kind": "replacement", "section": section, "original": "Prior provision.",
            "revised": text, "segments": []}


def _answer(clause_type, values=(), *, confidence=0.95, rationale="Supported by the revised text.", novel_issue=None):
    return {"clause_type": clause_type, "values": list(values), "novel_issue": novel_issue,
            "confidence": confidence, "rationale": rationale}


def _value(field, value, quote):
    return {"field": field, "value": value, "quote": quote}


def _scripted_extract(monkeypatch, change, answer, context=""):
    """Run the real extract_live call with a scripted completion and no network/cache."""
    async def complete(system, user, schema, name, max_tokens):
        assert schema is extraction.SCHEMA
        return json.loads(json.dumps(answer)), "scripted-offline-model"

    monkeypatch.setattr(extraction, "complete_json", complete)
    result = asyncio.run(extraction.extract_live(change, context))
    assert set(result) == ANSWER_KEYS | {"model", "latencyMs"}
    assert {key: result[key] for key in ANSWER_KEYS} == answer
    assert all(set(v) == {"field", "value", "quote"} and isinstance(v["value"], str)
               and v["field"] in EXPECTED_FIELDS for v in result["values"])
    quotes_ok = all(verify_value(v, change, context) for v in result["values"])
    assert quotes_ok
    return result, decide(change, result, quotes_ok)


def test_canonical_and_playbook_fields_preserve_the_strict_output_schema():
    assert len(CANONICAL_FIELDS) == 34
    assert len(PLAYBOOK_FIELDS) == 16
    assert set(CANONICAL_FIELDS).isdisjoint(PLAYBOOK_FIELDS)
    assert len(EXPECTED_FIELDS) == 50
    assert extraction.FIELDS == EXPECTED_FIELDS
    assert CLAUSE_TYPES == EXPECTED_CLAUSE_TYPES
    assert extraction.SCHEMA == {
        "type": "object",
        "properties": {
            "clause_type": {"type": "string", "enum": EXPECTED_CLAUSE_TYPES},
            "values": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": list(EXPECTED_FIELDS)},
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


def test_complete_user_supplied_terminology_is_preserved_and_matches_fields():
    path = Path(extraction.__file__).with_name("cta_terminology.json")
    terminology = json.loads(path.read_text(encoding="utf-8"))
    assert extraction.TERMINOLOGY == terminology
    # SHA-256 of canonical JSON from the complete supplied v1.1 dictionary; independent
    # of whitespace/key ordering, sensitive to missing hints, aliases, or guardrails.
    canonical = json.dumps(terminology, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode()).hexdigest() == "8a430490a8bbe4e5e42d11da6cabb7dfea371a69341c60622dcceb3a1b3d23f2"
    assert {field: (info["category"], info["definition"])
            for field, info in terminology["fields"].items()} == CANONICAL_FIELDS


def test_live_extraction_receives_complete_terminology_and_original_interface(monkeypatch):
    """Capture the actual transport arguments, including every hint/alias/guardrail."""
    captured = []
    text = "Payment is due within thirty days of receipt of an undisputed invoice."
    change = _change(text, "Cost and Billings")
    change["segments"] = [{"type": "ins", "text": text, "author": "Institution"}]
    change["siteComment"] = "Please confirm this payment period."
    context = "Institution is the Sponsor-Investigator; Company provides study funding."
    answer = _answer("payment_terms", [_value("net_days", "30", text)])

    async def complete(system, user, schema, name, max_tokens):
        captured.append((system, user, schema, name, max_tokens))
        return dict(answer), "scripted-offline-model"

    monkeypatch.setattr(extraction, "complete_json", complete)
    out = asyncio.run(extraction.extract_live(change, context))
    assert {key: out[key] for key in ANSWER_KEYS} == answer
    assert out["model"] == "scripted-offline-model"
    assert isinstance(out["latencyMs"], int)
    assert len(captured) == 1
    system, user, schema, name, max_tokens = captured[0]
    assert schema is extraction.SCHEMA and name == "extraction" and max_tokens == 16000
    for supported in (text, context, change["section"], change["original"], change["siteComment"],
                      "INSERTED by Institution"):
        assert supported in user

    # Decode the embedded object instead of depending on JSON indentation or escaping.
    embedded = []
    decoder = json.JSONDecoder()
    for index, char in enumerate(system):
        if char == "{":
            try:
                embedded.append(decoder.raw_decode(system[index:])[0])
            except ValueError:
                pass
    reference = {key: value for key, value in extraction.TERMINOLOGY.items() if key != "extraction_prompt"}
    assert reference in embedded
    # Its standalone extraction_prompt has a conflicting output shape. Keep that
    # source text on disk while adapting every semantic section to the live schema.
    assert "Return one JSON object with every canonical key" not in system
    for field, (category, fmt) in EXPECTED_FIELDS.items():
        assert f"- {field} ({category}): {fmt}" in system
    adapter = system.split("How to interpret the reference:", 1)[1].lower()
    for instruction in (
        "authoritative live registry", "reference does not restrict extraction to that subset",
        "semantic_hints and category_aliases", "never exact keyword-matching triggers",
        "roles and duties", "do not automatically equate company or funding agency with sponsor",
        "omit that field", "never turn silence into false", "confidence below 0.8",
        "rationale", "every reported value is still a string", "50 existing field names",
        "proposed field:", "outside all supported fields in the live registry", "do not add a field or decision rule",
    ):
        assert instruction in adapter
    assert "Public-records disclosure terms are confidentiality, wherever they sit in the agreement." in system


@pytest.mark.parametrize(("clause_type", "text", "facts", "expected"), [
    ("payment_terms", "Indirect costs are 25% of direct costs.",
     [("overhead_pct", "25")], ("accept", "PAY-A4")),
    ("payment_terms", "Sponsor withholds 5% of each payment until database lock.",
     [("holdback_pct", "5")], ("accept", "PAY-A5")),
    ("payment_terms", "Sponsor pays up to 0.33 screen failures per enrolled subject.",
     [("screen_failures_per_enrolled", "0.33")], ("accept", "PAY-A6")),
    ("confidentiality", "Institution may disclose Confidential Information to its affiliates.",
     [("discloses_to_affiliates", "true")], ("counter", "CONF-C2")),
    ("confidentiality", "Only information marked confidential is protected.",
     [("marking_required", "true")], ("counter", "CONF-C3")),
    ("confidentiality", "Institution is a public state institution and may disclose the agreement under public-records law after notifying Sponsor.",
     [("public_records_disclosure", "true"), ("public_records_notice", "true"),
      ("institution_is_public", "true")], ("accept", "CONF-A4")),
    ("indemnification", "Institution must notify Sponsor of a claim within 10 days.",
     [("claim_notice_days", "10")], ("accept", "IND-A3")),
    ("indemnification", "Sponsor does not control the defense or settlement of indemnified claims.",
     [("sponsor_controls_defense", "false")], ("escalate", "IND-E3")),
    ("indemnification", "Sponsor names Institution as an additional insured on its policy.",
     [("additional_insured", "true")], ("accept", "IND-A4")),
    ("subject_injury", "The exclusions for underlying disease, standard of care and protocol deviations are deleted.",
     [("removes_injury_exclusions", "true")], ("escalate", "SI-E3")),
    ("publication", "Institution waits 12 months for the multi-site publication before publishing independently.",
     [("multisite_wait_months", "12")], ("accept", "PUB-A4")),
    ("intellectual_property", "Institution may file patents on Study inventions in its own name.",
     [("site_may_file_patents", "true")], ("counter", "IP-C1")),
    ("data_privacy", "Sponsor notifies Institution of security incidents within 5 business days.",
     [("incident_notice_days", "5")], ("accept", "DP-A3")),
    ("data_privacy", "Study Data must remain in Massachusetts.",
     [("restricts_data_transfer", "true")], ("escalate", "DP-E3")),
    ("governing_law", "Disputes must be arbitrated in Boston, Massachusetts, United States.",
     [("arbitration_domestic", "true")], ("counter", "GOV-C2")),
])
def test_scripted_new_playbook_fields_survive_the_semantic_adapter(monkeypatch, clause_type, text, facts, expected):
    """Every added field still reaches quote verification and its existing decision rule."""
    values = [_value(field, value, text) for field, value in facts]
    out, verdict = _scripted_extract(monkeypatch, _change(text, "General Provisions"),
                                    _answer(clause_type, values))
    assert out["values"] == values
    assert (verdict.outcome, verdict.rule_id) == expected


@pytest.mark.parametrize(("heading", "text"), [
    ("Payments", "Invoices are payable net 30 days."),
    ("Cost and Billings", "Payment shall be made within thirty days of receipt of invoice."),
    ("Financial Terms", "Undisputed invoices will be settled in 30 days."),
    ("Schedule 2", "Remittance is due thirty days after receiving a valid and accepted tax invoice."),
])
def test_scripted_payment_synonyms_keep_the_same_canonical_field_and_rule(monkeypatch, heading, text):
    out, verdict = _scripted_extract(monkeypatch, _change(text, heading),
                                    _answer("payment_terms", [_value("net_days", "30", text)]))
    assert out["values"][0]["field"] == "net_days"
    assert (verdict.outcome, verdict.rule_id) == ("accept", "PAY-A2")


@pytest.mark.parametrize(("days", "expected"), [
    ("10", ("escalate", "PAY-E1")),
    ("30", ("accept", "PAY-A2")),
    ("45", ("accept", "PAY-A1")),
])
def test_scripted_payment_timing_preserves_materially_different_consequences(monkeypatch, days, expected):
    text = f"Payment is due within {days} days of invoice receipt."
    _, verdict = _scripted_extract(monkeypatch, _change(text),
                                  _answer("payment_terms", [_value("net_days", days, text)]))
    assert (verdict.outcome, verdict.rule_id) == expected


@pytest.mark.parametrize(("coverage", "value", "expected"), [
    ("Reimbursement excludes lost wages.", "false", ("accept", "SI-A1")),
    ("Reimbursement includes lost wages.", "true", ("escalate", "SI-E1")),
    ("Compensation does not include loss of earnings.", "false", ("accept", "SI-A1")),
    ("Compensation includes loss of earnings.", "true", ("escalate", "SI-E1")),
])
def test_scripted_wage_synonyms_respect_negation_in_the_existing_rule_interface(monkeypatch, coverage, value, expected):
    insurance = "Sponsor reimburses medical costs less amounts paid by insurance."
    answer = _answer("subject_injury", [
        _value("covers_lost_wages", value, coverage),
        _value("coordination_with_insurance", "net_of_insurance", insurance),
    ])
    _, verdict = _scripted_extract(monkeypatch, _change(coverage + " " + insurance), answer)
    assert (verdict.outcome, verdict.rule_id) == expected


@pytest.mark.parametrize(("clause_type", "text"), [
    ("payment_terms", "The budget appears in Schedule 2."),
    ("confidentiality", "Confidential Information includes trade secrets."),
    ("subject_injury", "Sponsor will pay reasonable medical treatment expenses."),
    ("termination", "The parties may terminate for a material breach."),
])
def test_scripted_silence_omits_fields_and_cannot_create_a_rule_outcome(monkeypatch, clause_type, text):
    out, verdict = _scripted_extract(monkeypatch, _change(text), _answer(clause_type))
    assert out["values"] == []
    assert (verdict.outcome, verdict.rule_id) == ("human_review", "SYS-NORULE")


@pytest.mark.parametrize(("text", "baa_required", "expected"), [
    ("Sponsor must execute a business associate agreement.", True, ("escalate", "DP-E1")),
    ("A HIPAA business associate contract must be signed by Sponsor.", True, ("escalate", "DP-E1")),
    ("Subjects must sign a HIPAA Authorization before enrollment.", False, ("human_review", "SYS-NORULE")),
    ("Each party must comply with HIPAA and applicable privacy law.", False, ("human_review", "SYS-NORULE")),
])
def test_scripted_baa_obligation_is_distinct_from_hipaa_authorization_and_compliance(monkeypatch, text, baa_required, expected):
    values = [_value("requires_baa", "true", text)] if baa_required else []
    out, verdict = _scripted_extract(monkeypatch, _change(text), _answer("data_privacy", values))
    assert (verdict.outcome, verdict.rule_id) == expected
    if not baa_required:
        assert "requires_baa" not in {v["field"] for v in out["values"]}


def test_scripted_conditional_invention_ownership_uses_low_confidence_and_rationale(monkeypatch):
    text = "Sponsor owns drug-specific inventions; Institution owns independently developed platform inventions."
    rationale = "Ownership is conditional on invention class: Sponsor owns drug-specific inventions and Institution owns platform inventions."
    out, verdict = _scripted_extract(monkeypatch, _change(text),
                                    _answer("intellectual_property", confidence=0.65, rationale=rationale))
    assert out["values"] == [] and out["confidence"] < 0.8
    assert rationale in verdict.rule_text
    assert (verdict.outcome, verdict.rule_id) == ("human_review", "SYS-LOWCONF")


def test_scripted_proposed_field_uses_novel_issue_without_expanding_live_schema(monkeypatch):
    text = "Institution must retain study records for 25 years after study close."
    novel = "Proposed field: record_retention_years; Institution must retain study records for 25 years after study close."
    out, verdict = _scripted_extract(monkeypatch, _change(text),
                                    _answer("data_privacy", novel_issue=novel))
    assert out["novel_issue"] == novel and out["values"] == []
    assert "record_retention_years" not in extraction.FIELDS
    assert set(out) == ANSWER_KEYS | {"model", "latencyMs"}
    assert (verdict.outcome, verdict.rule_id) == ("human_review", "SYS-NOVEL")


def test_numeric_value_still_requires_the_number_in_its_verbatim_evidence():
    text = "Payment is due within thirty days after invoice receipt."
    change = _change(text)
    unsupported = _value("net_days", "45", text)
    assert not verify_value(unsupported, change)
    # The quote gate remains authoritative even when a term matches a semantic hint.
    verdict = decide(change, _answer("payment_terms", [unsupported]), False)
    assert (verdict.outcome, verdict.rule_id) == ("human_review", "SYS-QUOTE")
