# Well-Architected checks for Fabric workloads

Checks drawn from the six Well-Architected pages for Fabric workloads, grouped by pillar, for use when planning, writing or reviewing a change to a Fabric workspace. This file guides and never authorizes a change. The security page says to use the Azure security baseline as a reference and a starting point for conversations, not as a checklist.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] a change to security, permissions, a network setting, a sensitivity label or a tenant setting, which the factory only flags, naming the guidance, and never makes. What a change itself contains, such as a secret in a file, is not a change to a setting: it is a [gate] when a program can decide it. A check that starts with Ask: needs knowledge of the tenant. A question about deleting, purging or pausing something is a question to ask about the change, never an instruction to do it.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| WAF overview | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/overview | 2026-07-09 | 2026-11-01 |
| WAF reliability | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/reliability | 2026-05-14 | 2026-11-01 |
| WAF security | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/security | 2026-05-14 | 2026-11-01 |
| WAF cost | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/cost-optimization | 2026-05-14 | 2026-11-01 |
| WAF operations | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/operational-excellence | 2026-07-15 | 2026-11-01 |
| WAF performance | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/performance-efficiency | 2026-05-14 | 2026-11-01 |
| Greenfield | https://learn.microsoft.com/azure/architecture/example-scenario/data/greenfield-lakehouse-fabric | 2026-08-18 | 2026-11-01 |

## Reliability

- `std-rel-01` Are the new or changed write operations idempotent, so that a retry cannot cause duplicate writes or processing errors? [review] Applies to: a notebook or pipeline that writes data. Source: WAF reliability, "Apply self-preservation techniques".
- `std-rel-02` Do retries use exponential backoff together with alerting, and is a circuit breaker used where a failing dependency could cause cascading failures? [review] Applies to: a pipeline activity or notebook that calls an external system. Source: WAF reliability, "Apply self-preservation techniques".
- `std-rel-03` Can the workload degrade gracefully, for example by skipping non-critical steps or using cached data when a dependency is unavailable? [review] Applies to: a pipeline or report that depends on another system. Source: WAF reliability, "Apply self-preservation techniques".
- `std-rel-04` If the change adds an external dependency (upstream API, gateway, database), does it say how failure is mitigated, such as caching, queuing or a backup source? [review] Applies to: a new data source, gateway or API call. Source: WAF reliability, "Define reliability goals for your workloads"; WAF reliability, "Understand where failures happen".
- `std-rel-05` Does the test plan simulate adverse conditions, such as broken connectivity to a data source or injected load that triggers throttling, since direct chaos testing inside Fabric is not possible? [review] Applies to: tests for a new pipeline or job. Source: WAF reliability, "Test reliability".
- `std-rel-06` Is a large solution split into smaller independent pieces, such as pipelines, datasets and processing stages, so that a failure has less impact? [review] Applies to: the layout of a large solution. Source: WAF overview, "Keep workloads modular".

## Security

- `std-sec-01` Are notebooks, scripts and pipeline definitions free of embedded secrets? [gate] Applies to: a new or changed notebook, script or pipeline. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)".
- `std-sec-02` Flag a connection to a data source that uses static credentials or basic authentication when workspace identity, OAuth, a managed identity or a service principal is available. [flag] Applies to: a new connection or external data access. Source: WAF security, "Secret management"; WAF security, "Harden workload assets"; WAF security, "Use identity as the foundation for Zero Trust security controls".
- `std-sec-03` Is security validation part of the development workflow, for example static analysis, secret detection and dependency scanning in pull request validation or CI pipelines? [review] Applies to: the validation workflow of a repository with notebooks or pipelines. Source: WAF security, "Secure Development Lifecycle (SDL)".
- `std-sec-04` Flag a role assignment or item share; the guidance maps workspaces to teams, projects or environments, uses item-level or finer permissions inside them, and notes that more workspaces add management overhead. [flag] Applies to: a role assignment or item sharing. Source: WAF security, "Design isolation boundaries".
- `std-sec-14` Does a credential in code come from workspace identity or a service principal where possible, and otherwise from Azure Key Vault at run time or, in a pipeline, a key vault reference or parameterization rule? [review] Applies to: a notebook, script or pipeline that needs a credential. Source: WAF security, "Secret management"; WAF security, "Secure Development Lifecycle (SDL)".

## Cost optimization

