# Third verification of the reference pack, every line, lens 3: from the page to the check (Grok 4.7)

The reply as it came back, with the agent's own header removed. It gave a verdict and a verbatim quote of the source for every check and every note (97 rows). A program then looked up each quote in the cited section of the cited page. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

std-rel-01 | S | retries don't cause duplicate writes or processing errors
std-rel-02 | S | Combine exponential backoff with alerting
std-rel-03 | S | pipelines can skip non-critical steps or use cached data
std-rel-04 | S | Mitigate these risks with caching, queuing, or backup sources
std-rel-05 | S | Direct chaos testing inside Fabric isn't possible
std-rel-06 | S | such as independent pipelines, datasets, and processing stages
std-sec-01 | S | Do not store secrets in notebooks, scripts, or pipelines
std-sec-02 | S | when alternatives exist
std-sec-03 | S | can run as part of pull request validation
std-sec-04 | S | Map them to teams, projects, or environments
std-sec-14 | P | through Azure key vault references or parameterization rules | Parameterization rules are stated for pipeline definitions, not notebooks or scripts.
std-cost-01 | S | Larger retention windows increase monthly storage cost
std-cost-02 | S | using shortcuts for in-place data sharing
std-cost-03 | S | prevent compute usage from growing unchecked
std-cost-04 | S | such as delta table optimization, purging obsolete data
std-ops-01 | S | Testing before promotion is non-negotiable
std-ops-02 | S | Validate schema changes or missing values
std-ops-03 | P | dedicated test workspaces and capacities that represent production | Drops dedicated test capacities that represent production.
std-ops-04 | S | may require careful reconciliation
std-ops-05 | S | automated approvals work well for non-production
std-ops-06 | S | Alerts must be meaningful, actionable, and escalated properly
std-ops-07 | S | can grow rapidly in busy workspaces
std-perf-01 | S | you might separate data preparation workloads
std-perf-02 | S | eliminates the need to schedule heavy workloads
std-perf-03 | S | Ideally, testing environments should use the same
std-perf-04 | S | benefit from well-defined partitions and parallel execution
std-perf-05 | S | techniques such as incremental refresh, query folding
note-wa-1 | S | schedule noncritical tasks during off-peak times
note-wa-2 | S | test capacities are often smaller than production
std-sec-05 | S | Assign workspace roles to Microsoft Entra security groups instead of individual users
std-sec-06 | S | so administrative privileges are activated only when required
std-sec-17 | S | Restrict workspace creation to admins to prevent sprawl
std-sec-07 | S | does not necessarily grant permission to query
std-sec-08 | S | shouldn't see the same records or tables
std-sec-09 | S | Don't create extra workspaces only to reproduce boundaries
note-sec-1 | S | that assignment grants access to everything inside the workspace
std-sec-10 | S | to securely connect to datasources behind private endpoints
std-sec-11 | S | now requires TLS 1.2 or later
std-sec-16 | P | When network security requirements apply across Fabric | Drops the case where requirements across Fabric should use tenant-level private links.
std-sec-12 | S | follow the data automatically from item to item
std-sec-15 | P | you may need workspace segmentation to separate supported | Drops that unsupported items may need workspace segmentation.
std-sec-13 | S | There are additional logging and monitoring options available
std-gov-01 | M | administrative privilege assignment to Microsoft Fabric tenant, capacities, and workspaces | Drops the scope to tenant, capacities, and workspaces, so any access change is that class.
std-gov-02 | S | changes that can increase cost or affect other data domains
std-gov-03 | S | should normally have automated failure alerts
std-gov-04 | S | capacity monitoring experience is currently in preview
std-gov-05 | S | it doesn't alone determine the release pattern
std-gov-06 | S | document the deployed version and the recovery process
std-gov-07 | S | An independent person or automated control should validate
std-gov-08 | S | when an owner is required for a data asset
std-gov-09 | S | usually subject to stricter governance requirements
std-del-01 | M | allows updates only through pull requests | Cited process is feature workspaces after definitions exist; Applies to any change.
std-del-02 | P | If your Git repository also needs to hold | Folder separation applies only when the repository also holds other files.
std-del-03 | P | A validation pipeline can run any time | A validation pipeline can run for Azure Pipelines, not every workflow.
note-del-1 | S | you can make direct updates to items in the dev workspace
std-del-04 | S | combines the item display name, a period, and the item type
std-del-05 | S | changing it can lead to unpredictable behavior
std-del-06 | P | something unique for that connected workspace | Drops uniqueness for that connected workspace.
std-del-07 | S | you must extend a notebook's item definition
note-del-2 | S | Never modify a logicalId value
std-del-08 | S | the recommended practice is to isolate environments
std-del-09 | M | It's best not to overload it with queries | Not loaded is stronger than not overload, and the development database should stay small.
std-del-10 | P | you probably want all BI creators | Drops that BI creators may still need pipeline access.
note-del-3 | S | can share a single capacity, which can be paused
std-del-11 | S | avoid hardcoding configuration settings that change across environments
std-del-12 | S | such as pipelines and shortcuts in a lakehouse
std-del-13 | S | set production deployment rules for data sources and parameters
std-del-14 | S | makes it possible to dynamically update environment-specific settings
std-del-20 | S | doesn't contain anything to indicate which value set is active
note-del-4 | M | you can configure parameter rules | Cited lifecycle heading states parameter rules, not deployment rules.
std-del-15 | S | Never commit files with sensitive credentials to Git
std-del-16 | S | upload the changes first to a dev or test environment
std-del-17 | P | using the SqlPackage and Data-tier Application Framework | Drops Data-tier Application Framework tooling beside SqlPackage.
std-del-18 | P | or another item type | Cited section also allows another item type, not only a pipeline or notebook.
std-del-19 | S | Execute API calls as a service principal whenever possible
std-del-21 | S | such as notebooks, pipelines, copy jobs, user-defined functions
std-del-22 | S | It's not possible to update the app through the UI
std-arc-01 | S | as it's transformed and refined
std-arc-02 | P | No changes are allowed | Drops that bronze allows no changes.
std-arc-03 | S | create a shortcut in the bronze layer instead of copying
std-arc-04 | P | When the data source is a relational database | Drops that Delta is a good bronze choice for a relational source.
std-arc-05 | S | based on your preference and the expertise of your team
std-arc-06 | S | as long as you focus data modification and preparation on Spark
std-arc-07 | S | partitioning is acceptable but discouraged for new implementations
std-arc-17 | S | you can't delete historical data within the last seven days
note-arc-1 | S | Whenever possible, keep the data in its original format
note-arc-2 | S | create each lakehouse in its own, separate workspace
note-arc-3 | S | use a partitioned folder structure wherever applicable
std-arc-08 | S | If you prefer a code-first experience, use Spark notebooks
std-arc-09 | S | you can define materialized lake views
std-arc-10 | S | A SQL analytics endpoint is read only
std-arc-11 | S | example scenarios can trigger a DirectQuery fallback
std-arc-12 | S | Deployment pipelines require separate workspaces
std-arc-13 | S | which suits functional validation but not production-like
std-arc-14 | S | can degrade interactive query performance for other users
std-arc-15 | S | all workloads on that capacity become unavailable
std-arc-16 | S | items that rely on shortcuts might fail

