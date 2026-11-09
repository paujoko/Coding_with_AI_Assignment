# P3 Design refinement (planned)

**Requirement (PDF, P3):** an interactive loop. The developer comments on a diagram, asks for a change or points out a problem; the environment updates the design consistently across all diagrams. It may also review its own design and propose improvements (missing classes, unclear responsibilities, uncovered requirements).

**Suggested design**

- Agents: `reviewer` (critic, reads requirements and all diagrams, returns findings with severity and the diagram/element they refer to) and `architect` (applies accepted findings or developer comments to the whole set).
- Actions: `review` (run the reviewer), `comment {diagram_id, text}` (developer remark on one diagram, the architect updates all affected diagrams), `apply {finding_ids}`, `discuss`.
- Deterministic checks before the LLM review: requirement coverage (`wings.domain.trace`), and later a PlantUML parser that checks every class in a sequence diagram exists in the class diagram.
- Output: new revisions of the `diagram-*` artifacts (owned by the design phase today; decide whether P3 writes them or owns refined copies, and record the decision as an ADR).

**Grading hooks:** C1 (phase beyond coding), C2 (change propagates across diagrams), C7 (quality of diagrams).
