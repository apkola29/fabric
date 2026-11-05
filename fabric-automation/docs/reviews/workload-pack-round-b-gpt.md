# Verification of the five workload files of the pack, round B: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the five files and the pages that they cite (reduced to text, with the quotes looked up by a program in the cited section) and took: `onelake-security.md` and `capacity-and-cost.md`, every line cold (41 rows), and the closure of 23 findings of round A that Gemini and Grok had raised about them. The author's checks and the dispositions are in [workload-pack-findings.md](workload-pack-findings.md).

# B1 — Round B verification

Reviewed all 41 checks/notes, both headers, and all 23 assigned closures. The eight primary source hashes and two runtime-source hashes match the drafting notes. All primary quote fields were verified verbatim against their required sections or new pack lines.

## onelake-security.md

```text
header-olk | S | Enforce OneLake security in authorized third-party engines (preview) | Data security explicitly marks this feature preview. The four-page scope is accurate; refusal/tag statements match the brief and SKILL. No header authorizes an operation.
std-olk-01 | S | Only in Delegated mode | Data security/"Share items and set item-level permissions" supports the Read, ReadData and ReadAll distinctions. The line does not claim ReadData alone supplies every permission needed to connect.
std-olk-02 | S | Write operations through the Lakehouse UX for viewers aren't supported | Both cited sections support the three write paths, current Lakehouse UX exclusion, and prohibition on RLS/CLS constraints in ReadWrite roles. Specific-folder/table scope is retained.
std-olk-03 | S | users who relied on that role lose data access | Access model explicitly conditions this consequence on OneLake security being enabled and reliance on DefaultReader; retaining ReadAll does not restore access.
note-olk-1 | S | You can give Viewers access to data | Data security supplies the Viewer footnote. Access model says "Default roles apply only to Viewers" and makes default access permission-dependent. Neither cited section states that Viewer carries ReadAll.
std-olk-04 | S | Direct Lake on SQL semantic models is subject to this limitation | The limitations section supports both the most-inclusive Guest user access setting in Entra External ID and distribution-list resolution failures for SQL analytics endpoints and Direct Lake on SQL.
std-olk-05 | S | You can't deny access that is granted through a different role | Table security also explicitly includes another permission model and exempts workspace Admins, Members and Contributors. Access model confirms grant-only roles; the flag is appropriate.
std-olk-06 | S | the endpoint intersects CLS allow lists across all the user's roles | Access model supports cross-role union, OR for row predicates on one table, and the SQL analytics endpoint's CLS-intersection exception. This checks expected behavior rather than changing roles.
std-olk-07 | S | the two policies have to be applied using a single OneLake security | The cited sections support keeping jointly applicable RLS/CLS rules in one role and query errors for unsupported combinations. The following note preserves their differing descriptions.
note-olk-2 | S | one contains RLS rules and another contains CLS rules | Table security uses this formulation. Access model instead specifies "two roles allow a different set of columns for a table" with RLS in either role. The note accurately records the distinction without ranking pages.
std-olk-08 | S | The folder doesn't contain any child shortcuts. | All four validity conditions were checked: Tables/, conditional schema folder, _delta_log containing metadata JSON files, and no child shortcuts. The section states denial when RLS/CLS applies and these conditions fail.
std-olk-09 | S | the query fails and returns no data. | Table security supports the mismatch consequence and missing-column example. Failure remains conditional on a mismatch; the line does not assert every column change causes one. Escalation follows the mandated flag policy.
std-olk-10 | S | The query succeeds and shows only the allowed columns. | The source distinguishes Spark success from SQL analytics endpoint and semantic-model errors for select-star queries with partial column access. The condition and engine distinctions are retained.
std-olk-11 | S | the owner identity of the consumer item or data source. | Best practices supports per-user evaluation in user's identity mode. Access model supports the owner-identity statement and its item-or-data-source disjunction.
std-olk-12 | P | Power BI semantic models using Direct Lake over SQL | The source explicitly includes these models in the owner-identity exception. The new line mentions separate settings but refers only to std-olk-11, whose scope is SQL analytics endpoints. The model-specific exception remains unstated; its treatment is UNVERIFIED by this check.
std-olk-13 | S | The access check evaluates once you try to open the shortcut | Access model distinguishes internal-shortcut directory listing from target authorization on opening. The verification question preserves that distinction and does not generalize it to external shortcuts.
std-olk-14 | S | This setting must be enabled to use shortcuts with OneLake security | The exact tenant-setting name and OneLake settings location match Data security. Ask and flag are appropriate for the required tenant setting.
std-olk-15 | S | Some scenarios might require alternative approaches due to current network security constraints. | Best practices identifies the central workspace/shortcut pattern as a recommended baseline, not a universal requirement. The alternative-scenario qualification remains.
note-olk-3 | S | data consumption, additional workloads, or domain-specific use cases. | Primary pattern calls it "the recommended baseline architecture for implementing OneLake security at scale." It names current network constraints without identifying them or prescribing alternatives. The unsupported comparison with other files has been removed.
std-olk-16 | S | the environment to be 3.5 or higher | Access model states both this unexplained version wording and runtime 1.3. The line preserves them and discloses the latest-runtime tension through std-eng-01 rather than inventing compatibility or precedence.
note-olk-4 | C | might fall back to older, insecure protocols (including TLS 1.0) | The cited section supports fallback and says "Inbound OneLake communication also enforces TLS 1.2". Live Fundamentals/"Data in transit" confirms "older protocols (including TLS 1.0 and TLS 1.1) are no longer supported." However, Fundamentals is absent from this file's Sources and the note's Source field; the older id std-sec-11 is also not named.
```

