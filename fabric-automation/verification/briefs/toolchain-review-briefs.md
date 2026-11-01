# Toolchain kit review briefs (three families, cold, parallel)

Shared preamble (paste first into every brief; fill CLONE and SHA):

You are reviewing part of an open-source project: the "toolchain kit" of a Fabric Code Factory. It pins and loads agent skills and MCP servers (Fabric, Power BI, Azure) for people and for unattended jobs: a manifest, 14 job profiles, a lock file, and a Python command line (`scripts/toolchain.py` and three helper modules).

WHERE: a fresh clone of the public repository https://github.com/apkola29/fabric at commit SHA, in the folder CLONE (the project is its `fabric-automation/` folder). Work ONLY inside CLONE. To try a mutation or an experiment, copy `fabric-automation/` to a scratch folder under CLONE's parent and change the copy. Never edit CLONE's tracked files. Do not push, do not use any stored credentials, do not call any tenant or cloud API with a sign-in. Public web reads are fine (to check facts against primary sources).

Read first: fabric-automation/toolchain/README.md, fabric-automation/AGENTS.md, and the section "3.13" of docs/04-design.md. The facts the kit relies on, with their sources, are in docs/research/raw/t10-toolchain-grounding.md.

HOW TO REVIEW: be adversarial and honest. Every finding needs a reproduction (the exact command and what you observed) or a primary-source citation (URL and the sentence). A finding you could not reproduce must say UNVERIFIED. Rank by real impact, not by how clever it is. No style nits. Cap: 15 findings. For each: ID (use your slice letter, e.g. R-A-1), severity (High / Medium / Low), where (file:line), what is wrong, evidence, and a suggested fix. Then a section "Checked and fine" listing what you looked at that held up, so we know the coverage. Return the whole report inline in your final message (at most 2500 words); do not rely on writing files.

Run the tests of your slice with: `python -m unittest scripts.test_NAME` from inside the project folder (Python 3.10 or newer; a Windows or Linux machine).

Hard rules of the design that findings may be measured against (docs/04-design.md): HR-3 (the agent job holds no credentials; a credentialed or hosted MCP server may be used only by a person in `dev` mode or by the trusted executor), HR-9 (nothing is installed or updated at run time; everything is pinned), HR-12 (a changed tool contract is a stop), K4/K6/K7/K9/K10 (agent plane and executor plane separation, pinned loading).

## Slice A (GPT 6.1 Sol): the command line

Files: fabric-automation/scripts/toolchain.py and scripts/test_toolchain.py (about 2,700 lines each). Look hard at:
1. Whether the mode rules truly keep the agent plane free of credentialed, networked and writing server variants, including through `render`, `install`, the load plan and the profile selectors (a wildcard, a quarantined skill, a skill present in two plugins).
2. What the lock's `inputs_digest` covers: name a manifest or profile change that should make the lock stale and does not (or the reverse).
3. `install`: can it delete or overwrite something that the user owns (an unmanaged skill folder, a user-level MCP file, a symlink or junction), is it idempotent and atomic, what does `--force` and `--scope user` do, is the managed marker trustworthy, is there a path traversal through names in the manifest or lock.
4. Rendering for the three hosts: compare with the host formats documented in docs/research/raw/t10-toolchain-grounding.md section 6 (and the live documentation) and report any entry that a host would reject or misread. Environment variable syntax per host. An explicit `tools` array.
5. Leaks: absolute paths, user names, tokens or hosts in any output of `doctor`, `verify`, `lock`, `list`, `render --host load-plan`, or in the lock.
6. The two new checks V12 (a server named like a server that an upstream plugin bundles) and V13 (a variant that promises read-only tools must have only read-only tools in its locked contract): gaps and false results.
7. Windows and Linux behaviour: line endings, path separators, case-insensitive file systems, exit codes.
Mutation task: for each of these safeguards, change a COPY of toolchain.py and run test_toolchain; report each mutation that no test notices: the three mode rules (network, credentials, access), `unattended` required, the quarantine rule, the stale-lock check, the unresolved-package rule per mode, the install ownership check, the user-scope merge, the license-variable rule.

