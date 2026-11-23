import type {
  ActionResult,
  ActivityEvent,
  Artifact,
  Attachment,
  Change,
  CatchUpResult,
  ChangeAdvance,
  ConnectionTest,
  DesignCheck,
  DiagramSettings,
  FolderImport,
  FolderStatus,
  Health,
  LlmSettings,
  Message,
  Models,
  PickedFolder,
  PhaseInfo,
  Project,
  Provider,
  Trace,
} from "./types";

// The backend API version this interface is built for (backend/src/wings/api/app.py: API_VERSION).
export const API_VERSION = 10;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc ?? []).join(".")}: ${d.msg}`).join("; ");
  return "The server returned an error without details.";
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "The backend is not reachable. Start it on port 8810.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, describe(body.detail));
  }
  return res.json() as Promise<T>;
}

// File -> base64 without the "data:...;base64," prefix (the API takes JSON, see backend dto.AttachmentUpload).
function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(new ApiError(0, `${file.name} could not be read.`));
    reader.readAsDataURL(file);
  });
}

const post = <T>(path: string, body?: unknown) => call<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

// A change as the views read it: every list and nested object is there, whatever the backend left out.
function fillChange(c: Partial<Change>): Change {
  const progress: Partial<Change["progress"]> = c.progress ?? {};
  const phases = (progress.phases ?? []).map((p) => ({ ...p, title: p.title ?? p.phase, state: p.state ?? "waiting", updated: p.updated ?? false }));
  const next = c.next ? { ...c.next, title: c.next.title ?? c.next.phase, label: c.next.label ?? "", input: c.next.input ?? {}, steps: c.next.steps ?? [], reason: c.next.reason ?? null, action: c.next.action ?? null } : null;
  return {
    number: c.number ?? 0,
    artifact_id: c.artifact_id ?? `change-${c.number ?? 0}`,
    kind: c.kind ?? "change",
    request: c.request ?? "",
    summary: c.summary ?? "",
    affected: c.affected ?? [],
    state: c.state ?? "open",
    started_at: c.started_at ?? null,
    completed_at: c.completed_at ?? null,
    progress: {
      phases,
      current: progress.current ?? null,
      started: progress.started ?? false,
      complete: progress.complete ?? false,
      done: progress.done ?? phases.filter((p) => p.state === "done").length,
      total: progress.total ?? phases.filter((p) => p.state !== "untouched").length,
    },
    next,
    receipt: (c.receipt ?? []).map((r) => ({ ...r, title: r.title ?? r.phase, updated: r.updated ?? [], added: r.added ?? [], removed: r.removed ?? [] })),
  };
}

export const api = {
  health: () => call<Health>("/health"),
  phases: () => call<PhaseInfo[]>("/phases"),
  projects: () => call<Project[]>("/projects"),
  createProject: (name: string, folder?: string) => post<Project>("/projects", { name, folder: folder?.trim() || null }),
  // The project's folder on the developer's computer (ADR 0015).
  folder: (id: string) => call<FolderStatus>(`/projects/${id}/folder`),
  setFolder: (id: string, path: string | null) =>
    call<FolderStatus>(`/projects/${id}/folder`, { method: "PUT", body: JSON.stringify({ path }) }),
  importFolder: (id: string, paths?: string[]) => post<FolderImport>(`/projects/${id}/folder/import`, { paths: paths ?? null }),
  restoreFolder: (id: string, paths: string[]) => post<FolderStatus>(`/projects/${id}/folder/restore`, { paths }),
  designCheck: (id: string) => call<DesignCheck>(`/projects/${id}/design-check`),
  // Opens the folder dialog on the computer the backend runs on; waits until the developer has chosen.
  pickFolder: (start: string, name: string) => post<PickedFolder>("/system/pick-folder", { start: start.trim() || null, name }),
  // Where a new project with this name would be saved by default. Older backends do not have it: callers treat a failure as "no suggestion".
  defaultFolder: (name: string) => call<{ path: string }>(`/system/default-folder?name=${encodeURIComponent(name)}`),
  project: (id: string) => call<Project>(`/projects/${id}`),
  run: (id: string, phase: string, action: string, input: Record<string, unknown>, attachments: string[] = []) =>
    post<ActionResult>(`/projects/${id}/phases/${phase}/actions/${action}`, { input, attachments }),
  settings: () => call<LlmSettings>("/settings"),
  saveSettings: (provider: Provider, apiKey: string, models: Models | null) =>
    call<LlmSettings>("/settings/llm", { method: "PUT", body: JSON.stringify({ provider, api_key: apiKey || null, models }) }),
  testSettings: () => post<ConnectionTest>("/settings/llm/test"),
  diagramSettings: () => call<DiagramSettings>("/settings/diagrams"),
  usePublicServer: (enabled: boolean) =>
    call<DiagramSettings>("/settings/diagrams", { method: "PUT", body: JSON.stringify({ public_server: enabled }) }),
  downloadPlantuml: () => post<DiagramSettings>("/settings/diagrams/download"),
  attachments: (id: string) => call<Attachment[]>(`/projects/${id}/attachments`),
  upload: async (id: string, file: File): Promise<Attachment> =>
    post<Attachment>(`/projects/${id}/attachments`, { name: file.name, media_type: file.type, content_base64: await toBase64(file) }),
  approve: (id: string, phase: string) => post<Project>(`/projects/${id}/phases/${phase}/approve`),
  reopen: (id: string, phase: string) => post<Project>(`/projects/${id}/phases/${phase}/reopen`),
  artifacts: (id: string, phase: string) => call<Artifact[]>(`/projects/${id}/artifacts?phase=${phase}`),
  updateArtifact: (id: string, artifactId: string, body: { content?: unknown; text?: string }) =>
    call<{ artifact: Artifact; stale: string[]; project: Project }>(`/projects/${id}/artifacts/${artifactId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  svgUrl: (id: string, artifactId: string, revision: number) => `/api/projects/${id}/artifacts/${artifactId}/svg?r=${revision}`,
  messages: (id: string, phase: string) => call<Message[]>(`/projects/${id}/messages?phase=${phase}`),
  events: (id: string, after: number) => call<ActivityEvent[]>(`/projects/${id}/events?after=${after}`),
  // Changes carried through the phases (API 9), newest first. A backend without the route has none to show.
  changes: async (id: string): Promise<Change[]> => {
    const found = await call<Partial<Change>[]>(`/projects/${id}/changes`).catch(() => []);
    return Array.isArray(found) ? found.map(fillChange) : [];
  },
  // One phase further per call; it can take minutes with a real model. A stop is an answer (`stopped_reason`), not an error.
  advanceChange: async (id: string, number: number, approve: boolean): Promise<ChangeAdvance> => {
    const r = await post<Partial<ChangeAdvance>>(`/projects/${id}/changes/${number}/advance`, { approve });
    if (!r.project || !r.change) throw new ApiError(0, "The backend answered without the change. Restart it and try again.");
    return { project: r.project, change: fillChange(r.change), ran: r.ran ?? [], approved: r.approved ?? null, stopped_reason: r.stopped_reason ?? null };
  },
  // API 10: updates the FIRST out-of-date phase (runs its own refresh, approves it when its code checks pass and `approve`
  // is true). One phase per call; 409 while an agent works. A stop is an answer (`stopped_reason`), not an error.
  catchUp: async (id: string, approve = true): Promise<CatchUpResult> => {
    const r = await post<Partial<CatchUpResult>>(`/projects/${id}/catch-up`, { approve });
    if (!r.project) throw new ApiError(0, "The backend answered without the project. Restart it and try again.");
    const remaining = r.remaining ?? r.project.stale ?? [];
    return { project: r.project, ran: r.ran ?? [], approved: r.approved ?? null, stopped_reason: r.stopped_reason ?? null, remaining, done: r.done ?? remaining.length === 0 };
  },
  // Filled with defaults so an older backend can never crash the views.
  trace: async (id: string): Promise<Trace> => {
    const t = await call<Partial<Trace>>(`/projects/${id}/trace`);
    return {
      covered: t.covered ?? {},
      uncovered: t.uncovered ?? [],
      unknown_refs: t.unknown_refs ?? [],
      ratio: t.ratio ?? 0,
      requirements: t.requirements ?? [],
      artifacts: t.artifacts ?? [],
      results: t.results ?? {},
      strength: t.strength, // undefined on a backend without the field, null when out of date or never run
    };
  },
};
