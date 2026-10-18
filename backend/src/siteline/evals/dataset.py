"""The labeled eval set: 231 fictional redline changes, each with the outcome a contract
manager would assign under the playbook (about four around each limit of every playbook
position, plus variants).

Every change is generated from templates written for this project (no real contract
text). Labels follow the playbook, not Siteline's rules code, and include cases the rules
do not cover: cosmetic edits (accept), and ambiguous wording or terms the playbook never
mentions (both human review).

After those 231 come 12 escalations judged with the site's history (precedent_items): six
where precedent should turn them into accepts and six where it must not.
"""

from __future__ import annotations

import json
import random

from siteline.config import DATA_DIR

DATASET_PATH = DATA_DIR / "evals" / "labeled_changes.jsonl"
TARGET = 231

_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + (f"-{_ONES[o]}" if o else "")
    h, r = divmod(n, 100)
    return f"{_ONES[h]} hundred" + (f" {words(r)}" if r else "")


def qty(n: int) -> str:
    return f"{words(n)} ({n})"


PUBLIC = "Institution is a public institution of its state."
PRIVATE = "Institution is a private, non-profit corporation."
SITE = "Site (eval)"


def T(t: str) -> dict:
    return {"type": "text", "text": t}


def I(t: str) -> dict:  # noqa: E743
    return {"type": "ins", "text": t, "author": SITE}


def D(t: str) -> dict:
    return {"type": "del", "text": t, "author": SITE}


def item(section: str, clause: str, segments: list[dict], gold: str, note: str, comment: str | None = None,
         mark: str | None = None, context: str = PUBLIC) -> dict:
    return {"section": section, "clause_type": clause, "segments": segments, "gold": gold, "note": note,
            "comment": comment, "mark": mark, "context": context}


def repl(section: str, clause: str, before: str, old: str, new: str, after: str, gold: str, note: str, **kw) -> dict:
    return item(section, clause, [T(before), D(old), I(new), T(after)], gold, note, **kw)


