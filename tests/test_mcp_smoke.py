"""Tests for scripts/ci/mcp_smoke.py."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "scripts/ci/mcp_smoke.py"
SMOKE_SHELL = REPO_ROOT / "scripts/ci/mcp-smoke.sh"


def test_mcp_smoke_script_exists() -> None:
    assert SMOKE_SCRIPT.is_file()
    assert SMOKE_SHELL.is_file()
    script = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert "find_documents" not in script
    assert "run_workflow" not in script
    assert "search_youtube" in script
    assert "search_web" in script
    assert "build_lesson_enrichment_query" in script


def test_mcp_smoke_parses_sse_payload() -> None:
    import importlib.util
    import urllib.request

    spec = importlib.util.spec_from_file_location("mcp_smoke", SMOKE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _post_json = module._post_json

    class _FakeResponse:
        def __init__(self, body: str) -> None:
            self._body = body.encode("utf-8")

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    payload = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
    body = f"event: message\ndata: {json.dumps(payload)}\n\n"

    original = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: _FakeResponse(body)  # type: ignore[assignment]
    try:
        parsed = _post_json("http://example.test/mcp", {"jsonrpc": "2.0"}, timeout=5.0)
    finally:
        urllib.request.urlopen = original

    assert parsed == payload