## Slice B (Grok 4.7): the helper modules

Files: fabric-automation/scripts/toolchain_io.py, toolchain_mcp.py, toolchain_sources.py and their tests test_toolchain_io.py, test_toolchain_mcp.py, test_toolchain_sources.py. Look hard at:
1. Running child processes: shell injection (especially the Windows .cmd shims), timeouts, killing the whole process tree on Windows and Linux, deadlocks on pipes, the environment that a launched server inherits (`capture_env`: a secret in the parent environment must not reach a server that is launched for a capture).
2. The HTTP helper: redirects, size caps, TLS, proxy handling, what `safe_detail` lets through (a URL, host, path or user name in an error text that ends up in the lock).
3. The MCP probe: both protocol eras (the legacy `initialize` handshake and the 2026-07-28 stateless revision with `server/discover` and per-request `_meta`). A hostile or buggy server: huge lines, endless pagination, duplicate tools, a reply to a request that was never made, output after close, a server that never exits. What a captured contract can contain.
4. Git handling in `resolve_git_ref`, `fetch_git`, `read_plugin`, `vendor_skills`: argument injection through a ref, tag or URL; the file: protocol; repository content that is hostile (symbolic links, submodules, path traversal in tree entries, names that collide on a case-insensitive file system, Windows reserved names, very long paths, git attributes or filters); anonymous access flags.
5. `digest_tree` and the skill digests: determinism across Windows and Linux (line endings, binary files, sort order, Unicode), and whether two different trees can give the same digest.
6. The package resolvers for npm (the npm command line, the registry, jsDelivr), PyPI and NuGet: answers that lie or are malformed, floating versions, integrity values, error classification.
Mutation task: for each of these safeguards, change a COPY and run the module's tests; report each mutation that no test notices: the environment allow-list, the tree kill on timeout, the shim metacharacter refusal, `safe_detail` (each pattern), the redirect and size limits, the duplicate-tool and over-long-line checks of the probe, the symbolic-link and submodule refusal in the digest, the commit and path validation in the git helpers, vendor staging and the digest check before copy, the quarantine in `vendor_skills`.

## Slice C (Gemini 4 Argon): data, documents, workflows and the first-run experience

Files: fabric-automation/toolchain/toolchain.json, profiles.json, toolchain.lock.json, instructions/factory-preamble.md, skills/factory-router/SKILL.md, README.md; fabric-automation/AGENTS.md, CLAUDE.md, .gitignore, .github/mcp.json, .vscode/mcp.json; and the two workflow files at .github/workflows/ in the clone's root (fabric-automation-validate.yml and fabric-automation-facts.yml). Look hard at:
1. Facts. A cold fact-check of every checkable claim about the hosts and servers in toolchain/README.md, the preamble, the router skill, the manifest's `summary`, `status`, `url` and flag fields, and the profile table: flags, URLs, package names, tool names, versions, behaviours. Use primary sources (documentation pages, the upstream READMEs, the package registries). List each claim that is wrong, overstated or unsupported.
2. GitHub Actions security of the two workflows: pinning, permissions, script injection, what the artifact can contain, behaviour on a scheduled run, what happens when an upstream package or skill is hostile.
3. Public exposure: any secret, token, internal host name, user name, tenant or subscription identifier, e-mail address or personal path in any tracked file of the project.
4. The first-run experience. Follow toolchain/README.md "Start from scratch" step by step as a newcomer on a clean machine (Windows or Linux). Run each command in the clone (`doctor`, `install` as a plan, `verify`, `list`, `render`). List every place where the text is wrong, ambiguous, or assumes something that a newcomer lacks, and every place where the real output contradicts the text. (Do not run `install --apply` in CLONE; do it in a scratch copy of the project folder.)
5. The lock file: anything suspicious (lint findings, install hints, bundled MCP names, a digest that cannot be right, an unresolved package) and whether the lock agrees with the manifest and the profiles.
6. The router skill, the preamble and AGENTS.md as agent instructions: do the named skills and servers exist in the lock; could any text steer an agent into a harmful action or be mistaken for an instruction inside untrusted content; are there contradictions between them and with the manifest's modes.
