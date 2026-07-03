"use client";

import { create } from "zustand";
import type {
  Message,
  ConnectionState,
  InterviewStatus,
  QuestionMeta,
} from "@/types";

interface PhaseInfo {
  name: string;
  label: string;
  description: string;
  questionCount: number;
  maxQuestions: number;
  isActive: boolean;
  isCompleted: boolean;
}

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

  // ── P2: Phase tracking ──
  phases: PhaseInfo[];
  currentPhaseIndex: number;
  totalPhases: number;
  positionContext: string | null;
  followUpDepth: number;
  parentQuestionId: string | null;

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
  setQuestionIndex: (idx: number) => void;
  incrementQuestionIndex: () => void;
  reset: () => void;

  // ── P2: Phase actions ──
  setPhases: (phases: PhaseInfo[]) => void;
  setCurrentPhaseIndex: (idx: number) => void;
  setTotalPhases: (total: number) => void;
  setPhaseQuestionCount: (phaseName: string, count: number) => void;
  markPhaseCompleted: (phaseName: string) => void;
  setPositionContext: (context: string | null) => void;
  setFollowUpInfo: (depth: number, parentId: string | null) => void;
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
  // P2 defaults
  phases: [] as PhaseInfo[],
  currentPhaseIndex: 0,
  totalPhases: 0,
  positionContext: null,
  followUpDepth: 0,
  parentQuestionId: null,
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

  setQuestionIndex: (idx) => set({ questionIndex: idx }),

  incrementQuestionIndex: () =>
    set((state) => ({
      questionIndex: state.questionIndex + 1,
    })),

  reset: () => set(initialState),

  // ── P2: Phase actions ──
  setPhases: (phases) => set({ phases }),
  setCurrentPhaseIndex: (idx) => set({ currentPhaseIndex: idx }),
  setTotalPhases: (total) => set({ totalPhases: total }),
  setPhaseQuestionCount: (phaseName, count) =>
    set((state) => ({
      phases: state.phases.map((p) =>
        p.name === phaseName ? { ...p, questionCount: count } : p
      ),
    })),
  markPhaseCompleted: (phaseName) =>
    set((state) => ({
      phases: state.phases.map((p) =>
        p.name === phaseName
          ? { ...p, isActive: false, isCompleted: true }
          : p
      ),
    })),
  setPositionContext: (context) => set({ positionContext: context }),
  setFollowUpInfo: (depth, parentId) =>
    set({ followUpDepth: depth, parentQuestionId: parentId }),
}));
