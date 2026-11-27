# Design system

How the interface looks and behaves, as it is now. Code: `frontend/src/styles.css` (tokens at the top, the guided-flow section at the end), `frontend/src/components/`, the flow logic in `frontend/src/lib/flow.ts`. Why: `docs/superpowers/specs/2026-11-23-guided-flow-design.md` and ADR 0017 (before that ADR 0007).

## Who uses it, where

Two students at laptops while building, then one 12 minute live demo on a projector in a bright seminar room, watched by people who grade software engineering. So: light by default, dark follows the operating system, everything readable from the back row, nothing that needs explaining.

## The model the user learns

One sentence, shown on the start page and in How it works (`MODEL` in `components/HowItWorks.tsx`), and true everywhere:

> Wings builds your program in six steps. At each step it shows you what it made: you accept it, or you say what to change. When you change something later steps depend on, Wings redoes those steps with you, one by one.

Three ideas: **step**, **accept**, **change**. The backend's statuses (draft, stale, approved ...) never appear as words. Everything else is a consequence (a step marked Redo) or a fact computed by code (labelled "Checked by code").

The course brief asks that the developer sees, discusses and can change each phase before the system moves on. Nothing moves on without Accept on that step; the one exception is the explicit link "Redo all, accept when checks pass" (ADR 0016), which says what it does.

## Screens

### Step list (side rail, `components/StepRail.tsx`)

The six build steps as a checklist with a line through it, then **Your program** (Maintenance) below a dashed rule. Plain names: Requirements, Design, Design review, Code, Tests, Deployment (`STEP_TITLE` in `lib/flow.ts`; the API keeps its own titles).

| Mark | Drawn as | Word |
|---|---|---|
| accepted | filled green circle with a tick; the line below turns green | none (screen readers: Accepted) |
| yours (a result, a question or a start waits for you) | ink ring with an ink dot | **Your turn** on a highlighter tag |
| redo (has to follow a change) | rust ring with the redo arrow | **Redo** on a rust tag |
| working | ink ring with a spinner | Working |
| later | grey ring, grey name | none |

Your program shows a diamond; green and "Ready" once all six steps are accepted. Under the rail: Traceability, Folder, Activity, How it works. All of it stays clickable while an agent works (see "While an agent works"); only the project switcher and the model line wait.

### A step screen (`components/PhaseWorkspace.tsx`)

The same shape for every step:

1. **Header:** "Step n of 6", the step title (32 px, bold), a 2 px ink rule. On the right, once there is a result and a conversation, a Result / Conversation switch with the message count. The screen opens on the conversation while the agent asks questions, while its agent works or nothing exists yet, otherwise on the result.
2. **The marked sentence:** the one thing to read on this screen, drawn like a highlighter stroke (`.marked`). It says what to check ("Check that the diagrams cover every requirement."), what failed ("2 of 9 tests fail.", with "Checked by code") or why the step has to be redone. A pass computed by code ("All 7 tests pass. They caught 7 of 8 injected bugs.") is green text without the highlighter. There is at most one per screen and it comes from `screen()` in `lib/flow.ts`.
   When the marked sentence names a problem computed by code, the lines behind it follow in mono, four shown, the rest folded (where code and class diagram differ).
