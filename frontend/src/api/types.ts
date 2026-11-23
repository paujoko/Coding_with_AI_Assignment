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

/** The developer's own folder for a project (API 8, ADR 0015). */
export interface ProjectFolder {
  path: string; // absolute path on the developer's computer
  synced_at: string | null; // when Wings last wrote to it
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  phases: PhaseState[];
  running?: RunningAction | null; // API 7
  folder?: ProjectFolder | null; // API 8
  open_change?: OpenChange | null; // API 9: the change being carried through the phases
}

/** The newest change while it is open (API 9). `next_phase` is null only in the moment before it is closed. */
export interface OpenChange {
  number: number;
  done: number;
  total: number;
  next_phase: string | null;
}

// Changes carried through the phases (API 9, backend domain/change.py). Everything here is computed by code.

export type ChangeKind = "change" | "bug" | "new_requirement";
export type ChangeState = "open" | "complete" | "dropped";
/** done: changed and approved again. current: the phase to act on. waiting: behind it. untouched: not moved by this change. */
export type ChangePhaseState = "done" | "current" | "waiting" | "untouched";

export interface ChangePhase {
  phase: string;
  title: string;
  state: ChangePhaseState;
  status: PhaseStatus;
  updated: boolean; // at least one artifact of the phase differs from the baseline
}

export interface ChangeProgress {
  phases: ChangePhase[];
  current: string | null;
  started: boolean;
  complete: boolean;
  done: number;
  total: number;
}

export interface ChangeStep {
  phase: string;
  action: string;
  label: string;
  input: Record<string, unknown>;
}

/** What happens next in the current phase. run: `steps` in order. approve: the gate is open.
 * input: the agent asked questions. blocked: `reason` says what the developer must do. */
export interface ChangeNext {
  phase: string;
  title: string;
  kind: "run" | "approve" | "input" | "blocked";
  action: string | null;
  label: string;
  input: Record<string, unknown>;
  steps: ChangeStep[];
  reason: string | null;
}

export interface ReceiptEntry {
  id: string;
  title: string;
  kind: string;
  path: string | null;
  before: number | null; // revision when the change was requested; null: added by the change
  after: number | null;
  changed: boolean; // false: written again with the same text and content
}

export interface ReceiptPhase {
  phase: string;
  title: string;
  updated: ReceiptEntry[];
  added: ReceiptEntry[];
  removed: ReceiptEntry[];
}

/** One element of GET /projects/{id}/changes. */
export interface Change {
  number: number;
  artifact_id: string;
  kind: ChangeKind | string;
  request: string;
  summary: string;
  affected: string[];
  state: ChangeState;
  started_at: string | null;
  completed_at: string | null;
  progress: ChangeProgress;
  next: ChangeNext | null;
  receipt: ReceiptPhase[];
}

export interface ChangeRan {
  phase: string;
  action: string;
  label: string;
  status: PhaseStatus | string;
  reply: string | null;
}

/** POST /projects/{id}/changes/{n}/advance: one phase further. `stopped_reason` null: the next call can go on. */
export interface ChangeAdvance {
  project: Project;
  change: Change;
  ran: ChangeRan[];
  approved: string | null;
  stopped_reason: string | null;
}

/** A file in the folder that differs from what Wings last wrote there (backend domain/sync.py). */
export interface FolderChange {
  path: string; // inside the folder, forward slashes
  change: "modified" | "added" | "deleted";
  artifact_id: string | null;
  phase: string | null;
  importable: boolean;
  newer_in_wings: boolean; // Wings made a newer revision since: importing replaces it, restoring loses the edit
  note: string;
}

export interface FolderStatus {
  path: string | null;
  exists: boolean;
  changes: FolderChange[];
  problem: string | null;
  project?: Project; // PUT /folder returns the project too
}

/** POST /system/pick-folder: the folder chosen in the operating system's dialog (null: cancelled). */
export interface PickedFolder {
  path: string | null;
  empty: boolean;
  suggested: string | null; // a subfolder named after the project, when the chosen folder already has files
}

/** GET /projects/{id}/design-check: the current class diagram against the current code, computed by code. */
export interface DesignCheck {
  checked: boolean; // false while there is no class diagram or no code
  diagram?: string;
  in_sync?: boolean;
  lines?: string[];
}

export interface FolderImport {
  project: Project;
  imported: FolderChange[];
  skipped: FolderChange[];
  stale: string[];
  drift: string[]; // design versus code after the import, checked by code
  reply: string;
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
    speaker?: string; // set when no agent wrote the message (e.g. the folder sync); shown instead of the agent's name
    drift?: string[]; // design versus code when the message was written; its next steps are moot once they agree
    change?: number; // API 9: the number of the change request this answer created
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
  strength?: StrengthCounts | null; // the latest injected-bug check; null when out of date or never run, missing on older backends
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

/** Counts of the injected-bug check (P5 `probe`, backend domain/mutation.py). */
export interface StrengthCounts {
  caught: number;
  survived: number;
  invalid: number;
  total: number;
  score: number | null; // caught / (caught + survived); null when nothing could be judged
  by_requirement: Record<string, number>; // REQ id -> bugs caught by a test named after it
}

/** One small bug Wings put into the code, and what the tests did with it (artifact kind test_strength). */
export interface Mutant {
  id: string;
  path: string;
  line: number;
  column?: number;
  operator: string;
  description: string;
  original: string; // the line as written
  mutated: string; // the same line with the bug
  outcome: "caught" | "survived" | "invalid";
  tests: string[]; // the tests that failed (caught only)
  requirements: string[];
  reason: string; // why a run did not count (invalid only)
  seconds?: number;
}

/** How to start the generated program from the project folder (artifact `run-guide`, kind run_guide). */
export interface RunGuide {
  start_command: string; // may be empty
  url: string | null; // web apps: where to open it
  example_commands: string[];
  stop_hint: string;
  checked: boolean; // the deployment check started exactly this program
  derived: boolean; // derived from the smoke command by code
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
  folder_picker?: boolean; // the backend can open the operating system's folder dialog
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