def build() -> list[dict]:
    out: list[dict] = []

    # Payment: invoice terms (standard Net 45, fallback Net 30, escalate under 30)
    for n, gold in [(60, "accept"), (50, "accept"), (40, "accept"), (35, "accept"), (30, "accept"),
                    (25, "escalate"), (20, "escalate"), (15, "escalate"), (10, "escalate")]:
        out.append(repl("§6.2 Invoices", "payment_terms", "Sponsor shall pay each undisputed invoice within ",
                        qty(45), qty(n), " days of receipt.", gold, f"Net {n}"))
    # Payment: start-up fee (standard 10%, fallback counter at 10%, escalate above 20% non-refundable)
    for n, gold in [(5, "accept"), (8, "accept"), (12, "counter"), (15, "counter"), (18, "counter"), (20, "counter"),
                    (25, "escalate"), (30, "escalate"), (40, "escalate")]:
        out.append(repl("§6.3 Start-up Fee", "payment_terms", "Sponsor shall pay a non-refundable start-up fee equal to ",
                        f"{words(10)} percent (10%)", f"{words(n)} percent ({n}%)", " of the study budget.", gold, f"fee {n}%"))

    # Confidentiality survival (standard 7, fallback 5, escalate under 3)
    for n, gold in [(10, "accept"), (8, "accept"), (6, "accept"), (5, "accept"), (4, "counter"), (3, "counter"),
                    (2, "escalate"), (1, "escalate")]:
        out.append(repl("§8.4 Term of Confidentiality", "confidentiality", "The obligations in this Section 8 survive for ",
                        qty(7), qty(n), " years after study close.", gold, f"survival {n}y"))
    out.append(item("§8.5 Trade Secrets", "confidentiality",
                    [I("Information that is a trade secret is protected only for the term stated in Section 8.4.")],
                    "escalate", "trade secrets lose perpetual protection", mark="ins"))
    out.append(item("§8.5 Trade Secrets", "confidentiality",
                    [T("Trade secrets remain confidential "), D("for as long as they remain trade secrets"), I("for three (3) years"), T(".")],
                    "escalate", "trade secrets capped at 3 years"))

    # Indemnification
    base = "Sponsor shall indemnify Institution from claims arising from the Study Drug or the Protocol, except to the extent caused by the "
    out.append(repl("§9.1 Indemnification by Sponsor", "indemnification", base, "negligence", "gross negligence or willful misconduct",
                    " of Institution.", "accept", "carve-out narrowed (fallback)"))
    out.append(item("§9.1 Indemnification by Sponsor", "indemnification",
                    [T(base), D("negligence"), I("gross negligence or willful misconduct"), T(" of Institution"), I(", as finally adjudicated by a court"), T(".")],
                    "counter", "gross negligence + adjudication"))
    out.append(item("§9.1 Indemnification by Sponsor", "indemnification",
                    [T("Sponsor shall indemnify Institution from claims arising from the Study Drug or the Protocol"),
                     D(", except to the extent caused by the negligence of Institution"), T(".")],
                    "escalate", "carve-out removed"))
    out.append(item("§9.1 Indemnification by Sponsor", "indemnification",
                    [T(base), D("negligence"), I("intentional fraud"), T(" of Institution.")],
                    "escalate", "carve-out gutted to fraud only"))
    for text in [
        "Each party shall indemnify the other for claims arising from its own acts, and the obligations in this Section 9 are mutual.",
        "Institution’s indemnification of Sponsor shall mirror Sponsor’s indemnification of Institution.",
        "Sponsor shall be indemnified by Institution on the same terms as Section 9.1, so that indemnification is reciprocal.",
    ]:
        out.append(item("§9.3 Mutual Indemnification", "indemnification", [I(text)], "escalate", "mutual indemnity", mark="ins"))

    # Subject injury
    si = "Sponsor shall reimburse reasonable and necessary medical expenses"
    tail = " incurred by a Study Subject for a Study Injury."
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(", lost wages"), T(tail)], "escalate", "lost wages"))
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(" and compensation for pain and suffering"), T(tail)], "escalate", "pain and suffering"))
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(", without any cap or limit,"), T(tail)], "escalate", "uncapped"))
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(", including income lost while recovering,"), T(tail)], "escalate", "lost income, reworded"))
    out.append(item("§10.4 Coordination of Benefits", "subject_injury",
                    [D("Reimbursement is net of amounts paid by the subject’s insurance.")], "accept", "sponsor pays first (fallback)", mark="del"))
    out.append(item("§10.4 Coordination of Benefits", "subject_injury",
                    [T("Sponsor shall pay "), I("first, "), T("without "), D("first "), T("seeking payment from the subject’s insurer.")],
                    "accept", "sponsor pays first, reordered"))
    out.append(repl("§10.2 Subject Injury", "subject_injury", "Sponsor shall reimburse reasonable and necessary medical expenses ",
                    "incurred", "actually incurred and documented", " by a Study Subject for a Study Injury.", "accept", "narrows in sponsor's favor"))

    # Publication review (standard 60, fallback up to 75, escalate under 30 or patent delay removed)
    for n, gold in [(90, "accept"), (75, "accept"), (70, "accept"), (50, "counter"), (45, "counter"), (40, "counter"), (30, "counter"),
                    (25, "escalate"), (20, "escalate"), (14, "escalate")]:
        out.append(repl("§12.1 Sponsor Review", "publication", "Institution shall provide Sponsor ", qty(60) + " days", qty(n) + " days",
                        " to review any proposed publication.", gold, f"review {n}d"))
    out.append(item("§12.3 Patent Delay", "publication",
                    [D("At Sponsor’s request, Institution shall delay publication up to an additional sixty (60) days to permit patent filings.")],
                    "escalate", "patent delay removed", mark="del"))
    out.append(item("§12.3 Patent Delay", "publication",
                    [T("At Sponsor’s request, Institution shall "), D("delay publication up to an additional sixty (60) days to permit patent filings"),
                     I("consider in good faith any request to delay publication"), T(".")],
                    "escalate", "patent delay made optional"))
    out.append(repl("§12.1 Sponsor Review", "publication", "Institution shall provide Sponsor ", qty(60) + " days", qty(45) + " days, or as otherwise agreed,",
                    " to review any proposed publication.", "escalate", "open-ended qualifier (the playbook escalates an open-ended window)"))
    out.append(repl("§12.1 Sponsor Review", "publication", "Institution shall provide Sponsor ", qty(60) + " days", "a reasonable period",
                    " to review any proposed publication.", "escalate", "undefined review period (the playbook escalates an open-ended window)"))

    # Intellectual property
    ip = "All inventions arising from the Protocol or Study Drug shall "
    out.append(repl("§13.2 Study Inventions", "intellectual_property", ip, "belong to Sponsor", "be jointly owned by Sponsor and Institution", ".", "escalate", "joint ownership"))
    out.append(repl("§13.2 Study Inventions", "intellectual_property", ip, "belong to Sponsor", "belong to Institution", ".", "escalate", "site ownership"))
    out.append(repl("§13.2 Study Inventions", "intellectual_property", "All inventions conceived by Institution personnel ",
                    "shall belong to Sponsor", "shall be owned by the inventing party", ".", "escalate", "inventor-owns"))
    out.append(item("§13.3 Research License", "intellectual_property",
                    [I("Institution retains a non-exclusive, royalty-free license to use Study inventions for internal research and teaching.")],
                    "accept", "research license (fallback)", mark="ins"))
    out.append(item("§13.1 Background IP", "intellectual_property", [T("Each party retains ownership of its background intellectual property.")],
                    "accept", "comment on background IP", comment="Please confirm our existing assay software stays our background IP."))

    # Data privacy
    out.append(item("§11.3 HIPAA", "data_privacy", [I("Sponsor shall sign Institution’s Business Associate Agreement before receiving study data.")],
                    "escalate", "BAA", mark="ins"))
    out.append(item("§11.3 HIPAA", "data_privacy", [I("Sponsor shall act as Institution’s business associate under HIPAA and sign a BAA.")],
                    "escalate", "BAA reworded", mark="ins"))
    out.append(item("§11.4 Secondary Research", "data_privacy", [I("Sponsor shall not use study data for any purpose other than this Study.")],
                    "escalate", "blocks secondary research", mark="ins"))
    out.append(item("§11.4 Secondary Research", "data_privacy",
                    [T("Sponsor may use coded study data "), D("for future research"), I("only for this Protocol"), T(".")],
                    "escalate", "secondary use removed"))
    out.append(item("§11.6 Data Use Addendum", "data_privacy",
                    [I("Sponsor shall sign a limited data-use addendum covering coded data received under this Agreement.")],
                    "accept", "data-use addendum (fallback)", mark="ins"))

    # Termination (standard 30, fallback 60 for site, escalate convenience without costs)
    for n, gold in [(30, "accept"), (45, "accept"), (60, "accept"), (90, "counter"), (120, "counter"), (15, "escalate"), (10, "escalate")]:
        old = 45 if n == 30 else 30
        out.append(repl("§14.2 Termination by Institution", "termination", "Institution may terminate this Agreement on ", qty(old), qty(n),
                        " days’ written notice.", gold, f"site notice {n}d"))
    out.append(item("§14.3 Termination for Convenience", "termination",
                    [I("Institution may terminate this Agreement for convenience at any time, and Sponsor shall have no claim to non-cancellable costs.")],
                    "escalate", "convenience without costs", mark="ins"))
    out.append(item("§14.3 Termination for Convenience", "termination",
                    [I("Institution may terminate for convenience on sixty (60) days’ notice; Sponsor shall pay for work completed and non-cancellable costs.")],
                    "accept", "convenience with costs", mark="ins"))

    # Governing law (standard NJ law and venue; fallback silent venue or public site's state)
    gl = "This Agreement is governed by the laws of the State of "
    out.append(repl("§17.1 Governing Law", "governing_law", gl, "New Jersey, with venue in its state courts", "Ohio", ".", "accept",
                    "public site's state, silent venue", context=PUBLIC))
    out.append(repl("§17.1 Governing Law", "governing_law", gl, "New Jersey, with venue in its state courts", "Ohio, with exclusive venue in Franklin County", ".",
                    "counter", "exclusive venue", context=PUBLIC))
    out.append(repl("§17.1 Governing Law", "governing_law", gl, "New Jersey, with venue in its state courts", "New Jersey", ".", "accept", "venue dropped"))
    out.append(repl("§17.1 Governing Law", "governing_law", gl, "New Jersey, with venue in its state courts", "Massachusetts", ".", "escalate",
                    "private site's state", context=PRIVATE))
    out.append(item("§17.2 Disputes", "governing_law", [I("All disputes shall be resolved by binding arbitration seated in London, England.")],
                    "escalate", "arbitration abroad", mark="ins"))
    out.append(item("§17.3 Sovereign Immunity", "governing_law",
                    [I("Sponsor acknowledges that Institution does not waive sovereign immunity and Sponsor waives any claim inconsistent with it.")],
                    "escalate", "sovereign immunity demand", mark="ins"))

    # Payment: institutional overhead (standard 25% of direct costs, counter above 25 up to 30, escalate above 30)
    for n, gold in [(20, "accept"), (25, "accept"), (26, "counter"), (30, "counter"), (31, "escalate"), (35, "escalate")]:
        old = 20 if n == 25 else 25
        out.append(repl("§6.7 Indirect Costs", "payment_terms", "Sponsor shall pay Institution’s indirect costs at ",
                        f"{words(old)} percent ({old}%)", f"{words(n)} percent ({n}%)", " of direct costs, included in the per-subject fees in Exhibit B.",
                        gold, f"overhead {n}%"))
    out.append(item("§6.7 Indirect Costs", "payment_terms",
                    [I("Institution’s facilities and administrative rate of twenty-eight percent (28%) applies to all direct costs in Exhibit B.")],
                    "counter", "overhead 28%, reworded", mark="ins"))

    # Payment: holdback (10% withheld to database lock; under 5% or deleted: restore the form)
    hb = "Sponsor shall withhold "
    hb_tail = " of each payment until database lock and the resolution of all queries."
    for n, gold in [(5, "accept"), (8, "accept"), (4, "counter"), (2, "counter")]:
        out.append(repl("§6.5 Holdback", "payment_terms", hb, f"{words(10)} percent (10%)", f"{words(n)} percent ({n}%)", hb_tail,
                        gold, f"holdback {n}%"))
    out.append(item("§6.5 Holdback", "payment_terms", [D(hb + f"{words(10)} percent (10%)" + hb_tail)], "counter", "holdback deleted", mark="del"))

    # Payment: screen failures (up to 1 per 3 enrolled; counter up to 1 per 2; escalate above 1 per 2 or uncapped)
    sf = "Sponsor shall pay for screen failures at the screening-visit rate, up to "
    sf_tail = " enrolled Study Subjects."
    sf_old = "one (1) screen failure for every three (3)"
    for new, gold, note in [("one (1) screen failure for every four (4)", "accept", "screen failures 1 per 4"),
                            ("one (1) screen failure for every two (2)", "counter", "screen failures 1 per 2"),
                            ("two (2) screen failures for every three (3)", "escalate", "screen failures 2 per 3"),
                            ("one (1) screen failure for every one (1)", "escalate", "screen failures 1 per 1")]:
        out.append(repl("§6.8 Screen Failures", "payment_terms", sf, sf_old, new, sf_tail, gold, note))
    out.append(item("§6.8 Screen Failures", "payment_terms",
                    [T("Sponsor shall pay for "), I("every "), T("screen failure"), D("s"), T(" at the screening-visit rate"),
                     D(", up to " + sf_old + sf_tail.rstrip(".")), I(", without limit"), T(".")],
                    "escalate", "screen failures uncapped"))

    # Confidentiality: disclosure to affiliates (employees and agents who need to know; wider: restore the form)
    cf = "Institution may disclose Confidential Information only to its "
    cf_tail = " for the Study and who are bound by obligations of confidentiality at least as protective as these."
    out.append(repl("§8.1 Confidential Information", "confidentiality", cf, "employees and agents who need to know it",
                    "employees, agents and affiliates who need to know it", cf_tail, "counter", "affiliates added"))
    out.append(repl("§8.1 Confidential Information", "confidentiality", cf, "employees and agents who need to know it",
                    "employees, agents and outside research collaborators who need to know it", cf_tail, "counter", "collaborators added"))
    out.append(item("§8.1 Confidential Information", "confidentiality",
                    [I("Institution may also share Confidential Information with its affiliated hospitals for the purposes of the Study.")],
                    "counter", "affiliated hospitals, inserted", mark="ins"))
    out.append(repl("§8.1 Confidential Information", "confidentiality", cf + "employees and agents who ", "need to know it", "have a need to know it",
                    cf_tail, "accept", "wording, scope unchanged"))

    # Confidentiality: marking requirement (all information protected; limited to marked: restore the form)
    ci = "“Confidential Information” means all non-public information disclosed by or for Sponsor in connection with the Study"
    out.append(item("§1.1 Defined Terms", "confidentiality",
                    [T(ci + ", "), D("whether disclosed in writing, orally or by observation"), I("if marked “confidential” when disclosed"), T(".")],
                    "counter", "marking required"))
    out.append(item("§1.1 Defined Terms", "confidentiality",
                    [T(ci + ", "), D("whether disclosed in writing, orally or by observation"),
                     I("if disclosed in writing and marked confidential, or if disclosed orally and summarized in writing within thirty (30) days"), T(".")],
                    "counter", "marking or written summary required"))
    out.append(item("§1.1 Defined Terms", "confidentiality",
                    [T(ci + ", whether disclosed in writing, orally or by observation"),
                     I(", but only to the extent it is identified as confidential at the time of disclosure"), T(".")],
                    "counter", "identification required"))
    out.append(item("§1.1 Defined Terms", "confidentiality",
                    [T(ci + ", whether disclosed in writing, orally or by observation"),
                     I(", and whether or not it is marked as confidential"), T(".")],
                    "accept", "confirms no marking needed"))

    # Confidentiality: public records (accept only for a public institution giving Sponsor notice first)
    notice = "Institution may disclose Confidential Information to the extent its state public records law requires, after giving Sponsor prompt written notice."
    no_notice = "Institution may release any record that its state public records law requires it to disclose, without notice to Sponsor."
    out.append(item("§8.6 Public Records", "confidentiality", [I(notice)], "accept", "public records, public site, notice", mark="ins", context=PUBLIC))
    out.append(item("§8.6 Public Records", "confidentiality", [I(no_notice)], "escalate", "public records, public site, no notice", mark="ins", context=PUBLIC))
    out.append(item("§8.6 Public Records", "confidentiality", [I(notice)], "escalate", "public records, private site, notice", mark="ins", context=PRIVATE))
    out.append(item("§8.6 Public Records", "confidentiality", [I(no_notice)], "escalate", "public records, private site, no notice", mark="ins", context=PRIVATE))
    out.append(item("§8.6 Public Records", "confidentiality",
                    [I("Sponsor acknowledges that Institution is subject to its state’s freedom of information law; Institution shall notify Sponsor "
                       "at least ten (10) business days before releasing any Confidential Information in response to a request.")],
                    "accept", "public records reworded, public site, notice", mark="ins", context=PUBLIC))

    # Indemnification: notice of claims (prompt; later than 30 days: counter at 30)
    ip_before = "A party seeking indemnification shall notify the indemnifying party "
    ip_after = ", allow it to control the defense and settlement, and cooperate in the defense at the indemnifying party’s expense."
    for n, gold in [(30, "accept"), (20, "accept"), (45, "counter"), (90, "counter")]:
        out.append(repl("§9.3 Indemnification Procedures", "indemnification", ip_before, "promptly of the claim",
                        f"of the claim within {qty(n)} days after learning of it", ip_after, gold, f"claim notice {n}d"))
    out.append(repl("§9.3 Indemnification Procedures", "indemnification", ip_before, "promptly of the claim",
                    "of the claim no later than sixty (60) days after service", ip_after, "counter", "claim notice 60d, reworded"))

    # Indemnification: control of defense (Sponsor controls; taken away: escalate)
    ctl_before = ip_before + "promptly of the claim, "
    ctl_after = ", and cooperate in the defense at the indemnifying party’s expense."
    out.append(repl("§9.3 Indemnification Procedures", "indemnification", ctl_before, "allow it to control the defense and settlement",
                    "allow it to participate in a defense that the indemnified party controls", ctl_after, "escalate", "site controls defense"))
    out.append(repl("§9.3 Indemnification Procedures", "indemnification", ctl_before, "allow it to control the defense and settlement",
                    "consult with it on the defense and settlement", ctl_after, "escalate", "sponsor only consulted"))
    out.append(item("§9.3 Indemnification Procedures", "indemnification",
                    [I("Institution may select its own counsel and direct the defense of any claim against it, at Sponsor’s expense.")],
                    "escalate", "site directs defense, inserted", mark="ins"))
    out.append(repl("§9.3 Indemnification Procedures", "indemnification", ctl_before + "allow it to ", "control", "direct and control",
                    " the defense and settlement" + ctl_after, "accept", "wording, sponsor keeps control"))

    # Indemnification: additional insured (accepted)
    ins = "Sponsor shall maintain clinical trial liability insurance with limits of at least five million US dollars (USD 5,000,000) per occurrence"
    out.append(item("§15.1 Sponsor Insurance", "indemnification",
                    [I("Sponsor shall name Institution as an additional insured under its clinical trial liability policy.")],
                    "accept", "additional insured", mark="ins"))
    out.append(item("§15.1 Sponsor Insurance", "indemnification",
                    [T(ins), I(", naming Institution as an additional insured,"), T(" for the duration of the Study and three (3) years after.")],
                    "accept", "additional insured, in place"))
    out.append(item("§15.1 Sponsor Insurance", "indemnification",
                    [I("Institution, its trustees and its employees shall be named as additional insureds on Sponsor’s policy, and Sponsor shall provide a certificate on request.")],
                    "accept", "additional insureds with certificate", mark="ins"))
    out.append(item("§15.1 Sponsor Insurance", "indemnification",
                    [I("Sponsor shall provide Institution a certificate of insurance listing Institution as additional insured before the first Study Subject is enrolled.")],
                    "accept", "additional insured certificate", mark="ins"))

    # Subject injury: travel to treatment (accepted; lost wages still escalate)
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(" and reasonable travel costs to receive that treatment"), T(tail)],
                    "accept", "travel to treatment"))
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(", including mileage and parking for treatment visits,"), T(tail)],
                    "accept", "mileage and parking"))
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(" and reasonable transportation to and from treatment"), T(tail)],
                    "accept", "transportation, reworded"))
    out.append(item("§10.2 Subject Injury", "subject_injury", [T(si), I(", reasonable travel costs and lost wages"), T(tail)],
                    "escalate", "travel plus lost wages"))

    # Subject injury: exclusions (deleted: escalate)
    ex = "Sponsor is not obligated to reimburse expenses for an injury caused by the underlying disease, by standard-of-care treatment, or by a failure of Institution or the Study Subject to follow the Protocol."
    out.append(item("§10.3 Exclusions", "subject_injury", [D(ex)], "escalate", "exclusions deleted", mark="del"))
    out.append(item("§10.3 Exclusions", "subject_injury", [D(ex), I("Sponsor shall reimburse expenses for any Study Injury, whatever its cause.")],
                    "escalate", "exclusions replaced by any cause"))
    out.append(item("§10.3 Exclusions", "subject_injury",
                    [T("Sponsor is not obligated to reimburse expenses for an injury caused "), D("by the underlying disease, by standard-of-care treatment, or "),
                     T("by a failure of Institution or the Study Subject to follow the Protocol.")],
                    "escalate", "disease and standard-of-care exclusions deleted"))
    out.append(repl("§10.3 Exclusions", "subject_injury", "Sponsor is not obligated to reimburse expenses for an injury caused by the ",
                    "underlying disease", "Study Subject’s underlying illness",
                    ", by standard-of-care treatment, or by a failure of Institution or the Study Subject to follow the Protocol.", "accept", "wording"))

    # Publication: multi-site first publication (18 months, 12 accepted; under 12: counter at 18)
    ms = "Institution shall not publish results from its site before the first multi-site publication of the Study, or "
    ms_tail = " after the Study ends at all sites, whichever is earlier."
    for n, gold in [(24, "accept"), (12, "accept"), (15, "accept"), (11, "counter"), (6, "counter")]:
        out.append(repl("§12.2 Multi-site Publication", "publication", ms, qty(18) + " months", qty(n) + " months", ms_tail, gold, f"multi-site wait {n}mo"))
    out.append(repl("§12.2 Multi-site Publication", "publication", ms, qty(18) + " months", "nine (9) months", " after database lock at its site, whichever is earlier.",
                    "counter", "multi-site wait 9mo, reworded"))

    # Intellectual property: patent prosecution (Sponsor files; site step-in: restore the form)
    for text, gold, note in [
        ("If Sponsor declines to file a patent application on a Study invention, Institution may file it in its own name.", "counter", "site step-in right"),
        ("Institution may file and prosecute patent applications on Study inventions made by its personnel.", "counter", "site files patents"),
        ("Institution may file a provisional patent application in its own name to protect a Study invention.", "counter", "site provisional filing"),
        ("Institution shall sign any document Sponsor reasonably needs to file patent applications on Study inventions in Sponsor’s name, at Sponsor’s expense.",
         "accept", "site assists sponsor filings"),
    ]:
        out.append(item("§13.2 Study Inventions", "intellectual_property", [I(text)], gold, note, mark="ins"))

    # Data privacy: security-incident notice (10 business days, 5 accepted; under 5: counter at 5)
    inc = "Sponsor shall notify Institution of any security incident involving Study Data within "
    for n, gold in [(5, "accept"), (7, "accept"), (4, "counter"), (2, "counter")]:
        out.append(repl("§11.7 Security Incidents", "data_privacy", inc, qty(10) + " business days", qty(n) + " business days", " of discovery.",
                        gold, f"incident notice {n}d"))
    out.append(repl("§11.7 Security Incidents", "data_privacy", inc, qty(10) + " business days", "forty-eight (48) hours", " of discovery.",
                    "counter", "incident notice 48 hours"))

    # Data privacy: data transfer (restricted to one place: escalate)
    for text, gold, note in [
        ("Sponsor shall not transfer Study Data outside the United States.", "escalate", "transfer restricted to one country"),
        ("Study Data shall be stored and processed only on servers located in Institution’s state.", "escalate", "storage restricted to one state"),
        ("Sponsor and its vendors shall host Study Data only in data centers located in Canada.", "escalate", "hosting restricted abroad"),
        ("Sponsor may transfer coded Study Data to its vendors in other countries, in compliance with Applicable Law.", "accept", "transfer allowed under law"),
    ]:
        out.append(item("§11.8 Data Transfer", "data_privacy", [I(text)], gold, note, mark="ins"))

    # Termination for convenience (with non-cancellable costs paid: accept; without: escalate)
    out.append(item("§14.3 Termination for Convenience", "termination",
                    [I("Either party may terminate for convenience on sixty (60) days’ written notice, and Sponsor shall pay non-cancellable obligations incurred before the termination date.")],
                    "accept", "mutual convenience with costs", mark="ins"))
    out.append(item("§14.3 Termination for Convenience", "termination",
                    [I("Institution may terminate for convenience on thirty (30) days’ notice; Sponsor shall pay only for subject visits completed before that date.")],
                    "escalate", "convenience, visits only", mark="ins"))

    # Termination: sponsor notice (30 days, to 60 accepted; over 60: counter at 60)
    sp = "Sponsor may terminate this Agreement on "
    sp_tail = " days’ written notice and shall pay for work completed."
    for n, gold in [(60, "accept"), (45, "accept"), (15, "accept"), (75, "counter"), (90, "counter")]:
        out.append(repl("§14.1 Termination by Sponsor", "termination", sp, qty(30), qty(n), sp_tail, gold, f"sponsor notice {n}d"))

    # Governing law: domestic arbitration (counter: restore the form); abroad escalates
    for text, gold, note in [
        ("All disputes shall be resolved by binding arbitration before a single arbitrator in New York, New York.", "counter", "arbitration in the US"),
        ("Any dispute shall be settled by confidential arbitration seated in Boston, Massachusetts.", "counter", "arbitration in the US, reworded"),
        ("Disputes not resolved by negotiation within thirty (30) days shall go to binding arbitration in the United States.", "counter", "arbitration after negotiation"),
        ("All disputes shall be resolved by binding arbitration seated in Toronto, Ontario.", "escalate", "arbitration abroad (Canada)"),
    ]:
        out.append(item("§17.2 Disputes", "governing_law", [I(text)], gold, note, mark="ins"))

    # Novel terms (no playbook position covers them, except data residency: a data-transfer restriction)
    novel = [
        ("§11.5 Machine Learning", "Sponsor shall not use study data to train artificial intelligence models without Institution’s written consent."),
        ("§11.5 Machine Learning", "Any model trained on study data must be disclosed to Institution and deleted at study close."),
        ("§18.1 Carbon Reporting", "Sponsor shall report the carbon emissions of study shipments to Institution each quarter."),
        ("§18.2 Community Benefit", "Sponsor shall fund a community outreach coordinator at Institution for the duration of the Study."),
        ("§18.3 Post-Trial Access", "Sponsor shall provide Study Drug free of charge to Study Subjects for five (5) years after study close."),
        ("§18.4 Cyber Insurance", "Sponsor shall carry cyber liability insurance of at least ten million dollars."),
        ("§18.5 Preferred Vendors", "Sponsor shall use Institution’s preferred courier for all specimen shipments."),
        ("§18.6 Payment Currency", "Institution may require payment in digital currency at its election."),
        ("§18.7 Naming Rights", "Institution may name any resulting publication series after its donors."),
        ("§18.8 Generative AI", "Sponsor shall not use generative AI tools to draft documents sent to Study Subjects."),
        ("§18.9 Audit Fees", "Sponsor shall pay Institution a fee of two thousand dollars for each monitoring visit."),
        ("§18.10 Diversity Plan", "Sponsor shall share its enrollment diversity plan with Institution’s community board."),
        ("§18.11 Data Residency", "All study data shall remain stored in servers located in Institution’s state."),
        ("§18.12 Press", "Sponsor shall obtain Institution’s consent before naming Institution in any investor presentation."),
        ("§18.13 Biobank", "Leftover samples shall transfer to Institution’s biobank at study close."),
        ("§18.14 Wellness", "Sponsor shall fund parking and meals for each Study Subject visit."),
    ]
    covered = {"§18.11 Data Residency": ("escalate", "data storage restricted to one state (data transfer)")}
    for section, text in novel:
        gold, note = covered.get(section, ("human_review", "no playbook rule"))
        out.append(item(section, "data_privacy" if "Machine" in section or "AI" in section or "Data" in section else "payment_terms",
                        [I(text)], gold, note, mark="ins"))

    # Ambiguous wording (a person should read it)
    amb = [
        repl("§6.2 Invoices", "payment_terms", "Sponsor shall pay each undisputed invoice within ", qty(45) + " days", "a commercially reasonable time",
             " of receipt.", "human_review", "undefined payment time"),
        repl("§8.4 Term of Confidentiality", "confidentiality", "The obligations in this Section 8 survive for ", qty(7) + " years",
             "a period to be agreed", " after study close.", "human_review", "TBD survival"),
        repl("§14.2 Termination by Institution", "termination", "Institution may terminate this Agreement on ", qty(30) + " days’",
             "thirty (60) days’", " written notice.", "human_review", "words and digits disagree"),
        repl("§6.2 Invoices", "payment_terms", "Sponsor shall pay each undisputed invoice within ", qty(45), "forty (45)",
             " days of receipt.", "human_review", "words and digits disagree"),
        repl("§9.1 Indemnification by Sponsor", "indemnification", base, "negligence", "fault, as the parties may determine,", " of Institution.",
             "human_review", "undefined standard"),
        repl("§13.2 Study Inventions", "intellectual_property", ip, "belong to Sponsor", "be allocated as the parties later agree", ".",
             "human_review", "ownership deferred"),
        repl("§10.2 Subject Injury", "subject_injury", si + " ", "incurred", "incurred, and such other costs as may be appropriate,", tail.lstrip(),
             "human_review", "open-ended costs"),
        repl("§17.1 Governing Law", "governing_law", gl, "New Jersey, with venue in its state courts", "the state the parties later select", ".",
             "human_review", "law deferred"),
    ]
    out.extend(amb)

    # Cosmetic edits (accept)
    cos = [
        repl("§6.1 Budget", "payment_terms", "Sponsor shall pay Institution ", "in accordance with", "according to", " the budget in Exhibit B.", "accept", "wording"),
        repl("§8.1 Confidential Information", "confidentiality", "Institution shall hold Sponsor’s Confidential Information in ", "confidance", "confidence",
             ".", "accept", "typo"),
        repl("§12.2 Multi-site Publication", "publication", "Institution may publish ", "after", "following", " the multi-site publication.", "accept", "wording"),
        repl("§14.1 Termination by Sponsor", "termination", "Sponsor may terminate this Agreement on thirty (30) days’ ", "written notice", "notice in writing",
             ".", "accept", "wording"),
        repl("§11.1 Coded Data", "data_privacy", "Institution shall provide Study data to Sponsor in ", "coded form", "a coded form", " only.", "accept", "article"),
        repl("§9.2 Insurance", "indemnification", "Each party shall maintain insurance ", "adequate for", "sufficient to cover", " its obligations.", "accept", "wording"),
        repl("§13.1 Background IP", "intellectual_property", "Each party ", "retains", "keeps", " ownership of its background intellectual property.", "accept", "wording"),
        repl("§17.4 Entire Agreement", "governing_law", "This Agreement and its exhibits ", "are", "constitute", " the entire agreement of the parties.", "accept", "wording"),
    ]
    out.extend(cos)

    # Extra variants to reach the target, drawn from the same rule families
    rng = random.Random(417)
    extra: list[dict] = []
    for n in range(46, 200):
        if len(out) + len(extra) >= TARGET:
            break
        kind = rng.choice(["net", "conf", "pub", "term"])
        if kind == "net":
            v = rng.choice([12, 18, 22, 28, 32, 38, 42, 55])
            gold = "escalate" if v < 30 else "accept"
            extra.append(repl("§6.2 Invoices", "payment_terms", "Sponsor shall pay each undisputed invoice within ", qty(45), qty(v),
                              " calendar days of receipt.", gold, f"Net {v} (variant)"))
        elif kind == "conf":
            v = rng.choice([1, 2, 3, 4, 5, 6, 9, 12])
            gold = "escalate" if v < 3 else "counter" if v < 5 else "accept"
            extra.append(repl("§8.4 Term of Confidentiality", "confidentiality", "Confidentiality obligations continue for ", qty(7), qty(v),
                              " years after the Study ends.", gold, f"survival {v}y (variant)"))
        elif kind == "pub":
            v = rng.choice([10, 21, 28, 35, 42, 55, 65, 80])
            gold = "escalate" if v < 30 else "counter" if v < 60 else "accept"
            extra.append(repl("§12.1 Sponsor Review", "publication", "Sponsor may review each manuscript for ", qty(60), qty(v),
                              " days before submission.", gold, f"review {v}d (variant)"))
        else:
            v = rng.choice([5, 20, 40, 50, 75, 100])
            gold = "escalate" if v < 30 else "accept" if v <= 60 else "counter"
            extra.append(repl("§14.2 Termination by Institution", "termination", "Institution may end this Agreement by giving ", qty(30), qty(v),
                              " days’ written notice.", gold, f"site notice {v}d (variant)"))
    out.extend(extra)
    out = out[:TARGET] + precedent_items()
    for i, it in enumerate(out, 1):
        it["id"] = f"lc-{i:03d}"
    return out


