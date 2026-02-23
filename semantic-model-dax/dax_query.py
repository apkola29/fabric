"""
Fabric Semantic Model - DAX Query Client

List semantic models (datasets) in a Fabric / Power BI workspace and
run DAX queries against them using the Power BI REST API.

Supports two authentication methods:
    1. Service Principal (SPN) - client_credentials grant (headless/CI)
    2. Interactive Browser     - user login with MFA via azure-identity

Authentication:
    SPN:
        POST https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token
        scope = https://analysis.windows.net/powerbi/api/.default

    Interactive:
        azure.identity.InteractiveBrowserCredential
        scope = https://analysis.windows.net/powerbi/api/.default

API Endpoints:
    List datasets:
        GET https://api.powerbi.com/v1.0/myorg/groups/{workspaceId}/datasets

    Execute DAX query:
        POST https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/executeQueries
        Body: { "queries": [{ "query": "<DAX>" }] }

    Docs:
        https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/execute-queries
        https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/get-datasets-in-group

Usage:
    python dax_query.py
"""

import json
import requests


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def auth_spn() -> str:
    """Authenticate with Service Principal (client_credentials)."""
    tenant_id    = input("  Tenant ID      : ").strip()
    client_id    = input("  Client ID      : ").strip()
    client_secret = input("  Client Secret  : ").strip()

    if not all([tenant_id, client_id, client_secret]):
        print("\n  [ERROR] All SPN fields are required.")
        raise SystemExit(1)

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://analysis.windows.net/powerbi/api/.default",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def auth_interactive() -> str:
    """Authenticate interactively via browser (supports MFA)."""
    try:
        from azure.identity import InteractiveBrowserCredential
    except ImportError:
        print("  [ERROR] azure-identity not installed.")
        print("  Run: pip install azure-identity")
        raise SystemExit(1)

    credential = InteractiveBrowserCredential()
    token = credential.get_token("https://analysis.windows.net/powerbi/api/.default")
    return token.token


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def list_datasets(token: str, workspace_id: str) -> list:
    """List all semantic models (datasets) in a workspace."""
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
    resp = requests.get(url, headers={
        "Authorization": f"Bearer {token}",
    })
    resp.raise_for_status()
    return resp.json().get("value", [])


def execute_dax(token: str, dataset_id: str, dax: str) -> dict:
    """Execute a DAX query against a dataset and return the result."""
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"
    resp = requests.post(url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"queries": [{"query": dax}]},
    )
    resp.raise_for_status()
    return resp.json()


def print_dax_result(result: dict):
    """Pretty-print a DAX query result."""
    tables = result.get("results", [])
    for i, table in enumerate(tables):
        rows = table.get("tables", [{}])[0].get("rows", [])
        if not rows:
            print("  (no rows returned)")
            continue
        # Print column headers
        columns = list(rows[0].keys())
        print(f"  Columns: {', '.join(columns)}")
        print(f"  Rows: {len(rows)}")
        print()
        # Print first 20 rows
        for j, row in enumerate(rows[:20]):
            vals = [str(row.get(c, "")) for c in columns]
            print(f"    {' | '.join(vals)}")
        if len(rows) > 20:
            print(f"    ... ({len(rows) - 20} more rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Fabric Semantic Model - DAX Query Client")
    print("=" * 60)
    print()

    # Choose auth method
    print("Authentication method:")
    print("  1. Service Principal (SPN)")
    print("  2. Interactive Browser (MFA)")
    print()
    choice = input("  Select [1/2]: ").strip()

    print()
    if choice == "2":
        print("Opening browser for login...")
        token = auth_interactive()
    else:
        token = auth_spn()
    print("Authenticated.")

    # Get workspace ID
    print()
    workspace_id = input("  Workspace ID   : ").strip()
    if not workspace_id:
        print("\n  [ERROR] Workspace ID is required.")
        raise SystemExit(1)

    # List datasets
    print()
    print("-" * 60)
    print("Semantic Models in Workspace")
    print("-" * 60)
    datasets = list_datasets(token, workspace_id)

    if not datasets:
        print("  No semantic models found in this workspace.")
        return

    for i, ds in enumerate(datasets):
        print(f"  {i + 1}. {ds['name']}  (ID: {ds['id']})")

    # Select dataset
    print()
    if len(datasets) == 1:
        selected = datasets[0]
        print(f"  Using: {selected['name']}")
    else:
        idx = input(f"  Select model [1-{len(datasets)}]: ").strip()
        try:
            selected = datasets[int(idx) - 1]
        except (ValueError, IndexError):
            print("  [ERROR] Invalid selection.")
            return

    # Interactive DAX loop
    print()
    print("-" * 60)
    print(f"  Dataset: {selected['name']}")
    print("  Enter DAX queries below. Type 'quit' to stop.")
    print("  Example: EVALUATE TOPN(10, 'TableName')")
    print("-" * 60)

    while True:
        print()
        try:
            dax = input("DAX> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not dax:
            continue
        if dax.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        try:
            result = execute_dax(token, selected["id"], dax)
            print()
            print_dax_result(result)
        except requests.HTTPError as e:
            try:
                err = e.response.json()
                code = err.get("error", {}).get("code", "")
                if code == "PowerBINotAuthorizedException":
                    print("  [ERROR] Not authorized. The SPN/user needs Build")
                    print("  permission on this semantic model to run DAX queries.")
                    print("  Grant it via: Fabric portal > Semantic Model > Manage permissions")
                else:
                    print(f"  [ERROR] {code}: {json.dumps(err, indent=2)[:500]}")
            except Exception:
                print(f"  [ERROR] {e}")
        except Exception as e:
            print(f"  [ERROR] {e}")


if __name__ == "__main__":
    main()
