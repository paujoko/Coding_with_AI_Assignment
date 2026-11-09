# 0013 Generated code runs in a local sandbox folder; Docker is not run

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) while building P5 and P6

## Context

P5 must run the generated tests and report real results; P6 must show that the deployment works. The results must come from running code, never from a model (C7, and our "LLM proposes, code verifies" rule). The code comes from a model, so it is untrusted. The developers run Wings on their own laptops (Windows, macOS); Docker may not be installed, and building images inside a tool takes minutes.

## Decision

- A `Sandbox` port (`run(files, argv, timeout, collect) -> ProcessResult`) with one adapter, `LocalSandbox`: a fresh temporary folder per run, the files written there (relative paths only, `..` and absolute paths refused), the program started with the same Python interpreter as Wings, a time limit (120 s for tests, 30 s for the smoke run), an environment that keeps only what Python needs (PATH, system variables) and drops everything else, no standard input (so a program cannot read the MCP server's stdio or wait for typing), its own process group that is stopped as a whole at the time limit, and output written to a file and capped. The folder is deleted afterwards.
- P5 runs `pytest --junitxml` and reads the XML; P6 runs the deployer's smoke command (must start with `python`).
- Docker is checked statically (`domain/deploy.py`: COPY sources and started modules exist, there is a CMD or ENTRYPOINT) but not built or run. `DEPLOY.md` tells the developer how.
- The wing never starts processes itself; the architecture test forbids `subprocess` in domain, application and the wings.

## Consequences

- Test and smoke results are real and reproducible on any machine with Python, without Docker.
- The sandbox is not a security boundary: generated code runs with the developer's user rights and could read files elsewhere (including `.env` with the API key, or the parent's environment through `/proc` on Linux) or use the network. The independent review of round 7 showed both reads; keeping the key out of the child's environment only stops accidental leaks (a program printing its environment). This is acceptable for a course tool where the developer reviews the code before running tests, and it is stated in the UI docs and the wing READMEs. A container-based adapter can replace `LocalSandbox` behind the same port.
- The Docker image itself is never proven to build. The static checks catch the common mistakes (wrong paths, wrong module names).
