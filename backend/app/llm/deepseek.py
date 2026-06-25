import asyncio
import logging

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

from app.config import settings
from app.llm.base import BaseLLMAdapter

logger = logging.getLogger(__name__)


class DeepSeekAdapter(BaseLLMAdapter):
    """LLM adapter for DeepSeek API (OpenAI-compatible protocol)."""

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds (1s, 2s, 4s)

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.deepseek_api_key
        self._model = model or settings.deepseek_model
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=base_url or settings.deepseek_base_url,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Call DeepSeek with retry logic and exponential backoff."""
        last_error: Exception | None = None

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self._client.chat.completions.create(
                        model=self._model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    timeout=settings.llm_request_timeout,
                )
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    return content if content else ""
                return ""

            except (APIError, APITimeoutError, RateLimitError) as e:
                last_error = e
                logger.warning(
                    f"DeepSeek API error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
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
            f"DeepSeek API call failed after {self.MAX_RETRIES} retries"
        ) from last_error
