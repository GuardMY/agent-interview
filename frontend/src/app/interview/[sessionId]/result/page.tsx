"use client";

import { Suspense, use, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { getCandidateReport } from "@/lib/api";
import { useI18n } from "@/i18n";
import type { SessionReport } from "@/types";
import { RadarChart } from "@/components/report/RadarChart";

function ResultContent({ sessionId }: { sessionId: string }) {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const { t } = useI18n();
  const [report, setReport] = useState<SessionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError(t.result.missingToken);
      setLoading(false);
      return;
    }
    getCandidateReport(sessionId, token)
      .then(setReport)
      .catch((e) => setError(e instanceof Error ? e.message : t.result.loadError))
      .finally(() => setLoading(false));
  }, [sessionId, token, t.result.missingToken, t.result.loadError]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-400">
        {t.result.loading}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4">
        <p className="text-red-500">{error}</p>
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          {t.result.backHome}
        </Link>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-400">
        {t.result.notAvailable}
      </div>
    );
  }

  const recommendation =
    (report.average_score ?? 0) >= 3.5
      ? t.result.strong
      : t.result.needsImprovement;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mb-3 text-5xl">🎉</div>
          <h1 className="text-2xl font-bold text-gray-900">
            {t.result.title}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {report.job_title} · {report.total_questions} questions
          </p>
        </div>

        {/* Score Card */}
        <div className="mb-6 rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">{t.result.overallScore}</p>
              <p className="text-4xl font-bold text-blue-600">
                {report.average_score?.toFixed(1) ?? "—"}
                <span className="text-lg font-normal text-gray-400">/5</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">{t.result.questionsAnswered}</p>
              <p className="text-2xl font-semibold text-gray-900">
                {report.answered_count}/{report.total_questions}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">{t.result.outcome}</p>
              <p className={`text-2xl font-semibold ${
                recommendation === t.result.strong ? "text-green-600" : "text-amber-600"
              }`}>
                {recommendation}
              </p>
            </div>
          </div>
        </div>

        {/* P3: Position Match Radar */}
        {report.position_match_summary && Object.keys(report.position_match_summary).length >= 3 && (
          <div className="mb-6 rounded-lg border bg-white p-4 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-center">{t.report.radarTitle}</h3>
            <RadarChart
              data={Object.entries(report.position_match_summary).map(([key, val]) => ({
                label: (t.dimensions as Record<string, string>)[key] || key,
                value: val,
              }))}
              maxValue={5}
              size={180}
            />
          </div>
        )}

        {/* Per-question summary */}
        <h2 className="mb-3 text-lg font-semibold text-gray-800">
          {t.result.questionSummary}
        </h2>
        <div className="space-y-3">
          {report.answers.map((ans, i) => (
            <div
              key={i}
              className="rounded-lg border bg-white p-4 shadow-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">
                  Q{i + 1} · {ans.category} · {ans.difficulty}
                </span>
                {ans.score !== null && (
                  <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
                    {ans.score}/5
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 line-clamp-2">
                {ans.question_text}
              </p>
              {ans.score_comment && (
                <p className="mt-1 text-xs italic text-gray-400">
                  {ans.score_comment}
                </p>
              )}
            </div>
          ))}
        </div>

        <div className="mt-8 text-center">
          <Link
            href="/"
            className="text-sm text-blue-600 hover:underline"
          >
            {t.result.backHome}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function CandidateResultPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const { t } = useI18n();
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center text-gray-400">
          {t.result.loading}
        </div>
      }
    >
      <ResultContent sessionId={sessionId} />
    </Suspense>
  );
}
