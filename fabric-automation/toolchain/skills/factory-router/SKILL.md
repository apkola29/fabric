---
name: factory-router
description: Use first for any Fabric, Power BI or Azure task in the fabric-automation repository and for every factory job. Checks the toolchain preflight, picks the owning skill and the MCP server variant that the active profile loaded, and applies the fail-closed rules (no installs, no license acceptance on anyone's behalf, stop on contract drift). Use it before running Fabric or Azure operations, creating or changing Fabric items, answering questions over reports and semantic models, or editing Bicep.
license: MIT
metadata:
  author: fabric-automation
  version: "1.0"
---

# Factory router

This skill routes work. It does not replace the workload skills or the MCP tools, and it adds no procedure of its own.

## 1. Preflight

1. Run `python scripts/toolchain.py verify --offline` once per session. It only reads. If it fails, stop and report what it printed.
2. Find your profile. A person's session uses a `dev-*` profile (the default is `dev-factory`). A job gets its profile from the runner. `python scripts/toolchain.py list` shows the profiles, and `python scripts/toolchain.py list --profile NAME` shows what one loads.
3. Use only what the profile loaded. If a skill or server you need is not in it, say so and stop that step. Do not install anything.

## 2. Pick the owner

| The task | Owning skill | MCP server (variant by profile) |
|---|---|---|
| Questions about a report or a semantic model | `fabriciq` | `fabric-iq`: read-only consumption, dev mode only |
| Semantic model objects, DAX, TMDL | `semantic-model-authoring` | `powerbi-authoring-local`, or `powerbi-authoring-remote` if the profile chose the hosted one |
| Reports (PBIR, PBIP) | `powerbi-report-cli` | the authoring server of the profile, plus the skill's own CLI |
| Warehouse or lakehouse SQL | `sqldw-cli`, `sqldb-cli` | `fabric-sql`, dev mode only |
| Notebooks and Spark | `spark-cli` | `fabric-local` |
| Eventhouse, KQL, Eventstreams, Activator | `eventhouse-cli`, `eventstream-cli`, `activator-cli` | `fabric-rti-local` |
| Workspaces, folders, items, roles | the workload skill | `fabric-core` (dev mode) or the core tools of `fabric-local` |
| Fabric documentation, API specs, item definitions | none | `fabric-local` with the `docs` variant, then `microsoft-learn` where the profile has it |
| Long Lakehouse and OneLake engineering | `project-osmos`, given one complete outcome as one task | `fabric-local` |
| Azure resources, Bicep, deployment | `azure-prepare`, then `azure-validate`, then `azure-deploy` | `azure-mcp`, `bicep-mcp` |

If two skills could own the task, take the more specific one. If none owns it, say so and use current official documentation, not memory.

## 3. Run it

1. Live work goes through the MCP tool, with the skill's safeguards. Do not swap in a script, the Fabric CLI or REST because a tool is missing. Say what is missing, and ask before using another route.
2. A read-only request stays read-only. A tool listing or a connection test is not permission to write.
3. A skill step that asks for a confirmation means escalate when no person is there.

## 4. Things that go wrong

1. The local and the hosted Power BI authoring servers are twins. Use the one in your profile, never both.
2. The authoring server is blocked until its license agreement is accepted. Never accept it for someone. The operator does that, once, on purpose.
3. A tool that is missing, renamed or changed against the lock is a contract drift. Stop and report it.
4. The ontology skill `fabriciq-ontology-cli` is quarantined and never loaded.
5. Hosted Fabric servers act as the signed-in person. Do not use them in a job.

More: `toolchain/README.md`, and the rules in `toolchain/instructions/factory-preamble.md`.
