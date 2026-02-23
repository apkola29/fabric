"""
Fabric Data Agent - MCP Client

Interactive client to query a published Microsoft Fabric Data Agent via the
Model Context Protocol (MCP). Uses JSON-RPC 2.0 over HTTP with SPN authentication.

MCP Methods:
    1. initialize  - Protocol handshake with the MCP server
    2. tools/list  - Discover available tools (agent name + input schema)
    3. tools/call  - Send a question to the agent and get a response

Authentication:
    POST https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token
    OAuth2 client_credentials grant, scoped to:
        https://api.fabric.microsoft.com/.default

MCP Endpoint:
    POST https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspaceId}
         /dataagents/{agentId}/agent
    Headers: Authorization: Bearer {token}, Content-Type: application/json
    Body:    JSON-RPC 2.0 message

Usage:
    python mcp_client.py
"""

import json
import requests


def get_config() -> dict:
    """Prompt for SPN credentials and Fabric IDs."""
    print("=" * 60)
    print("  Fabric Data Agent - MCP Client")
    print("=" * 60)
    print()
    print("Enter your SPN and Fabric details below.")
    print()

    tenant_id    = input("  Tenant ID      : ").strip()
    client_id    = input("  Client ID      : ").strip()
    client_secret = input("  Client Secret  : ").strip()
    workspace_id = input("  Workspace ID   : ").strip()
    agent_id     = input("  Agent ID       : ").strip()

    if not all([tenant_id, client_id, client_secret, workspace_id, agent_id]):
        print("\n  [ERROR] All fields are required.")
        raise SystemExit(1)

    return {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "workspace_id": workspace_id,
        "agent_id": agent_id,
    }


def get_token(config: dict) -> str:
    """Acquire a Bearer token via OAuth2 client_credentials grant."""
    url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "scope": "https://api.fabric.microsoft.com/.default",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def mcp_request(token: str, mcp_url: str, method: str,
                params: dict = None, req_id: int = 1) -> dict:
    """Send a JSON-RPC 2.0 request to the MCP server and return the result."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params:
        payload["params"] = params

    resp = requests.post(mcp_url, headers=headers, json=payload)

    content_type = resp.headers.get("Content-Type", "")
    if "text/event-stream" in content_type:
        # SSE stream -- extract the last JSON-RPC result from the event data
        result = {}
        for line in resp.text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                try:
                    result = json.loads(line[len("data:"):].strip())
                except json.JSONDecodeError:
                    pass
        return result
    else:
        resp.raise_for_status()
        return resp.json()


def main():
    config = get_config()

    print()
    print("Authenticating...", end=" ", flush=True)
    try:
        token = get_token(config)
    except Exception as e:
        print(f"FAILED\n  {e}")
        return
    print("OK")

    mcp_url = (
        f"https://api.fabric.microsoft.com/v1/mcp/workspaces/"
        f"{config['workspace_id']}/dataagents/{config['agent_id']}/agent"
    )

    # --- Step 1: Initialize ---
    print()
    print("-" * 60)
    print("Step 1: MCP Initialize")
    print("-" * 60)
    init_resp = mcp_request(token, mcp_url, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "fabric-mcp-client", "version": "1.0.0"},
    }, req_id=1)

    server_info = init_resp.get("result", {}).get("serverInfo", {})
    print(f"  Server: {server_info.get('name', '?')} v{server_info.get('version', '?')}")
    print(f"  Protocol: {init_resp.get('result', {}).get('protocolVersion', '?')}")

    # --- Step 2: List Tools ---
    print()
    print("-" * 60)
    print("Step 2: List Available Tools")
    print("-" * 60)
    tools_resp = mcp_request(token, mcp_url, "tools/list", {}, req_id=2)

    tools = tools_resp.get("result", {}).get("tools", [])
    if not tools:
        print("  No tools found. Is the agent published?")
        return

    tool_name = tools[0].get("name", "")
    print(f"  Found {len(tools)} tool(s):")
    for t in tools:
        print(f"    - {t.get('name', '?')}")
        schema = t.get("inputSchema", {})
        props = schema.get("properties", {})
        for prop, info in props.items():
            req = "required" if prop in schema.get("required", []) else "optional"
            print(f"      param: {prop} ({info.get('type', '?')}, {req})")

    # --- Step 3: Interactive chat ---
    print()
    print("-" * 60)
    print(f"Connected via MCP. Tool: {tool_name}")
    print("Type your questions below. Type 'quit' or 'exit' to stop.")
    print("-" * 60)

    req_id = 3
    while True:
        print()
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        print("Agent: ", end="", flush=True)
        try:
            resp = mcp_request(token, mcp_url, "tools/call", {
                "name": tool_name,
                "arguments": {"userQuestion": question},
            }, req_id=req_id)
            req_id += 1

            # Extract response text
            result = resp.get("result", {})
            content = result.get("content", [])
            if content:
                for block in content:
                    if block.get("type") == "text":
                        print(block.get("text", ""))
            elif "error" in resp:
                err = resp["error"]
                print(f"[ERROR] {err.get('message', err)}")
            else:
                print("[No response from agent]")
        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
