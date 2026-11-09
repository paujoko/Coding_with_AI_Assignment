import io
import zipfile

import pytest

from wings.adapters.documents import DocumentTextExtractor
from wings.adapters.fs_store import FileSystemStore
from wings.domain.attachments import Attachment
from wings.domain.errors import InvalidInputError, NotFoundError
from wings.domain.phases import PhaseId
from wings.domain.project import Project

X = DocumentTextExtractor()


def minimal_pdf(text: str) -> bytes:
    """A one-page PDF with one line of text, written by hand so the test needs no PDF writer."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def minimal_docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_text_and_markdown_are_read_as_utf8():
    assert X.extract("notes.md", "text/markdown", "# Büro\nRooms".encode()) == "# Büro\nRooms"
    assert X.extract("data.csv", "", b"a,b\n1,2") == "a,b\n1,2"


def test_pdf_text_is_extracted():
    assert "Hello PDF" in X.extract("spec.pdf", "application/pdf", minimal_pdf("Hello PDF"))


def test_docx_paragraphs_are_extracted():
    assert X.extract("brief.docx", "", minimal_docx(["First line", "Second line"])) == "First line\nSecond line"


@pytest.mark.parametrize("name", ["photo.png", "archive.zip", "noextension"])
def test_unsupported_files_are_refused_with_a_reason(name):
    with pytest.raises(InvalidInputError, match="supported"):
        X.extract(name, "", b"\x89PNG")


def test_broken_pdf_is_a_developer_error_not_a_crash():
    with pytest.raises(InvalidInputError):
        X.extract("broken.pdf", "application/pdf", b"%PDF-1.4 not really")


def test_store_keeps_attachments_with_their_original_bytes(tmp_path):
    store = FileSystemStore(tmp_path)
    store.save_project(Project.new("Docs", {PhaseId.REQUIREMENTS: []}))
    first = store.save_attachment("docs", Attachment(name="spec.md", media_type="text/markdown", size=5, text="hello"), b"hello")
    second = store.save_attachment("docs", Attachment(name="spec.md", media_type="text/markdown", size=3, text="new"), b"new")
    assert (first.id, second.id) == ("att-001", "att-002")  # same name twice is fine
    assert [a.id for a in store.list_attachments("docs")] == ["att-001", "att-002"]
    assert store.get_attachment("docs", "att-002").text == "new"
    assert (tmp_path / "docs" / "attachments" / "att-001" / "original").read_bytes() == b"hello"
    with pytest.raises(NotFoundError):
        store.get_attachment("docs", "att-999")
    with pytest.raises(NotFoundError):
        store.get_attachment("docs", "../escape")
