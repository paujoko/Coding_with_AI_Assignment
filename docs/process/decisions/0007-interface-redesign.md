# 0007 Interface redesign: the pipeline as the one visual idea

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) on Paul's instruction ("überarbeite die komplette UI ... einheitlich und clean ... nicht nach AI slop ... minimalistischer, überlege dir auch ein Logo"); Paul can overturn it

## Context

The first interface (session s01) worked but looked assembled: a decorative "wingspan" with trapezoid wings and a black pill for P4, agent replies drawn like input fields, an eyebrow label above every heading, raw event names (`agent.llm_call`) in the log, diagrams that showed a Graphviz error instead of a picture, and no way to follow a requirement to a diagram. Every team in the course builds with AI, so a generic AI look does not stand out; criteria C3 (usability, the system explains itself) and C5 (navigation requirement -> diagram -> code) are graded.

## Decision

- Treat Wings as a working tool: familiar controls, quiet chrome, content first. Light by default for the projector, dark follows the OS.
- One visual idea, used three times: the seven phases as the logo (seven strokes tracing a V, like the V-model), as stations on a line in the project header (track solid when approved, broken into a stale phase), and as status badges.
- Restrained colour with one job each: green done/go (a nod to the HSG colour), amber needs you, rust out of date, red errors only.
- One self-hosted grotesk (Host Grotesk) plus JetBrains Mono for IDs and source. No CDN fonts, so the demo works offline.
- System steps appear inside the conversation, the full log is its own view; a traceability matrix is its own view; requirements and diagrams link to each other.
- First run asks for name and description and starts P1 right away.
- Design rules and tokens live in `docs/code/design.md`; `CLAUDE.md` points every session there.

The "impeccable" design skill Paul asked for is not installed in the cloud environment. Its public guidance (operate mode, craft floor, bans on eyebrows, card grids, side stripes, gradient text, emoji icons) was read from the skill's repository and followed by hand; its helper binary was not run.

## Alternatives

- Keep the wingspan and polish it: rejected, the decoration did not carry information and broke at narrow widths.
- Dark "developer tool" look with a neon accent: rejected, one of the most common AI-generated looks and poor on a projector.
- A UI library (shadcn, MUI): rejected for now, the screens are few and a library look is exactly the generic appearance we want to avoid.

## Consequences

- New wings need no UI work for actions; new artifact kinds follow the `.doc` pattern in `design.md`.
- The mark doubles as a progress icon, so status colours must stay stable (`lib/status.ts`, CSS `data-status`).
- Diagrams get the house style at render time (backend renderer), so pictures match the interface without touching stored sources.

## Amendment, same day: familiar chat-tool patterns

After his first look Paul found the screen too full and asked to follow the interfaces people know from ChatGPT, Claude and Claude Code. The visual system stays (mark, pipeline line, colours, type); the layout follows the chat pattern: start page as a new chat, chat with the input at the bottom, results in a side panel that appears with the first result, the next step as a card above the input. Detail is collapsed by default. A backend older than the interface is detected (`api_version`) instead of crashing the page.

## Amendment, same day: navigation as a checklist in the sidebar

The horizontal line of stations is replaced by a checklist of steps in the sidebar (GitHub Actions job list, coding-agent plans), with a project switcher above it and the project views below. The main area shows only the current step. The pipeline stays the one idea; it is drawn as a list with status icons instead of a line.
