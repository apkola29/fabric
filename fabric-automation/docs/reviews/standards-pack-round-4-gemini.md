# Fourth verification of the reference pack, the 24 rows changed after the third: lens A, the literal-minded agent (Gemini 4 Argon)

The reply as it came back, with the agent's own header removed. It checked the 23 checks and the note that were changed after the third verification, with a verbatim quote for each row that a program looked up in the cited section. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

std-arc-02 | S | Store everything exactly as it arrives. No changes are allowed.
std-arc-04 | S | Whenever possible, keep the data in its original format.
std-arc-15 | S | Consider the reliability effect before you pause a capacity that supports production
std-del-01 | S | with a branch policy that allows updates only through pull requests.
std-del-02 | S | If your Git repository also needs to hold workflow files,
std-del-03 | S | A validation pipeline can run any time a developer creates
std-del-06 | S | If necessary, update the logicalId and/or display names in any dependencies.
std-del-09 | S | If you're using the test stage to simulate real life data usage,
std-del-10 | S | However, you probably want all BI creators for a specific workspace
std-del-12 | S | Whenever possible, use variable libraries to manage parameterization across environments.
std-del-14 | S | For example, you can configure a semantic model with a deployment rule
std-del-17 | S | You still need to run the notebook in the target workspace
std-del-18 | S | Whether you implement a data orchestration strategy by using notebooks, pipelines,
std-gov-01 | S | address asset lifecycle management processes for potentially high impact modifications.
std-gov-04 | S | Its capacity monitoring experience is currently in preview, so the organization
std-gov-10 | S | An approved alternative should apply when a Fabric item does not
std-ops-03 | S | Test environments should use sample or anonymized data sources to avoid
std-ops-06 | S | Make sure there are escalation paths so higher severity alerts reach
std-rel-04 | S | If upstream gateways or databases go down, your workloads may stall
std-sec-10 | S | Managed private endpoints provide private connectivity for supported Fabric workloads
std-sec-14 | S | through Azure key vault references or parameterization rules rather than embedding
std-sec-15 | S | not all Fabric artifacts currently support CMK, so you may need
std-sec-16 | S | use workspace-level private links where the required Fabric capabilities support them.
note-del-4 | S | However, variable libraries should usually be your first choice for parameterization

## (a) Findings

None. All 24 rows are `S` (Supported). Under Lens A (the literal-minded agent), each of the 23 checks and `note-del-4` preserves the source conditions, open-ended examples ("such as", "for example"), modal verbs ("can", "may", "probably", "whenever possible"), preview caveats, and scoped `Applies to` clauses so that a literal-minded agent neither blocks a valid change nor passes a bad one:

