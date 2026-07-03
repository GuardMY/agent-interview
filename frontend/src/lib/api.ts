import { API_BASE } from "./constants";
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  InterviewTemplate,
  JobPosition,
  JobPositionListResponse,
  SessionListResponse,
  SessionResponse,
  SessionReport,
} from "@/types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
  }
}

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
    throw new ApiError(res.status, detail.detail || `HTTP ${res.status}`);
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
    `/api/sessions${qs ? `?${qs}` : ""}`
  );
}

export async function getTemplates(): Promise<InterviewTemplate[]> {
  return request<InterviewTemplate[]>("/api/templates");
}

// ── Position APIs ────────────────────────────────────────

export async function listPositions(
  params?: {
    page?: number;
    size?: number;
    level?: string;
    status?: string;
    q?: string;
  }
): Promise<JobPositionListResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.size) query.set("size", String(params.size));
  if (params?.level) query.set("level", params.level);
  if (params?.status) query.set("status", params.status);
  if (params?.q) query.set("q", params.q);
  const qs = query.toString();
  return request<JobPositionListResponse>(
    `/api/positions${qs ? `?${qs}` : ""}`
  );
}

export async function getPosition(
  positionId: string
): Promise<JobPosition> {
  return request<JobPosition>(`/api/positions/${positionId}`);
}

export async function createPosition(
  data: Record<string, unknown>
): Promise<JobPosition> {
  return request<JobPosition>("/api/positions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePosition(
  positionId: string,
  data: Record<string, unknown>
): Promise<JobPosition> {
  return request<JobPosition>(`/api/positions/${positionId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function archivePosition(
  positionId: string
): Promise<void> {
  return request<void>(`/api/positions/${positionId}`, {
    method: "DELETE",
  });
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return request("/health");
}

// ── Resume Upload ──────────────────────────────────────────

export interface ResumeUploadResponse {
  session_id: string;
  status: string;
  resume_text_length: number;
  profile: Record<string, unknown> | null;
  message: string;
}

export async function uploadResume(
  sessionId: string,
  file: File,
  adminToken: string
): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/resume`, {
    method: "POST",
    headers: { "X-Admin-Token": adminToken },
    body: formData,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, detail.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
