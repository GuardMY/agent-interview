import asyncio
import logging

import anthropic
from anthropic import APIError, APITimeoutError, RateLimitError

from app.config import settings
from app.llm.base import BaseLLMAdapter

logger = logging.getLogger(__name__)


class ClaudeAdapter(BaseLLMAdapter):
    """LLM adapter for Anthropic's Claude API."""

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds (1s, 2s, 4s)

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.llm_model
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Call Claude with retry logic and exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self._client.messages.create(
                        model=self._model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system=system_prompt or "",
                        messages=[{"role": "user", "content": prompt}],
                    ),
                    timeout=settings.llm_request_timeout,
                )
                # Extract text from response
                if response.content and len(response.content) > 0:
                    return response.content[0].text
                return ""

            except (APIError, APITimeoutError, RateLimitError) as e:
                last_error = e
                logger.warning(
                    f"Claude API error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Request timed out after {settings.llm_request_timeout}s"
                )
                logger.warning(
                    f"Timeout (attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(f"All {self.MAX_RETRIES} retries failed. Last error: {last_error}")
        raise RuntimeError(
            f"Claude API call failed after {self.MAX_RETRIES} retries"
        ) from last_error
