# Second verification of the reference pack, slice Q2: well-architected.md and architecture-patterns.md (Gemini 4 Argon)

The reply as it came back, with the agent's own header removed. It judged every check and note of the two files cold against the text of the pages, after the corrections of the first verification. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

# Round 2 Verification Report — Slice Q2 (`well-architected.md` and `architecture-patterns.md`)

## 1. Header Paragraphs and Sources Tables

### `well-architected.md`
- **Verdict:** **SUPPORTED**
- **Verification:**
  - All seven entries in the `Sources` table (`WAF overview`, `WAF reliability`, `WAF security`, `WAF cost`, `WAF operations`, `WAF performance`, and `Greenfield`) match the `SOURCE:` URLs and `MS.DATE:` dates in `sources\`.
  - The header claim *"The security page says to use the Azure security baseline as a reference and a starting point for conversations, not as a checklist"* is directly supported by `azure-well-architected-microsoft-fabric-security.md`, `"Start with a baseline"`: `"don't treat it as a checklist; instead, treat it as a starting point"` (13 words; within 12 words: `"treat it as a starting point for conversations about your environment"`).
  - The safety framing (*"This file guides and never authorizes a change"* and *"A question about deleting, purging or pausing something is a question to ask about the change, never an instruction to do it"*) prevents an agent from acting on destructive or capacity-pausing questions.

### `architecture-patterns.md`
- **Verdict:** **PARTLY** (Severity: **Medium**)
- **Verification of header claims:**
  - All five entries in the `Sources` table (`Patterns`, `Greenfield`, `Medallion`, `CAF governance`, `CICD concepts`) match the `SOURCE:` URLs and `MS.DATE:` dates in `sources\`.
  - *"The medallion page calls medallion architecture the recommended design approach for Fabric"*: **SUPPORTED** by `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"# Understand medallion architecture for Fabric with OneLake"`: `"It's the recommended design approach for Fabric."` (7 words).
  - *"and the greenfield page says it can be adapted to your needs"*: **SUPPORTED** by `azure-architecture-example-scenario-data-greenfield-lakehouse-fabric.md`, `"Cold path for batch analytics"`: `"The medallion architecture is the standard approach, but you can adapt it"` (12 words).
  - **Special attention — *"each check keeps the conditions that its page gives"*:** **PARTLY (false for several checks as drafted).** While most checks preserve their source conditions, `std-arc-06` drops the explicit Spark condition on allowing smaller files in bronze, `std-arc-05` drops the `"two patterns to consider"` and `"business users"` qualifiers, and `std-arc-08` drops the batch-lakehouse scope condition from `"Cold path for batch analytics"`.
  - **Evidence:**
    - `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"File size"`: `"as long as you focus data modification and preparation on Spark."` (11 words).
    - `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"Deployment model"`: `"Here are two patterns to consider:"` (6 words).
  - **Suggested replacement line (for line 4 of `architecture-patterns.md`):**
    `These pages describe patterns and an example scenario, not rules: each check aims to keep the conditions its page gives, and a review check is a prompt for a reviewer, not a requirement. The medallion page calls medallion architecture the recommended design approach for Fabric, and the greenfield page says it can be adapted to your needs.`

---

## 2. Special Attention Areas Requested in Brief

1. **Dropped conditions (`"when"`, `"if"`, `"whenever possible"`, `"can"`, `"may"`, `"such as"`, `"for example"`):**
   - Found in `std-sec-03` (`"can run as part of pull request validation or CI pipelines"` turned into an unconditional PR-validation flag), `std-ops-04` (`"stores, pipelines, or models may require"` turned into an unconditional conjunction `"reconciling data across stores, pipelines and models"`), `std-perf-01` (`"can reduce contention. For example, you might separate..."` turned into an unconditional check), `std-cost-04` (`"Consider these strategies: ... Automate tasks..."` turned into an unconditional data-upkeep check), `std-perf-05` (`"techniques such as..."` turned into a closed list), `std-arc-06` (dropped `"as long as you focus data modification and preparation on Spark"`), and `std-arc-05` (dropped `"Here are two patterns to consider"` and `"business users"`).
2. **Scope in `"Applies to"`:**
   - Found in `std-arc-08` (`Applies to: a new transformation step` generalizes batch lakehouse transformations from `"Cold path for batch analytics"` across all transformations, colliding with `std-arc-09` and real-time transformations), `std-cost-04` (`Applies to: a new table or dataset` does not fit `"trimming log retention"` in the check), `std-cost-01` (`Applies to: a table, cache or log retention setting` includes log retention, which is not in the cited sections), `std-perf-05` (`Applies to: a semantic model or report` includes reports for model-level refresh/folding/aggregation settings), and `std-arc-07` (`Applies to: a new silver or gold table` omits a new bronze table despite carrying the bronze partitioning check).
3. **Gen2 / Amazon / Google wording of `std-arc-03`:**
   - **Verdict: SUPPORTED.** Both `Medallion, "Tables and files"` and `Medallion, "Deployment model"` state: `"If the source data is from OneLake, Azure Data Lake Store Gen2 (ADLS Gen2), Amazon S3, or Google, create a shortcut in the bronze layer instead of copying the data across."` `std-arc-03` writes `"For bronze data whose source is OneLake, ADLS Gen2, Google or the Amazon store that the page names"`, preserving the condition and complying with exposure rule (b) for `"Amazon S3"`.
4. **Pattern numbers in `std-arc-12` and `std-arc-13`:**
   - **Verdict: SUPPORTED.** Both checks replace the raw pattern numbers (`Pattern 1`, `Pattern 2`, `Pattern 3`) with self-contained descriptions that match `Patterns, "Operational Excellence"` and `Patterns, "Pattern 1: Monolithic deployment"` verbatim in meaning:
     - `std-arc-12` maps `"pattern 1"` to `"a single-workspace pattern"` (`"Deployment pipelines require separate workspaces, so they aren't available in pattern 1"` and `"Pattern 1 provides no preproduction separation"`).
     - `std-arc-13` maps `"Pattern 3"` to `"environment-aligned workspaces with capacity-level isolation"` and `"Pattern 2"` to `"the pattern where all environments share one capacity, which suits functional validation"` (`"Pattern 2 supports separate development, testing, and production workspaces on one shared capacity, which suits functional validation but not production-like performance or resilience testing. Pattern 3 supports production-like preproduction validation through environment-aligned workspaces with capacity-level isolation"`).

---

## 3. Findings on Checks (Ranked by Impact: High to Low)

### High Impact

#### 1. `std-sec-03` (`well-architected.md`)
- **Verdict:** **MISLEADING, WRONG TAG, WRONG CITATION** (Severity: **High**)
- **Current line:**
  `- \`std-sec-03\` Flag a pull request that changes notebooks, pipelines or dependencies without static analysis, secret detection and dependency scanning in its validation; guidance: these can run during pull request validation or CI. [flag] Applies to: a pull request that changes notebooks, pipelines or dependencies. Source: WAF security, "Secure Development Lifecycle (SDL)".`
