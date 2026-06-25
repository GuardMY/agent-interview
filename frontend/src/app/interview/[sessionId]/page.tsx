"use client";

import { use, useCallback } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import { useInterviewStore } from "@/stores/interview-store";
import { useI18n } from "@/i18n";
import { InterviewHeader } from "@/components/interview/InterviewHeader";
import { ChatPanel } from "@/components/interview/ChatPanel";
import { InputPanel } from "@/components/interview/InputPanel";

export default function InterviewPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const { t } = useI18n();
  const { sendAnswer, sendChat, sendSkip, sendRepeat, connectionState } =
    useWebSocket(sessionId);

  const interviewStatus = useInterviewStore((s) => s.interviewStatus);
  const isWaiting = useInterviewStore((s) => s.isWaitingForResponse);
  const isConnected = connectionState === "connected";

  const handleSend = useCallback(
    (content: string) => {
      if (interviewStatus === "qa_loop") {
        sendAnswer(content);
      } else {
        sendChat(content);
      }
    },
    [interviewStatus, sendAnswer, sendChat]
  );

  const isDone = interviewStatus === "done";
  const isQaActive = interviewStatus === "qa_loop" && !isWaiting;

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <InterviewHeader />

      {isDone && (
        <div className="mx-auto mt-12 max-w-md rounded-2xl border bg-white p-8 text-center shadow-sm">
          <div className="mb-3 text-5xl">🎉</div>
          <h2 className="mb-2 text-xl font-bold text-gray-900">
            {t.interview.complete}
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            {t.interview.completeMessage}
          </p>
        </div>
      )}

      {!isDone && (
        <>
          <ChatPanel />
          <InputPanel
            onSend={handleSend}
            onSkip={sendSkip}
            onRepeat={sendRepeat}
            disabled={!isConnected || isWaiting}
            isQaActive={isQaActive}
          />
        </>
      )}
    </div>
  );
}
