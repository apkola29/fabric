# Verification of the five workload files of the pack, round A: the reply of GPT 6.1 Sol

The reply as it came back, with the agent's own header removed. It read the five files and the pages that they cite (reduced to text, with the quotes looked up by a program in the cited section) and took: `data-engineering.md` and `data-agents.md`, every line (50 rows), cold. The author's checks and the dispositions are in [workload-pack-findings.md](workload-pack-findings.md).

std-eng-01 | S | Fabric Runtime 2.0 (Spark 4.1, Java 21, Python 3.13) | Monitoring explicitly identifies Runtime 2.0 as current GA; the development page agrees on the current version.
std-eng-02 | S | Always place %%configure in the first cell of a notebook. | Both cited sections support first-cell placement; notebook placement is deterministically inspectable.
std-eng-03 | S | with the same lakehouse, environment, and Spark configs | Shared-session conditions, pipeline session tags and workspace-level enablement are supported. The check asks for consideration, not an administrative change.
std-eng-04 | S | The native execution engine doesn't currently support structured streaming. | Suitability examples and fallback behavior match the cited sections; unsupported streaming is correctly identified.
std-eng-05 | S | you must configure separate managed private endpoints for both the Blob | The Blob/DFS requirement applies when NEE-enabled jobs access storage through managed private endpoints. Ask and flag appropriately preserve the network boundary.
note-eng-1 | S | It takes effect when it becomes the first executed cell, | The same paragraph also says “changes don't take effect unless you restart the session.” The contradictory first-cell wording is genuinely present.
note-eng-2 | M | use session overrides sparingly for debugging. | “Configure via code for reproducibility” does not conflict with environment defaults. The development section explicitly distinguishes “Pipeline Execution Phase”; claiming the pages provide no applicable contexts overstates the tension.
note-eng-3 | S | Doesn't support ANSI SQL mode. | The other page says “On Runtime 2.0 (Apache Spark 4.1), ANSI SQL mode is supported:”. UDF, CSV and Runtime 1.3 rounding/collection comparisons also match.
note-eng-4 | P | during the preview phase | The UI tension is real: “Check the box labeled Enable native execution engine.” versus mechanisms that “are under active development.” The release-status absence claim is UNVERIFIED and too categorical.
std-eng-06 | S | if unavoidable, increase driver size and benchmark. | The named driver-heavy operations and conditional mitigation are directly supported.
std-eng-07 | S | For Spark-written tables primarily consumed through Direct Lake, enable V-Order | Producer/consumer conditions, the Spark-only exclusion and the new-workspace default are preserved.
std-eng-08 | S | the `spark.sql.parquet.vorder.enable` setting is removed. | Exact setting name and Runtime 1.3-or-later condition match; its presence is mechanically inspectable.
note-eng-5 | S | ~10% read performance improvement | Monitoring recommends enabling for read-heavy endpoint/warehouse consumption; table maintenance says “Don't enable V-Order solely for Spark or SQL analytics endpoint performance.” SQL endpoint guidance also qualifies the default recommendation.
note-eng-6 | S | which automatically enable V-order for read-focused performance. | Monitoring lists “V-order enabled, OptimizeWrite enabled, 1 GB bin size” for the Power BI profile and omits V-order from the Spark row. This is a documented omission, not proof Spark disables it.
note-eng-7 | S | often around 15% on average | Monitoring separately reports “15–33% slower writes” for Spark. Both estimates are reproduced correctly; they are not mutually exclusive.
std-eng-09 | S | Lakehouse Delta tables require an explicit maintenance strategy | All named writers, separately scheduled maintenance and append-only small-file accumulation are supported.
std-eng-10 | S | Schedule `OPTIMIZE` separately instead of running synchronous auto compaction. | The strict-latency exception is retained; monitoring explicitly lists auto compaction as false by default.
std-eng-11 | S | without evaluating time-travel requirements and concurrent readers or writers. | The warning about shortening retention and losing required versions is faithfully preserved.
std-eng-12 | S | from 128 MB to 1 GB. | Runtime 2.0-or-later defaults, per-table adaptation, static-target avoidance and Runtime 1.3 opt-in status all match.
std-eng-13 | S | partitions close to or greater than 1 GB. | The requirement-based partitioning exception, high-cardinality warning and SQL endpoint size guidance are supported.
std-eng-14 | S | A consumer-specific layout whose measured benefit outweighs | Independent purpose, changed grain, security/retention differences and measured layout benefits are supported examples.
note-eng-8 | S | Recommended by Microsoft for most workloads but not enabled by default. | SQL endpoint guidance says “These runtimes enable adaptive target file size by default”, explicitly referring to Runtime 2.0 or later. Runtime 1.3 opt-in and monitoring’s missing runtime qualification are accurately recorded.
note-eng-9 | S | with row groups of 1–2 million rows. | Direct Lake guidance gives “between 1 million and 16 million rows.” Both ranges and their differing contexts are accurately recorded; the ranges overlap.
std-eng-15 | S | less than one minute. | Normal lag, variability and on-demand synchronization are supported; the immediate-after-write framing matches the examples.
std-eng-16 | S | Don't grant developers direct access to production workspaces. | Both pages support privileged log retrieval and developer handoff. The check flags access changes rather than implementing them.
std-eng-17 | S | Combining a Fast Copy operation with non-folding transformations | Both sections support separating non-folding transformations to preserve Fast Copy; folding transformations are not unnecessarily excluded.
std-eng-18 | S | adjust the parameters during runtime to retrieve the full dataset | The design-time/runtime distinction and full-data-only-when-needed condition are preserved.
note-eng-10 | S | consider using incremental refresh or the pattern to incrementally amass data. | Table maintenance says these destinations “don't support `OPTIMIZE` or `REORG TABLE`.” The recommendation/restriction tension and lack of a concrete compaction method in these sections are accurately recorded.
std-agt-01 | S | A single Data Agent can use up to five data sources | Five and any combination are explicit. Source control documents one folder per source, permitting deterministic counting within each stage.
std-agt-02 | S | column-level selection isn't currently supported. | Effective selection is table-level. Column entries may still contain flags; the check must not be interpreted as prohibiting those fields.
note-agt-1 | S | tables, columns, views, and functions | Source control says “column-level selection isn't currently supported.” The apparent selection inconsistency is genuine and correctly described.
std-agt-03 | S | explain which one is authoritative and when to use each one. | Focused schema selection and guidance for similar objects are directly supported.
std-agt-04 | S | Use this recommended format to write effective agent-level instructions: | All five named template sections are present; the check correctly calls the format recommended.
std-agt-05 | S | Write direct instructions that state what the agent should do. | Cross-object rules, join paths, grain, default filters and conditional duplicate-row prevention are supported.
std-agt-06 | S | document values that the agent needs to construct filters correctly: | Business terminology and stored filter-value representations, including state representations, are supported.
note-agt-2 | S | Describe key tables and important columns within those tables. | The other section says “Put object-specific definitions in schema object descriptions”, which are “available only when the data agent uses the preview runtime.” The template/placement tension is real.
std-agt-07 | S | switch the data agent to the preview runtime. | Each feature requires the preview runtime; descriptions/topics are SQL-specific, while advanced DAX concerns semantic models. The sentence preserves that distinction.
std-agt-08 | S | it doesn't support example queries | Source control explicitly excludes semantic models; the example-query support table separately excludes ontology. The gate does not invent a closed list of supported types.
std-agt-09 | M | should be explicitly represented in the SQL. | The literal-mapping rule is SQL-specific, but the operative question applies it to every example query. Acknowledging SQL in Applies to does not clearly restrict that demand.
std-agt-10 | S | verify that every example still matches the current schema. | Renames/removals are valid triggering examples; schema-validation failures are explicitly withheld from the agent.
note-agt-3 | S | passes the top three to the data agent tool. | The other page says “typically the top four”. Both numbers and the latter qualification are correctly preserved.
std-agt-11 | S | Data agent instructions aren't passed to the tool | Model-specific guidance belongs in Prep for AI; the check does not prohibit shared routing or formatting instructions.
note-agt-4 | S | whether in SQL, DAX, or KQL | The semantic-model section says it “doesn't support data source instructions or descriptions for semantic models.” Source control generically lists `dataSourceInstructions` without explaining that exception; the note accurately distinguishes this silence.
std-agt-12 | S | When selecting schema, also include dependent objects. | Both matching table selection and inclusion of measure dependencies are explicitly recommended.
note-agt-5 | S | include all of those dependent objects in your schema. | The pitfalls section says “include only the measures that calculate actual business metrics.” Dependent helper measures expose a genuine unresolved interaction.
std-agt-13 | S | update the verified answer and save it again | Rename handling is explicit; the separate warning establishes that verified answers referencing hidden columns do not work.
note-agt-6 | S | Since Q&A retires in December 2026 | The section also says “Instance value indexing currently requires the semantic model's Q&A setting”. Import/Direct Lake defaults and the unnamed replacement are correctly recorded.
std-agt-14 | C | Changes should be made in the draft folder. | Folder-editing guidance is supported and mechanically inspectable. However, the preview qualification appears only in the page introduction, outside both cited sections.
std-agt-15 | S | doesn't extend to other Fabric data agent features. | Service-principal support is explicitly limited to ALM; Git integration and deployment pipelines remain examples rather than an exhaustive list.
std-agt-16 | S | Access to this workspace must be restricted | Development publishing restrictions and production-only end-user consumption are supported. The flag correctly concerns access changes.

