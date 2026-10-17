import asyncio
import io
import zipfile
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