- `std-cost-01` Does the change set a retention window or keep cached results, and does it weigh that larger retention windows raise monthly storage cost? [review] Applies to: a data retention window or a cache. Source: WAF cost, "Identify key cost drivers"; WAF cost, "Monitor costs and implement governance".
- `std-cost-02` Does the change avoid needless data movement and duplication, for example by sharing data in place through a shortcut? [review] Applies to: a new copy activity, ingestion step or cross-team data sharing. Source: WAF cost, "Model costs effectively"; WAF cost, "Consolidate costs effectively".
- `std-cost-03` If the change lets a workload autoscale, does it also set a scaling limit so that compute cannot grow unchecked? [review] Applies to: a workload that supports autoscaling. Source: WAF cost, "Monitor costs and implement governance".
- `std-cost-04` Does the design consider automating storage and workload tasks that prevent waste, for example reducing log retention, archiving datasets, purging obsolete data and optimizing Delta tables? [review] Applies to: a table, a dataset or a log retention setting. Source: WAF cost, "Reduce costs through automation".

## Operational excellence

- `std-ops-01` Does the change come with tests that run before promotion, such as tests of notebook or pipeline logic and integration checks across the full data workflow? [review] Applies to: a new or changed notebook, pipeline or semantic model. Source: WAF operations, "Deploy changes safely"; WAF operations, "Don't assume everything works".
- `std-ops-02` Does the change validate data quality, such as schema changes or missing values, and not only the code? [review] Applies to: a change to a table schema or an ingestion step. Source: WAF operations, "Don't assume everything works".
- `std-ops-03` Do tests run in dedicated test workspaces and capacities that represent production, using sample or anonymized data sources? [review] Applies to: a test or validation environment. Source: WAF operations, "Don't assume everything works".
- `std-ops-04` Does the change say how it would be rolled back, given there is no one-click rollback: redeploying from Git or a pipeline, and reconciling data where multiple stores, pipelines or models may require it? [review] Applies to: a release or a change to a data item. Source: WAF operations, "Deploy changes safely".
- `std-ops-05` Does the release pipeline run pre-deployment and post-deployment checks and alert on failure, with approvals that scale with risk and a required approval for production? [review] Applies to: a deployment pipeline or release workflow. Source: WAF operations, "Deploy changes safely"; WAF operations, "Drive deployment through code".
- `std-ops-06` If a new job, pipeline or refresh has failure alerts, are they meaningful and actionable, with an escalation path so higher severity alerts reach the right support teams? [review] Applies to: a new scheduled job, pipeline or semantic model refresh. Source: WAF operations, "Create dashboards and alerts"; WAF operations, "Monitor your environment".
- `std-ops-07` If workspace monitoring or OneLake diagnostics is turned on to investigate performance, is it selective or temporary, since logs from busy workspaces can grow quickly? [review] Applies to: a workspace monitoring or diagnostics setting used for an investigation. Source: WAF operations, "Manage monitoring data".

## Performance efficiency

- `std-perf-01` For a larger solution, does the layout consider isolating layers across workspaces or capacities, which can reduce contention, for example by separating data preparation, orchestration pipelines and presentation workloads? [review] Applies to: the workspace or capacity layout of a larger solution. Source: WAF performance, "Plan capacity intentionally".
- `std-perf-02` If the change schedules heavy background jobs off-peak, is that needed, given that smoothing spreads background workloads over 24 hours but sustained overutilization can still throttle? [review] Applies to: a pipeline or notebook schedule. Source: WAF performance, "Plan capacity intentionally"; WAF cost, "Model costs effectively".
- `std-perf-03` Do performance tests run the same mix of workloads as production, ideally on a matching capacity size, region and network setup? [review] Applies to: a performance or load test setup. Source: WAF performance, "Do performance testing".
- `std-perf-04` Do Spark jobs use well-defined partitions and parallel execution, and do SQL queries use filters and aggregations that reduce the data processed? [review] Applies to: a notebook, Spark job or SQL query. Source: WAF performance, "Optimize performance".
- `std-perf-05` Does a Power BI semantic model use techniques such as incremental refresh, query folding or aggregation tables to reduce the data that must be refreshed or queried? [review] Applies to: a Power BI semantic model. Source: WAF performance, "Optimize performance".

Note: the performance page says capacity smoothing removes the need to schedule heavy workloads off-peak, while the greenfield lakehouse page advises scheduling noncritical tasks off-peak and staggering long-running jobs, and elsewhere says bursting and smoothing let you schedule activities at any time. Source: WAF performance, "Plan capacity intentionally"; Greenfield, "Cost Optimization"; Greenfield, "Performance Efficiency".

Note: the operations page says test capacities are often smaller than production and temporarily scaled up for load tests, while the performance page says test environments should ideally match the production capacity size. Source: WAF operations, "Don't assume everything works"; WAF performance, "Do performance testing".
