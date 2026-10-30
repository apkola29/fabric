# Fabric Automation

[![validate](https://github.com/apkola29/fabric/actions/workflows/fabric-automation-validate.yml/badge.svg)](https://github.com/apkola29/fabric/actions/workflows/fabric-automation-validate.yml)

Design and research for the **Fabric Code Factory**: an autonomous, Git-backed way to turn a natural-language requirement into a verified pull request against Microsoft Fabric and Power BI items. A person approves at the end.

> **Status.** Design v0.2 is complete, has been reviewed by three model families, and was corrected after a first verification round. **Nothing is built yet**, and nothing in it has been tested on a tenant. The next step is Phase 0: a set of spikes that test the platform assumptions on a real tenant. This folder holds the documents, and the tooling that checks them.

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

### Suggested reading order

1. Design section 1 (summary) and section 2 (hard rules).
2. Design 3.1 (zones and trust boundaries) and 3.3 (run lifecycle).
3. Design 4.1 (how the design answers the top attack paths).
4. Design section 5 (roadmap and the Phase 0 spikes) and section 10 (open questions).
5. Then the requirements and the decision register, and for the evidence the [reviews index](docs/reviews/README.md).

### Terms used in the documents

| Term | Meaning |
|---|---|
| FR, NFR | Functional and non-functional requirements, in the requirements document |
| D-nn | A decision in the decision register |
| HR-n | A hard rule that every component obeys (design section 2) |
| T0 to T3 | The risk tier of a change: T0 documentation and formatting, T1 additive, T2 a change to existing shared behaviour, T3 security-sensitive (refused in v1) |
| S1 to S11 | The Phase 0 spikes: short experiments that test platform assumptions on a real tenant before anything is built |
| N1 to N12 | Negative tests of the repository and evidence controls (spike S11) |
| Phase 0 to 3 | The roadmap phases (design section 5) |
| Model family | A vendor line of models, for example GPT, Gemini, Grok or Claude. Reviews use families other than the author's, so that one family's blind spots are not shared |
| Run store | The system of record for each run (design 3.3) |
| Executor, publisher | The trusted components that hold the Fabric identities and write to GitHub (design 3.1) |

## How it was produced

Nine research threads on live sources, then a cross-verification of the decision-driving claims by three model families, a design, an attack on that design by three reviewers from different angles, a written disposition of every finding, and a closure check by the same reviewers. After publication came verification rounds on the published text: a clean-room CI run, a check of the platform facts against primary sources, and a second three-model pass. The trail is in `docs/reviews` and `docs/research`. Facts the reviewers disputed were re-fetched from their primary source before they were accepted.

## Checking this folder

Run these from the `fabric-automation` folder. They need Python 3 and nothing else (CI uses `python3`).

```
python scripts/validate_docs.py --strict
python -m unittest discover -s scripts -p "test_*.py"
python scripts/verify_facts.py
```

- `validate_docs.py` checks the structure of the documents: tables and diagrams, section numbering, that every identifier (requirement, decision, hard rule, spike, finding) is defined and traced, that the counts stated in the text match the tables, that links and file references resolve, and that no local path, address or secret is published.
- The tests do two things. For the validator, each test injects one known defect into a copy of this folder and requires the validator to report it, and one more test requires the unmodified folder to be clean. For the fact checker, the tests replace the network with a fake and check each outcome. They show that the checks can fail. They do not show that the documents are right.
- `verify_facts.py` checks concrete claims (package versions, repository contents, wording of documentation pages) against their public sources. It needs the open internet. A GitHub Action runs the validator and the tests on every change to this folder and on pull requests, and a second one runs the fact checks on demand.
- `verify_remote.py` compares the Git hash of every file with what GitHub holds.
- A green validator is not proof that a publication is clean. The list of private terms cannot live in a public repository, so only the maintainer's publish script applies it, and that script refuses to publish without it. CI applies only the generic patterns.

Every verification round, what it found and what changed is recorded in the [verification log](docs/reviews/verification-log.md).

## What is not published

Two local environment surveys (referred to as L1 and L2 in the documents) describe the author's machine and lab, so they stay local. Local machine paths and other non-public details were removed from the raw reports before publication. The validator can refuse any file that contains a term from a private list kept outside the repository.

## Keeping it in sync (maintainers)

`scripts/sync_to_github.ps1 -Message "what changed"` validates the folder with the private term list (and stops if there is none), runs the tests, mirrors the folder into a local clone of the repository, commits only these paths, checks that everything it would push touches only these paths, pushes that commit by its SHA, and proves that GitHub holds the same bytes. It never force-pushes.

## Caveats

Nothing here has been tested on a live tenant. Claims that a source could not confirm are marked UNVERIFIED. Several Fabric features named in the design are in preview and can change. The documents are dated 2026-10-30 and describe the platform on that day.

These documents are provided as-is for learning and discussion, without warranty. The repository's MIT license applies.