## capacity-and-cost.md

```text
header-cap | S | Microsoft might change or update the Fabric throttling policy. | Throttling/"Throttle triggers and throttle stages" supports the dated-policy warning. The four source scopes are accurate. Capacity-change refusal and the non-authorizing interpretation of questions match the brief.
std-cap-01 | S | Slow performance is often due to the design of an item. | Both cited sections support confirming throttling rather than inferring it from slowness or utilization above 100 percent.
std-cap-02 | S | Always optimize workloads before increasing capacity. | Manage growth explicitly states optimization before scaling and expansion only when necessary. The question reviews the plan's justification; it does not authorize resizing.
std-cap-03 | S | Ideally, this stays at 0 | The cited section recommends monitoring proximity to limits and throttled, delayed or rejected operations. Zero applies to those adverse events, not to capacity utilization.
std-cap-04 | S | thresholds determined by capacity SKU size and license type. | Manage growth explicitly requires observing workload thresholds and gives semantic-model capacity requirements as an example. The tenant-dependent hosting question is correctly prefixed Ask.
note-cap-1 | S | optimize first, expand only when necessary. | Manage growth supplies precedence. Optimize capacity lists "three strategies to resolve it: optimize, scale up, and scale out." Throttling advises "load balance across multiple capacities or increase the capacity's SKU size." No amount of prior optimization is specified.
note-cap-2 | S | start small and then gradually increase the size of your capacity | Optimize capacity supports this advice; Plan deployment says "start small, learn, and scale gradually." Manage growth says "If the semantic model demands F128 capacity, begin with the F128 SKU." The note now correctly identifies that named-size example.
note-cap-3 | S | consistently above ~80% during peak times | The self-service threshold is accurately scoped. Common practices says "scale up to the next SKU before reaching full utilization." Plan deployment says "comfortably under 100 percent"; Throttling says "utilization exceeding 100% doesn't automatically mean throttling". These are not collapsed into one universal trigger.
std-cap-05 | S | the throttling state of the consuming capacity | The introductory section explicitly assigns this throttling decision to the consuming capacity when another capacity produces the item.
std-cap-06 | S | Throttling calculations include only billable operations. | The section also identifies possible non-billable preview operations and expressly recommends using them to plan capacity for future billability. The qualification "some" is retained.
std-cap-07 | S | Spark usage operates in a pay-as-you-go mode | The smoothing section explicitly excludes bursting and smoothing when Autoscale Billing for Spark is enabled. This asks which existing mode applies; it does not require enabling it.
std-cap-08 | S | Reserve required executors for your Spark jobs | Optimize capacity supports reserving required executors, freeing resources for other jobs, and reducing the chance of HTTP 430 failures. The stated meaning of that status is accurate.
std-cap-09 | S | the default Spark session expiration time is set to 20 minutes. | The same section supports stopping unused active sessions, possible CU accrual, and user-adjustable timeout. The line does not invent when the expiration clock starts.
std-cap-10 | S | Avoid refreshing data more frequently than the data source requires. | The source explicitly uses hourly refresh of a source updated once every 24 hours as its example. Scope includes both dataflows and pipelines.
std-cap-11 | S | Your choice of data type can heavily influence the query plans | The recommendation is smallest possible types. The source separately gives shorter VARCHAR as an example that can reduce allocated query resources; the revised line preserves that distinction.
note-cap-4 | S | Reschedule consecutive pipelines to avoid resource peaks. | Growth places this under optimization before scaling. Planning says "There's no need to schedule jobs after another one finishes." It also says "Sustained overload still leads to throttling." Throttling says "scheduled jobs can all run simultaneously". The std-perf-02 pointer and its existing note were checked.
note-cap-5 | S | All data warehouse operations are background operations | Optimize capacity says all. Throttling says "almost all operations in the Warehouse category as background" and describes interactive-chain treatment. Growth says "Many interactive operations like SQL query are also considered background" within surge protection and warns of rejection. All three sides are represented accurately.
std-cap-12 | S | Critical workloads still require dedicated capacity for full protection. | Both sections support active surge-protection rejection and its limitations. Growth supplies delays/reruns and dedicated capacity; Optimize supplies the correctly sized isolation recommendation retained in Applies to.
std-cap-13 | S | billing event for the accumulated future capacity usage. | Throttling supports the future-usage billing event, possible content unavailability and three-times normal capacity rate. Applies to correctly limits this guidance to F SKUs.
std-cap-14 | S | Plan resizes for periods of low activity. | Manage growth explicitly supports scheduled F SKU resizing, possible disruption of operations in progress, and avoiding frequent resizing. The flag prevents treating that guidance as authorization.
std-cap-15 | S | smoothed usage is well below the set threshold | The large-job condition, lower-size threshold and example percentages match the section. Applies to now confines 40/80 to the page's named F128-to-F64 example rather than every downsize.
std-cap-16 | S | High CU items have an increased chance of throttling | Optimize supports isolation through scale-out. Planning attaches cost and this throttling downside to creating multiple smaller capacities; the revised line now preserves that context.
```

