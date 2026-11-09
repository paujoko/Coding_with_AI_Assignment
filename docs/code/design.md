# Design system

How the interface looks and why, as it is now. Code: `frontend/src/styles.css` (tokens at the top), `frontend/src/components/`. Decision record: `docs/process/decisions/0007-interface-redesign.md`.

## Who uses it, where

Two students at laptops while building, then one 12 minute live demo on a projector in a bright seminar room, watched by people who grade software engineering. So: light by default (projectors wash out dark screens), dark follows the operating system, everything readable from the back row, nothing that needs explaining.

It is a working tool (an "operate" surface): the developer must always see where the project stands, what the agent did and what to do next. Familiar controls, quiet chrome, the content (requirements, diagrams, trace) carries the screen.

**Familiar first.** Paul's rule (session s02): behave like the AI tools everyone already knows (ChatGPT, Claude, Claude Code), so nobody needs to be told what to do.

- Start page like a new chat: one large input in the middle, example prompts below, Enter starts. The project name is taken from the description.
- Chat on the left, input box pinned at the bottom; your messages right-aligned in a bubble, the agent's as plain text.
- Results in a side panel on the right, like Claude's artifacts or ChatGPT's canvas. The panel appears once there is something to show; before that the chat takes the full width.
- The next step sits right above the input, like a coding agent's approval prompt: "ready for review, Approve", "approved, Go to Design", "out of date, Go to Requirements".
- Chat and panel scroll on their own; the page itself does not. On a phone a Chat / Results switch shows one at a time.
- Patterns taken from chat UI kits (session s02, round 3), rebuilt in our own CSS without the libraries: prompt-kit (rounded input with an attach button on the left and a round send arrow on the right, a 768 px message column, user bubbles, copy on hover, a "to the newest" button, a drop overlay), Vercel AI Elements (artifact panel with download and hide, a suggestion in an empty chat), assistant-ui (scroll that sticks to the bottom unless you scroll up), CopilotKit (an approval card with "Request changes" and "Approve", a live checklist of the agent's steps). Not taken: token streaming, model pickers, branching, voice, the libraries themselves.
- Show less by default: system steps collapse into one line per turn, acceptance criteria open on request, a phase's description shows only before it produced anything, status words in the pipeline only where the developer has to act.

## The one idea

The pipeline is the product. It appears three times, always with the same seven phases and the same status colours:

1. **The mark.** Seven strokes: P1 to P3 the left wing, P4 the body, P5 to P7 the right wing. Read in order they trace a V, the shape of the V-model (specification down the left, code at the bottom, verification up the right). Static it is the logo; in the project list each stroke takes its phase's status, so the logo is also the project's progress.
2. **The line.** In the project header the phases are stations on a track. The track turns solid green once a phase is approved and breaks (dashed rust) where a later phase went out of date. Code generation, the body, is the only square station.
3. **The status badge** next to every phase title.

Assets: `docs/assets/wings-mark.svg`, `docs/assets/wings-mark-progress.svg`, favicon `frontend/public/favicon.svg`. Geometry lives once in `frontend/src/lib/mark.ts`.

## Colour

Restrained: tinted neutrals plus three colours that each have exactly one job. Colour is never the only cue; every status also has a label.

| Token | Light | Job |
|---|---|---|
| `--green` | `#11703c` | done and go: approved, primary buttons, links, coverage hit |
| `--amber-fill` / `--amber` | `#d98a1c` / `#a65a00` | needs the developer's answer |
| `--rust` | `#b3401a` | out of date, uncovered requirement |
| `--red` | `#b42318` | errors only |
| `--ink`, `--ink-2`, `--ink-3` | `#16181c`, `#4a4e57`, `#6a6f78` | text: primary, secondary, meta (all at least 4.5:1 on white) |
| `--canvas`, `--sidebar`, `--surface`, `--subtle` | `#fafaf8`, `#f1f1ed`, `#fff`, `#f4f4f1` | page, side rail, panels, quiet fills |

Green is a nod to the HSG house colour. Dark mode redefines the same tokens under `prefers-color-scheme: dark`. Diagrams always sit on white (`--paper`), because PlantUML draws dark ink.

## Steps: one word says what to do

Every step shows its number and, under its name, one action word: **Start**, **Answer**, **Review**, **Done**, **Update**, **Locked**, **Soon**. The same word appears in the phase badge and in the project list, so there is one vocabulary (`ACTION_LABEL` in `lib/status.ts`; the longer status names stay in tooltips and for screen readers). The groups above the line are named in plain words (Specify, Build, Verify and run) with the wing names as a quiet second label. "How it works" next to the views explains the loop (talk, check, approve) and the words; it is open until the developer closes it once.

## Status vocabulary

| Status | Label | Station / badge |
|---|---|---|
| `locked` | Locked | grey ring |
| `ready` | Ready | ink ring |
| `needs_input` | Needs your answer | filled amber; the next-step strip turns amber |
| `draft` | Ready for review | green ring with a green centre |
| `approved` | Approved | filled green; track to the next station solid green |
| `stale` | Out of date | rust ring with a rust centre; track into it dashed; the strip names the phase that changed |
| planned wing | Planned | dashed grey ring |

Labels live in `frontend/src/lib/status.ts`, the only place to change them.

## Type

- **Host Grotesk** (400, 500, 600) for everything, self-hosted through `@fontsource` so the demo works offline. **JetBrains Mono** only for trace IDs, file paths, PlantUML source and keyboard hints, with ligatures off (an `->` must stay an arrow of two characters).
- Fixed scale, ratio about 1.2: 12, 13, 14 (base), 16, 19, 23, 28 px (`--fs-*`). Headings 600 with slight negative tracking; body measure at most 72ch.
- Numbers in tables and times use tabular figures.

## Layout and components

- Shell: 252 px side rail (brand, new project, projects with their progress mark, one runtime line) and the main area at full viewport height. Below 900 px the rail becomes a top bar with a project picker.
- Project header: name, view switch (Phases, Traceability, Activity), the pipeline line.
- Phase view: title and badge, then chat (left) and results panel (right). One column with a Chat / Results switch below 1100 px.
- Conversation: messages in time order; quiet system steps between two messages collapse into one line ("Architect replied, 3 results saved") that opens on click; staleness and errors stand on their own coloured line. Clarifying questions are cards; clicking an answer fills the input.
- Dock (bottom of the chat): the next-step card, then the input. The input is one rounded box: text first, then the action pills (Start, Revise, Discuss ...) and the send button; fields come from each action's JSON schema; `Ctrl+Enter` sends.
- Spacing on a 4 px grid (`--s1` to `--s7`); radii 6 (controls), 8 (inner panels), 12 (panes). Elevation by borders, not shadows.
- Icons: one authored set in `components/Icon.tsx`, 16 px grid, 1.5 px stroke. No emoji or text glyphs as icons.
- Motion only for state: 150 to 250 ms transitions, a progress bar while an agent works. `prefers-reduced-motion` turns it off.
- Browser surfaces are themed: focus ring (green, 2 px offset), text selection, caret, scrollbars.

## Rules for new UI

- New wing: no frontend change for actions (the composer reads the schema). A new artifact kind gets a view component that follows the `.doc` pattern (head with title, meta, actions; body).
- Reuse `.button`, `.button-primary`, `.button-quiet`, `.tabs`, `.segmented`, `.badge`, `.tag`, `.notice`. One primary button per area.
- No new colours without a job. No cards inside cards, no side-stripe borders, no gradient text, no eyebrow labels above headings.
- Every state needs a design: empty, loading (agent working), error (the alert under the header; a crash shows a card with "Back to the project", "Start page" and "Reload", never a dead end), disabled (navigation is disabled while an agent works).
- Prefer the pattern people know from chat tools over a new one; add a control only when the next step cannot be said in the next-step card.
- Check every change in the browser at 1440, 1024 and 390 px wide, light and dark.
