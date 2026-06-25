"use client";

import { Card, CardContent } from "@/components/ui/card";
import { useI18n } from "@/i18n";
import type { SessionReport } from "@/types";
import { Star, Clock, CheckCircle } from "lucide-react";

const levelLabelsMap: Record<string, string> = {
  junior: "Junior",
  mid: "Mid-Level",
  senior: "Senior",
};

export function ReportHeader({ report }: { report: SessionReport }) {
  const { t } = useI18n();

  const levelLabels: Record<string, string> = {
    junior: t.session.levelJunior,
    mid: t.session.levelMid,
    senior: t.session.levelSenior,
  };

  const scoreLabel =
    report.average_score !== null
      ? `${report.average_score.toFixed(1)} / 5`
      : "N/A";

  const recommendation =
    report.average_score !== null
      ? report.average_score >= 3.5
        ? t.report.recommended
        : t.report.notRecommended
      : t.report.insufficientData;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">
          {report.candidate_name}
        </h1>
        <p className="text-sm text-gray-500">
          {report.job_title} ·{" "}
          {levelLabels[report.experience_level] || report.experience_level}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Star className="h-5 w-5 text-yellow-500" />
            <div>
              <p className="text-xl font-bold">{scoreLabel}</p>
              <p className="text-xs text-gray-500">
                {t.report.averageScore}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <CheckCircle className="h-5 w-5 text-green-500" />
            <div>
              <p className="text-xl font-bold">
                {report.answered_count}/{report.total_questions}
              </p>
              <p className="text-xs text-gray-500">
                {t.report.questionsAnswered}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Clock className="h-5 w-5 text-blue-500" />
            <div>
              <p className="text-sm font-bold">{recommendation}</p>
              <p className="text-xs text-gray-500">
                {t.status[report.status as keyof typeof t.status] || report.status}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
