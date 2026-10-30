# Verification round 4: Gemini 4 Argon

Lens: the design text that round 3 changed, and the platform facts it rests on (a narrow closure check). The reviewer had not seen an earlier round. It read a frozen copy of the published commit `6ca7594335` and the diff of round 3, fetched the primary sources itself, and replied inline. This is the reply condensed. The disposition of each finding is in [round-4-findings.md](round-4-findings.md).

## Part 1: consistency of the edits

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R4-B-1 | Medium | Design 3.6 (Branches) | The sentence says that GitHub signs an App's commit only when no custom author or committer is given | It contradicts 3.5, which says commits are signed "if supported" and leaves verification to S11 | Say that the condition is required for bot signature verification, and that whether the mutation signs is tested in S11 |
| R4-B-2 | Medium | Design 3.3 (diagram and terminal-state table) | The diagram draws four terminal states and omits CANCELLED | The table and the prose list five, and the note under the diagram explains why edges are omitted, not why a state is | Add the state to the diagram, or say in the prose that it is omitted |
| R4-B-3 | Low | Design 4.1 (risk row 1) | "in D0 it is limited by the engine's limits and the organisation budget" | Round 3 replaced that wording in I-3, the risk row 13, 3.14, 4.3 and D-21, and left this row with the older phrasing | Name the gh-aw workflow limits |
| R4-B-4 | Low | README status line and the design header | Both describe the state as corrected after a first verification round | The brief, the reviews index and the log record more rounds | Point both at the verification rounds that were run |

## Part 2: platform facts, checked against primary sources

| ID | Claim | Verdict | Source |
|---|---|---|---|
| R4-B-F1 | An App can be the required source of a status check only with statuses write, a recent check run and an association with a pre-existing required check in the ruleset, and no order is given | CONFIRMED | [Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |
| R4-B-F2 | Success, skipped and neutral count as passing, a check and a commit status with the same name must both pass, and only the latest commit counts | CONFIRMED | [Troubleshooting required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks) |
| R4-B-F3 | People with write permission and the author can change the stage of a pull request, and no one can merge a draft until it is marked ready | CONFIRMED | [Changing the stage of a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-stage-of-a-pull-request) |
| R4-B-F4 | The REST call that updates a pull request has no draft parameter | CONFIRMED | [REST API endpoints for pull requests](https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request) |
| R4-B-F5 | GraphQL has `convertPullRequestToDraft` and `markPullRequestReadyForReview` | CONFIRMED | [GraphQL reference, pulls](https://docs.github.com/en/graphql/reference/pulls) |
| R4-B-F6 | `createCommitOnBranch` authors the commit as the credential's owner, cannot set the author or committer, and signs it "if supported" | CONFIRMED | [GraphQL reference, commits](https://docs.github.com/en/graphql/reference/commits#createcommitonbranch) |
| R4-B-F7 | gh-aw: `max-ai-credits` (default 1000, a hard stop, one credit is one US cent, best-effort pricing), `max-daily-ai-credits` and `max-turns` (default 500) | CONFIRMED, with a note: the frontmatter reference says the daily cap is disabled when omitted, and the cost page says 5,000 per workflow per day. The design states no default | [frontmatter reference](https://raw.githubusercontent.com/github/gh-aw/main/docs/src/content/docs/reference/frontmatter.md) and [cost management](https://raw.githubusercontent.com/github/gh-aw/main/docs/src/content/docs/reference/cost-management.md) |
| R4-B-F8 | The experimental enclave settings for model requests and tokens are advisory, not enforced | CONFIRMED | [enclaves](https://raw.githubusercontent.com/github/gh-aw/main/docs/src/content/docs/experimental/enclaves.md) |
| R4-B-F9 | The firewall proxy adds usage after a response, refuses later requests once the total reaches the cap, and has an absolute ceiling of 10,000 | CONFIRMED | [ai-credits-guard.js](https://raw.githubusercontent.com/github/gh-aw-firewall/main/containers/api-proxy/guards/ai-credits-guard.js) |
| R4-B-F10 | The membership event covers a member added or removed, the team event covers created, deleted, edited and repository access changes, and both need the Members permission | CONFIRMED | [Webhook events and payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads) |
| R4-B-F11 | The git-integration skill says that connecting with a folder that does not exist fails with a 404 `GitProviderResourceNotFound` | CONFIRMED | [the skill](https://raw.githubusercontent.com/microsoft/skills-for-fabric/main/plugins/fabric-skills/skills/git-integration-operations-cli/SKILL.md) |
| R4-B-F12 | The Learn reference for Git - Connect lists five common error codes and none for a missing folder | CONFIRMED | [Git - Connect](https://learn.microsoft.com/en-us/rest/api/fabric/core/git/connect) |

## Checked and sound

- The old ideas that round 3 replaced no longer appear as facts or controls in any document: the draft as a control, the persistence of a failed check after the App stops, the canary posted before the ruleset exists, the gh-aw credit cap called soft, the 404 stated as an API fact, member changes called team events, and the claim that GitHub signs as the App.
- Spikes S3, S4, S9 and S11 agree with the N-tests and prose they refer to, and every section reference points at text that supports it.
- The run lifecycle in 3.3 is consistent: working states are defined once, the deadline counts working-state time only, the lock rows carry the run ID and then the PR number, and the terminal table agrees with the rules.

## Could not verify

- What GitHub does at run time when a failed check run is left by a suspended App, which permission `convertPullRequestToDraft` needs, whether `Restrict updates` blocks an App's API merge, and whether commits made with the mutation verify under the signed-commit rule (all S11).
- The actual error answer of `git/connect` for a missing folder (S4), and live service-principal behaviour for the recoverable-item delete and for outbound access protection with reports (S2).

Verdict from the reviewer: 0 critical, 0 high, 2 medium, 2 low.
