# First verification of the reference pack, slice P1: well-architected.md and architecture-patterns.md (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed. It judged every check and every note of the two files against the text of the pages. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

# P1 verification: CORRECTIONS REQUIRED

Reviewed all **41 checks**, all **4 Notes**, and both files’ header paragraphs. **Eight checks, one Note, and one header assurance need correction.**

All 16 source hashes match `DRAFT-NOTES.md`. Source-table dates match the supplied `MS.DATE` values. Every cited P1 heading exists and contains the relevant discussion. Checks meet the 35-word limit; no excessive consecutive copying was detected. Neither P1 file contains `(control ...)` citations.

Disputed Greenfield and Medallion passages were also checked on the same public Learn pages. No pack edits, credential use, pushes, or live Fabric operations occurred. No finding below is UNVERIFIED.

Source filenames below are relative to `pack\sources\`.

## Check findings

### 1. `std-sec-01` — WRONG TAG — High

The source supports the credential-handling guidance, but `[gate]` bypasses the brief’s flag-only treatment of security changes. An implementing agent could treat credential remediation as ordinary gate compliance instead of escalating it.

**Evidence:** `azure-well-architected-microsoft-fabric-security.md`, “Secret management”: “Do not store secrets in notebooks, scripts, or pipelines.”

**Replacement:**

- `std-sec-01` Flag embedded secrets or credential-handling changes; guidance keeps secrets out of notebooks, scripts and pipelines, using runtime Azure Key Vault retrieval, key vault references or parameterization rules. [flag] Applies to: a notebook, script or pipeline needing credentials. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)".

### 2. `std-ops-07` — PARTLY — Medium

The check drops **“when investigating performance issues”** and applies the selective-or-temporary recommendation to every monitoring-setting change. That can incorrectly discourage persistent operational monitoring outside investigations.

**Evidence:** `azure-well-architected-microsoft-fabric-operational-excellence.md`, “Manage monitoring data”: “enable them selectively or temporarily when investigating performance issues”.

**Replacement:**

- `std-ops-07` For performance investigations, does the change enable Workspace Monitoring or OneLake Diagnostics selectively or temporarily, since detailed logs can grow rapidly? [review] Applies to: workspace monitoring or diagnostics for performance investigations. Source: WAF operations, "Manage monitoring data".

### 3. `std-arc-03` — PARTLY — Medium

“Amazon storage” generalizes beyond the named Amazon service. “Azure Data Lake Storage” also loses the source’s **Gen2** qualification. The exposure restriction explains the drafter’s substitution but does not make that broader scope supported.

**Evidence:** `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, “Tables and files” and “Deployment model”: “Amazon S3”; “Azure Data Lake Store Gen2 (ADLS Gen2)”.

The replacement narrows the supported providers rather than introducing an unsupported expanded service name.

**Replacement:**

- `std-arc-03` For bronze data from OneLake, ADLS Gen2 or Google, does the change create a shortcut instead of copying the data? [review] Applies to: a new bronze source in OneLake, ADLS Gen2 or Google. Source: Medallion, "Tables and files"; Medallion, "Deployment model".

### 4. `std-arc-04` — PARTLY — Medium

The bronze formats are presented as equivalent alternatives. The cited deployment section specifically prefers preserving the original format **whenever possible**.