3. **The result**, full width (max 1120 px for the whole screen), sections separated by space and rules, no cards around them. When the agent has just answered a request of the developer ("Change it"), its reply stands above the result in a quiet box with a link to the whole conversation, so a change is never silent.
4. **The action bar**, fixed at the bottom: the text box on the left, the one solid button on the right, quiet text links above that button.
   - The text box always means "change this step" (revise, answer, start or apply, chosen by state); "Ask a question" in the small switch beside the attach button turns it into a question (discuss). The switch lists the change first and the question last. Design review has no revise: its box only asks questions and shows no switch.
   - The solid button says what happens next: "Accept and choose the diagrams", "Draw the design", "Accept and write the code", "Write the tests", "Accept and redo Code", "Accept and finish", "Redo Design", "Run the tests", "Make the code follow the diagram", "Continue with Design".
   - While an agent works on this step the bar shows one line instead: "The coder is writing the code 1:12"; after 15 seconds it adds "A step usually takes one to three minutes."
   - While an agent works on another step the bar keeps its buttons, all off, and the note on the left says "Actions here wait until Code is done." (`--ink-3`, regular weight). A "Go to ..." button only opens a step and stays on.
   - Questions from the agent: once one answer is picked on the cards, the solid button is "Send 2 of 3 answers" (or "Send the answers").
   - Design review: ticked findings are not applied by Accept. While any is ticked the solid button is "Apply N findings" and the sentence says so; "Accept without applying" is the quiet link. Nothing ticked: Accept.
   - Tests: the text box asks a question by default (typing never writes new tests by accident); "Change the tests" in the switch writes them again with the typed guidance. Once the tests ran, the bold line next to the solid button says how many requirements a passing test verifies ("3 of 19 requirements verified by a passing test"); green tests that do not verify every requirement are a `read` marked sentence with the summary and the ids per reason below it, not a green pass (ADR 0020).

**Accept** approves the step and starts the next one in the same click (`afterAccept` in `lib/flow.ts`): the next redo if a change is open, else the next step's generator when it needs no input and offers no choices, else it opens the next step (on its choices for Design and Tests), else Your program. Written tests wait for "Run the tests".

### A sent message (`components/Conversation.tsx`, `lib/outbox.ts`)

Like a chat app: the moment the developer sends, the text box empties and the message stands in the conversation as their bubble, with the agent's working line ("Thinking 0:12") below it. The step shows its Conversation while its agent works; afterwards it opens as it would anyway. If the run fails, the bubble stays with a red hairline and one small red line under it, "Not sent" and the quiet link "Try again"; the words are back in the box too. A message never disappears without a word.

### The conversation as a record (`components/Conversation.tsx`, `lib/history.ts`, ADR 0022)

Each step's conversation tells its whole story, so a finished project can be walked through step by step in the demo. Three looks, one rule: only words someone typed are a bubble.

- **Typed words**: the developer's bubble on the right (above). Answers to the agent's questions show each question small above its answer.
- **A decision of the developer** (a choice, a button, an edit by hand, an import): one line on the right, `--fs-sm`, `--ink-2`, with a 14 px icon in `--ink-3` (tick in `--green` for Accept, pencil for an edit, folder for the folder). Examples: "Draw: use case, class, sequence · simple", "Write focused tests", "Apply F1 (Domain classes)", "Run the tests", "Accepted", "Accepted without applying F3", "Kept unchanged, although Requirements changed". A note Wings gave with an approval follows below in `--fs-xs`, `--ink-3`, starting "Wings:".
- **What Wings did on the developer's behalf** (Redo, Redo all, a change carried through): on the left. A decision reads "On your behalf, carrying change #1: Accepted on your behalf: its checks pass". An instruction written to the agent on the developer's behalf shows the logo (`Mark`, 14 px) with "On your behalf, redoing this step" and a folded line "Revise: instruction to Architect"; an approval note starts with the logo instead of a name; opened, the words sit behind a 2 px `--line-strong` rule.

### While an agent works (`components/WorkNotice.tsx`, `lib/work.ts`)

The developer may look at other steps, Traceability, Folder and Activity while an agent works. Everything there can be read, opened and scrolled; every action is off. A slim notice sits on top of every screen but the working step: surface colour, 1 px line, a 3 px ink edge on the left, spinner, "Code is being worked on · 2:31 · Back to Code". When the agent finishes, Wings does not jump: the notice becomes "Code is ready · Show it" with a green edge and tick ("did not finish", red, when it failed) and goes once the developer opens that step. The step rail keeps the Working mark on the working step.

### Choices before an agent starts (`components/StartChoices.tsx`, ADR 0018)

Design and Tests open on their choices while nothing is made yet: a bold group title (`--fs-md`), then one tile per option in a grid (`minmax(220px, 1fr)`): native checkbox or radio, the option name (600) and one quiet line (`--ink-3`, `--fs-sm`). A ticked tile gets the 3 px ink left edge, like the selected step. The marked sentence says what to do ("Choose the diagrams, then draw them."); the solid button starts the agent with what is ticked. While the agent works the tiles stay visible and disabled. CSS: the "Slim demo" section at the end of `styles.css` (`.start-choices`, `.start-option`).

