"""Nine sample redlines for tests and demos, one per playbook clause (Sites 21–29).

Each sample is the form agreement (cta_base) with tracked changes that center on one clause's
issues, plus a few edits elsewhere. Every change carries a hand-written seed extraction, so the samples triage
without an API key, and the outcome and rule ID a contract manager would expect. Between them
the samples reach every clause rule and system check in rules.py, and every priority level.

All text is written for this project. It is not real contract language and comes from no real
sponsor, site or agreement (PRD clean-room rule).

Run `uv run siteline make-samples` to (re)write data/samples/*.docx and add their seeds to the
extraction cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from siteline.config import DATA_DIR
from siteline.cta_base import PRIVATE, Block, Site, agreement_blocks
from siteline.demo import build_redline
from siteline.docx_redline import parse_docx

SAMPLES_DIR = DATA_DIR / "samples"
DATE = "2026-10-16T13:20:00Z"


def T(text: str) -> dict:
    return {"type": "text", "text": text}


def I(text: str) -> dict:  # noqa: E743
    return {"type": "ins", "text": text}


def D(text: str) -> dict:
    return {"type": "del", "text": text}


@dataclass
class Change:
    section: str
    segments: list[dict]
    clause: str
    values: list[tuple[str, str, str]]  # (field, value, verbatim quote)
    expect: tuple[str, str]  # (outcome, rule ID) under the default playbook and priority config
    rationale: str
    confidence: float = 0.95
    novel: str | None = None
    comment: str | None = None
    mark: str | None = None  # "ins" | "del" when the whole paragraph is inserted or deleted

    def seed(self) -> dict:
        return {
            "clause_type": self.clause,
            "confidence": self.confidence,
            "novel_issue": self.novel,
            "rationale": self.rationale,
            "values": [{"field": f, "value": v, "quote": q} for f, v, q in self.values],
            "model": "seed (hand-written)",
            "latencyMs": 0,
        }


@dataclass
class Sample:
    number: str
    clause: str
    slug: str
    name: str
    city: str
    status: str  # how the preamble describes the institution
    author: str
    enrollment: tuple[int, int, int]  # subjects, months, USD per subject
    priority: str  # the level those figures give under data/priority_config.json
    changes: list[Change] = field(default_factory=list)

    @property
    def agreement_id(self) -> str:
        return f"site-{self.number}"

    @property
    def file_name(self) -> str:
        return f"NSO-417_CTA_Site{self.number}_{self.slug}_redline.docx"

    @property
    def path(self):
        return SAMPLES_DIR / self.file_name


def _invoices(new: str) -> list[dict]:
    return [T("Sponsor shall pay each undisputed invoice within "), D("forty-five (45)"), I(new), T(" days of receipt, with quarterly reconciliation.")]


def _start_up_fee(new: str) -> list[dict]:
    return [T("Sponsor shall pay a non-refundable start-up fee equal to "), D("ten percent (10%)"), I(new), T(" of the study budget.")]


def _survival(new: str) -> list[dict]:
    return [T("The obligations in this Section 8 survive for "), D("seven (7)"), I(new), T(" years after study close.")]


def _review(new: str) -> list[dict]:
    return [T("Institution shall provide Sponsor "), D("sixty (60) days"), I(new), T(" to review any proposed publication.")]


def _site_notice(new: str) -> list[dict]:
    return [T("Institution may terminate this Agreement on "), D("thirty (30)"), I(new), T(" days’ written notice.")]


FEE_NONREFUNDABLE = ("start_up_fee_refundable", "false", "non-refundable start-up fee")


SAMPLES: list[Sample] = [
    Sample("21", "payment_terms", "payment", "Copperline Regional Medical Center", "Boise, ID", PRIVATE,
           "K. Okafor (Site 21)", (60, 12, 22000), "high", [
        Change("§6.2 Invoices", _invoices("twenty (20)"), "payment_terms",
               [("net_days", "20", "twenty (20) days of receipt")], ("escalate", "PAY-E1"),
               "Shortens invoice payment from Net 45 to Net 20."),
        Change("§6.3 Start-up Fee", _start_up_fee("fourteen percent (14%)"), "payment_terms",
               [("start_up_fee_pct", "14", "fourteen percent (14%)"), FEE_NONREFUNDABLE], ("accept", "PAY-A3P"),
               "Raises the non-refundable start-up fee from 10% to 14% of the budget."),
        Change("§6.4 Pass-Through Costs",
               [T("Sponsor shall reimburse pass-through costs within "), D("forty-five (45)"), I("thirty-five (35)"),
                T(" days of receipt of an itemized invoice.")], "payment_terms",
               [("net_days", "35", "thirty-five (35) days of receipt")], ("accept", "PAY-A2"),
               "Shortens pass-through reimbursement from 45 to 35 days."),
        Change("§6.5 Holdback", [D("Sponsor may withhold ten percent (10%) of each payment until the Study database is locked.")],
               "payment_terms", [], ("human_review", "SYS-NORULE"),
               "Deletes the sponsor's holdback; the playbook has no holdback term.", confidence=0.9, mark="del"),
        Change("§6.6 Administration Fee",
               [I("Sponsor shall pay Institution a monthly study administration fee of USD 1,750, whether or not any subject is enrolled.")],
               "payment_terms", [], ("human_review", "SYS-NOVEL"), "Adds a fixed monthly fee owed regardless of enrollment.",
               confidence=0.92, mark="ins",
               novel="Adds a monthly administration fee owed whether or not anyone enrolls; the playbook has no rule on recurring fees."),
        Change("§6.7 Currency", [T("All payments shall be made in United States "), D("Dollars"), I("dollars"), T(" by electronic transfer.")],
               "payment_terms", [("no_substantive_change", "true", "United States dollars")], ("accept", "SYS-COSMETIC"),
               "Capitalization fix only."),
        Change("§14.2 Termination by Institution", _site_notice("forty-five (45)"), "termination",
               [("site_notice_days", "45", "forty-five (45) days’ written notice")], ("accept", "TERM-A1"),
               "Extends the institution's termination notice from 30 to 45 days."),
    ]),
    Sample("22", "confidentiality", "confidentiality", "Halvorsen Research Hospital", "Duluth, MN", PRIVATE,
           "L. Brandt (Site 22)", (20, 24, 15000), "standard", [
        Change("§6.2 Invoices", _invoices("sixty (60)"), "payment_terms",
               [("net_days", "60", "sixty (60) days of receipt")], ("accept", "PAY-A1"),
               "Lengthens invoice payment from Net 45 to Net 60."),
        Change("§8.1 Confidential Information",
               [T("Institution shall hold Sponsor’s Confidential Information in confidence and use it only to conduct the Study.")],
               "confidentiality", [], ("human_review", "SYS-COMMENT"), "Comment asks a question about unchanged text.",
               confidence=0.9,
               comment="Does this cover oral disclosures at the site initiation visit? Our IRB would prefer that it does not."),
        Change("§8.2 Permitted Disclosures",
               [T("Institution may disclose Confidential Information "), I("to its affiliates and research collaborators and "),
                T("as required by law.")], "confidentiality", [], ("human_review", "SYS-LOWCONF"),
               "Unclear whether research collaborators are bound by Section 8.", confidence=0.62),
        Change("§8.4 Term of Confidentiality", _survival("two (2)"), "confidentiality",
               [("survival_years", "2", "survive for two (2) years after study close")], ("escalate", "CONF-E1"),
               "Shortens confidentiality survival from 7 to 2 years."),
        Change("§8.5 Trade Secrets",
               [T("Information that is a trade secret remains confidential "), D("for as long as it remains a trade secret"),
                I("only for the term stated in Section 8.4"), T(".")], "confidentiality",
               [("trade_secrets_perpetual", "false", "only for the term stated in Section 8.4")], ("escalate", "CONF-E2"),
               "Ends perpetual protection for trade secrets."),
        Change("§8.6 Third-Party Information",
               [T("Obligations for confidential information of third parties disclosed during the Study survive for "),
                D("seven (7)"), I("four (4)"), T(" years after study close.")], "confidentiality",
               [("survival_years", "4", "survive for four (4) years after study close")], ("counter", "CONF-F1"),
               "Shortens survival for third-party information from 7 to 4 years."),
        Change("§12.1 Sponsor Review", _review("seventy (70) days"), "publication",
               [("review_days", "70", "seventy (70) days to review")], ("accept", "PUB-A2"),
               "Lengthens the publication review to 70 days."),
    ]),
    Sample("23", "indemnification", "indemnification", "Marrowgate Health System", "Albany, NY", PRIVATE,
           "P. Delacroix (Site 23)", (30, 24, 12000), "standard", [
        Change("§9.1 Indemnification by Sponsor",
               [T("Sponsor shall indemnify and hold harmless Institution from claims arising from the Study Drug or the Protocol"),
                D(", except to the extent caused by the negligence of Institution"), T(".")], "indemnification",
               [("carve_out_standard", "none", "except to the extent caused by the negligence of Institution")],
               ("escalate", "IND-E1"), "Deletes the negligence carve-out from the sponsor's indemnity."),
        Change("§9.2 Indemnified Persons",
               [T("Sponsor’s obligations in Section 9.1 extend to Institution’s investigators and staff, except to the extent caused by their "),
                D("negligence"), I("gross negligence or willful misconduct, as finally adjudicated"), T(".")], "indemnification",
               [("carve_out_standard", "gross_negligence_or_willful_misconduct", "gross negligence or willful misconduct"),
                ("adjudication_required", "true", "as finally adjudicated")], ("counter", "IND-F1"),
               "Narrows the investigators' carve-out to gross negligence and requires final adjudication."),
        Change("§9.3 Indemnification by Institution",
               [I("Institution shall indemnify Sponsor to the same extent that Sponsor indemnifies Institution, so that the obligations in this Section 9 are mutual.")],
               "indemnification", [("mutual_indemnity", "true", "the obligations in this Section 9 are mutual")],
               ("escalate", "IND-E2"), "Adds a reciprocal indemnity from the institution.", mark="ins",
               comment="Our board requires reciprocal indemnities in every industry agreement."),
        Change("§9.5 Comparator Products",
               [T("For claims arising from a comparator product supplied by Sponsor, Sponsor’s indemnity applies except to the extent caused by the "),
                D("negligence"), I("gross negligence or willful misconduct"), T(" of Institution.")], "indemnification",
               [("carve_out_standard", "gross_negligence_or_willful_misconduct", "gross negligence or willful misconduct")],
               ("accept", "IND-A2"), "Narrows the comparator carve-out to gross negligence or willful misconduct."),
        Change("§9.6 Notice of Claims",
               [T("Institution shall notify Sponsor in writing of any claim within "), D("ten (10)"), I("thirty (30)"),
                T(" days after receiving notice of it.")], "indemnification", [], ("human_review", "SYS-NORULE"),
               "Extends the time to notify Sponsor of a claim; the playbook has no notice-of-claim term.", confidence=0.88),
        Change("§9.7 Insurance",
               [I("Sponsor shall name Institution as an additional insured on its clinical trial liability policy and provide a certificate of insurance on request.")],
               "indemnification", [], ("human_review", "SYS-NOVEL"), "Adds an additional-insured requirement.", confidence=0.9, mark="ins",
               novel="Requires Sponsor to name Institution as an additional insured; the playbook has no insurance term."),
        Change("§10.4 Coordination of Benefits",
               [T("Reimbursement is net of amounts paid by the subject’s "), D("insurance"), I("health insurance or other third-party payer"), T(".")],
               "subject_injury", [("coordination_with_insurance", "net_of_insurance", "net of amounts paid by the subject’s health insurance")],
               ("accept", "SI-A1"), "Clarifies that reimbursement stays net of any third-party payer."),
        Change("§17.1 Governing Law and Venue",
               [T("This Agreement is governed by the laws of the State of New Jersey, with venue in "), D("its state courts"),
                I("the state or federal courts located in Mercer County, New Jersey"), T(".")], "governing_law",
               [("governing_law_state", "New Jersey", "governed by the laws of the State of New Jersey"),
                ("venue", "sponsor_courts", "the state or federal courts located in Mercer County, New Jersey")],
               ("accept", "GOV-A1"), "Keeps New Jersey law and names a New Jersey venue."),
    ]),
    Sample("24", "subject_injury", "subject-injury", "Saltmarsh Clinical Research Center", "Savannah, GA", PRIVATE,
           "M. Haddad (Site 24)", (16, 18, 13500), "standard", [
        Change("§6.3 Start-up Fee", _start_up_fee("eight percent (8%)"), "payment_terms",
               [("start_up_fee_pct", "8", "eight percent (8%)"), FEE_NONREFUNDABLE], ("accept", "PAY-A3"),
               "Lowers the start-up fee from 10% to 8% of the budget."),
        Change("§8.4 Term of Confidentiality", _survival("five (5)"), "confidentiality",
               [("survival_years", "5", "survive for five (5) years after study close")], ("accept", "CONF-A2"),
               "Shortens confidentiality survival from 7 to 5 years."),
        Change("§10.2 Subject Injury Reimbursement",
               [T("Sponsor shall reimburse reasonable and necessary medical expenses"), I(", together with compensation for pain and suffering,"),
                T(" incurred by a Study Subject for the diagnosis and treatment of a Study Injury.")], "subject_injury",
               [("covers_pain_and_suffering", "true", "compensation for pain and suffering")], ("escalate", "SI-E1"),
               "Adds pain and suffering to subject-injury reimbursement."),
        Change("§10.3 Limits",
               [T("Sponsor’s reimbursement under this Section 10 "), D("shall not exceed the amounts set out in Exhibit C"),
                I("is not subject to any cap or limit"), T(".")], "subject_injury",
               [("reimbursement_cap", "uncapped", "is not subject to any cap or limit")], ("escalate", "SI-E2"),
               "Removes the cap on subject-injury reimbursement."),
        Change("§10.4 Coordination of Benefits",
               [T("Reimbursement is "), D("net of amounts paid by"), I("paid by Sponsor first, without first billing"), T(" the subject’s insurance.")],
               "subject_injury", [("coordination_with_insurance", "sponsor_pays_first", "paid by Sponsor first, without first billing the subject’s insurance")],
               ("accept", "SI-A2"), "Sponsor pays first instead of coordinating with the subject's insurance."),
        Change("§10.5 Travel Costs",
               [I("Sponsor shall also reimburse reasonable travel costs a Study Subject incurs to attend treatment for a Study Injury.")],
               "subject_injury", [("covers_travel", "true", "reimburse reasonable travel costs")], ("human_review", "SYS-NORULE"),
               "Adds travel costs to subject-injury reimbursement.", mark="ins"),
        Change("§10.6 Medical Monitoring",
               [I("For five (5) years after a Study Injury, Sponsor shall fund medical monitoring of the affected Study Subject.")],
               "subject_injury", [], ("human_review", "SYS-NOVEL"), "Adds sponsor-funded follow-up care.", confidence=0.9, mark="ins",
               novel="Adds five years of sponsor-funded medical monitoring after a Study Injury; the playbook has no follow-up care term."),
        Change("§14.2 Termination by Institution", _site_notice("ninety (90)"), "termination",
               [("site_notice_days", "90", "ninety (90) days’ written notice")], ("counter", "TERM-F1"),
               "Extends the institution's termination notice from 30 to 90 days."),
    ]),
    Sample("25", "publication", "publication", "Thornbury University Hospital", "Lexington, KY",
           "a public institution of the Commonwealth of Kentucky", "Dr. S. Iyer (PI, Site 25)", (18, 24, 16000), "standard", [
        Change("§12.1 Sponsor Review", _review("twenty-one (21) days"), "publication",
               [("review_days", "21", "twenty-one (21) days to review any proposed publication")], ("escalate", "PUB-E2"),
               "Shortens the sponsor's publication review from 60 to 21 days."),
        Change("§12.2 Abstracts and Presentations",
               [T("Institution shall provide Sponsor "), D("sixty (60) days"), I("forty (40) days"),
                T(" to review abstracts and conference presentations.")], "publication",
               [("review_days", "40", "forty (40) days to review abstracts")], ("counter", "PUB-F1"),
               "Shortens the review of abstracts from 60 to 40 days."),
        Change("§12.3 Patent Delay",
               [T("At Sponsor’s request, Institution shall "), D("delay publication up to an additional sixty (60) days to permit patent filings"),
                I("give good-faith consideration to any request to delay publication"), T(".")], "publication",
               [("patent_delay", "removed", "delay publication up to an additional sixty (60) days to permit patent filings")],
               ("escalate", "PUB-E1"), "Replaces the sponsor's patent delay with a good-faith consideration."),
        Change("§12.4 Independent Publication",
               [T("Institution may publish its own results after the multi-site publication or "), D("eighteen (18)"), I("twelve (12)"),
                T(" months after study close, whichever is earlier.")], "publication", [], ("human_review", "SYS-NORULE"),
               "Shortens the wait before independent publication from 18 to 12 months; no rule field covers it.", confidence=0.86),
        Change("§12.6 Student Theses",
               [T("Institution shall provide Sponsor "), D("sixty (60) days"), I("thirty (30) days, or as otherwise agreed,"),
                T(" to review a student thesis that uses Study data.")], "publication",
               [("review_days", "30", "thirty (30) days, or as otherwise agreed"),
                ("review_window_open_ended", "true", "or as otherwise agreed")], ("escalate", "PUB-E3"),
               "Shortens thesis review to 30 days and leaves it open-ended.", confidence=0.86),
        Change("§17.1 Governing Law and Venue",
               [T("This Agreement is governed by the laws of the "), D("State of New Jersey, with venue in its state courts"),
                I("Commonwealth of Kentucky"), T(".")], "governing_law",
               [("governing_law_state", "Kentucky", "governed by the laws of the Commonwealth of Kentucky"),
                ("venue", "silent", "with venue in its state courts"),
                ("institution_is_public", "true", "a public institution of the Commonwealth of Kentucky")],
               ("accept", "GOV-A2"), "Switches to Kentucky law for a public institution and drops the venue clause."),
    ]),
    Sample("26", "intellectual_property", "ip", "Ashgrove Biomedical Institute", "Worcester, MA", PRIVATE,
           "Tech Transfer (Site 26)", (12, 18, 19000), "standard", [
        Change("§6.3 Start-up Fee", _start_up_fee("twelve percent (12%)"), "payment_terms",
               [("start_up_fee_pct", "12", "twelve percent (12%)"), FEE_NONREFUNDABLE], ("counter", "PAY-F2"),
               "Raises the non-refundable start-up fee from 10% to 12% of the budget."),
        Change("§8.4 Term of Confidentiality", _survival("ten (10)"), "confidentiality",
               [("survival_years", "10", "survive for ten (10) years after study close")], ("accept", "CONF-A1"),
               "Lengthens confidentiality survival from 7 to 10 years."),
        Change("§13.1 Background IP",
               [T("Each party retains ownership of its background intellectual property"),
                I(", including software and know-how developed before the Effective Date"), T(".")], "intellectual_property",
               [("background_ip_retained", "true", "Each party retains ownership of its background intellectual property")],
               ("accept", "IP-A3"), "Spells out that pre-existing software and know-how stay background IP."),
        Change("§13.2 Study Inventions",
               [T("All inventions arising from the Protocol or Study Drug shall "), D("belong to Sponsor"),
                I("belong to Institution where conceived solely by Institution personnel"), T(".")], "intellectual_property",
               [("invention_ownership", "institution", "belong to Institution where conceived solely by Institution personnel")],
               ("escalate", "IP-E1"), "Gives the institution ownership of inventions its own staff conceive."),
        Change("§13.3 Research License",
               [I("Institution retains a non-exclusive, royalty-free license to use Study Inventions for internal, non-commercial research.")],
               "intellectual_property",
               [("site_research_license", "true", "a non-exclusive, royalty-free license to use Study Inventions for internal, non-commercial research")],
               ("accept", "IP-A2"), "Adds a non-exclusive research license for the institution.", mark="ins"),
        Change("§13.4 Joint Inventions",
               [T("Inventions conceived jointly by Sponsor and Institution personnel shall "), D("be assigned to Sponsor"),
                I("be jointly owned by Sponsor and Institution"), T(".")], "intellectual_property",
               [("invention_ownership", "joint", "be jointly owned by Sponsor and Institution")], ("escalate", "IP-E1"),
               "Makes jointly conceived inventions jointly owned."),
        Change("§13.5 Patent Filings",
               [T("Sponsor shall control and pay for patent filings on Study Inventions."),
                I(" If Sponsor declines to file within ninety (90) days, Institution may file in its own name.")],
               "intellectual_property", [], ("human_review", "SYS-NOVEL"), "Adds a step-in right to file patents.", confidence=0.9,
               novel="Lets Institution file patents in its own name if Sponsor declines; the playbook has no patent-prosecution term."),
        Change("§13.6 Invention Disclosure",
               [T("Sponsor shall "), D("recieve"), I("receive"), T(" prompt written disclosure of each Study Invention.")],
               "intellectual_property", [("no_substantive_change", "true", "receive prompt written disclosure")],
               ("accept", "SYS-COSMETIC"), "Spelling fix only."),
    ]),
    Sample("27", "data_privacy", "data-protection", "Kestrel Valley Health", "Spokane, WA", PRIVATE,
           "Privacy Office (Site 27)", (22, 24, 14500), "standard", [
        Change("§6.3 Start-up Fee", _start_up_fee("twenty-five percent (25%)"), "payment_terms",
               [("start_up_fee_pct", "25", "twenty-five percent (25%)"), FEE_NONREFUNDABLE], ("escalate", "PAY-E2"),
               "Raises the non-refundable start-up fee from 10% to 25% of the budget."),
        Change("§11.3 Business Associate Agreement",
               [I("Before any Study data is transferred, Sponsor shall sign Institution’s form Business Associate Agreement.")],
               "data_privacy", [("requires_baa", "true", "Sponsor shall sign Institution’s form Business Associate Agreement")],
               ("escalate", "DP-E1"), "Requires the sponsor to sign a Business Associate Agreement.", mark="ins"),
        Change("§11.4 Limited Data Set",
               [I("For any Limited Data Set, Sponsor shall execute Institution’s limited data use addendum.")],
               "data_privacy", [("data_use_addendum", "true", "Sponsor shall execute Institution’s limited data use addendum")],
               ("accept", "DP-A2"), "Requires a limited data-use addendum.", mark="ins"),
        Change("§11.5 Secondary Use",
               [T("Sponsor may use coded Study data for future research"), D(" related to the Study Drug or other oncology programs"),
                I(" only with Institution’s written approval of each project"), T(".")], "data_privacy",
               [("blocks_secondary_research", "true", "only with Institution’s written approval of each project")],
               ("escalate", "DP-E2"), "Makes every secondary research use subject to the institution's approval."),
        Change("§11.6 Artificial Intelligence",
               [I("Sponsor shall not use coded Study data to train artificial intelligence models or disclose it to a third-party artificial intelligence service.")],
               "data_privacy", [("ml_training_restriction", "true", "shall not use coded Study data to train artificial intelligence models")],
               ("human_review", "SYS-NOVEL"), "Restricts AI training on coded data.", confidence=0.91, mark="ins",
               novel="Bars training AI models on coded data or sharing it with AI services; the playbook has no rule on model training."),
        Change("§11.7 Security Incidents",
               [T("Sponsor shall notify Institution of a security incident involving Study data within "), D("ten (10)"), I("two (2)"),
                T(" business days.")], "data_privacy", [], ("human_review", "SYS-NORULE"),
               "Shortens the sponsor's breach notice from 10 to 2 business days; the playbook has no breach-notice term.", confidence=0.87),
        Change("§12.1 Sponsor Review", _review("ninety (90) days"), "publication",
               [("review_days", "90", "ninety (90) days to review")], ("accept", "PUB-A1"),
               "Lengthens the publication review to 90 days."),
    ]),
    Sample("28", "termination", "termination", "Brightwater Oncology Partners", "Tulsa, OK", PRIVATE,
           "D. Castellano (Site 28)", (26, 30, 11000), "standard", [
        Change("§12.3 Patent Delay",
               [T("At Sponsor’s request, Institution shall delay publication up to an additional "), D("sixty (60)"), I("ninety (90)"),
                T(" days to permit patent filings.")], "publication",
               [("patent_delay", "retained", "Institution shall delay publication"),
                ("patent_delay_days", "90", "ninety (90) days to permit patent filings")], ("accept", "PUB-A3"),
               "Lengthens the patent delay from 60 to 90 days."),
        Change("§13.2 Study Inventions",
               [T("All inventions arising from the Protocol or Study Drug shall belong to Sponsor"),
                I(", which shall have the sole right to seek patent protection for them"), T(".")], "intellectual_property",
               [("invention_ownership", "sponsor", "shall belong to Sponsor")], ("accept", "IP-A1"),
               "Keeps sponsor ownership and adds its sole right to patent."),
        Change("§14.2 Termination by Institution", _site_notice("ten (10)"), "termination",
               [("site_notice_days", "10", "ten (10) days’ written notice")], ("escalate", "TERM-E2"),
               "Shortens the institution's termination notice from 30 to 10 days."),
        Change("§14.3 Termination for Convenience",
               [I("Institution may terminate this Agreement for convenience at any time, and Sponsor’s payment obligations end on the termination date.")],
               "termination",
               [("termination_for_convenience", "true", "terminate this Agreement for convenience"),
                ("pays_noncancellable_costs", "false", "Sponsor’s payment obligations end on the termination date")],
               ("escalate", "TERM-E1"), "Adds termination for convenience with no payment for non-cancellable costs.", mark="ins"),
        Change("§14.5 Loss of Investigator",
               [T("Institution may terminate "), D("immediately on"), I("on thirty (30) days’"),
                T(" written notice if the Principal Investigator leaves and no successor is approved.")], "termination",
               [("site_notice_days", "30", "on thirty (30) days’ written notice")], ("accept", "TERM-A0"),
               "Replaces immediate termination with 30 days' notice."),
        Change("§14.6 After Enrollment Closes",
               [T("Institution may terminate on "), D("sixty"), I("thirty"), T(" (60) days’ written notice once enrollment closes.")],
               "termination",
               [("site_notice_days", "30", "thirty (60) days’ written notice"), ("site_notice_days", "60", "thirty (60) days’ written notice")],
               ("human_review", "SYS-CONFLICT"), "The words and the digits give different notice periods.", confidence=0.84),
        Change("§14.7 Subject Follow-up",
               [T("After termination, Institution shall give "), D("thirty (30)"), I("forty-five (45)"),
                T(" days’ notice before it stops following enrolled subjects.")], "termination",
               # Deliberately paraphrased, so quote verification sends it to human review
               [("site_notice_days", "45", "forty five days of notice")], ("human_review", "SYS-QUOTE"),
               "Extends the notice before follow-up ends from 30 to 45 days.", confidence=0.9),
        Change("§17.1 Governing Law and Venue",
               [T("This Agreement is governed by the laws of the State of "), D("New Jersey"), I("Oklahoma"), T(", with venue in its state courts.")],
               "governing_law",
               [("governing_law_state", "Oklahoma", "governed by the laws of the State of Oklahoma"),
                ("institution_is_public", "false", PRIVATE)], ("escalate", "GOV-E2"),
               "Switches to Oklahoma law for a private institution."),
    ]),
    Sample("29", "governing_law", "governing-law", "Cardinal Plains State University Medical Center", "Lincoln, NE",
           "a public institution of the State of Nebraska", "Office of General Counsel (Site 29)", (40, 24, 12000), "elevated", [
        Change("§9.1 Indemnification by Sponsor",
               [T("Sponsor shall indemnify and hold harmless Institution from claims arising from the Study Drug or the Protocol, except to the extent caused by the negligence "),
                I("or willful misconduct "), T("of Institution.")], "indemnification",
               [("carve_out_standard", "negligence", "negligence or willful misconduct of Institution")], ("accept", "IND-A1"),
               "Keeps the negligence carve-out and adds willful misconduct."),
        Change("§14.2 Termination by Institution", _site_notice("fifty (50)"), "termination",
               [("site_notice_days", "50", "fifty (50) days’ written notice")], ("accept", "TERM-A1"),
               "Extends the institution's termination notice from 30 to 50 days."),
        Change("§17.1 Governing Law and Venue",
               [T("This Agreement is governed by the laws of the State of "), D("New Jersey, with venue in its state courts"),
                I("Nebraska, with exclusive venue in the district courts of Lancaster County"), T(".")], "governing_law",
               [("governing_law_state", "Nebraska", "governed by the laws of the State of Nebraska"),
                ("venue", "site_courts_exclusive", "exclusive venue in the district courts of Lancaster County"),
                ("institution_is_public", "true", "a public institution of the State of Nebraska")], ("counter", "GOV-F1"),
               "Switches to Nebraska law with exclusive venue in the institution's county courts."),
        Change("§17.2 Sovereign Immunity",
               [I("Nothing in this Agreement waives Institution’s sovereign immunity, and Sponsor shall accept Institution’s statutory limits on liability as a condition of this Agreement.")],
               "governing_law", [("sovereign_immunity_waiver_required", "true", "Sponsor shall accept Institution’s statutory limits on liability")],
               ("escalate", "GOV-E1"), "Makes the sponsor accept the institution's sovereign immunity terms.", mark="ins"),
        Change("§17.3 Dispute Resolution",
               [I("Any dispute under this Agreement shall be resolved by binding arbitration seated in Geneva, Switzerland.")],
               "governing_law", [("arbitration_abroad", "true", "binding arbitration seated in Geneva, Switzerland")],
               ("escalate", "GOV-E1"), "Adds mandatory arbitration abroad.", mark="ins"),
        Change("§17.5 Public Records",
               [I("Sponsor acknowledges that this Agreement and its budget are public records that Institution may disclose under Nebraska law.")],
               "governing_law", [], ("human_review", "SYS-NOVEL"), "Adds a public-records disclosure right.", confidence=0.9, mark="ins",
               novel="Lets Institution disclose the agreement and budget as public records; the playbook has no public-records term."),
        Change("§17.6 Headings",
               [T("Section headings are for convenience "), D("only,"), I("only"), T(" and do not affect interpretation.")],
               "governing_law", [("no_substantive_change", "true", "headings are for convenience only")],
               ("accept", "SYS-COSMETIC"), "Punctuation fix only."),
    ]),
]


def blocks(s: Sample) -> list[Block]:
    """The form agreement (cta_base) with this sample's changes, each signed by the site's author."""
    site = Site(s.number, s.name, s.city, s.status, *s.enrollment)
    edits = [
        (c.section,
         [seg if seg["type"] == "text" else {**seg, "author": s.author, "date": DATE} for seg in c.segments],
         (s.author, c.comment) if c.comment else None,
         (c.mark, s.author) if c.mark else None)
        for c in s.changes
    ]
    return agreement_blocks(site, edits, "This document is fictional and was written for Siteline tests and demos.")


def sample_bytes(s: Sample) -> bytes:
    return build_redline(blocks(s), f"NSO-417 CTA, Site {s.number} redline")


def matched(s: Sample, parsed: dict) -> list[tuple[dict, Change]]:
    """Each parsed change with the sample change it came from, in document order."""
    by_section = {c.section: c for c in s.changes}
    pairs = [(ch, by_section[ch["section"]]) for ch in parsed["changes"]]
    if sorted(c.section for _, c in pairs) != sorted(by_section):
        raise ValueError(f"Site {s.number}: parsed changes do not match the sample's sections")
    return pairs


def seed_entries() -> dict[str, dict]:
    """Extraction-cache entries for every sample: one per change, plus the whole-agreement figures."""
    from siteline.demo_cache import _figures
    from siteline.extraction import cache_key, doc_cache_key
    from siteline.cta_base import enrollment_sentence, payment_sentence
    from siteline.priority import document_text

    out: dict[str, dict] = {}
    for s in SAMPLES:
        parsed = parse_docx(sample_bytes(s))
        out.update({cache_key(ch): c.seed() for ch, c in matched(s, parsed)})
        subjects, months, usd = s.enrollment
        fig = {"targetSubjects": subjects, "months": months, "perPatientUsd": usd}
        out[doc_cache_key(document_text(parsed))] = _figures(
            str(subjects), str(months), str(usd), enrollment_sentence(fig), payment_sentence(fig))
    return out


def write_samples() -> list[str]:
    from siteline.extraction import store_cache

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for s in SAMPLES:
        s.path.write_bytes(sample_bytes(s))
    store_cache(seed_entries(), seed=True)
    return [str(s.path) for s in SAMPLES]