**Evidence:** `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, “Deployment model”: “Whenever possible, keep the data in its original format.”

**Replacement:**

- `std-arc-04` Are silver and gold preferably Delta tables, with bronze kept in its original format whenever possible, or otherwise stored as Parquet or Delta Lake? [review] Applies to: a new medallion table or layer write step. Source: Medallion, "What is medallion architecture?"; Medallion, "Deployment model".

### 5. `std-arc-11` — MISLEADING — Medium

The check generalizes the fallback expectation to a Direct Lake model without retaining the cited passage’s explicit **Direct Lake on the SQL analytics endpoint** condition. It also strengthens example scenarios that **can** trigger fallback into an expected outcome.

**Evidence:** `azure-architecture-example-scenario-data-greenfield-lakehouse-fabric.md`, “Hot path for real-time analytics”:

- “The following example scenarios can trigger a DirectQuery fallback:”
- “If you turn on Direct Lake on the SQL analytics endpoint”

The live page confirms those qualifications. This is a query-mode check, not an instruction to implement row-level security.

**Replacement:**

- `std-arc-11` With Direct Lake on the SQL analytics endpoint, does the design account for possible DirectQuery fallback when row-level security or endpoint views are involved? [review] Applies to: a Direct Lake semantic model using a SQL analytics endpoint. Source: Greenfield, "Hot path for real-time analytics".

### 6. `std-arc-12` — PARTLY — Medium

The single-workspace limitations are supported. However, the check makes separate development, test and production workspaces the default for **any workspace layout**, without retaining the staged-promotion context. The page explicitly permits a monolithic pattern for suitable simpler deployments.

**Evidence:** `azure-architecture-data-guide-technology-choices-fabric-deployment-patterns.md`:

- “Operational Excellence”: “In patterns 2, 3, and 4, create dedicated workspaces”.
- “Pattern 1: Monolithic deployment”, beneath “When to use this pattern”: “Your organization doesn't have complex engineering requirements”.

**Replacement:**

- `std-arc-12` When using deployment pipelines for staged promotion, does the design provide separate development, test and production workspaces, recognizing that a monolithic workspace cannot use deployment pipelines? [review] Applies to: a workspace layout for staged deployment. Source: Patterns, "Operational Excellence"; Patterns, "Pattern 1: Monolithic deployment".

### 7. `std-arc-13` — PARTLY — Medium

“Several workspaces on one shared capacity” is broader than the cited **all-environments-shared-capacity pattern**. The section also permits shared dev/test capacity with separate production capacity; it does not universally require an exclusive capacity for test.

**Evidence:** `azure-architecture-data-guide-technology-choices-fabric-deployment-patterns.md`, “Operational Excellence”: “a shared capacity for dev/test with a separate production capacity”.

**Replacement:**

- `std-arc-13` For production-like performance or resilience testing, does preproduction use environment-aligned workspaces with capacity-level isolation, rather than the all-environments-shared-capacity pattern suited only to functional validation? [review] Applies to: a preproduction workspace and capacity layout. Source: Patterns, "Operational Excellence".

### 8. `std-sec-03` — WRONG TAG — Low

This is security validation and therefore must use `[flag]` under the drafting contract, rather than ordinary `[review]`. The source supports these scanning techniques but presents them as techniques that can run in CI or pull-request validation.

**Evidence:** `azure-well-architected-microsoft-fabric-security.md`, “Secure Development Lifecycle (SDL)”: “Static analysis, secret detection, and dependency scanning can run”.

**Replacement:**

- `std-sec-03` Flag missing security validation; guidance says static analysis, secret detection and dependency scanning can run during pull request validation or CI for changed notebooks and pipelines. [flag] Applies to: a pull request changing notebooks, pipelines or dependencies. Source: WAF security, "Secure Development Lifecycle (SDL)".

## The four Notes

### `well-architected.md`, line 58 — scheduling

**Tension is real; the Note states each side correctly.** The recommendations diverge, including within Greenfield.

**Evidence:**

- `azure-well-architected-microsoft-fabric-performance-efficiency.md`, “Plan capacity intentionally”: “eliminates the need to schedule heavy workloads during off-peak hours.”
- `azure-architecture-example-scenario-data-greenfield-lakehouse-fabric.md`, “Cost Optimization”: “schedule noncritical tasks during off-peak times to avoid spikes in CU usage.”
- Same file and section: “Schedule long-running jobs at staggered times”.
- Same file, “Performance Efficiency”: “You can schedule these activities at any time.”

No replacement needed.

### `well-architected.md`, line 60 — test capacity size

**A real cost-versus-test-fidelity tradeoff, not a strict contradiction. Both sides are accurately stated.** Temporarily scaling a smaller test capacity can satisfy the performance page’s ideal.

**Evidence:**

- `azure-well-architected-microsoft-fabric-operational-excellence.md`, “Don't assume everything works”: “test capacities are often smaller than production”; “temporarily scaled up during load tests”.
- `azure-well-architected-microsoft-fabric-performance-efficiency.md`, “Do performance testing”: “Ideally, testing environments should use the same capacity size”.

No replacement needed.

### `architecture-patterns.md`, line 27 — workspace boundaries

**PARTLY — Medium.** The layout tradeoff is real, and the four layout descriptions are accurately reported. However, **“The pages do not say how to choose” is false**: governance supplies criteria concerning different controls, CI/CD supplies an audience-access condition, and Patterns supplies operational-responsibility criteria. Absence of one universal algorithm is not absence of selection guidance.

**Evidence:**

- `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, “Deployment model”: “create each lakehouse in its own, separate workspace”.
- `azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, “2. Fabric data security”: “Don't create extra workspaces only to reproduce boundaries”; “materially different administration, deployment, or network controls.”
- `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, “Fabric solutions”: “security requirement preventing business users from accessing staging data”.
- `azure-architecture-data-guide-technology-choices-fabric-deployment-patterns.md`, “Pattern 2: Multiple workspaces, single capacity”: “one team manages the bronze and silver layers”; “another team manages the gold layer”.

