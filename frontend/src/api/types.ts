// Mirrors the JSON returned by backend/src/wings/api (dto.py and app.py).

export type PhaseStatus = "locked" | "ready" | "needs_input" | "draft" | "approved" | "stale";

export interface JsonSchemaProperty {
  type?: string;
  description?: string;
  default?: unknown;
  minLength?: number;
}

export interface ActionInfo {
  name: string;
  label: string;
  description: string;
  input_schema: { properties?: Record<string, JsonSchemaProperty>; required?: string[] };
  message_field: string | null;
}

export interface AgentInfo {
  name: string;
  role: string;
  tier: string;
}

export interface PhaseInfo {
  id: string;
  title: string;
  summary: string;
  requires: string[];
  implemented: boolean;
  actions: ActionInfo[];
  agents: AgentInfo[];
}

export interface PhaseState {
  id: string;
  title: string;
  status: PhaseStatus;
  requires: string[];
  implemented: boolean;
  can_run: boolean;
  updated_at: string;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  phases: PhaseState[];
}

export interface Artifact {
  id: string;
  kind: "requirements" | "diagram" | string;
  phase: string;
  title: string;
  revision: number;
  content: Record<string, any>;
  text: string | null;
  path: string | null;
  defines: string[];
  covers: string[];
  author: string;
  retired: boolean;
  created_at: string;
}

export interface Question {
  id: string;
  question: string;
  why: string;
  options: string[];
}

export interface Message {
  phase: string;
  role: "developer" | "agent" | "system";
  text: string;
  author: string;
  data: { questions?: Question[]; coverage?: Coverage; [key: string]: unknown };
  created_at: string;
}

export interface ActivityEvent {
  seq: number;
  at: string;
  kind: string;
  phase: string | null;
  summary: string;
  data: Record<string, unknown>;
}

export interface Coverage {
  covered: Record<string, string[]>;
  uncovered: string[];
  unknown_refs: string[];
  ratio: number;
}

export interface Health {
  ok: boolean;
  llm_provider: string;
  models: Record<string, string>;
  renderer: boolean;
  workspace_dir: string;
}

export interface ActionResult {
  project: Project;
  reply: string | null;
  artifacts: Artifact[];
  data: Record<string, unknown>;
  stale: string[];
}

export interface RequirementItem {
  id: string;
  title: string;
  description: string;
  type: "functional" | "non_functional";
  priority: "must" | "should" | "could";
  acceptance_criteria: string[];
}
