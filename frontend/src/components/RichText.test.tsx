import { render } from "@testing-library/react";
import type { PhaseInfo, PhaseState } from "../api/types";
import { preferredAction } from "./PhaseWorkspace";
import { blocks, RichText } from "./RichText";

// Ben's message to code generation (session s04), as the debugger proposed it.
const fix = 'In todo/cli.py, method `Cli.run`, replace the `list` branch:\n\n    elif command == "list":\n        tasks = self._service.list()\n        if not tasks:\n            self._out("No tasks.")\n\nThis makes `out` contain one entry per task.';

test("an indented fix stays code, with its indentation", () => {
  const b = blocks(fix);
  expect(b.map((x) => x.kind)).toEqual(["p", "code", "p"]);
  expect(b[1]).toEqual({ kind: "code", text: 'elif command == "list":\n    tasks = self._service.list()\n    if not tasks:\n        self._out("No tasks.")' });
  const { container } = render(<RichText text={fix} />);
  expect(container.querySelector("pre.msg-code")?.textContent).toContain('    tasks = self._service.list()');
  expect([...container.querySelectorAll("p code")].map((c) => c.textContent)).toEqual(["Cli.run", "list", "out"]);
});

test("fenced code, lists and plain lines", () => {
  const text = "Design and code disagree (checked by code):\n- Task.archive() is in the code\n- Cli is missing\nPick a direction.\n\n```python\ndef f():\n    return 1\n```";
  expect(blocks(text)).toEqual([
    { kind: "p", lines: ["Design and code disagree (checked by code):"] },
    { kind: "list", items: ["Task.archive() is in the code", "Cli is missing"] },
    { kind: "p", lines: ["Pick a direction."] },
    { kind: "code", text: "def f():\n    return 1" },
  ]);
});

test("ordinary text is unchanged", () => {
  expect(blocks("5 requirements drafted.\nReview them.")).toEqual([{ kind: "p", lines: ["5 requirements drafted.", "Review them."] }]);
});

const action = (name: string, props: Record<string, unknown> = {}, message_field: string | null = null) => ({
  name,
  label: name,
  description: "",
  input_schema: { properties: props },
  message_field,
});
const testing = { id: "testing", actions: [action("generate", { guidance: {} }, "guidance"), action("run"), action("explain"), action("discuss", { question: {} }, "question")] } as unknown as PhaseInfo;
const state = (status: PhaseState["status"]) => ({ status }) as PhaseState;

test("once there are tests, typing does not silently write new ones", () => {
  // Ben typed "run the tests" twice with "Write tests" selected and got new tests both times.
  expect(preferredAction(testing, state("ready"))).toBe("generate");
  expect(preferredAction(testing, state("draft"))).toBe("run");
  expect(preferredAction(testing, state("stale"))).toBe("run");
});