- **Why:**
  1. **MISLEADING (condition dropped / disjunction turned into conjunction):** The source says static analysis, secret detection, and dependency scanning *can* run as part of pull request validation *or* CI pipelines. Although the second clause notes `; guidance: these can run during pull request validation or CI`, the first clause unconditionally instructs an agent to flag any pull request that lacks all three scans in *pull request validation* (even if they run in CI pipelines instead, or if no dependencies exist).
  2. **WRONG TAG (`[flag]`):** The factory refuses and escalates `[flag]` items (reserved for security, permission, network, sensitivity-label, or tenant-setting changes). Applying `[flag]` to `a pull request that changes notebooks, pipelines or dependencies` would cause an agent to escalate ordinary notebook and pipeline PRs; CI/PR validation workflow checks belong under `[review]` (consistent with `std-del-03`).
  3. **WRONG CITATION:** `"Secure Development Lifecycle (SDL)"` names `"notebooks, pipelines, and reports"`, whereas `"notebooks, pipelines, dependencies"` comes from `"Security Testing"`, which is not cited.
- **Evidence:**
  - `azure-well-architected-microsoft-fabric-security.md`, `"Secure Development Lifecycle (SDL)"`: `"can run as part of pull request validation or CI pipelines."` (11 words) and `"track changes in notebooks, pipelines, and reports."` (7 words).
  - `azure-well-architected-microsoft-fabric-security.md`, `"Security Testing"`: `"including notebooks, pipelines, dependencies, and data access configurations."` (8 words).
