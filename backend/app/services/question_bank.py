import hashlib
import json
import logging
import random
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.question import QuestionData

logger = logging.getLogger(__name__)

# Language-specific question files; fall back to questions.json if missing
_QUESTIONS_FILE_MAP: dict[str, str] = {
    "en": "questions_en.json",
    "zh": "questions_zh.json",
}
_DEFAULT_QUESTIONS_FILE = "questions.json"


class QuestionBankService:
    """Manages question selection with adaptive difficulty logic.

    Loads questions from a language-specific JSON file so questions are
    already in the target interview language — no runtime translation needed.
    """

    DIFFICULTY_ORDER = ["junior", "mid", "senior"]
    DIFFICULTY_ADJUST_UP = "up"
    DIFFICULTY_ADJUST_DOWN = "down"

    def __init__(
        self,
        data_path: str | None = None,
        seed: str | None = None,
        language: str = "en",
    ) -> None:
        self._language = language
        self._questions: list[QuestionData] = []
        self._used_indices: set[int] = set()
        self._current_difficulty: str = "junior"
        self._consecutive_good: int = 0
        self._consecutive_poor: int = 0
        self._seed: str | None = seed
        self._rng = random.Random(seed) if seed else random.Random()

        if data_path is None:
            data_path = self._resolve_data_path()
        self._load(str(data_path))

    def _resolve_data_path(self) -> str:
        """Pick the language-preferring JSON file, falling back to questions.json."""
        data_dir = Path(__file__).parent.parent.parent / "data"

        # Prefer language-specific file
        lang_file = _QUESTIONS_FILE_MAP.get(self._language)
        if lang_file:
            lang_path = data_dir / lang_file
            if lang_path.exists():
                logger.info(f"Loading questions from {lang_path}")
                return str(lang_path)

        # Fall back to generic questions.json
        fallback = data_dir / _DEFAULT_QUESTIONS_FILE
        if fallback.exists():
            logger.warning(
                f"Language-specific questions not found for '{self._language}', "
                f"falling back to {fallback}"
            )
            return str(fallback)

        raise FileNotFoundError(
            f"No question bank file found for language '{self._language}' "
            f"and fallback {fallback} is missing."
        )

    def _load(self, path: str) -> None:
        """Load questions from a JSON file (fallback when DB not available)."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data["questions"]:
            self._questions.append(QuestionData(
                question_text=item["question_text"],
                category=item.get("category", "general"),
                difficulty=item.get("difficulty", "mid"),
                expected_keywords=item.get("expected_keywords", []),
                question_zh=item.get("question_zh"),  # kept for backward compat
            ))

    async def reload_from_db(self, db: AsyncSession) -> int:
        """Reload questions from the question_bank DB table.

        Uses question_zh column when language is 'zh', otherwise question_text.
        Only loads active questions. Preserves current selection state.
        Returns the number of questions loaded.
        """
        from app.models.question_bank import QuestionBank

        result = await db.execute(
            select(QuestionBank).where(QuestionBank.is_active == True)
        )
        rows = result.scalars().all()

        self._questions = []
        for q in rows:
            # Select the language-appropriate text
            if self._language == "zh" and q.question_zh and q.question_zh.strip():
                text = q.question_zh
            else:
                text = q.question_text

            self._questions.append(QuestionData(
                question_text=text,
                category=q.category,
                difficulty=q.difficulty,
                expected_keywords=q.expected_keywords or [],
                question_zh=q.question_zh,
            ))

        # Clear used indices that are now out of range
        max_idx = len(self._questions)
        self._used_indices = {i for i in self._used_indices if i < max_idx}

        logger.info(
            f"Reloaded {len(self._questions)} questions from question_bank table "
            f"(language={self._language})"
        )
        return len(self._questions)

    def select_question(
        self, category: str | None = None, difficulty: str | None = None
    ) -> QuestionData | None:
        """
        Select the next question. Filters by category (optional) and difficulty,
        excludes previously used questions. Returns None if no questions remain.
        """
        target_difficulty = difficulty or self._current_difficulty
        pool = [
            (i, q)
            for i, q in enumerate(self._questions)
            if i not in self._used_indices
            and q.difficulty == target_difficulty
            and (category is None or q.category == category)
        ]

        # If no questions at target difficulty, broaden search
        if not pool:
            pool = [
                (i, q)
                for i, q in enumerate(self._questions)
                if i not in self._used_indices
                and (category is None or q.category == category)
            ]

        if not pool:
            # Fallback: return any unused question regardless of category
            pool = [
                (i, q)
                for i, q in enumerate(self._questions)
                if i not in self._used_indices
            ]

        if not pool:
            return None

        index, question = self._rng.choice(pool)
        self._used_indices.add(index)
        return question

    def update_difficulty(self, score: int) -> None:
        """Adjust difficulty based on recent scores."""
        threshold = settings.scoring_consecutive_good

        if score >= 4:
            self._consecutive_good += 1
            self._consecutive_poor = 0
        elif score <= 2:
            self._consecutive_poor += 1
            self._consecutive_good = 0
        else:
            self._consecutive_good = 0
            self._consecutive_poor = 0

        if self._consecutive_good >= threshold:
            self._adjust_up()
            self._consecutive_good = 0

        if self._consecutive_poor >= threshold:
            self._adjust_down()
            self._consecutive_poor = 0

    def _adjust_up(self) -> None:
        current_idx = self.DIFFICULTY_ORDER.index(self._current_difficulty)
        if current_idx < len(self.DIFFICULTY_ORDER) - 1:
            self._current_difficulty = self.DIFFICULTY_ORDER[current_idx + 1]

    def _adjust_down(self) -> None:
        current_idx = self.DIFFICULTY_ORDER.index(self._current_difficulty)
        if current_idx > 0:
            self._current_difficulty = self.DIFFICULTY_ORDER[current_idx - 1]

    def set_seed(self, seed: str) -> None:
        """Set the random seed for deterministic question selection."""
        self._seed = seed
        self._rng = random.Random(seed)

    def set_initial_difficulty(self, experience_level: str) -> None:
        """Set the initial difficulty based on the candidate's experience level."""
        if experience_level in self.DIFFICULTY_ORDER:
            self._current_difficulty = experience_level

    def has_more_questions(self, category: str | None = None) -> bool:
        """Check if there are still unused questions."""
        if category:
            return any(
                i not in self._used_indices and q.category == category
                for i, q in enumerate(self._questions)
            )
        return len(self._used_indices) < len(self._questions)

    @property
    def current_difficulty(self) -> str:
        return self._current_difficulty

    @property
    def used_count(self) -> int:
        return len(self._used_indices)

    @property
    def total_count(self) -> int:
        return len(self._questions)

    @property
    def language(self) -> str:
        return self._language

    def reset(self) -> None:
        """Reset usage tracking (for testing). Rebuilds RNG from original seed."""
        self._used_indices.clear()
        self._current_difficulty = "junior"
        self._consecutive_good = 0
        self._consecutive_poor = 0
        self._rng = random.Random(self._seed) if self._seed else random.Random()
