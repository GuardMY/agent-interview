"use client";

import { useState, useEffect, useCallback } from "react";
import { SessionList } from "@/components/dashboard/SessionList";
import { SessionCreateDialog } from "@/components/dashboard/SessionCreateDialog";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { LanguageSwitcher } from "@/components/shared/LanguageSwitcher";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Button } from "@/components/ui/button";
import { createSession, listSessions, deleteSession } from "@/lib/api";
import { useSessionNotifications } from "@/hooks/use-notification";
import { useI18n } from "@/i18n";
import { Briefcase } from "lucide-react";
import Link from "next/link";
import type { SessionListStats, SessionResponse } from "@/types";

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
    setError(null);
    try {
      const response = await listSessions({ page: 1, size: 100 });
      setSessions(response.items);
      setStats(response.stats);
    } catch (e) {
      setError(e instanceof Error ? e.message : t.dashboard.failLoad);
    } finally {
      setFetching(false);
    }
  }, [t.dashboard.failLoad]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Polling notifications for completed interviews
  useSessionNotifications(locale);

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
      // Store tokens for session-specific access (interviews & reports)
      localStorage.setItem(`admin_${session.id}`, session.admin_token);
      localStorage.setItem(`candidate_${session.id}`, session.candidate_token);
      setSessions((prev) => [session, ...prev]);
      window.open(
        `/interview/${session.id}?token=${encodeURIComponent(session.candidate_token)}`,
        "_blank"
      );
      return { id: session.id, admin_token: session.admin_token, candidate_token: session.candidate_token };
    } catch (e) {
      setError(e instanceof Error ? e.message : t.dashboard.failCreate);
      throw e;
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
    } catch (e) {
      setError(e instanceof Error ? e.message : t.dashboard.failDelete);
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
            <Link href="/dashboard/positions">
              <Button variant="outline" size="sm">
                <Briefcase className="mr-2 h-4 w-4" />
                Positions
              </Button>
            </Link>
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
