# Data engineering checks for Fabric changes

Checks drawn from eight Microsoft Learn pages on Spark development, monitoring and capacity planning, the native execution engine, Delta table layout and maintenance, the SQL analytics endpoint and Dataflow Gen2 performance, for use when a change adds or alters a notebook, a Spark environment, a lakehouse table or a dataflow. This file guides and never authorizes a change.
The pages give tuning advice, not rules, and several tie a point to a runtime version, a default or a preview state, so each check keeps the conditions that its page gives. Where two pages differ, a Note says so and no check ranks them.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. A question about vacuuming, disabling or compacting something is a question to ask about the change, never an instruction to do it.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| Spark monitoring | https://learn.microsoft.com/fabric/data-engineering/spark-monitoring-best-practices | 2026-10-23 | 2026-11-04 |
| Spark development | https://learn.microsoft.com/fabric/data-engineering/spark-best-practices-development-monitoring | 2026-08-18 | 2026-11-04 |
| Spark capacity | https://learn.microsoft.com/fabric/data-engineering/spark-best-practices-capacity-planning | 2026-08-13 | 2026-11-04 |
| V-order | https://learn.microsoft.com/fabric/data-engineering/delta-optimization-and-v-order | 2026-08-04 | 2026-11-04 |
| Table maintenance | https://learn.microsoft.com/fabric/fundamentals/table-maintenance-optimization | 2026-09-20 | 2026-11-04 |
| SQL endpoint | https://learn.microsoft.com/fabric/data-engineering/sql-analytics-endpoint-performance | 2026-09-16 | 2026-11-04 |
| Native engine | https://learn.microsoft.com/fabric/data-engineering/native-execution-engine-overview | 2026-08-10 | 2026-11-04 |
| Dataflow performance | https://learn.microsoft.com/fabric/data-factory/dataflow-gen2-performance-best-practices | 2026-09-29 | 2026-11-04 |

## Runtime and session

- `std-eng-01` Does a new Spark workload start on the latest runtime, which the monitoring page calls the current general-availability runtime, Runtime 2.0, and the development page currently calls the most up-to-date? [review] Applies to: a new notebook, Spark job definition or environment; a notebook that works with OneLake security also falls under std-olk-16, which names runtime 1.3, and the pages do not say how the two fit. Source: Spark monitoring, "Always use the latest general availability runtime"; Spark development, "Scenario: You need to know which runtime to use for development.".
- `std-eng-02` Where a notebook uses %%configure, is it in the first cell, as the pages advise? [gate] Applies to: a new or changed notebook. Source: Spark monitoring, "The %%configure magic command"; Spark development, "Scenario: Customize session configuration in the Notebook".
- `std-eng-03` Where a pipeline runs several notebooks that share the same default lakehouse, environment and Spark configuration, does the change consider High Concurrency mode with session tags to cut cumulative start-up time? [review] Applies to: a pipeline that runs notebooks, for example in a ForEach loop; the development page says to enable High Concurrency mode at the workspace level. Source: Spark development, "Scenario: When to run on High Concurrency Mode?"; Spark monitoring, "High concurrency mode and session lifecycle"; Spark capacity, "Scenario: You're migrating workloads from Azure Synapse to Fabric.".
- `std-eng-04` If the change enables the native execution engine, does the workload suit it, for example Parquet or Delta data and computationally intensive queries, and avoid unsupported features such as structured streaming? [review] Applies to: enabling the native execution engine in an environment, notebook or Spark job definition; unsupported features fall back to the default engine. Source: Native engine, "When to use the native execution engine"; Native engine, "Existing limitations".
- `std-eng-05` Ask: do Spark jobs in the workspace reach a storage account through a managed private endpoint, which then needs separate endpoints for Blob and DFS under the native execution engine, even for one account? [flag] Applies to: enabling the native execution engine in a workspace that may have managed private endpoints to storage accounts. Source: Native engine, "Other considerations and limitations".

Note: the development page says to put %%configure in the first cell and that it takes effect as the first executed cell, then says that, if you execute it as the first cell, its changes don't take effect unless the session restarts; the page doesn't reconcile the two. Source: Spark development, "Scenario: Customize session configuration in the Notebook".

