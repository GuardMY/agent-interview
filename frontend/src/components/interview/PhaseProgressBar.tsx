"use client";

import { useInterviewStore } from "@/stores/interview-store";
import { useI18n } from "@/i18n";

function formatPhaseLabel(name: string, t: (key: string) => string): string {
  // Use i18n phases section if available
  const key = `phases.${name}`;
  const translated = t(key);
  if (translated && translated !== key) return translated;
  // Fallback: capitalize
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function PhaseProgressBar() {
  const { t } = useI18n();
  const phases = useInterviewStore((s) => s.phases);
  const currentPhaseIndex = useInterviewStore((s) => s.currentPhaseIndex);
  const positionContext = useInterviewStore((s) => s.positionContext);

  if (phases.length === 0) return null;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center gap-0.5">
        {phases.map((phase, i) => {
          const isActive = i === currentPhaseIndex;
          const isCompleted = i < currentPhaseIndex;
          const isPending = i > currentPhaseIndex;

          let bgColor = "bg-gray-200";
          if (isActive) bgColor = "bg-blue-500";
          else if (isCompleted) bgColor = "bg-green-500";

          const label = formatPhaseLabel(phase.name, t as (key: string) => string);

          return (
            <div
              key={phase.name}
              className="flex flex-col items-center"
              title={`${label}${phase.questionCount > 0 ? ` (${phase.questionCount})` : ""}`}
            >
              <div
                className={`h-1.5 w-10 rounded-full transition-colors duration-300 sm:w-14 ${
                  isActive ? "bg-blue-500 animate-pulse" : isCompleted ? "bg-green-500" : "bg-gray-200"
                }`}
              />
              <span
                className={`mt-0.5 text-[10px] leading-tight ${
                  isActive
                    ? "font-semibold text-blue-700"
                    : isCompleted
                      ? "text-green-600"
                      : "text-gray-400"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
      {positionContext && (
        <p className="text-[10px] text-blue-600 bg-blue-50 px-2 py-0.5 rounded max-w-md truncate">
          {positionContext}
        </p>
      )}
    </div>
  );
}
