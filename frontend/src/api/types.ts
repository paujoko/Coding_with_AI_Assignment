// Mirrors the JSON returned by backend/src/wings/api (dto.py and app.py).

export type PhaseStatus = "locked" | "ready" | "needs_input" | "draft" | "approved" | "stale";

export interface JsonSchemaProperty {
  type?: "string" | "integer" | "number" | "boolean" | "array" | "object";
  description?: string;
  default?: unknown;
  minLength?: number;
  enum?: unknown[];
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
  stale_cause: string | null; // the upstream phase whose change made this one stale
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

/** An uploaded document (POST /projects/{id}/attachments). Its text is what the agents read. */
export interface Attachment {
  id: string;
  name: string;
  media_type: string;
  size: number; // bytes of the original file
  chars: number; // characters of extracted text
  created_at: string;
}

export interface AttachmentRef {
  id: string;
  name: string;
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
  data: { summary?: string; questions?: Question[]; attachments?: AttachmentRef[]; [key: string]: unknown };
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

export interface TraceArtifact {
  id: string;
  title: string;
  phase: string;
  kind: string;
  covers: string[];
}

/** GET /projects/{id}/trace: deterministic coverage plus the titles needed to read it. */
export interface Trace {
  covered: Record<string, string[]>; // requirement id -> artifact ids covering it
  uncovered: string[];
  unknown_refs: string[];
  ratio: number;
  requirements: { id: string; title: string }[];
  artifacts: TraceArtifact[];
}

export interface Health {
  ok: boolean;
  api_version?: number; // missing on backends older than session s02
  llm_ready?: boolean; // false: a paid provider is chosen but has no key yet
  settings?: boolean; // the backend offers the Settings page
  llm_provider: string;
  models: Record<string, string>;
  renderer: boolean;
  renderer_mode?: "jar" | "server" | null;
  workspace_dir: string;
}

export type Provider = "mock" | "openai" | "openrouter";
export type Models = Record<"small" | "mid" | "frontier", string>;

/** GET /settings. Keys never come back, only whether one is saved and its last characters. */
export interface LlmSettings {
  provider: Provider;
  providers: Provider[];
  ready: boolean;
  key_set: boolean;
  key_hint: string | null;
  keys: Record<"openai" | "openrouter", { set: boolean; hint: string | null }>;
  models: Models;
  defaults: Record<"openai" | "openrouter", Models>;
  env_file: string;
}

/** GET /settings/diagrams: how PlantUML diagrams become pictures. */
export interface DiagramSettings {
  mode: "jar" | "server" | null;
  java: boolean;
  jar_path: string | null;
  server_url: string | null;
  public_server: string;
}

export interface ConnectionTest {
  ok: boolean;
  message?: string;
  error?: string;
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
