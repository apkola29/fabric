"""
Fabric Data Agent - Interactive CLI Client

Query any published Microsoft Fabric Data Agent using Service Principal (SPN)
authentication. No user credentials are passed through -- only the SPN's
client_credentials are used.

Prerequisites:
    pip install openai requests

    The Data Agent must be published in the Fabric portal before it can be
    queried via this script.

    The SPN must have Contributor access to the workspace and, if the agent
    uses a Semantic Model data source, Build permission on that model.

Authentication:
    POST https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token
    OAuth2 client_credentials grant, scoped to:
        https://api.fabric.microsoft.com/.default

API:
    Base URL (constructed from workspace + agent IDs):
        https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}
            /dataagents/{agentId}/aiassistant/openai

    This endpoint is OpenAI Assistants-compatible. The OpenAI SDK calls:
        POST   /assistants              - register assistant handle
        POST   /threads                 - create conversation session
        POST   /threads/{id}/messages   - post user question
        POST   /threads/{id}/runs       - trigger agent processing
        GET    /threads/{id}/runs/{id}  - poll run status
        GET    /threads/{id}/messages   - retrieve agent response
        DELETE /threads/{id}            - clean up session

    All requests carry:
        Authorization: Bearer {spn_token}
        ?api-version=2024-05-01-preview

Usage:
    python fabric_agent.py
"""

import typing as t
import time
import uuid
import requests

from openai import OpenAI
from openai._models import FinalRequestOptions
from openai._types import Omit
from openai._utils import is_given


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def get_config() -> dict:
    """Prompt for SPN credentials and Fabric IDs. All fields are required."""
    print("=" * 60)
    print("  Fabric Data Agent - Interactive Client")
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


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# OpenAI client with Fabric SPN auth
# ---------------------------------------------------------------------------

class FabricOpenAI(OpenAI):
    """OpenAI client that replaces API-key auth with a Fabric SPN Bearer token."""

    def __init__(self, access_token: str, base_url: str, **kwargs: t.Any) -> None:
        self._access_token = access_token
        default_query = kwargs.pop("default_query", {})
        default_query["api-version"] = "2024-05-01-preview"
        super().__init__(
            api_key="not-used",
            base_url=base_url,
            default_query=default_query,
            **kwargs,
        )

    def _prepare_options(self, options: FinalRequestOptions) -> None:
        headers: dict[str, str | Omit] = (
            {**options.headers} if is_given(options.headers) else {}
        )
        options.headers = headers
        headers["Authorization"] = f"Bearer {self._access_token}"
        if "Accept" not in headers:
            headers["Accept"] = "application/json"
        if "ActivityId" not in headers:
            headers["ActivityId"] = str(uuid.uuid4())
        return super()._prepare_options(options)


# ---------------------------------------------------------------------------
# Agent interaction
# ---------------------------------------------------------------------------

def ask_agent(client: FabricOpenAI, question: str) -> str:
    """Send a question to the Data Agent and return the response text."""
    assistant = client.beta.assistants.create(model="not used")
    thread = client.beta.threads.create()

    try:
        client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=question,
        )
        run = client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=assistant.id,
        )

        # Poll until the run reaches a terminal state
        terminal = {"completed", "failed", "cancelled", "requires_action"}
        start = time.time()
        while run.status not in terminal:
            if time.time() - start > 300:
                print()
                return "[ERROR] Timed out waiting for agent response."
            print(".", end="", flush=True)
            time.sleep(2)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id,
            )
        print(" ", end="", flush=True)

        if run.status != "completed":
            return f"[ERROR] Run finished with status: {run.status}"

        # Extract the assistant's reply
        messages = client.beta.threads.messages.list(
            thread_id=thread.id, order="asc",
        )
        for m in messages:
            if m.role == "assistant" and m.content:
                parts = [b.text.value for b in m.content if hasattr(b, "text")]
                if parts:
                    return "\n".join(parts)

        return "[No response from agent]"

    finally:
        try:
            client.beta.threads.delete(thread_id=thread.id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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

    base_url = (
        f"https://api.fabric.microsoft.com/v1/workspaces/"
        f"{config['workspace_id']}/dataagents/{config['agent_id']}/aiassistant/openai"
    )
    client = FabricOpenAI(access_token=token, base_url=base_url)

    print()
    print("Connected to Data Agent. Type your questions below.")
    print("Type 'quit' or 'exit' to stop.")
    print("-" * 60)

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
            answer = ask_agent(client, question)
            print(answer)
        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
