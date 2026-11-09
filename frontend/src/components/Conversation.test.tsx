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
  render(<Conversation messages={[asked]} events={[]} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByRole("button", { name: "Terminal" })).toBeDisabled();
});

test("system steps of the phase appear between the messages", () => {
  const events = [{ seq: 4, at: "2026-11-09T10:00:01Z", kind: "phase.stale", phase: "design", summary: "Design is out of date because Requirements changed", data: {} }];
  render(<Conversation messages={[asked]} events={events} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByText(/Design is out of date because Requirements changed/)).toBeInTheDocument();
});
