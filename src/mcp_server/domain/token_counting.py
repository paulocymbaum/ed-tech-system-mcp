"""Port for estimating LLM token usage without provider-specific dependencies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenCounts:
    """Aggregate and per-field token estimates for one LLM invocation."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    system_prompt_tokens: int = 0
    user_prompt_tokens: int = 0
    raw_output_tokens: int = 0


class ITokenCounter(ABC):
    """Port for counting tokens in prompt and completion text."""

    @abstractmethod
    def count(self, text: str, *, model_name: str | None = None) -> int:
        """Return the estimated token count for ``text``."""

    def count_invocation(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        raw_output: str,
        model_name: str | None = None,
    ) -> TokenCounts:
        """Count tokens for a typical system + user → completion exchange."""
        system_tokens = self.count(system_prompt, model_name=model_name)
        user_tokens = self.count(user_prompt, model_name=model_name)
        output_tokens = self.count(raw_output, model_name=model_name)
        input_tokens = system_tokens + user_tokens
        return TokenCounts(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            system_prompt_tokens=system_tokens,
            user_prompt_tokens=user_tokens,
            raw_output_tokens=output_tokens,
        )
