from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.evaluation import AnswerReport, SessionReport


class ReportService:
    """Builds interview session reports from database records."""

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

        for q in session.questions:
            ans = answer_map.get(q.id)
            if ans and ans.score is not None:
                total_score += ans.score
                scored_count += 1

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
                )
            )

        avg_score = total_score / scored_count if scored_count > 0 else None

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
        )
