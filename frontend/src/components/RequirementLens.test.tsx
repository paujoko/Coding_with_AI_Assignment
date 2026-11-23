import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Artifact, PhaseState, Trace } from "../api/types";
import { diagramNames, linesNamedInDiagrams } from "./RequirementLens";
import { TraceView } from "./TraceView";

const art = (over: Partial<Artifact>): Artifact => ({
  id: "x",
  kind: "source_file",
  phase: "codegen",
  title: "x",
  revision: 1,
  content: {},
  text: "",
  path: null,
  defines: [],
  covers: [],
  author: "agent:coder",
  retired: false,
  created_at: "2026-11-23T10:00:00Z",
  ...over,
});

const CODE = "class TaskService:\n    def add_task(self, title):\n        return title\n\n    def _helper(self):\n        pass\n";

const store: Record<string, Artifact[]> = {
  requirements: [
    art({
      id: "requirements",
      kind: "requirements",
      phase: "requirements",
      content: {
        requirements: [
          { id: "REQ-001", title: "Add a task", description: "The user adds a task with a title.", type: "functional", priority: "must", acceptance_criteria: ["An empty title is refused."] },
          { id: "REQ-002", title: "List tasks", description: "The user sees all tasks.", type: "functional", priority: "should", acceptance_criteria: [] },
        ],
      },
    }),
  ],
  design: [],
  refinement: [
    art({ id: "refined-classes", kind: "diagram", phase: "refinement", title: "Domain classes", content: { kind: "class" }, text: "@startuml\nclass TaskService {\n  +addTask(title)\n}\n@enduml", covers: ["REQ-001"] }),
  ],
  codegen: [art({ id: "source-service", title: "todo/service.py", content: { path: "todo/service.py", purpose: "Keeps the tasks." }, text: CODE, covers: ["REQ-001"] })],
  testing: [
    art({ id: "test-service", kind: "test_file", phase: "testing", title: "tests/test_service.py", covers: ["REQ-001"] }),
    art({
      id: "test-report",
      kind: "test_report",
      phase: "testing",
      content: {
        tests: [
          { name: "test_req_001_add", classname: "t", outcome: "passed", message: "", requirement: "REQ-001" },
          { name: "test_req_002_list", classname: "t", outcome: "passed", message: "", requirement: "REQ-002" },
        ],
      },
    }),
    art({
      id: "test-strength",
      kind: "test_strength",
      phase: "testing",
      content: { mutants: [{ id: "M1", path: "todo/service.py", line: 3, description: "`return title` became `return None`", outcome: "caught", tests: ["test_req_001_add"], requirements: ["REQ-001"] }] },
    }),
  ],
};

const trace: Trace = {
  covered: { "REQ-001": ["refined-classes", "source-service", "test-service"] },
  uncovered: ["REQ-002"],
  unknown_refs: [],
  ratio: 0.5,
  requirements: [
    { id: "REQ-001", title: "Add a task" },
    { id: "REQ-002", title: "List tasks" },
  ],
  artifacts: [
    { id: "refined-classes", title: "Domain classes", phase: "refinement", kind: "diagram", covers: ["REQ-001"] },
    { id: "source-service", title: "todo/service.py", phase: "codegen", kind: "source_file", covers: ["REQ-001"] },
    { id: "test-service", title: "tests/test_service.py", phase: "testing", kind: "test_file", covers: ["REQ-001"] },
  ],
  results: { "REQ-001": "passed", "REQ-002": "passed" },
  strength: { caught: 1, survived: 1, invalid: 0, total: 2, score: 0.5, by_requirement: { "REQ-001": 1 } },
};

const phases = ["requirements", "design", "refinement", "codegen", "testing"].map(
  (id): PhaseState => ({ id, title: id === "codegen" ? "Code generation" : id.charAt(0).toUpperCase() + id.slice(1), status: "approved", requires: [], implemented: true, can_run: true, updated_at: "", stale_cause: null }),
);

