import type { ActionInfo } from "../api/types";

// The design wing's generate action as the backend describes it (GenerateInput's JSON schema).
export const DESIGN_GENERATE: ActionInfo = {
  name: "generate",
  label: "Generate design",
  description: "",
  message_field: "guidance",
  input_schema: {
    properties: {
      kinds: {
        type: "array",
        description: "Diagrams to draw",
        items: { type: "string", enum: ["use_case", "class", "sequence", "activity", "component", "deployment", "state"] },
        default: ["use_case", "class", "sequence"],
        minItems: 1,
        option_hints: { class: "The parts of the program; the code is checked against it" },
      },
      level: { type: "string", description: "How detailed", enum: ["simple", "detailed"], default: "simple", option_hints: { simple: "Fast." } },
      guidance: { type: "string", description: "Optional: anything the architect should take into account", default: "" },
    },
  },
};