### Redo strip (`components/RedoStrip.tsx`)

Rust-bordered line above every step screen while a change is not through: "Redo after your change: Design › Design review › Code › Tests › Deployment", each name a link, the current one bold. On the right one quiet link, "Redo all, accept when checks pass". It has no solid button: the screen below carries it. Redo order = the backend's `stale` plus the steps an open change has not reached yet (`redoOf`).

### Your program (`components/ProgramView.tsx`)

After the build: a status line, **Run it** (the copyable `cd` and start command, example commands), **What code checked** (requirements with a passing test, code against the class diagram, the deployment check, injected bugs with "Inject bugs"), the last change with its receipt, and at the bottom "What should change?". Sending a change makes Wings write the requirement change at once and open Requirements for Accept; the redo strip then leads through the rest. While the build is not done it shows how far it is and "Continue with ...".

## Colour

Colour carries meaning only. Structure comes from rules and space.

Light is the default and the theme in use: `index.html` sets `data-theme="light"`, so the dark tokens below never apply, whatever the operating system prefers (Paul, 2026-11-25: light reads better, also on the projector). They stay in `styles.css` for a later switch.

| Token | Light | Dark | Job |
|---|---|---|---|
| `--canvas` | `#edf0eb` drafting film | `#131a22` | page |
| `--surface` | `#fafbf8` | `#19222c` | text boxes, selected step |
| `--sidebar` | `#e3e8e1` | `#0f151c` | side rail |
| `--ink`, `--ink-2`, `--ink-3` | `#1a2633`, `#3c4a59`, `#5a6876` | `#e6ebef` ... | text; `--accent` (solid buttons) is ink |
| `--mark` | `#ffe14d` | `#f2d43d` (dark text) | the one sentence to read, "Your turn" |
| `--green` | `#2e7a4b` | `#62bd88` | accepted, checked by code and passed |
| `--rust` | `#b0491a` | `#ec9160` | redo |
| `--red` | `#b42318` | `#f2837a` | errors and failed checks, and the confirm of a delete (`.button-danger`, the bin on hover) |
| `--focus-color` | `#2a57c4` | `#86a8ff` | keyboard focus ring |

Diagrams always sit on white (`--paper`), because PlantUML draws dark ink.

## Type

- **Atkinson Hyperlegible Next** (400, 400 italic, 600, 700) for everything: drawn for legibility, which was the request. **JetBrains Mono** only for code, paths, commands and trace IDs. Both bundled through `@fontsource` so the demo works offline.
- Scale (`--fs-*`): 13 meta, 15 buttons and tables, 16 interface, **17 prose** (`--fs-read`, line height 1.6), 14 code, 19 the marked sentence, 22 section titles, 32 step titles, 40 start page.

## Form

- Radii 3 / 4 / 6 px. No drop shadows; a selected step is the surface colour with a 3 px ink edge.
- One solid button per screen. Secondary choices are underlined text links (`.button-link`), tools are outlined buttons (`.button`).
- Motion only for state: the spinner while an agent works, nothing on load.

## Rules for new UI

- A new text gets a level: the marked sentence (only via `screen()` in `lib/flow.ts`, with a test), the result, or hidden (Details, tooltip, How it works). If a sentence only explains the tool, delete it.
- Never a second solid button on a screen; never a status word from the backend on screen.
- New artifact kinds: a view in the `.doc` pattern inside the step's result.
- New CSS in its own section at the end of `styles.css`, sizes only from `--fs-*`, colours only from tokens with a job.
- Check in the browser at desktop widths (1440 and 1024 px), in the light theme. Wings is a desktop tool; there is no phone layout.

## The name

The UI never names the tool. The sidebar shows the logo alone (`.brand .mark`, 28 px, `--ink`), the browser tab shows the open project's name ("Projects" without one), and texts say what happens ("Working", "Injected bugs", "On your behalf") instead of who does it.