EVAL_SITE = "Riverbend Cancer Care"


def prec(clause: str, values: dict, site: str = EVAL_SITE, agreement: str = "eval-prior", reply: int | None = None) -> dict:
    return {"siteName": site, "agreementId": agreement, "siteNumber": "12", "protocol": "NSO-311", "clauseType": clause,
            "values": values, "via": "executed" if reply is None else "approver_reply", "reply": reply,
            "decidedAt": "2026-03-01T00:00:00Z", "label": ", ".join(f"{k} {v}" for k, v in values.items())}


def precedent_items() -> list[dict]:
    """Escalations judged with a site's history. `ask` holds the values a correct extraction
    reports, so the precedent step can be tested offline."""
    baa = "Sponsor shall sign Institution’s Business Associate Agreement before receiving study data."
    mutual = "Each party shall indemnify the other for claims arising from its own acts, and the obligations in this Section 9 are mutual."
    si = "Sponsor shall reimburse reasonable and necessary medical expenses"
    out: list[dict] = []

    def add(it: dict, ask: dict, precedents: list[dict], note: str, site: str = EVAL_SITE) -> None:
        out.append({**it, "note": note, "ask": ask, "precedents": precedents, "siteName": site, "agreementId": "eval-current"})

    # Precedent should apply: same site, equal or more sponsor-favourable, nothing newer against it
    add(item("§11.3 HIPAA", "data_privacy", [I(baa)], "accept", "", mark="ins"),
        {"requires_baa": "true"}, [prec("data_privacy", {"requires_baa": "true"})], "BAA signed with this site before")
    add(item("§9.3 Mutual Indemnification", "indemnification", [I(mutual)], "accept", "", mark="ins"),
        {"mutual_indemnity": "true"}, [prec("indemnification", {"mutual_indemnity": "true"}, reply=1)], "mutual indemnity approved for this site")
    add(repl("§6.2 Invoices", "payment_terms", "Sponsor shall pay each undisputed invoice within ", qty(45), qty(20), " days of receipt.", "accept", ""),
        {"net_days": "20"}, [prec("payment_terms", {"net_days": "15"}, reply=1)], "Net 20 after this site got Net 15")
    add(repl("§8.4 Term of Confidentiality", "confidentiality", "The obligations in this Section 8 survive for ", qty(7), qty(2), " years after study close.", "accept", ""),
        {"survival_years": "2"}, [prec("confidentiality", {"survival_years": "2"})], "2-year survival signed with this site")
    add(item("§12.3 Patent Delay", "publication",
             [D("At Sponsor’s request, Institution shall delay publication up to an additional sixty (60) days to permit patent filings.")],
             "accept", "", mark="del"),
        {"patent_delay": "removed"}, [prec("publication", {"patent_delay": "removed"})], "patent delay dropped in this site's signed CTA")
    add(item("§11.3 HIPAA", "data_privacy", [I(baa)], "accept", "", mark="ins"),
        {"requires_baa": "true"}, [prec("data_privacy", {"requires_baa": "true"}, site="RIVERBEND CANCER CARE.")], "same site, name typed differently")

    # Precedent should not apply
    add(item("§11.3 HIPAA", "data_privacy", [I(baa)], "escalate", "", mark="ins"),
        {"requires_baa": "true"}, [prec("data_privacy", {"requires_baa": "true"}, site="Cedar Hollow Cancer Center")], "BAA granted only to another site")
    add(repl("§6.2 Invoices", "payment_terms", "Sponsor shall pay each undisputed invoice within ", qty(45), qty(10), " days of receipt.", "escalate", ""),
        {"net_days": "10"}, [prec("payment_terms", {"net_days": "20"}, reply=1)], "Net 10 is worse than the Net 20 granted")
    add(repl("§6.3 Start-up Fee", "payment_terms", "Sponsor shall pay a non-refundable start-up fee equal to ", f"{words(10)} percent (10%)",
             f"{words(25)} percent (25%)", " of the study budget.", "escalate", ""),
        {"start_up_fee_pct": "25", "start_up_fee_refundable": "false"}, [prec("payment_terms", {"net_days": "30"})],
        "a different payment field was granted")
    add(item("§11.3 HIPAA", "data_privacy", [I(baa)], "escalate", "", mark="ins"),
        {"requires_baa": "true"}, [prec("data_privacy", {"requires_baa": "true"}, agreement="eval-current", reply=1)], "only match is this same agreement")
    add(item("§10.2 Subject Injury", "subject_injury",
             [T(si), I(", lost wages and compensation for pain and suffering"), T(" incurred by a Study Subject for a Study Injury.")], "escalate", ""),
        {"covers_lost_wages": "true", "covers_pain_and_suffering": "true"}, [prec("subject_injury", {"covers_lost_wages": "true"})],
        "ask goes beyond what was granted")
    add(item("§10.2 Subject Injury", "subject_injury", [T(si), I(", lost wages"), T(" incurred by a Study Subject for a Study Injury.")], "escalate", ""),
        {"covers_lost_wages": "true"}, [prec("subject_injury", {"covers_pain_and_suffering": "true"})], "a different subject-injury term was granted")
    return out


def write_dataset() -> str:
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w") as f:
        for it in build():
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return str(DATASET_PATH)


def load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        write_dataset()
    return [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]
