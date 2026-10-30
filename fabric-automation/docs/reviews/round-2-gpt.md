# Verification round 2: GPT 6.1 Sol

Lens: platform facts against live primary sources. The reviewer had not seen round 1. It checked the claims that round 1 added or changed, then 20 more of its own choosing, and replied inline. This is the reply with the confirmed rows shortened. The disposition of each finding, including the points where the check below was itself checked, is in [round-2-findings.md](round-2-findings.md).

## Claims that were not confirmed as written

| ID | Severity | Design section | Claim | Source | Verdict | Correction proposed by the reviewer |
|---|---|---|---|---|---|---|
| R2-B-1 | High | 3.3, 3.16 | Deadlines cancel jobs, refreshes and exports | Power BI REST reference: reports | PARTLY | No export-job cancellation endpoint is documented. Attempt the supported cancellations, and drain or quarantine exports without claiming their backend execution stopped. |
| R2-B-2 | High | 3.14; decision register D-21 | The organization budget is the hard stop in D0 | GitHub docs: Copilot budgets | PARTLY | Organization budgets limit metered charges and stay alert-only unless "Stop usage when budget limit is reached" is enabled. Configure it explicitly and check it in the preflight. |
| R2-B-3 | Medium | 3.14; D-21 | D0 cannot cap parallel proxy requests | gh-aw firewall repository: `containers/api-proxy/enclave-model-budget.js` | PARTLY | The firewall offers optional signed request and token budgets, and a token-capped invocation rejects concurrent requests. S9 should establish whether the pinned gh-aw path exposes these controls. |
| R2-B-4 | Medium | 3.5 | Entra allows 20 credentials but no wildcard matching | Learn: flexible federated identity credentials | PARTLY | Standard credentials require exact matching, and flexible credentials support wildcard expressions on applications and user-assigned managed identities. Environment-only trust is a factory policy, not an absolute Entra limit. |
| R2-B-5 | Medium | 3.5 and 3.6 | The publisher's listed permissions suffice for App-pinned checks | GitHub docs: rulesets, required status checks | PARTLY | Current guidance also requires `statuses:write`, a recent check run and a pre-existing required-check association. Add these as setup prerequisites, or verify a supported route that uses checks only. |
| R2-B-6 | Medium | 3.8 | Git sync requires service principal support across every workspace item | Learn: Update From Git | PARTLY | Say "all items involved in the operation". The current reference does not state the wider workspace-level condition. |
| R2-B-7 | Medium | digest 3.2 | `executeQueries` limits are 120 a minute and 100,000 rows | Power BI REST reference: Execute Queries | PARTLY | Include one million values and 15 MB, and per-identity throttling across datasets. Reject incomplete or error-bearing responses even when the HTTP status is 200. |
| R2-B-8 | none | 3.6 | An App's success persists until it is reposted | GitHub docs: check runs | UNVERIFIABLE | Label this an assumption pending N11. The API reference does not state what happens after a review is dismissed or a team changes. |
| R2-B-9 | none | digest 3.3 | A stale `workspaceHead` specifically returns HTTP 400 | Learn: Update From Git | UNVERIFIABLE | Name `WorkspaceHeadMismatch`. The current reference does not map that error to HTTP 400. Confirm in S4. |

## Claims confirmed (28)

| ID | Design section | Claim | Source |
|---|---|---|---|
| R2-B-10 | 3.7 B3 | Release 1.4.0 of `fabric-cicd` tolerates binding failures, and the strict flag entered `main` on October 28 | `fabric-cicd` source at v1.4.0 and the commit that added the flag |
| R2-B-11 | 3.7 B4 | A semantic model's connections can be read through the item connections API | Learn: List Item Connections |
| R2-B-12 | 3.7 Network | The outbound access protection matrix and the contradictory report restriction match the current pages | Learn: availability matrix and overview |
| R2-B-13 | 3.5 | Immutable OIDC subjects apply after 2026-07-15 for creation, rename or transfer | GitHub docs: OIDC |
| R2-B-14 | 3.5, S8 | The pause and resume custom-role guidance includes `capacities/write` | Learn: pause and resume |
| R2-B-15 | 3.7 | OneLake retains deleted files for seven days, billed at the active rate | Learn: OneLake soft delete |
| R2-B-16 | 3.7 | Git recreation changes item IDs, and recycle-bin restoration preserves them | Learn: Git integration process |
| R2-B-17 | 3.6 | `Restrict updates` is documented as limiting pushes, not as preventing an API merge | GitHub docs: available rules |
| R2-B-18 | 3.6 | Any user with repository write access can enqueue a qualifying PR | GitHub docs: merge queue |
| R2-B-19 | 3.6 | Dismissal, PR edit and synchronize, and membership and team webhooks exist with the described permissions | GitHub docs: webhook events |
| R2-B-20 | 3.14 | Credit accounting is response-based, and `max-turns` limits iterations | gh-aw firewall types; gh-aw cost management |
| R2-B-21 | 3.3 | Actions supports cancelling workflow runs, and acceptance is asynchronous | GitHub docs: workflow runs |
| R2-B-22 | 3.5 | Workspace creation supports service principals and needs tenant and capacity permissions | Learn: Create Workspace |
| R2-B-23 | 3.5 | Workspace deletion supports service principals and needs workspace Admin | Learn: Delete Workspace |
| R2-B-24 | 3.6 | Definition retrieval requires item read and write permissions | Learn: Get Item Definition |
| R2-B-25 | 3.8 | Git status can return HTTP 202 as a long-running operation | Learn: Git Get Status |
| R2-B-26 | digest 3.3 | Git synchronization rejects an overlapping operation | Learn: Update From Git |
| R2-B-27 | 3.10 | `executeQueries` rejects service principals on RLS or SSO models | Power BI REST reference |
| R2-B-28 | 3.10 | `exportToFile` requires a supported capacity and excludes PPU | Power BI embedded: export to file |
| R2-B-29 | 3.10 | One export request supports at most fifty pages or visuals | Power BI embedded: export to file |
| R2-B-30 | 3.10 | Uncertified custom, R and Python visuals do not render | Power BI embedded: export to file |
| R2-B-31 | 3.10 | PNG export does not support sensitivity labels | Power BI embedded: export to file |
| R2-B-32 | 3.6 | Applicable rulesets aggregate, and the stricter overlapping requirement wins | GitHub docs: about rulesets |
| R2-B-33 | 3.6 | Bypass permissions belong to their own ruleset | GitHub docs: available rules |
| R2-B-34 | 3.6 | Approval of the latest push must come from someone other than its pusher | GitHub REST schema |
| R2-B-35 | 3.6 | Native CODEOWNERS protection can require one owner approval | GitHub docs: about code owners |
| R2-B-36 | 3.14 | GitHub App installation tokens expire after one hour | GitHub docs: authenticating as an installation |
| R2-B-37 | 3.1 | The Copilot firewall excludes MCP-server and setup-step processes | GitHub docs: customize the firewall |

## Could not verify

- R2-B-8 needs N11: no explicit primary-source guarantee of review-driven check invalidation or persistence.
- R2-B-9: the documented error code is verified, but its specific HTTP mapping is not.

Verdict: sound after corrections - 28 confirmed, 7 partly, 0 wrong or outdated, 2 unverifiable
