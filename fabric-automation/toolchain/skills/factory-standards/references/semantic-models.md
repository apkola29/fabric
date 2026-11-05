# Semantic model checks for Fabric and Power BI changes

Checks drawn from the two Direct Lake pages (query performance, and developing models), three Power BI guidance pages (star schema, the optimization guide, and data reduction for Import models) and the dimensional modeling overview for Fabric Data Warehouse, for use when a change creates or alters a semantic model or the Delta tables that a Direct Lake model reads. This file guides and never authorizes a change.
The pages give different advice for different modes, and much of it is guidance and not a rule, so each check names its mode (Direct Lake, Import, or a semantic model in general) and keeps the conditions of its page. Where a page weighs two options, the check asks which one the change uses and why. The develop page marks calculated columns and calculated tables that reference Direct Lake tables as preview, and the optimization guide and the Import data reduction page carry a notice that Microsoft is retiring the Power BI Premium per-capacity SKUs; no check below rests on a capacity size.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. A question about vacuuming, overwriting or optimizing a table is a question to ask about the change, never an instruction to do it.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| Direct Lake storage | https://learn.microsoft.com/fabric/fundamentals/direct-lake-understand-storage | 2026-08-03 | 2026-11-04 |
| Direct Lake develop | https://learn.microsoft.com/fabric/fundamentals/direct-lake-develop | 2026-11-04 | 2026-11-04 |
| Star schema | https://learn.microsoft.com/power-bi/guidance/star-schema | 2026-04-01 | 2026-11-04 |
| Power BI optimization | https://learn.microsoft.com/power-bi/guidance/power-bi-optimization | 2026-04-01 | 2026-11-04 |
| Import reduction | https://learn.microsoft.com/power-bi/guidance/import-modeling-data-reduction | 2026-01-02 | 2026-11-04 |
| Warehouse modeling | https://learn.microsoft.com/fabric/data-warehouse/dimensional-modeling-overview | 2026-07-06 | 2026-11-04 |

## Direct Lake models: form, definition and deployment

- `std-sem-01` Does a Direct Lake model name its reason for Direct Lake on OneLake (for example composite modeling) or Direct Lake on SQL (for example SQL analytics endpoint security rules in delegated identity mode)? [review] Applies to: a new Direct Lake semantic model, or a change of its form. Source: Direct Lake develop, "Choose the right storage mode".
- `std-sem-02` If a Direct Lake model needs calculated tables or calculated columns that reference Direct Lake tables, does the change record that the page marks this feature, listed under Direct Lake on OneLake, as preview? [review] Applies to: a calculated column or calculated table in a Direct Lake model. Source: Direct Lake develop, "Choose the right storage mode".
- `std-sem-03` Where a Direct Lake model allows DirectQuery fallback, does it keep fallback only for a scenario that needs it, since the page advises disabling it where possible to avoid hybrid query plans? [review] Applies to: a Direct Lake semantic model that can fall back to DirectQuery. Source: Direct Lake storage, "What affects Direct Lake query performance"; Direct Lake develop, "Choose the right storage mode".
- `std-sem-04` Does the definition of a Direct Lake model show a database compatibility level of 1604 or higher and Direct Lake partitions in directLake mode? [gate] Applies to: the definition of a new or changed Direct Lake semantic model. Source: Direct Lake develop, "Direct Lake model metadata".
- `std-sem-05` Ask: does a Direct Lake on OneLake model in a deployment pipeline, which has no data source rules for it, use text M parameters with a deployment parameter rule for each changing value? [review] Applies to: a Direct Lake on OneLake semantic model in a deployment pipeline. Source: Direct Lake develop, "Use M parameters with deployment pipelines".

Note: the develop page lists reasons to choose each form of Direct Lake, including that Direct Lake on SQL suits scenarios that need an unsupported case to fall back to DirectQuery and that Direct Lake on OneLake does not fall back, while the storage page advises disabling fallback where possible; so fallback is a concern only for Direct Lake on SQL. Source: Direct Lake develop, "Choose the right storage mode"; Direct Lake develop, "Direct Lake model metadata"; Direct Lake storage, "What affects Direct Lake query performance".

- `std-sem-18` Does the connector of a Direct Lake model match its form: Azure Data Lake Storage for Direct Lake on OneLake, SQL Server or OneLake.SqlAnalytics() for Direct Lake on SQL? [review] Applies to: the data source expression of a new or changed Direct Lake semantic model, where the page says the connector in TMDL view shows which form a model is on. Source: Direct Lake develop, "Power Query connectors".

## Delta tables behind a Direct Lake model

- `std-sem-06` Does a table behind a Direct Lake model have V-Order applied and row groups near the ideal of 1 million to 16 million rows, with Fabric's default size left alone in general? [review] Applies to: a notebook or pipeline that writes or rewrites a Delta table read by a Direct Lake model. Source: Direct Lake storage, "Understand Direct Lake query performance"; Direct Lake storage, "Row group size"; Direct Lake storage, "Considerations and limitations".
- `std-sem-07` For a large Delta table behind a Direct Lake model, does the load avoid destructive patterns, such as the Overwrite option or deletes and updates that touch most files, so incremental framing still works? [review] Applies to: a notebook or pipeline that loads, updates or deletes rows in a Delta table read by a Direct Lake model. Source: Direct Lake storage, "Delta table update patterns"; Direct Lake storage, "Batch processing without partitioning"; Direct Lake storage, "Considerations and limitations".
- `std-sem-08` If a Delta table behind a Direct Lake model is partitioned, does its partition column have low cardinality, fewer than 100-200 distinct values, which a daily date key over five years exceeds? [review] Applies to: a Delta table that is partitioned for a Direct Lake model; for a new silver or gold table, std-arc-07 asks whether Liquid Clustering is used instead of partitioning, which the storage page does not mention. Source: Direct Lake storage, "Batch processing with partitioning"; Direct Lake storage, "Partitioned rolling window updates"; Direct Lake storage, "Considerations and limitations".
- `std-sem-09` Where a step vacuums a table behind a Direct Lake model, does it keep the Delta commit version that the framed model references until the next refresh, since users get query errors otherwise? [review] Applies to: a vacuum or retention step on a Delta table read by a Direct Lake model. Source: Direct Lake storage, "Vacuuming".

