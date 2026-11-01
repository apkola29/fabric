# T11: reference frameworks for the factory-standards skill

Raw notes for the `factory-standards` skill of the toolchain kit (`../../../toolchain/skills/factory-standards/SKILL.md`). Date of the reading: 2026-11-01. The 16 pages below were read on learn.microsoft.com. Each was downloaded and reduced to its main text with a script, and the same text went to the model that drafted the pack and to the models that checked it. The Microsoft Learn server and the Azure MCP server were used to find the pages. Nothing here was tested on a tenant. A point that a page does not state is not in the pack.

## 1. Why the guidance is in the repository

The agents of a job run in a sandbox with no network, so they cannot read Learn while they work (design 3.1 and HR-3). If the Well-Architected, security, lifecycle and architecture guidance is to shape a plan, a test or a review, it has to be in the repository, in a form that an agent can apply, with the page and the date that each point came from. A reviewer can then find the source, and a person can see how old it is. The pack guides and never authorizes: the design refuses security, permission, network, label and tenant-setting changes in this version (tier T3), so a check about one of them is flagged to a person and never carried out.

## 2. The pages

| Page | Address | Updated | Feeds |
|---|---|---|---|
| Microsoft Fabric workloads (Well-Architected overview) | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/overview | 2026-07-09 | `well-architected.md` |
| Reliability considerations for Microsoft Fabric workloads | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/reliability | 2026-05-14 | `well-architected.md` |
| Security considerations for Microsoft Fabric workloads | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/security | 2026-05-14 | `well-architected.md` |
| Cost considerations for Microsoft Fabric workloads | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/cost-optimization | 2026-05-14 | `well-architected.md` |
| Microsoft Fabric workload operations | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/operational-excellence | 2026-07-15 | `well-architected.md` |
| Performance efficiency for Microsoft Fabric workloads | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/performance-efficiency | 2026-05-14 | `well-architected.md` |
| Microsoft Fabric security fundamentals | https://learn.microsoft.com/fabric/security/security-fundamentals | 2026-02-12 | `security-and-governance.md` |
| Security in Microsoft Fabric | https://learn.microsoft.com/fabric/security/security-overview | 2026-09-29 | `security-and-governance.md` |
| Azure security baseline for Microsoft Fabric | https://learn.microsoft.com/security/benchmark/azure/baselines/fabric-security-baseline | 2026-08-25 | `security-and-governance.md` |
| Fabric governance in a unified data platform (Cloud Adoption Framework) | https://learn.microsoft.com/azure/cloud-adoption-framework/data/fabric-governance-unified-data-platform | 2026-10-27 | `security-and-governance.md` |
| Microsoft Fabric adoption roadmap: Governance | https://learn.microsoft.com/power-bi/guidance/fabric-adoption-roadmap-governance | 2026-01-02 | `security-and-governance.md` |
| Best practices for lifecycle management in Fabric | https://learn.microsoft.com/fabric/cicd/best-practices-cicd | 2026-07-22 | `delivery-and-lifecycle.md` |
| Fabric CI/CD concepts and best practices | https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd | 2026-09-09 | `delivery-and-lifecycle.md` |
| Choose a Microsoft Fabric deployment pattern | https://learn.microsoft.com/azure/architecture/data-guide/technology-choices/fabric-deployment-patterns | 2026-09-21 | `architecture-patterns.md` |
| Greenfield lakehouse on Microsoft Fabric | https://learn.microsoft.com/azure/architecture/example-scenario/data/greenfield-lakehouse-fabric | 2026-08-18 | `architecture-patterns.md` |
| Understand medallion architecture for Fabric with OneLake | https://learn.microsoft.com/fabric/onelake/onelake-medallion-lakehouse-architecture | 2026-08-26 | `architecture-patterns.md` |

## 3. What was observed

1. Microsoft publishes Well-Architected guidance for Fabric workloads: an overview and one page for each of the five pillars (the first six rows). The Fabric CI/CD concepts page is very large (about 150,000 characters in the reduced text), so the drafter read its headings first and used only the sections that it cited.
2. The Well-Architected tool of the Azure MCP Server covers Azure services and not Fabric: its list held 31 Azure services, and Fabric was not among them (a tool call on 2026-11-01; the fact list cannot check it, because it needs a launched server). So the Fabric guidance comes from the pages above, and the tool serves only the Azure services around Fabric. The pinned contract of that server has the `documentation`, `wellarchitectedframework`, `cloudarchitect` and `get_azure_bestpractices` tools.
3. The Azure security baseline for Fabric carries a notice that it is "based on a previous version of Microsoft Cloud Security Benchmark (v1.0) and may contain outdated guidance", and sends the reader to the Fabric documentation for the latest guidance. The security file of the pack says so, and the claim `page-fabric-security-baseline-notice` watches the notice.
4. A Learn page carries two dates in its markup: `ms.date`, which the author sets, and `updated_at`, which is set when the page is published. They differ: the Well-Architected overview has `ms.date` 2026-05-13 and `updated_at` 2026-07-09. The pack records the `updated_at` date, because it is the one that moves when the text changes. The fact list watches that date for every page that the pack cites (one claim for each page, marked `stable: false`, so that a later date shows as drift and not as a failure).
5. The Fabric security overview (2026-09-29) is newer than the baseline page (2026-08-25), and the fundamentals page (2026-02-12) is older. The brief for the pack asked that, where two pages say different things, the pack say so and cite both. It does not rank the pages.

## 4. How the pack stays current

- The weekly fact check reports a source page with a later `updated_at` as drift. A person then reads the page, refreshes the pack in a pull request and updates the date in the claim and in the sources table of the file. A test refuses a page of the pack that no claim watches (`StandardsPackTests`).
- A run does not edit the pack. Where the Learn server answers and its page is newer than the pack and differs, the run reports the difference in the pull request (`factory-standards`, section 4).
- A cross-family check of every line against the page text was made before the pack was published: four rounds by three other model families, the third with a quote of the source for every row that a program looked up in the cited section. It is recorded in `../../reviews/standards-pack-findings.md` and in `../../reviews/verification-log.md` (loop 13).
- A person who refreshes the pack finds what a program can check in `../../../verification/tools/` (the structure and the quotes: `pack_mechanics.py`, `pack_quotes.py`; the dates: `pack_dates.py`; the hedge words that a check has lost: `pack_hedges.py`). The document validator reads a name made of a capital letter and a digit, such as the name of the Amazon object store, as an identifier of the design, so the pack says "the Amazon store that the page names".

## 5. UNVERIFIED and limits

- The pack is a condensation of the pages by a model, checked by other models. It is not a Microsoft checklist and not a statement of compliance, and the pages themselves say that they give guidance and not a certification.
- The pages change without notice. The pack records the date of each page, and the weekly check shows a change, but between the change and the refresh the pack is old.
- Pages in other languages, other cloud frameworks (for example the CIS or NIST publications) and the Fabric release notes were not read. The pack does not claim to cover them.
