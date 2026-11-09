import type { ActionResult, ActivityEvent, Artifact, Health, Message, PhaseInfo, Project, Trace } from "./types";

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

const post = <T>(path: string, body?: unknown) => call<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => call<Health>("/health"),
  phases: () => call<PhaseInfo[]>("/phases"),
  projects: () => call<Project[]>("/projects"),
  createProject: (name: string) => post<Project>("/projects", { name }),
  project: (id: string) => call<Project>(`/projects/${id}`),
  run: (id: string, phase: string, action: string, input: Record<string, unknown>) =>
    post<ActionResult>(`/projects/${id}/phases/${phase}/actions/${action}`, { input }),
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
  trace: (id: string) => call<Trace>(`/projects/${id}/trace`),
};
