"""Read a Word file's tracked insertions, deletions and comments into JSON.

Standard library only, so the same file runs inside a Daytona sandbox:

    python3 docx_redline.py agreement.docx > changes.json

Each paragraph becomes a list of segments (plain text, inserted text, deleted text).
A paragraph with tracked changes or a comment becomes one change.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def _q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _attr(el: ET.Element, name: str) -> str:
    return el.get(_q(name), "")


def _run_text(run: ET.Element, deleted: bool) -> str:
    out: list[str] = []
    for child in run:
        tag = child.tag
        if tag == _q("t") and not deleted:
            out.append(child.text or "")
        elif tag == _q("delText") and deleted:
            out.append(child.text or "")
        elif tag == _q("t") and deleted:
            # Some writers keep w:t inside w:del; it is still deleted text.
            out.append(child.text or "")
        elif tag in (_q("tab"), _q("ptab")):
            out.append("\t")
        elif tag in (_q("br"), _q("cr")):
            out.append("\n")
        elif tag == _q("noBreakHyphen"):
            out.append("‑")
        elif tag == _q("softHyphen"):
            continue
    return "".join(out)


class _Collector:
    """Walks one paragraph in document order and records segments and comment anchors."""

    def __init__(self) -> None:
        self.segments: list[dict] = []
        self.comment_ids: list[str] = []
        self.authors: list[str] = []
        self.dates: list[str] = []

    def add(self, kind: str, text: str, author: str = "", date: str = "") -> None:
        if not text:
            return
        if self.segments and self.segments[-1]["type"] == kind and self.segments[-1].get("author", "") == author:
            self.segments[-1]["text"] += text
            return
        seg = {"type": kind, "text": text}
        if kind != "text":
            seg["author"] = author
            if date:
                seg["date"] = date
            if author:
                self.authors.append(author)
            if date:
                self.dates.append(date)
        self.segments.append(seg)

    def walk(self, el: ET.Element, mode: str = "text", author: str = "", date: str = "") -> None:
        for child in el:
            tag = child.tag
            if tag == _q("r"):
                self.add(mode, _run_text(child, deleted=(mode == "del")), author, date)
                # A comment can be anchored by a reference inside a run, without a range.
                for ref in child.iter(_q("commentReference")):
                    self.note_comment(_attr(ref, "id"))
            elif tag in (_q("ins"), _q("moveTo")):
                self.walk(child, "ins", _attr(child, "author"), _attr(child, "date"))
            elif tag in (_q("del"), _q("moveFrom")):
                self.walk(child, "del", _attr(child, "author"), _attr(child, "date"))
            elif tag == _q("commentRangeStart"):
                self.note_comment(_attr(child, "id"))
            elif tag in (_q("hyperlink"), _q("smartTag"), _q("sdt"), _q("sdtContent"), _q("fldSimple"), _q("customXml")):
                self.walk(child, mode, author, date)

    def note_comment(self, cid: str) -> None:
        if cid and cid not in self.comment_ids:
            self.comment_ids.append(cid)


def _paragraph_mark_change(p: ET.Element) -> tuple[str, str, str] | None:
    """A paragraph whose mark itself is inserted or deleted (whole-paragraph insert/delete)."""
    rpr = p.find("w:pPr/w:rPr", NS)
    if rpr is None:
        return None
    for kind, tag in (("ins", "ins"), ("del", "del")):
        mark = rpr.find(f"w:{tag}", NS)
        if mark is not None:
            return kind, _attr(mark, "author"), _attr(mark, "date")
    return None


def _style(p: ET.Element) -> str:
    st = p.find("w:pPr/w:pStyle", NS)
    return _attr(st, "val") if st is not None else ""


def _plain(el: ET.Element) -> str:
    parts: list[str] = []
    for p in el.iter(_q("p")):
        c = _Collector()
        c.walk(p)
        parts.append("".join(s["text"] for s in c.segments if s["type"] != "del"))
    return "\n".join(x for x in parts if x).strip()


def _read_comments(z: zipfile.ZipFile) -> dict[str, dict]:
    if "word/comments.xml" not in z.namelist():
        return {}
    root = ET.fromstring(z.read("word/comments.xml"))
    out: dict[str, dict] = {}
    for c in root.findall("w:comment", NS):
        out[_attr(c, "id")] = {
            "author": _attr(c, "author"),
            "date": _attr(c, "date"),
            "text": _plain(c),
        }
    return out


HEADING_RE = re.compile(r"^(§\s*\d+(\.\d+)*|\d+(\.\d+)+)\s+\S")


def _is_heading(style: str, text: str) -> bool:
    s = style.lower()
    if s.startswith("heading") or s in ("title", "subtitle"):
        return True
    return bool(HEADING_RE.match(text)) and len(text) < 90


def parse_docx(data: bytes | str) -> dict:
    """Parse a .docx (bytes or path) into paragraphs and changes."""
    if isinstance(data, (bytes, bytearray)):
        import io

        z = zipfile.ZipFile(io.BytesIO(data))
    else:
        z = zipfile.ZipFile(data)
    with z:
        if "word/document.xml" not in z.namelist():
            raise ValueError("Not a Word document: word/document.xml is missing")
        root = ET.fromstring(z.read("word/document.xml"))
        comments = _read_comments(z)

    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("Word document has no body")

    paragraphs: list[dict] = []
    changes: list[dict] = []
    section = ""
    for p in body.iter(_q("p")):
        c = _Collector()
        c.walk(p)
        mark = _paragraph_mark_change(p)
        segments = c.segments
        style = _style(p)
        original = "".join(s["text"] for s in segments if s["type"] != "ins")
        revised = "".join(s["text"] for s in segments if s["type"] != "del")
        text_for_heading = revised or original
        heading = _is_heading(style, text_for_heading.strip())
        if heading and text_for_heading.strip():
            section = text_for_heading.strip()

        p_index = len(paragraphs)
        paragraphs.append({"index": p_index, "style": style, "heading": heading, "segments": segments})

        has_ins = any(s["type"] == "ins" for s in segments)
        has_del = any(s["type"] == "del" for s in segments)
        site_comments = [comments[cid] for cid in c.comment_ids if cid in comments]
        if not (has_ins or has_del or site_comments):
            continue

        whole_insert = mark is not None and mark[0] == "ins" and not any(s["type"] == "text" and s["text"].strip() for s in segments)
        whole_delete = mark is not None and mark[0] == "del" and not any(s["type"] == "text" and s["text"].strip() for s in segments)
        if has_ins and has_del:
            kind = "replacement"
        elif has_ins:
            kind = "insertion"
        elif has_del:
            kind = "deletion"
        else:
            kind = "comment"
        if whole_insert:
            original = ""
        if whole_delete:
            revised = ""

        author = c.authors[0] if c.authors else (site_comments[0]["author"] if site_comments else "")
        changes.append(
            {
                "index": len(changes) + 1,
                "paragraph": p_index,
                "kind": kind,
                "section": section,
                "original": original.strip(),
                "revised": revised.strip(),
                "segments": segments,
                "author": author,
                "date": (c.dates[0] if c.dates else (site_comments[0]["date"] if site_comments else "")),
                "siteComment": "\n".join(x["text"] for x in site_comments) or None,
                "commentAuthor": site_comments[0]["author"] if site_comments else None,
            }
        )

    counts = {k: sum(1 for ch in changes if ch["kind"] == k) for k in ("insertion", "replacement", "deletion", "comment")}
    return {"paragraphs": paragraphs, "changes": changes, "counts": counts}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: docx_redline.py FILE.docx", file=sys.stderr)
        return 2
    try:
        result = parse_docx(argv[1])
    except (zipfile.BadZipFile, ValueError, ET.ParseError) as e:
        print(json.dumps({"error": str(e)}))
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
