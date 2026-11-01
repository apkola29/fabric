# Third verification of the reference pack, every line, lens 2: tags, citations and the cited section as a whole (Gemini 4 Argon)

The reply as it came back, with the agent's own header removed. It gave a verdict and a verbatim quote of the source for every check and every note (97 rows). A program then looked up each quote in the cited section of the cited page. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

### Verification Table (Lens 2: Gemini 4 Argon — File Order: `well-architected.md`, `security-and-governance.md`, `architecture-patterns.md`, `delivery-and-lifecycle.md`)

std-rel-01 | S | Make sure retries don't cause duplicate writes or processing errors.
std-rel-02 | S | Combine exponential backoff with alerting to recover gracefully from transient failures.
std-rel-03 | S | For example, pipelines can skip non-critical steps or use cached data
std-rel-04 | S | Mitigate these risks with caching, queuing, or backup sources.
std-rel-05 | S | Simulate adverse conditions: break connectivity to data sources, inject load
std-rel-06 | S | smaller components such as independent pipelines, datasets, and processing stages.
std-sec-01 | S | Do not store secrets in notebooks, scripts, or pipelines.
std-sec-02 | S | Disable basic authentication for data sources when alternatives exist.
std-sec-03 | S | Static analysis, secret detection, and dependency scanning can run
std-sec-04 | S | Adding more workspaces and capacities increases operational complexity and management overhead.
std-sec-14 | S | through Azure key vault references or parameterization rules rather than embedding
std-cost-01 | S | Larger retention windows increase monthly storage cost
std-cost-02 | S | using shortcuts for in-place data sharing, minimizing unnecessary data movement
std-cost-03 | S | Define reasonable scaling limits to prevent compute usage from growing unchecked.
std-cost-04 | S | purging obsolete data, archiving datasets, or reducing log retention to prevent
std-ops-01 | S | Unit tests, integration checks, data validation, and business verification
std-ops-02 | S | Validate schema changes or missing values
std-ops-03 | S | Test environments should use sample or anonymized data sources to avoid
std-ops-04 | S | Multiple data stores, pipelines, or models may require careful reconciliation
std-ops-05 | S | Pipelines should enforce approvals for production deployments and capture logs
std-ops-06 | M | Fabric also provides built-in notifications for job failures, such as | Turns optional built-in failure notifications and general alert design advice into a requirement for every new scheduled job, pipeline or refresh.
std-ops-07 | S | enable them selectively or temporarily when investigating performance issues.
std-perf-01 | S | isolating architectural layers across workspaces or capacities can reduce contention.
std-perf-02 | S | eliminates the need to schedule heavy workloads during off-peak hours.
std-perf-03 | S | Ideally, testing environments should use the same capacity size, region,
std-perf-04 | S | when filters and aggregations reduce the amount of data processed.
std-perf-05 | S | techniques such as incremental refresh, query folding, and aggregation tables reduce
note-wa-1 | S | schedule noncritical tasks during off-peak times to avoid spikes in CU
note-wa-2 | S | test capacities are often smaller than production and temporarily scaled up
std-sec-05 | S | Assign workspace roles to Microsoft Entra security groups instead of individual
std-sec-06 | S | Exercise caution and care when delegating settings to capacity and workspace
std-sec-17 | S | Restrict workspace creation to admins to prevent sprawl and misconfigurations.
std-sec-07 | S | Sharing an item does not necessarily grant permission to query
std-sec-08 | S | several audiences use the same data product but shouldn't see
std-sec-09 | S | only to reproduce boundaries that item permissions or OneLake security can
note-sec-1 | S | that assignment grants access to everything inside the workspace.
std-sec-10 | P | provide private connectivity for supported Fabric workloads and supported data sources. | Omits the condition in CAF governance "3. Fabric networking" that managed private endpoints only apply to supported workloads and data sources.
std-sec-11 | S | Outbound Fabric communication to customer-owned infrastructure now requires TLS 1.2 or
std-sec-16 | S | use workspace-level private links where the required Fabric capabilities support them.
std-sec-12 | S | classify items that contain sensitive data using these same sensitivity labels.
std-sec-15 | S | Note that not all Fabric artifacts currently support CMK, so you
std-sec-13 | S | additional logging and monitoring options available and configurable at workspace level
std-gov-01 | S | changes to access, data sensitivity level, network configuration, and administrative privilege
std-gov-02 | S | not receive unrestricted authority to resize the Fabric capacity, change overage
std-gov-03 | S | business-critical data product should normally have automated failure alerts and
std-gov-04 | S | currently in preview, so the organization should not depend on it
std-gov-05 | S | select a deployment pattern from the potential business effect of a
std-gov-06 | S | data domain should document the deployed version and the recovery process.
std-gov-07 | P | An approved alternative should apply when a Fabric item does not | Omits the same-section exception that an approved alternative applies when a Fabric item does not support Git integration or deployment pipelines.
std-gov-08 | S | Specifies when an owner is required for a data asset
std-gov-09 | S | Critical data is usually subject to stricter governance requirements.
std-arc-01 | S | separated in its own lakehouse or warehouse in OneLake, with data
std-arc-02 | S | Fix errors, standardize formats, and remove duplicates.
std-arc-03 | S | create a shortcut in the bronze layer instead of copying
std-arc-04 | S | Whenever possible, keep the data in its original format.
std-arc-05 | S | based on your preference and the expertise of your team.
std-arc-06 | S | target file sizes between 128 MB and 1 GB, depending on
std-arc-07 | S | In the bronze layer, partitioning is acceptable but discouraged for new
std-arc-17 | S | by default you can't delete historical data within the last seven
note-arc-1 | S | Store everything exactly as it arrives. No changes are allowed.
note-arc-2 | S | we recommend that you create each lakehouse in its own, separate
note-arc-3 | S | use a partitioned folder structure wherever applicable.
std-arc-08 | S | If you prefer a code-first experience, use Spark notebooks.
std-arc-09 | S | Define data transformations using SQL statements rather than building manual pipelines
std-arc-10 | S | A SQL analytics endpoint is read only. To modify data, switch
std-arc-11 | S | The following example scenarios can trigger a DirectQuery fallback:
std-arc-12 | S | Deployment pipelines require separate workspaces, so they aren't available in pattern
std-arc-13 | S | suits functional validation but not production-like performance or resilience testing.
std-arc-14 | S | An expensive query or data pipeline can degrade interactive query performance
std-arc-15 | S | Consider the reliability effect before you pause a capacity that supports
std-arc-16 | S | If the external source is unavailable, items that rely on shortcuts
std-del-01 | M | a branch policy that allows updates only through pull requests. | Applies feature-branch workflow to any item change despite the simplest direct-commit dev option, and checks remote branch policy without Ask:.
std-del-02 | S | synchronize both workspaces to the same Git branch in the same
std-del-03 | M | A validation pipeline can run any time a developer creates | Turns a permissive statement ("can run") in "Azure Pipelines workflows" into an unqualified expectation for any workflow definition in the repository.
note-del-1 | S | don't directly update items or run Commit to Git operations
std-del-04 | S | combines the item display name, a period, and the item type
std-del-05 | S | Never modify a logicalId value: Fabric doesn't support doing so
std-del-06 | S | Change the logicalId to something unique for that connected workspace.
std-del-07 | S | you must extend a notebook's item definition with a notebook-settings.json file.
note-del-2 | S | Change the logicalId to something unique for that connected workspace.
std-del-08 | S | While you can assign workspaces from all environments to a single
std-del-09 | S | the test database should be as similar as possible to
std-del-10 | S | let only specific people manage this sensitive operation.
note-del-3 | S | Dev/test workloads with similar requirements can share a single capacity
std-del-11 | S | avoid hardcoding configuration settings that change across environments.
std-del-12 | M | parameterize connections for ETL items, such as pipelines and shortcuts | Drops conditions that connection reference variables target external data sources and that item reference variables require an item type supporting variable libraries.
std-del-13 | S | set production deployment rules for data sources and parameters defined
std-del-14 | M | dynamically update environment-specific settings as part of the deployment process. | Omits deployment pipeline rules (the first option in "Release process options" and std-del-13) when an environment-specific value stays in a committed definition.
std-del-20 | S | item definition doesn't contain anything to indicate which value set is
note-del-4 | S | variable libraries should usually be your first choice for parameterization
std-del-15 | S | add a .gitignore entry so that you never upload terraform.tfvars
std-del-16 | S | Use commit messages to describe the changes made.
std-del-17 | S | still need to run the notebook in the target workspace
std-del-18 | S | Expose a single top-level pipeline or notebook to run end-to-end ETL
std-del-19 | S | Execute API calls as a service principal whenever possible.
std-del-21 | S | Avoid putting ETL logic directly into the scripts you write
std-del-22 | S | To update the associated app, use the deployment pipelines API.

