# Fourth verification of the reference pack, the 24 rows changed after the third: lens B, tags, citations and the cited section as a whole (Grok 4.7)

The reply as it came back, with the agent's own header removed. It checked the 23 checks and the note that were changed after the third verification, with a verbatim quote for each row that a program looked up in the cited section. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

std-arc-02 | S | No changes are allowed
std-arc-04 | S | Whenever possible, keep the data in its original format
std-arc-15 | S | before you pause a capacity that supports production workloads
std-del-01 | S | allows updates only through pull requests
std-del-02 | S | If your Git repository also needs to hold workflow files
std-del-03 | S | A validation pipeline can run any time a developer
std-del-06 | S | If necessary, update the logicalId and/or display names
std-del-09 | S | If you're using the test stage to simulate real life
std-del-10 | M | only enabling permissions to users that are part | M: drops same-section limit that repo or pipeline access is only for content-creation users.
std-del-12 | S | When you encounter an item type that doesn't support variable libraries
std-del-14 | S | you need to run a post-sync job after an
std-del-17 | S | You still need to run the notebook in the target
std-del-18 | S | notebooks, pipelines, or another item type
std-gov-01 | S | These modifications include changes to access, data sensitivity
std-gov-04 | S | Its capacity monitoring experience is currently in preview
std-gov-10 | S | when a Fabric item does not support the standard pattern
std-ops-03 | S | Have dedicated test workspaces and capacities that represent production
std-ops-06 | S | so higher severity alerts reach the appropriate support teams
std-rel-04 | S | Mitigate these risks with caching, queuing, or backup sources
std-sec-10 | S | When private connectivity is required, data domains should use
std-sec-14 | T | Where possible, rely on workspace identity or service principals | T: a credential in a file is a gate, not a flag; same section prefers identity where possible.
std-sec-15 | S | you may need workspace segmentation to separate supported
std-sec-16 | S | where the required Fabric capabilities support them
note-del-4 | S | variable libraries should usually be your first choice

## FINDINGS

**Medium — `std-sec-14` (T).** Secret management says: "Use Azure Key Vault, with dynamic retrieval at runtime" and, in the same sentence group, "Where possible, rely on workspace identity or service principals, avoiding static credentials entirely." SDL adds key vault references or parameterization rules for pipeline definitions. The line states only the Key Vault path, so a workspace-identity design looks noncompliant. The tag is also wrong: the file header says a secret in a file is a `[gate]` when a program can decide it, and `std-sec-01` already gates embedded secrets. `[flag]` would make the factory refuse a code change it is allowed to make.

Replacement: `` `std-sec-14` Keep credentials out of item definitions; use Azure Key Vault at run time, or where possible workspace identity or a service principal, and for a pipeline a key vault reference or parameterization rule. [review] Applies to: a notebook, script or pipeline that needs a credential. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)". ``

**Medium — `std-del-10` (M).** "Manage who can deploy to production" supports specific people, production workspace permissions, the viewer role, and "you probably want all BI creators... to have access to the pipeline." The same section then says: "limit access to the repo or pipeline by only enabling permissions to users that are part of the content creation process." Applies to includes a pipeline permission, but the guidance drops that limit. Citation and `[flag]` are right.

Replacement: `` `std-del-10` Flag who can deploy to production; limit that to specific people by production workspace permissions, others can be viewers, BI creators probably need pipeline access, and repo or pipeline rights stay with content-creation users. [flag] Applies to: a workspace role or a pipeline permission. Source: Lifecycle, "Manage who can deploy to production". ``

## (b) Headers

Both changed `Tags:` paragraphs are accurate. `well-architected.md` correctly limits `[flag]` to a change to security, permissions, a network setting, a sensitivity label, or a tenant setting, and says a secret in a file is a `[gate]`. That agrees with every line in the file except `std-sec-14`. `delivery-and-lifecycle.md` agrees with its own lines: permissions and identity are `[flag]` (`std-del-10`, `std-del-19`); a credential file is `[gate]` (`std-del-15`). The two headers agree on that secret-in-file rule. They do not disagree with each other.

## (c) CONFLICTS

No pair needs a new ranking rule. `std-sec-14` disagrees with `std-sec-01` and the well-architected header; the header already resolves it against `std-sec-14`. `std-arc-02` and `std-arc-04` stay compatible because `note-arc-1` says the page does not say whether a format change counts as a change. `std-del-01` is scoped to the feature-workspace process, so `note-del-1` does not collide. `std-del-12`, `std-del-14`, and `note-del-4` fit: variable libraries first where supported; if a value stays committed, update it per environment. `std-gov-10` adds the unsupported-item case to `std-gov-05` through `std-gov-07` without overriding them. `std-del-06` and the logicalId note stay distinct: do not change an existing id; a copy gets a new one. The operations note already records that test capacities are often smaller; `std-ops-03` uses the page's own "represent production" and does not require equal size.

## (d) DANGER

None. The network, key, private-link, permission, and high-impact rows are `[flag]` questions or flags, not instructions to change a setting. `std-arc-15` asks about pausing; it does not tell the agent to pause.
