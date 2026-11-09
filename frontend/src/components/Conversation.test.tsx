import { fireEvent, render, screen } from "@testing-library/react";
import type { Message } from "../api/types";
import { Conversation } from "./Conversation";

const asked: Message = {
  phase: "requirements",
  role: "agent",
  text: "Summary\n\nBefore I write requirements I need to know:\nQ1. Terminal or browser? (Decides the UI.)",
  author: "Requirements",
  data: { summary: "Summary", questions: [{ id: "Q1", question: "Terminal or browser?", why: "Decides the UI.", options: ["Terminal", "Browser"] }] },
  created_at: "2026-11-09T10:00:00Z",
};

test("questions become cards whose options report the pick and show the chosen one", () => {
  const picks: string[] = [];
  render(
    <Conversation
      intro=""
      messages={[asked]}
      events={[]}
      agentName="Analyst"
      busy={false}
      answers={{ Q1: "Browser" }}
      canAnswer
      onPick={(q, o) => picks.push(`${q}: ${o}`)}
    />,
  );
  expect(screen.queryByText(/Before I write requirements/)).toBeNull(); // the raw CLI text is not repeated
  expect(screen.getByRole("button", { name: "Browser" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "Terminal" }));
  expect(picks).toEqual(["Q1: Terminal"]);
});

test("answered questions are no longer clickable", () => {
  render(<Conversation intro="" messages={[asked]} events={[]} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByRole("button", { name: "Terminal" })).toBeDisabled();
});

test("system steps of the phase appear between the messages", () => {
  const events = [{ seq: 4, at: "2026-11-09T10:00:01Z", kind: "phase.stale", phase: "design", summary: "Design is out of date because Requirements changed", data: {} }];
  render(<Conversation intro="" messages={[asked]} events={events} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByText(/Design is out of date because Requirements changed/)).toBeInTheDocument();
});

test("quiet system steps collapse into one line that opens on click", () => {
  const at = (s: number) => `2026-11-09T10:00:0${s}Z`;
  const events = [
    { seq: 1, at: at(1), kind: "agent.llm_call", phase: "design", summary: "Architect replied (mock/architect, 1 attempt, 0.0 s)", data: {} },
    { seq: 2, at: at(2), kind: "artifact.saved", phase: "design", summary: "Use cases: revision 1 saved by architect", data: {} },
    { seq: 3, at: at(3), kind: "artifact.saved", phase: "design", summary: "Domain classes: revision 1 saved by architect", data: {} },
  ];
  render(<Conversation intro="" messages={[asked]} events={events} agentName="Architect" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  const toggle = screen.getByRole("button", { name: /Architect replied, 2 results saved/ });
  expect(screen.queryByText(/Use cases: revision 1/)).toBeNull();
  fireEvent.click(toggle);
  expect(screen.getByText(/Use cases: revision 1/)).toBeInTheDocument();
});

test("a message shows the documents it was sent with", () => {
  const said: Message = { phase: "requirements", role: "developer", text: "See the brief", author: "developer", data: { attachments: [{ id: "att-001", name: "brief.pdf" }] }, created_at: "2026-11-09T09:59:00Z" };
  render(<Conversation intro="" messages={[said]} events={[]} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByText("brief.pdf")).toBeInTheDocument();
});

test("while the agent works its finished steps show as a checklist", () => {
  const events = [
    { seq: 1, at: "2026-11-09T10:00:01Z", kind: "action.started", phase: "design", summary: "Design: Generate design", data: {} },
    { seq: 2, at: "2026-11-09T10:00:02Z", kind: "agent.llm_call", phase: "design", summary: "Architect replied (mock/architect, 1 attempt, 0.0 s)", data: {} },
  ];
  render(<Conversation intro="" messages={[]} events={events} agentName="Architect" busy answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByText("Architect replied")).toBeInTheDocument();
  expect(screen.getByText("Finishing")).toBeInTheDocument();
});

test("tool calls of an agent are counted in the collapsed line and listed when opened", () => {
  const at = (s: number) => `2026-11-09T10:00:0${s}Z`;
  const events = [
    { seq: 1, at: at(1), kind: "agent.tool_call", phase: "design", summary: "Architect used check_plantuml: OK: valid PlantUML.", data: { agent: "architect", tool: "check_plantuml" } },
    { seq: 2, at: at(2), kind: "agent.tool_call", phase: "design", summary: "Architect used check_consistency: OK", data: { agent: "architect", tool: "check_consistency" } },
    { seq: 3, at: at(3), kind: "agent.llm_call", phase: "design", summary: "Architect replied (mock/architect, 2 calls, 0.0 s)", data: {} },
  ];
  render(<Conversation intro="" messages={[asked]} events={events} agentName="Architect" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: /Architect ran 2 checks, Architect replied/ }));
  expect(screen.getByText(/check_consistency: OK/)).toBeInTheDocument();
});
