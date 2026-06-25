// API base URL — override via NEXT_PUBLIC_API_URL env var
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

// Interview defaults
export const MAX_RECONNECT_ATTEMPTS = 3;
export const RECONNECT_BASE_DELAY_MS = 1000;
export const HEARTBEAT_INTERVAL_MS = 30_000;

// Status display labels
export const STATUS_LABELS: Record<string, string> = {
  idle: "Ready",
  intro: "Opening",
  qa_loop: "In Progress",
  wrapup: "Closing",
  done: "Completed",
};

export const EXPERIENCE_LABELS: Record<string, string> = {
  junior: "Junior",
  mid: "Mid-Level",
  senior: "Senior",
};

export const DIFFICULTY_COLORS: Record<string, string> = {
  junior: "bg-green-100 text-green-800",
  mid: "bg-yellow-100 text-yellow-800",
  senior: "bg-red-100 text-red-800",
};

export const CATEGORY_COLORS: Record<string, string> = {
  backend: "bg-blue-100 text-blue-800",
  frontend: "bg-purple-100 text-purple-800",
  general: "bg-gray-100 text-gray-800",
  devops: "bg-orange-100 text-orange-800",
  ai_ml: "bg-teal-100 text-teal-800",
};
