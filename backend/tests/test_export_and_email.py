import asyncio
import io
import zipfile
from email.message import EmailMessage
from xml.etree import ElementTree

import pytest

from siteline import export, inbound_email, store
from siteline.docx_writer import DocxWriter


@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    store.reset()


def test_export_file_name_fits_in_a_header_without_a_site_number(fresh_state):
    store.put_agreement({"id": "agr-1a2b3c", "siteNumber": "—", "siteName": "Unknown", "status": "awaiting_approval",
                         "receivedAt": "2026-10-01T00:00:00Z"})
    name = export.file_name("agr-1a2b3c")
    name.encode("latin-1")  # Starlette encodes header values as latin-1
    assert name.endswith("_counter-proposal.docx") and "—" not in name


def test_quotes_in_author_names_keep_the_document_valid():
    w = DocxWriter(title="t")
    author = 'R. "Bob" Tanaka'
    cid = w.add_comment(author, "A comment")
    w.paragraph([{"type": "text", "text": "Net "}, {"type": "ins", "text": "30", "author": author, "date": "2026-10-01T00:00:00Z"}],
                comment_ids=[cid], mark=("ins", author, "2026-10-01T00:00:00Z"))
    with zipfile.ZipFile(io.BytesIO(w.to_bytes())) as z:
        for part in ("word/document.xml", "word/comments.xml"):
            root = ElementTree.fromstring(z.read(part))
            authors = {v for el in root.iter() for k, v in el.attrib.items() if k.endswith("}author")}
            assert authors == {author}, part


def test_one_failing_email_does_not_drop_the_rest(fresh_state, tmp_path, monkeypatch):
    monkeypatch.setattr(inbound_email, "INBOX_DIR", tmp_path / "inbox")
    batch = [{"uid": str(i), "from": f"site{i}@example.test", "siteName": f"Site {i}", "subject": f"Redline {i}",
              "attachment": f"r{i}.docx", "receivedAt": "2026-10-01T00:00:00Z", "data": b"docx"} for i in range(3)]
    seen, triaged = [], []

    async def triage_email(email_id):
        triaged.append(email_id)
        if len(triaged) == 1:
            raise ValueError("No tracked changes or comments found in this file.")

    monkeypatch.setattr(inbound_email, "_fetch_unseen", lambda: batch)
    monkeypatch.setattr(inbound_email, "_mark_seen", seen.append)
    monkeypatch.setattr(inbound_email, "triage_email", triage_email)
    asyncio.run(inbound_email.poll_once())
    assert seen == ["0", "1", "2"] and len(triaged) == 3
    recorded = [e for e in store.list_emails() if e["subject"].startswith("Redline")]
    assert len(recorded) == 3 and all("uid" not in e and "data" not in e for e in recorded)


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _email(*attachments, inline_logo=False):
    msg = EmailMessage()
    msg["From"] = "Harbor Clinic <contracts@harbor.example>"
    msg["Subject"] = "Our redline"
    msg["Date"] = "Thu, 01 Oct 2026 09:00:00 +0000"
    msg.set_content("Redline attached.")
    if inline_logo:
        msg.add_alternative("<p>Redline attached.</p>", subtype="html")
        msg.get_payload()[1].add_related(b"png", maintype="image", subtype="png", filename="logo.png", disposition="inline")
    for name, data in attachments:
        maintype, subtype = DOCX.split("/") if name.endswith(".docx") else ("application", "octet-stream")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return msg


def test_an_email_with_one_docx_gets_through():
    found, reason = inbound_email.screen(_email(("site07.docx", b"docx")))
    assert reason == "" and found["attachment"] == "site07.docx" and found["data"] == b"docx"
    assert found["from"] == "contracts@harbor.example" and found["siteName"] == "Harbor Clinic"


def test_a_signature_logo_does_not_count_as_an_attachment():
    found, _ = inbound_email.screen(_email(("site07.docx", b"docx"), inline_logo=True))
    assert found and found["attachment"] == "site07.docx"


@pytest.mark.parametrize(
    "attachments, reason",
    [
        ((), "no attachment"),
        ((("a.docx", b"1"), ("b.docx", b"2")), "2 attachments"),
        ((("a.docx", b"1"), ("notes.pdf", b"2")), "2 attachments"),
        ((("redline.pdf", b"1"),), "attachment is not a .docx (redline.pdf)"),
        ((("redline.docx", b""),), "empty attachment"),
    ],
)
def test_any_other_email_is_blocked(attachments, reason):
    assert inbound_email.screen(_email(*attachments)) == (None, reason)


def test_a_blocked_email_is_marked_read_and_never_returned(monkeypatch):
    raw = {b"1": _email(("a.docx", b"1"), ("b.docx", b"2")).as_bytes(), b"2": _email(("ok.docx", b"x")).as_bytes()}
    flagged = []

    class FakeImap:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def uid(self, command, *args):
            if command == "search":
                return "OK", [b" ".join(raw)]
            if command == "fetch":
                return "OK", [(b"", raw[args[0]])]
            flagged.append(args[0])
            return "OK", []

    monkeypatch.setattr(inbound_email, "_connect", FakeImap)
    batch = inbound_email._fetch_unseen()
    assert [m["uid"] for m in batch] == ["2"] and flagged == [b"1"]
