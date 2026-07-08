import json
import logging
import re
from pathlib import Path

from pypdf import PdfReader

from app.config import settings
from app.llm.base import BaseLLMAdapter
from app.llm.prompts.resume_parser import get_resume_parse_prompt
from app.schemas.resume import ResumeData

logger = logging.getLogger(__name__)


class ResumeParserService:
    """Extracts text from PDF resumes and parses them into structured data via LLM."""

    def __init__(self, llm: BaseLLMAdapter) -> None:
        self._llm = llm

    def extract_text(self, file_path: str) -> str:
        """Extract raw text from a PDF file using pypdf."""
        text_pages: list[str] = []
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_pages.append(page_text)

        raw = "\n\n".join(text_pages)
        if not raw.strip():
            raise ValueError("Could not extract text from PDF — file may be empty or image-based.")
        return raw

    async def parse(self, file_path: str, language: str = "en") -> ResumeData:
        """Extract PDF text and parse with LLM into structured ResumeData."""
        raw_text = self.extract_text(file_path)

        # Truncate very long resumes to avoid token overflow
        max_chars = 15000
        if len(raw_text) > max_chars:
            raw_text = raw_text[:max_chars] + "\n...[truncated]"

        template = get_resume_parse_prompt(language)
        prompt = template.format(resume_text=raw_text)

        try:
            response = await self._llm.generate(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.1,
            )
            logger.debug(f"Resume parse raw response: {response[:300]}")
            data = self._parse_json(response)
        except Exception as e:
            logger.warning(f"LLM resume parsing failed: {e}")
            raise

        if data is None:
            raise ValueError("Failed to parse resume JSON from LLM response")

        return ResumeData(
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            summary=data.get("summary", ""),
            skills=data.get("skills", []),
            experience_years=data.get("experience_years", ""),
            experience=data.get("experience", []),
            education=data.get("education", []),
            projects=data.get("projects", []),
            suggested_job_title=data.get("suggested_job_title", ""),
        )

    def _parse_json(self, raw: str) -> dict | None:
        """Robust JSON parsing with multiple fallback strategies."""
        raw = raw.strip()

        # 1. Remove code fences
        fence_match = re.search(
            r"```(?:json)?\s*\n?([\s\S]*?)\n?```", raw
        )
        if fence_match:
            raw = fence_match.group(1).strip()

        # 2. Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 3. Extract first JSON object
        brace_match = re.search(r"\{[\s\S]*\}", raw)
        if brace_match:
            extracted = brace_match.group(0)
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                try:
                    fixed = re.sub(r",\s*}", "}", extracted)
                    fixed = re.sub(r",\s*]", "]", fixed)
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        logger.warning(f"Could not parse resume JSON from: {raw[:200]}")
        return None