Note: the storage page calls 1 million to 16 million rows the ideal row group size and says Fabric might use larger row groups for large tables whose data compresses well; its sample table averages about 40 million rows per row group, which it calls above the recommended maximum yet not a significant problem, and it names row groups significantly under 1 million rows as the case that can cause performance problems. Source: Direct Lake storage, "Row group size".

Note: the storage page advises optimizing infrequently, for example over weekends or at the end of the month, because replaced files cost a short cold-state penalty, and optimizing more often when small files accumulate quickly, with daily runs or more for streaming; it calls the cadence a tradeoff to balance. Source: Direct Lake storage, "Spark Optimize"; Direct Lake storage, "Stream processing".

Note: the storage page gives the limit for the partition column as fewer than 100-200 distinct values in one section and fewer than 200 in another, and does not say which bound applies. Source: Direct Lake storage, "Batch processing with partitioning"; Direct Lake storage, "Partitioned rolling window updates".

Note: the storage page presents partitioning on a low-cardinality column as a way to limit the effect of deletes and of Optimize on incremental framing, warns that extensive partitioning can hurt query performance, and says that partitioning is not necessary for incremental loading or stream processing; it does not mention Liquid Clustering. Source: Direct Lake storage, "Batch processing with partitioning"; Direct Lake storage, "Spark Optimize"; Direct Lake storage, "Incremental loading"; Direct Lake storage, "Stream processing".

## Star schema design

- `std-sem-10` For an enterprise solution, is the semantic model built on a dimensional model (star schema) in a Fabric Warehouse, the page's recommended prerequisite, and does a model connecting directly to source data say why? [review] Applies to: a new enterprise semantic model or a Fabric Warehouse design; the page gives self-service analysts who need agility as an example where that might not be the best approach, and std-arc-05 covers the choice of a lakehouse or a warehouse for a new gold layer, which the page does not discuss. Source: Warehouse modeling, "Dimensional modeling for Power BI"; Warehouse modeling, "Star schema design".
- `std-sem-11` For a requirement to analyze past dimension values accurately, where the source stores no versions, does an intermediate system such as a data warehouse capture Type 2 versions, as Power Query cannot produce them? [review] Applies to: a semantic model or dimension table that must show history. Source: Warehouse modeling, "Dimensional modeling for Power BI"; Star schema, "Type 2 SCD".
- `std-sem-12` Is each model table either a dimension table or a fact table, with exceptions such as a degenerate dimension column in a fact table, and do fact tables load at a consistent grain? [review] Applies to: a table added to or changed in a semantic model. Source: Star schema, "Star schema relevance to Power BI semantic models"; Star schema, "Degenerate dimensions".
- `std-sem-13` If one dimension plays several roles for a fact table (for example order, ship and delivery date), does the model use inactive relationships with USERELATIONSHIP or a table per role, and say why? [review] Applies to: a date or other dimension that relates to a fact table in several roles. Source: Star schema, "Role-playing dimensions".
- `std-sem-14` If report authors will query with MDX, for example Analyze in Excel, or the design wants to control how a column is summarized, does the model define explicit measures, hiding that column where needed? [review] Applies to: a semantic model that report authors query. Source: Star schema, "Measures".

Note: the star schema page suggests hiding a column and offering measures to control how it is summarized; it says this suits reports built in the Power BI service and Q&A, but that live connections from Power BI Desktop can display hidden fields and so defeat the approach. Source: Star schema, "Measures".

## Import models

- `std-sem-15` Does each column loaded into an Import table serve reporting or model structure, such as relationships, calculations or security roles, since adding a column later is easier than removing one? [review] Applies to: a table added to or changed in an Import model. Source: Import reduction, "Remove unnecessary columns".
- `std-sem-16` Does an Import table avoid loading all available history by default, for example through a relative time filter driven by Power Query parameters, unless full history is a known reporting requirement? [review] Applies to: a fact table or date table loaded into an Import model. Source: Import reduction, "Remove unnecessary rows".

Note: the data reduction page calls loading pre-summarized data perhaps the most effective way to reduce an Import model, says that summarizing fact data always involves tradeoffs, gives a month-level grain with a possible 99% reduction at the cost of day-level and order-line reporting, and says that DirectQuery tables could mitigate the loss. Source: Import reduction, "Group by and summarize".

## Usability for report authors

- `std-sem-17` Does a model give tables, columns and measures descriptive names, and consider adding descriptions that can explain how to use an object and hiding objects that reports are not expected to use? [review] Applies to: a new or changed semantic model. Source: Power BI optimization, "Optimizing for report authors and model consumers".
