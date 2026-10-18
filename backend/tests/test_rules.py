"""Every playbook position, decided from its limits: each rule ID at and around its thresholds."""

import copy
import inspect
import re

import pytest

from siteline import rules
from siteline.playbook import default_playbook
from siteline.rules import RULE_IDS, decide

FORM = "The form’s text."


def v(clause: str, revised: str = "The site’s text.", **values) -> tuple[dict, dict]:
    change = {"kind": "replacement", "section": "§1.1 Test", "original": FORM, "revised": revised}
    ex = {"clause_type": clause, "confidence": 0.95, "novel_issue": None, "rationale": "",
          "values": [{"field": k, "value": str(val), "quote": str(val)} for k, val in values.items()]}
    return change, ex


CASES = [
    # payment terms
    ("payment_terms", {"net_days": 45}, "PAY-A1"),
    ("payment_terms", {"net_days": 35}, "PAY-A2"),
    ("payment_terms", {"net_days": 29}, "PAY-E1"),
    ("payment_terms", {"start_up_fee_pct": 10}, "PAY-A3"),
    ("payment_terms", {"start_up_fee_pct": 12, "start_up_fee_refundable": "false"}, "PAY-C2"),
    ("payment_terms", {"start_up_fee_pct": 25, "start_up_fee_refundable": "true"}, "PAY-C2"),
    ("payment_terms", {"start_up_fee_pct": 25, "start_up_fee_refundable": "false"}, "PAY-E2"),
    ("payment_terms", {"overhead_pct": 25}, "PAY-A4"),
    ("payment_terms", {"overhead_pct": 28}, "PAY-C3"),
    ("payment_terms", {"overhead_pct": 31}, "PAY-E3"),
    ("payment_terms", {"holdback_pct": 10}, "PAY-A5"),
    ("payment_terms", {"holdback_pct": 5}, "PAY-A5"),
    ("payment_terms", {"holdback_pct": 4}, "PAY-C4"),
    ("payment_terms", {"holdback_pct": 0}, "PAY-C4"),
    ("payment_terms", {"screen_failures_per_enrolled": 0.33}, "PAY-A6"),
    ("payment_terms", {"screen_failures_per_enrolled": 0.5}, "PAY-C5"),
    ("payment_terms", {"screen_failures_per_enrolled": 0.6}, "PAY-E4"),
    ("payment_terms", {"screen_failures_per_enrolled": "uncapped"}, "PAY-E4"),
    # confidentiality
    ("confidentiality", {"survival_years": 7}, "CONF-A1"),
    ("confidentiality", {"survival_years": 5}, "CONF-A2"),
    ("confidentiality", {"survival_years": 4}, "CONF-C1"),
    ("confidentiality", {"survival_years": 2}, "CONF-E1"),
    ("confidentiality", {"trade_secrets_perpetual": "true"}, "CONF-A3"),
    ("confidentiality", {"trade_secrets_perpetual": "false"}, "CONF-E2"),
    ("confidentiality", {"discloses_to_affiliates": "true"}, "CONF-C2"),
    ("confidentiality", {"marking_required": "true"}, "CONF-C3"),
    ("confidentiality", {"public_records_disclosure": "true", "institution_is_public": "true", "public_records_notice": "true"}, "CONF-A4"),
    ("confidentiality", {"public_records_disclosure": "true", "institution_is_public": "true", "public_records_notice": "false"}, "CONF-E3"),
    ("confidentiality", {"public_records_disclosure": "true", "institution_is_public": "false", "public_records_notice": "true"}, "CONF-E3"),
    # indemnification
    ("indemnification", {"carve_out_standard": "negligence"}, "IND-A1"),
    ("indemnification", {"carve_out_standard": "gross_negligence_or_willful_misconduct"}, "IND-A2"),
    ("indemnification", {"carve_out_standard": "gross_negligence_or_willful_misconduct", "adjudication_required": "true"}, "IND-C1"),
    ("indemnification", {"carve_out_standard": "none"}, "IND-E1"),
    ("indemnification", {"mutual_indemnity": "true"}, "IND-E2"),
    ("indemnification", {"claim_notice_days": 30}, "IND-A3"),
    ("indemnification", {"claim_notice_days": 45}, "IND-C2"),
    ("indemnification", {"sponsor_controls_defense": "false"}, "IND-E3"),
    ("indemnification", {"additional_insured": "true"}, "IND-A4"),
    # subject injury
    ("subject_injury", {"covers_travel": "true"}, "SI-A3"),
    ("subject_injury", {"covers_lost_wages": "true"}, "SI-E1"),
    ("subject_injury", {"covers_pain_and_suffering": "true"}, "SI-E1"),
    ("subject_injury", {"coordination_with_insurance": "net_of_insurance"}, "SI-A1"),
    ("subject_injury", {"coordination_with_insurance": "sponsor_pays_first"}, "SI-A2"),
    ("subject_injury", {"reimbursement_cap": "uncapped"}, "SI-E2"),
    ("subject_injury", {"removes_injury_exclusions": "true"}, "SI-E3"),
    # publication
    ("publication", {"review_days": 60}, "PUB-A1"),
    ("publication", {"review_days": 90}, "PUB-A1"),
    ("publication", {"review_days": 45}, "PUB-C1"),
    ("publication", {"review_days": 20}, "PUB-E2"),
    ("publication", {"review_days": 45, "review_window_open_ended": "true"}, "PUB-E3"),
    ("publication", {"patent_delay": "retained"}, "PUB-A3"),
    ("publication", {"patent_delay": "removed"}, "PUB-E1"),
    ("publication", {"multisite_wait_months": 12}, "PUB-A4"),
    ("publication", {"multisite_wait_months": 6}, "PUB-C2"),
    # intellectual property
    ("intellectual_property", {"invention_ownership": "sponsor"}, "IP-A1"),
    ("intellectual_property", {"invention_ownership": "joint"}, "IP-E1"),
    ("intellectual_property", {"site_research_license": "true"}, "IP-A2"),
    ("intellectual_property", {"background_ip_retained": "true"}, "IP-A3"),
    ("intellectual_property", {"site_may_file_patents": "true"}, "IP-C1"),
    # data protection
    ("data_privacy", {"requires_baa": "true"}, "DP-E1"),
    ("data_privacy", {"blocks_secondary_research": "true"}, "DP-E2"),
    ("data_privacy", {"data_use_addendum": "true"}, "DP-A2"),
    ("data_privacy", {"incident_notice_days": 5}, "DP-A3"),
    ("data_privacy", {"incident_notice_days": 2}, "DP-C1"),
    ("data_privacy", {"restricts_data_transfer": "true"}, "DP-E3"),
    ("data_privacy", {"ml_training_restriction": "true"}, "SYS-NOVEL"),
    # termination
    ("termination", {"site_notice_days": 30}, "TERM-A0"),
    ("termination", {"site_notice_days": 45}, "TERM-A1"),
    ("termination", {"site_notice_days": 90}, "TERM-C1"),
    ("termination", {"site_notice_days": 10}, "TERM-E2"),
    ("termination", {"termination_for_convenience": "true", "pays_noncancellable_costs": "true"}, "TERM-A2"),
    ("termination", {"termination_for_convenience": "true", "pays_noncancellable_costs": "false"}, "TERM-E1"),
    ("termination", {"sponsor_notice_days": 60}, "TERM-A3"),
    ("termination", {"sponsor_notice_days": 90}, "TERM-C2"),
    # governing law
    ("governing_law", {"governing_law_state": "New Jersey", "venue": "sponsor_courts"}, "GOV-A1"),
    ("governing_law", {"governing_law_state": "Wisconsin", "venue": "silent", "institution_is_public": "true"}, "GOV-A2"),
    ("governing_law", {"governing_law_state": "Oklahoma", "institution_is_public": "false"}, "GOV-E2"),
    ("governing_law", {"venue": "site_courts_exclusive"}, "GOV-C1"),
    ("governing_law", {"arbitration_domestic": "true"}, "GOV-C2"),
    ("governing_law", {"arbitration_abroad": "true"}, "GOV-E1"),
]


