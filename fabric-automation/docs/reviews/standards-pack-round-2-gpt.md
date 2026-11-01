# Second verification of the reference pack, slice Q1: security-and-governance.md and delivery-and-lifecycle.md (GPT 6.1 Sol)

The reply as it came back, with the agent's own header removed. It judged every check and note of the two files cold against the text of the pages, after the corrections of the first verification. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

# Q1 verdict: NEEDS CORRECTION

Reviewed all **43 checks**, both headers and source tables, and **all five actual `Note:` lines**—the brief says four. Five checks and one Note need correction. All findings below are **Medium** impact.

Review was read-only: no pack edits, credentials, pushes, or live operations.

## Evidence keys

These filenames are under `pack2\sources`:

- **CAF:** `azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`
- **CICD:** `fabric-fundamentals-understand-best-practices-fabric-cicd.md`
- **Lifecycle:** `fabric-cicd-best-practices-cicd.md`
- **Cost:** `azure-well-architected-microsoft-fabric-cost-optimization.md`
- **Baseline:** `security-benchmark-azure-baselines-fabric-security-baseline.md`
- **WAF security:** `azure-well-architected-microsoft-fabric-security.md`
- **Roadmap:** `power-bi-guidance-fabric-adoption-roadmap-governance.md`

## Check findings

### `std-gov-03` — PARTLY: qualification lost

**Evidence:** CAF, “4. Fabric monitoring”:

> “A business-critical data product should normally have automated failure alerts”

The owner requirement is supported. The alert/escalation clause drops **“normally”**, making the recommendation appear exceptionless. A reviewer could reject an adequately justified alternative monitoring arrangement.

**Suggested replacement:**

```text
- `std-gov-03` Does each production data product have a named operational owner for monitoring and response, and does a business-critical product normally have automated failure alerts and an escalation path? [review] Applies to: a new production pipeline, model or report. Source: CAF governance, "4. Fabric monitoring".
```

### `std-del-09` — MISLEADING: test-data condition dropped

**Evidence:** Lifecycle, “Use deployment rules with a real-life data source”:

> “If you're using the test stage to simulate real life data usage”

Separate development/testing databases are supported by “Connect different stages to different databases.” However, making the test database resemble production is conditioned on simulating real-life data usage. The check applies that recommendation to every promoted semantic-model connection.

**Suggested replacement:**

```text
- `std-del-09` Do development and test semantic models avoid loading production through separate databases, and, when test simulates real-life data usage, is its database as similar to production as possible? [review] Applies to: a semantic-model data-source connection across stages. Source: Lifecycle, "Connect different stages to different databases"; Lifecycle, "Use deployment rules with a real-life data source".
```

### `std-del-10` — MISLEADING: optional access becomes prescribed access

**Evidence:** Lifecycle, “Manage who can deploy to production”:

> “Other users can have a production workspace viewer role”

Limiting production deployers is supported. **“Give others the viewer role”** changes an available option into an instruction to grant access. Other users need not receive production access merely because they cannot deploy.

The `[flag]` tag correctly prevents factory implementation, but the guidance conveyed to the person still needs correction.

**Suggested replacement:**

```text
- `std-del-10` Flag changes to production deployment access; guidance recommends limiting deployers through workspace permissions, while other users may receive the production workspace viewer role to see content without changing it. [flag] Applies to: production workspace access or deployment permissions. Source: Lifecycle, "Manage who can deploy to production".
```

### `std-del-18` — PARTLY: applicability exceeds the lakehouse-ETL guidance

**Evidence:** CICD, “Data orchestration”:

> “extend the item definition of notebooks and pipelines”

CICD, “Data orchestration strategy”:

> “populate all lakehouses with data”

The top-level lakehouse orchestration recommendation and `.schedules` filename are supported. But **“a new refresh schedule”** admits unrelated schedules, including semantic-model refresh changes. Those do not necessarily concern lakehouse population or the notebook/pipeline definition mechanism described here.

**Suggested replacement:**

```text
- `std-del-18` Does a lakehouse solution expose one top-level pipeline or notebook to populate all lakehouses, with notebook and pipeline refresh schedules defined in .schedules files? [review] Applies to: a lakehouse solution or its notebook/pipeline refresh schedules. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".
```

### `std-del-21` — MISLEADING: examples become an exclusive implementation list

**Evidence:** CICD, “Automation targets”:

> “notebooks, pipelines, copy jobs, user-defined functions, and dataflows”

The source recommends ETL-focused workspace items and gives examples. The check’s unqualified four-type list omits **user-defined functions**, potentially rejecting a source-supported implementation.

Its applicability also includes post-sync scripts, whereas this specific recommendation concerns scripts for post-deploy jobs.

**Suggested replacement:**

```text
- `std-del-21` Does a post-deploy script run ETL-focused workspace items rather than contain ETL logic itself? [review] Applies to: a post-deploy script. Source: CICD concepts, "Automation targets".
```

## All five Notes

### Security: Note after `std-sec-09` — SUPPORTED

**Real conditional tension; both sides are stated correctly.**

CAF, “2. Fabric data security”:

> “Don't create extra workspaces only to reproduce boundaries”

CICD, “Fabric solutions”:

> “split the solution into a staging workspace and a presentation workspace”

CAF’s advice depends on item permissions or OneLake security reliably enforcing the boundary. CICD discusses a medallion solution whose business users must not access staging data. The Note preserves those contexts rather than requiring either layout universally.

There is no unconditional conflict; the access-boundary decision remains a human escalation.

### Delivery: Note after `std-del-03` — MISLEADING, Medium