---

### (a) Findings (Ranked by Real Impact)

#### 1. `std-ops-06` — Verdict: `M` (Impact: Medium)
- **Why**: In `WAF operations`, `"Create dashboards and alerts"`, the page states as a platform capability that Fabric *provides* built-in notifications for job failures (such as semantic model refresh failures or pipeline execution errors), and then gives general alert design rules ("Alerts must be meaningful, actionable, and escalated properly. False alarms are as dangerous as no alarms because they erode trust and slow response"). It does not require every new scheduled job, pipeline, or semantic model refresh to have a failure alert and escalation path. Turning this into an unqualified check on every new scheduled job, pipeline, or refresh also creates an unnoted tension with `std-gov-03` (`CAF governance`, `"4. Fabric monitoring"`), which states that a *business-critical* data product should normally have automated failure alerts and an escalation path, while a less critical data product can use periodic review.
- **Evidence**: `sources\azure-well-architected-microsoft-fabric-operational-excellence.md`, heading `#### Create dashboards and alerts` (under `## Monitor your environment`): `"Fabric also provides built-in notifications for job failures, such as"` and `"False alarms are as dangerous as no alarms because they erode trust"`.
- **Suggested replacement**:
  `- \`std-ops-06\` Where failure alerts are configured, such as built-in notifications for semantic model refreshes or pipeline runs, are they meaningful and actionable with an escalation path for higher severity, avoiding false alarms? [review] Applies to: an alert for a scheduled job, pipeline or semantic model refresh. Source: WAF operations, "Create dashboards and alerts"; WAF operations, "Monitor your environment".`

