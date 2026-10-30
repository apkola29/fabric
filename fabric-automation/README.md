# Fabric Automation

Design and research for the **Fabric Code Factory**: an autonomous, Git-backed way to turn a natural-language requirement into a verified pull request against Microsoft Fabric and Power BI items. A person approves at the end.

> **Status.** Design v0.2 is complete and has been reviewed by three model families. **Nothing is built yet.** The next step is Phase 0: a set of spikes that test the platform assumptions on a real tenant. This folder holds the documents, and the tooling that checks them.

## The idea

1. Fabric workspaces are backed up in Git, and Git is the source of truth.
2. A requirement arrives as a GitHub issue.
3. The factory opens a branch, changes the item definitions (semantic models, reports, data agents and ontologies first, then notebooks, pipelines, lakehouses and more), and validates the change in an ephemeral sandbox workspace with synthetic data.
4. It runs static, data and BI quality gates, asks other model families to review, and opens a draft pull request with an evidence bundle.
5. A person approves. The factory never merges, approves or promotes.

## Where to start

| Read | What it is |
|---|---|
| [Design](docs/04-design.md) | Architecture, hard rules, security design, roadmap, risks and scenarios. Start at section 1. |
| [Requirements](docs/01-requirements.md) | Functional and non-functional requirements, assumptions, open questions. |
| [Decision register](docs/02-decision-register.md) | Each decision, what closes it, and what changed since v0.1. |
| [Research digest](docs/03-landscape-research.md) | The landscape in one document, with the quality-gate catalogue and the threat model. |
| [Brief](docs/00-brief.md) | The idea, the way of working, and the research rules. |
| [Reviews](docs/reviews/) | The cross-verification, the three-model design review, the disposition of every finding, the closure check, and the verification log. |
| [Research](docs/research/) | The raw reports behind the digest. |
| [Archive](docs/archive/) | Version 0.1 of the design and the register. |

## How it was produced

Nine research threads on live sources, then a cross-verification of the decision-driving claims by three model families, a design, an attack on that design by three reviewers from different angles, a written disposition of every finding, and a closure check by the same reviewers. The trail is in `docs/reviews` and `docs/research`. Facts the reviewers disputed were re-fetched from their primary source before they were accepted.

## Checking this folder

```
python scripts/validate_docs.py --strict
python -m unittest discover -s scripts -p "test_*.py"
python scripts/verify_facts.py
```

- `validate_docs.py` checks the structure of the documents: tables and diagrams, section numbering, that every identifier (requirement, decision, hard rule, spike, finding) is defined and traced, that the counts stated in the text match the tables, that links and file references resolve, and that no local path, address or secret is published.
- The tests inject known defects into a copy of this folder and require the validator to report each one, so a passing validator means something.
- `verify_facts.py` checks concrete claims (package versions, repository contents, wording of documentation pages) against their public sources. It needs the open internet. A GitHub Action runs the first two checks on every change to this folder, and the third on demand.
- `verify_remote.py` compares the Git hash of every file with what GitHub holds.

## What is not published

Two local environment surveys (referred to as L1 and L2 in the documents) describe the author's machine and lab, so they stay local. Local machine paths and details of a non-public mirror of a skills repository were removed from the raw reports before publication. The validator can refuse any file that contains a term from a private list kept outside the repository.

## Keeping it in sync (maintainers)

`scripts/sync_to_github.ps1 -Message "what changed"` validates the folder, mirrors it into a local clone of the repository, commits only these paths, pushes, and proves that GitHub holds the same bytes.

## Caveats

Nothing here has been tested on a live tenant. Claims that a source could not confirm are marked UNVERIFIED. Several Fabric features named in the design are in preview and can change. The documents are dated 2026-10-30 and describe the platform on that day.

These documents are provided as-is for learning and discussion, without warranty. The repository's MIT license applies.

