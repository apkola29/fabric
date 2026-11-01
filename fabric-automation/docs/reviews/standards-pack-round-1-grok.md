# First verification of the reference pack, slice P3: a different angle over all four files (Grok 4.7)

The reply as it came back, with the agent's own header removed. It judged a sample of 24 checks line by line, listed the points of the pages that the pack leaves out, looked for conflicts between checks, for tags that do not fit and for wording that an autonomous agent could misread, and read the headers. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

# Slice P3 report (Grok 4.7)

Source SHA-256 values for all 16 files match `DRAFT-NOTES.md`. Judgments use those extracts. Live pages were not fetched; cited passages were present and readable. The pack was not edited.

## 1. Line-by-line sample (24)

Ids: `std-rel-02`, `std-sec-01`, `std-sec-04`, `std-cost-03`, `std-ops-07`, `std-perf-01`; `std-sec-05`, `std-sec-09`, `std-sec-10`, `std-sec-11`, `std-gov-02`, `std-gov-08`; `std-del-04`, `std-del-05`, `std-del-07`, `std-del-11`, `std-del-15`, `std-del-19`; `std-arc-01`, `std-arc-03`, `std-arc-06`, `std-arc-07`, `std-arc-12`, `std-arc-15`. Thirteen are `[gate]`, `[flag]`, or `Ask:`. Verdicts below are only the ones that are not fully supported. Supported ids are at the end.

**`std-sec-01` WRONG TAG. Medium.** Secret management and SDL do say not to store secrets in notebooks, scripts, or pipelines, and to use Key Vault or parameterization. A program can scan added files for embedded secrets. It cannot decide "retrieved from Azure Key Vault at run time" from item definitions. Quote, Secret management: "dynamic retrieval at runtime".
Replacement: `- std-sec-01 Are notebooks, scripts and pipeline definitions free of embedded secrets? [gate] Applies to: a new notebook, script or pipeline. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)".`

**`std-sec-04` MISLEADING. Medium (wrong scope).** The page recommends mapping workspaces and states a tradeoff. It does not say to flag every layout change. `Applies to: a workspace layout` would escalate environment splits that `std-arc-12` and `std-del-08` ask the agent to design. Quote, Design isolation boundaries: "Map them to teams, projects, or environments."
Replacement: `- std-sec-04 Flag a role assignment or item share; guidance maps workspaces to teams, projects or environments, uses item-level or finer permissions, and more workspaces add overhead. [flag] Applies to: a role assignment or item sharing. Source: WAF security, "Design isolation boundaries".`

**`std-cost-03` PARTLY. Medium.** The scaling-limit sentence is in "Monitor costs and implement governance": "prevent compute usage from growing unchecked". That section does not name a Spark pool or an environment setting. `Applies to` adds both.
Replacement: `- std-cost-03 If the change lets a workload autoscale, does it set a scaling limit so compute cannot grow unchecked? [review] Applies to: a workload that supports autoscaling. Source: WAF cost, "Monitor costs and implement governance".`

**`std-ops-07` MISLEADING. Medium.** Same section: enable monitoring "selectively or temporarily when investigating performance issues". The check drops that condition, so an agent can treat ongoing monitoring as noncompliant. Quote: "when investigating performance issues".
Replacement: `- std-ops-07 If workspace monitoring or OneLake diagnostics is turned on to investigate performance, is it selective or temporary, since busy-workspace logs can grow rapidly? [review] Applies to: a workspace monitoring or diagnostics setting used for an investigation. Source: WAF operations, "Manage monitoring data".`

**`std-perf-01` MISLEADING. Medium.** Performance, "Plan capacity intentionally": separate those layers "so one layer cannot starve another". Overview, "Design for shared capacity", is about interactive work, and does not name those three layers. The "so that" clause fuses them.
Replacement: `- std-perf-01 For a larger solution, are data preparation, orchestration pipelines and presentation separated across workspaces or capacities so one layer cannot starve another? [review] Applies to: a larger solution's workspace or capacity layout. Source: WAF performance, "Plan capacity intentionally".`

**`std-sec-09` WRONG TAG. Medium.** The sentence matches CAF "2. Fabric data security". It is an access-boundary and network-control decision. The factory must flag that, not review-and-implement it. Quote: "materially different administration, deployment, or network controls".
Replacement: `- std-sec-09 Flag a workspace added only to copy an access or network boundary that item permissions or OneLake security already enforce; separate workspaces when those controls differ materially. [flag] Applies to: a workspace layout for access or network control. Source: CAF governance, "2. Fabric data security".`

