# P4 Code generation

**Requirement (PDF, P4):** code is generated from the approved design, not from the initial description. Classes from the class diagram appear in the code; interactions from sequence diagrams are visible in the calls. Least credit here, so it is kept proportionate.

**How it works**

- `generate {guidance}`: the `coder` (mid) gets the requirements, the current design (refined if P3 made one) and the documents of P1; it may call `check_python` and `compare_with_design` before answering.
- Every Python file must parse (`ast`), else the answer is rejected and retried (up to twice). Web pages (`.html`, `.css`, `.js`, `.svg`) are allowed for local web apps served by `http.server`; the classes of the class diagram stay Python.
- `deviations`: every requirement the code does not meet as asked, with the reason. Saved as `code-gaps` on every generation (also empty) and named in the reply; such a requirement never counts as verified.
- One artifact per file: `source-<slug>`, path `app/<file>`, `covers` = REQ ids.
- After the answer, code compares the classes and public methods with the class diagram (`domain/code.py`); differences appear in the reply and in `data.drift`.
- `revise {feedback}`: changes the code; also the target of next steps from P5 (a code bug) and P7 (a bug report, or "update the code from the design").
- Hand edits are allowed and validated (must parse). P7 reports them.

**Limits:** Python logic only; JavaScript in web pages is neither checked against the design nor tested. The drift check covers classes and public methods, not attributes or associations.

**Grading hooks:** C5 (requirement -> diagram -> code navigation), baseline for C6.