## Closure rows

```text
G-F1 | F | Flag a change that hides data with OneLake security | std-olk-05 is now flag. The grant-only, other-permission-model and elevated-workspace-role statements match both cited sections.
G-F2 | F | folder with metadata JSON files and no child shortcuts. | std-olk-08 now includes metadata JSON, conditional schema placement and the denial consequence, with the required flag tag.
G-F3 | J | the query fails and returns no data. | std-olk-09 now escalates the change. Rejecting the suggested mandatory role update is justified: Table security/"Column-level and row-level security" states the mismatch/error consequence, not a required remediation method.
G-F4 | F | Users can access data stored in OneLake with apps external to Fabric | std-olk-14 now uses the exact setting name, retains Ask, and carries flag. The requirement is explicit in the cited Data security section.
G-F6 | F | the pages do not say how that fits this limitation. | std-olk-16 and std-eng-01 now cross-reference the conflicting runtime guidance. Access model's 1.3 requirement and the two Spark pages' 2.0 guidance were checked; the fix invents neither compatibility nor page precedence.
G-F10 | F | not the Lakehouse UX at this time. | std-olk-02 now retains the current UX limitation and all three supported write paths, alongside the ReadWrite role constraint.
G-F11 | F | Direct Lake on SQL cannot resolve list members. | std-olk-04 now includes the Direct Lake on SQL limitation and the exact Guest user access setting name with its most-inclusive qualification.
G-F12 | F | owner identity of the consumer item or data source. | std-olk-11 restores the source's disjunction and matches Access model/"OneLake security in passthrough shortcuts".
G-F13 | P | std-olk-11 gives the owner identity rule of delegated identity mode. | External delegated authentication and separation of settings are now stated. However, the referenced check covers SQL analytics endpoints, not the explicitly documented Direct Lake over SQL model exception. See F1.
G-F15 | F | without naming the constraints or the approach | note-olk-3 removes the unsupported comparison with other files. Its remaining architecture, downstream-use and unspecified-constraint claims are all in Primary pattern.
G-F16 | P | the TLS check of the security and governance file | note-olk-4 adds the supported inbound contrast but retains the older-page assertion without adding Fundamentals to Sources or Source. The citation defect remains. See F2.
K-F4 | F | folder with metadata JSON files | std-olk-08 now requires the metadata JSON files, not merely an empty _delta_log directory. Its flag tag follows the round-B rule.
K-F12 | F | owner identity of the consumer item or data source. | The lost disjunction is restored in std-olk-11 and agrees verbatim in meaning with the cited access-model section.
K-F13 | F | Users can access data stored in OneLake with apps external to Fabric | std-olk-14 restores the exact tenant-setting name. The flag adaptation is appropriate under the brief's mandatory tagging rule.
K-F16 | F | and that question still applies. | The note now distinguishes retaining std-sec-11's source-support question from ranking the contradictory protocol descriptions. The older check and live Fundamentals text were checked. This addresses operational ambiguity; its separate provenance defect remains under G-F16/F2.
K-F1 | F | the 40 and 80 percent figures are the page's example | std-cap-15 now expressly confines the example to the two sizes named by Manage growth, retaining the large-job and lower-size conditions.
K-F2 | F | while several smaller capacities add cost and more throttling risk | std-cap-16 now ties the downsides to multiple smaller capacities, as Planning/"Key actions in phase 3" does, rather than every capacity move.
K-F3 | F | billing event for accumulated future usage | std-cap-13 now identifies what the pause billing event settles. The unavailability warning, F SKU scope and three-times overage rate remain supported.
K-F5 | F | critical solutions should be isolated for full protection. | std-cap-12 separates isolation from the not-a-substitute list. Correct sizing is retained in Applies to, and both source sections support their respective parts.
K-F6 | F | heavily influence query plans | std-cap-11 now attaches heavily to query plans and presents reduced resource allocation as a possible example outcome, matching Optimize capacity.
K-F7 | F | and, in its example, that a semantic model | note-cap-2 now identifies the named-size semantic-model statement as an example instead of generalizing it into an unrestricted sizing rule.
K-F8 | F | among its points on surge protection | note-cap-5 now retains the surge-protection context and possible rejection, while accurately preserving the other pages' all/almost-all distinction.
K-F15 | F | adding that sustained overload still leads to throttling | note-cap-4 now supplies Planning's overload qualification and identifies std-perf-02 and its note. All cited statements were checked; no scheduling precedence is invented.
```

