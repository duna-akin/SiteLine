"""The Site 07 demo redline: a fictional CTA with 14 tracked changes.

All text is written for this demo. It is not real contract language and comes from
no real sponsor, site or agreement (PRD clean-room rule).

Run `uv run siteline make-demo` to (re)write data/demo/NSO-417_CTA_Site07_redline.docx.
"""

from __future__ import annotations

from siteline.config import DATA_DIR
from siteline.docx_writer import DocxWriter

DEMO_FILE_NAME = "NSO-417_CTA_Site07_redline.docx"
DEMO_PATH = DATA_DIR / "demo" / DEMO_FILE_NAME

SITE = {
    "agreementId": "site-07",
    "siteNumber": "07",
    "siteName": "Larkspur Cancer Institute",
    "city": "Madison, WI",
}

WHIT = "J. Whitcombe (Site 07)"
TAN = "R. Tanaka (Site 07)"
PRIV = "Privacy Office (Site 07)"
PI = "Dr. A. Mensah (PI, Site 07)"
TT = "Tech Transfer (Site 07)"
DATE = "2026-10-14T15:02:00Z"


def T(text: str) -> dict:
    return {"type": "text", "text": text}


def I(text: str, who: str = WHIT) -> dict:  # noqa: E743
    return {"type": "ins", "text": text, "author": who, "date": DATE}


def D(text: str, who: str = WHIT) -> dict:
    return {"type": "del", "text": text, "author": who, "date": DATE}


# (style, segments, comment(author, text) | None, paragraph mark (kind, author) | None)
Block = tuple[str, list[dict], tuple[str, str] | None, tuple[str, str] | None]


