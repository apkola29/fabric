# Verification round 1: Gemini 4 Argon

Lens: platform facts against live primary sources. The reviewer was asked to pick the 30 claims that would break the design if wrong and check each against a primary source. It replied inline. This is the reply with the confirmed rows shortened. The disposition of each finding, including the points where the check below was itself checked, is in [round-1-findings.md](round-1-findings.md).

## Claims that were not confirmed as written

| ID | Severity | Design section | Claim | Source | Verdict | Correction proposed by the reviewer |
|---|---|---|---|---|---|---|
| R1-B-1 | Critical | 3.7 (B3), 3.9, 3.10, 5.1 (S3) | `fabric-cicd` 1.4.0 supports strict `semantic_model_binding` so bad bindings fail deployment | `src/fabric_cicd/_items/_semanticmodel.py` at tag v1.4.0 | WRONG | State that 1.4.0 only logs binding failures and lacks `enable_strict_semantic_model_binding` (a feature flag on `main`, not a `parameter.yml` setting). Either pin a commit or release that has the flag, or assert bindings in `env.postdeploy` through the item connections API. |
| R1-B-2 | High | 3.7 (Network), 4.1 (rank 3), 4.3, 7 (R1) | Workspace outbound access protection is preview and only excludes browser-side report actions | Learn: workspace outbound access protection overview | WRONG | State that it is GA except Real-Time Events, and that Power BI items other than semantic models cannot be created in a workspace with the protection, so it cannot be enabled on a Stage-1 run that deploys a report. |
| R1-B-3 | High | 3.1, 3.5, 5.1 (S2) | Entra federated credentials bind OIDC trust to the GitHub Environments `sandbox` and `publisher` | GitHub docs: OIDC, immutable subject claims | PARTLY | Add that repositories created, renamed or transferred after 2026-07-15 emit an immutable default `sub` (`repo:OWNER@OWNER-ID/REPO@REPO-ID:...`), so S2 and the preflight must match that format or customize it. |
| R1-B-4 | Medium | 3.5, 5.1 (S8) | The custom role `fcf-capacity` needs only `read`, `suspend` and `resume` on the capacity | Learn: pause and resume a capacity | PARTLY | Learn's custom-role prerequisites also list `Microsoft.Fabric/capacities/write`. S8 must test whether suspend and resume work without it. |
| R1-B-5 | Medium | 3.7, 4.3, 10; digest 3.3 | OneLake 7-day soft-delete billing, and whether Git re-creates deleted items with new IDs, are unverified | Learn: OneLake soft delete; Git integration process | PARTLY | Replace "billing effect not yet verified" with "billed at the same rate as active data for 7 days". Note that the Git process page documents re-creation under a new item ID. |
| R1-B-6 | Low | digest 2 and 3.2; requirements A12 | Data agent Git integration is preview and the ontology is unlisted; gh-aw has four active engines | Learn: Git integration overview; gh-aw engines reference | OUTDATED | The overview lists Data Agents without a preview tag and the ontology as preview. gh-aw marks the Gemini engine deprecated and adds Pi and Agy (experimental). |
| R1-B-7 | Low | 3.6 (RS-A, N2), 10 | Whether `Restrict updates` blocks an App's PR merge, and how a merge queue behaves, are unverified | GitHub docs: available rules for rulesets; managing a merge queue | PARTLY | Note that `Restrict updates` is documented as limiting who can push, and that any user with write access can add a passing PR to a merge queue, so the queue must stay off in v1. |
| R1-B-8 | High | 3.10, 5.1 (S6); digest 3.2 and 9 | Whether a service principal can publish and evaluate a data agent unattended | Learn: data agent source control | UNVERIFIABLE | None to the design: it is already gated on spike S6 and on the exception policy D-31. The source control page says service principals are supported only for ALM scenarios, and no public REST endpoint for publishing is documented. |

## Claims confirmed (22)