- **Suggested replacement line (28 words in sentence):**
  `- \`std-sec-03\` Do pull request validation or CI pipelines run static analysis, secret detection and dependency scanning when notebooks, pipelines, reports or dependencies change? [review] Applies to: a pull request validation or CI workflow. Source: WAF security, "Secure Development Lifecycle (SDL)"; WAF security, "Security Testing".`

---

### Medium Impact

#### 2. `std-arc-06` (`architecture-patterns.md`)
- **Verdict:** **PARTLY / MISLEADING** (Severity: **Medium**)
- **Current line:**
  `- \`std-arc-06\` Do writes and maintenance aim for files of 128 MB to 1 GB, scaled to table size and consumption, with smaller files allowed in bronze and larger files and row groups in gold? [review] Applies to: a new Delta table or a table maintenance step. Source: Medallion, "File size".`
- **Why:**
  The cited section explicitly conditions using smaller files in the bronze layer on focusing data modification and preparation on Spark. `std-arc-06` drops that condition (`"with smaller files allowed in bronze"`), allowing smaller bronze files unconditionally even when non-Spark engines consume or prepare them.
- **Evidence:**
  - `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"File size"`: `"as long as you focus data modification and preparation on Spark."` (11 words).
- **Suggested replacement line (35 words in sentence):**
  `- \`std-arc-06\` Do writes and maintenance target files of 128 MB to 1 GB by table size and consumption, allowing smaller bronze files when Spark handles preparation and larger files and row groups in gold? [review] Applies to: a new Delta table or a table maintenance step. Source: Medallion, "File size".`

#### 3. `std-ops-04` (`well-architected.md`)
- **Verdict:** **MISLEADING** (Severity: **Medium**)
- **Current line:**
  `- \`std-ops-04\` Does the change say how it would be rolled back, given there is no one-click rollback, by redeploying from Git or a pipeline and reconciling data across stores, pipelines and models? [review] Applies to: a release or a change to a data item. Source: WAF operations, "Deploy changes safely".`
- **Why:**
  The cited section states that when rolling back, multiple data stores, pipelines, *or* models *may* require careful reconciliation. `std-ops-04` drops `"may"` and converts the disjunction (`"stores, pipelines, or models"`) into an unconditional conjunction (`"reconciling data across stores, pipelines and models"`), violating Truthfulness Rule 5.
- **Evidence:**
  - `azure-well-architected-microsoft-fabric-operational-excellence.md`, `"Deploy changes safely"`: `"Multiple data stores, pipelines, or models may require careful reconciliation"` (10 words).
- **Suggested replacement line (32 words in sentence):**
  `- \`std-ops-04\` Does the change say how it would be rolled back by redeploying from Git or a pipeline, and whether multiple data stores, pipelines or models may need reconciliation? [review] Applies to: a release or a change to a data item. Source: WAF operations, "Deploy changes safely".`

