from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.answer import Answer
from app.models.question import Question
from app.models.session import InterviewSession
from app.schemas.evaluation import (
    AnswerReport,
    BehavioralDimensions,
    ConversationEntry,
    EvaluationDimensions,
    PositionMatchDimensions,
    SessionReport,
)


class ReportService:
    """Builds interview session reports from database records."""

    CORE_DIMENSION_FIELDS = [
        "technical_accuracy",
        "depth_of_knowledge",
        "communication",
        "problem_solving",
    ]

    BEHAVIORAL_DIMENSION_FIELDS = [
        "teamwork", "leadership", "ownership",
        "growth_mindset", "culture_fit",
    ]

    POSITION_MATCH_DIMENSION_FIELDS = [
        "skill_coverage", "experience_alignment", "level_alignment",
        "domain_fit", "growth_potential",
    ]

    ALL_DIMENSION_FIELDS = (
        CORE_DIMENSION_FIELDS + BEHAVIORAL_DIMENSION_FIELDS + POSITION_MATCH_DIMENSION_FIELDS
    )

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

        # Dimension accumulators (all dimensions)
        dim_sums: dict[str, float] = {d: 0.0 for d in ReportService.ALL_DIMENSION_FIELDS}
        dim_counts: dict[str, int] = {d: 0 for d in ReportService.ALL_DIMENSION_FIELDS}

        # Phase score accumulators
        phase_scores: dict[str, list[int]] = {}

        for q in session.questions:
            ans = answer_map.get(q.id)
            ans_dims = None
            ans_behavioral = None
            ans_position_match = None

            if ans and ans.score is not None:
                total_score += ans.score
                scored_count += 1

                # Extract core dimension scores
                core_dims_present = 0
                dim_values: dict[str, int] = {}
                for dim in ReportService.CORE_DIMENSION_FIELDS:
                    val = getattr(ans, f"dimension_{dim}", None)
                    if val is not None:
                        dim_values[dim] = val
                        dim_sums[dim] += val
                        dim_counts[dim] += 1
                        core_dims_present += 1

                if core_dims_present >= 3:  # Allow partial core dimensions
                    ans_dims = EvaluationDimensions(
                        technical_accuracy=dim_values.get("technical_accuracy", 3),
                        depth_of_knowledge=dim_values.get("depth_of_knowledge", 3),
                        communication=dim_values.get("communication", 3),
                        problem_solving=dim_values.get("problem_solving", 3),
                    )

                # Extract behavioral dimensions
                b_values: dict[str, int] = {}
                b_present = False
                for dim in ReportService.BEHAVIORAL_DIMENSION_FIELDS:
                    val = getattr(ans, f"dimension_{dim}", None)
                    if val is not None:
                        b_values[dim] = val
                        dim_sums[dim] += val
                        dim_counts[dim] += 1
                        b_present = True
                if b_present:
                    ans_behavioral = BehavioralDimensions(**b_values)

                # Extract position match dimensions
                pm_values: dict[str, int] = {}
                pm_present = False
                for dim in ReportService.POSITION_MATCH_DIMENSION_FIELDS:
                    val = getattr(ans, f"dimension_{dim}", None)
                    if val is not None:
                        pm_values[dim] = val
                        dim_sums[dim] += val
                        dim_counts[dim] += 1
                        pm_present = True
                if pm_present:
                    ans_position_match = PositionMatchDimensions(**pm_values)

                # Phase score accumulation
                phase = q.phase or "qa_loop"
                if phase not in phase_scores:
                    phase_scores[phase] = []
                phase_scores[phase].append(ans.score)

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
                    behavioral=ans_behavioral,
                    position_match=ans_position_match,
                    phase=q.phase,
                    relates_to_position_requirement=(
                        ans.relates_to_position_requirement if ans else None
                    ),
                )
            )

        avg_score = total_score / scored_count if scored_count > 0 else None

        # Compute dimension averages
        dimension_averages: dict[str, float] | None = None
        if any(dim_counts[d] > 0 for d in ReportService.ALL_DIMENSION_FIELDS):
            dimension_averages = {
                d: round(dim_sums[d] / dim_counts[d], 2)
                for d in ReportService.ALL_DIMENSION_FIELDS
                if dim_counts[d] > 0
            }

        # Compute phase scores
        computed_phase_scores: dict[str, float] | None = None
        if phase_scores:
            computed_phase_scores = {
                phase: round(sum(scores) / len(scores), 2)
                for phase, scores in phase_scores.items()
                if scores
            }

        # Build position match radar data
        position_match_summary = ReportService._build_position_match_summary(
            dim_sums, dim_counts
        )

        # Build gap summary
        gap_summary = ReportService._build_gap_summary(session)

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
            phase_scores=computed_phase_scores,
            position_match_summary=position_match_summary,
            gap_summary=gap_summary,
        )

    # ── P3: Enhanced report helpers ───────────────────────────

    @staticmethod
    def _build_position_match_summary(
        dim_sums: dict[str, float], dim_counts: dict[str, int]
    ) -> dict[str, float] | None:
        """Build position match radar data (5 sub-dimensions)."""
        pm_keys = ReportService.POSITION_MATCH_DIMENSION_FIELDS
        if not any(dim_counts.get(k, 0) > 0 for k in pm_keys):
            return None
        return {
            k: round(dim_sums[k] / dim_counts[k], 2)
            for k in pm_keys
            if dim_counts.get(k, 0) > 0
        }

    @staticmethod
    def _build_gap_summary(session: InterviewSession) -> dict | None:
        """Build gap analysis summary from session data."""
        gap_data = session.gap_analysis_json
        if not gap_data:
            return None

        # Extract verified skills from answered questions
        verified_skills: set[str] = set()
        for q in session.questions:
            if q.category and q.status == "answered":
                verified_skills.add(q.category)

        skills_missing = gap_data.get("skills_missing", [])
        skills_matched = gap_data.get("skills_matched", [])

        return {
            "skill_coverage_pct": gap_data.get("skill_coverage_pct", 0),
            "skills_missing": skills_missing,
            "skills_matched": [
                m.get("skill_name", "") for m in (skills_matched or [])
            ],
            "verified_in_interview": list(verified_skills),
            "still_unverified": [
                s for s in skills_missing
                if s.lower() not in {v.lower() for v in verified_skills}
            ],
            "experience_gap": gap_data.get("experience_gap_summary", ""),
            "level_delta": gap_data.get("level_delta", 0),
            "recommended_focus": gap_data.get("recommended_focus_areas", []),
        }