## FINDINGS

No High findings. No check reverses a page into a forbidden action.

**Medium**

1. std-arc-02. Medallion, "What is medallion architecture?": "No changes are allowed." The check keeps "exactly as it arrives" but drops the ban, so a bronze step that changes data can pass.
`- std-arc-02` Does each step sit in the right layer: bronze stores everything exactly as it arrives and allows no changes, silver fixes errors, standardizes formats and removes duplicates, and gold organizes data for reports and dashboards? [review] Applies to: a notebook, pipeline or dataflow that moves data between layers. Source: Medallion, "What is medallion architecture?".

2. std-del-01. CICD concepts, "Feature workspaces": "allows updates only through pull requests" only after the one-time Commit to Git. Applies to any item-definition change, which note-del-1 says the simplest scenario does not require.
`- std-del-01` When feature workspaces are in use, does the change arrive by pull request, with updates to the integration branch allowed only through pull requests after the initial item definitions exist? [review] Applies to: a change under the feature-workspace process. Source: CICD concepts, "Feature workspaces"; CICD concepts, "Continuous integration development process".

3. std-sec-16. CAF governance, "3. Fabric networking": "When network security requirements apply across Fabric". The check flags tenant-level links and never says that case should use them.
`- std-sec-16` Flag a tenant-level private link; guidance: use workspace-level links where supported for selected workspaces, use tenant-level links when requirements apply across Fabric, and assess the operational effect first. [flag] Applies to: a private link or network access setting for Fabric. Source: CAF governance, "3. Fabric networking".