#### 4. `std-perf-01` (`well-architected.md`)
- **Verdict:** **MISLEADING** (Severity: **Medium**)
- **Current line:**
  `- \`std-perf-01\` For a larger solution, are data preparation, orchestration pipelines and presentation workloads separated across workspaces or capacities so that one layer cannot starve another? [review] Applies to: the workspace or capacity layout of a larger solution. Source: WAF performance, "Plan capacity intentionally".`
- **Why:**
  The cited section states that isolating architectural layers across workspaces or capacities *can* reduce contention and gives separating data preparation workloads, orchestration pipelines, and presentation workloads as an *example* (`"For example, you might separate..."`). `std-perf-01` drops both `"can"` and `"For example, you might"`, turning an example into a rule for every larger solution.
- **Evidence:**
  - `azure-well-architected-microsoft-fabric-performance-efficiency.md`, `"Plan capacity intentionally"`: `"isolating architectural layers across workspaces or capacities can reduce contention."` (10 words) and `"For example, you might separate data preparation workloads, orchestration pipelines"` (10 words).
- **Suggested replacement line (31 words in sentence):**
  `- \`std-perf-01\` For a larger solution where compute contention is a risk, consider isolating layers across workspaces or capacities, for example separating data preparation, orchestration pipelines and presentation workloads. [review] Applies to: the workspace or capacity layout of a larger solution. Source: WAF performance, "Plan capacity intentionally".`

#### 5. `std-cost-04` (`well-architected.md`)
- **Verdict:** **PARTLY** (Severity: **Medium**)
- **Current line:**
  `- \`std-cost-04\` Does the change say how new data will be kept up, for example by Delta table optimization, purging obsolete data, archiving datasets or trimming log retention? [review] Applies to: a new table or dataset. Source: WAF cost, "Reduce costs through automation".`
- **Why:**
  The cited section is about *automating* workload and storage operations as a strategy to consider (`"Consider these strategies: ... Automate tasks such as delta table optimization, purging obsolete data, archiving datasets, or reducing log retention to prevent waste"`). `std-cost-04` drops automation (`"Automate tasks..."`) and turns `"Consider these strategies"` into a requirement that every new table or dataset state `"how new data will be kept up"`. Furthermore, `"Applies to: a new table or dataset"` does not match `"trimming log retention"`.
- **Evidence:**
  - `azure-well-architected-microsoft-fabric-cost-optimization.md`, `"Reduce costs through automation"`: `"Automate tasks such as delta table optimization, purging obsolete data"` (10 words) and `"archiving datasets, or reducing log retention to prevent waste."` (9 words).
- **Suggested replacement line (27 words in sentence):**
  `- \`std-cost-04\` Does the design consider automating storage and workload maintenance, such as Delta table optimization, purging obsolete data, archiving datasets or reducing log retention? [review] Applies to: a table, dataset, log setting or maintenance automation. Source: WAF cost, "Reduce costs through automation".`

#### 6. `std-arc-08` (`architecture-patterns.md`)
- **Verdict:** **PARTLY** (Severity: **Medium**)
- **Current line:**
  `- \`std-arc-08\` Does the transformation tool match the team's preference: Spark notebooks for a code-first experience, dataflows for a low-code or no-code one? [review] Applies to: a new transformation step. Source: Greenfield, "Cold path for batch analytics".`
- **Why:**
  1. **Scope in `"Applies to"` exceeds the cited section:** `"Cold path for batch analytics"` compares Spark notebooks and dataflows specifically for batch lakehouse preparation/transformation in the greenfield scenario. Applying `std-arc-08` to any `"new transformation step"` ignores real-time transformations in eventstreams/KQL (`"Hot path for real-time analytics"` on the same page) and SQL materialized lake views (`std-arc-09`).
  2. **Missing `Ask:` for team preference:** Whether a tool matches `"the team's preference"` requires tenant/team knowledge unless stated in the PR.
- **Evidence:**
  - `azure-architecture-example-scenario-data-greenfield-lakehouse-fabric.md`, `"Cold path for batch analytics"`: `"You can prepare and transform data in two ways."` (9 words) and `"If you prefer a code-first experience, use Spark notebooks."` (9 words).
