# Data agent checks for Fabric changes

Checks drawn from six Microsoft Learn pages on Fabric data agents: query-generation practices, configurations, example queries, data sources, semantic models as a source, and source control. They are for a change that creates or alters a data agent, its instructions or example queries, or a semantic model that it queries. This file guides and never authorizes a change.
The pages mark source control for data agents, schema object descriptions, topics and advanced DAX generation as preview. Some of these need the preview runtime, so each check keeps the state that its page gives. The factory does not change access to a workspace; it flags such a change to a person, so the flag check names the guidance that applies.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. A Note: line is not a check; it records where pages differ or leave a choice open.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| Query best practices | https://learn.microsoft.com/fabric/data-science/data-agent-configuration-best-practices | 2026-08-31 | 2026-11-04 |
| Configurations | https://learn.microsoft.com/fabric/data-science/data-agent-configurations | 2026-09-29 | 2026-11-04 |
| Example queries | https://learn.microsoft.com/fabric/data-science/data-agent-example-queries | 2026-06-23 | 2026-11-04 |
| Data sources | https://learn.microsoft.com/fabric/data-science/data-agent-add-datasources | 2026-09-30 | 2026-11-04 |
| Semantic model practices | https://learn.microsoft.com/fabric/data-science/semantic-model-best-practices | 2026-09-01 | 2026-11-04 |
| Source control | https://learn.microsoft.com/fabric/data-science/data-agent-source-control | 2026-08-31 | 2026-11-04 |

## Data sources and schema selection

- `std-agt-01` Does the data agent use at most five data sources, the most that one agent can use according to the data sources page, whatever the mix of types? [gate] Applies to: the data source folders of a new or changed data agent. Source: Data sources, "Overview"; Source control, "Root structure".
- `std-agt-02` In the schema map of a data source, does the change set selection at table level only, since column-level selection is currently not supported and a selected table includes all its columns? [gate] Applies to: the elements of a data source in a data agent definition. Source: Source control, "Root structure".

Note: the best practices page says to limit the selection to the tables, columns, views and functions that the questions need. The source control page says column-level selection is currently not supported and a selected table includes all of its columns. The pages do not say how the two fit together. Source: Query best practices, "Limit the selected schema"; Source control, "Root structure".

- `std-agt-03` Does the schema selection include only objects that the agent's intended questions need, and, for two selected objects with similar data, does the configuration say which is authoritative and when to use each? [review] Applies to: the schema selection of a data agent's data source. Source: Query best practices, "Limit the selected schema"; Configurations, "Data agent schema selection".

## Instructions and descriptions

- `std-agt-04` Do the agent-level instructions follow the recommended format, with sections for the objective, the data sources and their priority, key terminology, response guidelines and handling of common topics? [review] Applies to: the agent-level instructions of a new or changed data agent. Source: Configurations, "Data agent instructions".
- `std-agt-05` Do the data source instructions state, as direct instructions, rules that span objects, for example join paths, table grain, default filters and how to avoid duplicated rows when two fact tables are joined? [review] Applies to: the data source instructions of a data agent, for a source type that supports them. Source: Query best practices, "Use data source instructions for rules across objects"; Query best practices, "Explain relationships and table grain".
- `std-agt-06` Do the instructions define terms that users might use but that do not map directly to the schema, and the stored values that filters need, for example the form of a state? [review] Applies to: the instructions and descriptions of a data agent's data source. Source: Query best practices, "Define business terms and expected values".

Note: the configurations page gives data source instructions a template section for table descriptions. The best practices page says that definitions of a single object belong in schema object descriptions, not in instruction space used as a glossary. Those descriptions are preview and need the preview runtime for SQL sources. The pages do not say where such definitions go otherwise. Source: Configurations, "Data source instructions"; Query best practices, "Use data source instructions for rules across objects"; Query best practices, "Describe schema objects (Preview)".

- `std-agt-07` Ask: if the change relies on schema object descriptions or topics (SQL data sources only) or on advanced DAX generation, does the data agent use the preview runtime, which each requires? [review] Applies to: a data agent that gets descriptions or topics for a SQL data source, or advanced DAX generation for a semantic model. Source: Configurations, "Schema object descriptions (Preview)"; Configurations, "Topics (Preview)"; Data sources, "SQL Sources Supported Configurations"; Semantic model practices, "Use advanced DAX generation".

