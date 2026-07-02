from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.evaluation import (
    AnswerReport,
    ConversationEntry,
    EvaluationDimensions,
    SessionReport,
)


class ReportService:
    """Builds interview session reports from database records."""

    DIMENSION_FIELDS = [
        "technical_accuracy",
        "depth_of_knowledge",
        "communication",
        "problem_solving",
    ]

    @staticmethod
    async def build_report(
        session_id: str, db: AsyncSession
    ) -> SessionReport | None:
        """Build a full session report including all questions and answers."""
        stmt = (
            select(InterviewSession)
            .where(InterviewSession.id == session_id)
            .options(
                selectinload(InterviewSession.questions),
                selectinload(InterviewSession.answers),
            )
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            return None

        # Build answer reports indexed by question_id
        answer_map: dict[str, Answer] = {
            a.question_id: a for a in session.answers
        }

        answer_reports: list[AnswerReport] = []
        total_score = 0
        scored_count = 0

        # Dimension accumulators
        dim_sums: dict[str, float] = {d: 0.0 for d in ReportService.DIMENSION_FIELDS}
        dim_counts: dict[str, int] = {d: 0 for d in ReportService.DIMENSION_FIELDS}

        for q in session.questions:
            ans = answer_map.get(q.id)
            ans_dims = None

            if ans and ans.score is not None:
                total_score += ans.score
                scored_count += 1

                # Extract dimension scores
                dims_present = 0
                dim_values: dict[str, int] = {}
                for dim in ReportService.DIMENSION_FIELDS:
                    val = getattr(ans, f"dimension_{dim}", None)
                    if val is not None:
                        dim_values[dim] = val
                        dim_sums[dim] += val
                        dim_counts[dim] += 1
                        dims_present += 1

                if dims_present == 4:
                    ans_dims = EvaluationDimensions(**dim_values)

            answer_reports.append(
                AnswerReport(
                    question_text=q.question_text,
                    category=q.category,
                    difficulty=q.difficulty,
                    order_index=q.order_index,
                    status=q.status,
                    answer_content=ans.content if ans else None,
                    score=ans.score if ans else None,
                    score_comment=ans.score_comment if ans else None,
                    dimensions=ans_dims,
                )
            )

        avg_score = total_score / scored_count if scored_count > 0 else None

        # Compute dimension averages
        dimension_averages: dict[str, float] | None = None
        if any(dim_counts[d] > 0 for d in ReportService.DIMENSION_FIELDS):
            dimension_averages = {
                d: round(dim_sums[d] / dim_counts[d], 2)
                for d in ReportService.DIMENSION_FIELDS
                if dim_counts[d] > 0
            }

        # Load conversation transcript from metadata
        transcript_data = session.metadata_json.get("transcript", [])
        conversation_transcript = (
            [ConversationEntry(**entry) for entry in transcript_data]
            if transcript_data else None
        )

        return SessionReport(
            session_id=session.id,
            candidate_name=session.candidate_name,
            job_title=session.job_title,
            experience_level=session.experience_level,
            status=session.status,
            total_questions=session.total_questions,
            answered_count=scored_count,
            average_score=avg_score,
            answers=answer_reports,
            started_at=session.started_at,
            completed_at=session.completed_at,
            dimension_averages=dimension_averages,
            conversation_transcript=conversation_transcript,
        )