const view = (opened: string[] = []) => (
  <TraceView
    trace={trace}
    phases={phases}
    busy={false}
    projectId="p"
    onOpenRequirement={(id) => opened.push(id)}
    onOpenArtifact={(id, phase) => opened.push(`${phase}/${id}`)}
    loadArtifacts={async (phase) => store[phase] ?? []}
  />
);

test("the matrix shows how many injected bugs the tests of a requirement caught", () => {
  render(view());
  expect(screen.getByText(/The tests caught 1 of 2 injected bugs\./)).toBeInTheDocument();
  const row = screen.getByRole("row", { name: /REQ-001/ });
  expect(within(row).getByText("1 bug caught")).toHaveAttribute("title", expect.stringContaining("Checked by code"));
  expect(within(screen.getByRole("row", { name: /REQ-002/ })).queryByText(/caught/)).not.toBeInTheDocument();
});

test("a requirement opens as one page: its text, the diagram, the code with marked lines, the tests and caught bugs", async () => {
  // Criterion C5: "pick a requirement and show how it appears in the design and in the code".
  const opened: string[] = [];
  render(view(opened));
  fireEvent.click(screen.getByRole("button", { name: /REQ-001/ }));

  expect(screen.getByRole("heading", { level: 1, name: /REQ-001 Add a task/ })).toBeInTheDocument();
  expect(await screen.findByText("The user adds a task with a title.")).toBeInTheDocument();
  expect(screen.getByText("An empty title is refused.")).toBeInTheDocument();

  // Design: the diagram that covers it (no renderer here, so the source), with the way to its phase.
  expect(screen.getByRole("heading", { level: 3, name: /Domain classes/ })).toBeInTheDocument();
  expect(screen.getByLabelText("PlantUML source of Domain classes")).toHaveTextContent("class TaskService");
  fireEvent.click(screen.getByRole("button", { name: "Open in Refinement" }));

  // Code: path and purpose, the listing folded; lines that define what the diagram names are marked.
  expect(screen.getByText("Keeps the tasks.")).toBeInTheDocument();
  const listing = screen.getByLabelText("Contents of todo/service.py");
  expect(listing.closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText(/2 named in the diagrams/)).toBeInTheDocument();
  expect([...listing.querySelectorAll("[data-mark]")].map((l) => l.textContent?.trim())).toEqual(["1class TaskService:", "2    def add_task(self, title):"]);
  fireEvent.click(screen.getByRole("button", { name: "Open in Code generation" }));

  // Tests: only this requirement's tests, with the latest result, and the bugs they caught.
  const tests = screen.getByRole("list", { name: "Tests of REQ-001, latest run" });
  expect(within(tests).getByText("test_req_001_add")).toBeInTheDocument();
  expect(within(tests).queryByText("test_req_002_list")).not.toBeInTheDocument();
  expect(screen.getByText("1 injected bug caught by these tests.")).toBeInTheDocument();
  expect(screen.getByText(/todo\/service.py line 3/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "tests/test_service.py" }));
  expect(opened).toEqual(["refinement/refined-classes", "codegen/source-service", "testing/test-service"]);
});

test("previous and next step through the requirements, the arrow keys too, and there is a way back", async () => {
  render(view());
  fireEvent.click(screen.getByRole("button", { name: /REQ-001/ }));
  expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  expect(screen.getByText("1 of 2")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("heading", { level: 1, name: /REQ-002 List tasks/ })).toBeInTheDocument();
  expect(await screen.findByText("No diagram covers this requirement.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();

  fireEvent.keyDown(window, { key: "ArrowLeft" });
  expect(screen.getByRole("heading", { level: 1, name: /REQ-001 Add a task/ })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "All requirements" }));
  expect(screen.getByRole("heading", { level: 1, name: "Traceability" })).toBeInTheDocument();
});

test("names are read from PlantUML and matched to definitions, camelCase or snake_case", () => {
  const names = diagramNames("class TaskService {\n +addTask(title)\n}\nCli -> TaskService: list_tasks()");
  expect([...names].sort()).toEqual(["addtask", "listtasks", "taskservice"]);
  expect([...linesNamedInDiagrams(CODE, names)]).toEqual([1, 2]);
  expect(linesNamedInDiagrams(CODE, new Set()).size).toBe(0);
});
