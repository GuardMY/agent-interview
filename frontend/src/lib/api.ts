import { API_BASE } from "./constants";
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  SessionResponse,
  SessionReport,
  ResumeUploadResponse,
} from "@/types";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const { headers: optHeaders, ...restOpts } = options || {};
  const hasBody = !!restOpts.body;

  const headers: Record<string, string> = {};
  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }
  if (optHeaders) {
    Object.assign(headers, optHeaders);
  }

  const res = await fetch(`${API_BASE}${url}`, { ...restOpts, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function createSession(
  data: CreateSessionRequest
): Promise<CreateSessionResponse> {
  return request<CreateSessionResponse>("/api/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getSession(
  sessionId: string,
  candidateToken: string
): Promise<SessionResponse> {
  return request<SessionResponse>(
    `/api/sessions/${sessionId}?token=${encodeURIComponent(candidateToken)}`
  );
}

export async function getSessionReport(
  sessionId: string,
  adminToken: string
): Promise<SessionReport> {
  return request<SessionReport>(`/api/sessions/${sessionId}/report`, {
    headers: { "X-Admin-Token": adminToken },
  });
}

export async function deleteSession(
  sessionId: string,
  adminToken: string
): Promise<void> {
  return request<void>(`/api/sessions/${sessionId}`, {
    method: "DELETE",
    headers: { "X-Admin-Token": adminToken },
  });
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return request("/health");
}

// ── Resume ─────────────────────────────────────────────────

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  // Bypass the request() helper — must NOT set Content-Type for multipart
  const res = await fetch(`${API_BASE}/api/resumes/parse`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function getResume(
  sessionId: string,
  adminToken: string
): Promise<ResumeUploadResponse> {
  return request<ResumeUploadResponse>(
    `/api/sessions/${sessionId}/resume`,
    { headers: { "X-Admin-Token": adminToken } }
  );
}