- **`std-del-01`, `std-del-02`, `std-del-03`**: `std-del-01` explicitly scopes both its question ("once item definitions exist in a feature-workspace project") and its `Applies to` ("a change to item definitions under the feature-workspace process"), preventing a literal agent from blocking initial `Commit to Git` operations or simple deployment-pipeline workflows documented in `note-del-1`. `std-del-02` conditions the Git folder separation on "where the repository holds both" and multi-workspace folder separation on "each workspace of a multi-workspace solution". `std-del-03` asks whether the design "considers" a separate PR validation pipeline (`[review]`), matching the permissive "can run" in `Azure Pipelines workflows`.
- **`std-del-06`, `std-del-09`, `std-del-10`**: `std-del-06` scopes `logicalId` replacement to "When an item is duplicated in Git" (`Applies to: a copied item`) and pairs cleanly with `std-del-05` ("a copied item folder is covered by std-del-06"). `std-del-09` preserves the condition "when test simulates real-life data usage". `std-del-10` preserves both "can have the viewer role" and "BI creators probably need pipeline access" under `[flag]`.
- **`std-del-12`, `std-del-14`, `note-del-4`**: `std-del-12` adds the guard "Where the item type supports variable libraries" and includes `or another item that connects to an external source` in `Applies to`, avoiding a closed list. `std-del-14` complements `std-del-11` and `std-del-12` for cases "Where an environment-specific value stays in a committed item definition, such as a semantic model's data-source path", listing deployment rules, `fabric-cicd` parameterization, or a post-sync job after "for example". `note-del-4` accurately states both sides of the tension between `Lifecycle` (parameter rules and deployment rules) and `CICD concepts` (deployment rules are still supported, but variable libraries should usually be the first choice).
- **`std-del-17`, `std-del-18`**: `std-del-17` conditions the notebook execution check on "When a lakehouse schema change is shipped as notebook logic". `std-del-18` keeps the top-level orchestrator open ("one top-level item, such as a pipeline or notebook") while restricting `.schedules` files to "its notebooks and pipelines", matching `Data orchestration`.
- **`std-arc-02`, `std-arc-04`, `std-arc-15`**: `std-arc-02` and `std-arc-04` accurately reflect `What is medallion architecture?` and `Deployment model` (including "whenever possible" and "Delta a good choice for a relational source"), while `note-arc-1` explains the source tension between "allows no changes" and converting bronze to Parquet or Delta Lake. `std-arc-15` is scoped to `Applies to: automation that pauses a capacity` and asks whether the automation targets nonproduction environments and assesses workload unavailability before pausing a capacity that supports production.
- **`std-sec-10`, `std-sec-15`, `std-sec-16`, `std-gov-01`, `std-gov-04`, `std-gov-10`**: `std-sec-10`, `std-sec-15`, `std-sec-16`, and `std-gov-01` carry `[flag]` and preserve all source conditions ("for supported workloads and data sources", "not every Fabric artifact currently supports it, so workspace segmentation may be needed", "where supported for selected workspaces"). `std-gov-04` preserves the preview status of the Monitor hub capacity view and checks that workspace monitoring coverage is confirmed for the items in use. `std-gov-10` prevents a literal agent from blocking items that lack Git integration or deployment pipeline support under `std-gov-05` to `std-gov-07` by checking for an approved alternative when an item does not support them.
- **`std-rel-04`, `std-sec-14`, `std-ops-03`, `std-ops-06`**: `std-rel-04` uses "such as caching, queuing or a backup source" (not a closed list). `std-sec-14` flags a credential introduced by a change (`Applies to: a notebook, script or pipeline that needs a credential`), complementing `std-sec-01` (`[gate]` against embedded secrets in files) and `std-sec-02` (`[flag]` when identity-based authentication is available). `std-ops-03` matches `Don't assume everything works` and is paired with the file's bottom `Note:` on smaller test capacities. `std-ops-06` starts with "If a new job, pipeline or refresh has failure alerts", avoiding a false requirement that every non-critical job must have failure alerts.

## (b) Header Tag Paragraphs (`well-architected.md` and `delivery-and-lifecycle.md`)

Both updated header paragraphs are accurate, consistent with the round-4 tag clarification in the brief, and agree with every line tag in their respective files:

1. **`well-architected.md` header**:
   - States: `Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] a change to security, permissions, a network setting, a sensitivity label or a tenant setting, which the factory only flags, naming the guidance, and never makes. What a change itself contains, such as a secret in a file, is not a change to a setting: it is a [gate] when a program can decide it. A check that starts with Ask: needs knowledge of the tenant. A question about deleting, purging or pausing something is a question to ask about the change, never an instruction to do it.`
   - Agreement with lines in `well-architected.md`:
     - `std-sec-01` ("Are notebooks, scripts and pipeline definitions free of embedded secrets?") checks what the files in a change contain and is tagged `[gate]`, matching the header's explanation.
     - `std-sec-02`, `std-sec-04`, and `std-sec-14` concern authentication/security configuration, role assignments/sharing, and introducing a credential (Key Vault / pipeline secret configuration), and are all tagged `[flag]`.
     - All remaining checks in `well-architected.md` require architectural or operational judgement and are tagged `[review]`.
2. **`delivery-and-lifecycle.md` header**:
   - States: `Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. What a change itself contains, such as a credential file, is not a change to a setting: it is a [gate] when a program can decide it.` (The preceding paragraph also notes: `Checks that touch permissions or identity carry the flag tag, because the factory flags them and does not change them.`)
   - Agreement with lines in `delivery-and-lifecycle.md`:
     - `std-del-04` (folder naming and `.platform` file), `std-del-05` (unchanged `logicalId` on existing items), and `std-del-15` (excluding files that hold sensitive credentials such as `terraform.tfvars` and not hardcoding workflow secrets) inspect what the branch/change itself contains and are all deterministically checkable `[gate]` items.
     - `std-del-10` (who can deploy to production / workspace and pipeline permissions) and `std-del-19` (automation identity running as a user principal vs. service principal) touch permissions and identity and are tagged `[flag]`.
     - `std-del-01`, `std-del-13`, and `std-del-20` require knowledge of the tenant/repository outside the branch files and begin with `Ask:` (tagged `[review]`).
     - All other checks in `delivery-and-lifecycle.md` are tagged `[review]`.

