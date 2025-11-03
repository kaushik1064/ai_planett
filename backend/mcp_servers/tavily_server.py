"""Minimal MCP-compatible stdio server wrapping Tavily search."""

from __future__ import annotations

import json
import sys
from typing import Any

from tavily import TavilyClient


def _respond(response: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def main() -> None:
    client = TavilyClient()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "serverInfo": {"name": "tavily-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": True},
                },
            })
            continue

        if method == "shutdown":
            _respond({"jsonrpc": "2.0", "id": req_id, "result": None})
            break

        if method == "tavily_search":
            params = request.get("params", {})
            query = params.get("query", "")
            max_results = params.get("max_results", 5)
            include_images = params.get("include_images", False)
            try:
                result = client.search(query=query, max_results=max_results, include_images=include_images)
                _respond({"jsonrpc": "2.0", "id": req_id, "result": result})
            except Exception as exc:  # pragma: no cover
                _respond({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}})
            continue

        _respond({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Unknown method"}})


if __name__ == "__main__":
    main()


