# Third verification of the reference pack, every line, lens 1: the literal-minded agent (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed. It gave a verdict and a verbatim quote of the source for every check and every note (97 rows). A program then looked up each quote in the cited section of the cited page. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

ID | Verdict | Quote | Reason (non-S only)
---|---|---|---
std-del-01 | M | as a one-time operation. | Universal scope excludes initial seeding and the documented simplest development process.
std-del-02 | M | you can specify an optional Git folder setting. | A single-workspace repository containing only item definitions need not configure a Git folder.
std-del-03 | M | A validation pipeline can run any time a developer | An Azure Pipelines option becomes a universal requirement for a separate validation pipeline.
note-del-1 | S | In the simplest development scenario, you can make direct updates
std-del-04 | S | Every item definition requires a file named .platform
std-del-05 | S | Never modify a logicalId value
std-del-06 | S | If necessary, update the logicalId and/or display names in any dependencies.
std-del-07 | S | Notebooks also don't support auto-binding by default
note-del-2 | S | Never modify a logicalId value
std-del-08 | S | you can assign workspaces from all environments to a single shared capacity
std-del-09 | S | it's best to separate the development and test data sources.
std-del-10 | S | Other users can have a production workspace viewer role
note-del-3 | S | Dev/test workloads with similar requirements can share a single capacity
std-del-11 | S | Whenever possible, use variable libraries to manage parameterization across environments.
std-del-12 | S | only supports auto-binding behavior between items that exist in the same workspace.
std-del-13 | S | parameters defined in the semantic model.
std-del-14 | M | You could implement a release process by using the Fabric REST APIs | Closed method list excludes deployment rules and custom API-driven releases.
std-del-20 | S | doesn't contain anything to indicate which value set is active.
note-del-4 | S | variable libraries should usually be your first choice for parameterization
std-del-15 | T | Never commit files with sensitive credentials to Git. | Credential-security checks require [flag] under the brief's tag definition.
std-del-16 | S | first to a dev or test environment.
std-del-17 | M | The most common way to update the table schema | The most common lakehouse method becomes mandatory, excluding other implementations.
std-del-18 | M | notebooks, pipelines, or another item type | Requiring a pipeline or notebook excludes the explicitly permitted alternative top-level item types.
std-del-19 | S | This is especially common while an item type is in public preview.
std-del-21 | S | ETL-focused workspace items, such as notebooks, pipelines, copy jobs
std-del-22 | S | If you use an app for content distribution
std-arc-01 | S | Keep each layer separated in its own lakehouse or warehouse
std-arc-02 | S | Store everything exactly as it arrives. No changes are allowed.
std-arc-03 | S | create a shortcut in the bronze layer instead of copying
std-arc-04 | S | Whenever possible, keep the data in its original format.
std-arc-05 | S | should be based on your preference and the expertise of your team.
std-arc-06 | S | as long as you focus data modification and preparation on Spark.
std-arc-07 | S | partitioning is acceptable but discouraged for new implementations.
std-arc-17 | S | by default you can't delete historical data within the last seven days.
note-arc-1 | S | No changes are allowed.
note-arc-2 | S | we recommend that you create each lakehouse in its own, separate workspace.
note-arc-3 | S | wherever applicable
std-arc-08 | S | If you prefer a low-code or no-code experience
std-arc-09 | S | you can define materialized lake views that automatically manage the transformations.
std-arc-10 | S | To modify data, switch to lakehouse mode and use Spark.
std-arc-11 | S | The following example scenarios can trigger a DirectQuery fallback:
std-arc-12 | S | Deployment pipelines require separate workspaces, so they aren't available in pattern 1.
std-arc-13 | S | suits functional validation but not production-like performance or resilience testing.
std-arc-14 | S | In patterns 3 and 4, you can isolate performance-sensitive workloads
std-arc-15 | M | before you pause a capacity that supports production workloads. | The nonproduction conjunct excludes production pausing even after the source's required reliability assessment.
std-arc-16 | S | items that rely on shortcuts might fail.
std-sec-05 | S | because these roles can manage or share workspace content.
std-sec-06 | S | so administrative privileges are activated only when required.
std-sec-17 | S | Restrict workspace creation to admins to prevent sprawl and misconfigurations.
std-sec-07 | S | does not necessarily grant permission to query its underlying OneLake data.
std-sec-08 | S | can limit viewer access to data using row-level security
std-sec-09 | S | when data products require materially different administration, deployment, or network controls.
note-sec-1 | S | with a security requirement preventing business users from accessing staging data
std-sec-10 | S | to securely connect to datasources behind private endpoints.
std-sec-11 | S | now requires TLS 1.2 or later
std-sec-16 | S | where the required Fabric capabilities support them.
std-sec-12 | S | exported to supported formats such as PBIX, Excel, PowerPoint, and PDF
std-sec-15 | S | not all Fabric artifacts currently support CMK
std-sec-13 | S | options available and configurable at workspace level for high value assets.
std-gov-01 | S | potentially high impact modifications
std-gov-02 | S | should not receive unrestricted authority to resize the Fabric capacity
std-gov-03 | S | A business-critical data product should normally have automated failure alerts
std-gov-04 | M | They shouldn't treat workspace monitoring as complete coverage for every Fabric experience. | Requires positive coverage of all items, rather than identifying supported telemetry and covering gaps.
std-gov-05 | S | but it doesn't alone determine the release pattern.
std-gov-06 | S | when a failed release has limited business effect and restoration is straightforward.
std-gov-07 | S | An independent person or automated control should validate the release.
std-gov-08 | S | Specifies when an owner is required for a data asset
std-gov-09 | S | Critical data is usually subject to stricter governance requirements.
std-rel-01 | S | Make sure retries don't cause duplicate writes or processing errors.
std-rel-02 | S | Pause requests to a failing dependency to prevent cascading failures.
std-rel-03 | S | For example, pipelines can skip non-critical steps or use cached data
std-rel-04 | M | If upstream gateways or databases go down | The conjunct makes an external dependency a pass condition even for an internal source.
std-rel-05 | S | chaos testing inside Fabric isn't possible
std-rel-06 | S | such as independent pipelines, datasets, and processing stages.
std-sec-01 | T | Do not store secrets in notebooks, scripts, or pipelines. | The brief requires [flag] for security topics; this check uses [gate].
std-sec-02 | S | Where possible, rely on workspace identity or service principals, avoiding static credentials
std-sec-03 | T | Security validation should be integrated into development workflows. | Security-workflow changes are security topics and require [flag], not [review].
std-sec-04 | S | Adding more workspaces and capacities increases operational complexity and management overhead.
std-sec-14 | S | through Azure key vault references or parameterization rules
std-cost-01 | S | Larger retention windows increase monthly storage cost
std-cost-02 | S | such as using shortcuts for in-place data sharing
std-cost-03 | S | set clear guardrails on workloads that support autoscaling.
std-cost-04 | S | Automate tasks such as delta table optimization, purging obsolete data
std-ops-01 | S | Testing before promotion is non-negotiable.
std-ops-02 | S | Validate schema changes or missing values
std-ops-03 | S | Test environments should use sample or anonymized data sources
std-ops-04 | S | Multiple data stores, pipelines, or models may require careful reconciliation
std-ops-05 | S | Pipelines should enforce approvals for production deployments
std-ops-06 | S | so higher severity alerts reach the appropriate support teams quickly.
std-ops-07 | S | enable them selectively or temporarily when investigating performance issues.
std-perf-01 | S | larger solutions, isolating architectural layers across workspaces or capacities can reduce contention.
std-perf-02 | S | capacity smoothing automatically distributes background workloads over a 24-hour period
std-perf-03 | S | Ideally, testing environments should use the same capacity size
std-perf-04 | S | Spark workloads benefit from well-defined partitions and parallel execution strategies.
std-perf-05 | S | techniques such as incremental refresh, query folding, and aggregation tables
note-wa-1 | S | You can schedule these activities at any time.
note-wa-2 | S | test capacities are often smaller than production and temporarily scaled up

