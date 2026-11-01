# First verification of the reference pack, slice P2: security-and-governance.md and delivery-and-lifecycle.md (Gemini 4 Argon)

The reply as it came back, with the agent's own header removed. It judged every check and every note of the two files against the text of the pages. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

# Slice P2 Verification Report (`security-and-governance.md` and `delivery-and-lifecycle.md`)

## 1. Source Integrity, Headers, Citations, and Special Focus Checks

### Source File Hashes and Dates
- All 16 extracted source files in `pack\sources\` match the SHA-256 hashes recorded at the end of `DRAFT-NOTES.md`.
- Every `Updated` date in the `Sources` tables of `security-and-governance.md` (6 sources) and `delivery-and-lifecycle.md` (3 sources) matches the `MS.DATE` header of its extracted source file.
- Plain ASCII and exposure rules (straight quotes, no IP-like dotted quads, no GUIDs, no letter-plus-digit control codes such as `PA-1` or `NS-1`, sentence length `<= 35` words, and `<= 12` consecutive source words) hold across all 37 checks and 4 `Note:` lines in both files.

### Header Paragraph Verification
- **`security-and-governance.md` header claims**:
  1. *"The baseline page is based on version 1.0 of the Microsoft cloud security benchmark and may contain outdated guidance"* — **SUPPORTED**. Source: `security-benchmark-azure-baselines-fabric-security-baseline.md`, `# Azure security baseline for Microsoft Fabric` (Important box): `"based on a previous version of Microsoft Cloud Security Benchmark (v1.0)"` and `"may contain outdated guidance."`
  2. *"the Well-Architected security page calls the baseline a starting point, not a checklist"* — **SUPPORTED**. Source: `azure-well-architected-microsoft-fabric-security.md`, `## Start with a baseline`: `"don't treat it as a checklist; instead, treat it as a starting point"`.
  3. *"The adoption roadmap page says it is not a comprehensive reference for data governance"* — **SUPPORTED**. Source: `power-bi-guidance-fabric-adoption-roadmap-governance.md`, `# Microsoft Fabric adoption roadmap: Governance`: `"it's not a comprehensive reference for data governance."`
  4. *"Baseline controls are cited by section and title, without their control codes"* — **PARTLY** followed in the file body: 5 of the 6 `Baseline` citations (`std-sec-05`, `std-sec-10`, `std-sec-12`, `std-sec-13`, `std-gov-01`) include both the section heading and `(control "<title>")`, and both exist on the page (`## Asset Management` -> `### AM-4: Limit access to asset management`, `### AM-3: Ensure security of asset lifecycle management`; `## Network Security` -> `### NS-1: Establish network segmentation boundaries`; `## Data Protection` -> `### DP-1: Discover, classify, and label sensitive data`; `## Logging and Threat Detection` -> `### LT-3: Enable logging for security investigation`). However, `std-sec-06` cites `Baseline, "Privileged access"` without `(control "Separate and limit highly privileged/administrative users")` (see finding below). Also, the first sentence of the header lists five source pages (`"Checks drawn from Fabric security fundamentals, Security in Microsoft Fabric, the Azure security baseline for Fabric and two governance pages"`) and omits the sixth table source (`WAF security`).
- **`delivery-and-lifecycle.md` header claims**:
  1. *"The concepts page says that not every recommendation applies to every project, so choose the practices that match the solution's scale, governance requirements and release process"* — **SUPPORTED**. Source: `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `# Fabric CI/CD concepts and best practices`: `"Not every recommendation applies to every project; use the guidance to choose"`.

### Summary of Special Focus Areas for Slice P2
1. **Tags in `security-and-governance.md`**:
   - `std-sec-09` (under `## Workspace and item boundaries`) is a security/access-boundary check (`std-sec-*`) that is tagged `[review]` instead of `[flag]`, contradicting the file header (`"so these checks say to flag a change and name the guidance"`) and `well-architected.md` `std-sec-04` (`[flag]`).
   - Conversely, `std-gov-09` is tagged `[flag]` even though it covers business-critical content needing `"data quality verifications and documentation"`, which is a `[review]` topic (not a refused security, permission, network, sensitivity-label, or tenant-setting change).
