"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SessionResponse } from "@/types";
import { useI18n } from "@/i18n";
import { ExternalLink, Trash2, FileText } from "lucide-react";
import Link from "next/link";

interface Props {
  sessions: SessionResponse[];
  onDelete: (id: string) => void;
}

const STATUS_BADGE: Record<string, string> = {
  idle: "bg-gray-100 text-gray-700",
  intro: "bg-blue-100 text-blue-700",
  qa_loop: "bg-green-100 text-green-700",
  wrapup: "bg-yellow-100 text-yellow-700",
  done: "bg-purple-100 text-purple-700",
};

export function SessionList({ sessions, onDelete }: Props) {
  const { t } = useI18n();

  const levelLabels: Record<string, string> = {
    junior: t.session.levelJunior,
    mid: t.session.levelMid,
    senior: t.session.levelSenior,
  };

  if (sessions.length === 0) {
    return (
      <div className="py-16 text-center text-gray-400">
        <p className="text-lg">{t.dashboard.noSessions}</p>
        <p className="text-sm">{t.dashboard.noSessionsHint}</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
          <tr>
            <th className="px-4 py-3">{t.dashboard.tableCandidate}</th>
            <th className="px-4 py-3">{t.dashboard.tablePosition}</th>
            <th className="hidden px-4 py-3 md:table-cell">
              {t.dashboard.tableLevel}
            </th>
            <th className="hidden px-4 py-3 md:table-cell">{t.dashboard.tableLanguage}</th>
            <th className="px-4 py-3">{t.dashboard.tableStatus}</th>
            <th className="hidden px-4 py-3 md:table-cell">
              {t.dashboard.tableScore}
            </th>
            <th className="px-4 py-3 text-right">{t.dashboard.tableActions}</th>
          </tr>
        </thead>
        <tbody className="divide-y bg-white">
          {sessions.map((s) => (
            <tr key={s.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium text-gray-900">
                {s.candidate_name}
              </td>
              <td className="px-4 py-3 text-gray-600">{s.job_title}</td>
              <td className="hidden px-4 py-3 text-gray-500 md:table-cell">
                {levelLabels[s.experience_level] || s.experience_level}
              </td>
              <td className="hidden px-4 py-3 md:table-cell">
                <Badge className="text-[10px] bg-gray-100 text-gray-700">
                  {s.interview_language === "zh" ? "中文" : "EN"}
                </Badge>
              </td>
              <td className="px-4 py-3">
                <Badge
                  className={`text-[10px] ${STATUS_BADGE[s.status] || "bg-gray-100"}`}
                >
                  {t.status[s.status as keyof typeof t.status] || s.status}
                </Badge>
              </td>
              <td className="hidden px-4 py-3 text-gray-500 md:table-cell">
                {s.status === "done" ? t.dashboard.viewReport : "—"}
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-1">
                  {s.status === "done" && (
                    <Link
                      href={`/report/${s.id}?token=${encodeURIComponent(
                        (typeof window !== "undefined" ? localStorage.getItem(`admin_${s.id}`) : null) || ""
                      )}`}
                    >
                      <Button
                        variant="ghost"
                        size="sm"
                        title={t.dashboard.viewReport}
                      >
                        <FileText className="h-4 w-4" />
                      </Button>
                    </Link>
                  )}
                  <Link
                    href={`/interview/${s.id}?token=${encodeURIComponent(
                      (typeof window !== "undefined" ? localStorage.getItem(`candidate_${s.id}`) : null) || ""
                    )}`}
                    target="_blank"
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      title={t.dashboard.openInterview}
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDelete(s.id)}
                    title={t.dashboard.deleteConfirm}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
