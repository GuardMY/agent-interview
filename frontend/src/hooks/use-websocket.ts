"use client";

import { useEffect, useRef, useCallback } from "react";
import { useInterviewStore } from "@/stores/interview-store";
import { WS_BASE, MAX_RECONNECT_ATTEMPTS, RECONNECT_BASE_DELAY_MS } from "@/lib/constants";
import type {
  WSEnvelope,
  Message,
  ServerMessageType,
} from "@/types";

let msgCounter = 0;
function nextId(): string {
  msgCounter += 1;
  return `msg-${Date.now()}-${msgCounter}`;
}

// Use getState() for stable access — avoids store object in dependency arrays
const getStore = () => useInterviewStore.getState();

export function useWebSocket(sessionId: string, token: string = "") {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const dispatchRef = useRef<(envelope: WSEnvelope) => void>(() => {});

  // Subscribe only to what the component renders
  const connectionState = useInterviewStore((s) => s.connectionState);

  // ── Message dispatcher (stable, no store dependency) ──────
  // Rebuilt whenever sessionId changes only
  const dispatch = useCallback(
    (envelope: WSEnvelope) => {
      const store = getStore();
      const { type, payload } = envelope;
      const ts = envelope.timestamp || new Date().toISOString();

      switch (type as ServerMessageType) {
        case "interview.start": {
          const p = payload as unknown as {
            session_id: string;
            job_title: string;
            total_questions: number;
            duration_minutes: number;
          };
          store.setSession(sessionId, p.job_title, p.total_questions, p.duration_minutes);
          store.setConnectionState("connected");
          store.setInterviewStatus("intro");
          break;
        }

        case "interview.chat": {
          const p = payload as { content: string };
          store.addMessage({
            id: nextId(),
            role: "interviewer",
            content: p.content,
            timestamp: ts,
          });
          store.setWaitingForResponse(false);
          break;
        }

        case "interview.question": {
          const p = payload as {
            question_id: string;
            content: string;
            category: string;
            difficulty: string;
            question_number: number;
            total_questions: number;
          };
          const meta = {
            questionId: p.question_id,
            category: p.category,
            difficulty: p.difficulty,
            questionNumber: p.question_number,
            totalQuestions: p.total_questions,
          };
          store.addMessage({
            id: nextId(),
            role: "interviewer",
            content: p.content,
            timestamp: ts,
            meta,
          });
          store.setCurrentQuestion(meta);
          store.setInterviewStatus("qa_loop");
          store.setWaitingForResponse(false);
          break;
        }

        case "interview.chat": {
          // Chat messages during resume_deep_dive phase — the phase is already set
          // by the interview.start or previous question message
          const p = payload as { content: string };
          store.addMessage({
            id: nextId(),
            role: "interviewer",
            content: p.content,
            timestamp: ts,
          });
          store.setWaitingForResponse(false);
          break;
        }

        case "interview.evaluation": {
          const p = payload as { feedback: string };
          store.setEvaluationFeedback(p.feedback);
          store.incrementQuestionIndex();
          break;
        }

        case "interview.end": {
          store.setInterviewStatus("done");
          store.setWaitingForResponse(false);
          break;
        }

        case "error": {
          const p = payload as { code: string; message: string };
          store.addMessage({
            id: nextId(),
            role: "system",
            content: `Error: ${p.message}`,
            timestamp: ts,
          });
          store.setWaitingForResponse(false);
          break;
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId]
  );

  // Keep the latest dispatch in a ref for the connect closure
  dispatchRef.current = dispatch;

  // ── Connect (only depends on sessionId) ───────────────────
  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const store = getStore();
    store.setConnectionState("connecting");

    const wsUrl = token
      ? `${WS_BASE}/ws/interview/${sessionId}?token=${encodeURIComponent(token)}`
      : `${WS_BASE}/ws/interview/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const envelope: WSEnvelope = JSON.parse(event.data as string);
        dispatchRef.current(envelope);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      getStore().setConnectionState("disconnected");

      // Don't reconnect if interview is already done
      if (getStore().interviewStatus === "done") return;

      if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        const delay =
          RECONNECT_BASE_DELAY_MS * Math.pow(2, reconnectAttempts.current);
        reconnectAttempts.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      // onclose will fire after this
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ── Send helpers ──────────────────────────────────────────
  const send = useCallback(
    (type: string, payload: Record<string, unknown> = {}) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        const envelope: WSEnvelope = {
          type,
          payload,
          timestamp: new Date().toISOString(),
        };
        ws.send(JSON.stringify(envelope));
        return true;
      }
      return false;
    },
    []
  );

  const sendAnswer = useCallback(
    (content: string) => {
      if (send("message.answer", { content })) {
        getStore().setWaitingForResponse(true);
        getStore().addMessage({
          id: nextId(),
          role: "candidate",
          content,
          timestamp: new Date().toISOString(),
        });
      }
    },
    [send]
  );

  const sendChat = useCallback(
    (content: string) => {
      if (send("message.chat", { content })) {
        getStore().setWaitingForResponse(true);
        getStore().addMessage({
          id: nextId(),
          role: "candidate",
          content,
          timestamp: new Date().toISOString(),
        });
      }
    },
    [send]
  );

  const sendSkip = useCallback(() => send("command.skip"), [send]);
  const sendRepeat = useCallback(() => send("command.repeat"), [send]);

  // ── Lifecycle (runs once on mount) ────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    sendAnswer,
    sendChat,
    sendSkip,
    sendRepeat,
    connectionState,
    isConnected: connectionState === "connected",
  };
}
