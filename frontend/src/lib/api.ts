import { API_BASE } from "./constants";
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  InterviewTemplate,
  SessionListResponse,
  SessionResponse,
  SessionReport,
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
    throw new Error(detail.detail || `HTTP ${res.status}`);
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

export async function getCandidateReport(
  sessionId: string,
  candidateToken: string
): Promise<SessionReport> {
  return request<SessionReport>(
    `/api/sessions/${sessionId}/candidate-report?token=${encodeURIComponent(candidateToken)}`
  );
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

export async function listSessions(
  masterToken: string,
  params?: {
    page?: number;
    size?: number;
    status?: string;
    date_from?: string;
    date_to?: string;
  }
): Promise<SessionListResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.size) query.set("size", String(params.size));
  if (params?.status) query.set("status", params.status);
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  const qs = query.toString();
  return request<SessionListResponse>(
    `/api/sessions${qs ? `?${qs}` : ""}`,
    { headers: { "X-Admin-Token": masterToken } }
  );
}

export async function getTemplates(): Promise<InterviewTemplate[]> {
  return request<InterviewTemplate[]>("/api/templates");
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return request("/health");
}
