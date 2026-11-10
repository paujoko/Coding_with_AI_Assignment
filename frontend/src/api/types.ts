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

/** The agent action in progress (API 7), so a reloaded page waits instead of sending again. */
export interface RunningAction {
  phase: string;
  action: string;
  label: string;
  started_at: string; // ISO time, UTC
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  phases: PhaseState[];
  running?: RunningAction | null; // API 7
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

/** A step an agent proposes after its answer: run `action` of `phase` with `input` (e.g. send a fix to code generation). */
export interface NextAction {
  label: string;
  phase: string;
  action: string;
  input: Record<string, unknown>;
}

export interface Message {
  phase: string;
  role: "developer" | "agent" | "system";
  text: string;
  author: string;
  data: {
    summary?: string;
    questions?: Question[];
    attachments?: AttachmentRef[];
    next_actions?: NextAction[];
    [key: string]: unknown;
  };
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
  results?: Record<string, Verdict>; // requirement id -> worst outcome of its tests in the latest run (API 6), or a declared gap (API 7)
}

export type TestOutcome = "passed" | "failed" | "error" | "skipped";
/** What counts per requirement: a test outcome, or a gap an agent declared ("partial": tests check only part of it,
 * "not_met": the code does not do it as asked). Only "passed" means verified. */
export type Verdict = TestOutcome | "partial" | "not_met";

export const VERDICT_LABEL: Record<string, string> = { partial: "partly tested", not_met: "not met" };

/** A requirement an agent says the code does not meet or the tests do not fully check (artifact kind known_gaps). */
export interface Gap {
  requirement: string;
  reason: string;
}

// Contents of the artifacts of P3 to P7 (backend/src/wings/phases/*/module.py).

export interface Finding {
  id: string;
  severity: "high" | "medium" | "low";
  diagram: string;
  finding: string;
  suggestion: string;
  source: "reviewer" | "check";
  status: "open" | "applied";
}

export interface TestRun {
  name: string;
  classname: string;
  outcome: TestOutcome;
  message: string;
  requirement: string | null;
}

export interface RequirementProgress {
  id: string;
  title: string;
  design: boolean;
  code: boolean;
  tests: boolean;
  result: Verdict | null;
  verified: boolean;
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
