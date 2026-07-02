// ── Message Roles & Status ──────────────────────────────────

export type MessageRole = "interviewer" | "candidate" | "system";

export type InterviewStatus =
  | "idle"
  | "intro"
  | "qa_loop"
  | "wrapup"
  | "paused"
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
  | "interview.resume"
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

export interface EvaluationDimensions {
  technical_accuracy: number;
  depth_of_knowledge: number;
  communication: number;
  problem_solving: number;
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
  dimensions?: EvaluationDimensions | null;
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
  dimension_averages?: Record<string, number> | null;
  conversation_transcript?: ConversationEntry[] | null;
}

// ── Dashboard / Session List Types ────────────────────────────

export interface SessionListStats {
  total_count: number;
  active_count: number;
  completed_count: number;
  avg_score: number | null;
  status_breakdown: Record<string, number>;
}

export interface SessionListResponse {
  items: SessionResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
  stats: SessionListStats;
}

// ── Question Bank Types ───────────────────────────────────────

export interface QuestionBankEntry {
  id: string;
  question_text: string;
  category: string;
  difficulty: string;
  expected_keywords: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateQuestionRequest {
  question_text: string;
  category: string;
  difficulty: string;
  expected_keywords: string[];
}

export interface UpdateQuestionRequest {
  question_text?: string;
  category?: string;
  difficulty?: string;
  expected_keywords?: string[];
}

export interface QuestionListResponse {
  items: QuestionBankEntry[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface CategoryListResponse {
  categories: string[];
}

export interface ConversationEntry {
  role: string;
  content: string;
  timestamp: string;
}

export interface InterviewTemplate {
  id: string;
  name: string;
  name_zh: string;
  job_title: string;
  experience_level: string;
  key_skills: string[];
  total_questions: number;
  categories: string[];
}
