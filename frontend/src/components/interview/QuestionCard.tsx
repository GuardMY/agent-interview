"use client";

import type { QuestionMeta } from "@/types";
import { Badge } from "@/components/ui/badge";
import { DIFFICULTY_COLORS, CATEGORY_COLORS } from "@/lib/constants";

interface Props {
  meta: QuestionMeta;
}

export function QuestionCard({ meta }: Props) {
  const diffClass =
    DIFFICULTY_COLORS[meta.difficulty || ""] || "bg-gray-100 text-gray-800";
  const catClass =
    CATEGORY_COLORS[meta.category || ""] || "bg-gray-100 text-gray-800";

  return (
    <div className="mb-2 flex flex-wrap items-center gap-2">
      {meta.questionNumber && meta.totalQuestions && (
        <span className="text-xs font-medium text-gray-500">
          Q{meta.questionNumber}/{meta.totalQuestions}
        </span>
      )}
      {meta.category && (
        <Badge variant="secondary" className={`text-[10px] ${catClass}`}>
          {meta.category}
        </Badge>
      )}
      {meta.difficulty && (
        <Badge variant="secondary" className={`text-[10px] ${diffClass}`}>
          {meta.difficulty}
        </Badge>
      )}
    </div>
  );
}
