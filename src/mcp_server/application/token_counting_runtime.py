"""Runtime accessor for the wired token counter port."""

from __future__ import annotations

from mcp_server.domain.token_counting import ITokenCounter, TokenCounts


class _NoOpTokenCounter(ITokenCounter):
    """Fallback counter used before bootstrap or in tests without wiring."""

    def count(self, text: str, *, model_name: str | None = None) -> int:
        _ = model_name
        return 0

    def count_invocation(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        raw_output: str,
        model_name: str | None = None,
    ) -> TokenCounts:
        _ = model_name
        return TokenCounts(input_tokens=0, output_tokens=0, total_tokens=0)


_token_counter: ITokenCounter = _NoOpTokenCounter()


def set_token_counter(counter: ITokenCounter | None) -> None:
    """Replace the process-wide token counter (``None`` resets to no-op)."""
    global _token_counter
    _token_counter = counter if counter is not None else _NoOpTokenCounter()


def get_token_counter() -> ITokenCounter:
    """Return the wired token counter."""
    return _token_counter


def reset_token_counter() -> None:
    """Reset to the no-op counter (for tests)."""
    set_token_counter(None)