**`std-del-07` PARTLY and WRONG TAG. Medium.** Auto-binding support does require `notebook-settings.json` for notebooks, and a post-sync script is for types that lack auto-binding ("plan to write"). `Applies to` includes pipelines, which often auto-bind. A program cannot know which types lack auto-binding, or that a script restores relations. Quote: "plan to write a post-sync script".
Replacement: `- std-del-07 Does a new notebook that depends on another item include notebook-settings.json for auto-binding? [gate] Applies to: a new notebook with a same-workspace dependency. Source: CICD concepts, "Auto-binding support".`

**`std-del-11` MISLEADING and WRONG TAG. Medium.** Variable libraries: "Whenever possible, use variable libraries", with a fallback when the item type does not support them. The `[gate]` drops that condition and would fail a hardcoded connection or a type that cannot use a library. A program also cannot see which value set is active (see omissions). Quote: "Whenever possible, use variable libraries".
Replacement: `- std-del-11 Where the item type supports it, do environment-specific settings such as database server and name come from a variable library, with value sets for the environments in use? [review] Applies to: a notebook, pipeline, copy job or dataflow that connects to a data source. Source: CICD concepts, "Variable libraries"; CICD concepts, "Parameterization for environment-specific settings".`

**`std-del-15` WRONG TAG. Low.** Excluding `terraform.tfvars` is decidable and supported: "never upload terraform.tfvars to a Git repository". "Workflow secrets kept in the Git provider's secret features" is not visible in the pull request.
Replacement: `- std-del-15 Does the branch exclude files that hold sensitive credentials, for example terraform.tfvars with a service principal client secret? [gate] Applies to: any file added to the repository. Source: CICD concepts, "Terraform for project infrastructure"; CICD concepts, "Security best practices".`

**`std-arc-03` PARTLY. Medium.** Tables and files, and Deployment model: "Azure Data Lake Store Gen2", "Amazon S3", "Google". The check says "Azure Data Lake Storage" and "Amazon storage", which are broader. The short Amazon code was avoided for the validator; the broadened name can still send an agent to the wrong store. Quote: "instead of copying the data across".
Replacement: `- std-arc-03 For bronze data from OneLake, Azure Data Lake Store Gen2, or the other two stores named in that section, does the change create a shortcut instead of copying? [review] Applies to: a new bronze source from those stores. Source: Medallion, "Tables and files"; Medallion, "Deployment model".`

**`std-arc-06` MISLEADING. Medium.** File size: "between 128 MB and 1 GB" is exact, and gold wants larger files and row groups. The same section allows smaller bronze files. The check applies the range to every new Delta table. Quote: "you can use smaller files".
Replacement: `- std-arc-06 Do writes and maintenance aim for files of 128 MB to 1 GB, scaled to table size and consumption, with smaller files allowed in bronze and larger files and row groups in gold? [review] Applies to: a new Delta table or a table maintenance step. Source: Medallion, "File size".`

**`std-arc-12` MISLEADING. Medium.** Operational Excellence: pattern 1 has no preproduction separation. Pattern 1 is still a valid pattern; deployment pipelines are unavailable there, not forbidden for every solution. `Applies to: a workspace layout` makes the split look required. Quote: "no preproduction separation".
Replacement: `- std-arc-12 If the layout needs preproduction separation or deployment pipelines, are development, test and production in separate workspaces, since one workspace has neither? [review] Applies to: a workspace layout that needs staged promotion. Source: Patterns, "Operational Excellence"; Patterns, "Pattern 1: Monolithic deployment".`

## 2. Omissions

Up to eight points a pull request can decide or a reviewer should check. Not generic cloud advice.

1. **High.** CICD concepts, "Variable libraries". Quote: "which value set is active". The definition has value sets but not which one is active. An agent that only satisfies `std-del-11` can leave production on the dev default.
`- std-del-20 Ask: which value set is active in each workspace, since the item definition does not record it and a post-deploy step must set it? [review] Applies to: a variable library promoted across environments. Source: CICD concepts, "Variable libraries".`

2. **Medium.** CICD concepts, "Automation targets". Quote: "Avoid putting ETL logic directly". An agent may hide refresh logic in a workflow script.
`- std-del-21 Does post-deploy automation keep ETL in notebooks, pipelines, copy jobs or dataflows, instead of embedding that logic in the script? [review] Applies to: a post-deploy or post-sync script. Source: CICD concepts, "Automation targets".`

3. **Medium.** Lifecycle, "Update the production app". Quote: "doesn't include updating the app". A pipeline deploy does not update the app.
`- std-del-22 If an app distributes the content, does the release update that app through the deployment pipelines API, since a pipeline deployment does not? [review] Applies to: a report or app in a deployment pipeline. Source: Lifecycle, "Update the production app".`

