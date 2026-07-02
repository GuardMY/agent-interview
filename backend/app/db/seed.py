"""Seed the question_bank table from JSON data on first run.

Loads from questions_en.json (question_text) and questions_zh.json (question_zh),
merging by position to produce bilingual DB entries.
"""

import json
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_bank import QuestionBank

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_QUESTIONS_EN = _DATA_DIR / "questions_en.json"
_QUESTIONS_ZH = _DATA_DIR / "questions_zh.json"
# Legacy fallback
_QUESTIONS_JSON = _DATA_DIR / "questions.json"


def _load_json(path: Path) -> list[dict]:
    """Load question items from a JSON file. Returns empty list if missing."""
    if not path.exists():
        logger.warning(f"Question file not found: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


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
