# Second verification of the reference pack, slice Q3: the closure of the first verification, the new lines and a sample (Grok 4.7)

The reply as it came back, with the agent's own header removed. It decided each finding of the first verification, judged the nine lines that were added after it, and judged a sample of 16 other checks. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

Slice Q3 closure check. Sources are the pack2 extracts. Quotes are at most 12 words. The pack was not edited.

## 1. Closure

### Tags and scope

- **std-sec-01 CLOSED.** The gate is now only "free of embedded secrets," which a program can see in the files. Secret management: "Do not store secrets in notebooks, scripts, or pipelines." Key Vault is no longer in the gate. No new defect.
- **std-sec-03 PARTLY CLOSED. Medium. New defect.** The old review question covered pull-request validation or CI. The new flag fires when scans are missing from "its validation," so CI-only scanning still fails the check. SDL: "pull request validation or CI pipelines." `[flag]` matches a security topic, but the lost "or" makes the factory refuse a notebook change that the page allows.
  Replacement: `- \`std-sec-03\` Flag a pull request that changes notebooks, pipelines or dependencies when neither its validation nor CI runs static analysis, secret detection and dependency scanning; guidance: these can run in either place. [flag] Applies to: a pull request that changes notebooks, pipelines or dependencies. Source: WAF security, "Secure Development Lifecycle (SDL)".`
- **std-sec-04 CLOSED.** Applies to is now a role assignment or item share, not a workspace layout. Design isolation boundaries: "Map them to teams, projects, or environments." Item-level or finer permissions and workspace overhead are in that section. No new defect.
- **std-sec-09 PARTLY CLOSED. Medium. New wording defect.** The tag, the "reliably" condition, and the separate-when-controls-differ clause are fixed. The new sentence treats a network boundary as something item permissions or OneLake security enforce. The page does not. Workspace isolation: "boundaries that item permissions or OneLake security can enforce reliably." Network is a reason to separate: "administration, deployment, or network controls." The Note states the page correctly; the check does not.
  Replacement: `- \`std-sec-09\` Flag a workspace added only to reproduce an access boundary that item permissions or OneLake security already enforce reliably; the guidance separates workspaces when administration, deployment or network controls differ materially. [flag] Applies to: a workspace layout for access or network control. Source: CAF governance, "2. Fabric data security".`
- **std-gov-09 CLOSED.** PII or regulated data "should" face stricter governance; critical data "usually" does. Decision criteria: "should be subject to stricter governance requirements" and "usually subject to stricter governance requirements." Data-quality examples sit with critical content in the cited key-decisions section. `[review]` plus `Ask:` is right: this is governance knowledge, not a label change. No new defect.
- **std-del-07 CLOSED.** `[review]` is decidable only by judgement. Same-workspace limit, `notebook-settings.json`, and a post-sync script are in Auto-binding support and Continuous integration development process. No new defect.
- **std-del-11 CLOSED.** The gate is gone. "Where the item type supports it" matches Workspace item types: "not all, workspace item types support." Value sets and the database server and name example are in Variable libraries. No new defect.
- **std-del-13 CLOSED.** `Ask:` is right: production deployment rules are service settings, not in the item definition. Set rules: "set production deployment rules for data sources and parameters." No new defect.
- **std-del-15 CLOSED.** The gate now checks files: exclude credential files, and reference secrets instead of hardcoding them. Security best practices: "Never commit files with sensitive credentials." Terraform names `terraform.tfvars` and a service-principal client secret. Workflow sections say to create provider secrets. A program can see that in the pull request. No new defect.
- **std-gov-01 CLOSED.** Applies to is the four modification types, not any tenant, capacity, or workspace edit. AM-3: "changes to access, data sensitivity level, network configuration." No new defect.

### Lost conditions or wording

- **std-ops-07 CLOSED.** The investigation condition is back. Manage monitoring data: "when investigating performance issues." No new defect.
- **std-perf-01 CLOSED.** The starve clause is now the performance page's own, and the overview citation is gone. Plan capacity intentionally: "so one layer cannot starve another." No new defect.
- **std-cost-03 CLOSED.** Applies to is a workload that supports autoscaling, not a Spark pool. Monitor costs: "workloads that support autoscaling" and "growing unchecked." No new defect.
- **std-cost-04 CLOSED.** "Obsolete" matches the page, and the line asks how upkeep is described rather than ordering a purge. Reduce costs through automation: "purging obsolete data." No new defect.
- **std-arc-03 CLOSED.** Gen2 is named as the page names it, and Amazon is not spelled as the two-character store id. Tables and files, and Deployment model: "instead of copying the data across." No new defect.
- **std-arc-04 CLOSED.** "Whenever possible" is restored. Deployment model: "Whenever possible, keep the data in its original format." Silver and gold as Delta tables is in both cited sections. No new defect.
- **std-arc-06 CLOSED.** 128 MB to 1 GB, table size and consumption, smaller bronze files, larger gold files and row groups. File size: "you can use smaller files" and "larger row groups." No new defect.
- **std-arc-11 PARTLY CLOSED. Low. Residual, not a new defect.** The endpoint-as-data-source requirement and the broad Applies to are gone. The page still lists a third fallback the line omits. Hot path: "table stats exceed the associated capacity guardrails."
  Replacement: `- \`std-arc-11\` With Direct Lake on the SQL analytics endpoint, does the design account for an automatic DirectQuery fallback when row-level security, an endpoint view or table stats over capacity guardrails are involved? [review] Applies to: a Direct Lake semantic model that uses a SQL analytics endpoint. Source: Greenfield, "Hot path for real-time analytics".`
