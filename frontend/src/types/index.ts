// ── Message Roles & Status ──────────────────────────────────

export type MessageRole = "interviewer" | "candidate" | "system";

export type InterviewStatus =
  | "idle"
  | "intro"
  | "qa_loop"
  | "wrapup"
  | "done";

export type ConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

// ── WebSocket Message Types ─────────────────────────────────

export type ServerMessageType =
  | "interview.start"
  | "interview.chat"
  | "interview.question"
  | "interview.evaluation"
  | "interview.end"
  | "error";

export type ClientMessageType =
  | "message.chat"
  | "message.answer"
  | "command.skip"
  | "command.repeat";

// ── WebSocket Envelope ──────────────────────────────────────

export interface WSEnvelope {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

// ── Chat Message ────────────────────────────────────────────

export interface QuestionMeta {
  questionId?: string;
  category?: string;
  difficulty?: string;
  questionNumber?: number;
  totalQuestions?: number;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  meta?: QuestionMeta;
}

// ── Server → Client Payloads ────────────────────────────────

export interface StartPayload {
  session_id: string;
  job_title: string;
  total_questions: number;
  duration_minutes: number;
}

export interface ChatPayload {
  content: string;
}

export interface QuestionPayload {
  question_id: string;
  content: string;
  category: string;
  difficulty: string;
  question_number: number;
  total_questions: number;
}

export interface EvaluationPayload {
  feedback: string;
}

export interface EndPayload {
  session_id: string;
  message: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

// ── REST Types ──────────────────────────────────────────────

export interface CreateSessionRequest {
  candidate_name: string;
  job_title: string;
  experience_level: string;
  key_skills: string[];
  interview_language: string;
}

export interface CreateSessionResponse extends SessionResponse {
  admin_token: string;
  candidate_token: string;
}

export interface SessionResponse {
  id: string;
  candidate_name: string;
  job_title: string;
  experience_level: string;
  interview_language: string;
  status: string;
  current_question_index: number;
  total_questions: number;
  started_at: string;
  completed_at: string | null;
}

export interface AnswerReport {
  question_text: string;
  category: string;
  difficulty: string;
  order_index: number;
  status: string;
  answer_content: string | null;
  score: number | null;
  score_comment: string | null;
}

export interface SessionReport {
  session_id: string;
  candidate_name: string;
  job_title: string;
  experience_level: string;
  status: string;
  total_questions: number;
  answered_count: number;
  average_score: number | null;
  answers: AnswerReport[];
  started_at: string;
  completed_at: string | null;
}