**Replacement:**

Note: medallion favors one workspace per lakehouse, while governance, CI/CD and deployment patterns provide selection criteria based on administration, deployment, networking, audience access and operational responsibilities. Source: Medallion, "Deployment model"; CAF governance, "2. Fabric data security"; CICD concepts, "Fabric solutions"; Patterns, "Pattern 2: Multiple workspaces, single capacity".

### `architecture-patterns.md`, line 29 — partitioning and clustering

**Apparent wording tension, not a demonstrated unavoidable conflict. The Note accurately states both sides.** “Wherever applicable” qualifies the folder recommendation, but the section does not explicitly explain that applicability.

**Evidence:** `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, “Table partitions and clustering”:

- “use a partitioned folder structure wherever applicable.”
- “In the bronze layer, partitioning is acceptable but discouraged for new implementations.”
- “For silver and gold layers, use Liquid Clustering instead of partitioning”

No replacement needed. The Note should not be interpreted as overriding the explicit layer-specific clustering guidance.

## Header checks

The substantive source-attribution claims are accurate:

- **Baseline as reference, not checklist:** `azure-well-architected-microsoft-fabric-security.md`, “Start with a baseline”: “don't treat it as a checklist”.
- **Medallion as recommended approach:** `fabric-onelake-onelake-medallion-lakehouse-architecture.md`, introduction: “It's the recommended design approach for Fabric.”
- **Adaptability:** `azure-architecture-example-scenario-data-greenfield-lakehouse-fabric.md`, “Cold path for batch analytics”: “you can adapt it for your needs.”

Both files clearly describe guidance rather than authorization or compliance certification.

**Architecture header assurance — PARTLY, Low:** “each check keeps the conditions the page gives” is presently inaccurate, as demonstrated by the qualifier findings above. For example, Medallion’s “Deployment model” says: “Whenever possible, keep the data in its original format.”

Replace that first header sentence with:

> These pages describe patterns and an example scenario; review checks prompt judgement rather than requirements and must be applied within the source's stated conditions.

Keep the subsequent, supported Medallion and Greenfield attribution sentence.

No additional direct P1 cross-pack contradiction was confirmed beyond the scope and Note problems reported above.

## CHECKED AND FINE

**33 check lines**, fully supported with acceptable scope, citation and tag:

- `std-rel-01`, `std-rel-02`, `std-rel-03`, `std-rel-04`, `std-rel-05`
- `std-sec-02`, `std-sec-04`
- `std-cost-01`, `std-cost-02`, `std-cost-03`, `std-cost-04`
- `std-ops-01`, `std-ops-02`, `std-ops-03`, `std-ops-04`, `std-ops-05`, `std-ops-06`
- `std-perf-01`, `std-perf-02`, `std-perf-03`, `std-perf-04`, `std-perf-05`
- `std-arc-01`, `std-arc-02`, `std-arc-05`, `std-arc-06`, `std-arc-07`, `std-arc-08`, `std-arc-09`, `std-arc-10`, `std-arc-14`, `std-arc-15`, `std-arc-16`
