# 0001 Ports and adapters with a phase plugin registry

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) on Paul's instruction ("decide on an architecture and make sure it is kept"); open to the team's revision.

## Context

Seven phases must be built by two people in about four weeks, each phase extendable on its own ("wings"), each triggerable directly, all of them sharing approval gates and change propagation. Grading criterion C4 asks for a real multi-agent architecture, not a script with prompts.

## Decision

- Hexagonal layering: `domain` (pure rules) <- `application` (ports, phase contract, orchestrator) <- `phases` and `adapters` <- `bootstrap` <- `api`/`cli`.
- Each phase is a plugin package exposing `MODULE`; the pipeline is the ordered list in `bootstrap.PHASES`.
- An orchestrator owns gates, approvals, staleness and logging (deterministic manager); wings own the agent work.
- Wings communicate only through versioned artifacts (blackboard), never by importing each other.
- The rules are enforced by an `ast`-based architecture test.

## Alternatives considered

- **Agent framework first (LangGraph, CrewAI, AutoGen):** fast to start, but the gates, staleness and traceability we are graded on would live inside framework abstractions, and switching later is expensive. Can still be used inside a single wing.
- **One flat service module per phase without ports:** less code now, but tests would need network or real subprocesses, and P5/P6 (running tests, Docker) would leak I/O into the core.
- **Event-driven agents talking to each other:** closer to "multi-agent" in name, harder to debug and to demo; the manager pattern from the lecture gives the same separation with a clear control flow.

## Consequences

- More files up front; each new external capability (test runner, Docker) needs a port and an adapter.
- Every wing is testable in isolation with the scripted mock.
- Ports map naturally to MCP tools later (ADR to follow when we add MCP).