2. **`[gate]` checks in `delivery-and-lifecycle.md`**:
   - `std-del-04` (`[gate]`) and `std-del-05` (`[gate]`) are genuinely decidable by a deterministic program from the item definition folders and `.platform` diff.
   - `std-del-07` (`[gate]`) and `std-del-11` (`[gate]`) are **not** deterministically decidable by an offline program (see High findings below).
   - `std-del-15` (`[gate]`) is deterministically decidable on repository files only if its second clause checks that workflow files reference secret variables rather than verifying the external Git provider's secret store.
3. **Numbers, file names, and setting names**:
   - Numbers (`1.2`, `1.0`, `1.1` in `std-sec-11`) and names (`.platform`, `logicalId`, `notebook-settings.json`, `terraform.tfvars`, `SqlPackage`, `variable library`, `value sets`) match the source pages, **except** in `std-del-18`, where the source file name `.schedules` lost its leading period and became `schedules files` (see Medium finding below).

---

## 2. Line-by-Line Findings (Ranked by Impact on an Agent)

### High Impact

#### 1. `std-del-07` (`delivery-and-lifecycle.md`) — `WRONG TAG` and `PARTLY`
- **Current line**:
  `- \`std-del-07\` Does a new notebook that depends on another item include a notebook-settings.json file for auto-binding, and do items without auto-binding have a post-sync script to restore their relations? [gate] Applies to: a new notebook, pipeline or other item with dependencies. Source: CICD concepts, "Auto-binding support"; CICD concepts, "Continuous integration development process".`
- **Defect**:
  1. **`WRONG TAG` (`[gate]`)**: No deterministic offline program can decide from item definitions (a) which Fabric item types currently lack auto-binding support (the source states auto-binding maturity varies and links out to an external support matrix) or (b) whether arbitrary script code in a repository semantically restores item relations after sync.
  2. **`PARTLY` (lost condition)**: The cited section states that auto-binding only works between items in the **same workspace**; cross-workspace dependencies cannot use `notebook-settings.json` auto-binding and must use variable-library item references instead. Dropping `"in the same workspace"` would cause a gate/agent to require `notebook-settings.json` on notebooks whose dependencies cross workspaces.
- **Evidence**:
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Auto-binding support`: `"Auto-binding maturity varies."`
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Auto-binding support`: `"Fabric only supports auto-binding behavior between items that exist in the same"` (workspace).
- **Suggested replacement**:
  `- \`std-del-07\` Does a new notebook with same-workspace dependencies include notebook-settings.json for auto-binding, and do items without auto-binding use a post-sync script to restore relations? [review] Applies to: a new notebook, pipeline or other item with dependencies. Source: CICD concepts, "Auto-binding support"; CICD concepts, "Continuous integration development process".`

#### 2. `std-del-11` (`delivery-and-lifecycle.md`) — `WRONG TAG` and `MISLEADING`
- **Current line**:
  `- \`std-del-11\` Do items read environment-specific settings, such as database server and name, from a variable library with value sets for test and production, instead of hardcoding them? [gate] Applies to: a notebook, pipeline, copy job or dataflow that connects to a data source. Source: CICD concepts, "Variable libraries"; CICD concepts, "Parameterization for environment-specific settings".`
- **Defect**:
  1. **`WRONG TAG` (`[gate]`)**: A deterministic program cannot reliably distinguish environment-specific string literals from non-environment constants across arbitrary notebook/pipeline/dataflow definitions, nor must value sets be named `test` and `production` (`### Fabric CI/CD projects`: `"Your project can use other common names, such as qa, uat, or ppe"`).
  2. **`MISLEADING` (lost condition / conflict with `std-del-13`, `std-del-14`, and Note 4)**: `CICD concepts` qualifies variable libraries with `"Whenever possible, use variable libraries"` (`### Workspace item types`, because not all item types support them) and `"variable libraries should usually be your first choice"` (`### Deployment pipelines`), while also supporting deployment rules (`std-del-13`) and `fabric-cicd` `parameter.yml` replacement (`std-del-14`). Making `std-del-11` an unconditional `[gate]` causes an automated gate to reject valid solutions that parameterize via `parameter.yml` or deployment rules.