Note: the monitoring page says to standardize settings at the environment level and use session overrides sparingly for debugging, while it also advises configuring through code and says that %%configure applies at session level; the development page describes %%configure for an interactive phase and, with parameters or a variable library, for a pipeline phase; the pages do not reconcile the debugging use of session overrides with these uses of %%configure. Source: Spark monitoring, "Configuration hierarchy"; Spark monitoring, "The %%configure magic command"; Spark development, "Scenario: Customize session configuration in the Notebook".

Note: the monitoring page lists user-defined functions and ANSI SQL mode as unsupported by the native execution engine, says it doesn't accelerate CSV, and gives its round() and collect_list() differences without a runtime, while the native engine page says it now supports Python and Scala UDFs and CSV, supports ANSI mode on Runtime 2.0, and ties the round() and collect_list() items to Runtime 1.3. Source: Spark monitoring, "Limitations of NEE"; Spark monitoring, "UDF best practices"; Native engine, "Existing limitations"; Native engine, "Other considerations and limitations".

Note: the native engine page says that using the engine during the preview phase needs specific configurations and that mechanisms to enable it at tenant, workspace and environment levels, integrated with the UI, are under active development, yet it also describes an environment-level setting; whether the engine is still in preview is not clear from the page. Source: Native engine, "Enable the native execution engine"; Native engine, "Control on the query level".

## Notebook code

- `std-eng-06` Does new Spark notebook code avoid driver-heavy operations such as collect(), countByKey() or a large toPandas(), and, if one is unavoidable, increase the driver size and benchmark? [review] Applies to: a new or changed notebook. Source: Spark monitoring, "Common OOM patterns".

## Lakehouse tables: layout and maintenance

- `std-eng-07` For a Spark-written table, is V-order enabled when it is primarily consumed through Power BI Direct Lake, and not solely for Spark performance, given that new workspaces have it off by default? [review] Applies to: a Spark write step or table property for a lakehouse table. Source: Table maintenance, "Apply consumer-specific optimization"; Spark monitoring, "V-order"; V-order, "Control V-order writes".
- `std-eng-08` Where the change targets Runtime 1.3 or later, is the setting spark.sql.parquet.vorder.enable, which the page says is removed there, absent from the code? [gate] Applies to: a notebook, Spark job definition or environment that sets V-order. Source: V-order, "Control V-order writes".

Note: the monitoring page lists about 10% better read performance from V-order for the SQL analytics endpoint and warehouse and says to enable it if read-heavy, while the table maintenance and SQL endpoint pages advise against enabling it solely, or by default, for the endpoint and name Power BI Direct Lake as its main beneficiary. Source: Spark monitoring, "V-order"; Table maintenance, "Apply consumer-specific optimization"; SQL endpoint, "Optimizing lakehouse tables for querying the SQL analytics endpoint".

Note: the V-order page says that the read-heavy resource profile for Spark automatically enables V-order, while the monitoring page lists V-order as enabled only in the read-heavy profile for Power BI and gives the Spark profile no V-order setting. Source: V-order, "Control V-order writes"; Spark monitoring, "Resource profiles".

Note: the V-order page says writes might take longer with V-order, often around 15% on average, while the monitoring page gives 15 to 33% slower writes for Spark. Source: V-order, "What is V-order?"; Spark monitoring, "V-order".