## FINDINGS

**Coverage:** 87 checks and 10 notes; 85 S, 9 M, 3 T. Every evidence quote was mechanically matched within a cited section, with the required length limit. All proposed check sentences below contain at most 35 words.

### High

None confirmed.

### Medium

**1. std-del-01 — A development-pattern rule is applied universally.**

The feature-workspace process excludes subsequent direct commits, but permits initial seeding. The page also permits the simplest direct-update process described in note-del-1. “Any change” loses these distinctions.

Evidence: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Feature workspaces”: “as a one-time operation.”; “Release process options”: “In the simplest development scenario, you can make direct updates”.

Replacement:

- `std-del-01` After initial seeding in a feature-workspace process, does the change merge through a feature-branch pull request under an integration-branch policy that prohibits direct commits? [review] Applies to: item-definition changes in a feature-workspace development process. Source: CICD concepts, "Feature workspaces"; CICD concepts, "Continuous integration development process".

**2. std-del-14 — Two implementations become an exclusive method list.**

Environment-specific values also occur in deployment-pipeline and custom API-driven releases. Those routes should not require an additional fabric-cicd or post-sync job merely to satisfy this check.

Evidence: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Release process options”: “You could implement a release process by using the Fabric REST APIs”; “Deployment pipelines”: “Deployment pipelines in Fabric continue to support deployment rules.”

