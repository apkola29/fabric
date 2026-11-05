# Verification of the five workload files of the pack, round C: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the five files and the pages that they cite (reduced to text, with the quotes looked up by a program in the cited section) and took: the 7 lines that round B had changed, the header and table of sources of `onelake-security.md` (8 rows), and the 7 closure rows. The author's checks and the dispositions are in [workload-pack-findings.md](workload-pack-findings.md).

```text
std-agt-06 | S | Place a definition in the schema object description | The cited section supports documenting business terms and filter values in descriptions or instructions. Both destinations are now explicit; neighbouring guidance preserves object-specific versus cross-object placement.
std-sem-04 | S | The mode property of Direct Lake partitions is set to | "Direct Lake model metadata" supports compatibility level 1604 or higher and directLake mode specifically for Direct Lake partitions, not every partition. The gate is deterministic.
note-eng-2 | S | Standardize at the environment level; use session overrides sparingly for debugging. | Monitoring/"Configuration hierarchy" supplies the environment-first advice. Development/"Scenario: Customize session configuration in the Notebook" says "Parameterize your configuration" for pipeline execution. The note accurately records differing uses without denying that hierarchy exists.
std-cap-12 | S | Many interactive operations like SQL query are also considered background | Manage growth/"Enterprise (centralized) capacities" supports the added interactive-SQL warning and possible rejection. Both cited sections support background rejection, possible reruns, optimization/scaling caveats and critical-workload isolation. The flag remains appropriate.
std-cap-13 | S | first make sure the capacity isn't in use. | "How to stop throttling when it occurs" supports the restored precondition, accumulated-future-usage billing, possible unavailability and three-times overage rate, within the retained F SKU scope.
std-olk-12 | S | use the owner identity of the consumer item or data source. | Access model supports both shortcut modes and separate query-engine identity. The line now explicitly includes Direct Lake over SQL alongside delegated SQL analytics endpoints in the owner-identity exception; std-olk-11 remains consistent.
note-olk-4 | S | might fall back to older, insecure protocols (including TLS 1.0) | Data security supports conditional outbound fallback and inbound TLS 1.2 enforcement. Fundamentals/"Data in transit" says "now requires TLS 1.2 or later". Both sides are cited; std-sec-11 is correctly identified, and no precedence is invented.
header-olk | S | Outbound Fabric communication to customer-owned infrastructure now requires TLS 1.2 | Fundamentals/"Data in transit" supports the added comparison. All five source-table URLs and Updated dates match SOURCE/UPDATED_AT metadata. The header accurately describes four OneLake pages plus the comparison note.

B-G1 | F | data source instructions or schema object descriptions | The operative question now names both supported destinations, matching its scope and the cited placement guidance.
B-K1 | F | Direct Lake partitions in directLake mode? | The gate no longer requires every partition of a composite model to use directLake mode.
B-K2 | F | do not reconcile the debugging use of session overrides | The false claim that no allocation rule exists is removed. Environment standardization and sparing debugging overrides remain explicit; the remaining observation concerns differing documented uses.
B-K3 | F | are also considered background and might be rejected | The line now warns that many interactive operations, including SQL queries, can fall within background rejection. The possibility hedge is retained.
B-K4 | F | first make sure the capacity isn't in use | The source's before-pausing precondition is restored without losing the billing, availability or overage-rate guidance.
B-P1 | F | Direct Lake over SQL and delegated SQL analytics endpoints | Both owner-identity cases are now explicit, and the owner is identified as that of the consumer item or data source. Shortcut authentication remains distinct.
B-P2 | F | the Fundamentals page says that such outbound communication now needs | The note now cites Fundamentals, names std-sec-11 and accurately states both TLS positions. The added source-table entry and revised header complete the citation repair.
```

## FINDINGS

None.

## CHECKED AND FINE

**15 rows: 8 S and 7 F.** All seven round-B findings are fixed. All five changed check sentences meet the 35-word limit; all report quotes were mechanically verified against their required locations.

**Not checked:** unchanged guidance against its sources or live Fabric behaviour; no live fetches, edits, installs or sign-in were performed.
