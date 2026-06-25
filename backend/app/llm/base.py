from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):
    """Abstract base for LLM providers. Implementations handle API calls."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Generate a text response from the LLM."""
        ...
