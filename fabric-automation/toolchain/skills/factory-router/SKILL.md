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

1. In a person's session, run `python scripts/toolchain.py verify --live` once (add `--host claude-code` for Claude Code). It only reads. If it fails, stop and report what it printed. A job does not run it: the runner has, and the agent plane has no copy of the script.
2. Find your profile. A person's session uses a `dev-*` profile (the default is `dev-factory`); `python scripts/toolchain.py list` shows the profiles, and `python scripts/toolchain.py list --profile NAME` shows what one loads. A job gets its profile from the runner and does not run these commands.
3. Use only what the profile loaded. If a skill or server you need is not in it, say so and stop that step. Do not install anything. In a person's session there is one exception: a server that the person connected in their own settings and asked you to use (`AGENTS.md`, "Servers").
4. Before you rely on a server, call one read-only tool of it and note which servers answered. Sign-in belongs to the person or the runner (the preamble says how each kind of server signs in), never to you.
5. Look for newer skills and servers once per session, as the preamble's "Freshness" says: `python scripts/toolchain.py update --check --fail-on-update --summary-file .factory/update-summary.md`. Report what it finds, including a package that it could not check, and keep working on the pinned versions. A job's runner has already done this: use its result, and if there is none say that freshness is unknown.

## 2. Pick the owner

The skills name MCP servers as their plugins register them. The kit registers its own servers under other ids (so that an installed plugin cannot replace a pinned server), so read the last column as a translation, not as a rename. A host shows a tool as the server id and the tool name joined in its own way; match on both parts.

