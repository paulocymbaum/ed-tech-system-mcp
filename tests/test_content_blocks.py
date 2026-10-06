"""Tests for Praxis v2 content-block fence validation (GA-10..13)."""

from __future__ import annotations

import pytest

from mcp_server.domain.content_blocks import has_content_blocks, validate_content_blocks


def tip(tone: str = "tip", body: str = "**Title.** Keep `x` non-zero.") -> str:
    return f"```edtech-tip tone={tone}\n{body}\n```"


class TestValidBlocks:
    def test_valid_tip_block_is_ok(self) -> None:
        report = validate_content_blocks(tip())
        assert report.ok

    def test_warning_tip_is_ok(self) -> None:
        report = validate_content_blocks(tip(tone="warning"))
        assert report.ok

    def test_valid_vocabulary_grid(self) -> None:
        md = "```edtech-vocabulary\nFloat | 1.0 (ponto flutuante)\nHalf (0.5) | 180°\n```"
        assert validate_content_blocks(md).ok

    def test_valid_educator_notes(self) -> None:
        md = "```edtech-educator-notes\nDevelops computational thinking.\n```"
        assert validate_content_blocks(md).ok

    def test_valid_visualizer(self) -> None:
        md = "```edtech-visualizer component=fraction-pizza\nangle = (360 / 4) * n\n```"
        assert validate_content_blocks(md).ok

    def test_plain_code_fences_are_ignored(self) -> None:
        md = "```python\nprint('hello edtech-unknown')\n```"
        assert validate_content_blocks(md).ok
        assert not has_content_blocks(md)

    def test_multiple_blocks_all_validated(self) -> None:
        md = f"# Lesson\n\n{tip()}\n\n```edtech-vocabulary\nFloat | 1.0\n```"
        assert validate_content_blocks(md).ok
        assert has_content_blocks(md)


class TestInvalidBlocks:
    def test_unknown_block_type_fails_loud(self) -> None:
        report = validate_content_blocks("```edtech-typo\nx\n```")
        assert not report.ok
        assert any("unknown block type 'edtech-typo'" in f.message for f in report.findings)

    def test_tip_requires_tone(self) -> None:
        report = validate_content_blocks("```edtech-tip\nBody.\n```")
        assert not report.ok
        assert any("tone=tip|warning" in f.message for f in report.findings)

    def test_tip_rejects_bad_tone(self) -> None:
        report = validate_content_blocks("```edtech-tip tone=info\nBody.\n```")
        assert not report.ok

    def test_empty_tip_body_fails(self) -> None:
        report = validate_content_blocks("```edtech-tip tone=tip\n\n```")
        assert not report.ok

    def test_vocabulary_row_without_pipe_fails(self) -> None:
        report = validate_content_blocks("```edtech-vocabulary\nFloat is a type\n```")
        assert not report.ok
        assert any("'term | subtitle'" in f.message for f in report.findings)

    def test_unknown_visualizer_fails(self) -> None:
        report = validate_content_blocks("```edtech-visualizer component=rocket\nx\n```")
        assert not report.ok
        assert any("unknown visualizer 'rocket'" in f.message for f in report.findings)

    def test_unclosed_block_fails(self) -> None:
        report = validate_content_blocks("# Lesson\n\n```edtech-tip tone=tip\nnever closed")
        assert not report.ok
        assert any("never closed" in f.message for f in report.findings)

    def test_errors_carry_line_numbers(self) -> None:
        report = validate_content_blocks("```edtech-tip tone=nope\nx\n```")
        assert any("line 1" in f.message for f in report.findings)


class TestNoBlocks:
    def test_plain_markdown_is_ok(self) -> None:
        assert validate_content_blocks("# Lesson\n\nJust prose with `code`.\n").ok

    def test_empty_is_ok(self) -> None:
        assert validate_content_blocks("").ok


@pytest.mark.parametrize(
    ("md", "expected"),
    [
        ("```edtech-tip tone=tip\nx\n```", True),
        ("```edtech-vocabulary\na | b\n```", True),
        ("```python\nprint('x')\n```", False),
        ("no fences at all", False),
    ],
)
def test_has_content_blocks(md: str, expected: bool) -> None:
    assert has_content_blocks(md) is expected