#### 2. `std-del-01` — Verdict: `M` (Impact: Medium)
- **Why**: Two issues:
  1. `Applies to: any change to item definitions` applies the feature-branch/pull-request workflow unconditionally, whereas `CICD concepts` (`"Feature workspaces"` and `"Release process options"`, noted in `note-del-1`) states that this workflow is for projects using feature workspaces, while the simplest scenario with a deployment pipeline makes direct updates and `Commit to Git` operations in the dev workspace.
  2. Whether the hosting Git repository has configured a branch protection policy on the integration branch is a repository setting in Azure DevOps or GitHub, not a file in the branch that a sandboxed agent with no network can inspect without asking (`Ask:`).
- **Evidence**: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, heading `### Feature workspaces`: `"a branch policy that allows updates only through pull requests."` (and `### Release process options`: `"In the simplest development scenario, you can make direct updates"`).
- **Suggested replacement**:
  `- \`std-del-01\` Ask: when the project uses feature branches instead of direct dev commits, does the change arrive through a pull request to an integration branch whose repository policy permits updates only through pull requests? [review] Applies to: a change to item definitions in a feature-branch workflow. Source: CICD concepts, "Feature workspaces"; CICD concepts, "Continuous integration development process".`

#### 3. `std-del-12` — Verdict: `M` (Impact: Medium)
- **Why**: Unlike `std-del-11` (which explicitly includes `"Where the item type supports it, do environment-specific settings..."`), `std-del-12` drops two conditions from `CICD concepts`:
  1. In `"Variable libraries"`, connection reference variables are used to parameterize environment-specific connections to *external data sources* for ETL items (not internal OneLake shortcuts that auto-bind within a workspace or connections that do not vary by environment).
  2. In `"Workspace item types"` (immediately following `"Variable libraries"`), only *some* workspace item types support reading variables from a variable library, so cross-workspace dependencies in unsupported item types cannot be held in item reference variables.