- **Evidence**:
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Deployment pipelines`: `"However, variable libraries should usually be your first choice for parameterization"`
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Workspace item types`: `"Whenever possible, use variable libraries to manage parameterization across environments."`
- **Suggested replacement**:
  `- \`std-del-11\` Do items read environment-specific settings, such as database server and name, from a variable library with value sets per environment whenever possible, instead of hardcoding them? [review] Applies to: a notebook, pipeline, copy job or dataflow that connects to a data source. Source: CICD concepts, "Variable libraries"; CICD concepts, "Parameterization for environment-specific settings"; CICD concepts, "Workspace item types".`

---

### Medium Impact

#### 3. `std-del-18` (`delivery-and-lifecycle.md`) — `PARTLY` / `MISLEADING` (wrong file name)
- **Current line**:
  `- \`std-del-18\` Does the solution expose one top-level pipeline or notebook that populates all lakehouses, with refresh schedules kept in the items' schedules files? [review] Applies to: a new lakehouse solution or a new refresh schedule. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".`
- **Defect**:
  - Drops the leading period from the Fabric item definition file name `.schedules`, writing `schedules files` instead of `.schedules files` (whereas `std-del-04` preserves the leading period in `.platform`). An agent trusting `std-del-18` will look for or create `schedules` instead of `.schedules`.
- **Evidence**:
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Data orchestration`: `"extend the item definition of notebooks and pipelines by using a .schedules file."`
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Data orchestration strategy`: `"Configure ETL items with scheduled jobs for ongoing data refresh through .schedules files"`
- **Suggested replacement**:
  `- \`std-del-18\` Does the solution expose one top-level pipeline or notebook that populates all lakehouses, with refresh schedules kept in the items' .schedules files? [review] Applies to: a new lakehouse solution or a new refresh schedule. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".`

#### 4. `std-sec-09` (`security-and-governance.md`) — `WRONG TAG` and `MISLEADING`
- **Current line**:
  `- \`std-sec-09\` Avoid creating a workspace just to mirror an access boundary that item permissions or OneLake security already enforce reliably; separate workspaces when administration, deployment or network controls differ materially. [review] Applies to: a workspace layout. Source: CAF governance, "2. Fabric data security".`
- **Defect**:
  1. **`WRONG TAG` (`[review]` instead of `[flag]`)**: `std-sec-09` sits in `security-and-governance.md` under `## Workspace and item boundaries` with a `std-sec-*` ID and governs security/access boundaries and network controls. The file header states that checks in this file on security, permission, and network boundaries say to flag a change (`[flag]`), and `well-architected.md` `std-sec-04` tags workspace isolation boundary changes `[flag]`. Writing `std-sec-09` as an imperative `[review]` check instructs an agent to enforce workspace boundary decisions rather than flagging them.
  2. **`MISLEADING` (cross-pack conflict without caveat in this file)**: `architecture-patterns.md` (Note 1) documents that `CAF governance, "2. Fabric data security"` is in unresolved tension with `Medallion, "Deployment model"` (`"We recommend you have a separate workspace for each lakehouse"`) and `CICD concepts, "Fabric solutions"` (`"The best way to enforce the security requirement is to split the solution"` into staging and presentation workspaces because workspace roles grant access to everything in the workspace). In `security-and-governance.md`, `std-sec-09` states the `CAF governance` side alone as an unqualified rule with no `Note:`.