def blocks() -> list[Block]:
    b: list[Block] = []

    def h1(text: str) -> None:
        b.append(("Heading1", [T(text)], None, None))

    def h2(text: str) -> None:
        b.append(("Heading2", [T(text)], None, None))

    def p(segs: list[dict] | str, comment: tuple[str, str] | None = None, mark: tuple[str, str] | None = None) -> None:
        b.append(("", [T(segs)] if isinstance(segs, str) else segs, comment, mark))

    b.append(("Title", [T("Clinical Trial Agreement")], None, None))
    p("Protocol NSO-417: Phase II study of NSO-417 in relapsed solid tumors")
    p("Sponsor: Northstar Oncology, Inc., Princeton, New Jersey")
    p("Institution: Larkspur Cancer Institute, Madison, WI")
    p("Site Number: 07")
    p("Enrollment: Institution will use reasonable efforts to enroll 48 subjects over an enrollment period of 18 months.")
    p("Per-patient payment: Sponsor will pay Institution USD 18,200 per enrolled subject, as set out in Exhibit B.")
    p(
        "This Clinical Trial Agreement is entered into by Northstar Oncology, Inc. (“Sponsor”) and "
        "Larkspur Cancer Institute, a public institution of the State of Wisconsin (“Institution”). "
        "This document is fictional and was written for a demo."
    )

    h1("Article 6. Payment")
    h2("§6.1 Budget")
    p("Sponsor shall pay Institution in accordance with the budget attached as Exhibit B.")
    h2("§6.2 Invoices")
    p("Sponsor shall pay each undisputed invoice within forty-five (45) days of receipt, with quarterly reconciliation.")
    h2("§6.3 Start-up Fee")
    p([
        T("Sponsor shall pay a non-refundable start-up fee equal to "),
        D("ten percent (10%)"),
        I("fifteen percent (15%)"),
        T(" of the study budget."),
    ])

    h1("Article 8. Confidentiality")
    h2("§8.1 Confidential Information")
    p("Institution shall hold Sponsor’s Confidential Information in confidence and use it only to conduct the Study.")
    h2("§8.4 Term of Confidentiality")
    p([
        T("The obligations in this Section 8 survive for "),
        D("seven (7)"),
        I("four (4)"),
        T(" years after study close."),
    ])

    h1("Article 9. Indemnification")
    h2("§9.1 Indemnification by Sponsor")
    p([
        T(
            "Sponsor shall indemnify and hold harmless Institution from claims arising from the Study Drug or the "
            "Protocol, except to the extent caused by the "
        ),
        D("negligence"),
        I("gross negligence or willful misconduct"),
        T(" of Institution"),
        I(", as finally adjudicated"),
        T("."),
    ])
    h2("§9.3 Indemnification by Institution")
    p(
        [
            I(
                "Sponsor shall in turn be indemnified by Institution only where required by law, and the parties’ "
                "obligations under this Section 9 shall be mutual."
            )
        ],
        comment=(WHIT, "Our counsel requires mutual language for all industry CTAs."),
        mark=("ins", WHIT),
    )

    h1("Article 10. Subject Injury")
    h2("§10.2 Subject Injury Reimbursement")
    p([
        T("Sponsor shall reimburse reasonable and necessary medical expenses"),
        I(", including lost wages and travel costs,", TAN),
        T(" incurred by a Study Subject for the diagnosis and treatment of a Study Injury."),
    ])
    h2("§10.4 Coordination of Benefits")
    p([D("Reimbursement is net of amounts paid by the subject’s insurance.", TAN)], mark=("del", TAN))

    h1("Article 11. Data Protection")
    h2("§11.1 Coded Data")
    p("Institution shall provide Study data to Sponsor in coded form only.")
    h2("§11.3 HIPAA")
    p(
        [I("Prior to receipt of any study data, Sponsor shall execute Institution’s form Business Associate Agreement.", PRIV)],
        mark=("ins", PRIV),
    )
    h2("§11.5 Secondary Use")
    p(
        [
            I(
                "Sponsor shall not use coded study data to train or fine-tune machine learning models without "
                "Institution’s prior written consent.",
                PRIV,
            )
        ],
        mark=("ins", PRIV),
    )

    h1("Article 12. Publication")
    h2("§12.1 Sponsor Review")
    p([
        T("Institution shall provide Sponsor "),
        D("sixty (60) days", PI),
        I("forty-five (45) days, or as otherwise agreed,", PI),
        T(" to review any proposed publication."),
    ])
    h2("§12.3 Patent Delay")
    p(
        [D("At Sponsor’s request, Institution shall delay publication up to an additional sixty (60) days to permit patent filings.", PI)],
        mark=("del", PI),
    )

    h1("Article 13. Intellectual Property")
    h2("§13.1 Background IP")
    p(
        "Each party retains ownership of its background intellectual property.",
        comment=(TT, "Please confirm Institution’s existing imaging software remains Institution background IP."),
    )
    h2("§13.2 Study Inventions")
    p([
        T("All inventions arising from the Protocol"),
        D(" or Study Drug", TT),
        T(" shall "),
        D("belong to Sponsor", TT),
        I("be jointly owned by Sponsor and Institution", TT),
        T("."),
    ])

    h1("Article 14. Term and Termination")
    h2("§14.1 Termination by Sponsor")
    p("Sponsor may terminate this Agreement on thirty (30) days’ written notice and shall pay for work completed.")
    h2("§14.2 Termination by Institution")
    p([
        T("Institution may terminate this Agreement on "),
        D("thirty (30)"),
        I("sixty (60)"),
        T(" days’ written notice."),
    ])

    h1("Article 17. General")
    h2("§17.1 Governing Law and Venue")
    p([
        T("This Agreement is governed by the laws of the State of "),
        D("New Jersey, with venue in its state courts"),
        I("Wisconsin, with exclusive venue in the courts of Dane County"),
        T("."),
    ])
    h2("§17.4 Entire Agreement")
    p("This Agreement and its exhibits are the entire agreement of the parties regarding the Study.")
    return b


def build_redline(blocks_: list[Block], title: str) -> bytes:
    w = DocxWriter(title=title)
    for style, segs, comment, mark in blocks_:
        cids = [w.add_comment(comment[0], comment[1], DATE)] if comment else None
        w.paragraph(segs, style=style, comment_ids=cids, mark=(mark[0], mark[1], DATE) if mark else None)
    return w.to_bytes()


def demo_bytes() -> bytes:
    return build_redline(blocks(), "NSO-417 CTA, Site 07 redline")


def write_demo() -> str:
    DEMO_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_PATH.write_bytes(demo_bytes())
    return str(DEMO_PATH)


def ensure_demo() -> bytes:
    if not DEMO_PATH.exists():
        write_demo()
    return DEMO_PATH.read_bytes()
