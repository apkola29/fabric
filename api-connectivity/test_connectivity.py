"""
Fabric API Connectivity Test

Verifies Service Principal (SPN) authentication and basic API access
to a Microsoft Fabric workspace. Runs three checks:

  1. Token acquisition  - OAuth2 client_credentials grant
  2. List workspace items - GET /v1/workspaces/{workspaceId}/items
  3. Get specific item   - GET /v1/workspaces/{workspaceId}/items/{itemId}
                           (optional, only if an item ID is provided)

Authentication:
    POST https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token
    scope = https://api.fabric.microsoft.com/.default

Usage:
    python test_connectivity.py
"""

import sys
import json
import requests


def get_config() -> dict:
    """Prompt for SPN credentials and Fabric workspace ID."""
    print("=" * 60)
    print("  Fabric API - Connectivity Test")
    print("=" * 60)
    print()
    print("Enter your SPN and Fabric details below.")
    print()

    tenant_id    = input("  Tenant ID      : ").strip()
    client_id    = input("  Client ID      : ").strip()
    client_secret = input("  Client Secret  : ").strip()
    workspace_id = input("  Workspace ID   : ").strip()

    if not all([tenant_id, client_id, client_secret, workspace_id]):
        print("\n  [ERROR] All fields are required.")
        raise SystemExit(1)

    return {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "workspace_id": workspace_id,
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


def api_get(token: str, url: str) -> dict:
    """Make an authenticated GET request to the Fabric REST API."""
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json()


def main():
    config = get_config()
    base = "https://api.fabric.microsoft.com/v1"
    results = {"token": False, "list_items": False, "get_item": False}

    # --- Check 1: Token acquisition ---
    print()
    print("-" * 60)
    print("CHECK 1: Token Acquisition")
    print("-" * 60)
    try:
        token = get_token(config)
        print(f"  Token acquired (length={len(token)})")
        results["token"] = True
    except Exception as e:
        print(f"  FAILED: {e}")
        print("\n  Cannot continue without a token.")
        print_summary(results)
        return

    # --- Check 2: List workspace items ---
    print()
    print("-" * 60)
    print("CHECK 2: List Workspace Items")
    print("-" * 60)
    items_url = f"{base}/workspaces/{config['workspace_id']}/items"
    print(f"  GET {items_url}")
    try:
        data = api_get(token, items_url)
        items = data.get("value", [])
        print(f"  Found {len(items)} item(s):")
        for item in items:
            print(f"    - {item.get('displayName', '?')} ({item.get('type', '?')})")
        results["list_items"] = True

        # --- Check 3: Get first item by ID ---
        if items:
            print()
            print("-" * 60)
            print("CHECK 3: Get Specific Item")
            print("-" * 60)
            first = items[0]
            item_url = f"{base}/workspaces/{config['workspace_id']}/items/{first['id']}"
            print(f"  GET {item_url}")
            try:
                detail = api_get(token, item_url)
                print(f"  Item: {detail.get('displayName', '?')}")
                print(f"  Type: {detail.get('type', '?')}")
                print(f"  ID:   {detail.get('id', '?')}")
                results["get_item"] = True
            except Exception as e:
                print(f"  FAILED: {e}")
        else:
            print("  No items found -- skipping Check 3.")
            results["get_item"] = None  # skipped

    except Exception as e:
        print(f"  FAILED: {e}")

    print_summary(results)


def print_summary(results: dict):
    """Print a pass/fail summary."""
    print()
    print("=" * 60)
    print("  RESULTS")
    print("=" * 60)

    labels = {
        "token": "Token Acquisition",
        "list_items": "List Workspace Items",
        "get_item": "Get Specific Item",
    }
    for key, label in labels.items():
        status = results.get(key)
        if status is True:
            mark = "PASS"
        elif status is None:
            mark = "SKIP"
        else:
            mark = "FAIL"
        print(f"  [{mark}] {label}")

    passed = sum(1 for v in results.values() if v is True)
    total = sum(1 for v in results.values() if v is not None)
    print()
    print(f"  {passed}/{total} checks passed.")
    print()


if __name__ == "__main__":
    main()