**The different recommendations are real, but they concern different development approaches. Both quoted actions are accurate; the claim that the page leaves them unreconciled overstates the conflict.**

CICD, “Feature workspaces”:

> “don't directly update items or run Commit to Git operations”

CICD, “Release process options”:

> “you can make direct updates to items in the dev workspace”

The first section describes a feature-workspace development process. The second expressly describes the simplest development scenario and then explains the scalable feature-branch alternative. The Note omits this distinction, making alternatives sound like contradictory instructions for one process.

**Suggested replacement:**

```text
Note: the feature-workspace process routes subsequent changes through feature branches; the deployment-pipeline release section also describes a simpler development process with direct dev-workspace updates and commits. Source: CICD concepts, "Feature workspaces"; CICD concepts, "Release process options".
```

### Delivery: Note after `std-del-07` — SUPPORTED

**Real apparent wording tension; both sides are stated correctly.**

CICD, “The role of the logicalId”:

> “Never modify a logicalId value”

Lifecycle, “Duplicate an item in a Git repository”:

> “Change the logicalId to something unique for that connected workspace”

The sources do not expressly explain a duplication exception to the blanket prohibition. Nevertheless, the pack now supplies an actionable distinction: `std-del-05` covers existing items and explicitly excludes copies; `std-del-06` covers copied items. Agents can follow both checks.

### Delivery: Note after `std-del-10` — SUPPORTED

**Real isolation-versus-cost tradeoff, not a contradiction; both sides are accurate.**

CICD, “Fabric CI/CD projects”:

> “creating a separate Fabric capacity for each one”

Cost, “Consolidate costs effectively”:

> “Dev/test workloads with similar requirements can share a single capacity”

The Note correctly retains similar requirements and off-hours pausing/downsizing. CICD itself also permits sharing; `std-del-08` preserves that permission. No conflicting mandatory capacity layout results.

### Delivery: Note after `std-del-20` — SUPPORTED

**Real difference in preferred parameterization approach; both sides are accurate.**

Lifecycle, “Use parameters for configurations that will change between stages”:

> “configure parameter rules to set different values”

CICD, “Deployment pipelines”:

> “variable libraries should usually be your first choice for parameterization”

The Note correctly retains continued deployment-rule support and **“usually.”** `std-del-11` limits variable-library use to supported item types, while `std-del-13` and `std-del-14` retain deployment-rule and other parameterization paths. No unresolved operational conflict was found.

## Headers, citations, tags, and forbidden actions

### Headers — SUPPORTED

- The security header’s six primary source pages are correctly identified; CICD is additionally cited for its Note.
- Baseline’s introduction supports version **1.0** and warns that it **“may contain outdated guidance.”**
- WAF security, “Start with a baseline,” says **“don't treat it as a checklist”** and calls it **“a starting point for conversations.”**
- Roadmap’s introduction says it is **“not a comprehensive reference for data governance.”**
- The delivery header correctly identifies its two primary pages; Cost supports its additional Note.
- CICD’s introduction supports selecting suitable practices: **“Not every recommendation applies to every project.”**
- Source labels and URLs resolve correctly. All `Updated` fields match the snapshots’ `MS.DATE` dates.
- Every check sentence meets the 35-word limit.

### Baseline citations — all SUPPORTED

Each cited section exists, and each control title exists beneath that section:

| Check | Section | Control title |
|---|---|---|
| `std-sec-05` | Asset Management | Limit access to asset management |
| `std-sec-06` | Privileged access | Separate and limit highly privileged/administrative users |
| `std-sec-10` | Network Security | Establish network segmentation boundaries |
| `std-sec-12` | Data Protection | Discover, classify, and label sensitive data |
| `std-sec-13` | Logging and Threat Detection | Enable logging for security investigation |
| `std-gov-01` | Asset Management | Ensure security of asset lifecycle management |

No wrong section headings or control titles were found elsewhere in Q1.

### Tags and scope safeguards — SUPPORTED

- Security, access, network, sensitivity-label, identity, and administrative-setting changes carry `[flag]`.
- Gates `std-del-04`, `std-del-05`, and `std-del-15` concern program-checkable repository properties: folder/platform metadata, unchanged existing logical IDs, and credential/file/reference hygiene.
- `std-del-15` does not authorize configuring identities, vaults, or permissions; its gate concerns committed content.
- The `Ask:` checks reasonably require organizational policy, external-source capability, or workspace configuration information.
- Governance ownership and quality/documentation reviews do not themselves authorize security changes.
- No check directly instructs the factory to perform forbidden live changes, deletion, or recreation. Flagged guidance remains an escalation, not implementation authority.

## CHECKED AND FINE

**38 check lines fully supported:**

**Security — 12:**
`std-sec-05`, `std-sec-06`, `std-sec-07`, `std-sec-08`, `std-sec-09`, `std-sec-10`, `std-sec-11`, `std-sec-12`, `std-sec-13`, `std-sec-15`, `std-sec-16`, `std-sec-17`.

**Governance — 8:**
`std-gov-01`, `std-gov-02`, `std-gov-04`, `std-gov-05`, `std-gov-06`, `std-gov-07`, `std-gov-08`, `std-gov-09`.

**Delivery — 18:**
`std-del-01`, `std-del-02`, `std-del-03`, `std-del-04`, `std-del-05`, `std-del-06`, `std-del-07`, `std-del-08`, `std-del-11`, `std-del-12`, `std-del-13`, `std-del-14`, `std-del-15`, `std-del-16`, `std-del-17`, `std-del-19`, `std-del-20`, `std-del-22`.
