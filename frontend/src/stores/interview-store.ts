"use client";

import { create } from "zustand";
import type {
  Message,
  ConnectionState,
  InterviewStatus,
  QuestionMeta,
} from "@/types";

interface InterviewState {
  // ── Session ──
  sessionId: string | null;
  candidateName: string;
  jobTitle: string;
  interviewStatus: InterviewStatus;

  // ── WebSocket ──
  connectionState: ConnectionState;

  // ── Progress ──
  questionIndex: number;
  totalQuestions: number;
  durationMinutes: number;

  // ── Chat ──
  messages: Message[];
  currentQuestionMeta: QuestionMeta | null;
  evaluationFeedback: string | null;
  isWaitingForResponse: boolean; // when AI is "typing"

  // ── Actions ──
  setSession: (
    sessionId: string,
    jobTitle: string,
    totalQuestions: number,
    durationMinutes: number
  ) => void;
  setConnectionState: (state: ConnectionState) => void;
  setInterviewStatus: (status: InterviewStatus) => void;
  addMessage: (msg: Message) => void;
  setCurrentQuestion: (meta: QuestionMeta) => void;
  setEvaluationFeedback: (feedback: string | null) => void;
  setWaitingForResponse: (waiting: boolean) => void;
  incrementQuestionIndex: () => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  candidateName: "",
  jobTitle: "",
  interviewStatus: "idle" as InterviewStatus,
  connectionState: "disconnected" as ConnectionState,
  questionIndex: 0,
  totalQuestions: 5,
  durationMinutes: 30,
  messages: [],
  currentQuestionMeta: null,
  evaluationFeedback: null,
  isWaitingForResponse: false,
};

export const useInterviewStore = create<InterviewState>((set) => ({
  ...initialState,

  setSession: (sessionId, jobTitle, totalQuestions, durationMinutes) =>
    set({
      sessionId,
      jobTitle,
      totalQuestions,
      durationMinutes,
      interviewStatus: "idle",
    }),

  setConnectionState: (connectionState) => set({ connectionState }),

  setInterviewStatus: (interviewStatus) => set({ interviewStatus }),

  addMessage: (msg) =>
    set((state) => ({
      messages: [...state.messages, msg],
    })),

  setCurrentQuestion: (meta) =>
    set({
      currentQuestionMeta: meta,
      evaluationFeedback: null,
    }),

  setEvaluationFeedback: (feedback) => set({ evaluationFeedback: feedback }),

  setWaitingForResponse: (waiting) => set({ isWaitingForResponse: waiting }),

  incrementQuestionIndex: () =>
    set((state) => ({
      questionIndex: state.questionIndex + 1,
    })),

  reset: () => set(initialState),
}));