- **Suggested replacement line (26 words in sentence):**
  `- \`std-arc-08\` Ask: for batch lakehouse transformations, does the tool match the team's preference between Spark notebooks for code-first work and dataflows for low-code or no-code work? [review] Applies to: a new batch lakehouse transformation step. Source: Greenfield, "Cold path for batch analytics".`

---

### Low Impact

#### 7. `std-perf-05` (`well-architected.md`)
- **Verdict:** **MISLEADING** (Severity: **Low**)
- **Current line:**
  `- \`std-perf-05\` Does a Power BI semantic model use incremental refresh, query folding or aggregation tables to reduce the data that must be refreshed or queried? [review] Applies to: a semantic model or report. Source: WAF performance, "Optimize performance".`
- **Why:**
  The source presents incremental refresh, query folding, and aggregation tables as examples (`"techniques such as..."`). Dropping `"such as"` turns examples into a closed requirement that every semantic model use one of those three (which is misleading for Direct Lake semantic models in `std-arc-11` where import refresh and Power Query folding do not apply). Also, `"Applies to: a semantic model or report"` includes reports, whereas these are semantic-model techniques.
- **Evidence:**
  - `azure-well-architected-microsoft-fabric-performance-efficiency.md`, `"Optimize performance"`: `"techniques such as incremental refresh, query folding, and aggregation tables"` (10 words).
- **Suggested replacement line (26 words in sentence):**
  `- \`std-perf-05\` Where applicable, does a Power BI semantic model use techniques such as incremental refresh, query folding or aggregation tables to reduce data refreshed or queried? [review] Applies to: a semantic model. Source: WAF performance, "Optimize performance".`

#### 8. `std-arc-05` (`architecture-patterns.md`)
- **Verdict:** **MISLEADING** (Severity: **Low**)
- **Current line:**
  `- \`std-arc-05\` Does the change say whether gold is a lakehouse read through its SQL analytics endpoint or a warehouse read through its warehouse endpoint, chosen by preference and team expertise? [review] Applies to: a new gold layer. Source: Medallion, "Deployment model".`
- **Why:**
  The cited section states that you can use `"lakehouses (one for each layer), a warehouse, or combination of both"` based on preference and team expertise, and then lists `"two patterns to consider"` for how `"business users access data"`. `std-arc-05` drops `"two patterns to consider"` and `"business users"`, turning two example patterns for business-user SQL access into an exhaustive binary requirement on how a gold layer is read.
- **Evidence:**
  - `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"Deployment model"`: `"Here are two patterns to consider:"` (6 words) and `"business users access data by using the SQL analytics endpoint."` (10 words).
- **Suggested replacement line (31 words in sentence):**
  `- \`std-arc-05\` For a new gold layer, is the choice between a lakehouse (with its SQL analytics endpoint for business users) and a warehouse based on preference and team expertise? [review] Applies to: a new gold layer. Source: Medallion, "Deployment model".`

#### 9. `std-arc-07` (`architecture-patterns.md`)
- **Verdict:** **PARTLY** (Severity: **Low**)
- **Current line:**
  `- \`std-arc-07\` For new silver and gold tables, is Liquid Clustering used instead of partitioning, given that partitioning in bronze is acceptable but discouraged for new implementations? [review] Applies to: a new silver or gold table. Source: Medallion, "Table partitions and clustering".`
- **Why:**
  The check sentence includes the page's rule on bronze partitioning (`"partitioning in bronze is acceptable but discouraged for new implementations"`), but `"Applies to: a new silver or gold table"` excludes bronze tables, so an agent filtering by `"Applies to"` will not run this check when a new partitioned bronze table is added.
- **Evidence:**
  - `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"Table partitions and clustering"`: `"In the bronze layer, partitioning is acceptable but discouraged"` (9 words).