- **std-arc-12 CLOSED.** The condition is "when deployment pipelines are used." Pattern 1: "aren't available, for example deployment pipelines." Operational Excellence: "no preproduction separation." No new defect.
- **std-arc-13 CLOSED.** The descriptions match pattern 2 and pattern 3 without mis-numbering them. Operational Excellence: "environment-aligned workspaces with capacity-level isolation" and "suits functional validation." No new defect.
- **std-arc-15 CLOSED.** Pause automation is for nonproduction; a production capacity needs the loss of every workload considered. Cost Optimization: "pausing for nonproduction environments." Reliability: "all workloads on that capacity become unavailable." No new defect.
- **std-gov-02 CLOSED.** "Can" is restored, and Applies to is no longer infrastructure code. 1.2 Permissions: "can increase cost or affect other data domains." No new defect.
- **std-gov-07 CLOSED.** Medium and high patterns match, including "an independent person or automated control" and "important business process or organizational reporting." 5. Deployment. No new defect.
- **std-sec-06 CLOSED.** The control title is on the page: "Separate and limit highly privileged/administrative users." "Care when delegating settings" is in that control. PIM "only when needed" is in Harden workload assets. No new defect.
- **std-del-03 CLOSED.** The conjunction is now "or," and it is not "every" pull request. Azure Pipelines workflows: "check files, run tests, or validate item definitions before reviewers approve." No new defect.
- **std-del-08 CLOSED.** Separate capacity is the recommended practice, and sharing one capacity is allowed. Fabric CI/CD projects: "you can assign workspaces from all environments to a single shared capacity." No new defect.
- **std-del-09 CLOSED.** Scope is semantic models, as the cited sections say. Connect different stages: "development or test semantic models." No new defect.
- **std-del-14 PARTLY CLOSED. Low. Residual.** Parameterization is now cited and is in The fabric-cicd library. "A rule" is not in Release process options or The fabric-cicd library. Those sections support a post-sync step and deployment-time parameterization. Deployment rules live under Deployment pipelines, which is not cited.
  Replacement: `- \`std-del-14\` Where an environment-specific value stays in a committed item definition, such as a semantic model's data-source path, does fabric-cicd parameterization or a post-sync step update it for each environment? [review] Applies to: a committed connection string or data-source path. Source: CICD concepts, "Release process options"; CICD concepts, "The fabric-cicd library".`
- **std-del-16 CLOSED.** Commit messages describe the change; the data effect is tried in dev or test. Updating data items: "Use commit messages to describe the changes made." No new defect.
- **std-del-18 CLOSED.** The file name is `.schedules`. Data orchestration strategy: "through .schedules files in item definitions." No new defect.

### Conflicts

- **std-arc-02 against std-arc-04 CLOSED.** The Note is real. What is medallion architecture: "No changes are allowed." Deployment model: "or use Parquet or Delta Lake." The Note does not invent a ranking. std-arc-02 now says "stores everything exactly as it arrives." No new defect.
- **std-del-05 against std-del-06 CLOSED.** Applies to now sends a copied folder to std-del-06. The existing Note still records the page tension. An agent can follow both. No new defect.
- **std-del-11 against std-del-14 CLOSED as a conflict.** std-del-11 is conditional on item-type support, so a committed value is no longer a hard failure. The "rule" gap above is a citation issue, not a conflict.
- **std-arc-15 against std-gov-02 CLOSED.** gov-02 flags resize, overage, and surge protection. arc-15 only asks about pause automation. They do not contradict. No new defect.
- **Workspace-boundary Notes CLOSED.** The old "pages do not say how to choose" is gone. Each cited page gives its own criterion, and none ranks the others. Pattern 2: "bronze and silver layers" in one workspace and gold in another, "for example where one team" manages each. The security-file Note matches CAF and Fabric solutions: "grants access to everything inside the workspace." Both sides are stated correctly.

### Headers

- **Security file CLOSED.** The opening sentence now names six pages, including the Well-Architected security page, matching the checks. The seventh table row is only the Note's CI/CD concepts page. No new defect.
- **Architecture header CLOSED for the lines checked here.** "Each check keeps the conditions that its page gives" holds for the corrected architecture lines and the sample below. I did not re-judge every unchanged architecture line outside that set.
- **Well-Architected header CLOSED.** "Implementing" is now "writing." The purge and pause sentence tells the agent not to treat those questions as instructions. No new defect.

