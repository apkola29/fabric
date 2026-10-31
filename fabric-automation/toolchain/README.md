# Toolchain: the pinned skills and MCP servers behind every job

Every session and every job of the factory starts from the same pinned set of agent skills and MCP servers for Fabric, Power BI and Azure. This folder says which ones, `scripts/toolchain.py` checks, installs, verifies and updates them, and the lock file records exactly what was reviewed. Nothing is loaded that this folder does not name, and nothing is installed at run time (hard rule HR-9).

## Start from scratch

1. **Install the basics.** You need Git 2.32 or newer, Python 3.10 or newer, Node.js 22 or newer (the Fabric, Power BI and Azure MCP servers are npm packages, and the Fabric server asks for Node.js 22), and one host: GitHub Copilot CLI, Visual Studio Code with GitHub Copilot, or Claude Code. Optional: the GitHub CLI, the Azure CLI, .NET 10 (Bicep server), `uv` (Real-Time Intelligence server) and the Fabric CLI (`fab`, from the `ms-fabric-cli` package).
2. **Clone and look.** Clone the repository, open the `fabric-automation` folder, and run `python scripts/toolchain.py doctor`. It lists what is missing and what each missing piece is for.
3. **Install.** Run `python scripts/toolchain.py install` to see the plan, then `python scripts/toolchain.py install --apply`. It fetches the pinned skills, checks their digests, and copies them where Copilot CLI and VS Code look for them, inside this folder and not in your home folder: `.github/skills` (the 56 pinned skills and the router skill of this repository, 57 in all) and `.github/common` (the shared files that many skills link to as `../../common/`). It also writes the MCP files for those hosts. Claude Code gets `.claude/skills`, `.claude/common` and `.mcp.json` only when you ask for it with `--host claude-code`, because Copilot CLI reads `.mcp.json` before `.github/mcp.json`. Run it again any time: a second run changes nothing. It never replaces a folder it did not install, and it stops on a skill that you edited after it was installed, unless you pass `--force`.
4. **Sign in.** Run `az login` for the servers that use an Azure identity. The hosted servers open a browser sign-in on first use. The Power BI authoring server asks you to accept its license: you do that once, yourself (see Cautions).
5. **Verify.** Run `python scripts/toolchain.py verify`, and `python scripts/toolchain.py verify --live` to check what is installed for each host. It exits 0 only when the manifest, the profiles, the lock and the generated host files agree.
6. **Work.** Start your host inside the `fabric-automation` folder or a folder below it (Copilot CLI reads the project's MCP files from the folder it starts in and the folders above it, up to the repository root, so starting at the repository root does not find them; VS Code reads `.vscode/mcp.json` of the folder it opens). The first time, Copilot CLI asks you to trust the folder and Claude Code asks you to approve each project server: until you do, the project servers do not appear. `AGENTS.md` and the `factory-router` skill route Fabric, Power BI and Azure tasks to the owning skill and MCP server of the profile in use (the default is `dev-factory`).

| Tool | Windows | macOS | Linux |
|---|---|---|---|
| Git | `winget install Git.Git` | `brew install git` | your package manager |
| Python 3.10+ | `winget install Python.Python.3.12` | `brew install python` | your package manager |
| Node.js 22+ | `winget install OpenJS.NodeJS.LTS` | `brew install node` | your package manager |
| Azure CLI | `winget install Microsoft.AzureCLI` | `brew install azure-cli` | the Microsoft package feed |
| GitHub Copilot CLI | `winget install GitHub.Copilot` | `brew install copilot-cli` | `npm install -g @github/copilot` |

## What gets loaded

A **mode** says who is working and what that may use. A **profile** is the exact list of skills and MCP server variants for one kind of session or job. A **variant** is one way of launching a server (its switches), with four declared facts: its credentials, its network, its access and whether it can run unattended.

| Mode | Who | May use | Used by |
|---|---|---|---|
| `dev` | A person, signed in as themselves | Anything, including the hosted servers and writes | Interactive sessions on a sandbox workspace |
| `agent` | The untrusted agent plane (design K4) | Only variants with no credentials, no network and read-only access | The planner, test author, implementer and verifiers (design 3.4) |
| `executor` | The trusted plane (K6, K7, K10) | Read-only variants that a workload identity can use, with no person involved | The static gates and the sandbox read-back (design 3.9, 3.10) |

`verify` refuses a profile that breaks the rules of its mode, so the credential-free agent plane cannot be handed a server that needs a sign-in. Every write in the agent and executor planes is a typed executor operation, not an MCP call.

| Profile | Mode | Loads |
|---|---|---|
| `agent-intake`, `agent-verifier` | agent | Nothing, on purpose |
| `agent-planner`, `agent-test-author` | agent | The semantic model and report skills, and the offline Fabric documentation |
| `agent-implementer` | agent | The same, plus the Power BI authoring server in read-only mode on local files |
| `executor-static-gates` | executor | The read-only authoring server on local files and the offline documentation |
| `executor-sandbox-read` | executor | The Fabric server (read-only tools) and the authoring server as a service principal |
| `dev-docs` | dev | Offline Fabric documentation and Microsoft Learn |
| `dev-fabric` | dev | All Fabric and Power BI skills and the Fabric servers |
| `dev-powerbi`, `dev-powerbi-hosted` | dev | Power BI authoring with the local or the hosted server, and Fabric IQ |
| `dev-realtime` | dev | Eventhouse, Eventstreams, Activator |
| `dev-azure` | dev | The Azure skills, the Azure and Bicep servers |
| `dev-factory` | dev | Everything needed to build and review the factory. The project MCP files are rendered from it |

`python scripts/toolchain.py list` shows the same table from the data, and `list --profile NAME` shows one profile with the version, access and credentials of every server.

## How it is pinned

| File | What it is | Edited by |
|---|---|---|
| `toolchain/toolchain.json` | The manifest: the modes, the hosts, the tools to check for, the two skill sources, the quarantine list and the MCP servers with their variants | A person |
| `toolchain/profiles.json` | The profiles | A person |
| `toolchain/toolchain.lock.json` | The lock: for each skill source the commit, for every skill a content digest, for each shared folder its digest; for each package the exact version and its integrity hash; for each launchable server variant its tool list with a digest of every tool schema | `python scripts/toolchain.py lock` or `update --write`, reviewed in a pull request |
| `toolchain/instructions/factory-preamble.md` | The rules that every session and job loads | A person |
| `toolchain/skills/factory-router/` | The one skill this repository owns: it routes work to the owning skill and server | A person |
| `.github/mcp.json`, `.vscode/mcp.json` | The MCP files for Copilot CLI and VS Code, rendered from the default profile | `render --write-project` |
| `.github/skills`, `.github/common`, `.claude/skills`, `.claude/common`, `.mcp.json`, `.factory/` | What `install` and `fetch` generate for a machine: the skills, the shared folder, the Claude Code file and the local pack. Git ignores them and they are never published | `install`, `fetch` |

The lock has no `latest` and no range. A skill is identified by the commit of its upstream repository and by a digest of its files (line endings normalised, so the digest is the same on Windows and Linux), which `install` checks before it copies anything. The two skill sources are Microsoft's own: `microsoft/skills-for-fabric` and `microsoft/azure-skills`. The kit takes their skills only, and one more thing: 24 of the 26 Fabric skills tell the agent to read files in the plugin's `common` folder (`../../common/COMMON-CLI.md` and others, 627 references), which sits outside every skill folder, so the manifest names that folder as shared, the lock records its digest and `install` puts it beside the skills. Their plugins also bundle MCP servers, but at unpinned versions and with names that collide, so the manifest defines its own servers instead. A skill on the quarantine list (today `fabriciq-ontology-cli`, which authors a retiring format) is never loaded, even when a profile selects every skill of a plugin.

An MCP server that the kit can launch is captured once: the lock records its tool names and a digest of every tool schema. `verify --contracts` launches the server again and fails when a tool is added, removed or changed, which is how a job notices that an upstream server changed under it (HR-12). Hosted servers cannot be captured without a sign-in, so they are not pinned this way, and they are for people only.

## What `verify` checks

`python scripts/toolchain.py verify` prints one line per finding, tagged with the check that raised it. It exits 1 on any `FAIL` (and with `--strict` on a `WARN`).

| Check | What it holds to account |
|---|---|
| V1 | `toolchain.json` and `profiles.json` follow the schema: no unknown key, no bad value, every variant states its four facts |
| V2 | Each profile obeys the rules of its mode and names only skills and servers that exist, and no quarantined skill by name |
| V3 | The lock exists, is fresh (its inputs digest, which covers the launches and the policy, matches the manifest), agrees with the manifest on the repository, path and tag of each source, and covers every source, plugin, shared folder, package and contract that a profile uses. An unresolved package is a warning in `dev` and a failure in `agent` and `executor` |
| V4 | Every server that a profile uses has an exact launch line, never `latest` |
| V5 | `.github/mcp.json` and `.vscode/mcp.json` equal the rendering of the default profile |
| V6 | Every instructions file that a profile names exists |
| V7 | The quarantine list still names skills that exist (a warning when it does not) |
| V8 | Skill lint findings (a failure in `agent` mode, and for the skills of this repository in every mode) and install steps that are inert in `agent` mode (a warning). The lint reads every text file of a skill |
| V9 | With `--live`: the skills, the shared folder and the MCP files installed for each host match the lock and the profile (the marker's profile, every needed skill present and unmodified, nothing left over), and no `.mcp.json` hides the rendering from Copilot CLI |
| V10 | A server of an `agent` or `executor` profile whose contract is skipped or unavailable is a warning, and the load plan of that profile is refused. With `--contracts`: every captured server is launched again and its tools must equal the lock |
| V11 | A captured contract lists at least one tool |
| V12 | No server of a profile has the name of a server that a locked upstream plugin bundles. A host lets the plugin's server replace a project server of the same name, so the pinned server would be swapped for an unpinned one (seen with Copilot CLI 1.0.102) |
| V13 | A variant marked `tools_read_only` has only tools annotated read-only in its locked contract. Today that is the Fabric server's `docs` and `read` variants |

## How a job uses it

The runner picks a profile for the job and asks for its **load plan**: `python scripts/toolchain.py render --profile agent-implementer --host load-plan`. The plan lists each skill with its commit and digest, the skills of this repository (the router) and the shared folder with theirs, each server with its exact launch command and tool contract, and the instruction files with their digests. The loader (K9) fetches the pinned pack into an image or a work folder with `fetch`, checks the digests, and starts the agent with exactly that. Two rules make the plan safe to hand to a job. A plan for an `agent` or `executor` profile is refused unless every server it launches has a captured contract, because a contract that was never captured cannot be checked for drift. And its `npx` and `uvx` launches carry `--offline` and say `provisioning: preinstalled`: the loader has to install the exact version and integrity that the lock names into its image first, because `npx` and `uvx` check a download against the registry's own hash and not against the one in the lock. `verify` runs before the job and a failure is a stop. The same plan feeds the other hosts: `render --host copilot-cli|vscode|claude-code` prints their MCP files. `install` is for people: it refuses `--scope user` for an `agent` or `executor` profile, because a user-level file is shared by everything that user runs.

## Keeping it current

- A weekly job (the `toolchain` job of the fact-check workflow) runs `update --check`, resolves a candidate lock on a GitHub-hosted runner, and keeps it as an artifact. It changes nothing in the repository.
- `python scripts/toolchain.py update` prints the gap analysis: new, removed, renamed and changed skills, new package versions, changed tool contracts, and which profile would stop verifying because of it. A renamed skill is the typical case: release v0.3.20 renamed one.
- `python scripts/toolchain.py update --write` writes the new lock only when every profile still verifies. Review it as a pull request, run `fetch` and `install`, and merge. To roll back, revert the lock.
- A lock refresh belongs on a hosted runner. On a network that blocks the npm or NuGet registry, a local `lock` leaves those packages `unresolved` and says so.

## Add a skill source, a server or a profile

1. Edit `toolchain/toolchain.json` or `toolchain/profiles.json`. Give a new variant its four facts honestly: a variant that needs a sign-in has credentials other than `none`, and a variant that can write has access `read-write`. If the variant's read-only switch removes the writing tools from the server's list, add `"tools_read_only": true` and the lock has to show it (V13). Choose a server id that no upstream plugin uses (V12).
2. Run `python scripts/toolchain.py lock`, then `python scripts/toolchain.py verify`.
3. If the default profile changed, run `python scripts/toolchain.py render --write-project`.
4. Run the tests: `python -m unittest discover -s scripts -p "test_*.py"`.

## Cautions

- **License acceptance.** The Power BI authoring server blocks every tool until its license is accepted. The kit never accepts it. In an interactive session you tell the agent to accept it, once. For unattended use the operator sets the environment variable named in the manifest after reading the license. The rendered files pass that variable through with the default `false`.
- **Hosted servers act as you.** The hosted Fabric, Fabric IQ, SQL endpoint and Power BI authoring servers use your browser sign-in; the sign-in method of the hosted Azure cost server is not documented, and the kit treats it the same way. Fabric IQ does not support service principals. Use them on a sandbox workspace and only in the `dev` mode.
- **The rules here are stricter than some pinned skills.** A few upstream skills tell the agent to install a tool (`winget install`, `pip install`, `npm install -g`) or to fall back to another route when their MCP tool is missing, without asking. The preamble overrides that: nothing is installed by an agent, and a missing tool is reported and asked about first. `doctor` and `install` are how a person installs what the skills expect.
- **Two copies of the same thing.** Your own configuration may already define Fabric or Power BI servers (the user file `$HOME/.copilot/mcp-config.json`, a VS Code profile), or you may have installed the upstream plugins, whose bundles register their own skills and unpinned servers. A session then sees two sets. The kit does not touch your files. See what is active with `copilot mcp list` and `copilot plugin list`, and switch the extra ones off for this project with `copilot mcp disable NAME` or `copilot plugin disable NAME`. A factory job is meant to start from the pack that `fetch` writes and from nothing else (K9), so this concerns people's sessions.
- **Unattended identity is not proven.** Whether each server accepts a service principal or a workload identity is a Phase 0 spike (S2, S6). The manifest marks what the documentation says, and `verify` only lets a variant into the executor plane when it says `true`.
- **No secrets, no tenant data.** The files in this folder are public. They hold server addresses, package names and digests, never a token, a tenant, a workspace or an item identifier.
- **Contract drift is a stop.** A missing, renamed or changed tool is reported, not worked around.

## Limits

- Nothing here has been run against a tenant. The pinned servers and skills are real and were read and launched, but no job has used them against Fabric.
- The lock records a tool contract only for a server that was launched. Five of the 15 are captured, on a hosted runner because `npx` cannot fetch a package on the machine where the kit was built: the three variants of the Fabric server at the pinned 1.6.0 (6, 34 and 62 tools), the read variant of the Azure server (70 tools) and the Real-Time Intelligence server (39 tools). The Bicep server could not be launched there (`dnx` is not on the runner's path), but its package resolved with an integrity hash, the Power BI authoring variants are skipped because their license is accepted by a person, and hosted servers are never captured because they need a sign-in. So the load plan of `agent-implementer`, `executor-static-gates` and `executor-sandbox-read`, which use the Power BI authoring server, is refused until an operator who accepted the license captures it. The weekly job of the fact-check workflow reads registry and tag metadata and re-checks the pinned contracts; it never launches a server version that nobody has reviewed. A person who wants a new capture dispatches that workflow with its `capture` input, reviews the candidate lock that it keeps as an artifact, and commits it.
- The tool annotations in a contract are the server's own claim. V13 holds a variant to them, but it cannot prove that a switch blocks a write. The Fabric server's read-only switch removes the writing tools from its list (all 34 tools that remain are annotated read-only), so its `docs` and `read` variants carry `tools_read_only`. The Azure server's list under `--read-only` has 70 tools of which only 5 are annotated read-only, because it groups commands under one tool per service and blocks the writes inside; the Power BI authoring server's `--readonly` also works inside the server. Those variants make no `tools_read_only` promise, and their read-only access rests on the documented switch.
- The Power BI authoring server blocks every tool until its license is accepted, and the kit never accepts it. Its contract stays `skipped` until an operator who accepted it runs the capture.
- Copilot CLI (version 1.0.102) was run against the generated files: it listed all 8 project servers of `dev-factory` and the 57 project skills, and a project skill won over a plugin skill of the same name. Claude Code (version 2.1.162) was run only as far as listing the two servers of a generated `.mcp.json`, which it showed as pending approval; no server was started. VS Code was not run, and receives files in its documented format. The first run on Linux is the hosted runner's.
- The MCP probe asks `server/discover` first, as the 2026-07-28 revision describes, and falls back to the older `initialize` handshake on a new process. On the hosted runner the Fabric server (1.6.0) and the Azure server (4.0.0-beta.4) answered `server/discover`, so their four contracts record the era `modern` (with the same tools that the older handshake gave); the real local Fabric server (1.5.0) answers both eras on a developer machine, and the Real-Time Intelligence server answers only the older handshake. A server that answers only the new era was never available, so that path is tested against a stand-in.
- Five links in the pinned skills point at folders that do not exist at the pinned tag (`mcp-setup` four times and `spark-authoring-cli` once). They are broken upstream and the kit does not rewrite upstream files.
- The SQL endpoint server's one tool is called `execute_query` by the skill and the plugin and `executeSQL` by Microsoft Learn. Which is current needs a signed-in session, so it is not settled here; the router tells the agent to use the name that the loaded server lists.
- `gh-aw` and the Copilot cloud agent have no renderer yet. The load plan is the interface for them. gh-aw resolves `skills:` entries to commits itself, so a renderer is a thin step.
- Only two skill sources are in scope. The bundled custom agents of the Fabric plugin (FabricAdmin and others) are not loaded.

The facts behind this folder, with their sources and the date they were read, are in `../docs/research/raw/t10-toolchain-grounding.md`. The design is in `../docs/04-design.md` (3.13, HR-9).