4. **Medium.** WAF security, "Data encryption". Quote: "not all Fabric artifacts currently support". Disabling the key makes workspace data inaccessible. This is a security change to flag, not implement.
`- std-sec-14 Flag a customer-managed key change; guidance: not every Fabric artifact supports it, and disabling the key makes workspace data inaccessible until restore. [flag] Applies to: an encryption or key setting for a workspace. Source: WAF security, "Data encryption".`

5. **Medium.** CAF governance, "3. Fabric networking". Quote: "before applying tenant-level restrictions". `std-sec-10` covers outbound managed private endpoints only.
`- std-sec-15 Flag a tenant-level private link; guidance: use workspace-level private links when only some workspaces need them, and assess the operational effect first. [flag] Applies to: a private link or public-access setting. Source: CAF governance, "3. Fabric networking".`

6. **Medium.** WAF security, "Harden workload assets". Quote: "Restrict workspace creation to admins". A tenant setting. No check flags it.
`- std-sec-16 Flag a change to who may create workspaces; guidance: restrict workspace creation to admins to limit sprawl and misconfiguration. [flag] Applies to: a tenant setting for workspace creation. Source: WAF security, "Harden workload assets".`

7. **Medium.** Medallion, "Historical retention". Quote: "within the last seven days". A maintenance notebook can set a shorter vacuum window.
`- std-arc-17 Does a vacuum step keep the default seven-day floor unless delta.deletedFileRetentionDuration sets another retention window? [review] Applies to: a table maintenance or vacuum step. Source: Medallion, "Historical retention".`

8. **Low.** CICD concepts, "Continuous integration development process". Quote: "Delete feature branches after pull requests".
`- std-del-23 Are feature branches deleted after the pull request merges, so they stay short-lived? [review] Applies to: a feature-branch workflow. Source: CICD concepts, "Continuous integration development process".`

## 3. Framing and conflicts

**High. `std-arc-02` vs `std-arc-04`.** "What is medallion architecture?": "No changes are allowed." Deployment model: "or use Parquet or Delta Lake." `std-arc-02` forbids bronze changes; `std-arc-04` allows a format change. No `Note:` records this. An agent can reject either a raw bronze copy or a bronze Delta write.
Replacement for `std-arc-02`: `- std-arc-02 Does each step match its layer: silver fixes errors, standardizes formats and removes duplicates, and gold organizes data for reports, with bronze format left to std-arc-04? [review] Applies to: a notebook, pipeline or dataflow that moves data between layers. Source: Medallion, "What is medallion architecture?".`

**High. `std-del-05` vs `std-del-06`.** Concepts, "The role of the logicalId": "Never modify a logicalId value." Lifecycle, "Duplicate an item in a Git repository": "Change the logicalId to something unique." The `[gate]` on every existing `logicalId` fails the duplication `std-del-06` requires. The `Note:` states both sides correctly and does not tell the agent which check wins.
Replacement: `- std-del-05 Does the change leave the logicalId of each already-tracked item unchanged, since Fabric does not support modifying it? [gate] Applies to: a change to an existing item, not a duplicated folder. Source: CICD concepts, "The role of the logicalId".`

**Medium. Workspace-layout cluster.** `std-sec-04` flags a workspace layout. `std-gov-01` `Applies to: a change to a tenant, a capacity or a workspace`, while its sentence is only access, sensitivity, network, or admin privilege (baseline, "Ensure security of asset lifecycle management"). `std-sec-09`, `std-arc-12`, and `std-del-08` then ask the agent to design that layout. An agent that trusts the flag lines escalates the work the other lines ask it to do.
Replacement for `std-gov-01`: `- std-gov-01 Flag a change to access, data sensitivity, network configuration or an administrative privilege; the baseline asks for a security process covering those high-impact modifications. [flag] Applies to: an access, label, network or admin-privilege change. Source: Baseline, "Asset Management" (control "Ensure security of asset lifecycle management").`

**Medium. `std-del-08` vs its own `Note:`.** Concepts, "Fabric CI/CD projects": "recommended practice is to isolate environments", and also "you can assign workspaces" to one shared capacity. The check says "instead of sharing one capacity", which removes the allowed alternative. The `Note:` correctly cites WAF cost, "Consolidate costs effectively": "Dev/test workloads with similar requirements can share".
Replacement: `- std-del-08 Does each environment have its own workspace, and a separate capacity when isolation is required, noting similar dev and test workloads may share a pausable capacity? [review] Applies to: a workspace or capacity layout. Source: CICD concepts, "Fabric CI/CD projects"; WAF cost, "Consolidate costs effectively".`

**Medium. `std-del-11` vs `std-del-14`.** The gate requires a variable library. `std-del-14` allows an environment value to stay in the definition if a rule or post-sync step updates it. Both cannot be gates.

