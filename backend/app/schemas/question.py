from pydantic import BaseModel


class QuestionData(BaseModel):
    question_text: str
    category: str
    difficulty: str
    expected_keywords: list[str] = []
    question_zh: str | None = None
