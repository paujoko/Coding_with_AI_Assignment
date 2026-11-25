import { fireEvent, render, screen } from "@testing-library/react";
import type { Artifact } from "../api/types";
import { DesignView } from "./DesignView";

const diagram: Artifact = {
  id: "diagram-use-cases",
  kind: "diagram",
  phase: "design",
  title: "Use cases",
  revision: 1,
  content: { kind: "use_case", rationale: "" },
  text: "@startuml\n@enduml",
  path: "design/use-cases.puml",
  defines: [],
  covers: ["REQ-001"],
  author: "agent:architect",
  retired: false,
  created_at: "",
};

const props = { projectId: "p", diagrams: [diagram], trace: null, canRender: false, focus: null, onOpenRequirement: () => {}, onOpenTrace: () => {}, onSetupDiagrams: () => {}, onSave: async () => {} };

test("while an agent works the links still open, but the source cannot be edited", () => {
  // Since 2026-11-25 the developer may look at other steps while an agent works (read-only there). Before, links
  // were off (review finding 1, s02: a response for the old step landed in the new one; App now drops those).
  const opened: string[] = [];
  render(<DesignView {...props} busy onOpenRequirement={(id) => opened.push(id)} />);
  fireEvent.click(screen.getByRole("button", { name: "REQ-001" }));
  expect(opened).toEqual(["REQ-001"]);
  expect(screen.getByRole("textbox", { name: /PlantUML source/ })).toHaveAttribute("readonly");
});

test("without a renderer the diagram view offers to set pictures up instead of a dead button", () => {
  let asked = false;
  render(<DesignView {...props} busy={false} onSetupDiagrams={() => (asked = true)} />);
  screen.getByRole("button", { name: "Set up pictures" }).click();
  expect(asked).toBe(true);
});