- **Suggested replacement line (25 words in sentence):**
  `- \`std-arc-07\` For new silver and gold tables, is Liquid Clustering used instead of partitioning, and is partitioning avoided for new bronze implementations where discouraged? [review] Applies to: a new bronze, silver or gold table. Source: Medallion, "Table partitions and clustering".`

#### 10. `std-cost-01` (`well-architected.md`)
- **Verdict:** **PARTLY / WRONG CITATION** (Severity: **Low**)
- **Current line:**
  `- \`std-cost-01\` Does the change set a retention window or keep cached results, and does it weigh that larger retention windows raise monthly storage cost? [review] Applies to: a table, cache or log retention setting. Source: WAF cost, "Identify key cost drivers"; WAF cost, "Monitor costs and implement governance".`
- **Why:**
  `"Applies to: a table, cache or log retention setting"` includes `"log retention setting"`, which does not appear in either `"Identify key cost drivers"` or `"Monitor costs and implement governance"` (on `WAF cost`, log retention is mentioned only in `"Reduce costs through automation"`).
- **Evidence:**
  - `azure-well-architected-microsoft-fabric-cost-optimization.md`, `"Identify key cost drivers"`: `"Long data retention periods, cached query results, or soft-deleted data"` (10 words).
  - `azure-well-architected-microsoft-fabric-cost-optimization.md`, `"Reduce costs through automation"`: `"archiving datasets, or reducing log retention to prevent waste."` (9 words).
- **Suggested replacement line (23 words in sentence):**
  `- \`std-cost-01\` Does the change set a retention window or keep cached results, and does it weigh that larger retention windows raise monthly storage cost? [review] Applies to: a table, dataset or cache retention setting. Source: WAF cost, "Identify key cost drivers"; WAF cost, "Monitor costs and implement governance".`

---

## 4. Verification of the 5 `Note:` Lines

### `well-architected.md` — Note 1 (Smoothing vs. off-peak scheduling)
- **Tension real?** **Yes.** There is a genuine tension between `WAF performance` (and `Greenfield, "Performance Efficiency"`) stating that smoothing removes the need to schedule heavy workloads off-peak and lets you schedule CPU-intensive activities at any time, and `Greenfield, "Cost Optimization"` advising scheduling noncritical tasks during off-peak times and staggering long-running jobs.
- **Both sides stated correctly?** **Yes.**
  - Side 1 (`azure-well-architected-microsoft-fabric-performance-efficiency.md`, `"Plan capacity intentionally"`): `"eliminates the need to schedule heavy workloads during off-peak hours."` (10 words).
  - Side 2a (`azure-architecture-example-scenario-data-greenfield-lakehouse-fabric.md`, `"Cost Optimization"`): `"schedule noncritical tasks during off-peak times to avoid spikes"` (9 words) and `"Schedule long-running jobs at staggered times based on resource availability"` (10 words).
  - Side 2b (`azure-architecture-example-scenario-data-greenfield-lakehouse-fabric.md`, `"Performance Efficiency"`): `"Both bursting and smoothing help... You can schedule these activities at any time."` (within 12 words: `"You can schedule these activities at any time."`).

### `well-architected.md` — Note 2 (Test capacity sizing)
- **Tension real?** **Yes.** `WAF operations` describes using smaller test capacities that are scaled up temporarily during load tests to control costs, whereas `WAF performance` states that test environments should ideally use the same capacity size as production.
- **Both sides stated correctly?** **Yes.**
  - Side 1 (`azure-well-architected-microsoft-fabric-operational-excellence.md`, `"Don't assume everything works"`): `"test capacities are often smaller than production and temporarily scaled up"` (11 words).
  - Side 2 (`azure-well-architected-microsoft-fabric-performance-efficiency.md`, `"Do performance testing"`): `"Ideally, testing environments should use the same capacity size, region"` (10 words).

