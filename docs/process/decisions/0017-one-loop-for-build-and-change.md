# 0017 One loop for building and changing, result first

- Date: 2026-11-23
- Status: accepted (supersedes the next-step card of session s06 and the chat-first layout of ADR 0007)
- Decided by: Claude Code (Opus 5.5) with full freedom from Paul, session s07

## Context

After a real change (a two-player mode in a DeepSeek project) Paul found Wings "viel zu kompliziert": a user had to understand about ten ideas (seven chats with action tabs, Approve, Revise, Request changes, Reopen, out of date, Update, Update all, Keep as it is, change requests with a tracker, consistency check, drift, a results panel beside the chat). Each came as the answer to one problem; none was designed as part of one flow. The s06 fix (one next-step card) rearranged buttons but kept the model. Paul also judged the look generic ("zu sehr nach AI slop").

The course brief requires that the developer sees, discusses and can change each phase before the system moves on.

## Decision

1. **One loop, three ideas.** Step, accept, change. Every step screen has the same shape: what Wings made, one marked sentence, a text box that means "change this step", and one solid button.
2. **Accept starts the next step.** Approving and starting the next generator are one click; Tests are run right after they are written. The button says what comes next ("Accept and write the code").
3. **Redo replaces "out of date".** A change to an accepted step marks later steps Redo. Each is made again without approval (`catch-up` with `approve: false`, or one step of an open change) and waits for Accept like any step. A change from Your program writes the requirement change at once and opens Requirements for Accept. "Redo all, accept when checks pass" stays as an explicit quiet link (ADR 0016).
4. **Result first.** The result fills the screen; the conversation is one switch away and opens by itself only while the agent asks questions.
5. **Maintenance is Your program.** How to start it, what code checked, the last change with its receipt, and one box for the next change.
6. **All decisions in one pure module** (`frontend/src/lib/flow.ts`), tested state by state.
7. **A visual identity of its own**: drafting-film canvas, navy ink, highlighter yellow for the one sentence to read, green for accepted and checked, rust for redo; Atkinson Hyperlegible Next for legibility. Details in `docs/code/design.md`.

No backend change: every call used existed.

Rejected:

- **Keep the chat layout and fix wording** (s06). Already judged too complicated.
- **A wizard without a step list.** Hides the seven phases the course grades and makes changing an earlier step awkward.
- **Auto-accept steps whose code checks pass, always.** Faster, but breaks "before the system moves on" for design steps a person has to judge; kept only as the explicit link.

## Consequences

- One click per step for a whole build and for a whole change; the demo shows a change reaching code, tests and deployment with a receipt, each step accepted by a person.
- Fewer words to learn; the backend's status names are gone from the screen.
- Limit: a change still costs six Accepts. The link "Redo all, accept when checks pass" is the shortcut, and it accepts design steps without a person looking.
- `lib/changes.ts` keeps `carryChange` and `maintenanceWord` with their tests although no screen uses them now.
