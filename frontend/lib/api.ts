/**
 * Typed client for the Duck backend. Every shape here mirrors a Pydantic
 * schema one-to-one — see backend/app/schemas/{repo,session}.py. If a field
 * changes on the backend, change it here in the same commit.
 */
import type { SessionPhase } from "./events";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Duck's backend isn't reachable right now. Check your connection and try again.");
  }

  if (!response.ok) {
    let detail = "Something went wrong talking to Duck's backend.";
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body (e.g. a raw 502/504 from the host) — keep the generic message
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// ---- repos -----------------------------------------------------------------

export interface RepoOut {
  id: string;
  github_url: string;
  owner: string;
  name: string;
  default_branch: string;
}

export interface RepoConnectResponse {
  repo: RepoOut;
  file_count: number;
  total_size_bytes: number;
  languages: Record<string, number>;
  reused_cached_copy: boolean;
}

export function getRepo(repoId: string): Promise<RepoOut> {
  return request<RepoOut>(`/repos/${repoId}`);
}

export function connectRepo(githubUrl: string): Promise<RepoConnectResponse> {
  return request<RepoConnectResponse>("/repos/connect", {
    method: "POST",
    body: JSON.stringify({ github_url: githubUrl }),
  });
}

export interface RepoFileContentOut {
  path: string;
  content: string;
  total_lines: number;
}

export function getFileContent(repoId: string, path: string): Promise<RepoFileContentOut> {
  const params = new URLSearchParams({ path });
  return request<RepoFileContentOut>(`/repos/${repoId}/file-content?${params.toString()}`);
}

// ---- sessions ----------------------------------------------------------------

export type SessionStatus = "active" | "resolved" | "abandoned";
export type MessageRole = "user" | "assistant";
export type HypothesisConfidence = "low" | "medium" | "high";

export interface SessionCreateResponse {
  session_id: string;
  title: string;
}

export interface MessageOut {
  role: MessageRole;
  phase_at_time: SessionPhase;
  content: string;
  created_at: string;
}

export interface EvidenceItem {
  file_path: string;
  line_number: number;
  note: string;
}

export interface HypothesisOut {
  id: string;
  description: string;
  evidence: EvidenceItem[] | null;
  confidence: HypothesisConfidence;
  confirmed: boolean | null;
  created_at: string;
}

export interface FixOut {
  id: string;
  file_path: string;
  diff_text: string;
  explanation: string;
  accepted: boolean | null;
  created_at: string;
}

export interface SessionStateResponse {
  id: string;
  repo_id: string;
  title: string | null;
  status: SessionStatus;
  current_phase: SessionPhase;
  resolution_summary: string | null;
  root_cause: string | null;
  tags: string[];
  words_spoken_count: number;
  created_at: string;
  updated_at: string;
  messages: MessageOut[];
  hypotheses: HypothesisOut[];
  fixes: FixOut[];
}

export function createSession(repoId: string, message: string): Promise<SessionCreateResponse> {
  return request<SessionCreateResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId, message }),
  });
}

export function getSession(sessionId: string): Promise<SessionStateResponse> {
  return request<SessionStateResponse>(`/sessions/${sessionId}`);
}

export function sendMessage(sessionId: string, message: string): Promise<{ status: string }> {
  return request(`/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function acceptFix(sessionId: string, fixId: string, feedback?: string): Promise<{ status: string }> {
  return request(`/sessions/${sessionId}/fixes/${fixId}/accept`, {
    method: "POST",
    body: JSON.stringify({ feedback: feedback ?? null }),
  });
}

export function rejectFix(sessionId: string, fixId: string, feedback?: string): Promise<{ status: string }> {
  return request(`/sessions/${sessionId}/fixes/${fixId}/reject`, {
    method: "POST",
    body: JSON.stringify({ feedback: feedback ?? null }),
  });
}

export function getStreamUrl(sessionId: string): string {
  return `${API_URL}/sessions/${sessionId}/stream`;
}

export function getApiUrl(): string {
  return API_URL;
}