- **Evidence**:
  - `azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, `## 2. Fabric data security`: `"Don't create extra workspaces only to reproduce boundaries that item permissions"` (or OneLake security can enforce reliably).
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Fabric solutions`: `"The best way to enforce the security requirement is to split the solution"`
- **Suggested replacement**:
  `- \`std-sec-09\` Flag a workspace layout change; guidance: avoid extra workspaces for boundaries that item permissions or OneLake security enforce reliably, and separate workspaces when administration, deployment or network controls differ materially. [flag] Applies to: a workspace layout. Source: CAF governance, "2. Fabric data security".`

#### 5. `std-gov-07` (`security-and-governance.md`) — `PARTLY` / `MISLEADING`
- **Current line**:
  `- \`std-gov-07\` For a medium-risk release, are source control, development isolation and validation before production required; for high risk, source control, production isolation, independent validation and a tested recovery process? [review] Applies to: a release with several contributors, frequent releases or a critical business process. Source: CAF governance, "5. Deployment".`
- **Defect**:
  - For the high-risk pattern, the source states `"An independent person or automated control should validate the release"`, and applies it when a failed release can materially disrupt `"an important business process or organizational reporting."` Compressing `"An independent person or automated control"` to `"independent validation"` drops `"or automated control"`, misleading a reviewer or agent into requiring a separate human/team validator even when an automated validation control is in place. It also omits `"or organizational reporting"` from `Applies to`.
- **Evidence**:
  - `azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, `## 5. Deployment`: `"An independent person or automated control should validate the release."`
  - `azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, `## 5. Deployment`: `"materially disrupt an important business process or organizational reporting."`
- **Suggested replacement**:
  `- \`std-gov-07\` Does a medium-risk release require source control, development isolation and pre-production validation, and a high-risk release require source control, production isolation, independent person or automated validation, and a tested recovery process? [review] Applies to: a release with several contributors, frequent releases, or an important business process or reporting. Source: CAF governance, "5. Deployment".`

#### 6. `std-gov-09` (`security-and-governance.md`) — `WRONG TAG` and `PARTLY`
- **Current line**:
  `- \`std-gov-09\` Ask: does the change involve personally identifiable, regulated or critical data, which the page says usually faces stricter governance requirements, such as data quality verifications and documentation? [flag] Applies to: a change that handles sensitive or business-critical content. Source: Roadmap governance, "Decision criteria"; Roadmap governance, "Key Fabric governance decisions".`
- **Defect**:
  1. **`WRONG TAG` (`[flag]`)**: In this pack, `[flag]` means the factory refuses and escalates the change because it modifies security, permissions, network, sensitivity labels, or tenant settings (`std-sec-12` already flags sensitivity labels with `[flag]`, and `std-gov-01` already flags data sensitivity level changes with `[flag]`). Tagging `std-gov-09` `[flag]` when it applies to `business-critical content` needing `data quality verifications and documentation` would make an agent refuse and escalate normal data-quality and documentation work on critical models/reports (which `std-ops-02`, `std-gov-03`, and `std-gov-07` treat as `[review]`).
  2. **`PARTLY` (imprecise merge)**: In `Decision criteria`, PII/regulated data `"should be subject to stricter governance requirements"`, whereas critical data `"is usually subject to stricter governance requirements"`, and in `Key Fabric governance decisions`, `"such as data quality verifications and documentation"` is stated specifically for `"critical content"`.
- **Evidence**:
  - `power-bi-guidance-fabric-adoption-roadmap-governance.md`, `### Decision criteria`: `"Critical data is usually subject to stricter governance requirements."`
  - `power-bi-guidance-fabric-adoption-roadmap-governance.md`, `### Key Fabric governance decisions`: `"Additional requirements applicable to critical content, such as data quality verifications and documentation"`
- **Suggested replacement**:
  `- \`std-gov-09\` Ask: does the change involve personally identifiable, regulated or critical data, which faces stricter governance requirements, including data quality verifications and documentation for critical content? [review] Applies to: a change that handles sensitive or business-critical content. Source: Roadmap governance, "Decision criteria"; Roadmap governance, "Key Fabric governance decisions".`

