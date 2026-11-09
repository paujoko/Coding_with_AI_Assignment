"""Documents the developer attaches to a project (a brief, a spec, notes).

The store keeps the original file; the text extracted from it is what agents read.
Attachments are context, not phase output: adding one never changes a phase status.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from wings.domain.project import utcnow


class Attachment(BaseModel):
    id: str = ""  # assigned by the store: att-001, att-002 ...
    name: str  # original file name, shown to people
    media_type: str = ""
    size: int = 0  # bytes of the original file
    text: str = ""  # extracted text; what agents read
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def ref(self) -> dict[str, str]:
        """How a message points to it."""
        return {"id": self.id, "name": self.name}
