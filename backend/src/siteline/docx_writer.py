"""Write a minimal Word file with tracked changes and comments.

Paragraphs are lists of segments, the same shape docx_redline.py reads back:
{"type": "text" | "ins" | "del", "text": str, "author"?: str, "date"?: str}.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>"""

SETTINGS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="{W_NS}"><w:trackRevisions/></w:settings>"""

STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="320" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="CommentText"><w:name w:val="annotation text"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="20"/></w:rPr></w:style>
</w:styles>"""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _t(text: str, tag: str = "w:t") -> str:
    return f'<{tag} xml:space="preserve">{escape(text)}</{tag}>'


def _run(text: str, deleted: bool = False, rpr: str = "") -> str:
    tag = "w:delText" if deleted else "w:t"
    parts: list[str] = []
    for i, line in enumerate(text.split("\n")):
        if i:
            parts.append("<w:br/>")
        chunks = line.split("\t")
        for j, chunk in enumerate(chunks):
            if j:
                parts.append("<w:tab/>")
            if chunk:
                parts.append(_t(chunk, tag))
    return f"<w:r>{rpr}{''.join(parts)}</w:r>"


@dataclass
class Comment:
    id: int
    author: str
    text: str
    date: str
    initials: str


@dataclass
class DocxWriter:
    title: str = "Agreement"
    paragraphs: list[str] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    _rev: int = 1

    def _next_rev(self) -> int:
        self._rev += 1
        return self._rev

    def add_comment(self, author: str, text: str, date: str | None = None) -> int:
        cid = len(self.comments)
        initials = "".join(w[0] for w in author.replace("(", " ").split() if w and w[0].isalpha())[:3].upper() or "S"
        self.comments.append(Comment(cid, author, text, date or _now(), initials))
        return cid

    def paragraph(
        self,
        segments: list[dict] | str,
        style: str = "",
        comment_ids: list[int] | None = None,
        mark: tuple[str, str, str] | None = None,
    ) -> None:
        """Add a paragraph. `mark` = ("ins"|"del", author, date) tracks the paragraph mark itself."""
        if isinstance(segments, str):
            segments = [{"type": "text", "text": segments}]
        ppr_parts: list[str] = []
        if style:
            ppr_parts.append(f'<w:pStyle w:val="{escape(style)}"/>')
        if mark:
            kind, author, date = mark
            ppr_parts.append(f'<w:rPr><w:{kind} w:id="{self._next_rev()}" w:author="{escape(author)}" w:date="{date}"/></w:rPr>')
        body: list[str] = [f"<w:pPr>{''.join(ppr_parts)}</w:pPr>"] if ppr_parts else []
        for cid in comment_ids or []:
            body.append(f'<w:commentRangeStart w:id="{cid}"/>')
        for seg in segments:
            text = seg.get("text", "")
            if not text:
                continue
            kind = seg.get("type", "text")
            if kind == "text":
                body.append(_run(text))
            else:
                author = escape(seg.get("author", "Unknown"))
                date = seg.get("date") or _now()
                body.append(
                    f'<w:{kind} w:id="{self._next_rev()}" w:author="{author}" w:date="{date}">'
                    f"{_run(text, deleted=(kind == 'del'))}</w:{kind}>"
                )
        for cid in comment_ids or []:
            body.append(f'<w:commentRangeEnd w:id="{cid}"/>')
            body.append(f'<w:r><w:commentReference w:id="{cid}"/></w:r>')
        self.paragraphs.append(f"<w:p>{''.join(body)}</w:p>")

    def _comments_xml(self) -> str:
        items = []
        for c in self.comments:
            paras = "".join(
                f'<w:p><w:pPr><w:pStyle w:val="CommentText"/></w:pPr>{_run(line)}</w:p>' for line in c.text.split("\n")
            )
            items.append(
                f'<w:comment w:id="{c.id}" w:author="{escape(c.author)}" w:date="{c.date}" w:initials="{escape(c.initials)}">{paras}</w:comment>'
            )
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:comments xmlns:w="{W_NS}">{"".join(items)}</w:comments>'

    def to_bytes(self) -> bytes:
        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document xmlns:w="{W_NS}"><w:body>{"".join(self.paragraphs)}'
            '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
            "</w:body></w:document>"
        )
        core = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{escape(self.title)}</dc:title><dc:creator>Siteline</dc:creator>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{_now()}</dcterms:created></cp:coreProperties>'
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", CONTENT_TYPES)
            z.writestr("_rels/.rels", ROOT_RELS)
            z.writestr("word/_rels/document.xml.rels", DOC_RELS)
            z.writestr("word/document.xml", document)
            z.writestr("word/styles.xml", STYLES)
            z.writestr("word/settings.xml", SETTINGS)
            z.writestr("word/comments.xml", self._comments_xml())
            z.writestr("docProps/core.xml", core)
        return buf.getvalue()
