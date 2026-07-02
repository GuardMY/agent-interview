"use client";

import { useState, useEffect, useCallback } from "react";
import { SessionList } from "@/components/dashboard/SessionList";
import { SessionCreateDialog } from "@/components/dashboard/SessionCreateDialog";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { LanguageSwitcher } from "@/components/shared/LanguageSwitcher";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { createSession, listSessions, deleteSession, getSession } from "@/lib/api";
import { useSessionNotifications } from "@/hooks/use-notification";
import { useI18n } from "@/i18n";
import type { SessionListStats, SessionResponse } from "@/types";

const MASTER_TOKEN_KEY = "master_admin_token";

function getMasterToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(MASTER_TOKEN_KEY);
}

export default function DashboardPage() {
  const { t, locale } = useI18n();
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [stats, setStats] = useState<SessionListStats>({
    total_count: 0,
    active_count: 0,
    completed_count: 0,
    avg_score: null,
    status_breakdown: {},
  });
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setFetching(true);
    const masterToken = getMasterToken();

    if (masterToken) {
      // Use the server-side list API with aggregate stats
      try {
        const response = await listSessions(masterToken, { page: 1, size: 100 });
        setSessions(response.items);
        setStats(response.stats);
        setFetching(false);
        return;
      } catch {
        // Fall through to localStorage fallback
      }
    }

    // Fallback: localStorage N+1 pattern (no master token configured)
    const stored = localStorage.getItem("session_ids");
    if (!stored) {
      setFetching(false);
      return;
    }
    const ids: string[] = JSON.parse(stored);
    const results: SessionResponse[] = [];
    for (const id of ids) {
      try {
        const token = localStorage.getItem(`candidate_${id}`);
        if (!token) continue;
        const s = await getSession(id, token);
        results.push(s);
      } catch {
        // Session may have been deleted
      }
    }
    results.sort(
      (a, b) =>
        new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
    );
    setSessions(results);
    setStats({
      total_count: results.length,
      active_count: results.filter(s => s.status !== "done" && s.status !== "idle").length,
      completed_count: results.filter(s => s.status === "done").length,
      avg_score: null,
      status_breakdown: {},
    });
    setFetching(false);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Polling notifications for completed interviews
  useSessionNotifications(getMasterToken(), locale);

  const handleCreate = async (data: {
    candidate_name: string;
    job_title: string;
    experience_level: string;
    key_skills: string[];
    interview_language: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const session = await createSession(data);
      // Store tokens for later access
      localStorage.setItem(`admin_${session.id}`, session.admin_token);
      localStorage.setItem(`candidate_${session.id}`, session.candidate_token);
      const stored = localStorage.getItem("session_ids");
      const ids: string[] = stored ? JSON.parse(stored) : [];
      ids.unshift(session.id);
      localStorage.setItem("session_ids", JSON.stringify(ids));
      setSessions((prev) => [session, ...prev]);
      window.open(
        `/interview/${session.id}?token=${encodeURIComponent(session.candidate_token)}`,
        "_blank"
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t.dashboard.failCreate);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const adminToken = localStorage.getItem(`admin_${id}`);
      if (!adminToken) return;
      await deleteSession(id, adminToken);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      localStorage.removeItem(`admin_${id}`);
      localStorage.removeItem(`candidate_${id}`);
      const stored = localStorage.getItem("session_ids");
      if (stored) {
        const ids: string[] = JSON.parse(stored).filter(
          (sid: string) => sid !== id
        );
        localStorage.setItem("session_ids", JSON.stringify(ids));
      }
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-5xl px-4 py-8">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {t.dashboard.title}
            </h1>
            <p className="text-sm text-gray-500">{t.dashboard.subtitle}</p>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <LanguageSwitcher />
            <SessionCreateDialog onCreate={handleCreate} loading={loading} />
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Stats */}
        <div className="mb-6">
          <StatsCards
            stats={{
              total: stats.total_count,
              active: stats.active_count,
              avgScore: stats.avg_score,
            }}
          />
        </div>

        {/* Session List */}
        <div>
          <h2 className="mb-3 text-sm font-semibold text-gray-700">
            {t.dashboard.sessions}
          </h2>
          {fetching ? (
            <div className="py-16 text-center text-gray-400">
              {t.common.loading}
            </div>
          ) : (
            <SessionList sessions={sessions} onDelete={handleDelete} />
          )}
        </div>
      </div>
    </div>
  );
}
