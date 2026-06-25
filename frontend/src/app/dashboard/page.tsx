"use client";

import { useState, useEffect, useCallback } from "react";
import { SessionList } from "@/components/dashboard/SessionList";
import { SessionCreateDialog } from "@/components/dashboard/SessionCreateDialog";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { LanguageSwitcher } from "@/components/shared/LanguageSwitcher";
import { createSession, getSession, deleteSession } from "@/lib/api";
import { useI18n } from "@/i18n";
import type { SessionResponse } from "@/types";

export default function DashboardPage() {
  const { t } = useI18n();
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    const stored = localStorage.getItem("session_ids");
    if (!stored) {
      setFetching(false);
      return;
    }
    const ids: string[] = JSON.parse(stored);
    const results: SessionResponse[] = [];
    for (const id of ids) {
      try {
        const s = await getSession(id);
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
    setFetching(false);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

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
      const stored = localStorage.getItem("session_ids");
      const ids: string[] = stored ? JSON.parse(stored) : [];
      ids.unshift(session.id);
      localStorage.setItem("session_ids", JSON.stringify(ids));
      setSessions((prev) => [session, ...prev]);
      window.open(`/interview/${session.id}`, "_blank");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create session");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
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

  const activeCount = sessions.filter(
    (s) => s.status !== "done" && s.status !== "idle"
  ).length;

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
              total: sessions.length,
              active: activeCount,
              avgScore: null,
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