- **Evidence**: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, heading `### Variable libraries`: `"parameterize connections for ETL items, such as pipelines and shortcuts"` and `"Design items that connect to external data sources by using"`.
- **Suggested replacement**:
  `- \`std-del-12\` Where the item type supports variable libraries, do environment-specific external connections for pipelines and lakehouse shortcuts use connection reference variables, and do cross-workspace dependencies use item reference variables? [review] Applies to: a pipeline, a shortcut to an external source, or a cross-workspace dependency. Source: CICD concepts, "Variable libraries"; CICD concepts, "Auto-binding support"; CICD concepts, "Workspace item types".`

#### 4. `std-del-14` — Verdict: `M` (Impact: Medium)
- **Why**: When an environment-specific value remains in a committed item definition in Git (such as a semantic model's dev data-source path committed from the dev workspace), `CICD concepts`, `"Release process options"` describes *three* release options: (1) deployment pipelines (which update stage-specific values using deployment rules/parameter rules, as in `std-del-13` and `"Deployment pipelines"`), (2) Git synchronization (which uses a post-sync job), and (3) an API-driven release (which uses `fabric-cicd` parameterization or REST API calls). `std-del-14` asks only whether `fabric-cicd` parameterization or a post-sync job updates the value, omitting deployment rules when the project releases via a deployment pipeline.
- **Evidence**: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, heading `### Release process options`: `"dynamically update environment-specific settings as part of the deployment process."` (and `### Deployment pipelines`: `"configure a semantic model with a deployment rule to update"`).
- **Suggested replacement**:
  `- \`std-del-14\` Where an environment-specific value stays in a committed item definition, such as a semantic model data-source path, do deployment rules, fabric-cicd parameterization or a post-sync job update it per environment? [review] Applies to: a committed connection string or data-source path. Source: CICD concepts, "Release process options"; CICD concepts, "The fabric-cicd library"; CICD concepts, "Deployment pipelines".`

#### 5. `std-gov-07` — Verdict: `P` (Impact: Low)
- **Why**: In `CAF governance`, `"5. Deployment"`, immediately after stating that medium-risk and high-risk patterns require source control and isolation, the next paragraph adds an explicit exception: data domains should use Fabric Git integration and deployment pipelines *when the Fabric item supports these capabilities*, and an approved alternative should apply when a Fabric item does not support the standard pattern. `std-gov-07` leaves out this same-section exception.
- **Evidence**: `sources\azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, heading `## 5. Deployment`: `"An approved alternative should apply when a Fabric item does not"`.
- **Suggested replacement**:
  `- \`std-gov-07\` Where the item supports Git and deployment pipelines (or else an approved alternative), do medium-risk releases add source control, dev isolation and pre-prod validation, and high-risk ones prod isolation, independent validation and tested recovery? [review] Applies to: a release with several contributors, frequent releases, or an important business process or organizational reporting. Source: CAF governance, "5. Deployment".`

#### 6. `std-sec-10` — Verdict: `P` (Impact: Low)
- **Why**: `std-sec-10` cites both `Baseline`, `"Network Security"` (control `"Establish network segmentation boundaries"`) and `CAF governance`, `"3. Fabric networking"`. While `Baseline` (`NS-1`) states the guidance without qualification, `CAF governance`, `"3. Fabric networking"` explicitly qualifies that managed private endpoints provide private connectivity *for supported Fabric workloads and supported data sources* (and that data domains should use supported private connectivity controls for the applicable workload and data source). `std-sec-10` omits the supported-data-source condition from its second cited section.
- **Evidence**: `sources\azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, heading `## 3. Fabric networking`: `"provide private connectivity for supported Fabric workloads and supported data sources."`.
- **Suggested replacement**:
  `- \`std-sec-10\` Flag a notebook, lakehouse or Spark job definition that must reach a data source behind a private endpoint; guidance: use managed private endpoints where the workload and data source are supported. [flag] Applies to: a new connection from a notebook, lakehouse or Spark job. Source: Baseline, "Network Security" (control "Establish network segmentation boundaries"); CAF governance, "3. Fabric networking".`

#### 7. `std-del-03` — Verdict: `M` (Impact: Low)
- **Why**: In `CICD concepts`, `"Azure Pipelines workflows"`, the page says a validation pipeline *can* run when a developer creates a pull request (`"A validation pipeline can run any time a developer creates a new pull request to check files, run tests, or validate item definitions before reviewers approve the merge"`) and that keeping validation and release responsibilities separate makes the workflow easier to govern. `std-del-03` drops the permissive modal verb (`"can"`) and turns an Azure Pipelines workflow pattern into an unqualified question across any `workflow definition in the repository`.
- **Evidence**: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, heading `### Azure Pipelines workflows`: `"A validation pipeline can run any time a developer creates"`.
- **Suggested replacement**:
  `- \`std-del-03\` Where a pull request validation workflow is used, does it check files, run tests or validate item definitions before reviewers approve, kept separate from the release pipeline so the workflow is easier to govern? [review] Applies to: a workflow definition in the repository. Source: CICD concepts, "Azure Pipelines workflows"; CICD concepts, "How do you develop Fabric CI/CD workflows?".`

---

### (b) File Headers and Sources Tables

All four file headers and `Sources` tables were checked against `sources\` and `DRAFTING-BRIEF.md`:
- **Header claims**: None of the four headers claim more than the source pages state. All required disclaimers are present and accurate:
  - `well-architected.md` and `security-and-governance.md` both state that the Well-Architected security page calls the Azure security baseline a reference and a starting point for conversations, not a checklist (`WAF security`, `"Start with a baseline"`).
  - `security-and-governance.md` states that the Azure security baseline is based on version 1.0 of the Microsoft cloud security benchmark and may contain outdated guidance (`Baseline` header note), and that the adoption roadmap governance page is not a comprehensive reference for data governance (`Roadmap governance` intro note).
  - `architecture-patterns.md` states that the medallion page calls medallion architecture the recommended design approach for Fabric (`Medallion` intro) and that the greenfield page says it can be adapted to your needs (`Greenfield`, `"Cold path for batch analytics"`).
  - `delivery-and-lifecycle.md` states that not every recommendation in the CI/CD concepts page applies to every project (`CICD concepts` intro).
- **`Sources` tables**: Every URL and every `Updated` date (`yyyy-mm-dd`) across all four files matches the `SOURCE:` and `MS.DATE:` header of the corresponding file in `sources\` exactly.

---

### (c) Conflicts Between Lines or Between a Line and a Note

1. **`std-ops-06` (`well-architected.md`) vs `std-gov-03` (`security-and-governance.md`)**:
   - `std-ops-06` asks of *any* new scheduled job, pipeline, or semantic model refresh (`Applies to: a new scheduled job, pipeline or semantic model refresh`): `"Does a new job, pipeline or refresh have a failure alert that is meaningful and actionable, with an escalation path for higher severity?"`
   - `std-gov-03` asks (`Applies to: a new production pipeline, model or report`): `"Does each production data product name an operational owner accountable for monitoring and response, and does a business-critical one normally have automated failure alerts and an escalation path?"` (from `CAF governance`, `"4. Fabric monitoring"`, which explicitly says a less critical data product can use periodic review when delayed recovery has limited business effect).
   - Without scoping `std-ops-06` to where alerts are configured (see Finding 1), an agent reviewing a non-critical scheduled pipeline or refresh gets conflicting guidance between `std-ops-06` (expecting a failure alert and escalation path on every new job/pipeline/refresh) and `std-gov-03` (requiring automated failure alerts and an escalation path normally only for business-critical production data products).

2. **`std-del-13` vs `std-del-14` (`delivery-and-lifecycle.md`)**:
   - `std-del-13` covers a semantic model promoted through a deployment pipeline and asks whether production deployment rules are set for its data sources and parameters.
   - `std-del-14` applies to `a committed connection string or data-source path` (`"such as a semantic model's data-source path"`) and asks only whether `fabric-cicd parameterization or a post-sync job` updates it for each environment.
   - Because a deployment pipeline's dev workspace is also connected to Git (`CICD concepts`, `"Release process options"`), a semantic model promoted through a deployment pipeline *also* has a committed data-source path in Git, but uses deployment rules (`std-del-13`) rather than `fabric-cicd` or a post-sync job (`std-del-14`). Adding deployment rules to `std-del-14` (Finding 4) resolves the conflict.

3. **`std-del-01` vs `note-del-1` (`delivery-and-lifecycle.md`)**:
   - `note-del-1` correctly records that `CICD concepts` describes both direct updates/commits in the dev workspace (for the simplest scenario with a deployment pipeline) and feature branches/workspaces (as the scalable alternative). However, `std-del-01` itself has `Applies to: any change to item definitions` and asks unconditionally whether the change arrives through a pull request from a feature branch. Qualifying `std-del-01` to when the project uses feature branches (Finding 2) aligns the check with `note-del-1`.

*(All other multi-page tensions—off-peak scheduling vs smoothing in `note-wa-1`, test capacity sizing in `note-wa-2`, workspace granularity in `note-sec-1` and `note-arc-2`, bronze format in `note-arc-1`, partitioning vs clustering in `note-arc-3`, `logicalId` on duplication in `note-del-2`, shared dev/test capacity in `note-del-3`, and deployment rules vs variable libraries in `note-del-4`—are accurately documented by their `Note:` lines.)*

---

### (d) Danger Check

- **Forbidden actions (changing permissions, network settings, sensitivity labels, tenant or capacity settings, or deleting, purging, pausing, or recreating items/capacities)**:
  - **None found.** Every check touching permissions, roles, workspace creation settings, item sharing, OneLake/RLS/CLS/OLS security, private endpoints, private links, TLS, sensitivity labels, customer-managed keys, security audit logging, high-impact lifecycle policy, shared capacity settings/permissions, or automation identity (`std-sec-02`, `std-sec-04` to `std-sec-17`, `std-gov-01`, `std-gov-02`, `std-del-10`, `std-del-19`) is tagged `[flag]` and phrased as `"Flag ...; guidance: ..."` or `"Ask: ... [flag]"`, never instructing an agent to perform the change.
  - Checks that mention purging obsolete data (`std-cost-04`), vacuuming history (`std-arc-17`), or pausing capacities (`std-arc-15`) are phrased strictly as review questions about a proposed design or automation in the change (`[review]`), and the headers of `well-architected.md` and `architecture-patterns.md` explicitly state: *"A question about deleting, purging or pausing [or vacuuming] something is a question to ask about the change, never an instruction to do it."*
- **Text reading like an instruction to an agent about something other than applying checks**:
  - **None found.** All four files confine their text to describing the checks, tags, sources, and inter-source notes, and each file header explicitly states: *"This file guides and never authorizes a change."*