4. std-gov-01. Baseline, "Asset Management" (control "Ensure security of asset lifecycle management"): "administrative privilege assignment to Microsoft Fabric tenant, capacities, and workspaces". The check treats every access change as that class.
`- std-gov-01` Flag a change to access, data sensitivity, network configuration, or administrative privilege assignment on a tenant, capacity, or workspace as a potentially high-impact modification that security policy should cover. [flag] Applies to: access, sensitivity, network, or admin privilege on a tenant, capacity, or workspace. Source: Baseline, "Asset Management" (control "Ensure security of asset lifecycle management").

5. std-del-09. Lifecycle, "Connect different stages to different databases": "It's best not to overload it with queries". "Not loaded" is stronger, and the development database should stay relatively small.
`- std-del-09` Do development and test semantic models use separate databases so their queries do not overload production, with a small development database and a test database as similar to production as possible when simulating real use? [review] Applies to: a data source connection of a semantic model promoted through stages. Source: Lifecycle, "Connect different stages to different databases"; Lifecycle, "Use deployment rules with a real-life data source".

6. std-del-18. CICD concepts, "Data orchestration": "or another item type". A dataflow or other single top-level item would fail a check the page allows.
`- std-del-18` Does a lakehouse solution expose one top-level pipeline, notebook, or other ETL item that populates all lakehouses, with scheduled refresh jobs for notebooks and pipelines kept in .schedules files? [review] Applies to: a lakehouse solution, or a scheduled refresh job of a notebook or pipeline. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".

7. std-ops-03. WAF operations, "Don't assume everything works": "dedicated test workspaces and capacities that represent production". A representative workspace on a non-representative capacity can pass.
`- std-ops-03` Do tests run in dedicated test workspaces and capacities that represent production, using sample or anonymized data sources? [review] Applies to: a test or validation environment. Source: WAF operations, "Don't assume everything works".

8. std-del-10. Lifecycle, "Manage who can deploy to production": "you probably want all BI creators" to have pipeline access. Flagging every pipeline permission can block that.
`- std-del-10` Flag who can deploy to production; guidance: limit that operation to specific people through production workspace permissions, while other users can have the viewer role and BI creators may still need pipeline access. [flag] Applies to: a workspace role or a pipeline permission. Source: Lifecycle, "Manage who can deploy to production".

9. std-del-02. CICD concepts, "Git folder settings": "If your Git repository also needs to hold" other files. The check asks this of every Git connection.
`- std-del-02` If the repository also holds workflow files, does a Git folder setting separate item definitions, and does each workspace of a multi-workspace solution use its own folder on one shared branch? [review] Applies to: a Git connection or repository layout. Source: CICD concepts, "Git folder settings"; CICD concepts, "Continuous integration development process".

10. std-arc-04. Medallion, "What is medallion architecture?": "When the data source is a relational database, Delta tables are a good choice" for bronze. The check omits that exception.
`- std-arc-04` Are silver and gold stored as Delta tables, and bronze kept in its original format whenever possible, or else as Parquet or Delta Lake, with Delta a good bronze choice for a relational source? [review] Applies to: a new table or a write step. Source: Medallion, "What is medallion architecture?"; Medallion, "Deployment model".

