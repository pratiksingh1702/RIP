"""
Simple test MCP server (JSON-RPC over HTTP).

Fixes vs. the original:
  - Every request now gets a response (no more silent connection drops).
  - Unknown methods/tools return a proper JSON-RPC error instead of nothing.
  - Handles notifications (requests with no "id") without trying to reply
    with a JSON-RPC id-bearing response.
  - Guards against missing/invalid Content-Length and malformed JSON.
  - Adds a "search" tool (since that's what real clients were calling).
  - Basic logging so failures are visible on the server side too.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mcp-server")

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get fake weather info",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
    {
        "name": "search",
        "description": "Search for something",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]


def call_get_weather(args):
    city = args.get("city", "Unknown")
    return [{"type": "text", "text": f"Weather in {city}: Sunny, 72°F (22°C)"}]


def call_search(args):
    query = args.get("query", "")
    limit = args.get("limit", 5)
    return [{"type": "text", "text": f"Fake search results for '{query}' (limit={limit})"}]


TOOL_HANDLERS = {
    "get_weather": call_get_weather,
    "search": call_search,
}


class SimpleMCPHandler(BaseHTTPRequestHandler):

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _rpc_result(self, req_id, result):
        self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": result})

    def _rpc_error(self, req_id, code, message, status=200):
        self._send_json(status, {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

    def log_message(self, fmt, *args):
        log.info("%s - %s", self.client_address[0], fmt % args)

    def do_POST(self):
        req_id = None
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            request = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, json.JSONDecodeError) as exc:
            log.warning("Bad request body: %s", exc)
            self._rpc_error(None, -32700, "Parse error", status=400)
            return

        method = request.get("method")
        req_id = request.get("id")
        is_notification = req_id is None

        try:
            if method == "initialize":
                self._rpc_result(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "test-mcp-server", "version": "1.1.0"},
                })

            elif method == "tools/list":
                self._rpc_result(req_id, {"tools": TOOLS})

            elif method == "tools/call":
                params = request.get("params") or {}
                tool_name = params.get("name")
                tool_args = params.get("arguments") or {}
                handler = TOOL_HANDLERS.get(tool_name)

                if handler is None:
                    self._rpc_error(req_id, -32601, f"Unknown tool: {tool_name}")
                    return

                content = handler(tool_args)
                self._rpc_result(req_id, {"content": content})

            elif method == "notifications/initialized":
                # Notifications expect no JSON-RPC response body.
                self.send_response(204)
                self.end_headers()

            elif is_notification:
                # Unknown notification: still must not hang the client.
                self.send_response(204)
                self.end_headers()

            else:
                self._rpc_error(req_id, -32601, f"Method not found: {method}")

        except Exception as exc:  # noqa: BLE001 - last line of defense
            log.exception("Unhandled error processing request")
            if not is_notification:
                self._rpc_error(req_id, -32603, f"Internal error: {exc}", status=500)
            else:
                self.send_response(204)
                self.end_headers()


def run_server(port=8765):
    httpd = HTTPServer(("0.0.0.0", port), SimpleMCPHandler)
    log.info("Test MCP Server running on http://localhost:%d", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        log.info("Test MCP Server stopped")


if __name__ == "__main__":
    run_server()