@pytest.mark.parametrize("clause,values,rule_id", CASES, ids=[f"{c[2]}-{i}" for i, c in enumerate(CASES)])
def test_position_rules(clause, values, rule_id):
    assert decide(*v(clause, **values), True).rule_id == rule_id


def test_cases_reach_every_rule():
    assert {c[2] for c in CASES} >= RULE_IDS - {"PAY-A3P", "CONF-A2P", "PUB-A2P"}


def test_every_rule_id_is_in_the_playbook():
    listed = {r["id"] for c in default_playbook()["clauses"] for p in c["positions"] for r in p["rules"]}
    assert listed == set(RULE_IDS)
    in_code = set(re.findall(r'"((?:PAY|CONF|IND|SI|PUB|IP|DP|TERM|GOV)-[A-Z][0-9]+P?)"', inspect.getsource(rules)))
    assert in_code - set(rules.RULE_ALIASES) == set(RULE_IDS)


def test_limits_drive_decisions():
    pb = copy.deepcopy(default_playbook())
    overhead = next(p for c in pb["clauses"] for p in c["positions"] if p["id"] == "overhead")
    overhead["limits"]["standard"]["value"], overhead["limits"]["escalate_above"]["value"] = 30, 35
    assert decide(*v("payment_terms", overhead_pct=28), True, playbook=pb).rule_id == "PAY-A4"
    assert decide(*v("payment_terms", overhead_pct=28), True).rule_id == "PAY-C3"