#### 7. `std-del-03` (`delivery-and-lifecycle.md`) — `PARTLY` / `MISLEADING`
- **Current line**:
  `- \`std-del-03\` Does a validation pipeline run on every new pull request, checking files, running tests and validating item definitions before review is complete, separate from the release pipeline? [review] Applies to: a workflow definition in the repository. Source: CICD concepts, "Azure Pipelines workflows"; CICD concepts, "How do you develop Fabric CI/CD workflows?".`
- **Defect**:
  - Turns a permissive capability (`"A validation pipeline can run any time a developer creates a new pull request"`) into an unconditional requirement (`"Does a validation pipeline run on every new pull request"`), and turns the disjunctive list `"check files, run tests, or validate item definitions"` (`or`) into a conjunctive requirement (`checking files, running tests and validating item definitions`). It also generalizes a statement from `### Azure Pipelines workflows` across all workflow definitions.
- **Evidence**:
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Azure Pipelines workflows`: `"A validation pipeline can run any time a developer creates a new"` (pull request).
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Azure Pipelines workflows`: `"to check files, run tests, or validate item definitions before reviewers approve"`
- **Suggested replacement**:
  `- \`std-del-03\` Can a validation pipeline run on a new pull request to check files, run tests or validate item definitions before merge approval, separate from the release pipeline? [review] Applies to: a workflow definition in the repository. Source: CICD concepts, "Azure Pipelines workflows"; CICD concepts, "How do you develop Fabric CI/CD workflows?".`

---

### Low Impact

#### 8. `std-sec-06` (`security-and-governance.md`) — `WRONG CITATION` and `PARTLY`
- **Current line**:
  `- \`std-sec-06\` Ask: are workspace and tenant administrator assignments limited, and is privileged identity management used so elevated rights are active only when needed? [flag] Applies to: a change that adds an administrator or delegates settings. Source: WAF security, "Harden workload assets"; Baseline, "Privileged access".`
- **Defect**:
  1. **`WRONG CITATION` (missing control title)**: The file header states `"Baseline controls are cited by section and title, without their control codes"`, and all other 5 `Baseline` citations include `(control "<title>")`. `std-sec-06` cites `Baseline, "Privileged access"` without `(control "Separate and limit highly privileged/administrative users")`.
  2. **`PARTLY` (scope vs check mismatch)**: `Applies to: a change that adds an administrator or delegates settings` includes `"or delegates settings"`, which comes from `PA-1` (`"Exercise caution and care when delegating settings to capacity and workspace Admins"`), but the check sentence itself omits any mention of delegating settings.
- **Evidence**:
  - `security-benchmark-azure-baselines-fabric-security-baseline.md`, `## Privileged access`: `"### PA-1: Separate and limit highly privileged/administrative users"`
  - `security-benchmark-azure-baselines-fabric-security-baseline.md`, `### PA-1: Separate and limit highly privileged/administrative users`: `"Exercise caution and care when delegating settings to capacity and workspace Admins"`
- **Suggested replacement**:
  `- \`std-sec-06\` Ask: are workspace and tenant administrator assignments limited, with caution when delegating settings, and is privileged identity management used so elevated rights are active only when needed? [flag] Applies to: a change that adds an administrator or delegates settings. Source: WAF security, "Harden workload assets"; Baseline, "Privileged access" (control "Separate and limit highly privileged/administrative users").`

#### 9. `std-gov-02` (`security-and-governance.md`) — `PARTLY`
- **Current line**:
  `- \`std-gov-02\` Flag a change that resizes a shared capacity, alters overage settings or weakens surge protection; guidance: central administration and an approval process for changes that raise cost or affect other data domains. [flag] Applies to: infrastructure code or settings for a shared capacity. Source: CAF governance, "1.2 Permissions".`
- **Defect**:
  - `Applies to: infrastructure code or settings for a shared capacity` adds `"infrastructure code"`, which does not appear anywhere in `CAF governance`. Moreover, section `1.2 Permissions` is specifically about aligning administrative authority with financial accountability (`"Participating data domains should not receive unrestricted authority to resize the Fabric capacity, change overage settings, or weaken surge protection"`), whereas capacity scaling decisions live in `1.3 Capacity changes`.
