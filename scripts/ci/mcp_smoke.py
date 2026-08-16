#!/usr/bin/env python3
"""Smoke-test MCP HTTP endpoints before deploy (health + RAG tools)."""

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
        help="Query passed to find_documents / run_workflow",
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
        for required in ("find_documents", "run_workflow"):
            if required not in tool_names:
                print(f"FAIL tools/list: missing {required}", file=sys.stderr)
                return 1
        print("PASS tools/list")

        if not os.environ.get("MCP_SMOKE_CALLER_JWT", "").strip():
            print("SKIP find_documents / run_workflow (set MCP_SMOKE_CALLER_JWT)")
            print("All MCP smoke checks passed.")
            return 0

        find_result = _call_tool(
            base_url,
            "find_documents",
            {"query": args.query, "document_limit": 3, "video_limit": 2},
            timeout=args.timeout,
        )
        structured = find_result.get("structuredContent")
        if not isinstance(structured, dict):
            msg = f"find_documents: missing structuredContent in {find_result!r}"
            raise RuntimeError(msg)
        print(f"PASS find_documents documents={len(structured.get('documents', []))}")

        workflow_result = _call_tool(
            base_url,
            "run_workflow",
            {"query": args.query, "document_limit": 3, "video_limit": 2},
            timeout=args.timeout,
        )
        workflow_structured = workflow_result.get("structuredContent")
        if not isinstance(workflow_structured, dict):
            msg = f"run_workflow: missing structuredContent in {workflow_result!r}"
            raise RuntimeError(msg)
        print(
            "PASS run_workflow "
            f"documents={workflow_structured.get('document_count')} "
            f"videos={workflow_structured.get('video_count')}"
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
