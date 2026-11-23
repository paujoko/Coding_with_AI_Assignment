# Guided flow: one loop for building and changing a project

- Date: 2026-11-23
- Branch: `feature/guided-flow` (from `feature/ux-overhaul`)
- Decided by: Claude Code (Opus 5.5) with full freedom from Paul ("Entscheide das selbst ... du kannst es gerne auch nochmals grundlegend verändern, auch die Farben der UI gefallen mir noch nicht")

## Why

Paul, after a real two-player change to a flappy bird project: "absolut viel zu kompliziert ... man versteht viel zu wenig was wie zusammenhängt und wird viel zu schlecht durch die Prozesse durchgeführt". The first fix (one next-step card, "Update all") rearranged buttons but kept the model underneath. He asked for the whole flow to be rethought, and for a look that does not read as generated.

What a user has to understand today, counted on the screen: seven steps, a chat per step with action tabs, Approve, Revise, Request changes, Reopen, "out of date", Update, Update all, Keep as it is, change requests with a tracker, a consistency check, drift, a results panel next to the chat, a folder banner. Each arrived as the answer to one problem. Nobody designed them as one flow.

## The model the user learns

One sentence, shown once on the start page and true everywhere after:

> Wings builds your program in six steps. At each step it shows you what it made. You accept it, or you say what to change. When you change something that later steps depend on, Wings redoes those steps with you, one by one.

So the user meets three ideas: **step**, **accept**, **change**. Everything else is either a consequence they see (a step marked "redo") or a fact checked by code (shown as such).

The course brief requires: "For each phase, the developer must be able to see what the system produced, discuss it, and change it before the system moves on. The developer stays in control." The loop keeps that literally: nothing moves on without Accept. What it removes is the work around Accept: finding the next step, starting it, finding what is out of date, deciding between Update and Approve.

## Goals

1. One loop for the first build and for every later change: look, then accept or ask for a change.
2. One click per step: **Accept** approves the step and starts the next one (opens it and runs its generator when that needs no input).
3. The result of a step is the main thing on screen, readable, full width. The conversation is one switch away.
4. Exactly one sentence per screen is marked as must-read (highlighter yellow). It says what to check in this step, or what Wings needs from you.
5. "Out of date" disappears as a word. A step that has to follow a change is marked **Redo** in the step list, and a strip on every step screen shows the redo order and the next one.
6. Maintenance becomes **Your program**: the place after the build, with how to start it, what code checked about it, and one box "What should change?". A change started there runs through the same loop.
7. A visual identity of its own (below), applied through the tokens.

## Non-goals

- No backend change in behaviour. Every action used exists (`run`, `approve`, `reopen`, `catch-up` with `approve: false|true`, `changes`). The backend's own names stay (phase ids, statuses).
- No new grading feature. Inject bugs, the run guide, the requirement lens, traceability and the folder stay as they are; they are moved, not rebuilt.
- No change to agent prompts.

## Anti-goals (would make this a failure even if it works)

