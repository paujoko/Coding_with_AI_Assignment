# 0009 Attached documents are project context, read through a port

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) on Paul's request ("schaue dass man bei unser UI die möglichkeit hat dokumente und so hoch zu laden")

## Context

Developers often start from a written brief or a spec. The agents should read it, and the upload must fit the rules: wings stay independent, the outside world is reached through ports, phases change status only through their own output.

## Decision

- An upload becomes an `Attachment` (domain model) with the original file and its extracted text, stored per project by the `ArtifactStore` port (`attachments/att-001/`).
- Attachments are **not** artifacts: uploading never changes a phase status and never stales anything. A message refers to documents by id (`data.attachments`); `PhaseContext.documents()` resolves them for a wing; `document_turns()` hands them to an agent with length limits.
- Text extraction is a new port `TextExtractor`; the adapter reads text formats, PDF (pypdf, the only new dependency) and .docx (standard library). Images and scanned PDFs are refused with a reason.
- The HTTP API takes JSON with base64 content (5 MB at most) instead of multipart, so the API needs no extra dependency and stays easy to drive from the CLI and tests.

## Alternatives

- Store uploads as artifacts of P1: rejected, every upload would reset P1 to draft and stale the design.
- Let the LLM read files directly (vision or file APIs): provider-specific, costs money, and not testable with the mock.
- Multipart upload: needs `python-multipart`; JSON is enough for documents of this size.

## Consequences

- Any wing can read documents with one call; P1 reads its own, P2 reads P1's and its own.
- Documents are part of the trace only indirectly (through the requirements written from them). Linking a requirement to the paragraph it came from is possible later (`covers` on attachments).
