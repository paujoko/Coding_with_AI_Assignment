"""Text from uploaded documents: plain text formats, PDF (pypdf) and Word (.docx, standard library).

Images and other binary formats are refused with a reason the developer can act on.
"""

import io
import re
import zipfile
from pathlib import PurePosixPath

from wings.domain.errors import InvalidInputError

TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
    ".puml", ".plantuml", ".py", ".js", ".ts", ".tsx", ".java", ".kt", ".cs", ".go", ".rs", ".sql", ".toml", ".ini",
}
SUPPORTED = "text and Markdown files, PDF and Word (.docx)"


class DocumentTextExtractor:
    def extract(self, name: str, media_type: str, data: bytes) -> str:
        suffix = PurePosixPath(name.replace("\\", "/")).suffix.lower()
        if suffix in TEXT_SUFFIXES or (not suffix and media_type.startswith("text/")):
            return data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        if suffix == ".pdf":
            return self._pdf(name, data)
        if suffix == ".docx":
            return self._docx(name, data)
        raise InvalidInputError(f"'{name}' cannot be read: supported are {SUPPORTED}.")

    def _pdf(self, name: str, data: bytes) -> str:
        try:
            from pypdf import PdfReader  # imported here: the dependency is only needed for PDFs

            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
        except Exception as err:  # pypdf raises many kinds of errors for broken files
            raise InvalidInputError(f"'{name}' is not a readable PDF ({type(err).__name__}).") from err
        if not text:
            raise InvalidInputError(f"'{name}' has no text layer (a scanned PDF?). Export it with text, or paste the text.")
        return text

    def _docx(self, name: str, data: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        except (zipfile.BadZipFile, KeyError) as err:
            raise InvalidInputError(f"'{name}' is not a readable Word document.") from err
        paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
        lines = ["".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, flags=re.S)) for p in paragraphs]
        return "\n".join(line for line in lines if line.strip())
