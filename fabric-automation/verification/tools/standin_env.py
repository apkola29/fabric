"""A stand-in MCP server (legacy handshake) that records which of the named environment variables it was started with.

usage: python standin_env.py OUTPUT_FILE
"""
import json
import os
import sys

NAMES = ("npm_config_before", "UV_EXCLUDE_NEWER", "GITHUB_TOKEN", "NPM_TOKEN", "AZURE_CLIENT_SECRET", "npm_config_registry")
seen = {}
for name in NAMES:
    for key, value in os.environ.items():
        if key.lower() == name.lower():
            seen[name] = value
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(seen, handle)


def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    try:
        message = json.loads(line)
    except ValueError:
        continue
    method, ident = message.get("method"), message.get("id")
    if method is None or ident is None:
        continue
    if method == "server/discover":
        send({"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "Method not found"}})
    elif method == "initialize":
        send({"jsonrpc": "2.0", "id": ident,
              "result": {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "Stand-in", "version": "1.0"}}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": ident, "result": {"tools": [{"name": "one", "inputSchema": {"type": "object"}}]}})