11. std-sec-15. WAF security, "Data encryption": "you may need workspace segmentation". The support gap is stated; the consequence is not.
`- std-sec-15` Flag a workspace customer-managed key; guidance: not every artifact supports it, unsupported items may need another workspace, and data stays inaccessible until a disabled or deleted key is restored. [flag] Applies to: an encryption or key setting for a workspace. Source: WAF security, "Data encryption".

12. std-del-06. Lifecycle, "Duplicate an item in a Git repository": "something unique for that connected workspace". Any unique value is not what the page says.
`- std-del-06` When an item is duplicated in Git, is the whole folder copied, with a logicalId unique for that connected workspace, a new display name, and dependencies updated where needed? [review] Applies to: a copied item. Source: Lifecycle, "Duplicate an item in a Git repository".

**Low**

13. std-del-03. CICD concepts, "Azure Pipelines workflows": "A validation pipeline can run". Permissive, and stated for Azure Pipelines, not every workflow file.
`- std-del-03` For an Azure Pipelines workflow, is there a validation pipeline that can check files, run tests, or validate item definitions before approval, kept separate from release? [review] Applies to: an Azure Pipelines workflow definition. Source: CICD concepts, "Azure Pipelines workflows".

14. std-sec-14. WAF security, "Secure Development Lifecycle (SDL)": "through Azure key vault references or parameterization rules" is the pipeline alternative. Key Vault retrieval covers notebooks and scripts.
`- std-sec-14` Flag a credential the change introduces; guidance: retrieve it from Azure Key Vault at run time, and for a pipeline pass it by key vault reference or parameterization rule. [flag] Applies to: a notebook, script or pipeline that needs a credential. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)".

15. std-del-17. CICD concepts, "Data orchestration": "using the SqlPackage and Data-tier Application Framework". SqlPackage alone is incomplete.
`- std-del-17` Are lakehouse schema changes shipped as notebook logic that is also run in each target workspace, and warehouse schema changes managed with SqlPackage and Data-tier Application Framework tooling? [review] Applies to: a table schema change. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".

16. note-del-4. Lifecycle, "Use parameters for configurations that will change between stages": "you can configure parameter rules". Deployment rules are on the same page, not in that heading. The tension itself is real.
Note: the lifecycle page uses parameter rules, and in other sections deployment rules, for stage-specific settings, while the concepts page says deployment rules remain supported but variable libraries should usually be the first choice. Source: Lifecycle, "Use parameters for configurations that will change between stages"; Lifecycle, "Use deployment rules with a real-life data source"; CICD concepts, "Deployment pipelines".

## HEADERS

No header or Sources-table claim exceeds the pages. Baseline version 1.0 may be outdated; the baseline is a starting point, not a checklist; the roadmap is not a comprehensive governance reference; not every CI/CD recommendation applies; medallion is the recommended approach and can be adapted. Those match the cited pages.

## CONFLICTS

std-del-01 and note-del-1 cannot be followed together without a rule the pack does not give. The check applies a pull-request rule to any item-definition change. The note correctly says the simplest deployment-pipeline scenario uses direct commits. The note does not limit the check.

Workspace-split tension (std-sec-09, note-sec-1, note-arc-2) is real and stated correctly. The notes say each page has its own criteria and none ranks them, so an agent is not forced to pick one absolute rule.

note-wa-1 and std-perf-02 fit: the check asks whether off-peak scheduling is needed; the note adds the greenfield advice. note-wa-2 and std-perf-03 fit because the check keeps "ideally". std-del-05 and std-del-06, with note-del-2, give a practical split the pages do not explain. That is not a conflict between the checks.

## DANGER

No. Flag checks start with Flag and name guidance; they do not tell the agent to assign a role, create a private endpoint, set a label, or change a tenant or capacity setting. Pause, purge, and VACUUM appear only inside review questions, not as instructions. No text instructs an agent to do something other than apply a check.
