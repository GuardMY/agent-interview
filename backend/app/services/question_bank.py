import json
import random
from pathlib import Path

from app.config import settings
from app.schemas.question import QuestionData


class QuestionBankService:
    """Manages question selection with adaptive difficulty logic."""

    DIFFICULTY_ORDER = ["junior", "mid", "senior"]
    DIFFICULTY_ADJUST_UP = "up"
    DIFFICULTY_ADJUST_DOWN = "down"

    def __init__(self, data_path: str | None = None) -> None:
        if data_path is None:
            data_path = Path(__file__).parent.parent.parent / "data" / "questions.json"
        self._questions: list[QuestionData] = []
        self._used_indices: set[int] = set()
        self._current_difficulty: str = "junior"
        self._consecutive_good: int = 0
        self._consecutive_poor: int = 0
        self._load(str(data_path))

    def _load(self, path: str) -> None:
        """Load questions from a JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data["questions"]:
            self._questions.append(QuestionData(**item))

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

        index, question = random.choice(pool)
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

    def reset(self) -> None:
        """Reset usage tracking (for testing)."""
        self._used_indices.clear()
        self._current_difficulty = "junior"
        self._consecutive_good = 0
        self._consecutive_poor = 0