- `std-eng-09` Does each lakehouse table that the change writes have an explicit maintenance plan, scheduled separately where a Copy activity or Dataflow Gen2 writes it, since even append-only workloads can accumulate small files? [review] Applies to: a new or changed writer of a lakehouse table. Source: Table maintenance, "Optimize Lakehouse tables"; Table maintenance, "Use the Spark runtime defaults".
- `std-eng-10` For a Spark-written table, does the change enable auto compaction, which the monitoring page lists as off by default, or schedule OPTIMIZE separately where a strict write-latency requirement rules out synchronous compaction? [review] Applies to: a Spark-written lakehouse table. Source: Table maintenance, "Prevent and compact small files"; Spark monitoring, "Quick reference: key Spark configurations".
- `std-eng-11` If the change shortens a VACUUM retention period, does it first weigh time-travel requirements and concurrent readers or writers, since early file removal can make needed table versions unavailable? [review] Applies to: a vacuum or table maintenance step; the default retention rule is in std-arc-17. Source: Table maintenance, "Prevent and compact small files".
- `std-eng-12` On Runtime 2.0 or later, does a Spark-written table keep adaptive target file size, which picks 128 MB to 1 GB per table, and avoid a static target or arbitrary row limit? [review] Applies to: a Spark write or table setting for a lakehouse table; Runtime 1.3 has it opt-in (see also std-arc-06). Source: Table maintenance, "Use the Spark runtime defaults"; SQL endpoint, "Optimizing lakehouse tables for querying the SQL analytics endpoint".
- `std-eng-13` If the change partitions a lakehouse table, does it name a justifying requirement and, where the SQL analytics endpoint reads it, avoid high-cardinality columns, aiming for partitions near 1 GB or more? [review] Applies to: a partitioned lakehouse table; the page's example of a justifying requirement is isolating concurrent writers (see also std-arc-07). Source: Table maintenance, "Organize data for file skipping"; SQL endpoint, "Partition size considerations".
- `std-eng-14` If the change adds another table for a different engine, does it give an independent purpose, such as a changed grain, different security or retention, or a measured layout benefit that outweighs its costs? [review] Applies to: a new table that holds the same data as an existing table (see also std-cost-02). Source: Table maintenance, "When to create another table".

Note: the monitoring page lists adaptive target file size as not enabled by default, though recommended for most workloads, while the table maintenance and SQL endpoint pages say that Runtime 2.0 or later enables it by default and that Runtime 1.3 has it opt-in; the monitoring page gives no runtime for its default. Source: Spark monitoring, "Adaptive target file size"; Spark monitoring, "Quick reference: key Spark configurations"; Table maintenance, "Use the Spark runtime defaults"; SQL endpoint, "Optimizing lakehouse tables for querying the SQL analytics endpoint".

Note: the monitoring page gives row groups of 1 to 2 million rows beside its file size target, while the table maintenance page says Power BI Direct Lake generally performs best with row groups of 1 million to 16 million rows; neither page reconciles the two ranges. Source: Spark monitoring, "File size tuning"; Table maintenance, "Power BI Direct Lake".

## SQL analytics endpoint

- `std-eng-15` Does a step querying a lakehouse table through the SQL analytics endpoint right after a write allow for sync lag, normally under one minute but variable, for example with an on-demand metadata sync? [review] Applies to: a pipeline or notebook step that reads a lakehouse table through the SQL analytics endpoint after writing it. Source: SQL endpoint, "SQL analytics endpoint performance considerations"; SQL endpoint, "Guidance".

## Monitoring and production access

- `std-eng-16` Flag a change that gives developers direct access to a production workspace; guidance: privileged users such as support engineers retrieve the Spark logs and share them with developers. [flag] Applies to: a workspace role or access change for a production workspace that runs Spark jobs. Source: Spark monitoring, "The principle: least-privilege access"; Spark development, "Scenario: You have Fabric Spark Notebooks deployed in a production workspace, but you don't have direct access to it. The production support team reports that a Fabric Spark job failed in the production workspace, and you need to analyze the logs to troubleshoot the issue.".

## Dataflow Gen2

- `std-eng-17` In a Dataflow Gen2 that uses Fast Copy, are transformations that don't fold to the source kept in a separate query, since combining them with Fast Copy can disable it? [review] Applies to: a Dataflow Gen2 query that moves data with Fast Copy and also transforms it. Source: Dataflow performance, "Consideration 1: Improve data movement with Fast Copy"; Dataflow performance, "Consideration 3: Optimize staging-to-Lakehouse data movement for a Lakehouse destination".
- `std-eng-18` If a Dataflow Gen2 filters on a parameter to limit design-time previews, does the value used for runs include the full dataset where the run needs all of it? [review] Applies to: a Dataflow Gen2 with a parameter filter, for example on a date range or IDs. Source: Dataflow performance, "Consideration 4: Large data previews during design-time".

Note: the Dataflow Gen2 page suggests incremental refresh for a large, frequently updated transactional dataset, while the table maintenance page says a Dataflow Gen2 lakehouse destination that uses incremental refresh doesn't support OPTIMIZE or REORG TABLE; neither page says how such a table is kept compacted. Source: Dataflow performance, "Consideration 6: Optimizing refresh time for large transactional datasets using incremental refresh"; Table maintenance, "Use the Spark runtime defaults".