### Danger wording

- **std-sec-05 CLOSED.** "The guidance says to" is not an order to assign roles. CAF: "Assign workspace roles to Microsoft Entra security groups." AM-4: "principle of least privilege." No new defect.
- **std-sec-10 CLOSED.** "The guidance says to create and use managed private endpoints" names the page. NS-1: "Create and use managed private endpoints for notebooks, lakehouses, and Spark job definitions." No new defect.

## 2. New lines

- **std-rel-06 PARTLY. Low.** The sentence matches Keep workloads modular: "independent pipelines, datasets, and processing stages" and "reduce the impact of failures." Applies to any new pipeline, dataset, or stage, which is wider than a large solution.
  Replacement: `- \`std-rel-06\` Is a large solution split into smaller independent pieces, such as pipelines, datasets and processing stages, so that a failure has less impact? [review] Applies to: the layout of a large solution. Source: WAF overview, "Keep workloads modular".`
- **std-sec-14 SUPPORTED.** Secret management: "dynamic retrieval at runtime." SDL: "key vault references or parameterization rules." `[flag]` is correct.
- **std-sec-15 PARTLY. Low.** The inaccessibility tradeoff is supported. Data encryption: "inaccessible until the key is restored." The page says "not all Fabric artifacts currently support CMK." "Currently" is dropped.
  Replacement: `- \`std-sec-15\` Flag a customer-managed key for a workspace; guidance: not every Fabric artifact currently supports it, and if the key is disabled or deleted, workspace data stays inaccessible until it is restored. [flag] Applies to: an encryption or key setting for a workspace. Source: WAF security, "Data encryption".`
- **std-sec-16 SUPPORTED.** 3. Fabric networking: "workspace-level private links where the required Fabric capabilities support them" and "assess the broader operational effect." `[flag]` is correct.
- **std-sec-17 SUPPORTED.** Harden workload assets: "Restrict workspace creation to admins to prevent sprawl and misconfigurations." `[flag]` is correct.
- **std-del-20 SUPPORTED.** Variable libraries: "doesn't contain anything to indicate which value set is active." `Ask:` is required. `[review]` is correct.
- **std-del-21 PARTLY. Low.** The ETL split is supported for post-deploy jobs. Automation targets: "scripts you write for post-deploy jobs." Applies to also names a post-sync script, which that sentence does not.
  Replacement: `- \`std-del-21\` Does post-deploy automation keep ETL logic in notebooks, pipelines, copy jobs or dataflows, and not inside the post-deploy script itself? [review] Applies to: a post-deploy script. Source: CICD concepts, "Automation targets".`
- **std-del-22 SUPPORTED.** Update the production app: "use the deployment pipelines API" and "not possible to update the app through the UI."
- **std-arc-17 SUPPORTED.** Historical retention: "within the last seven days" and `delta.deletedFileRetentionDuration`. The line asks; it does not order a vacuum.

## 3. Sample

Not judged in round 1. Ids: `std-sec-02`, `std-ops-01`, `std-ops-04`, `std-ops-06`; `std-sec-07`, `std-sec-08`, `std-gov-03`, `std-gov-04`; `std-del-06`, `std-del-10`, `std-del-12`, `std-del-17`; `std-arc-05`, `std-arc-10`, `std-arc-14`, `std-arc-16`.

All 16 are **SUPPORTED**. Spot checks: std-sec-02 matches "avoiding static credentials" and "Disable basic authentication"; std-sec-07 matches Item security and "does not necessarily grant permission"; std-sec-08 matches "same records or tables" and viewer RLS, CLS, and OLS; std-gov-04 matches "currently in preview"; std-del-06 matches "Copy the entire item directory"; std-arc-10 matches "read only" and "use Spark."

## 4. Danger

No check, followed literally, tells the agent to change a permission, network setting, label, tenant or capacity setting, or to delete, purge, pause, or vacuum. Flag lines name guidance. The new header sentences say those verbs are questions, not instructions. Headers say the files guide and never authorize. The only behavioral risk is std-sec-03, which can refuse a content change; that is escalation, not performing a forbidden change.

## CHECKED AND FINE

52 lines fully supported: std-sec-01, std-sec-04, std-sec-05, std-sec-06, std-sec-10, std-gov-01, std-gov-02, std-gov-07, std-gov-09, std-del-03, std-del-05, std-del-07, std-del-08, std-del-09, std-del-11, std-del-13, std-del-15, std-del-16, std-del-18, std-ops-07, std-perf-01, std-cost-03, std-cost-04, std-arc-02, std-arc-03, std-arc-04, std-arc-06, std-arc-12, std-arc-13, std-arc-15, std-sec-14, std-sec-16, std-sec-17, std-del-20, std-del-22, std-arc-17, std-sec-02, std-ops-01, std-ops-04, std-ops-06, std-sec-07, std-sec-08, std-gov-03, std-gov-04, std-del-06, std-del-10, std-del-12, std-del-17, std-arc-05, std-arc-10, std-arc-14, std-arc-16.
