"""Pytest hooks shared across the test suite."""

from __future__ import annotations

import os

import pytest

CURSOR_HARNESS_SKIP_REASON = (
    "cursor_harness tests require local .cursor/skills recursive-loop scripts "
    "and changelog fixtures (not available on GitHub Actions)"
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "cursor_harness: recursive-loop agent tooling; run locally via scripts/dev/run-cursor-harness-tests.sh",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    skip_ci = pytest.mark.skip(reason=CURSOR_HARNESS_SKIP_REASON)
    for item in items:
        if "cursor_harness" in item.keywords:
            item.add_marker(skip_ci)