Replacement:

- `std-del-14` When Git synchronization propagates committed environment-specific settings, does a post-sync job correct them; when fabric-cicd deploys them, does its parameterization apply the target values? [review] Applies to: environment-specific values deployed by Git synchronization or fabric-cicd. Source: CICD concepts, "Release process options"; CICD concepts, "The fabric-cicd library".

**3. std-gov-04 — Checking support becomes requiring complete support.**

“Confirm that workspace monitoring supports the items in use” requires a positive answer for all items. The source instead requires understanding telemetry support and warns against assuming complete coverage. A valid plan can cover unsupported items through other tooling.

Evidence: `sources\azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, “4. Fabric monitoring”: “They shouldn't treat workspace monitoring as complete coverage for every Fabric experience.”

Replacement:

- `std-gov-04` Does the plan avoid relying solely on the preview Monitor hub capacity view and, when using workspace monitoring, check which items have supported telemetry rather than assuming complete coverage? [review] Applies to: a monitoring or alerting change. Source: CAF governance, "4. Fabric monitoring".

**4. std-del-17 — The common lakehouse implementation becomes mandatory.**

The explanatory section calls notebook-based schema updates the most common method, not the only method. Its important execution requirement applies when that method is chosen. Warehouse tooling is specifically recommended for schema CI/CD.

Evidence: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Data orchestration”: “The most common way to update the table schema”.

Replacement:

- `std-del-17` When a lakehouse schema update is implemented in a notebook, is it executed in every target workspace; does warehouse schema CI/CD consider SqlPackage and Data-tier Application Framework tooling? [review] Applies to: a lakehouse or warehouse schema change. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".

**5. std-del-18 — The top-level ETL item types are unnecessarily closed.**

The checklist recommends a pipeline or notebook, but its explanatory section expressly permits another item type. Preserve the single-entry-point requirement without rejecting that alternative.

Evidence: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Data orchestration”: “notebooks, pipelines, or another item type”.

Replacement:

- `std-del-18` Does the lakehouse solution expose a single top-level ETL item to populate its data containers, with notebook and pipeline refresh schedules versioned in .schedules files? [review] Applies to: a lakehouse solution, or a scheduled notebook or pipeline refresh. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".

**6. std-arc-15 — Nonproduction guidance becomes a restriction.**

The first conjunct requires a nonproduction target. The reliability section nevertheless discusses considering a production capacity pause after assessing its effect; it does not prohibit that proposal. This distinction concerns reviewing a proposal, not authorizing execution.

Evidence: `sources\azure-architecture-data-guide-technology-choices-fabric-deployment-patterns.md`, “Reliability”: “before you pause a capacity that supports production workloads.”

Replacement:

- `std-arc-15` Does capacity-pausing automation consider off-hours pausing for nonproduction and, before pausing a capacity supporting production, assess the resulting unavailability of every workload on that capacity? [review] Applies to: proposed capacity-pausing automation. Source: Patterns, "Reliability"; Patterns, "Cost Optimization".

**7. std-del-02 — The Git-folder scenario condition is missing.**

The field is optional. The source describes using it to separate other project files, or to coordinate a multi-workspace solution. An item-only, single-workspace repository should not fail for leaving it blank.

Evidence: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Git folder settings”: “you can specify an optional Git folder setting.”

Replacement:

- `std-del-02` If item definitions share a repository with other project files, does a Git folder separate them; for multi-workspace solutions, does each workspace use a unique folder in one shared repository branch? [review] Applies to: a Git connection or repository layout. Source: CICD concepts, "Git folder settings"; CICD concepts, "Continuous integration development process".

**8. std-del-03 — Optional workflow structure becomes a universal requirement.**

The cited Azure Pipelines section describes a validation pipeline that can run for pull requests. Separating responsibilities does not establish a universal requirement for two distinct pipelines across both Git providers.

Evidence: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Azure Pipelines workflows”: “A validation pipeline can run any time a developer”.

Replacement:

- `std-del-03` For Azure Pipelines, consider pull-request validation that checks files, runs tests or validates definitions before merge, keeping validation and release responsibilities separate. [review] Applies to: an Azure Pipelines workflow definition. Source: CICD concepts, "Azure Pipelines workflows".

**9. std-rel-04 — Dependency identification is joined to mitigation with “and”.**

Within the broad “new data source” scope, an internal source can correctly introduce no external dependency. The question should make mitigation conditional, rather than making an external dependency itself a positive pass condition.

Evidence: `sources\azure-well-architected-microsoft-fabric-reliability.md`, “Understand where failures happen”: “If upstream gateways or databases go down”.

Replacement:

- `std-rel-04` If the change adds an external dependency, does its design mitigate failure through measures such as caching, queuing or backup sources? [review] Applies to: a new external data source, gateway or API call. Source: WAF reliability, "Define reliability goals for your workloads"; WAF reliability, "Understand where failures happen".

### Low

These three findings apply the brief’s literal rule that security topics require `[flag]`. The brief supplies no explicit exception for secret hygiene or security-validation workflow changes.

**10. std-sec-03 — Security validation uses `[review]`.**

The content is supported, but changes to security validation should be routed for escalation rather than ordinary implementation review.

Evidence: `sources\azure-well-architected-microsoft-fabric-security.md`, “Secure Development Lifecycle (SDL)”: “Security validation should be integrated into development workflows.”

Replacement:

- `std-sec-03` Flag a change to security validation; guidance: integrate it into development, with checks such as static analysis, secret detection and dependency scanning. [flag] Applies to: the validation workflow of a repository with notebooks or pipelines. Source: WAF security, "Secure Development Lifecycle (SDL)".

**11. std-sec-01 — Embedded-secret security uses `[gate]`.**

Deterministic detection does not override the brief’s required security-topic tag.

Evidence: `sources\azure-well-architected-microsoft-fabric-security.md`, “Secret management”: “Do not store secrets in notebooks, scripts, or pipelines.”

Replacement:

- `std-sec-01` Flag an embedded secret in a notebook, script or pipeline; guidance: do not store secrets there. [flag] Applies to: a new or changed notebook, script or pipeline. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)".

**12. std-del-15 — Credential-security handling uses `[gate]`.**

Its substantive guidance is supported; its tag conflicts with the supplied security-topic definition.

Evidence: `sources\fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Security best practices”: “Never commit files with sensitive credentials to Git.”