- **Evidence**:
  - `azure-cloud-adoption-framework-data-fabric-governance-unified-data-platform.md`, `### 1.2 Permissions`: `"Participating data domains should not receive unrestricted authority to resize the Fabric capacity"`
- **Suggested replacement**:
  `- \`std-gov-02\` Flag a change that gives a domain unrestricted authority to resize a shared capacity, alter overage settings or weaken surge protection; guidance: use central administration and an approval process. [flag] Applies to: permissions or settings for a shared capacity. Source: CAF governance, "1.2 Permissions".`

#### 10. `std-del-09` (`delivery-and-lifecycle.md`) — `PARTLY` ("Applies to" broader than cited source)
- **Current line**:
  `- \`std-del-09\` Do development and test items use their own data sources, with test as similar to production as possible, so that production is not loaded by their queries? [review] Applies to: a connection in a semantic model, dataflow or pipeline. Source: Lifecycle, "Connect different stages to different databases"; Lifecycle, "Use deployment rules with a real-life data source".`
- **Defect**:
  - `Applies to: a connection in a semantic model, dataflow or pipeline` names `dataflow` and `pipeline`, neither of which appears in the cited `Lifecycle` sections (`fabric-cicd-best-practices-cicd.md` never mentions dataflows or data pipelines; `Connect different stages to different databases` only mentions `semantic models` and databases). Either cite `CICD concepts, "Fabric CI/CD projects"` / `"Variable libraries"` alongside `Lifecycle`, or narrow `Applies to` to what `Lifecycle` states.
- **Evidence**:
  - `fabric-cicd-best-practices-cicd.md`, `### Connect different stages to different databases`: `"overload it with queries generated by BI creators for their development or test"` (semantic models).
- **Suggested replacement**:
  `- \`std-del-09\` Do development and test items use their own data sources, with test as similar to production as possible, so that production is not loaded by their queries? [review] Applies to: a data source connection in a semantic model or stage. Source: Lifecycle, "Connect different stages to different databases"; Lifecycle, "Use deployment rules with a real-life data source".`

#### 11. `std-del-13` (`delivery-and-lifecycle.md`) — `WRONG TAG` (missing `Ask:`)
- **Current line**:
  `- \`std-del-13\` If a semantic model is promoted through a deployment pipeline, are production deployment rules set for its data sources and parameters? [review] Applies to: a semantic model in a deployment pipeline. Source: Lifecycle, "Set rules to ensure production stage availability".`
- **Defect**:
  - Deployment pipeline rules are configured on the deployment pipeline stage in the Fabric service (tenant state), not inside the semantic model's Git item definition (`CICD concepts`, `### Release process options`: `"Setting up a deployment pipeline always requires some degree of manual configuration"`). Under the pack's format rules, a check that cannot be decided from the branch/PR alone and requires knowledge of the tenant must start with `Ask:`.
- **Evidence**:
  - `fabric-cicd-best-practices-cicd.md`, `### Set rules to ensure production stage availability`: `"Make sure that you set production deployment rules for data sources and parameters"`
- **Suggested replacement**:
  `- \`std-del-13\` Ask: if a semantic model is promoted through a deployment pipeline, are production deployment rules set for its data sources and parameters? [review] Applies to: a semantic model in a deployment pipeline. Source: Lifecycle, "Set rules to ensure production stage availability".`

#### 12. `std-del-14` (`delivery-and-lifecycle.md`) — `PARTLY`
- **Current line**:
  `- \`std-del-14\` Where an environment-specific value stays in a committed item definition, such as a semantic model's data-source path, is there a rule or post-sync step that updates it for each environment? [review] Applies to: a committed connection string or data-source path. Source: CICD concepts, "Release process options"; CICD concepts, "The fabric-cicd library".`
