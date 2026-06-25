"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n";
import type { AnswerReport } from "@/types";
import { DIFFICULTY_COLORS, CATEGORY_COLORS } from "@/lib/constants";

export function AnswerCard({ answer }: { answer: AnswerReport }) {
  const { t } = useI18n();

  const diffClass =
    DIFFICULTY_COLORS[answer.difficulty] || "bg-gray-100 text-gray-800";
  const catClass =
    CATEGORY_COLORS[answer.category] || "bg-gray-100 text-gray-800";

  const isSkipped = answer.status === "skipped";
  const isAnswered = answer.status === "answered";

  return (
    <Card className={isSkipped ? "opacity-60" : ""}>
      <CardContent className="space-y-3 p-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-600">
              Q{answer.order_index + 1}
            </span>
            <Badge className={`text-[10px] ${catClass}`}>
              {answer.category}
            </Badge>
            <Badge className={`text-[10px] ${diffClass}`}>
              {answer.difficulty}
            </Badge>
            {isAnswered && answer.score !== null && (
              <span className="ml-auto text-sm font-bold text-yellow-600">
                {"⭐".repeat(answer.score)}
                <span className="ml-1 text-gray-400">
                  {answer.score}/5
                </span>
              </span>
            )}
            {isSkipped && (
              <Badge variant="outline" className="text-[10px]">
                {t.report.skipped}
              </Badge>
            )}
          </div>
        </div>

        {/* Question */}
        <div>
          <p className="text-xs font-medium text-gray-400">
            {t.report.question}
          </p>
          <p className="text-sm text-gray-800">{answer.question_text}</p>
        </div>

        {/* Answer */}
        {answer.answer_content && (
          <div>
            <p className="text-xs font-medium text-gray-400">
              {t.report.answer}
            </p>
            <p className="whitespace-pre-wrap text-sm text-gray-700">
              {answer.answer_content}
            </p>
          </div>
        )}

        {/* Score comment */}
        {answer.score_comment && (
          <div className="rounded-lg bg-gray-50 px-3 py-2">
            <p className="text-xs text-gray-600">
              <span className="font-medium">{t.report.evaluator}</span>{" "}
              {answer.score_comment}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