### `architecture-patterns.md` — Note 1 (Bronze "no changes" vs. format conversion)
- **Tension real?** **Yes.** `"What is medallion architecture?"` states that bronze stores everything exactly as it arrives with no changes allowed, while `"Deployment model"` (and `"What is medallion architecture?"` for relational databases) recommends storing bronze data in its original format whenever possible, or using Parquet or Delta Lake, without reconciling whether converting to Parquet or Delta Lake counts as a change.
- **Both sides stated correctly?** **Yes.**
  - Side 1 (`fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"What is medallion architecture?"`): `"Bronze (Raw): Store everything exactly as it arrives. No changes are allowed."` (12 words).
  - Side 2 (`fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"Deployment model"`): `"store the data in its original format, or use Parquet or Delta"` (12 words) and `"Whenever possible, keep the data in its original format."` (9 words).

### `architecture-patterns.md` — Note 2 (Workspace boundaries across medallion layers)
- **Tension real?** **Yes.** The four cited pages give different criteria and layouts for placing medallion layers into workspaces without a single ranking rule across them.
- **All sides stated correctly?** **Yes.**
  - Side 1 (`fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"Deployment model"`): `"recommend that you create each lakehouse in its own, separate workspace."` (11 words).
  - Side 2 (`azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, `"2. Fabric data security"`): `"Don't create extra workspaces only to reproduce boundaries that item permissions"` (11 words).
  - Side 3 (`fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `"Fabric solutions"`): `"split the solution into a staging workspace and a presentation workspace."` (11 words).
  - Side 4 (`azure-architecture-data-guide-technology-choices/fabric-deployment-patterns.md`, `"Pattern 2: Multiple workspaces, single capacity"`): `"host the bronze and silver layers of a medallion architecture"` (10 words) and `"and host the gold layer in a separate workspace."` (9 words).

### `architecture-patterns.md` — Note 3 (Partitioned folder structure vs. Liquid Clustering / bronze partitioning)
- **Tension real?** **Yes.** Within a single paragraph of `"Table partitions and clustering"`, the page advises using a partitioned folder structure in each layer wherever applicable, and immediately thereafter discourages partitioning in bronze for new implementations and tells readers to use Liquid Clustering instead of partitioning for silver and gold.
- **Both sides stated correctly?** **Yes.**
  - Side 1 (`fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"Table partitions and clustering"`): `"When you store data in each layer, use a partitioned folder structure"` (12 words).
  - Side 2 (`fabric-onelake-onelake-medallion-lakehouse-architecture.md`, `"Table partitions and clustering"`): `"In the bronze layer, partitioning is acceptable but discouraged for new implementations."` (12 words) and `"For silver and gold layers, use Liquid Clustering instead of partitioning"` (11 words).

---

## CHECKED AND FINE

- **Fully supported check lines:** **34** (out of 44 checks across both files: 21 of 27 in `well-architected.md`, and 13 of 17 in `architecture-patterns.md`), plus all **5** `Note:` lines (39 supported check/Note lines in total).
- **Supported check IDs in `well-architected.md` (21):**
  `std-rel-01`, `std-rel-02`, `std-rel-03`, `std-rel-04`, `std-rel-05`, `std-rel-06`, `std-sec-01`, `std-sec-02`, `std-sec-04`, `std-sec-14`, `std-cost-02`, `std-cost-03`, `std-ops-01`, `std-ops-02`, `std-ops-03`, `std-ops-05`, `std-ops-06`, `std-ops-07`, `std-perf-02`, `std-perf-03`, `std-perf-04`.
- **Supported check IDs in `architecture-patterns.md` (13):**
  `std-arc-01`, `std-arc-02`, `std-arc-03`, `std-arc-04`, `std-arc-09`, `std-arc-10`, `std-arc-11`, `std-arc-12`, `std-arc-13`, `std-arc-14`, `std-arc-15`, `std-arc-16`, `std-arc-17`.
