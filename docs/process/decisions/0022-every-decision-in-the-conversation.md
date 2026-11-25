# 0022 Every decision in the conversation, and Wings' actions never as the developer's

- Date: 2026-11-25
- Status: accepted (extends what a message is, ADR 0007 and 0016)
- Decided by: Claude Code (Opus 5.5) as a subagent, on Paul's brief for the demo

## Context

In the demo the team first walks through a product built before, step by step: every prompt, every answer, every choice and change. A mock run showed that only typed words were messages. The choice of diagrams and level, the depth of the tests, the findings applied, Accept, Keep it unchanged, Run the tests, Inject bugs, Redo, Reopen, hand edits and folder imports were only events, folded into "Details" or not in the conversation at all. Worse, when Wings carried a change or caught up, the refresh step's text ("The requirements changed. Update every diagram ...") and the analyst's planned requirement revision were stored as the developer's messages: a look-back showed words the developer never typed as theirs.

## Decision

1. **A decision is a message.** Role `developer`, author `developer`, `data.decision` = `{action, ...input}`, text one readable line. `run_action` records one for every action: the wing's `ActionSpec.decision(params, artifacts)` when it has one (design kinds and level, test depth, run, injected bugs, applied findings), else the action's label when the developer typed nothing. A choice and typed words are two messages, the choice first. The orchestrator also records Accept (the wing's `acceptance`, e.g. "Accepted without applying F2"), Keep it unchanged (approving a stale step), Reopen, an edit by hand, a folder import and a restore. The approval note goes in `data.note`; it is Wings' text, not the developer's.
2. **On the developer's behalf is Wings'.** What `advance_change`, `catch_up` and the check after a change run or approve is stored with role `system`, author `wings` and `data.on_behalf` (`{change}` and/or `{catch_up}`). Its text is either Wings' instruction to the agent or, with `data.decision`, a line such as "Accepted on your behalf: its checks pass".
3. **What agents read.** `for_agents` (in `turns_from`) sends the developer's words, agent replies and Wings' instructions (as user turns, so the refresh step still reaches the model) and leaves every decision line out. The agents' turns are therefore the same as before this decision; only the stored record changed.
4. **Recorded on the backend**, so the UI, the CLI, the MCP server and the API read the same history. All or nothing as before: a failed action saves no decision. API 13.

Rejected:

- **Show the events in the conversation instead.** Events describe what the system did, not what the developer chose, and a choice such as "class, sequence, simple" is not in any event.
- **Send decision lines to the model.** "Accepted" or "Run the tests" mean nothing to an agent and would change the replies of the scripted mock and real runs alike.
- **Keep on-behalf messages as role `developer` with another author.** Every reader that only looks at the role would still attribute the words to the developer.

## Consequences

- Each step's conversation tells its whole story in order, and nothing the developer did not type reads as theirs.
- Projects from before keep loading; their old on-behalf messages stay stored as the developer's (messages are append-only and are not rewritten).
- More lines in the conversation. The frontend draws decisions as one compact line, not a bubble, and Wings' instruction behind a "Wings" label with the text folded.
