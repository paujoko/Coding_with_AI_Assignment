# P6 Deployment

**Requirement (PDF, P6):** a way to run the software outside the development environment (Dockerfile, start scripts). The artifacts are generated, consistent with the design, and they must work.

**How it works**

- `generate {guidance}`: the `deployer` (mid) writes a Dockerfile, `run.sh`, `run.ps1` and `DEPLOY.md`, guided by the component or deployment diagram if there is one, plus a smoke command (`python -m todo list`). The check runs at once.
- Check, by code: every `COPY` source and every `python -m` module exists in the generated code, and the Dockerfile has a `CMD` or `ENTRYPOINT` (`domain/deploy.py`). Then the smoke command starts the program in the Sandbox with the code, without a shell (no pipes or redirection; the schema refuses them); for an interactive program the deployer gives `smoke_input`, which the program reads as standard input (real run s03: a tic-tac-toe game could not be checked before). Exit code 0 passes. Artifact `deployment-check`.
- `check`: run the checks again (after a hand edit). `revise {feedback}`, `discuss {question}`.

**Limits:** Docker itself is not run (it may not be installed, and building images in the tool would be slow); DEPLOY.md has the commands. See ADR 0013.

**Grading hooks:** C1, C7 ("the deployment runs").
