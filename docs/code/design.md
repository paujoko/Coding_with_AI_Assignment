# Design system

How the interface looks and why, as it is now. Code: `frontend/src/styles.css` (tokens at the top), `frontend/src/components/`. Decision record: `docs/process/decisions/0007-interface-redesign.md`.

## Who uses it, where

Two students at laptops while building, then one 12 minute live demo on a projector in a bright seminar room, watched by people who grade software engineering. So: light by default (projectors wash out dark screens), dark follows the operating system, everything readable from the back row, nothing that needs explaining.

It is a working tool (an "operate" surface): the developer must always see where the project stands, what the agent did and what to do next. Familiar controls, quiet chrome, the content (requirements, diagrams, trace) carries the screen.

**Familiar first.** Paul's rule (session s02): behave like the AI tools everyone already knows (ChatGPT, Claude, Claude Code), so nobody needs to be told what to do.

- Start page like a new chat: one large input in the middle, example prompts below, Enter starts. The project name is taken from the description. Directly under the input sits one compact row, always visible: "Project folder", the path, Browse. It is prefilled with the backend's default folder for the project name and follows the description until the developer edits or browses it. A project cannot start without a folder: the send button says what is missing (its tooltip, and one amber line after a try).
- Chat on the left, input box pinned at the bottom; your messages right-aligned in a bubble, the agent's as plain text.
- Results in a side panel on the right, like Claude's artifacts or ChatGPT's canvas. The panel appears once there is something to show; before that the chat takes the full width.
- The next step sits right above the input, like a coding agent's approval prompt: "ready for review, Approve", "approved, Go to Design", "out of date, Go to Requirements".
- Chat and panel scroll on their own; the page itself does not. On a phone a Chat / Results switch shows one at a time.
- Patterns taken from chat UI kits (session s02, round 3), rebuilt in our own CSS without the libraries: prompt-kit (rounded input with an attach button on the left and a round send arrow on the right, a 768 px message column, user bubbles, copy on hover, a "to the newest" button, a drop overlay), Vercel AI Elements (artifact panel with download and hide, a suggestion in an empty chat), assistant-ui (scroll that sticks to the bottom unless you scroll up), CopilotKit (an approval card with "Request changes" and "Approve", a live checklist of the agent's steps). Not taken: token streaming, model pickers, branching, voice, the libraries themselves.
- Show less by default: system steps collapse into one line per turn, acceptance criteria open on request, an empty conversation shows one line about the step and its one start button, status words in the pipeline only where the developer has to act.
- No instructions nobody reads (session s05): views have no intro paragraphs. What stays is what tells the developer where the project stands or what to do next: the next-step card, status labels, errors, empty states of one line.

## The one idea

The pipeline is the product. It appears three times, always with the same seven phases and the same status colours:

1. **The mark.** Seven strokes: P1 to P3 the left wing, P4 the body, P5 to P7 the right wing. Read in order they trace a V, the shape of the V-model (specification down the left, code at the bottom, verification up the right). Static it is the logo; in the project list each stroke takes its phase's status, so the logo is also the project's progress.
2. **The checklist.** The seven steps in the sidebar, with the same status colours (see Navigation).
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

## Navigation: everything you move between lives in the sidebar

Session s02, round 5 replaced the horizontal line of numbered stations. A progress bar was the wrong picture: Wings is a list of tasks of which you work on one at a time. References: the job list on a GitHub Actions run page (statuses on the left, the selected job on the right), the plan list of coding agents (Claude Code, Cursor), Shopify's setup guide (the next thing is the loud one), Linear's and Vercel's project switcher.

- **Project switcher** at the top of the sidebar: the mark shows the project's progress, the line below says where it stands ("Design: review", or "Change #1: step 2 of 6" while a change is carried through); the menu lists every project and "New project".
- **Steps as a checklist**, grouped in plain words (Specify, Build, Verify and run) with the wing names as a quiet second label. Each step: a status icon (tick when done, filled amber dot when it waits for answers, green ring when ready for review, rust alert when it needs an update, lock, dashed circle when not built yet) and its name. A word appears only where you have to act: **Start**, **Answer**, **Review**, **Update**; unbuilt steps say **Soon** in grey. A thin line joins the icons of a group and turns green below finished steps. The same words appear in the phase badge and the switcher (`ACTION_LABEL` in `lib/status.ts`).
- **Maintenance is not a step to finish.** It never says Start or Review: while a change is open its word is "Change 2 of 6" (a neutral pill; the step of the change the developer is at), otherwise it has no word and reads as ready, and "Check" in rust when it is out of date. The phase badge says the same.
- **Project views** under the steps: Traceability, Folder (the project's folder on the developer's computer; an amber count shows how many files were changed there by hand), Activity, How it works (a dialog with the loop and the legend; the three-line loop of talk, check, approve is shown only there).
- **The main area belongs to the step**: its title and badge, the chat with the next-step card, the results panel. No header strip, no tabs. The line between chat and results can be dragged (or moved with the arrow keys); its position is remembered.
- **Phones**: the sidebar sits on top; steps and views become rows of chips that scroll sideways; unbuilt steps are hidden there.

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
- Fixed scale (`--fs-*`, raised in session s05 after the body text was tiny on a 2000 px screen). Nothing is below 13 px.

  | Token | Size | Used for |
  |---|---|---|
  | `--fs-xs` | 13 px | meta lines, badges, tags, times |
  | `--fs-sm` | 14 px | buttons, pills, table text, notices |
  | `--fs-base` | 15 px | interface text: sidebar, tabs, labels, the next-step card |
  | `--fs-read` | 16 px | prose: chat messages, requirement descriptions, review findings, rationale, change plans; line height `--lh-read` (1.6) |
  | `--fs-code` | 13.5 px | code listings, PlantUML source, console output, paths in fields |
  | `--fs-md`, `--fs-lg`, `--fs-xl`, `--fs-2xl` | 18, 21, 26, 32 px | small headings, step and panel titles, page titles, the start page |

- Headings 600 with slight negative tracking. Prose is at most `--measure` (72ch) wide, also in a very wide results panel; tables and code listings may use the width.
- The message column is `--chat-measure` wide: 720 px, 820 px on screens from 1700 px, where the chat also takes half of the main area by default (until the developer drags the line).
- Numbers in tables and times use tabular figures.

## Layout and components

- Shell: 272 px side rail (`--rail`) (brand, project switcher, step checklist, project views, model line) and the main area at full viewport height. Below 900 px the rail becomes a top bar with chip rows (see Navigation).
- Phase view: title and badge, then chat (left) and results panel (right). One column with a Chat / Results switch below 1100 px.
- Conversation: messages in time order; quiet system steps between two messages collapse into one line ("Architect replied, 3 results saved") that opens on click; staleness and errors stand on their own coloured line. Clarifying questions are cards; clicking an answer fills the input.
- Dock (bottom of the chat): the next-step card, then the input. The input is one rounded box: text first, then the action pills (Start, Revise, Discuss ...) and the send button; fields come from each action's JSON schema; `Ctrl+Enter` sends. The pills stay on one line and scroll sideways in a narrow chat column (fade on the right, the chosen pill is kept in view); the send button keeps its place.
- "Checked by code" (`components/CheckedByCode.tsx`, `.by-code`): the one label for everything a program computed and no model wrote: traceability, test results, the deployment check, consistency, what a change touches, review findings found by a check, folder sync, the code against the class diagram. Always these words and this shape, never a varying sentence. Things an agent wrote keep the agent's name.
- Change tracker (`components/ChangeTracker.tsx`, `.tracker`): the one bold element of the Maintenance screen, one bordered panel on the results surface with rows and hairlines inside. Top to bottom: "Change #1", kind tag, where it stands; the request in the developer's words at 18 px; the affected requirement chips; the steps as the sidebar checklist (green tick done, grey ring waiting, dashed ring not affected; the step to act on is the loud one, with its own status icon and an ink pill "Now"); one primary button named for the next step and "Carry it through" beside it, with one sentence that says Wings approves each step whose code checks pass; the live log of a run; the receipt. In a panel from 620 px the steps become one line of six and the receipt two columns (container query on the panel). A reason to stop is an amber box (red only when the request itself failed). A completed change shows no steps: its receipt is the headline, with the totals in 18 px.
- Receipt (`.receipt`): "What this change updated" with the "Checked by code" label and the totals, then per phase one row per artifact: its name as a link into its phase, its kind, "rev 1 to 2" with the new revision in green, a tag for new and removed ones. A file written again without a difference stays in the list, small and grey, as "rewritten, identical".
- A change in progress seen from another view: one neutral strip (`.alert-change`) in the row of banners, one line and one button.
- Commands to paste (`.term`, "Run it"): one command per line on a quiet fill, a prompt sign that cannot be selected, the command in mono, a copy button per line that answers "Copied" in words. A long path scrolls inside its line.
- Injected bugs (`.mutants`): rows separated by hairlines, the rows are the evidence, no big numbers. The change is two mono lines tagged `code` and `bug`; the bug line is green when a test caught it and amber when no test noticed (that one needs the developer); runs that did not count are grey. The verdict line is green only when nothing went unnoticed, amber otherwise, never red: a bug the tests miss is work for the developer, not an error of the tool.
- One requirement end to end (`.lens`): a page read top to bottom (requirement, In the design, In the code, In the tests), parts separated by hairlines, Previous and Next in a bar that stays in view. A diagram is at most 68 % of the window high, so it fits a projector without scrolling inside it. Marked code lines get a green fill, no side stripe.
- Paths: a path shown as text wraps inside its box (Folder view); a path in a field scrolls inside the field. Neither may widen the page (pages are a one-column grid of `minmax(0, 1fr)`).
- Diagram picture: while it is being drawn the canvas shows "Drawing the diagram" with a spinner on a quiet fill; if drawing fails, a notice with "Try again" and the PlantUML source below.
- Spacing on a 4 px grid (`--s1` to `--s7`); radii 6 (controls), 8 (inner panels), 12 (panes). Elevation by borders, not shadows.
- Icons: one authored set in `components/Icon.tsx`, 16 px grid, 1.5 px stroke. No emoji or text glyphs as icons.
- Motion only for state: 150 to 250 ms transitions, a progress bar while an agent works. `prefers-reduced-motion` turns it off.
- Browser surfaces are themed: focus ring (green, 2 px offset), text selection, caret, scrollbars.

## Rules for new UI

- New wing: no frontend change for actions (the composer reads the schema). A new artifact kind gets a view component that follows the `.doc` pattern (head with title, meta, actions; body).
- Reuse `.button`, `.button-primary`, `.button-quiet`, `.tabs`, `.segmented`, `.badge`, `.tag`, `.notice`, `.by-code`. One primary button per area.
- Sizes only from the `--fs-*` tokens; prose gets `--fs-read`, `--lh-read` and `max-width: var(--measure)`. New CSS goes in its own section at the end of `styles.css`.
- No explanatory paragraph above a view. If a control needs a sentence to be understood, rename the control.
- No new colours without a job. No cards inside cards, no side-stripe borders, no gradient text, no eyebrow labels above headings.
- Every state needs a design: empty, loading (agent working), error (the alert under the header; a crash shows a card with "Back to the project", "Start page" and "Reload", never a dead end), disabled (navigation is disabled while an agent works).
- Prefer the pattern people know from chat tools over a new one; add a control only when the next step cannot be said in the next-step card.
- Check every change in the browser at 1440, 1024 and 390 px wide, light and dark.
