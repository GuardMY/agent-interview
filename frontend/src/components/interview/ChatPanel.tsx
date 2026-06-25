"use client";

import { useEffect, useRef } from "react";
import { useInterviewStore } from "@/stores/interview-store";
import { useI18n } from "@/i18n";
import { MessageBubble } from "./MessageBubble";

export function ChatPanel() {
  const { t } = useI18n();
  const messages = useInterviewStore((s) => s.messages);
  const isWaiting = useInterviewStore((s) => s.isWaitingForResponse);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isWaiting]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400">
        <div className="text-center">
          <div className="mb-2 text-4xl">🤖</div>
          <p className="text-sm">{t.interview.waiting}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-3xl">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isWaiting && (
          <div className="mb-4 flex justify-start">
            <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm border bg-white px-5 py-4 shadow-sm">
              <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:0ms]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:150ms]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:300ms]" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
