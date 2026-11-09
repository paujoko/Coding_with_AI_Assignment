# Frontend

React 18, TypeScript (strict), Vite 6, Vitest 3. Code: `frontend/src/`.

## Structure

| File | Job |
|---|---|
| `App.tsx` | state: health, wing catalog, projects, selected project and phase, messages, artifacts, coverage, events; polling of the activity log (0.7 s while busy, 3 s otherwise) |
| `api/client.ts`, `api/types.ts` | typed fetch wrapper; types mirror backend DTOs; errors become readable `ApiError` messages |
| `components/Wingspan.tsx` | the pipeline: P1 to P3 left wing, P4 body, P5 to P7 right wing, status per phase |
| `components/PhaseWorkspace.tsx` | header with status, hint and approve/reopen; conversation and composer on the left, artifacts on the right |
| `components/ActionComposer.tsx` | one tab per action; form fields generated from the action's input JSON schema; answer chips for clarifying questions; Ctrl+Enter submits |
| `components/RequirementsView.tsx` | requirements list and structured editor; saving creates a developer revision |
| `components/DiagramView.tsx` | picture (SVG from the backend) or editable PlantUML source |
| `components/CoverageBar.tsx` | covered and uncovered requirement IDs |
| `components/ActivityLog.tsx` | "What the system did", newest first |
| `components/ErrorBoundary.tsx` | render errors show a message instead of a blank page |
| `lib/status.ts` | status labels, hints that say what to do next, wing grouping |

## Design decisions

- Visual direction: cool drafting-film background, ink text, ultramarine for actions, one colour per phase status. Schibsted Grotesk for the interface, JetBrains Mono (ligatures off) only for PlantUML source.
- The memorable element is the wingspan; everything else is kept quiet so the content (requirements, diagrams) carries the screen in a demo.
- New actions in a wing need no frontend change: the composer renders a field per input property by its schema type (text, number, checkbox, select for enums, one-per-line list for arrays). New artifact kinds need a view component.
- While an agent works, the pipeline and the project picker are disabled, so a result always lands in the phase and project that asked for it.
- Nothing typed is lost on failure: the composer clears only after the backend accepted the action, editors keep their draft when a save fails.
- Layout collapses to one column below 960 px.

## Run

```bash
npm install
npm run dev          # 5190, proxies /api to 8810
npx vitest run       # component and logic tests
npx tsc -b --noEmit  # typecheck
npm run build
```
