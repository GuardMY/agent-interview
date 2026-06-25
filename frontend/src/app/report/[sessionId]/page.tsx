"use client";

import { Suspense, use, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getSessionReport } from "@/lib/api";
import { useI18n } from "@/i18n";
import type { SessionReport } from "@/types";
import { ReportHeader } from "@/components/report/ReportHeader";
import { AnswerCard } from "@/components/report/AnswerCard";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

function ReportContent({ sessionId }: { sessionId: string }) {
  const searchParams = useSearchParams();
  const adminToken = searchParams.get("token") || "";
  const { t } = useI18n();
  const [report, setReport] = useState<SessionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSessionReport(sessionId, adminToken)
      .then(setReport)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load")
      )
      .finally(() => setLoading(false));
  }, [sessionId, adminToken]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-gray-400">
        {t.common.loading}
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-gray-500">
        <p className="text-lg">{error || "Report not found"}</p>
        <Link href="/dashboard">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />{" "}
            {t.report.backToDashboard}
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="mb-6">
          <Link href="/dashboard">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />{" "}
              {t.report.backToDashboard}
            </Button>
          </Link>
        </div>

        <ReportHeader report={report} />

        <div className="mt-8 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700">
            {t.report.answerDetails}
          </h2>
          {report.answers.map((a, i) => (
            <AnswerCard key={i} answer={a} />
          ))}
        </div>

        <div className="mt-8 border-t pt-6 text-center text-xs text-gray-400">
          {t.report.generatedBy} · {new Date().toLocaleDateString()}
        </div>
      </div>
    </div>
  );
}

export default function ReportPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-gray-400">Loading...</div>}>
      <ReportContent sessionId={sessionId} />
    </Suspense>
  );
}
