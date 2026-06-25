"use client";

import type { Message } from "@/types";
import { QuestionCard } from "./QuestionCard";

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isInterviewer = message.role === "interviewer";
  const isCandidate = message.role === "candidate";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div className="mx-auto my-2 max-w-sm rounded-lg bg-gray-100 px-4 py-2 text-center text-xs text-gray-500">
        {message.content}
      </div>
    );
  }

  return (
    <div
      className={`flex ${isCandidate ? "justify-end" : "justify-start"} mb-4`}
    >
      <div
        className={`max-w-[85%] sm:max-w-[75%] ${
          isInterviewer
            ? "rounded-2xl rounded-bl-sm bg-white border px-4 py-3 shadow-sm"
            : "rounded-2xl rounded-br-sm bg-blue-600 px-4 py-3 text-white"
        }`}
      >
        {message.meta?.questionId && (
          <QuestionCard meta={message.meta} />
        )}
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
        </p>
        <span
          className={`mt-1 block text-right text-[10px] ${
            isInterviewer ? "text-gray-400" : "text-blue-200"
          }`}
        >
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}
