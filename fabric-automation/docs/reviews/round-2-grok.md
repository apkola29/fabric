# Verification round 2: Grok 4.7

Lens: consistency, logical soundness and closure of the round-1 logic fixes. The reviewer had not seen round 1. It read a frozen copy of the published commit `41a41c285a` and replied inline. This is the reply condensed. The disposition of each finding is in [round-2-findings.md](round-2-findings.md).

Summary from the reviewer: the round-1 text was added, but three of the logic fixes do not close. The state machine, the lock rule and the approval bound still contradict other sections, and two of them can admit a merge the design says cannot happen.

## Findings

| ID | Severity | Where | Evidence | Why it matters | Concrete fix |
|---|---|---|---|---|---|
| R2-A-1 | High | 04-design.md 1 (item 6), 3.6, 3.17, 4.1 row 4, scenario 11; S11; requirements FR-37 | "a sweep re-posts the check"; N11 passes if "shorter than the bound S11 sets"; S11 says "N11 sets the bound" | Requester exclusion is not native. A dismissed eligible approval leaves a green check, and RS-B still passes on the requester if they are a code owner. The sweep is specified as a re-post, not a re-evaluation, and the Members permission is not in the preflight. N11 cannot fail: any measured window sets the bound. Part 3 detects after the merge and only halts new runs. The summary, 3.17, 4.1 and scenario 11 still say the check enforces exclusion. PS-2 would still pass | Pre-declare a numeric bound. The sweep must re-read team membership and head approvals and fail the check. The preflight must assert the Members permission and a fresh sweep. Make the merge-time audit a required check that fails before the merge, not an incident after. Point 1, 3.17, 4.1, scenario 11 and FR-37 at that window |
| R2-A-2 | High | 04-design.md 3.3, 3.16 | The reconciler re-dispatches when "last event is older than the stage timeout", then ESCALATED. Cancel is "from any state". A run "ends in exactly one terminal state". Cancel leaves "a comment that says who cancelled and when" | NEEDS_INFO (7 days), APPROVAL (no timeout) and AWAITING_HUMAN (14 days) have no exemption, so the reconciler can re-dispatch or escalate a run a human is still deciding, and push commits that dismiss review. "From any state" includes MERGED and ESCALATED, so terminals are not exclusive. The deadline "quarantine" is not a terminal state. Cancel and `FACTORY_HALT` do not fail the `factory/*` checks or close the PR, so a maintainer can merge a cancelled run. APPROVAL has no reject path. STATIC_GATES, DYNAMIC_GATES and VERIFYING have no exit when the budget is exhausted | Exclude the human-wait states from the stage timeout, with their own deadlines. Make terminal writes compare-and-swap and refuse a second terminal. Cancel and halt must fail the required checks and close the PR. Add the missing failure edges, all to ESCALATED. Map CLOSED, CANCELLED and MERGED in the outcome labels, and delete "Each leaves a draft PR or a comment with a failure report", which includes DONE |
| R2-A-3 | High | 04-design.md 3.3 lifetimes and terminal table; scenario 8; requirements NFR-07 | Locks held "until the PR is merged or closed, or 72 hours". Scenario 8: "After the first merges, the second restarts". NFR-07: "no two runs mutate the same items" | The PR can stay open 14 days. After 72 hours a second run can edit the same paths and open another PR. The terminal table says locks release at the merge, which contradicts the 72-hour cap. The lock row is described as an item path, with no owner or expiry | Hold the item reservation until merge, close or cancel. If a cap remains, block new runs on paths with an open factory PR, and say so in scenario 8. Store the run ID and an expiry on the lock |
| R2-A-4 | Medium | 04-design.md 3.14, 3.16, 4.1 row 1, 4.3 | 4.3: "exceed the cap by a bounded amount". 3.14: "the factory states no bound of its own". Row 1: the proxy "is budget-capped" | 3.14, I-3, 4.1 row 13, D-21 and the NFR-09 amendment agree. These three sentences put the withdrawn D0 bound back | Say that the D0 overshoot is unbounded until S9 and that the owner must accept the figure. Drop "bounded" and "budget-capped" for D0. Say that the 3.16 dollar counters do not stop in-job proxy calls |
| R2-A-5 | Medium | 04-design.md 3.3 intents; S5; HR-7; NFR-06 | S5: "no duplicate workspace or job". Resume asks Fabric to "list workspaces" and "list job instances" | A crash after GitHub accepts a PR, check or comment and before the result write is not in that procedure. S5 can pass with a duplicate PR | Add a lookup by `Factory-Run` with adopt or retry for the PR, the check and the comment, and make a duplicate PR fail S5 |
| R2-A-6 | Medium | 04-design.md 3.7, B5 and reviewer preview | The preview adds "B5 when the change is a data agent or an ontology". B5: "Publish the data agent". "Ontology steps are specified with the pack" | An ontology preview runs the data-agent publish and still has no ontology steps | Split `env.publish` into data-agent and ontology operations. Do not claim an ontology preview until the pack names the steps |
| R2-A-7 | Medium | 04-design.md 3.3, 3.12 | "a requester outside the trusted sub-group" | The R1-A-2 guards are ordered, but the predicate is never defined, so APPROVAL against TEST_AUTHORING cannot be evaluated | Define the set, where it lives and who may change it. An unknown tier fails closed before PLANNED |
| R2-A-8 | Medium | 04-design.md 3.3 lifetime 3, the CANCELLED row, 3.7 sweeper; 4.2 against 5.2 | The workspace is "torn down 24 hours after its last dynamic gate". Cancel: "at once or left to the sweeper". 5.2 marks FR-35 to FR-44 Ready, and 4.2 defers hidden checks to Phase 2 | A workspace that dies before a dynamic gate has no expiry, so the sweeper will not delete it. Cancel's "or" contradicts lifetime 3. FR-39 requires hidden checks that Phase 1 does not run | Start the expiry at creation. Cancel always tears down. Mark FR-39 partial until hidden checks exist |

