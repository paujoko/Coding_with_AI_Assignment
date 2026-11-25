import { afterWork, follows, moveWork, noticeFor, type Work } from "./work";

const running: Work = { project: "p", phase: "codegen", state: "running" };
const onCode = { view: "phase", phase: "codegen" } as const;
const onDesign = { view: "phase", phase: "design" } as const;
const onTrace = { view: "trace", phase: "codegen" } as const;

test("the screen follows the work only while the developer looks at the step it works on", () => {
  expect(follows(running, onCode)).toBe(true);
  expect(follows(running, onDesign)).toBe(false);
  expect(follows(running, onTrace)).toBe(false); // the step's id is remembered, but Traceability is on screen
  expect(follows(null, onDesign)).toBe(true); // nothing runs: show() moves the screen as before
});

test("Accept and Redo all move the work to the next step; the developer moves with it only when following", () => {
  expect(moveWork(running, "testing")).toEqual({ ...running, phase: "testing" });
  expect(moveWork(null, "testing")).toBeNull();
});

test("the notice appears on every other screen, never on the working step itself", () => {
  expect(noticeFor(running, onCode)).toBeNull();
  expect(noticeFor(running, onDesign)).toEqual({ phase: "codegen", state: "running" });
  expect(noticeFor(running, onTrace)).toEqual({ phase: "codegen", state: "running" });
  expect(noticeFor(null, onDesign)).toBeNull();
});

test("when the work ends elsewhere Wings does not jump: the notice says the step is ready", () => {
  expect(afterWork(running, true, onDesign)).toEqual({ ...running, state: "ready" });
  expect(afterWork(running, false, onDesign)).toEqual({ ...running, state: "failed" });
  expect(afterWork(running, true, onCode)).toBeNull(); // watched it finish: nothing to point at
  expect(noticeFor({ ...running, state: "ready" }, onDesign)).toEqual({ phase: "codegen", state: "ready" });
});

test("a ready notice goes once the developer opens that step", () => {
  expect(noticeFor({ ...running, state: "ready" }, onCode)).toBeNull();
});