## (c) Conflicts Between Changed Rows and Other Lines or Notes

None. In particular:
- **`std-del-01` to `std-del-03` and `note-del-1`**: `std-del-01` is explicitly scoped to a feature-workspace project once item definitions exist, which aligns with `note-del-1` (contrasting the feature-workspace process with direct updates in the dev workspace in the simplest deployment-pipeline scenario).
- **`std-del-05`, `std-del-06`, and `note-del-2`**: `std-del-05` explicitly excludes copied item folders (`a copied item folder is covered by std-del-06`), and `note-del-2` records the underlying tension between the two source pages.
- **`std-del-11`, `std-del-12`, `std-del-13`, `std-del-14`, and `note-del-4`**: `std-del-11` and `std-del-12` apply where the item type supports variable libraries; `std-del-14` applies where an environment-specific value remains in a committed item definition (such as a semantic model's data-source path); `note-del-4` explains how the two pages treat parameter/deployment rules versus variable libraries.
- **`std-gov-05` to `std-gov-07` and `std-gov-10`**: `std-gov-10` provides the source's fallback rule ("use an approved alternative to the pattern that needs them") when a Fabric item does not support Git integration or deployment pipelines required by a medium- or high-risk pattern in `std-gov-05` to `std-gov-07`.
- **`std-arc-02`, `std-arc-04`, and `note-arc-1`**: Both checks are `[review]` prompts and `note-arc-1` explicitly documents the source page's tension between "allows no changes" in bronze and storing bronze as Parquet or Delta Lake when keeping the original format is not possible.
- **`std-ops-03` and the capacity/data notes**: `std-ops-03` ("dedicated test workspaces and capacities that represent production, using sample or anonymized data sources") is contextualized by the second `Note:` at the bottom of `well-architected.md` (test capacities are often smaller than production and scaled up for load tests) and by `std-del-09` (which specifies a production-like test database specifically "when test simulates real-life data usage").
- **`std-ops-06` and `std-gov-03`**: `std-gov-03` says a business-critical data product normally has automated failure alerts and an escalation path, while `std-ops-06` asks "If a new job, pipeline or refresh has failure alerts, are they meaningful and actionable, with an escalation path...", so neither contradicts the other on less-critical workloads.
- **`std-sec-01`, `std-sec-02`, and `std-sec-14`**: `std-sec-01` gates embedded secrets in files (`[gate]`), `std-sec-02` flags static credentials when workspace identity, OAuth, managed identity, or a service principal is available (`[flag]`), and `std-sec-14` flags a credential introduced by a change where a notebook, script, or pipeline needs a credential (`[flag]`), naming the Key Vault and pipeline parameterization guidance.

## (d) Danger

None. No row in the 24 checked items, when followed literally, instructs or authorizes an agent to change a permission, network setting, sensitivity label, tenant setting, or capacity setting, or to delete, purge, pause, or recreate any resource:
- All checks on permissions, identities, network settings, encryption keys, and high-impact lifecycle modifications (`std-del-10`, `std-sec-10`, `std-sec-14`, `std-sec-15`, `std-sec-16`, `std-gov-01`) begin with `Flag ...` and carry the `[flag]` tag.
- `std-gov-01` covers only flagging high-impact modifications to access, sensitivity level, network configuration, or administrative privileges, and does not instruct an agent to delete or remove unused resources.
- `std-arc-15` (`Does capacity-pausing automation target nonproduction environments, and, before pausing a capacity that supports production, assess the unavailability of every workload on it? [review] Applies to: automation that pauses a capacity.`) is a review question applied only when a proposed change itself contains capacity-pausing automation, and the header of `architecture-patterns.md` explicitly states: `A question about pausing, deleting or vacuuming something is a question to ask about the change, never an instruction to do it.`
