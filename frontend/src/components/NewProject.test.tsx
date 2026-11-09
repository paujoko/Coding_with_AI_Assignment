import { nameFrom } from "./NewProject";

test("a project is named after the first clause of its description", () => {
  expect(nameFrom("A small to-do app for a team: tasks with a due date")).toBe("Small to-do app");
  expect(nameFrom("A command-line expense tracker that groups spending")).toBe("Command-line expense tracker");
  expect(nameFrom("  room booking. With calendars")).toBe("Room booking");
  expect(nameFrom("   ")).toBe("New project");
});
