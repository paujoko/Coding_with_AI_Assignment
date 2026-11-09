# 0005 Stable trace IDs and phase-level staleness as the consistency backbone

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5)

## Decision

- Requirements get IDs `REQ-001` ... assigned by code, never by the LLM; kept across revisions, never reused.
- Artifacts declare `defines` and `covers` trace IDs; coverage is computed deterministically.
- Any new revision of a phase's artifact marks all transitive dependants stale (`Project.mark_changed`).

## Why

Criteria C2 (alignment under change) and C5 (requirement -> diagram -> code navigation) both need a link that survives LLM regeneration. If the LLM numbered requirements, a revision could silently swap IDs and break every link.

## Consequences

- Fine-grained impact analysis (only the diagrams and files covering REQ-004) builds on these links in P7.
- Phase-level staleness is coarse: any requirements edit stales the whole design. Acceptable for the skeleton; to be refined with the trace graph.
