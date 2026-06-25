"use client";

import { useI18n } from "@/i18n";
import type { ConnectionState } from "@/types";

const dotColors: Record<ConnectionState, string> = {
  connecting: "bg-yellow-500 animate-pulse",
  connected: "bg-green-500",
  disconnected: "bg-gray-400",
  error: "bg-red-500 animate-pulse",
};

const textColors: Record<ConnectionState, string> = {
  connecting: "text-yellow-600",
  connected: "text-green-600",
  disconnected: "text-gray-500",
  error: "text-red-600",
};

export function ConnectionBadge({ state }: { state: ConnectionState }) {
  const { t } = useI18n();

  const labels: Record<ConnectionState, string> = {
    connecting: t.interview.connecting,
    connected: t.interview.connected,
    disconnected: t.interview.disconnected,
    error: t.interview.connectionError,
  };

  return (
    <div
      className={`flex items-center gap-1.5 text-xs font-medium ${textColors[state]}`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${dotColors[state]}`} />
      {labels[state]}
    </div>
  );
}
