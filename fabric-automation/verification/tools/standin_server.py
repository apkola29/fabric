"""A stand-in MCP server over stdio for the replay of the helper findings. usage: python standin_server.py MODE

future     server/discover is unknown; initialize is refused and names only a future revision
boolproto  server/discover is unknown; initialize answers with a boolean protocolVersion
futureok   server/discover is unknown; initialize succeeds and names only a future revision
leak       server/discover is unknown; initialize answers with a token-shaped name and a host-shaped version
"""
import json
import sys

MODE = sys.argv[1]
TOKEN = "ghp_" + "A1b2C3d4E5" * 2 + "F6G7h8I9"


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
        if MODE == "future":
            send({"jsonrpc": "2.0", "id": ident,
                  "error": {"code": -32022, "message": "Unsupported protocol version", "data": {"supported": ["2027-01-01"]}}})
        elif MODE == "boolproto":
            send({"jsonrpc": "2.0", "id": ident,
                  "result": {"protocolVersion": True, "capabilities": {}, "serverInfo": {"name": "Stand-in", "version": "1.0"}}})
        elif MODE == "futureok":
            send({"jsonrpc": "2.0", "id": ident,
                  "result": {"protocolVersion": "2027-01-01", "capabilities": {}, "serverInfo": {"name": "Stand-in", "version": "1.0"}}})
        else:
            send({"jsonrpc": "2.0", "id": ident,
                  "result": {"protocolVersion": "2025-06-18", "capabilities": {},
                             "serverInfo": {"name": "Server " + TOKEN, "version": "internal.contoso.corp"}}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": ident, "result": {"tools": [{"name": "one", "inputSchema": {"type": "object"}}]}})
