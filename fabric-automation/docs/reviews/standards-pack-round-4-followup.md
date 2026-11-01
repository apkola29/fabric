# Fourth verification of the reference pack, the follow-up on three lines

After the fourth verification two lines were rewritten: `std-sec-14`, which two families had questioned, and `std-del-10`, which one family had. The families that had questioned them checked the new text. One of them (GPT) found that `std-del-10` was still too wide, the line was split in two (`std-del-10` and a new `std-del-23`), and all three families then checked the three resulting lines. The replies are kept as they came back, with the agent's own header and the message that asked for the check removed. The author's check of each finding is in [standards-pack-findings.md](standards-pack-findings.md).

## First follow-up: `std-sec-14` and `std-del-10`, by GPT 6.1 Sol and Grok 4.7

### GPT 6.1 Sol

```
std-sec-14 | S | Where possible, rely on workspace identity or service principals,
std-del-10 | M | for a specific workspace to have access to the pipeline. | The BI-creator recommendation is workspace-specific and pipeline-only; attaching it to combined repo/pipeline access broadens its scope.
```

The tags now agree: `std-sec-01` gates embedded secrets; `std-sec-02` flags connection/authentication changes involving avoidable static credentials; `std-sec-14` reviews credential handling without authorizing security-setting changes. My round-4 tag finding is closed. The corrected texts also preserve the identity preference and add the content-creation access restriction.

However, `std-del-10` should separate its final recommendations: "restrict repo/pipeline access to content creators; probably include all BI creators for that workspace in pipeline access." The source's probable BI-creator access recommendation does not concern repository access.

Complete three-family historical closure is **UNVERIFIED**: I could not locate the other families' round-3/4 reports. The source-scope issue above is confirmed.

### Grok 4.7

```
std-sec-14 | S | Where possible, rely on workspace identity or service principals
std-del-10 | S | you probably want all BI creators for a specific
```

These two lines now agree with the Tags paragraph and with std-sec-01 and std-sec-02. A secret in a file remains a [gate] (std-sec-01). std-sec-14 is [review], not [flag]: "where possible" is a judgement about retrieval, not a setting change. std-sec-02 stays [flag] because a static-credential connection is a security setting; its OAuth and managed-identity names are outside this line and do not conflict. std-del-10 stays [flag] as a permission change.

No round-3 or round-4 point on these lines is still open. Round 3 Grok's pipeline-only parameterization note and the dropped BI-creator access are in the new text. Round 4 GPT's wrong [flag] is now [review]. Round 4 Grok's identity preference and content-creation limit are restored. Gemini marked both S in both rounds. The comma that joins content-creation users and BI creators is tighter than the page's two sentences, but both limits are present, so that point is closed.

## Second follow-up: `std-sec-14`, `std-del-10` and the new `std-del-23`, by all three

### Gemini 4 Argon

```
std-sec-14 | S | Where possible, rely on workspace identity or service principals, avoiding static credentials
std-del-10 | S | Other users can have a production workspace viewer role to see content
std-del-23 | S | However, you probably want all BI creators for a specific workspace
```

All three rows are `S` (Supported), under 35 words, and free of collisions. `std-sec-14` (`[review]`) complements `std-sec-01` (`[gate]` against embedded secrets in files) and `std-sec-02` (`[flag]` on data-source connections using static credentials when identity-based authentication is available) by checking how code or pipelines obtain credentials at run time when needed. Splitting `std-del-10` and `std-del-23` cleanly attaches the BI-creator recommendation to the deployment pipeline only, and neither collides with `std-del-19`, which applies only to the identity used by automation workflows or scripts calling Fabric APIs.

### GPT 6.1 Sol

```
std-sec-14 | S | Where possible, rely on workspace identity or service principals,
std-del-10 | S | Other users can have a production workspace viewer role
std-del-23 | S | you probably want all BI creators for a specific workspace
```

No remaining defect or conflict is confirmed. The BI-creator recommendation is now correctly pipeline-only. `std-del-10` and `std-del-23` concern access authorization; `std-del-19` concerns automation's execution identity and does not grant production permissions. `std-sec-14` reviews credential handling without relaxing `std-sec-01`'s embedded-secret gate or `std-sec-02`'s escalation when safer authentication is available. The tags agree.

### Grok 4.7

```
std-sec-14 | S | Where possible, rely on workspace identity or service principals
std-del-10 | S | Other users can have a production workspace viewer role
std-del-23 | S | you probably want all BI creators for a specific
```

Nothing is still wrong, and nothing collides. std-del-10 and std-del-23 split the same section without overlap: deploy rights stay with specific people and viewers, while repository access stays with content-creation users and the BI-creator "probably" applies only to the pipeline. std-del-19 is a different subject, the identity of an API caller, not who may deploy. std-sec-14 reviews how code obtains a credential; std-sec-01 gates an embedded secret; std-sec-02 flags a static-credential connection. An agent can apply all three.