## FINDINGS

### F1 — Medium — note-eng-2

**Evidence:** `sources\fabric-data-engineering-spark-monitoring-best-practices.md`, “Configuration hierarchy”: “use session overrides sparingly for debugging.”  
`sources\fabric-data-engineering-spark-best-practices-development-monitoring.md`, “Scenario: Customize session configuration in the Notebook”: “Pipeline Execution Phase”.

**Problem:** Code-based configuration and environment standardization are compatible. The note turns differing scopes into an unresolved contradiction and overstates the absence of applicability guidance.

**Suggested replacement:**

Note: the monitoring page favors environment defaults and sparse session overrides for debugging; the development page describes interactive notebook configuration and parameterized pipeline configuration. Source: Spark monitoring, "Configuration hierarchy"; Spark development, "Scenario: Customize session configuration in the Notebook".

### F2 — Medium — note-eng-4

**Evidence:** `sources\fabric-data-engineering-native-execution-engine-overview.md`, “Enable the native execution engine”: “during the preview phase”; “Control on the query level”: “are under active development.”

**Problem:** The environment/UI inconsistency is real, but claiming that no release status is stated discounts the explicit preview wording. The current status remains UNVERIFIED; the live cited page retains the same wording.

**Suggested replacement:**

Note: the native engine page retains preview wording and describes environment enablement, while another section calls tenant, workspace and environment UI enablement under development; its current release status remains UNVERIFIED. Source: Native engine, "Enable the native execution engine"; Native engine, "Control on the query level".