## Example queries

- `std-agt-08` Does the change keep example queries out of a semantic model or ontology data source, which the example queries page currently lists as not supporting them? [gate] Applies to: the data source folders of a data agent. Source: Example queries, "Provide example queries"; Source control, "Root structure".
- `std-agt-09` Does each example query pair a clear question with a query that includes every number, date or category that the question names, and do the examples avoid overlap and contradiction? [review] Applies to: the example queries of a data source; the literal rule is stated for SQL. Source: Example queries, "Best practices for writing example queries"; Example queries, "Understand validator scores"; Query best practices, "Use example queries for complex logic".
- `std-agt-10` If a change renames or removes a table or column, are the example queries that use it updated, since one that fails validation against the schema is not sent to the agent? [review] Applies to: a schema change to a table or column that example queries use. Source: Example queries, "Provide example queries"; Query best practices, "Use example queries for complex logic".

Note: the configurations page says the tool passes the top three example queries to the data agent tool. The example queries page says the agent typically retrieves the top four. Neither page says which number applies. Source: Configurations, "Data source example queries"; Example queries, "Example queries".

## Semantic models as a data source

- `std-agt-11` For a semantic model source, are the instructions about the model kept in its Prep for AI instructions and not in the data agent instructions, which the DAX generation tool does not receive? [review] Applies to: a data agent that uses a semantic model as a data source. Source: Semantic model practices, "Prep for AI: Make semantic model AI ready"; Semantic model practices, "AI instructions".

Note: the configurations page says data source instructions give the context to build queries in SQL, DAX or KQL. The semantic model page says the data agent supports neither data source instructions nor descriptions for semantic models. The source control page describes datasource.json, which a semantic model folder also holds, as defining the data source instructions, and does not say they go unused there. Source: Configurations, "Data source instructions"; Semantic model practices, "AI instructions"; Source control, "Root structure".

- `std-agt-12` Does the data agent select the same tables as the model's AI data schema in Prep for AI, and does that schema also include the objects that its measures depend on? [review] Applies to: a data agent that uses a semantic model as a data source. Source: Semantic model practices, "AI data schemas"; Semantic model practices, "Tips for AI data schemas".

Note: the page says to include in the AI data schema the objects that a measure depends on. It also says to include only measures that calculate business metrics and to leave helper measures out. It does not say what to do with a helper measure that a business measure uses. Source: Semantic model practices, "Tips for AI data schemas"; Semantic model practices, "Common pitfalls to avoid".

- `std-agt-13` Does a change that renames a table, column or measure used by a verified answer update and save that answer again, and does it avoid hiding a column that the answer uses? [review] Applies to: a rename or a hidden column in a semantic model that has verified answers. Source: Semantic model practices, "Configuration tips for verified answers"; Semantic model practices, "Common pitfalls to avoid".

Note: the page says instance value indexing in advanced DAX generation currently needs the Q&A setting of the model, which is on by default for Import models and for Direct Lake models. It also says Q&A retires in December 2026 and that a replacement setting will follow, without naming it. Source: Semantic model practices, "Use advanced DAX generation".

## Git, promotion and publishing

- `std-agt-14` Does the change leave a data agent's published folder untouched and make configuration edits in its draft folder, since publishing carries draft changes into the published folder? [gate] Applies to: a data agent item in a Git-connected workspace, where source control for data agents is preview. Source: Source control, "Root structure"; Source control, "Best practices".
- `std-agt-15` If automation acts on a data agent as a service principal, is it limited to ALM operations, for example Git integration and deployment pipelines, the only use that the page says is supported? [review] Applies to: a workflow or script that calls a data agent. Source: Source control, "Limitations and considerations"; Source control, "Bulk synchronization via batch APIs (preview)".
- `std-agt-16` Flag a change to access to a development workspace with data agents; guidance: limit publishing there to authorized users who develop agents, and have end users use only the production workspace's published agents. [flag] Applies to: a workspace role or other access change for a development workspace with data agents. Source: Source control, "Publish a Fabric data agent for the deployment pipelines".
