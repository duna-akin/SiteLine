"""The sponsor's full form Clinical Trial Agreement for NSO-417, shared by every generated redline.

The Site 07 demo, the nine sample redlines and the seeded inbound emails are all this form with a
site's tracked changes applied, so each one reads as a whole agreement: key terms, recitals, every
article, the signature page and the exhibits.

All text is written for this project. It is not real contract language and comes from no real
sponsor, site or agreement (PRD clean-room rule).

The first paragraph of a section is its operative text. A site's edit to a section replaces that
paragraph (or, for a whole new paragraph, follows the section's text). An edit that names a
different section under the same number (a site's own §11.3, say) replaces the form's section.
Changes are cached by section heading and text (extraction.cache_key), so edits keep their own
headings and wording exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (style, segments, comment (author, text) | None, paragraph mark (kind, author) | None)
Block = tuple[str, list[dict], tuple[str, str] | None, tuple[str, str] | None]
# (section heading, segments, comment (author, text) | None, paragraph mark (kind, author) | None)
Edit = tuple[str, list[dict], tuple[str, str] | None, tuple[str, str] | None]

SPONSOR = "Northstar Oncology, Inc."
PRIVATE = "a private, non-profit corporation"


@dataclass(frozen=True)
class Site:
    number: str
    name: str
    city: str
    status: str  # how the preamble describes the institution
    # Enrollment figures for the key terms; None leaves them out (priority then reads as unknown)
    subjects: int | None = None
    months: int | None = None
    usd_per_subject: int | None = None


def enrollment_sentence(fig: dict) -> str:
    return f"Enrollment: Institution will use reasonable efforts to enroll {fig['targetSubjects']} subjects over an enrollment period of {fig['months']} months."


def payment_sentence(fig: dict) -> str:
    return f"Per-patient payment: Sponsor will pay Institution USD {fig['perPatientUsd']:,} per enrolled subject, as set out in Exhibit B."


RECITALS = [
    "WHEREAS, Sponsor is developing NSO-417, an investigational oral inhibitor for the treatment of relapsed solid "
    "tumors (the “Study Drug”), and has designed a clinical study of the Study Drug described in the protocol "
    "identified above, as amended from time to time (the “Protocol”);",
    "WHEREAS, Institution has the facilities, personnel and experience needed to conduct the study at its site, and "
    "the Principal Investigator is a member of Institution’s staff who has agreed to lead the study there (the “Study”);",
    "WHEREAS, the parties wish to set out the terms on which Institution will conduct the Study and Sponsor will "
    "support it;",
    "NOW, THEREFORE, in consideration of the mutual promises below, the parties agree as follows.",
]

# (article, [(section heading, [paragraphs])]); a section's first paragraph is its operative text
ARTICLES: list[tuple[str, list[tuple[str, list[str]]]]] = [
    ("Article 1. Definitions", [
        ("§1.1 Defined Terms", [
            "Capitalized terms used in this Agreement have the meanings given in this Article 1 or where they are "
            "first defined in the text.",
            "“Applicable Law” means all laws, regulations and binding guidance that apply to the Study, including "
            "those governing clinical research, the protection of human subjects, data privacy and anti-corruption.",
            "“Confidential Information” means all non-public information disclosed by or for Sponsor in connection "
            "with the Study, including the Protocol, the Investigator’s Brochure and the Study Drug, whether "
            "disclosed in writing, orally or by observation.",
            "“IRB” means the institutional review board or independent ethics committee responsible for reviewing "
            "the Study at Institution.",
            "“Principal Investigator” means the physician named in Exhibit A who is responsible for the conduct of "
            "the Study at Institution.",
            "“Study Data” means all data recorded on case report forms or in the electronic data capture system for "
            "the Study, and all reports Institution is required to deliver under the Protocol.",
            "“Study Injury” means an illness or injury to a Study Subject that is directly caused by the Study Drug "
            "or by a procedure required by the Protocol that the Study Subject would not have undergone but for "
            "participation in the Study.",
            "“Study Subject” means an individual who has signed the informed consent form for the Study and been "
            "enrolled at Institution.",
        ]),
        ("§1.2 Interpretation", [
            "In this Agreement, “including” means “including without limitation”, a reference to a Section or "
            "Exhibit is to a section of or exhibit to this Agreement, and a reference to a law includes that law "
            "as amended.",
        ]),
    ]),
    ("Article 2. Conduct of the Study", [
        ("§2.1 Standard of Performance", [
            "Institution shall conduct the Study in accordance with this Agreement, the Protocol, the written "
            "instructions of Sponsor that are consistent with the Protocol, Good Clinical Practice and Applicable Law.",
            "If a term of this Agreement conflicts with the Protocol, this Agreement governs on legal and financial "
            "matters and the Protocol governs on matters of medical and scientific conduct.",
        ]),
        ("§2.2 Protocol Amendments", [
            "Sponsor may amend the Protocol at any time. Institution shall implement an amendment only after the "
            "IRB has approved it, except where a change is necessary to remove an immediate hazard to a Study Subject.",
            "If an amendment materially increases the work required of Institution, the parties shall negotiate "
            "in good faith an adjustment to the budget.",
        ]),
        ("§2.3 Enrollment", [
            "Institution shall use reasonable efforts to enroll the number of Study Subjects stated in the Key Terms "
            "within the enrollment period. Sponsor may close enrollment at any time, including when the target for "
            "the Study as a whole has been reached, by written notice to Institution.",
            "Institution shall enroll only individuals who meet the eligibility criteria of the Protocol. Sponsor "
            "will not pay for a Study Subject enrolled in violation of those criteria unless Sponsor approved the "
            "enrollment in writing in advance.",
        ]),
        ("§2.4 Informed Consent", [
            "Before any Study procedure is performed, Institution shall obtain the written informed consent of each "
            "Study Subject, or of the subject’s legally authorized representative, on the form approved by the IRB.",
        ]),
        ("§2.5 Recruitment Materials", [
            "Institution shall use only recruitment materials that Sponsor has reviewed and the IRB has approved.",
        ]),
    ]),
    ("Article 3. Principal Investigator and Study Staff", [
        ("§3.1 Responsibilities", [
            "Institution shall cause the Principal Investigator to supervise the conduct of the Study at Institution "
            "and to ensure that all persons assisting with the Study are qualified and properly delegated.",
        ]),
        ("§3.2 Replacement", [
            "If the Principal Investigator becomes unable or unwilling to continue, Institution shall notify Sponsor "
            "within ten (10) business days and may propose a qualified successor. The successor shall serve only "
            "with Sponsor’s written approval, which Sponsor shall not unreasonably withhold.",
        ]),
        ("§3.3 Training", [
            "Institution shall ensure that the Principal Investigator and Study staff complete the Protocol and "
            "Good Clinical Practice training that Sponsor reasonably requires before they perform Study procedures.",
        ]),
    ]),
    ("Article 4. Regulatory Compliance and Subject Safety", [
        ("§4.1 IRB Approval", [
            "Institution shall not begin the Study until the IRB has approved the Protocol and the informed consent "
            "form, and shall keep IRB approval in effect for the duration of the Study.",
        ]),
        ("§4.2 Safety Reporting", [
            "Institution shall report each serious adverse event to Sponsor within twenty-four (24) hours of learning "
            "of it, as required by the Protocol, and shall report to the IRB as the IRB’s policies require.",
            "Sponsor shall promptly inform Institution of any finding that could adversely affect the safety of "
            "Study Subjects or their willingness to continue in the Study.",
        ]),
        ("§4.3 Regulatory Inspections", [
            "Institution shall notify Sponsor within two (2) business days of any inspection or inquiry by a "
            "regulatory authority that relates to the Study, and shall give Sponsor the opportunity to assist in "
            "preparing for it.",
        ]),
    ]),
    ("Article 5. Study Drug and Materials", [
        ("§5.1 Supply", [
            "Sponsor shall supply the Study Drug and any comparator at no cost to Institution or Study Subjects, in "
            "quantities sufficient to conduct the Study.",
        ]),
        ("§5.2 Storage and Accountability", [
            "Institution shall store the Study Drug under the conditions stated in the Protocol, keep accurate "
            "dispensing records, and use the Study Drug only for the Study.",
        ]),
        ("§5.3 Return or Destruction", [
            "At the end of the Study, Institution shall return or destroy unused Study Drug as Sponsor directs in "
            "writing, at Sponsor’s expense.",
        ]),
        ("§5.4 Loaned Equipment", [
            "Any equipment Sponsor provides for the Study remains Sponsor’s property. Institution shall use it only "
            "for the Study and return it at the end of the Study in the condition received, less normal wear.",
        ]),
    ]),
    ("Article 6. Payment", [
        ("§6.1 Budget", [
            "Sponsor shall pay Institution in accordance with the budget attached as Exhibit B.",
            "The amounts in Exhibit B are the full compensation for the work required by the Protocol, including "
            "Institution’s indirect costs.",
        ]),
        ("§6.2 Invoices", [
            "Sponsor shall pay each undisputed invoice within forty-five (45) days of receipt, with quarterly reconciliation.",
            "Payments for completed subject visits are calculated from the Study Data entered in the electronic data "
            "capture system; Institution invoices separately for the items in Exhibit B marked as invoiceable.",
        ]),
        ("§6.3 Start-up Fee", [
            "Sponsor shall pay a non-refundable start-up fee equal to ten percent (10%) of the study budget.",
            "The start-up fee is payable on execution of this Agreement and covers IRB preparation, contract and "
            "budget review, pharmacy set-up and site initiation.",
        ]),
        ("§6.4 Pass-Through Costs", [
            "Sponsor shall reimburse IRB fees and other pass-through costs listed in Exhibit B at cost, against "
            "receipts.",
        ]),
        ("§6.5 Final Payment", [
            "Sponsor shall make the final payment after all Study Data have been received, all queries resolved and "
            "all Study Drug reconciled.",
        ]),
        ("§6.6 Payee and Taxes", [
            "All payments shall be made to Institution at the address in Exhibit B. Each party is responsible for "
            "its own taxes.",
        ]),
    ]),
    ("Article 7. Records, Monitoring and Audit", [
        ("§7.1 Study Records", [
            "Institution shall maintain complete and accurate source documents and Study records as required by the "
            "Protocol and Applicable Law.",
        ]),
        ("§7.2 Record Retention", [
            "Institution shall retain Study records for the longer of two (2) years after the last marketing "
            "approval of the Study Drug or two (2) years after Sponsor notifies Institution that development has "
            "been discontinued, or longer if Applicable Law requires.",
        ]),
        ("§7.3 Monitoring and Audit", [
            "During normal business hours and on reasonable notice, Institution shall permit Sponsor’s monitors and "
            "auditors to visit the site, review Study records and source documents, and meet with Study staff.",
        ]),
    ]),
    ("Article 8. Confidentiality", [
        ("§8.1 Confidential Information", [
            "Institution shall hold Sponsor’s Confidential Information in confidence and use it only to conduct the Study.",
            "Institution may disclose Confidential Information only to its employees and agents who need to know it "
            "for the Study and who are bound by obligations of confidentiality at least as protective as these.",
        ]),
        ("§8.2 Permitted Disclosures", [
            "These obligations do not apply to information that is or becomes public through no fault of "
            "Institution, was known to Institution before disclosure, is independently developed without use of "
            "Confidential Information, or is received from a third party without restriction.",
            "Institution may disclose Confidential Information to the extent required by law or court order, after "
            "giving Sponsor prompt notice and a reasonable opportunity to seek protective treatment.",
        ]),
        ("§8.3 Disclosures to Subjects and the IRB", [
            "Nothing in this Article prevents Institution from disclosing information to the IRB, or to a Study "
            "Subject where needed for the subject’s informed consent or medical care.",
        ]),
        ("§8.4 Term of Confidentiality", [
            "The obligations in this Section 8 survive for seven (7) years after study close.",
        ]),
        ("§8.5 Return of Confidential Information", [
            "On Sponsor’s request at the end of the Study, Institution shall return or destroy Confidential "
            "Information, except for one archival copy and records it must retain under Article 7.",
        ]),
    ]),
    ("Article 9. Indemnification", [
        ("§9.1 Indemnification by Sponsor", [
            "Sponsor shall indemnify and hold harmless Institution from claims arising from the Study Drug or the "
            "Protocol, except to the extent caused by the negligence of Institution.",
        ]),
        ("§9.2 Indemnified Persons", [
            "Sponsor’s obligations under Section 9.1 extend to Institution’s trustees, officers, employees, the "
            "Principal Investigator and Study staff, and the IRB.",
        ]),
        ("§9.3 Indemnification Procedures", [
            "A party seeking indemnification shall notify the indemnifying party promptly of the claim, allow it to "
            "control the defense and settlement, and cooperate in the defense at the indemnifying party’s expense. "
            "No settlement admitting fault of an indemnified party may be made without that party’s consent.",
        ]),
        ("§9.4 Limitation of Liability", [
            "Neither party is liable to the other for indirect, special or consequential damages arising from this "
            "Agreement, except for claims under this Article 9 or a breach of Article 8.",
        ]),
    ]),
    ("Article 10. Subject Injury", [
        ("§10.1 Medical Care", [
            "If a Study Subject suffers a Study Injury, Institution shall provide or arrange for appropriate medical "
            "care, and the Principal Investigator shall report the injury to Sponsor.",
        ]),
        ("§10.2 Subject Injury Reimbursement", [
            "Sponsor shall reimburse reasonable and necessary medical expenses incurred by a Study Subject for the "
            "diagnosis and treatment of a Study Injury.",
        ]),
        ("§10.3 Exclusions", [
            "Sponsor is not obligated to reimburse expenses for an injury caused by the underlying disease, by "
            "standard-of-care treatment, or by a failure of Institution or the Study Subject to follow the Protocol.",
        ]),
        ("§10.4 Coordination of Benefits", [
            "Reimbursement is net of amounts paid by the subject’s insurance.",
        ]),
    ]),
    ("Article 11. Data Protection", [
        ("§11.1 Coded Data", [
            "Institution shall provide Study data to Sponsor in coded form only.",
            "Institution shall keep the key linking codes to Study Subjects’ identities and shall not disclose it to "
            "Sponsor, except as needed for safety reporting or as required by Applicable Law.",
        ]),
        ("§11.2 HIPAA Authorization", [
            "Institution shall obtain each subject’s HIPAA authorization before collecting Study data.",
        ]),
        ("§11.3 Privacy Laws", [
            "Each party shall comply with the privacy and data-protection laws that apply to it in connection with "
            "the Study.",
        ]),
        ("§11.4 Use of Study Data", [
            "Sponsor may use Study Data for the Study, for regulatory submissions and for the further development "
            "of the Study Drug, consistent with the informed consent and authorization signed by each Study Subject.",
        ]),
    ]),
    ("Article 12. Publication", [
        ("§12.1 Sponsor Review", [
            "Institution shall provide Sponsor sixty (60) days to review any proposed publication.",
            "Institution shall delete Sponsor’s Confidential Information (other than Study results) from a proposed "
            "publication on Sponsor’s request, and shall consider Sponsor’s other comments in good faith.",
        ]),
        ("§12.2 Multi-site Publication", [
            "Institution shall not publish results from its site before the first multi-site publication of the "
            "Study, or eighteen (18) months after the Study ends at all sites, whichever is earlier.",
        ]),
        ("§12.3 Patent Delay", [
            "At Sponsor’s request, Institution shall delay publication up to an additional sixty (60) days to permit patent filings.",
        ]),
        ("§12.4 Registration and Results", [
            "Sponsor shall register the Study and post its results in public registries as required by Applicable Law.",
        ]),
    ]),
    ("Article 13. Intellectual Property", [
        ("§13.1 Background IP", [
            "Each party retains ownership of its background intellectual property.",
        ]),
        ("§13.2 Study Inventions", [
            "All inventions arising from the Protocol or Study Drug shall belong to Sponsor.",
            "Institution shall promptly disclose any such invention to Sponsor and, at Sponsor’s expense, provide the "
            "assistance Sponsor reasonably needs to protect it.",
        ]),
        ("§13.3 No Implied License", [
            "Except as expressly stated in this Agreement, no license under any patent or other intellectual property "
            "is granted by either party.",
        ]),
    ]),
    ("Article 14. Term and Termination", [
        ("§14.1 Termination by Sponsor", [
            "Sponsor may terminate this Agreement on thirty (30) days’ written notice and shall pay for work completed.",
            "Sponsor may terminate this Agreement immediately if the safety of Study Subjects requires it or a "
            "regulatory authority halts the Study.",
        ]),
        ("§14.2 Termination by Institution", [
            "Institution may terminate this Agreement on thirty (30) days’ written notice.",
        ]),
        ("§14.3 Effect of Termination", [
            "On termination, Institution shall stop enrolling Study Subjects, transition enrolled Study Subjects to "
            "appropriate care consistent with their safety, and deliver all Study Data. Sponsor shall pay for work "
            "properly performed and non-cancellable obligations incurred before the termination date.",
        ]),
        ("§14.4 Survival", [
            "Articles 7 through 13, Section 14.3 and Article 17 survive the expiration or termination of this Agreement.",
        ]),
    ]),
    ("Article 15. Insurance", [
        ("§15.1 Sponsor Insurance", [
            "Sponsor shall maintain clinical trial liability insurance with limits of at least five million US dollars "
            "(USD 5,000,000) per occurrence for the duration of the Study and three (3) years after.",
        ]),
        ("§15.2 Institution Insurance", [
            "Institution shall maintain professional liability insurance, or a program of self-insurance, adequate to "
            "cover its obligations under this Agreement.",
        ]),
    ]),
    ("Article 16. Compliance", [
        ("§16.1 Debarment", [
            "Institution represents that neither it nor any person working on the Study is debarred or excluded from "
            "federal health care programs, and shall notify Sponsor immediately if that changes.",
        ]),
        ("§16.2 Anti-Corruption", [
            "Neither party shall offer or pay anything of value to improperly influence any person in connection with "
            "the Study. Payments under this Agreement reflect fair market value for the work performed and are not "
            "conditioned on the prescription or purchase of any product.",
        ]),
        ("§16.3 Financial Disclosure", [
            "Institution shall cause the Principal Investigator and sub-investigators to provide the financial "
            "disclosure information Sponsor needs for its regulatory filings, and to update it during the Study and "
            "for one (1) year after.",
        ]),
    ]),
    ("Article 17. General", [
        ("§17.1 Governing Law and Venue", [
            "This Agreement is governed by the laws of the State of New Jersey, with venue in its state courts.",
        ]),
        ("§17.2 Notices", [
            "Notices under this Agreement shall be in writing and delivered by hand, by courier or by email with "
            "confirmation of receipt, to the addresses on the signature page.",
        ]),
        ("§17.3 Independent Contractors", [
            "The parties are independent contractors. Nothing in this Agreement creates a partnership, joint venture "
            "or agency between them.",
        ]),
        ("§17.4 Entire Agreement", [
            "This Agreement and its exhibits are the entire agreement of the parties regarding the Study.",
            "This Agreement may be amended only in a writing signed by both parties.",
        ]),
        ("§17.5 Use of Names", [
            "Neither party shall use the name or marks of the other in any publicity or advertising without its "
            "prior written consent, except that Sponsor may disclose Institution’s participation in the Study as "
            "required by law or in public registries.",
        ]),
        ("§17.6 Assignment", [
            "Neither party may assign this Agreement without the other’s written consent, except that Sponsor may "
            "assign it to an affiliate or to a successor to the Study Drug program on written notice.",
        ]),
        ("§17.7 Counterparts", [
            "This Agreement may be signed in counterparts and by electronic signature, each of which is an original.",
        ]),
    ]),
]

SIGNATURES = [
    "IN WITNESS WHEREOF, the parties have caused this Agreement to be signed by their authorized representatives.",
    "NORTHSTAR ONCOLOGY, INC.",
    "By: ______________________   Name: ______________________   Title: ______________________   Date: __________",
    "INSTITUTION",
    "By: ______________________   Name: ______________________   Title: ______________________   Date: __________",
    "Read and understood by the Principal Investigator:",
    "Signature: ______________________   Date: __________",
]


def _exhibits(site: Site) -> list[tuple[str, list[str]]]:
    fee = f"USD {site.usd_per_subject:,}" if site.usd_per_subject else "USD [amount]"
    return [
        ("Exhibit A. Study Summary", [
            "Protocol: NSO-417-201, a Phase II, open-label, multi-center study of NSO-417 in adults with relapsed "
            "solid tumors.",
            "Study Drug: NSO-417 tablets, supplied by Sponsor.",
            f"Site: {site.name}, {site.city}.",
            "Principal Investigator: to be named by Institution before site initiation.",
            "Planned duration of subject participation: up to twenty-four (24) months of treatment, followed by "
            "survival follow-up every three (3) months.",
        ]),
        ("Exhibit B. Budget and Payment Schedule", [
            f"Per-subject fee: {fee} for each Study Subject who completes all Protocol visits, prorated by completed "
            "visit as follows.",
            "Screening visit: 8% of the per-subject fee. Treatment visits (cycles 1–6): 60%, paid by completed cycle. "
            "Treatment visits (cycle 7 onward): 22%. End-of-treatment and safety follow-up: 10%.",
            "Screen failures: reimbursed at the screening-visit amount, up to one (1) screen failure for every "
            "three (3) Study Subjects enrolled.",
            "Invoiceable items: IRB initial review and continuing review fees at cost; pharmacy set-up; archiving; "
            "unscheduled visits and additional imaging when required by the Protocol.",
            "Payee: Institution’s Office of Research Finance, at the remittance address Institution provides in "
            "writing.",
        ]),
    ]


def _num(section: str) -> tuple[int, int]:
    m = re.match(r"§(\d+)\.(\d+)", section)
    if not m:
        raise ValueError(f"Section needs a §N.N number: {section!r}")
    return int(m.group(1)), int(m.group(2))


def _title(section: str) -> str:
    return re.sub(r"^§\d+\.\d+\s*", "", section)


def agreement_blocks(site: Site, edits: list[Edit], note: str, terms: list[str] | None = None) -> list[Block]:
    """The form agreement for one site, with that site's edits applied in document order.

    `note` is the closing sentence of the preamble that says the document is fictional; `terms`
    replaces the enrollment and payment key terms (the blank form uses placeholders)."""

    def text(t: str) -> list[dict]:
        return [{"type": "text", "text": t}]

    fig = {"targetSubjects": site.subjects, "months": site.months, "perPatientUsd": site.usd_per_subject}
    if terms is None:
        terms = [enrollment_sentence(fig), payment_sentence(fig)] if None not in fig.values() else []
    b: list[Block] = [
        ("Title", text("Clinical Trial Agreement"), None, None),
        ("", text("Protocol NSO-417: Phase II study of NSO-417 in relapsed solid tumors"), None, None),
        ("", text("Sponsor: Northstar Oncology, Inc., Princeton, New Jersey"), None, None),
        ("", text(f"Institution: {site.name}, {site.city}".rstrip(", ")), None, None),
        ("", text(f"Site Number: {site.number}"), None, None),
        *(("", text(t), None, None) for t in terms),
        ("", text(f"This Clinical Trial Agreement is entered into by {SPONSOR} (“Sponsor”) and {site.name}, "
                  f"{site.status} (“Institution”). {note}"), None, None),
        ("Heading1", text("Recitals"), None, None),
        *(("", text(r), None, None) for r in RECITALS),
    ]

    by_num: dict[tuple[int, int], Edit] = {}
    for e in edits:
        n = _num(e[0])
        if n in by_num:
            raise ValueError(f"Two edits for §{n[0]}.{n[1]}: {by_num[n][0]!r} and {e[0]!r}")
        by_num[n] = e
    articles = {_num(sections[0][0])[0] for _, sections in ARTICLES}
    if stray := [e[0] for e in edits if _num(e[0])[0] not in articles]:
        raise ValueError(f"No article for {stray}")

    for article, sections in ARTICLES:
        art = _num(sections[0][0])[0]
        form = {_num(s): (s, paras) for s, paras in sections}
        nums = sorted({*form, *(n for n in by_num if n[0] == art)})
        b.append(("Heading1", text(article), None, None))
        for n in nums:
            edit = by_num.get(n)
            heading, paras = form.get(n, (None, []))
            if edit is None:
                b.append(("Heading2", text(heading), None, None))
                b.extend(("", text(p), None, None) for p in paras)
                continue
            section, segs, comment, mark = edit
            b.append(("Heading2", text(section), None, None))
            if heading is None or _title(heading) != _title(section):
                # The site's own section under this number: it stands in for the form's.
                b.append(("", segs, comment, mark))
            elif mark and mark[0] == "ins":
                # A new paragraph added to the form's section.
                b.extend(("", text(p), None, None) for p in paras)
                b.append(("", segs, comment, mark))
            else:
                # The site's edit to the section's operative paragraph; the rest of the section stands.
                b.append(("", segs, comment, mark))
                b.extend(("", text(p), None, None) for p in paras[1:])

    b.append(("Heading1", text("Signatures"), None, None))
    b.extend(("", text(p), None, None) for p in SIGNATURES)
    for title, paras in _exhibits(site):
        b.append(("Heading1", text(title), None, None))
        b.extend(("", text(p), None, None) for p in paras)
    return b


def form_blocks() -> list[Block]:
    """The blank form, with no site's edits: placeholders where a site's details go."""
    site = Site("[number]", "[Institution]", "[City, State]", "[legal status of Institution]")
    terms = [
        "Enrollment: Institution will use reasonable efforts to enroll [number] subjects over an enrollment period of [number] months.",
        "Per-patient payment: Sponsor will pay Institution USD [amount] per enrolled subject, as set out in Exhibit B.",
    ]
    return agreement_blocks(site, [], "This form is fictional and was written for Siteline demos and tests.", terms)