- A step accepted without the user having pressed Accept on that step, unless the user chose "Accept the rest when checks pass" for a redo run (existing, logged as on the developer's behalf).
- Any screen with two primary buttons, or a status the user has to translate (draft, stale, approved).
- Text in the main area that only explains how the tool works.

## Approaches considered

1. **Keep the per-step chat layout, fix wording and buttons** (what s06 did). Cheap, but the chat stays the main thing and every internal message ("Requirements changed, so Code generation is out of date") lands in it. Paul already judged the result too complicated.
2. **A single linear wizard** (one page, Next, Next, Next) with no step list. Simplest, but hides where you are in seven phases, makes changing an earlier step awkward, and the brief's phases would disappear from view in the demo.
3. **Step list plus one loop per step, result first** (chosen). The step list keeps the phases visible and clickable; each step screen is the same shape: what Wings made, one marked sentence, Accept or Change. Redo reuses the same screen. The conversation stays available but is no longer the frame.

## The screens

### Step list (left rail)

```
Wings
[Flappy bird      v]

 ✓ Requirements
 ✓ Design
 ● Design review        <- you are here
 ○ Code
 ○ Tests
 ○ Deployment
 ─────────────
 ◇ Your program

 Traceability   Folder   Activity
 Demo model  ⚙
```

Marks: accepted (check), current (filled dot), waiting for you (yellow dot: questions, or a result to accept), redo (circular arrow, rust), not yet (empty). Under each name one short state word only where it helps: "Your turn", "Redo", "Working". Titles in plain words: Requirements, Design, Design review, Code, Tests, Deployment, Your program (the backend titles stay in the API).

### A step screen

```
Step 3 of 6
Design review                                   [Result | Conversation 4]
┌──────────────────────────────────────────────────────────────────────┐
│▌Check the findings. Apply the ones you agree with, then accept.      │  <- marked sentence
└──────────────────────────────────────────────────────────────────────┘
  (result: findings, diagrams, code, tests ... full width, readable)

──────────────────────────────────────────────────────────────────────────
 [ Say what to change ...                                    ] [Send]
                                          [Accept and write the code]
```

- Header: "Step n of 6", the title, and a two-way switch Result / Conversation (with the message count). The switch picks itself: Conversation while the agent asks questions or nothing is made yet, Result otherwise. The user can always switch.
- Marked sentence: one per screen, from a pure function. Examples: "Answer the questions so the analyst can write the requirements." / "Check that every requirement has a place in a diagram." / "The code differs from the class diagram in 2 places." (with "Checked by code") / "3 tests fail." (checked by code).
- Action bar (bottom, sticky): an input that always means "change this step" (revise, answer, apply, or start, chosen by state; "Ask a question instead" switches it to discuss), and on the right the one primary button.
- Primary button labels say what happens next: "Accept and draw the design", "Accept and write the code", "Accept and redo Code", "Accept and finish". While a step works: no button, a line "The coder is writing the code (1:12)".

### Redo strip (after any change to an accepted step)

```
 ↻ Redo after your change:  Design  ›  Design review  ›  Code  ›  Tests  ›  Deployment
                                                    [Redo Design]   Accept the rest when checks pass
```

- Shown on every step screen while at least one step needs a redo.
- "Redo X" runs `catch-up` with `approve: false`: the step is made again and waits for Accept like any step. Accept then starts the next redo.
- "Accept the rest when checks pass" is the existing run with `approve: true`; it stops at the first step where a code check fails or the agent asks something. Its label says what it does.
- "Keep X unchanged" is a quiet link on the screen of a step that needs a redo, with one confirmation; it approves without regenerating.

### Your program (Maintenance)

```
Your program                                         [Conversation 2]
 Ready. All 6 steps accepted.

 Run it
   cd C:\Users\paul\WingsProjects\todo   [copy]
   python -m todo list                   [copy]

 Checked by code
   ✓ 12 of 12 requirements have a passing test
   ✓ The code matches the class diagram
   ✓ The tests caught 7 of 8 injected bugs        [Inject bugs again]
   ✓ Consistency check: no findings              [Check again]

 What should change?
 [ Add a two-player mode where ...                               ] [Start the change]

 Last change: #1 Two-player mode, complete. Updated 11 files, added 4.  (receipt)
```

- During the build it shows how far the build is and a button to the current step.
- "Start the change" runs the Maintenance `change` action. Its result revises the requirements, which marks later steps for redo, and the redo strip takes over.

## Visual identity

Subject: a tool that walks a developer through a build in order, closer to a pre-flight checklist and a drafting sheet than to a chat app. The current look (near-black, green accent, rounded cards, Host Grotesk) is the generic dark SaaS kit.

- **Colour**
  - Drafting film `#EDF0EB` (canvas)
  - Sheet `#FAFBF8` (surfaces)
  - Navy ink `#1A2633` (text and primary buttons)
  - Rule `#D3D9D3` (lines)
  - Highlighter `#FFE14D` (the one must-read sentence, nothing else)
  - Signal green `#2E7A4B` (checked by code, accepted)
  - Rust `#B9521F` (redo)
  - Red `#B42318` (errors only)
  - Dark mode keeps the logic: blue-black sheet, pale ink, the same highlighter with dark text.
- **Type**
  - Atkinson Hyperlegible Next for everything, chosen for legibility (Paul asked for bigger, more readable text). Reading size 17 px.
  - JetBrains Mono only for code, paths and commands.
- **Form.**
  - 4 px radius, no drop shadows.
  - Structure from rules and the step list's connecting line, not from cards.
  - Primary buttons are solid navy ink; colour is kept for meaning (yellow: read this; green: checked; rust: redo).
- **Motion.** None except the working indicator and the drawer.

## What is left to the builder

- Exact component split, test names, CSS class names.
- Phone layout (390 px): rail becomes a top bar with the current step and a menu; the action bar stays sticky.
- Which components are deleted after the move (NextCard, StatusBadge in headers, HowItWorks if the start page carries the one-sentence model).

## Verification

- Unit tests for the pure flow function (every state above) and the redo order.
- Frontend tests updated; `tsc` clean; backend suite untouched and green.
- Browser on the demo model: new project to Your program with one click per step; a change from Your program through all redo steps; a revise on an accepted Requirements step; 1440, 1024, 390 px; light and dark.
