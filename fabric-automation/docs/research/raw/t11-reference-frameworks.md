# T11: reference frameworks for the factory-standards skill

Raw notes for the `factory-standards` skill of the toolchain kit (`../../../toolchain/skills/factory-standards/SKILL.md`). Dates of the readings: 2026-11-01 for the 16 pages of the first four files and 2026-11-04 for the 28 pages of the five workload files that came later (section 2). All 44 pages were read on learn.microsoft.com. Each was downloaded and reduced to its main text with a script, and the same text went to the model that drafted the pack and to the models that checked it. The Microsoft Learn server and the Azure MCP server were used to find the pages. Nothing here was tested on a tenant. A point that a page does not state is not in the pack.

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
| Choose a Microsoft Fabric deployment pattern | https://learn.microsoft.com/azure/architecture/data-guide/technology-choices/fabric-deployment-patterns | 2026-11-02 | `architecture-patterns.md` |
| Greenfield lakehouse on Microsoft Fabric | https://learn.microsoft.com/azure/architecture/example-scenario/data/greenfield-lakehouse-fabric | 2026-08-18 | `architecture-patterns.md` |
| Understand medallion architecture for Fabric with OneLake | https://learn.microsoft.com/fabric/onelake/onelake-medallion-lakehouse-architecture | 2026-08-26 | `architecture-patterns.md` |

The five workload files (`data-engineering.md`, `capacity-and-cost.md`, `semantic-models.md`, `onelake-security.md` and `data-agents.md`) were drafted in a second reading on 2026-11-04 from these 28 pages, with the `updated_at` date that each page carried then:

