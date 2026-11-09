import { render, screen } from "@testing-library/react";
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

const props = { projectId: "p", diagrams: [diagram], trace: null, canRender: false, focus: null, onOpenRequirement: () => {}, onOpenTrace: () => {}, onSave: async () => {} };

test("links to requirements wait while an agent works", () => {
  // Review finding 1 (s02): following a link mid-request showed the old phase's data in the new one.
  const { rerender } = render(<DesignView {...props} busy />);
  expect(screen.getByRole("button", { name: "REQ-001" })).toBeDisabled();
  rerender(<DesignView {...props} busy={false} />);
  expect(screen.getByRole("button", { name: "REQ-001" })).toBeEnabled();
});
