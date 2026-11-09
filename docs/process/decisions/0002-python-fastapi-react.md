# 0002 Python and FastAPI backend, React and TypeScript frontend

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5), Paul's call to delegate the stack

## Decision

Backend in Python 3.14 with FastAPI, Pydantic v2 and httpx; frontend in React 18, TypeScript, Vite.

## Why

- Python's `ast` module makes code-to-diagram drift detection (P7) cheap if generated projects are Python too.
- Pydantic gives one definition per data shape that serves LLM structured output, API validation and the frontend forms (via JSON schema).
- FastAPI publishes an OpenAPI page, useful for targeted control and the demo.
- React with generated forms keeps the UI independent of individual wings.

## Alternatives

- Django (known from another project of Paul's): heavier than needed, no use for an ORM here.
- A notebook interface: allowed by the PDF, but weaker for criterion C3 (usability) and the live demo.

## Consequences

Generated showcase projects default to Python. A non-Python showcase would need a different drift parser.