- **Defect**:
  - `std-del-14` cites `CICD concepts, "The fabric-cicd library"`, where `fabric-cicd` updates committed environment-specific values **during deployment using `parameter.yml` parameterization** — which `Release process options` explicitly contrasts with a post-sync job (`"Compare this to Git synchronization, which pushes environment-specific settings... and then requires additional automation after an Update from Git operation"`). Yet the check sentence only asks for `"a rule or post-sync step"` and omits deployment-time parameterization (`parameter.yml`).
- **Evidence**:
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Release process options`: `"fabric-cicd supports parameterization, which makes it possible to dynamically update environment-specific settings"`
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### The fabric-cicd library`: `"Use the second file, named parameter.yml, to configure parameterization to manage environment-specific settings"`
- **Suggested replacement**:
  `- \`std-del-14\` Where an environment-specific value stays in a committed item definition, such as a semantic model's data-source path, does deployment parameterization, a rule or a post-sync step update it per environment? [review] Applies to: a committed connection string or data-source path. Source: CICD concepts, "Release process options"; CICD concepts, "The fabric-cicd library".`

#### 13. `std-del-15` (`delivery-and-lifecycle.md`) — `PARTLY` / `WRONG TAG` precision on `[gate]`
- **Current line**:
  `- \`std-del-15\` Does the branch exclude files that hold sensitive credentials, for example terraform.tfvars with a service principal client secret, with workflow secrets kept in the Git provider's secret features? [gate] Applies to: any file added to the repository, including workflow and infrastructure files. Source: CICD concepts, "Terraform for project infrastructure"; CICD concepts, "Security best practices"; CICD concepts, "Azure Pipelines workflows"; CICD concepts, "GitHub Actions workflows".`
- **Defect**:
  - Tagged `[gate]`. A deterministic check on the repository branch can verify that `terraform.tfvars` and credential files are excluded and that workflow YAML files reference secret variables instead of hardcoding secrets, but an offline `[gate]` cannot inspect the Git provider's external secret store (Azure DevOps variable groups or GitHub repository/environment settings) to confirm secrets are kept there. Rewording the second clause to check how workflow files reference secrets makes `[gate]` strictly accurate.
- **Evidence**:
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Terraform for project infrastructure`: `"add a .gitignore entry so that you never upload terraform.tfvars to a Git"`
  - `fabric-fundamentals-understand-best-practices-fabric-cicd.md`, `### Security best practices`: `"Never commit files with sensitive credentials to Git."`
- **Suggested replacement**:
  `- \`std-del-15\` Does the branch exclude files that hold sensitive credentials, for example terraform.tfvars with a service principal client secret, and reference workflow secrets from the Git provider instead of hardcoding them? [gate] Applies to: any file added to the repository, including workflow and infrastructure files. Source: CICD concepts, "Terraform for project infrastructure"; CICD concepts, "Security best practices"; CICD concepts, "Azure Pipelines workflows"; CICD concepts, "GitHub Actions workflows".`

#### 14. `std-del-16` (`delivery-and-lifecycle.md`) — `PARTLY` ("Applies to" broader than cited source)
- **Current line**:
  `- \`std-del-16\` For a change to a data item definition, does the description say what it does to existing data, and was it tried first in dev or test with test data? [review] Applies to: a lakehouse, warehouse or other item that stores data. Source: Lifecycle, "Updating data items".`
- **Defect**:
  - `Applies to: a lakehouse, warehouse or other item that stores data` names `lakehouse` and `warehouse`, neither of which appears anywhere in `Lifecycle` (`fabric-cicd-best-practices-cicd.md` simply says `"Data items are items that store data"`). Also, the section says `"Know in advance what the changes are and what their impact might be on the existing data. Use commit messages to describe the changes made"`, which the check merges into requiring the description to state what it does to existing data.
- **Evidence**:
  - `fabric-cicd-best-practices-cicd.md`, `### Updating data items`: `"Know in advance what the changes are and what their impact might be"`
  - `fabric-cicd-best-practices-cicd.md`, `### Updating data items`: `"Use commit messages to describe the changes made."`