| Page | Address | Updated | Feeds |
|---|---|---|---|
| Spark monitoring and performance optimization best practices | https://learn.microsoft.com/fabric/data-engineering/spark-monitoring-best-practices | 2026-10-23 | `data-engineering.md` |
| Development and Monitoring | https://learn.microsoft.com/fabric/data-engineering/spark-best-practices-development-monitoring | 2026-08-18 | `data-engineering.md` |
| Fabric Spark Capacity and Cluster Planning | https://learn.microsoft.com/fabric/data-engineering/spark-best-practices-capacity-planning | 2026-08-13 | `data-engineering.md` |
| Optimize Delta Lake tables with V-Order in Fabric | https://learn.microsoft.com/fabric/data-engineering/delta-optimization-and-v-order | 2026-08-04 | `data-engineering.md` |
| Cross-Workload Table Maintenance and Optimization in Microsoft Fabric | https://learn.microsoft.com/fabric/fundamentals/table-maintenance-optimization | 2026-09-20 | `data-engineering.md` |
| SQL Analytics Endpoint Performance Considerations | https://learn.microsoft.com/fabric/data-engineering/sql-analytics-endpoint-performance | 2026-09-16 | `data-engineering.md` |
| Native execution engine for Fabric Data Engineering | https://learn.microsoft.com/fabric/data-engineering/native-execution-engine-overview | 2026-08-10 | `data-engineering.md` |
| Best practices for getting the best performance with Dataflow Gen2 in Fabric Data Factory | https://learn.microsoft.com/fabric/data-factory/dataflow-gen2-performance-best-practices | 2026-09-29 | `data-engineering.md` |
| Evaluate and optimize your Microsoft Fabric capacity | https://learn.microsoft.com/fabric/enterprise/optimize-capacity | 2026-09-29 | `capacity-and-cost.md` |
| Microsoft Fabric Capacity Planning Guide: Plan Your First Deployment | https://learn.microsoft.com/fabric/enterprise/capacity-planning-plan-deployment | 2026-02-17 | `capacity-and-cost.md` |
| Microsoft Fabric Capacity Planning Guide: Manage Growth and Governance | https://learn.microsoft.com/fabric/enterprise/capacity-planning-manage-capacity-growth-governance | 2026-09-29 | `capacity-and-cost.md` |
| Understand capacity throttling and smoothing | https://learn.microsoft.com/fabric/enterprise/throttling | 2026-08-18 | `capacity-and-cost.md` |
| Understand Direct Lake query performance | https://learn.microsoft.com/fabric/fundamentals/direct-lake-understand-storage | 2026-08-03 | `semantic-models.md` |
| Develop Direct Lake semantic models | https://learn.microsoft.com/fabric/fundamentals/direct-lake-develop | 2026-11-04 | `semantic-models.md` |
| Understand star schema and the importance for Power BI | https://learn.microsoft.com/power-bi/guidance/star-schema | 2026-04-01 | `semantic-models.md` |
| Optimization guide for Power BI | https://learn.microsoft.com/power-bi/guidance/power-bi-optimization | 2026-04-01 | `semantic-models.md` |
| Data reduction techniques for Import modeling | https://learn.microsoft.com/power-bi/guidance/import-modeling-data-reduction | 2026-01-02 | `semantic-models.md` |
| Dimensional Modeling (Fabric Data Warehouse) | https://learn.microsoft.com/fabric/data-warehouse/dimensional-modeling-overview | 2026-07-06 | `semantic-models.md` |
| Security best practices (OneLake) | https://learn.microsoft.com/fabric/onelake/security/best-practices-secure-data-in-onelake | 2026-09-01 | `onelake-security.md` |
| OneLake security roles, permissions, and scopes | https://learn.microsoft.com/fabric/onelake/security/data-access-control-model | 2026-10-16 | `onelake-security.md` |
| OneLake table, column, and row-level security | https://learn.microsoft.com/fabric/onelake/security/table-column-row-security | 2026-08-19 | `onelake-security.md` |
| Data security overview (OneLake) | https://learn.microsoft.com/fabric/onelake/security/get-started-security | 2026-09-29 | `onelake-security.md` |
| Best practices for improving data agent query generation | https://learn.microsoft.com/fabric/data-science/data-agent-configuration-best-practices | 2026-08-31 | `data-agents.md` |
| Data agent configurations | https://learn.microsoft.com/fabric/data-science/data-agent-configurations | 2026-09-29 | `data-agents.md` |
| Data Agent Example Queries | https://learn.microsoft.com/fabric/data-science/data-agent-example-queries | 2026-06-23 | `data-agents.md` |
| Add a data source to Data Agent | https://learn.microsoft.com/fabric/data-science/data-agent-add-datasources | 2026-09-30 | `data-agents.md` |
| Semantic model best practices for data agent | https://learn.microsoft.com/fabric/data-science/semantic-model-best-practices | 2026-09-01 | `data-agents.md` |
| Source Control, CI/CD, and ALM for Fabric Data Agent | https://learn.microsoft.com/fabric/data-science/data-agent-source-control | 2026-08-31 | `data-agents.md` |

## 3. What was observed

1. Microsoft publishes Well-Architected guidance for Fabric workloads: an overview and one page for each of the five pillars (the first six rows). The Fabric CI/CD concepts page is very large (about 150,000 characters in the reduced text), so the drafter read its headings first and used only the sections that it cited.
2. The Well-Architected tool of the Azure MCP Server covers Azure services and not Fabric: its list held 31 Azure services, and Fabric was not among them (a tool call on 2026-11-01; the fact list cannot check it, because it needs a launched server). So the Fabric guidance comes from the pages above, and the tool serves only the Azure services around Fabric. The pinned contract of that server has the `documentation`, `wellarchitectedframework`, `cloudarchitect` and `get_azure_bestpractices` tools.
3. The Azure security baseline for Fabric carries a notice that it is "based on a previous version of Microsoft Cloud Security Benchmark (v1.0) and may contain outdated guidance", and sends the reader to the Fabric documentation for the latest guidance. The security file of the pack says so, and the claim `page-fabric-security-baseline-notice` watches the notice.
4. A Learn page carries two dates in its markup: `ms.date`, which the author sets, and `updated_at`, which is set when the page is published. They differ: the Well-Architected overview has `ms.date` 2026-05-13 and `updated_at` 2026-07-09. The pack records the `updated_at` date, because it is the one that moves when the text changes. The fact list watches that date for every page that the pack cites (one claim for each page, marked `stable: false`, so that a later date shows as drift and not as a failure).
5. The Fabric security overview (2026-09-29) is newer than the baseline page (2026-08-25), and the fundamentals page (2026-02-12) is older. The brief for the pack asked that, where two pages say different things, the pack say so and cite both. It does not rank the pages.
6. The deployment pattern page was republished on 2026-11-02, after the pack was written. The upstream change is one sentence of its Well-Architected section, which now names the "Design area considerations" tables where it named "the per-pattern tables earlier in this article". The check lines of `architecture-patterns.md` were read again against the new text and none of them changed; only the date in the sources table and in the claim moved.

