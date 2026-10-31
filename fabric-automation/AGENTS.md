# Working in this folder

This folder holds the design of a Fabric code factory and the toolchain that its agents and jobs load: pinned agent skills and MCP servers for Fabric, Power BI and Azure. Read `README.md` first.

## Before any Fabric, Power BI or Azure task

1. Run `python scripts/toolchain.py verify` once per session. It only reads. If it fails, stop and report what it printed.
2. Use the `factory-router` skill. It picks the owning skill and the MCP server from the profile in use.
3. Use only the skills and MCP servers that the profile loaded. `python scripts/toolchain.py list` shows the profiles. Do not install anything.

## Rules

1. This repository is public. Never write a tenant, workspace, item or capacity identifier, a person's name, a token or a local path into a file.
2. Live work follows the owning skill: an MCP tool where the skill names one, the skill's own CLI or REST steps where it prescribes them (dev mode only, and a person approves anything that changes a tenant). Do not swap one for the other. If a tool is missing, say so and ask before using another route.
3. Never accept a license agreement on anyone's behalf. The Power BI authoring server asks for one, and the operator accepts it once, on purpose.
4. A tool that is missing, renamed or changed against the lock is a contract drift. Stop and report it.
5. The full rules for every session and job are in `toolchain/instructions/factory-preamble.md`.

## Commands

```
python scripts/toolchain.py doctor      # what is missing on this machine
python scripts/toolchain.py install     # the plan; add --apply to do it
python scripts/toolchain.py verify      # is everything pinned, consistent and loaded
python scripts/toolchain.py update      # what changed upstream, and what it would break
python scripts/validate_docs.py --strict
python -m unittest discover -s scripts -p "test_*.py"
```

More: `toolchain/README.md`.