# FINDINGS

## F1 — Medium — std-olk-12

**Evidence:** `sources\fabric-onelake-security-data-access-control-model.md`, **“OneLake security in passthrough shortcuts”**: **“Power BI semantic models using Direct Lake over SQL”**.

The source includes these models in its owner-identity exception. The fix supplies a cross-reference that covers only SQL analytics endpoints, leaving this part of G-F13 unclosed. Saying settings are separate does not identify which identity this model actually uses.

**Suggested replacement** — 31 words in the check sentence:

- `std-olk-12` Does a shortcut declare passthrough (normally user identity, OneLake default) or delegated (connection identity, mandatory externally), accounting separately for owner identity in Direct Lake over SQL and delegated SQL analytics endpoints? [review] Applies to: a new shortcut, or a semantic model or SQL analytics endpoint that reads through one; std-olk-11 identifies the owner as that of the consumer item or data source. Source: Access model, "Shortcuts"; Access model, "OneLake security in passthrough shortcuts".

## F2 — Low — note-olk-4

**Evidence:** `sources\fabric-onelake-security-get-started-security.md`, **“Encrypt data in transit by using TLS”**: **“might fall back to older, insecure protocols (including TLS 1.0)”**.

The other side is also factually confirmed: [Fundamentals](https://learn.microsoft.com/fabric/security/security-fundamentals), **“Data in transit”**, says **“older protocols (including TLS 1.0 and TLS 1.1) are no longer supported.”**

However, that second page is still not cited by the note or listed in this file’s Sources. The revision therefore does not close G-F16. It also describes, rather than names, the older check despite the brief’s cross-reference requirement.

Add this Sources entry; its update date was verified against live metadata:

```text
| Fundamentals | https://learn.microsoft.com/fabric/security/security-fundamentals | 2026-02-12 | 2026-11-04 |
```

**Suggested replacement** — 29 words after `Note:`:

Note: Data security describes possible outbound TLS 1.0 fallback if newer protocols are unsupported; Fundamentals requires outbound TLS 1.2 or later; std-sec-11's source-support question remains; neither page ranks the other. Source: Data security, "Encrypt data in transit by using TLS"; Fundamentals, "Data in transit".

# CHECKED AND FINE

**61 rows are S or F:** 41 S and 20 F. Additionally: one justified rejection, two defective line rows, and two partly closed findings. All 32 check sentences meet the 35-word limit; headings and source-table metadata match; no checked body exceeds 12 consecutive copied source words.

**Not checked:** live tenant behavior, security enforcement, actual billing or cross-runtime compatibility remain UNVERIFIED; the other three files were inspected only for B1 cross-references. No supplied files were modified.
