"use client";

import { useEffect, useState, useCallback } from "react";
import { useInterviewStore } from "@/stores/interview-store";
import { useI18n } from "@/i18n";
import { ConnectionBadge } from "./ConnectionBadge";
import { PhaseProgressBar } from "./PhaseProgressBar";

export function InterviewHeader() {
  const { t } = useI18n();
  const jobTitle = useInterviewStore((s) => s.jobTitle);
  const questionIndex = useInterviewStore((s) => s.questionIndex);
  const totalQuestions = useInterviewStore((s) => s.totalQuestions);
  const interviewStatus = useInterviewStore((s) => s.interviewStatus);
  const connectionState = useInterviewStore((s) => s.connectionState);
  const phases = useInterviewStore((s) => s.phases);
  const hasPhases = phases.length > 0;

  const [elapsed, setElapsed] = useState(0);

  const tick = useCallback(() => {
    setElapsed((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (interviewStatus === "done") return;
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [interviewStatus, tick]);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timeStr = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  const progressPct =
    totalQuestions > 0
      ? Math.round((questionIndex / totalQuestions) * 100)
      : 0;

  const statusLabel =
    t.status[interviewStatus as keyof typeof t.status] || interviewStatus;

  return (
    <header className="border-b bg-white px-4 py-3 shadow-sm">
      <div className="mx-auto flex max-w-3xl items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-gray-900">
            {jobTitle || t.interview.title}
          </h1>
          <p className="text-xs text-gray-500">{statusLabel}</p>
        </div>

        <div className="flex items-center gap-4">
          {hasPhases ? (
            <PhaseProgressBar />
          ) : (
            <div className="hidden w-32 items-center gap-2 sm:flex">
              <div className="h-1.5 flex-1 rounded-full bg-gray-200">
                <div
                  className="h-1.5 rounded-full bg-blue-600 transition-all duration-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <span className="text-xs tabular-nums text-gray-500">
                {questionIndex}/{totalQuestions}
              </span>
            </div>
          )}

          <span className="text-sm tabular-nums text-gray-600">{timeStr}</span>

          <ConnectionBadge state={connectionState} />
        </div>
      </div>
    </header>
  );
}
