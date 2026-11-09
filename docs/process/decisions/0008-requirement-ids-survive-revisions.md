# 0008 Requirement IDs survive revisions without IDs (title fallback)

- Date: 2026-11-09
- Status: accepted, refines 0005
- Decided by: Claude Code (Opus 5.5)

## Context

ADR 0005 keeps an ID only when the model echoes it back on a revision. Clicking through the redesigned UI showed that the mock (and, often, real models) returns revised requirements without IDs: every requirement got a new number (REQ-006 to REQ-010), all diagram links pointed to IDs that no longer existed, and the trace showed 0 of 5 covered. That breaks C2 and C5 silently.

## Decision

`assign_ids` resolves in three passes: explicit kept IDs first; then items without a usable ID take the ID of a kept previous requirement with the same title (case and spacing ignored), never one already taken; everything else gets the next number after the highest ID ever issued.

## Alternatives

- Ask the model harder (prompt only): already in the prompt and not reliable.
- Fuzzy matching on description: more matches, but wrong matches would silently move links between different requirements. Exact titles are predictable and testable.
- Let the LLM map old to new IDs in a second call: costs a call and is not deterministic.

## Consequences

- A renamed requirement without its ID still gets a new number; the trace view shows the broken links, so the developer sees it.
- Covered by `test_revision_without_ids_keeps_ids_by_title` and `test_revise_through_the_wing_keeps_the_trace`.

## Amendment, same day (after the independent review)

- Repeated titles map to their IDs in order (a plain dict lost REQ-001 when two requirements shared a title).
- An explicit ID is not kept when its title changed into the title of another kept requirement: the model deleted REQ-002 and shifted REQ-003 down to "REQ-002", which silently changed what REQ-002 meant. That item now keeps REQ-003. A plain rename keeps its ID.
- Tests: `test_duplicate_titles_keep_their_ids_in_order`, `test_an_id_does_not_move_to_another_kept_requirement`.
