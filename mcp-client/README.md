# Fabric Data Agent - MCP Client

Interactive client to query a published Microsoft Fabric Data Agent via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Uses JSON-RPC 2.0 over HTTP with SPN authentication.

## How MCP Works

MCP provides a standardized way to interact with AI tools. The Fabric Data Agent exposes itself as an MCP server with a single tool per agent.

The client makes three types of JSON-RPC 2.0 calls:

| Method | Purpose | Key Response Fields |
|---|---|---|
| `initialize` | Protocol handshake | Server name, version, protocol version |
| `tools/list` | Discover available tools | Tool name, input schema (`userQuestion`) |
| `tools/call` | Send a question to the agent | Agent response text |

### MCP Endpoint

```
POST https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspaceId}/dataagents/{agentId}/agent
```

### Request Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "DataAgent_{agentName}",
    "arguments": {
      "userQuestion": "What tables do you have access to?"
    }
  }
}
```

## Prerequisites

- **Python 3.10+**
- A **Service Principal** (App Registration) in Microsoft Entra ID
- A **Fabric Data Agent** that has been **published** in the Fabric portal
- SPN must have **Contributor** role on the workspace

## Setup

```bash
cd mcp-client
pip install -r requirements.txt
```

## Usage

```bash
python mcp_client.py
```

You will be prompted for:

| Field | Where to find it |
|---|---|
| **Tenant ID** | Azure portal > Microsoft Entra ID > Overview |
| **Client ID** | Azure portal > App Registrations > your SPN > Application (client) ID |
| **Client Secret** | Azure portal > App Registrations > your SPN > Certificates & secrets |
| **Workspace ID** | Fabric portal URL: `app.fabric.microsoft.com/groups/{workspaceId}/...` |
| **Agent ID** | Fabric portal > Data Agent > Settings > Properties |

The script will:
1. Authenticate with the SPN
2. Initialize the MCP session
3. Discover the agent's tool name automatically
4. Enter an interactive chat loop

```
============================================================
  Fabric Data Agent - MCP Client
============================================================

Enter your SPN and Fabric details below.

  Tenant ID      : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client ID      : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client Secret  : ********************************
  Workspace ID   : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Agent ID       : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

Authenticating... OK

------------------------------------------------------------
Step 1: MCP Initialize
------------------------------------------------------------
  Server: DataAgent MCP Server v1.0.0
  Protocol: 2025-06-18

------------------------------------------------------------
Step 2: List Available Tools
------------------------------------------------------------
  Found 1 tool(s):
    - DataAgent_my_agent
      param: userQuestion (string, required)

------------------------------------------------------------
Connected via MCP. Tool: DataAgent_my_agent
Type your questions below. Type 'quit' or 'exit' to stop.
------------------------------------------------------------

You: what tables do you have access to?
Agent: I have access to the following tables...
```

## MCP vs OpenAI Assistants API

Both endpoints let you query the same Data Agent. Choose based on your use case:

| | MCP Client | OpenAI Assistants API |
|---|---|---|
| Protocol | JSON-RPC 2.0 | REST (OpenAI SDK) |
| Dependencies | `requests` only | `openai` + `requests` |
| Session management | Stateless per-call | Thread lifecycle (create/delete) |
| Best for | Simple integrations, MCP ecosystems | Multi-turn conversations, OpenAI tooling |

See [`data-agent-spn/`](../data-agent-spn/) for the OpenAI Assistants API approach.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Bad SPN credentials | Verify Client ID/Secret in Azure portal |
| `403 Forbidden` | SPN lacks workspace access | Grant SPN **Contributor** role on the workspace |
| No tools found | Agent not published | Publish the agent in the Fabric portal |
| `Stage configuration not found` | Agent not published | Open agent in Fabric portal, click **Publish** |
