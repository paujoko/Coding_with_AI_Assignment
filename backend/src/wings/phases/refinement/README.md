# P3 Design refinement

**Requirement (PDF, P3):** an interactive loop. The developer comments on a diagram, asks for a change or points out a problem; the environment updates the design consistently across all diagrams. It may also review its own design and propose improvements.

**How it works**

- `review {focus}`: code checks run first (class/sequence consistency, requirement coverage, PlantUML basics) and become findings with source `check`. Then the `reviewer` (frontier, design tools) adds its own findings. Ids F1, F2 ... are assigned by code. Artifact `review` (`refinement/review.md`).
- `apply {findings, note}`: the `refiner` (frontier, design tools) applies the picked findings to the whole set and returns every diagram. Every diagram must be valid PlantUML (schema check, one retry); code then checks consistency and coverage of the new set again and reports problems in the reply. Applied findings are marked `applied`.
- `comment {diagram, comment}`: a developer remark on one diagram; the refiner updates the whole set so it stays consistent.
- `discuss {question}`: answers, changes nothing.
- The wing owns a refined copy of the design (`refined-<slug>`, `refinement/<slug>.puml`). Later wings use it through `ctx.current_design()`; the trace view hides the P2 diagrams it replaced (ADR 0012).

**UI:** findings as pickable rows with severity; "Apply N findings" runs `apply`. The refined design shows below.

**Limits:** the reviewer's findings are proposals; only the `check` findings are facts. A comment names a diagram by title.

**Grading hooks:** C1 (phase beyond coding), C2 (change propagates across diagrams), C7 (quality of diagrams).