Replacement:

- `std-del-15` Flag files containing sensitive credentials or hardcoded workflow secrets; guidance: keep credential files out of Git and use Git-provider secrets. [flag] Applies to: repository files, including workflow and infrastructure files. Source: CICD concepts, "Terraform for project infrastructure"; CICD concepts, "Security best practices"; CICD concepts, "Azure Pipelines workflows"; CICD concepts, "GitHub Actions workflows".

## HEADER ISSUES

No unsupported product claim or source-table error confirmed.

- Source URLs resolve to the supplied source files; listed update dates match their `MS.DATE` dates.
- Every cited heading exists. Baseline control titles are present under the cited parent sections.
- The baseline’s version 1.0 and possible outdatedness are accurately disclosed.
- The Well-Architected baseline caveat and the roadmap’s non-comprehensive scope are accurately disclosed.
- Generic “guides, never authorizes” and project-selection caveats do not repair the local scope and method-selection defects above.

## CONFLICTS

The practical overlaps are captured by M findings rather than counted again as separate X findings:

- **std-del-01 versus note-del-1:** “Any change” defeats the note’s permitted simplest direct-update process unless the check is explicitly qualified.
- **std-del-14 versus std-del-13 and note-del-4:** deployment rules are supported, and sometimes specifically requested, but del-14’s closed method list makes a rules-only release fail. Method-dependent wording removes that collision.

No additional unavoidable X-verdict pair confirmed.

- std-del-05 and std-del-06 distinguish preserving an existing item’s identity from assigning a copied item a new identity.
- The workspace and capacity notes preserve conditional alternatives, not simultaneous mandatory topologies.
- note-arc-3 records an apparent partitioning tension; it does not establish that every table must simultaneously be partitioned and Liquid Clustered.

## DANGER

**No check explicitly orders a forbidden live mutation when read with its file header.**

Capacity pausing in std-arc-15, history removal in std-arc-17, and purging in std-cost-04 remain non-authorizing review questions. Schema-release checks likewise do not grant permission to execute destructive operations.

The three missing `[flag]` tags create a routing hazard, particularly if an agent automatically repairs security-validation workflows. Those checks must not be treated as authorization to implement security changes.

No unrelated agent instructions or prompt-injection text found in the four pack files. No credentials, live operations, pushes, or pack edits were used.
