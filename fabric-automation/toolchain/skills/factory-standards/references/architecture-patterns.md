# Architecture pattern checks for Fabric solutions

Checks drawn from the Choose a Microsoft Fabric deployment pattern page, the greenfield lakehouse page and the medallion architecture page, covering layering, where each kind of item belongs, choosing between item types, and workspace and capacity layout. This file guides and never authorizes a change.
These pages describe patterns and an example scenario, not rules: each check is written to keep the conditions that its page gives, and a review check is a prompt for a reviewer, not a requirement. The medallion page calls medallion architecture the recommended design approach for Fabric, and the greenfield page says it can be adapted to your needs.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. A question about pausing, deleting or vacuuming something is a question to ask about the change, never an instruction to do it.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| Patterns | https://learn.microsoft.com/azure/architecture/data-guide/technology-choices/fabric-deployment-patterns | 2026-09-21 | 2026-11-01 |
| Greenfield | https://learn.microsoft.com/azure/architecture/example-scenario/data/greenfield-lakehouse-fabric | 2026-08-18 | 2026-11-01 |
| Medallion | https://learn.microsoft.com/fabric/onelake/onelake-medallion-lakehouse-architecture | 2026-08-26 | 2026-11-01 |
| CAF governance | https://learn.microsoft.com/azure/cloud-adoption-framework/data/fabric-governance-unified-data-platform | 2026-10-27 | 2026-11-01 |
| CICD concepts | https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd | 2026-09-09 | 2026-11-01 |

## Layering (medallion)

- `std-arc-01` Is each medallion layer kept in its own lakehouse or warehouse, so that data moves between layers as it is cleaned and refined? [review] Applies to: a new lakehouse or a layered data flow. Source: Medallion, "What is medallion architecture?".
- `std-arc-02` Does each step sit in the right layer: bronze stores everything exactly as it arrives and allows no changes, silver fixes errors, standardizes formats and removes duplicates, and gold organizes data for reports and dashboards? [review] Applies to: a notebook, pipeline or dataflow that moves data between layers. Source: Medallion, "What is medallion architecture?".
- `std-arc-03` For bronze data whose source is OneLake, ADLS Gen2, Google or the Amazon store that the page names, does the change create a shortcut instead of copying the data across? [review] Applies to: a new bronze source. Source: Medallion, "Tables and files"; Medallion, "Deployment model".
- `std-arc-04` Are silver and gold stored as Delta tables, and bronze kept in its original format whenever possible, or otherwise as Parquet or Delta Lake, with Delta a good choice for a relational source? [review] Applies to: a new table or write step. Source: Medallion, "What is medallion architecture?"; Medallion, "Deployment model".
- `std-arc-05` For a new gold layer, is the choice between a lakehouse, whose SQL analytics endpoint serves business users, and a warehouse, whose data warehouse endpoint does, based on preference and team expertise? [review] Applies to: a new gold layer. Source: Medallion, "Deployment model".
- `std-arc-06` Do writes and maintenance target 128 MB to 1 GB files by table size and consumption, with bronze allowed smaller files if modification and preparation focus on Spark, and gold larger files and row groups? [review] Applies to: a new Delta table or a table maintenance step. Source: Medallion, "File size".
- `std-arc-07` Does a new silver or gold table use Liquid Clustering instead of partitioning, and does a new bronze table avoid partitioning, which is acceptable there but discouraged for new implementations? [review] Applies to: a new bronze, silver or gold table. Source: Medallion, "Table partitions and clustering".
- `std-arc-17` Where a maintenance step removes history with VACUUM, does it account for the default rule that history within the last seven days cannot be deleted, and the table property delta.deletedFileRetentionDuration that sets that period? [review] Applies to: a table maintenance or vacuum step. Source: Medallion, "Historical retention".

Note: the medallion page says that bronze stores everything exactly as it arrives and allows no changes, and also recommends storing bronze data in its original format or as Parquet or Delta Lake, keeping the original format whenever possible; the page does not say whether a change of format counts as a change. Source: Medallion, "What is medallion architecture?"; Medallion, "Deployment model".

Note: the medallion page recommends a separate workspace for each lakehouse for layer-level control and governance, the governance page says to avoid extra workspaces that only mirror boundaries which item permissions or OneLake security can enforce reliably, and the CI/CD concepts page splits a medallion solution into a staging workspace and a presentation workspace when business users must not reach staging data. The deployment patterns page gives bronze and silver in one workspace and gold in another, for separate teams, as an example. Each page gives its own criteria; none gives one rule that ranks the options. Source: Medallion, "Deployment model"; CAF governance, "2. Fabric data security"; CICD concepts, "Fabric solutions"; Patterns, "Pattern 2: Multiple workspaces, single capacity".

Note: the medallion page says to use a partitioned folder structure wherever applicable, and in the same section discourages partitioning for new bronze tables and prefers Liquid Clustering over partitioning for silver and gold; the page does not reconcile the two statements. Source: Medallion, "Table partitions and clustering".

## Choosing between item types

- `std-arc-08` For a batch lakehouse transformation, does the tool follow the team's preference: Spark notebooks for a code-first experience, dataflows for a low-code or no-code one? [review] Applies to: a new batch transformation step in a lakehouse solution. Source: Greenfield, "Cold path for batch analytics".
- `std-arc-09` Consider a materialized lake view instead of a hand-built pipeline where silver or gold tables are SQL transformations of upstream data; it manages dependencies, quality rules and refresh. [review] Applies to: a new silver or gold transformation. Source: Medallion, "Use materialized lake views for medallion architecture".
- `std-arc-10` Does the change avoid writing to lakehouse tables through the SQL analytics endpoint, which is read only, and use Spark to modify data instead? [review] Applies to: a SQL script or notebook that changes lakehouse data. Source: Greenfield, "Hot path for real-time analytics".
- `std-arc-11` With Direct Lake on the SQL analytics endpoint, does the design account for DirectQuery fallback, which scenarios such as row-level security, a view in the endpoint or table stats over capacity guardrails can trigger? [review] Applies to: a Direct Lake semantic model that uses a SQL analytics endpoint. Source: Greenfield, "Hot path for real-time analytics".

## Workspace and capacity layout

- `std-arc-12` When deployment pipelines are used for staged promotion, does the design give development, test and production separate workspaces, recognizing that a single-workspace pattern has no preproduction separation and cannot use deployment pipelines? [review] Applies to: a workspace layout for staged deployment. Source: Patterns, "Operational Excellence"; Patterns, "Pattern 1: Monolithic deployment".
- `std-arc-13` For production-like performance or resilience testing, does preproduction use environment-aligned workspaces with capacity-level isolation, and not the pattern where all environments share one capacity, which suits functional validation? [review] Applies to: a preproduction workspace and capacity layout. Source: Patterns, "Operational Excellence".
- `std-arc-14` Are performance-sensitive workloads isolated on a dedicated capacity, since in a shared capacity an expensive query or pipeline can degrade interactive queries for other users? [review] Applies to: a workspace and capacity layout. Source: Patterns, "Performance Efficiency".
- `std-arc-15` Does capacity-pausing automation target nonproduction environments, and, before pausing a capacity that supports production, assess the unavailability of every workload on it? [review] Applies to: automation that pauses a capacity. Source: Patterns, "Reliability"; Patterns, "Cost Optimization".
- `std-arc-16` Does a new shortcut to an external source come with health monitoring of that source and a plan for graceful degradation, since items that rely on it might fail? [review] Applies to: a new shortcut. Source: Patterns, "Reliability".