**Medium. `std-arc-15` vs `std-gov-02`.** `std-gov-02` flags shared-capacity resize, overage, and surge changes. `std-arc-15` is only a review of pause automation, and its `Applies to` assumes that automation exists. Cost Optimization says automate pause for nonproduction; Reliability says pausing makes "all workloads" unavailable. An agent can add production pause automation and call the review satisfied.
Replacement: `- std-arc-15 If automation pauses a capacity, is it limited to nonproduction, and has the loss of every workload on that capacity been accepted? [review] Applies to: automation that pauses a nonproduction capacity. Source: Patterns, "Reliability"; Patterns, "Cost Optimization".`

**Low. `std-del-18`.** Concepts, "Data orchestration strategy", says `.schedules` files. The check says "schedules files". An agent can look for the wrong name.
Replacement: `- std-del-18 Does the solution expose one top-level pipeline or notebook that populates all lakehouses, with refresh schedules kept in the items' .schedules files? [review] Applies to: a new lakehouse solution or a new refresh schedule. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".`

The workspace-per-layer `Note:` and the partition `Note:` in the architecture file state both sides correctly. The capacity `Note:` and the logicalId `Note:` in the delivery file also state both sides correctly; they do not stop the conflicting checks above.

## 4. Tags

**`[gate]` a program cannot fully decide**

- `std-sec-01`: Key Vault runtime retrieval is not in the definition.
- `std-del-07`: which types lack auto-binding, and whether a script restores relations.
- `std-del-11`: which settings are environment-specific, whether the item type supports a variable library, and that test and production value sets exist as a hard rule.
- `std-del-15`: that workflow secrets live in the Git provider, which is outside the pull request.

Decidable, so not listed as bad gates: `std-del-04` (folder name, `.platform`, `logicalId` present) and `std-del-05` (value unchanged). `std-del-05` is still the wrong rule for a copy; that is a conflict, not an undecidable gate.

**Security, permission, network, label, or tenant topic not `[flag]`**

- `std-sec-09`: access boundary and network controls. Retag to `[flag]` (replacement above).
- `std-sec-01` and `std-del-15`: secret handling. A strict reading wants `[flag]`. Do not retag the "no embedded secret" half. Flagging it would stop the agent from omitting secrets, which is the safe action. Narrow the gates as above.
- `std-sec-03`: pull-request secret scanning. It is a security topic, but it is a CI check, not a tenant setting. Leave `[review]`. Retagging to `[flag]` would escalate work the agent should confirm, not refuse.

`std-arc-15` is a capacity action, not a tenant setting, so it is not a missing `[flag]` under the tag list. Treat it as the conflict above. `std-gov-08` is an ownership-policy `Ask:` and is not one of those topics.

## 5. Danger

No check's lead verb tells the agent to change a permission, network setting, label, tenant or capacity setting, or to delete or recreate an item. Flag lines name guidance after "Flag". Headers say the files guide and never authorize.

Residual misreads:

- **Medium.** `std-cost-04` says "Consider automating upkeep" including "purging stale data". The cost page says "purging obsolete data". Followed as an implementation step, an agent can delete data. Replacement: `- std-cost-04 Does the change say how new data will be kept, such as Delta optimization, archival, or a reviewed purge of obsolete data, rather than adding an unreviewed delete? [review] Applies to: a new table or dataset. Source: WAF cost, "Reduce costs through automation".`
- **Low.** `std-sec-05` and `std-sec-10` embed imperatives ("assign roles", "create and use managed private endpoints") after "guidance:". A reader that skips "Flag" would change permissions or network settings. The security header blocks that if it is read.
- **Low.** Well-architected header says the file is for "planning, implementing or reviewing". "Implementing" can be read as authority to carry out security lines in that file. The next sentence says it never authorizes a change.

## 6. The files as a whole

Headers are honest. They say the files are condensed checks, guide and never authorize, and are not a compliance statement. They do not call the pack a Microsoft checklist.

Claims checked against the pages:

- WAF security, "Start with a baseline": "don't treat it as a checklist" and "starting point for conversations". Header match.
- Baseline opening: "based on a previous version" "v1.0" and "may contain outdated guidance". Header match.
- Roadmap governance opening: "not a comprehensive reference for data governance". Header match.
- CICD concepts opening: "Not every recommendation applies to every project". Header match.
- Medallion opening: "recommended design approach for Fabric". Greenfield, "Cold path for batch analytics": "you can adapt it for your needs". Architecture header match.

Control titles cited in the sample exist as the text after the control code: "Limit access to asset management", "Establish network segmentation boundaries". Section headings "Asset Management", "Network Security", and "Privileged access" exist.

CHECKED AND FINE: 12. `std-rel-02`, `std-sec-05`, `std-sec-10`, `std-sec-11`, `std-gov-02`, `std-gov-08`, `std-del-04`, `std-del-05`, `std-del-19`, `std-arc-01`, `std-arc-07`, `std-arc-15`.