### F3 — Medium — std-agt-09

**Evidence:** `sources\fabric-data-science-data-agent-example-queries.md`, “Understand validator scores”: “should be explicitly represented in the SQL.”

**Problem:** The SQL literal-mapping criterion becomes a general requirement for every query language. The scope caveat should qualify the operative clause, not merely describe where its evidence originated.

**Suggested replacement:**

- `std-agt-09` Do examples pair clear questions with matching queries, avoid overlap or contradiction, and, for SQL examples, include every number, date and category from the question in the SQL? [review] Applies to: example queries of a data source. Source: Example queries, "Best practices for writing example queries"; Example queries, "Understand validator scores"; Query best practices, "Use example queries for complex logic".

### F4 — Low — std-agt-14

**Evidence:** `sources\fabric-data-science-data-agent-source-control.md`, “Source Control, CI/CD, and ALM for Fabric data agent”: “Source control for Fabric data agents is currently in preview.”

**Problem:** The preview statement is true but absent from the cited “Root structure” and “Best practices” sections. Add the page-introduction heading as its citation.

**Suggested replacement:**

- `std-agt-14` Does the change leave a data agent's published folder untouched and make configuration edits in its draft folder, since publishing carries draft changes into the published folder? [gate] Applies to: a data agent item in a Git-connected workspace, where source control for data agents is preview. Source: Source control, "Root structure"; Source control, "Source Control, CI/CD, and ALM for Fabric data agent".

## CHECKED AND FINE

**46 rows S:** 32 checks and 14 notes. Both headers reviewed; source counts, data-agent preview claims, all 14 SHA-256 hashes and both source tables verified. All 70 report excerpts were checked against their cited sections.

Not checked: live tenant state, executable gate implementations, runtime behavior, or the other three new reference files.
