"use client";

import { Suspense, use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getSessionReport } from "@/lib/api";
import { useI18n } from "@/i18n";
import type { SessionReport } from "@/types";
import { ReportHeader } from "@/components/report/ReportHeader";
import { AnswerCard } from "@/components/report/AnswerCard";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Download } from "lucide-react";

function ReportContent({ sessionId }: { sessionId: string }) {
  const searchParams = useSearchParams();
  const adminToken = searchParams.get("token") || "";
  const { t } = useI18n();
  const [report, setReport] = useState<SessionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSessionReport(sessionId, adminToken)
      .then(setReport)
      .catch((e) =>
        setError(e instanceof Error ? e.message : t.report.loadError)
      )
      .finally(() => setLoading(false));
  }, [sessionId, adminToken]);

  const exportPDF = useCallback(async () => {
    if (!contentRef.current) return;
    setExporting(true);
    try {
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const canvas = await html2canvas(contentRef.current, {
        scale: 2,
        useCORS: true,
        logging: false,
      });
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = (canvas.height * pageWidth) / canvas.width;
      pdf.addImage(imgData, "PNG", 0, 0, pageWidth, pageHeight);
      pdf.save(`interview-report-${sessionId}.pdf`);
    } catch (e) {
      console.error("PDF export failed:", e);
    } finally {
      setExporting(false);
    }
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        {t.common.loading}
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-muted-foreground">
        <p className="text-lg">{error || t.report.notFound}</p>
        <Link href="/dashboard">
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t.report.backToDashboard}
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div ref={contentRef} className="mx-auto max-w-3xl px-4 py-8">
        {/* Actions bar */}
        <div className="mb-6 flex items-center justify-between no-print">
          <Link href="/dashboard">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              {t.report.backToDashboard}
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            onClick={exportPDF}
            disabled={exporting}
          >
            <Download className="mr-2 h-4 w-4" />
            {exporting ? t.report.exporting : t.report.downloadPdf}
          </Button>
        </div>

        <ReportHeader report={report} />

        <div className="mt-8 space-y-4">
          <h2 className="text-sm font-semibold">
            {t.report.answerDetails}
          </h2>
          {report.answers.map((a, i) => (
            <AnswerCard key={i} answer={a} />
          ))}
        </div>

        {/* Transcript section */}
        {report.conversation_transcript && report.conversation_transcript.length > 0 && (
          <div className="mt-8">
            <h2 className="mb-3 text-sm font-semibold">
              {t.report.conversationTranscript}
            </h2>
            <div className="rounded-lg border bg-card p-4 space-y-2 max-h-96 overflow-y-auto">
              {report.conversation_transcript.map((entry, i) => (
                <div key={i} className="text-sm">
                  <span className={`font-semibold ${entry.role === "interviewer" ? "text-blue-600" : "text-green-600"}`}>
                    {entry.role === "interviewer" ? t.report.roleInterviewer : t.report.roleCandidate}:
                  </span>{" "}
                  <span className="text-muted-foreground">{entry.content}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 border-t pt-6 text-center text-xs text-muted-foreground no-print">
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
  const { t } = useI18n();
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-gray-400">{t.common.loading}</div>}>
      <ReportContent sessionId={sessionId} />
    </Suspense>
  );
}