## 4. How the pack stays current

- The weekly fact check reports a source page with a later `updated_at` as drift. A person then reads the page, refreshes the pack in a pull request and updates the date in the claim and in the sources table of the file. A test refuses a page of the pack that no claim watches (`StandardsPackTests`).
- A run does not edit the pack. Where the Learn server answers and its page is newer than the pack and differs, the run reports the difference in the pull request (`factory-standards`, section 4).
- A cross-family check of every line against the page text was made before the pack was published: four rounds by three other model families, the third with a quote of the source for every row that a program looked up in the cited section. It is recorded in `../../reviews/standards-pack-findings.md` and in `../../reviews/verification-log.md` (loop 13).
- A person who refreshes the pack finds what a program can check in `../../../verification/tools/` (the structure and the quotes: `pack_mechanics.py`, `pack_quotes.py`; the dates: `pack_dates.py`; the hedge words that a check has lost: `pack_hedges.py`). The document validator reads a name made of a capital letter and a digit, such as the name of the Amazon object store, as an identifier of the design, so the pack says "the Amazon store that the page names".

## 5. UNVERIFIED and limits

- The pack is a condensation of the pages by a model, checked by other models. It is not a Microsoft checklist and not a statement of compliance, and the pages themselves say that they give guidance and not a certification.
- The pages change without notice. The pack records the date of each page, and the weekly check shows a change, but between the change and the refresh the pack is old.
- Pages in other languages, other cloud frameworks (for example the CIS or NIST publications) and the Fabric release notes were not read. The pack does not claim to cover them.
- **Microsoft guidance on the workloads themselves is in the pack only for five areas.** The five workload files cover Spark and Delta tables (with the SQL analytics endpoint and Dataflow Gen2 performance), semantic models (Direct Lake, Import, star schema and the dimensional modeling page of the Warehouse), capacity and cost, OneLake security, and data agents. Eventhouse and Real-Time Intelligence, ontology, pipelines, and Warehouse tuning beyond the dimensional modeling page were not searched for. A job that needs one of these has no check for it: it follows the existing deployment and the owning skill, and says that the point rests on them.
- The 56 pinned skills carry part of this as procedure. A fetch of them on 2026-11-01 found V-order in 13 files, Direct Lake in 12, row-level security in 15 and the Best Practice Analyzer in none. They are pinned by digest and checked against the manifest. Nobody has read them as knowledge for correctness or for currency, so none of it is verified here.
- Industry guidance from outside Microsoft (OWASP, NIST, MITRE, CIS, and community advice on modelling, DAX and Spark tuning) is not in the pack. The design and the research notes use some of it for the factory's own protection and gates: the Microsoft Best Practice Analyzer rule file is a gate for semantic models in the design, and [t3c-bi-elt-testing.md](t3c-bi-elt-testing.md) and [t5-security-governance.md](t5-security-governance.md) cite the testing and agent-security sources. Nothing turns that into checks that an agent applies to a change.
- Nobody has run an agent with the pack, and the checks were verified as text by models of three other families that read the same extracted page text. No person who knows Fabric has reviewed it.
