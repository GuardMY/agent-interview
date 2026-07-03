// ── Message Roles & Status ──────────────────────────────────

export type MessageRole = "interviewer" | "candidate" | "system";

export type InterviewStatus =
  | "idle"
  | "intro"
  | "qa_loop"
  | "wrapup"
  | "paused"
  | "done"
  // P2: Multi-phase strategy states
  | "strategy_gen"
  | "ice_break"
  | "project_deep_dive"
  | "technical_assessment"
  | "behavioral"
  | "candidate_qa";

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
  | "error"
  // P2: New message types
  | "interview.phase_change"
  | "interview.follow_up"
  | "interview.position_context"
  | "interview.strategy_ready";

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
  // P2: Phase-aware metadata
  phase?: string;
  isFollowUp?: boolean;
  parentQuestionId?: string;
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
  position_id?: string | null;
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
  position_id: string | null;
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

// ── P2: Phase & Follow-up Payloads ─────────────────────────

export interface PhaseChangePayload {
  from_phase: string;
  to_phase: string;
  phase_index: number;
  total_phases: number;
  phase_description: string;
  position_context: string;
}

export interface FollowUpPayload {
  question_id: string;
  parent_question_id: string;
  content: string;
  category: string;
  difficulty: string;
  depth: number;
  question_number: number;
  total_questions: number;
}

export interface PositionContextPayload {
  position_title: string;
  focus_areas: string[];
  phase_relevance: string;
}

export interface StrategyReadyPayload {
  strategy_summary: string;
  phases_count: number;
  phase_names: string[];
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

// ── Job Position Types ──────────────────────────────────────

export interface SkillRequirement {
  skill: string;
  min_years: number;
  level: string;
}

export interface JobPosition {
  id: string;
  title: string;
  department: string;
  level: string;
  status: string;
  description: string | null;
  responsibilities: string[];
  required_skills: SkillRequirement[];
  preferred_skills: SkillRequirement[];
  soft_skill_requirements: Record<string, string>;
  domain_knowledge: string[] | null;
  default_total_questions: number;
  default_duration_minutes: number;
  interview_focus_areas: string[];
  created_at: string;
  updated_at: string;
}

export interface JobPositionListItem {
  id: string;
  title: string;
  department: string;
  level: string;
  status: string;
  default_total_questions: number;
  default_duration_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface JobPositionListResponse {
  items: JobPositionListItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
