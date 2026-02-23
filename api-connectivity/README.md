# Fabric API Connectivity Test

Quick connectivity check for Service Principal (SPN) access to a Microsoft Fabric workspace. Verifies token acquisition and basic REST API calls.

## What It Tests

| Check | API Call | What It Proves |
|---|---|---|
| 1. Token Acquisition | `POST /oauth2/v2.0/token` | SPN credentials are valid |
| 2. List Items | `GET /v1/workspaces/{id}/items` | SPN has workspace access |
| 3. Get Item | `GET /v1/workspaces/{id}/items/{itemId}` | Item-level read works |

## Setup

```bash
cd api-connectivity
pip install -r requirements.txt
```

## Usage

```bash
python test_connectivity.py
```

You will be prompted for:

| Field | Where to find it |
|---|---|
| **Tenant ID** | Azure portal > Microsoft Entra ID > Overview |
| **Client ID** | Azure portal > App Registrations > your SPN > Application (client) ID |
| **Client Secret** | Azure portal > App Registrations > your SPN > Certificates & secrets |
| **Workspace ID** | Fabric portal URL: `app.fabric.microsoft.com/groups/{workspaceId}/...` |

## Expected Output

```
============================================================
  Fabric API - Connectivity Test
============================================================

Enter your SPN and Fabric details below.

  Tenant ID      : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client ID      : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client Secret  : ********************************
  Workspace ID   : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

------------------------------------------------------------
CHECK 1: Token Acquisition
------------------------------------------------------------
  Token acquired (length=1615)

------------------------------------------------------------
CHECK 2: List Workspace Items
------------------------------------------------------------
  GET https://api.fabric.microsoft.com/v1/workspaces/.../items
  Found 9 item(s):
    - my_lakehouse (Lakehouse)
    - my_agent (DataAgent)
    ...

------------------------------------------------------------
CHECK 3: Get Specific Item
------------------------------------------------------------
  GET https://api.fabric.microsoft.com/v1/workspaces/.../items/...
  Item: my_lakehouse
  Type: Lakehouse
  ID:   xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

============================================================
  RESULTS
============================================================
  [PASS] Token Acquisition
  [PASS] List Workspace Items
  [PASS] Get Specific Item

  3/3 checks passed.
```

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` on token | Bad client ID or secret | Verify in Azure portal; regenerate secret if expired |
| `403 Forbidden` on items | SPN lacks workspace access | Grant SPN **Contributor** role on the Fabric workspace |
| `404 Not Found` | Wrong workspace ID | Double-check the ID from the Fabric portal URL |