| The task | Owning skill | How the skill works | Kit server (the skill's name for it) |
|---|---|---|---|
| Questions about a report or a semantic model | `fabriciq` | MCP tools of Fabric IQ | `fabric-iq` (`FabricIQ`): read-only, dev mode only |
| Semantic model objects, DAX, TMDL | `semantic-model-authoring` | MCP tools of the authoring server first; TMDL files, and `az rest` to deploy | `powerbi-authoring-local` (`powerbi-modeling-mcp`), or `powerbi-authoring-remote` if the profile chose the hosted one |
| Reports (PBIR, PBIP) | `powerbi-report-cli` | the `powerbi-report-author` CLI, `az rest` to publish, and the authoring server only for the model | the authoring server of the profile |
| Warehouse, lakehouse SQL endpoint and mirrored database queries and DDL | `sqldw-cli` | all T-SQL through one MCP tool, `az rest` only to find the workspace and item, `sqlcmd` only as the skill's own fallback | `fabric-sql` (`fabric-sqlendpoint`), dev mode only. The skill and the plugin call the tool `execute_query`, and Microsoft Learn lists `executeSQL` for the server. The kit has not seen the live list, because that needs a sign-in. Use the name the loaded server lists, and tell the person when it differs from the skill's |
| A Fabric SQL database (OLTP) | `sqldb-cli` | CLI and REST (`sqlcmd`, `az rest`), no MCP | none: `fabric-sql` serves warehouses and SQL endpoints, not this item type |
| Notebooks, Spark, one Lakehouse or OneLake outcome | `spark-cli`, `project-osmos` (one complete outcome as one task) | CLI and REST (`az rest`, helper scripts), no MCP | `fabric-local` with the `docs` variant for API references only |
| Eventhouse, Eventstreams, Activator | `eventhouse-cli`, `eventstream-cli`, `activator-cli` | CLI and REST (`az rest`). `eventhouse-cli` and `activator-cli` also name MCP servers that the kit does not load (a Fabric KQL server, and the per-item Activator server): never add them to a file; in a session call one only if the person connected it in their own settings and asked (AGENTS.md, "Servers"), and never in a job | none; `fabric-rti-local` (only in `dev-realtime`) is a separate toolset for ad-hoc KQL and Eventstream work when the person asks |
| Dataflows Gen2, event schema sets, Azure Monitor data in an Eventhouse | `dataflows-cli`, `eventschemaset-cli`, `azmon-mirroredcatalogs-operations-cli` | CLI and REST | none |
| Git integration, deployment pipelines, variable libraries, catalog and search, migrations | `git-integration-operations-cli`, `deployment-pipelines-authoring-cli`, `variable-library-cli`, `onelake-catalog-cli`, `search-consumption-cli`, the `*-migration` skills | CLI and REST (`synapse-migration` also calls the SQL endpoint tool for warehouse SQL) | none |
| Workspaces, folders, items, roles | the workload skill | REST in the skill | `fabric-core` (dev mode) or the core tools of `fabric-local` |
| Fabric documentation, API specs, item definitions | none | read documentation | `fabric-local` with the `docs` variant, then `microsoft-learn` where the profile has it |
| Azure resources, Bicep, deployment | `azure-prepare` (azd projects), `azure-validate`, `azure-deploy` and the other `azure-*` skills | MCP tools of the Azure and Bicep servers, and the azd, `az` and Terraform CLIs | `azure-mcp` (`azure`) and `bicep-mcp` (`bicep`), the second only in `dev-azure` |
| Azure costs | `cost-analysis`, `cost-estimation`, `cost-optimization`, `cost-governance` | MCP tools such as `query_costs`, with `az rest` and Azure CLI fallbacks inside the skill | `azure-arm-cost` (`azure-resource-manager-mcp`), dev mode only. Treat it as the whole Azure Resource Manager server, which can also deploy and change resources |
| Architecture, reliability, security, cost, operations, performance, lifecycle or governance questions, and the review of a plan or a change | `factory-standards` | the checks of its pack, each with its source and date; then the newer page from the Learn server where it answers | `microsoft-learn`; `azure-mcp` for the Azure services around Fabric (its Well-Architected service guides cover 31 Azure services and not Fabric itself, checked on 2026-11-01) |

The table names the usual owners, not every pinned skill: `python scripts/toolchain.py list --profile NAME` lists them all, and each skill's description says what it is for. If two skills could own the task, take the more specific one. If none owns it, say so and use current official documentation, not memory.

## 3. Run it

1. Follow the skill's surface. Where it calls an MCP tool, use the tool of the server your profile loaded. Where the skill's own procedure is a CLI or REST workflow, run it as written in the dev mode. Before anything that changes a tenant, say the route (the tool or the command), the identity that it will use and the change, and wait for the person to approve that statement: the task itself is not that approval. In the agent and executor modes no live CLI or REST step runs: the agent plane has no credentials and no network, and the executor plane acts only through the read-only tools of its profile and its own typed operations. Say that the step needs a dev-mode session or an executor operation, and stop it.
2. Some pinned skills tell you to fall back to another route when their MCP tool is missing, or to install a tool (`winget install`, `pip install`, `npm install -g`, an `npx` package). The rules here are stricter on purpose. If a tool is missing, say what is missing and ask the person before another route. Never install anything: in a person's session `python scripts/toolchain.py doctor` lists what the machine lacks and what each piece is for, and the person installs it; a job says what is missing and ends that step.
3. A read-only request stays read-only. A tool listing or a connection test is not permission to write.
4. A skill step that asks for a confirmation means escalate when no person is there.

## 4. If a server does not answer

A server that does not answer is reported and not worked around.

1. Say which server, what you called and what came back.
2. Carry on with what needs no sign-in: the `docs` variant of `fabric-local`, `microsoft-learn`, `bicep-mcp`, the `offline-readonly` variant of the authoring server, the pinned skills, the files of the repository and the standards. The documentation and Well-Architected tools of `azure-mcp` read public pages and may answer without a sign-in; try one call.
3. Stop only the step that needed the missing server: a live read of the tenant, a change, a query. Do not do it through another route. Rule 2 of the preamble ("How to work") says when a skill's own CLI or REST step is allowed. In a job, the step ends blocked, with the reason.
4. Say in your report which parts of the answer rest on the repository and the standards alone, and which on live state.

## 5. Things that go wrong

1. The local and the hosted Power BI authoring servers are twins. Use the one in your profile, never both.
2. The local authoring server (the npm package) is blocked until its license agreement is accepted. Never accept it for someone. The operator does that, once, on purpose.
3. A tool that is missing, renamed or changed against the lock is a contract drift. Stop and report it. The lock holds the tool lists of the stdio servers only, so a hosted server has no recorded list to drift from: compare its tools with what the skill expects, and tell the person about a difference.
4. The ontology skill `fabriciq-ontology-cli` is quarantined and never loaded.
5. Hosted Fabric servers act as the signed-in person. Do not use them in a job.

More: `toolchain/README.md`, and the rules in `toolchain/instructions/factory-preamble.md`.
