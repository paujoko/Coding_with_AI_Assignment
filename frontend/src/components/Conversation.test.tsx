import { fireEvent, render, screen } from "@testing-library/react";
import type { Message } from "../api/types";
import type { Outgoing } from "../lib/outbox";
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

test("an out-of-date line is a record behind Details: the next-step card says it once", () => {
  const events = [{ seq: 4, at: "2026-11-09T10:00:01Z", kind: "phase.stale", phase: "design", summary: "Design is out of date because Requirements changed", data: {} }];
  render(<Conversation intro="" messages={[asked]} events={events} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.queryByText(/Design is out of date because Requirements changed/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Details" }));
  expect(screen.getByText(/Design is out of date because Requirements changed/)).toBeInTheDocument();
});

test("an error stays on its own line: it must be read", () => {
  const events = [{ seq: 5, at: "2026-11-09T10:00:01Z", kind: "phase.error", phase: "design", summary: "Design: the step did not finish", data: {} }];
  render(<Conversation intro="" messages={[asked]} events={events} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByText(/the step did not finish/)).toBeInTheDocument();
});

test("quiet system steps collapse into one line that opens on click", () => {
  const at = (s: number) => `2026-11-09T10:00:0${s}Z`;
  const events = [
    { seq: 1, at: at(1), kind: "agent.llm_call", phase: "design", summary: "Architect replied (mock/architect, 1 attempt, 0.0 s)", data: {} },
    { seq: 2, at: at(2), kind: "artifact.saved", phase: "design", summary: "Use cases: revision 1 saved by architect", data: {} },
    { seq: 3, at: at(3), kind: "artifact.saved", phase: "design", summary: "Domain classes: revision 1 saved by architect", data: {} },
  ];
  render(<Conversation intro="" messages={[asked]} events={events} agentName="Architect" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  const toggle = screen.getByRole("button", { name: "Details" });
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

test("tool calls of an agent are listed when Details opens", () => {
  const at = (s: number) => `2026-11-09T10:00:0${s}Z`;
  const events = [
    { seq: 1, at: at(1), kind: "agent.tool_call", phase: "design", summary: "Architect used check_plantuml: OK: valid PlantUML.", data: { agent: "architect", tool: "check_plantuml" } },
    { seq: 2, at: at(2), kind: "agent.tool_call", phase: "design", summary: "Architect used check_consistency: OK", data: { agent: "architect", tool: "check_consistency" } },
    { seq: 3, at: at(3), kind: "agent.llm_call", phase: "design", summary: "Architect replied (mock/architect, 2 calls, 0.0 s)", data: {} },
  ];
  render(<Conversation intro="" messages={[asked]} events={events} agentName="Architect" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "Details" }));
  expect(screen.getByText(/check_consistency: OK/)).toBeInTheDocument();
});

test("next steps show only under the newest agent answer and report the click", () => {
  const step = { label: "Send the fix to Code generation", phase: "codegen", action: "revise", input: { feedback: "Fix delete." } };
  const older: Message = { ...asked, data: { next_actions: [{ ...step, label: "Old step" }] }, text: "old", created_at: "2026-11-09T10:00:00Z" };
  const newest: Message = { ...asked, data: { next_actions: [step] }, text: "The test is right; the code is wrong.", created_at: "2026-11-09T10:01:00Z" };
  const clicked: string[] = [];
  render(
    <Conversation
      intro=""
      messages={[older, newest]}
      events={[]}
      agentName="Debugger"
      busy={false}
      answers={{}}
      canAnswer={false}
      onPick={() => {}}
      canStep
      onStep={(s) => clicked.push(`${s.phase}.${s.action}`)}
    />,
  );
  expect(screen.queryByRole("button", { name: /Old step/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Send the fix to Code generation/ }));
  expect(clicked).toEqual(["codegen.revise"]);
});

test("while an agent works the time since the start is shown", () => {
  // Real run (s03): a seven-minute step showed only "Finishing" and looked frozen.
  const since = new Date(Date.now() - 65_000).toISOString();
  render(<Conversation intro="" messages={[]} events={[]} agentName="Tester" busy busySince={since} answers={{}} canAnswer={false} onPick={() => {}} />);
  expect(screen.getByText(/^1:0[5-6]$/)).toBeInTheDocument();
});

const imported: Message = {
  phase: "codegen",
  role: "agent",
  text: "Imported from your folder: todo/models.py (changed).\nDesign and code disagree (checked by code):\n- Task.archive() is in the code but not in the class diagram.",
  author: "Folder sync (code)",
  data: {
    speaker: "Folder sync, checked by code",
    drift: ["Task.archive() is in the code but not in the class diagram."],
    next_actions: [{ label: "Update the design from the code", phase: "refinement", action: "comment", input: {} }],
  },
  created_at: "2026-11-14T13:30:00Z",
};

test("a message no agent wrote names its real speaker, and its repair steps go once design and code agree", () => {
  const props = { intro: "", messages: [imported], events: [], agentName: "Coder", busy: false, answers: {}, canAnswer: false, onPick: () => {}, canStep: true, onStep: () => {} };
  const { rerender } = render(<Conversation {...props} />);
  expect(screen.getByText("Folder sync")).toBeInTheDocument();
  expect(screen.getAllByText("Checked by code").length).toBeGreaterThan(0); // the uniform label, not words in the name
  expect(screen.queryByText("Coder")).toBeNull();
  expect(screen.getByRole("button", { name: /Update the design from the code/ })).toBeEnabled();
  rerender(<Conversation {...props} driftResolved />);
  expect(screen.queryByRole("button", { name: /Update the design from the code/ })).toBeNull();
  expect(screen.getByRole("status")).toHaveTextContent("Resolved since: design and code agree now");
});

// ---------- Reading levels in a reply ----------

const reply = (text: string, data: Message["data"] = {}): Message => ({ phase: "codegen", role: "agent", text, author: "Coder", data, created_at: "2026-11-14T13:30:00Z" });
const props = { intro: "", events: [], agentName: "Coder", busy: false, answers: {}, canAnswer: false, onPick: () => {} };

test("a long reply shows its first paragraph; Show more opens the rest", () => {
  render(<Conversation {...props} messages={[reply("Code written for 3 requirements.\n\nIt follows the class diagram closely.\nEvery class has a module.\nEvery method a test hook.")]} />);
  expect(screen.getByText("Code written for 3 requirements.")).toBeInTheDocument();
  expect(screen.queryByText(/Every class has a module/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Show more" }));
  expect(screen.getByText(/Every class has a module/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show less" }));
  expect(screen.queryByText(/Every class has a module/)).toBeNull();
});

test("a short reply has no Show more, and a failure line is never folded", () => {
  const { rerender } = render(<Conversation {...props} messages={[reply("Done.\nThree files.")]} />);
  expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
  rerender(<Conversation {...props} messages={[reply("Tests written.\n\nLong detail line one.\nLong detail line two.\n\n2 tests failed: delete and archive.")]} />);
  expect(screen.getByText(/2 tests failed/)).toBeInTheDocument();
  expect(screen.queryByText(/Long detail line one/)).toBeNull();
});

test("drift lines come with a plain headline: the first three, the rest folded", () => {
  const lines = Array.from({ length: 11 }, (_, i) => `Thing${i} is in the class diagram but not in the code.`);
  render(<Conversation {...props} messages={[reply(["Checked your folder.", ...lines.map((l) => `- ${l}`)].join("\n"), { drift: lines })]} />);
  expect(screen.getByText(/11 differences between the class diagram and the code/)).toBeInTheDocument();
  expect(screen.getByText(lines[0])).toBeInTheDocument();
  expect(screen.getByText(lines[2])).toBeInTheDocument();
  expect(screen.queryByText(lines[3])).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Show 8 more" }));
  expect(screen.getByText(lines[10])).toBeInTheDocument();
});

// ---------- A sent message shows at once (like a chat app) ----------

const bubble = (state: "sending" | "failed"): Outgoing => ({
  id: 1,
  project: "p",
  phase: "codegen",
  action: "revise",
  input: { feedback: "Add a delete command" },
  attachments: [],
  message: { phase: "codegen", role: "developer", text: "Add a delete command", author: "developer", data: {}, created_at: "2026-11-14T13:31:00Z" },
  state,
  seen: 0,
});

test("a sent message is a bubble at once, after the saved ones and above the working line", () => {
  const since = new Date(Date.now() - 5_000).toISOString();
  render(<Conversation {...props} messages={[reply("Code written.")]} busy busySince={since} pending={[bubble("sending")]} />);
  const items = screen.getByRole("list", { name: "Conversation" }).querySelectorAll(":scope > li");
  expect(Array.from(items).map((li) => li.getAttribute("data-role"))).toEqual(["agent", "developer", "agent"]);
  expect(items[1]).toHaveTextContent("Add a delete command");
  expect(items[1]).toHaveAttribute("data-state", "sending");
  expect(items[2]).toHaveClass("msg-working");
  expect(screen.queryByText("Not sent")).toBeNull();
});

test("a sent message shows even in an empty conversation", () => {
  render(<Conversation {...props} intro="What this step makes" messages={[]} busy pending={[bubble("sending")]} />);
  expect(screen.getByText("Add a delete command")).toBeInTheDocument();
  expect(screen.queryByText("What this step makes")).toBeNull();
});

test("a message that failed stays, marked Not sent, with Try again", () => {
  const retried: number[] = [];
  render(<Conversation {...props} messages={[]} pending={[bubble("failed")]} canRetry onRetry={(o) => retried.push(o.id)} />);
  expect(screen.getByText("Add a delete command").closest("li")).toHaveAttribute("data-state", "failed");
  expect(screen.getByText("Not sent")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retried).toEqual([1]);
});

test("Try again waits while an agent works", () => {
  render(<Conversation {...props} messages={[]} pending={[bubble("failed")]} onRetry={() => {}} canRetry={false} />);
  expect(screen.getByRole("button", { name: "Try again" })).toBeDisabled();
});

// ---------- The whole story: decisions and what Wings did on the developer's behalf (ADR 0022) ----------

const line = (text: string, data: Message["data"], role: Message["role"] = "developer", author = "developer"): Message => ({ phase: "design", role, text, author, data, created_at: "2026-11-25T10:00:00Z" });

test("a decision of the developer is one line on their side, not a bubble, and the approval note is Wings'", () => {
  const accepted = line("Accepted", { decision: { action: "approve" }, note: "3 of 7 requirements are verified by a passing test." });
  render(<Conversation {...props} messages={[line("Draw: use case, class · simple", { decision: { action: "generate", kinds: ["use_case", "class"], level: "simple" } }), accepted]} />);
  const items = screen.getByRole("list", { name: "Conversation" }).querySelectorAll(":scope > li");
  expect(Array.from(items).map((li) => li.getAttribute("data-role"))).toEqual(["developer", "developer"]);
  expect(items[0]).toHaveClass("msg-decision");
  expect(items[0].querySelector(".msg-body")).toBeNull(); // never drawn as typed words
  expect(items[0]).toHaveTextContent("Draw: use case, class · simple");
  expect(items[1].querySelector(".decision-note")).toHaveTextContent("Wings: 3 of 7 requirements");
});

test("Wings' instruction on the developer's behalf is named as Wings', its words folded", () => {
  const words = line("The requirements changed. Update every diagram this touches.", { on_behalf: { change: 1 }, action: "revise", label: "Revise" }, "system", "wings");
  render(<Conversation {...props} agentName="Architect" messages={[words]} />);
  const [item] = Array.from(screen.getByRole("list", { name: "Conversation" }).querySelectorAll(":scope > li"));
  expect(item).toHaveAttribute("data-role", "wings");
  expect(item).toHaveTextContent("Wings, carrying change #1");
  expect(screen.queryByText(/Update every diagram/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Revise: Wings' instruction to Architect/ }));
  expect(screen.getByText(/Update every diagram/)).toBeInTheDocument();
});

test("an approval Wings gave is a Wings line", () => {
  render(<Conversation {...props} messages={[line("Accepted on your behalf: its checks pass", { decision: { action: "approve" }, on_behalf: { catch_up: true } }, "system", "wings")]} />);
  const [item] = Array.from(screen.getByRole("list", { name: "Conversation" }).querySelectorAll(":scope > li"));
  expect(item).toHaveAttribute("data-role", "wings");
  expect(item).toHaveTextContent("Wings, redoing this step:Accepted on your behalf: its checks pass");
});

test("answers read next to their questions in a look-back", () => {
  const answer: Message = { ...asked, role: "developer", author: "developer", text: "Q1: Browser", data: {}, created_at: "2026-11-09T10:01:00Z" };
  render(<Conversation intro="" messages={[asked, answer]} events={[]} agentName="Analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} />);
  const items = screen.getByRole("list", { name: "Conversation" }).querySelectorAll(":scope > li");
  expect(items[1].querySelector("dt")).toHaveTextContent("Terminal or browser?");
  expect(items[1].querySelector("dd")).toHaveTextContent("Browser");
});