#!/usr/bin/env python3
"""Smoke-test MCP HTTP endpoints before deploy (health + non-RAG tools)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request


def _mcp_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    inbound = os.environ.get("MCP_INBOUND_TOKEN", "").strip()
    if inbound:
        headers["Authorization"] = f"Bearer {inbound}"
    caller = os.environ.get("MCP_SMOKE_CALLER_JWT", "").strip()
    if caller:
        headers["X-EdHarness-Caller-Jwt"] = caller.removeprefix("Bearer ").strip()
    return headers


def _post_json(url: str, payload: dict[str, object], *, timeout: float) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=_mcp_headers(),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")

    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    msg = "No SSE data payload in MCP response"
    raise RuntimeError(msg)


def _call_tool(base_url: str, name: str, arguments: dict[str, object], *, timeout: float) -> dict[str, object]:
    payload = _post_json(
        f"{base_url.rstrip('/')}/mcp",
        {
            "jsonrpc": "2.0",
            "id": name,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        timeout=timeout,
    )
    result = payload.get("result")
    if not isinstance(result, dict):
        msg = f"{name}: missing result in {payload!r}"
        raise RuntimeError(msg)
    if result.get("isError"):
        content = result.get("content")
        msg = f"{name}: tool error {content!r}"
        raise RuntimeError(msg)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MCP HTTP smoke test")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="MCP server base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-request timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--query",
        default="smoke test",
        help="Query passed to search_youtube / build_lesson_enrichment_query",
    )
    args = parser.parse_args(argv)
    base_url = args.base_url.rstrip("/")

    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=min(args.timeout, 30.0)) as response:
            health = json.loads(response.read().decode("utf-8"))
        if health.get("status") != "ok":
            print(f"FAIL health: unexpected payload {health!r}", file=sys.stderr)
            return 1
        print("PASS /health")

        inbound = os.environ.get("MCP_INBOUND_TOKEN", "").strip()
        if not inbound:
            print("SKIP tools/list (set MCP_INBOUND_TOKEN for /mcp checks)")
            print("All MCP smoke checks passed.")
            return 0

        tools_payload = _post_json(
            f"{base_url}/mcp",
            {"jsonrpc": "2.0", "id": "tools/list", "method": "tools/list", "params": {}},
            timeout=args.timeout,
        )
        tools = tools_payload.get("result", {}).get("tools", [])
        tool_names = {tool["name"] for tool in tools if isinstance(tool, dict) and "name" in tool}
        for required in ("search_youtube", "build_lesson_enrichment_query"):
            if required not in tool_names:
                print(f"FAIL tools/list: missing {required}", file=sys.stderr)
                return 1
        print("PASS tools/list")

        if not os.environ.get("MCP_SMOKE_CALLER_JWT", "").strip():
            print("SKIP search_youtube / build_lesson_enrichment_query (set MCP_SMOKE_CALLER_JWT)")
            print("All MCP smoke checks passed.")
            return 0

        youtube_result = _call_tool(
            base_url,
            "search_youtube",
            {"query": args.query, "max_results": 3, "language": "en", "safe_search": True},
            timeout=args.timeout,
        )
        structured = youtube_result.get("structuredContent")
        if not isinstance(structured, dict):
            msg = f"search_youtube: missing structuredContent in {youtube_result!r}"
            raise RuntimeError(msg)
        print(f"PASS search_youtube videos={len(structured.get('videos', []))}")

        query_result = _call_tool(
            base_url,
            "build_lesson_enrichment_query",
            {
                "course_title": "smoke course",
                "module_title": "smoke module",
                "lesson_title": args.query,
            },
            timeout=args.timeout,
        )
        query_structured = query_result.get("structuredContent")
        if not isinstance(query_structured, dict):
            msg = f"build_lesson_enrichment_query: missing structuredContent in {query_result!r}"
            raise RuntimeError(msg)
        print(
            "PASS build_lesson_enrichment_query "
            f"terms={query_structured.get('terms')}"
        )
    except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        text = str(exc)
        if re.search(r"\b50[23]\b", text):
            print(
                "FAIL: upstream returned 502/503 — container may be cold-starting or OOM. "
                "Retry after warm-up or check Render logs.",
                file=sys.stderr,
            )
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("All MCP smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