def test_strictest_position_wins():
    verdict = decide(*v("payment_terms", overhead_pct=28, holdback_pct=0), True)
    assert verdict.rule_id == "PAY-C3" and "PAY-C4" in verdict.rule_text  # tie: overhead is listed first
    assert decide(*v("payment_terms", net_days=20, overhead_pct=28), True).rule_id == "PAY-E1"


def test_novel_term_never_hides_an_escalation():
    change, ex = v("data_privacy", requires_baa="true", ml_training_restriction="true")
    assert decide(change, ex, True).rule_id == "DP-E1"


@pytest.mark.parametrize("clause,values,revised,expected", [
    ("payment_terms", {"overhead_pct": 28}, "Indirect costs of twenty-eight percent (28%) of direct costs.",
     "Indirect costs of twenty-five percent (25%) of direct costs."),
    ("indemnification", {"claim_notice_days": 45}, "Notice within forty-five (45) days.", "Notice within thirty (30) days."),
    ("publication", {"multisite_wait_months": 6}, "Or six (6) months after the Study ends.", "Or eighteen (18) months after the Study ends."),
    ("data_privacy", {"incident_notice_days": 2}, "Notice within two (2) business days.", "Notice within five (5) business days."),
    ("termination", {"sponsor_notice_days": 90}, "On ninety (90) days’ written notice.", "On sixty (60) days’ written notice."),
    ("payment_terms", {"holdback_pct": 0}, "The site’s text.", FORM),
    ("confidentiality", {"discloses_to_affiliates": "true"}, "The site’s text.", FORM),
    ("intellectual_property", {"site_may_file_patents": "true"}, "The site’s text.", FORM),
    ("governing_law", {"arbitration_domestic": "true"}, "The site’s text.", FORM),
])
def test_counters_substitute_or_restore_the_form(clause, values, revised, expected):
    verdict = decide(*v(clause, revised=revised, **values), True)
    assert verdict.outcome == "counter" and verdict.counter_text == expected


def test_aliases_point_at_live_rules():
    assert set(rules.RULE_ALIASES.values()) <= set(RULE_IDS)


def test_priority_never_widens_a_band_whose_floor_equals_its_standard():
    pb = copy.deepcopy(default_playbook())
    fee = next(p for c in pb["clauses"] for p in c["positions"] if p["id"] == "start_up_fee")
    fee["limits"]["escalate_above"]["value"] = 10  # "escalate anything over 10%"
    high = {"level": "high", "share": 0.5, "days": 0, "bucket": "0-30", "moneyAtRiskPerWeek": 11200}
    verdict = decide(*v("payment_terms", start_up_fee_pct=60, start_up_fee_refundable="true"), True, high, pb)
    assert verdict.rule_id != "PAY-A3P" and verdict.outcome != "accept"


def test_two_positions_firing_counter_with_the_form():
    change, ex = v("payment_terms", revised="Holdback deleted; overhead twenty-eight percent (28%).", overhead_pct=28, holdback_pct=0)
    verdict = decide(change, ex, True)
    assert verdict.rule_id == "PAY-C3" and verdict.counter_text == FORM


def test_engine_positions_declare_exactly_the_rule_ids():
    assert {r for need in rules.ENGINE.values() for r in need["rules"]} == set(RULE_IDS)