- **Suggested replacement**:
  `- \`std-del-16\` For a change to a data item definition, do commit messages describe the change and was its effect on existing data tried first in dev or test with test data? [review] Applies to: an item that stores data. Source: Lifecycle, "Updating data items".`

---

## 3. Verification of `Note:` Lines in Slice P2

The brief refers to "the 5 `Note:` lines" in Slice P2; in the pack as drafted, `security-and-governance.md` has **0** `Note:` lines and `delivery-and-lifecycle.md` has **4** `Note:` lines (4 in Slice P2 + 4 in Slice P1 = 8 across the pack). If a 5th `Note:` line was expected in `security-and-governance.md`, the missing `Note:` is either the cross-page workspace-boundary tension on `std-sec-09` (documented in `architecture-patterns.md` Note 1) or the intra-page contradiction in `fabric-security-security-overview.md` (`### Workspace roles`), where the prose states `"Users with a viewer role... can't access Fabric items"` while the `Viewer` row in the table immediately below states `"Can see all the items in the workspace"`.

All 4 `Note:` lines in `delivery-and-lifecycle.md` are **SUPPORTED** (each tension is real and both sides are accurately stated and cited):

1. **Note 1 (`delivery-and-lifecycle.md`, under `## Git integration and branching`)** — **SUPPORTED**:
   - Side 1 (`CICD concepts`, `### Feature workspaces`): `"don't directly update items or run Commit to Git operations in the dev workspace."`
   - Side 2 (`CICD concepts`, `### Release process options`): `"In the simplest development scenario, you can make direct updates to items"` (in the dev workspace and run `Commit to Git`).
2. **Note 2 (`delivery-and-lifecycle.md`, under `## Item definitions and dependencies`)** — **SUPPORTED**:
   - Side 1 (`CICD concepts`, `#### The role of the logicalId`): `"Never modify a logicalId value: Fabric doesn't support doing so"`
   - Side 2 (`Lifecycle`, `### Duplicate an item in a Git repository`): `"Change the logicalId to something unique for that connected workspace."`
3. **Note 3 (`delivery-and-lifecycle.md`, under `## Environments and workspace layout`)** — **SUPPORTED**:
   - Side 1 (`CICD concepts`, `### Fabric CI/CD projects`): `"the recommended practice is to isolate environments by creating a separate Fabric capacity"`
   - Side 2 (`WAF cost`, `## Consolidate costs effectively`): `"Dev/test workloads with similar requirements can share a single capacity"` (`"paused or downsized outside of working hours"`).
4. **Note 4 (`delivery-and-lifecycle.md`, under `## What to parameterize`)** — **SUPPORTED**:
   - Side 1 (`Lifecycle`, `### Use parameters for configurations that will change between stages`): `"configure parameter rules to set different values for each deployment stage."`
   - Side 2 (`CICD concepts`, `### Deployment pipelines`): `"continue to support deployment rules. However, variable libraries should usually be your first choice"`

---

## CHECKED AND FINE

- **Checks checked and found fully supported**: **23** of 37 checks
  - `security-and-governance.md` (13 of 18): `std-sec-05`, `std-sec-07`, `std-sec-08`, `std-sec-10`, `std-sec-11`, `std-sec-12`, `std-sec-13`, `std-gov-01`, `std-gov-03`, `std-gov-04`, `std-gov-05`, `std-gov-06`, `std-gov-08`
  - `delivery-and-lifecycle.md` (10 of 19): `std-del-01`, `std-del-02`, `std-del-04`, `std-del-05`, `std-del-06`, `std-del-08`, `std-del-10`, `std-del-12`, `std-del-17`, `std-del-19`
- **`Note:` lines checked and found fully supported**: **4** of 4 `Note:` lines in `delivery-and-lifecycle.md` (Note 1 under `Git integration and branching`, Note 2 under `Item definitions and dependencies`, Note 3 under `Environments and workspace layout`, Note 4 under `What to parameterize`; `security-and-governance.md` has 0 `Note:` lines).
- **Total lines CHECKED AND FINE**: **27** (23 check lines + 4 `Note:` lines).
