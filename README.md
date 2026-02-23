# Fabric Data Agent CLI

Interactive CLI client to query any published [Microsoft Fabric Data Agent](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agents) using Service Principal (SPN) authentication.

No user credentials are passed through -- only the SPN's `client_credentials` grant is used.

## Prerequisites

- **Python 3.10+**
- A **Service Principal** (App Registration) in Microsoft Entra ID
- A **Fabric Data Agent** that has been **published** in the Fabric portal

### SPN Permissions

| Requirement | Details |
|---|---|
| Workspace access | The SPN must have **Contributor** (or higher) role on the Fabric workspace |
| Semantic Model access | If the agent uses a Semantic Model data source, the SPN needs **Build** permission on that model |
| XMLA endpoints | Must be enabled in the tenant for Semantic Model-backed agents |

## Setup

```bash
git clone https://github.com/apkola29/fabric.git
cd fabric
pip install -r requirements.txt
```

## Usage

```bash
python fabric_agent.py
```

You will be prompted for five values:

| Field | Where to find it |
|---|---|
| **Tenant ID** | Azure portal > Microsoft Entra ID > Overview |
| **Client ID** | Azure portal > App Registrations > your SPN > Application (client) ID |
| **Client Secret** | Azure portal > App Registrations > your SPN > Certificates & secrets |
| **Workspace ID** | Fabric portal URL: `app.fabric.microsoft.com/groups/{workspaceId}/...` |
| **Agent ID** | Fabric portal > Data Agent > Settings > Properties, or from the agent's programmatic URL |

Once authenticated, you enter an interactive chat loop:

```
============================================================
  Fabric Data Agent - Interactive Client
============================================================

Enter your SPN and Fabric details below.

  Tenant ID      : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client ID      : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client Secret  : ********************************
  Workspace ID   : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Agent ID       : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

Authenticating... OK

Connected to Data Agent. Type your questions below.
Type 'quit' or 'exit' to stop.
------------------------------------------------------------

You: what are the tables connected to this agent?
Agent: ... The agent has access to the following tables: ...
```

## How It Works

### Authentication

The script acquires a Bearer token via **OAuth2 client_credentials** flow:

```
POST https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token

grant_type    = client_credentials
client_id     = {spn_client_id}
client_secret = {spn_client_secret}
scope         = https://api.fabric.microsoft.com/.default
```

### API

The Data Agent exposes an **OpenAI Assistants-compatible** endpoint:

```
Base URL:
  https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/dataagents/{agentId}/aiassistant/openai
```

The script uses the OpenAI Python SDK to make these calls in sequence:

| Step | Method | Path | Purpose |
|---|---|---|---|
| 1 | `POST` | `/assistants` | Register an assistant handle |
| 2 | `POST` | `/threads` | Create a conversation session |
| 3 | `POST` | `/threads/{id}/messages` | Post user question |
| 4 | `POST` | `/threads/{id}/runs` | Trigger agent processing |
| 5 | `GET` | `/threads/{id}/runs/{id}` | Poll run status until completion |
| 6 | `GET` | `/threads/{id}/messages` | Retrieve agent response |
| 7 | `DELETE` | `/threads/{id}` | Clean up session |

All requests include:
- `Authorization: Bearer {spn_token}`
- `?api-version=2024-05-01-preview`

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Bad SPN credentials or expired secret | Verify Client ID/Secret in Entra; regenerate secret if expired |
| `403 Forbidden` | SPN lacks workspace access | Grant SPN **Contributor** role on the workspace |
| `404 Not Found` | Wrong workspace/agent ID, or agent not published | Double-check IDs; publish the agent in Fabric portal |
| `Stage configuration not found` | Agent is not published | Open the agent in Fabric portal and click **Publish** |
| `PowerBINotAuthorizedException` | SPN lacks Build permission on the Semantic Model | Grant Build permission on the model; enable XMLA endpoints |
| `Timed out waiting for agent response` | Agent took longer than 5 minutes | Retry; check agent health in Fabric portal |