## Round-1 fixes checked

- R1-A-1: NOT CLOSED. The four-part text is there, but the bound is circular, the sweep may not re-evaluate, and the merge audit is detective. Other sections still claim enforcement.
- R1-A-2: CLOSED WITH RESERVATION. The order makes T0 to T3 exclusive, but "trusted sub-group" is undefined.
- R1-A-3: CLOSED WITH RESERVATION. 3.14, I-3, 4.1 row 13, S9, D-21 and the NFR-09 amendment match. 4.3, 4.1 row 1 and 3.16 still imply a D0 bound.
- R1-A-4: NOT CLOSED. The table, the 7-day edge and the label map exist, but terminals are not exclusive, human waits race the reconciler, and the outcome sentence contradicts DONE.
- R1-A-5: CLOSED. A zero-pass task is audited, and an exclusion keeps the original denominator.
- R1-A-6: CLOSED WITH RESERVATION. No LLM runs in the rebuild and a data agent is published. The ontology is wired to the wrong step.
- R1-A-7: CLOSED. N12, 3.16, S11 and D-27 all require the evidence store to refuse overwrite, delete and retention changes.

## Checked and sound

- PLANNED tries T3, oversize and policy failure before APPROVAL, so those no longer also match TEST_AUTHORING.
- The Fabric handover (cancel the old Actions run, re-read the epoch, rebuild if the old run is not confirmed ended) is consistent with HR-12.
- The deny list of HR-8 in 3.9 covers roles, RLS and OLS, labels, schedules, connections and external URLs, and an unparsed item fails closed.
- NFR-02 and HR-3 are spike-gated on S7, not asserted. The rule of FR-36 that one lifetime must not end another holds: the end of a workspace does not close the PR.
- The success line of S9 is falsifiable: the owner must approve a measured overshoot, unlike N11.

## Could not verify

- Whether GitHub drops a required check's conclusion when the publishing App is disabled, so a halt might or might not block a merge already in review.
- Whether a team-membership event is delivered to a GitHub App that holds the Members permission. That is outside `facts.json`.
- The full decision register and landscape digest, beyond D-21, D-27 and the phrases searched.
- That 3.11's hidden-check wording matches 4.2. The contradiction above is from 4.2, 5.2 and FR-39 only.

Verdict: ready after fixes - 0 critical, 3 high, 5 medium, 0 low