| ID | Design section | Claim | Source |
|---|---|---|---|
| R1-B-9 | 3.8, 3.10 | Git integration: notebooks, pipelines and lakehouses are GA; semantic models, reports, warehouses and ontologies are preview | Learn: Git integration overview |
| R1-B-10 | 3.8, 3.9 | The `.platform` v2 file stores `logicalId`, `type` and `displayName` to pair items across workspaces | Learn: Git source code format |
| R1-B-11 | 3.9, 3.10 | Semantic models use TMDL, reports use PBIR, the new ontology uses TMDL (the old one retires 2027-01-31) | Learn: ontology definition |
| R1-B-12 | 3.9; digest 3.3 | Git limits: 1,000 items, 250-character path, 25 MB file, LF line endings, foreign files in an item folder are deleted | Learn: Git integration process |
| R1-B-13 | 3.8, 3.16 | Git REST APIs support service principals, `PreferRemote` and `allowOverrideItems`, long-running operations, and the 2027-02-28 read-write rule | Learn: Update From Git |
| R1-B-14 | 3.8, 10 | A GitHub connection in Fabric needs a PAT, whereas Azure DevOps supports a service principal | Learn: Git automation |
| R1-B-15 | 3.5, 3.7 | Workspace create, delete (Admin) and assign to capacity support service principals | Learn: Create Workspace |
| R1-B-16 | 3.6, 3.7 | `getDefinition` is a long-running operation, needs item read-write, and omits sensitivity labels | Learn: Get Item Definition |
| R1-B-17 | 3.7, 3.9; digest 9 | Unified REST quotas of 500, 200 and 500 calls per minute per identity, with 429 and `Retry-After` | Learn: throttling |
| R1-B-18 | 3.10; digest 3.2 | Item APIs reject service principals for ML model and experiment, Reflex, digital twin builder and mirrored databases | Learn: item management overview |
| R1-B-19 | 3.7 | Capacity suspend and resume through Azure Resource Manager (api-version 2023-11-01) reset throttling, bill carry-forward and make items unavailable | Azure REST reference: fabric capacities |
| R1-B-20 | 3.7, 5.1 (S2) | Semantic models and reports bypass item soft delete, and lowering workspace retention can purge deleted workspaces at once | Learn: retention and recovery |
| R1-B-21 | 3.5, 3.10 | `executeQueries` needs two tenant switches, caps at 120 per minute and 100k rows, and rejects service principals on RLS and SSO | Power BI REST reference |
| R1-B-22 | 3.7, 3.10 | `exportToFile` PNG rejects PPU and labels, needs the image-export switch, caps at 50 pages, and fails uncertified, R and Python visuals | Power BI embedded: export to file |
| R1-B-23 | 3.5, 5.1 (S2) | Concurrent creation of federated credentials on one managed identity fails with HTTP 409 | Entra: workload identity federation considerations |
| R1-B-24 | 3.5, 3.6 | Rulesets pin checks to an integration ID and require last-push approval; `createCommitOnBranch` signs an App's commits when no custom author is set | GitHub GraphQL reference |
| R1-B-25 | 3.1, 3.6, 4.1 | `GITHUB_TOKEN` pushes do not trigger workflows (App tokens do); `pull_request_target` exposes base secrets; an Environment with no reviewers does not pause | GitHub docs: trigger a workflow |
| R1-B-26 | 3.1 | The Copilot cloud agent firewall covers only processes started through its shell tool, and excludes MCP servers and setup steps | GitHub docs: customize the firewall |
| R1-B-27 | 3.1, 3.2 | gh-aw defaults to strict mode, allows GitHub domains unless `network: {}`, and defaults threat detection to warn | gh-aw reference: threat detection |
| R1-B-28 | 3.7, 3.8 | `fabric-cicd` 1.4.0 supports 31 item types, `$items.*.$sqlendpoint` and `enable_hard_delete`; the bulk APIs rebind by `logicalId` | fabric-cicd documentation: parameterization |
| R1-B-29 | 3.1, 3.9, 3.10 | The local Power BI modeling MCP is GA with PBIP and TMDL, `--readonly`, `--accepteula` and service-principal auth; the hosted one is preview | Learn: Power BI authoring MCP |
| R1-B-30 | 3.10 | `semantic-link-labs` targets Fabric notebooks and provides model and report BPA, VertiPaq Analyzer and DAX impersonation | semantic-link-labs README |

## Could not verify

- **Data agent unattended publish and evaluation (R1-B-8).** The source control page says service principals are supported only for ALM scenarios, and no public REST endpoint for publishing a data agent is documented. Needs spike S6.
- **The role needed to purge a soft-deleted item.** The REST reference says workspace write, the retention page says Admin. Needs spike S2.
- **ARM `suspend` and `resume` without the `write` action (R1-B-4).** Needs spike S8.
- **Headless execution of the report authoring CLI at 0.5.0 inside a Linux container with no network.** The package exists on npm, but rendering without a display or browser inside the container needs spikes S3 and S10.

Verdict: sound after corrections - 22 confirmed, 4 partly, 3 wrong or outdated, 1 unverifiable
