"""Seed the question_bank and job_positions tables from JSON data on first run.

Loads from questions_en.json (question_text) and questions_zh.json (question_zh),
merging by position to produce bilingual DB entries.
Also seeds job positions from job_positions.json.
"""

import json
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_bank import QuestionBank
from app.models.job_position import JobPosition

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_QUESTIONS_EN = _DATA_DIR / "questions_en.json"
_QUESTIONS_ZH = _DATA_DIR / "questions_zh.json"
# Legacy fallback
_QUESTIONS_JSON = _DATA_DIR / "questions.json"
_JOB_POSITIONS = _DATA_DIR / "job_positions.json"


def _load_json(path: Path) -> list[dict]:
    """Load items from a JSON file. Returns empty list if missing."""
    if not path.exists():
        logger.warning(f"Data file not found: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Support both {"questions": [...]} and {"positions": [...]} wrappers
    if "questions" in data:
        return data.get("questions", [])
    if "positions" in data:
        return data.get("positions", [])
    return []


async def seed_question_bank(db: AsyncSession) -> None:
    """Seed question_bank from language-specific JSON files if the table is empty."""
    result = await db.execute(select(func.count(QuestionBank.id)))
    count = result.scalar()
    if count and count > 0:
        logger.info(f"Question bank already has {count} questions, skipping seed.")
        return

    # Try language-specific files first, fall back to legacy questions.json
    en_questions = _load_json(_QUESTIONS_EN)
    zh_questions = _load_json(_QUESTIONS_ZH)

    if not en_questions:
        # Fall back to legacy questions.json
        legacy = _load_json(_QUESTIONS_JSON)
        if not legacy:
            logger.warning("No question bank files found, skipping seed.")
            return
        en_questions = legacy

    # Map zh questions by position for merging
    zh_by_idx: dict[int, str] = {}
    for i, item in enumerate(zh_questions):
        if item.get("question_text"):
            zh_by_idx[i] = item["question_text"]

    seeded = []
    for i, item in enumerate(en_questions):
        question_zh = zh_by_idx.get(i)

        seeded.append(
            QuestionBank(
                question_text=item["question_text"],
                category=item.get("category", "general"),
                difficulty=item.get("difficulty", "mid"),
                expected_keywords=item.get("expected_keywords", []),
                question_zh=question_zh,
            )
        )

    if seeded:
        db.add_all(seeded)
        await db.commit()
        # Log how many have Chinese translations
        zh_count = sum(1 for q in seeded if q.question_zh)
        logger.info(
            f"Seeded question bank with {len(seeded)} questions "
            f"({zh_count} with Chinese translations)."
        )


async def seed_job_positions(db: AsyncSession) -> None:
    """Seed job_positions from JSON file if the table is empty."""
    result = await db.execute(select(func.count(JobPosition.id)))
    count = result.scalar()
    if count and count > 0:
        logger.info(f"Job positions already has {count} entries, skipping seed.")
        return

    positions_data = _load_json(_JOB_POSITIONS)
    if not positions_data:
        logger.warning("No job_positions.json found, skipping seed.")
        return

    seeded = []
    for item in positions_data:
        seeded.append(
            JobPosition(
                title=item["title"],
                department=item.get("department", ""),
                level=item.get("level", "mid"),
                description=item.get("description"),
                responsibilities=item.get("responsibilities", []),
                required_skills=item.get("required_skills", []),
                preferred_skills=item.get("preferred_skills", []),
                soft_skill_requirements=item.get("soft_skill_requirements", {}),
                domain_knowledge=item.get("domain_knowledge"),
                default_total_questions=item.get("default_total_questions", 8),
                default_duration_minutes=item.get("default_duration_minutes", 45),
                interview_focus_areas=item.get("interview_focus_areas", []),
            )
        )

    if seeded:
        db.add_all(seeded)
        await db.commit()
        logger.info(f"Seeded job positions with {len(seeded)} entries.")
