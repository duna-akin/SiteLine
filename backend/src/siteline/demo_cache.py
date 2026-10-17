"""Seed extraction for the demo file (PRD fallback: "cached extraction for the demo file").

These 14 entries were written by hand to match the demo script, including one deliberately
bad quote (change 12) and one low-confidence read (change 9), so the demo shows quote
verification and human review. Replace them with real model output any time with
`uv run siteline cache-demo`, which calls OpenAI on the demo file and overwrites the seed.
"""

from __future__ import annotations

import json

from siteline.demo import demo_bytes
from siteline.docx_redline import parse_docx
from siteline.extraction import cache_key, doc_cache_key, store_cache


def _v(field: str, value: str, quote: str) -> dict:
    return {"field": field, "value": value, "quote": quote}


SEED: dict[int, dict] = {
    1: {"clause_type": "payment_terms", "confidence": 0.97, "novel_issue": None,
        "rationale": "Raises the non-refundable start-up fee from 10% to 15% of the budget.",
        "values": [_v("start_up_fee_pct", "15", "fifteen percent (15%) of the study budget"),
                   _v("start_up_fee_refundable", "false", "non-refundable start-up fee")]},
    2: {"clause_type": "confidentiality", "confidence": 0.98, "novel_issue": None,
        "rationale": "Shortens confidentiality survival from 7 to 4 years.",
        "values": [_v("survival_years", "4", "survive for four (4) years after study close")]},
    3: {"clause_type": "indemnification", "confidence": 0.93, "novel_issue": None,
        "rationale": "Narrows the carve-out to gross negligence or willful misconduct and adds an adjudication requirement.",
        "values": [_v("carve_out_standard", "gross_negligence_or_willful_misconduct", "gross negligence or willful misconduct"),
                   _v("adjudication_required", "true", "as finally adjudicated")]},
    4: {"clause_type": "indemnification", "confidence": 0.95, "novel_issue": None,
        "rationale": "Adds a new section making indemnification obligations mutual.",
        "values": [_v("mutual_indemnity", "true", "the parties’ obligations under this Section 9 shall be mutual")]},
    5: {"clause_type": "subject_injury", "confidence": 0.96, "novel_issue": None,
        "rationale": "Adds lost wages and travel costs to subject-injury reimbursement.",
        "values": [_v("covers_lost_wages", "true", "including lost wages and travel costs"),
                   _v("covers_travel", "true", "including lost wages and travel costs")]},
    6: {"clause_type": "subject_injury", "confidence": 0.94, "novel_issue": None,
        "rationale": "Deletes coordination with the subject's insurance, so the sponsor pays first.",
        "values": [_v("coordination_with_insurance", "sponsor_pays_first", "Reimbursement is net of amounts paid by the subject’s insurance.")]},
    7: {"clause_type": "data_privacy", "confidence": 0.97, "novel_issue": None,
        "rationale": "Requires the sponsor to sign the institution's Business Associate Agreement.",
        "values": [_v("requires_baa", "true", "Sponsor shall execute Institution’s form Business Associate Agreement")]},
    8: {"clause_type": "data_privacy", "confidence": 0.91,
        "novel_issue": "Bars using coded study data to train or fine-tune machine learning models without consent; the playbook has no rule on model training.",
        "rationale": "New restriction on machine-learning use of coded data.",
        "values": [_v("ml_training_restriction", "true", "shall not use coded study data to train or fine-tune machine learning models")]},
    9: {"clause_type": "publication", "confidence": 0.58, "novel_issue": None,
        "rationale": "The qualifier makes the review window open-ended.",
        "values": [_v("review_days", "45", "forty-five (45) days, or as otherwise agreed"),
                   _v("review_window_open_ended", "true", "or as otherwise agreed")]},
    10: {"clause_type": "publication", "confidence": 0.96, "novel_issue": None,
         "rationale": "Deletes the sponsor's right to delay publication for patent filings.",
         "values": [_v("patent_delay", "removed", "Institution shall delay publication up to an additional sixty (60) days to permit patent filings")]},
    11: {"clause_type": "intellectual_property", "confidence": 0.92, "novel_issue": None,
         "rationale": "Comment asks to confirm that existing software stays background IP; the text keeps background IP with its owner.",
         "values": [_v("background_ip_retained", "true", "Each party retains ownership of its background intellectual property.")]},
    12: {"clause_type": "intellectual_property", "confidence": 0.88, "novel_issue": None,
         "rationale": "Makes study inventions jointly owned.",
         "values": [_v("invention_ownership", "joint", "inventions arising from the Protocol or Study Drug shall be jointly owned")]},
    13: {"clause_type": "termination", "confidence": 0.99, "novel_issue": None,
         "rationale": "Extends the institution's termination notice from 30 to 60 days.",
         "values": [_v("site_notice_days", "60", "sixty (60) days’ written notice")]},
    14: {"clause_type": "governing_law", "confidence": 0.95, "novel_issue": None,
         "rationale": "Switches to Wisconsin law with exclusive venue in Dane County courts.",
         "values": [_v("governing_law_state", "Wisconsin", "governed by the laws of the State of Wisconsin"),
                    _v("venue", "site_courts_exclusive", "exclusive venue in the courts of Dane County"),
                    _v("institution_is_public", "true", "a public institution of the State of Wisconsin")]},
}


def _figures(target: str, months: str, usd: str, enroll_quote: str, pay_quote: str) -> dict:
    return {"confidence": 0.97, "rationale": "The agreement states the site's enrollment target, period and per-patient payment.",
            "figures": [_v("enrollment_target_subjects", target, enroll_quote),
                        _v("enrollment_period_months", months, enroll_quote),
                        _v("per_patient_amount_usd", usd, pay_quote)],
            "model": "seed (hand-written)", "latencyMs": 0}


def seed_figures() -> dict[str, dict]:
    """Whole-agreement readings (priority figures) for the demo file and the seeded emails'
    attachments, keyed like extract_document's cache, so priority works without an API key."""
    from siteline.inbound_email import enrollment_sentence, payment_sentence, seed_attachment
    from siteline.priority import document_text
    from siteline.store import SEED_PATH

    out = {doc_cache_key(document_text(parse_docx(demo_bytes()))): _figures(
        "48", "18", "18200", "enroll 48 subjects over an enrollment period of 18 months", "USD 18,200 per enrolled subject")}
    for e in json.loads(SEED_PATH.read_text())["emails"]:
        if fig := e.get("enrollment"):
            text = document_text(parse_docx(seed_attachment(e)))
            out[doc_cache_key(text)] = _figures(str(fig["targetSubjects"]), str(fig["months"]), str(fig["perPatientUsd"]),
                                                enrollment_sentence(fig), payment_sentence(fig))
    return out


def write_seed() -> int:
    parsed = parse_docx(demo_bytes())
    entries = {}
    for change in parsed["changes"]:
        seed = SEED[change["index"]]
        entries[cache_key(change)] = {**seed, "model": "seed (hand-written)", "latencyMs": 0}
    entries.update(seed_figures())
    store_cache(entries, seed=True)
    return len(entries)
