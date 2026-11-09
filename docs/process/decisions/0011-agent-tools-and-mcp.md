# 0011 Agents call deterministic tools; Wings is offered as an MCP server

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) on Paul's question ("MCP tools hinzufügen, so dass die KI Agenten UML erstellen können ... Macht das Sinn?")

## Context

The architect wrote PlantUML blind: syntax, consistency and coverage were only checked after its answer. The course asks for a real multi-agent architecture (C4) and for alignment between artifacts (C2). "MCP" can mean two things here: tools our agents call, and Wings offering its operations to other AI clients.

## Decision

1. **Tool calling inside Wings.** The LLM port carries tool specs, tool calls and tool results; `LLMAgent.ask(tools=...)` runs a bounded loop. Tools are deterministic and read-only (`application/tools.py`, parsers in `domain/uml.py`, PlantUML syntax through the renderer port). The architect gets `check_plantuml`, `check_consistency`, `check_coverage`; the design wing re-runs the consistency check by code regardless of what the model did.
2. **Wings as an MCP server** (`wings-mcp`, stdio, MCP Python SDK 2.x as an optional dependency): projects, actions, approval, artifacts, trace and the UML checks for Claude Desktop, Claude Code or Cursor.
3. **Not now:** connecting our agents to external MCP servers (file system, Docker, browser). P5 and P6 need that only together with a sandbox; it will come with them, behind a port.

## Alternatives

- Expose our tools to our own agents through MCP as well (agent -> MCP client -> our MCP server): adds a process boundary and latency for tools that live in the same program; the internal tool contract is shaped so that the same functions back both.
- Let the LLM check its own diagrams in prose: not deterministic, and exactly what the rule "the LLM proposes, code verifies" excludes.

## Consequences

- Each tool round is a model call; the loop is bounded (4 rounds) and visible in the activity log.
- New wings add tools to `application/tools.py` and pass them to their agents; the MCP server can offer them with one decorator each.
