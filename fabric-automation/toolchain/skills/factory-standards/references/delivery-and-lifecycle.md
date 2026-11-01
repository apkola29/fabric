# Delivery and lifecycle checks for Fabric changes

Checks drawn from two pages on lifecycle management in Fabric: best practices for lifecycle management, and CI/CD concepts and best practices. They cover Git integration, branching, workspace layout, environments, deployment pipelines, parameterization, what stays out of a branch, and testing and release. This file guides and never authorizes a change.
The concepts page says that not every recommendation applies to every project, so choose the practices that match the solution's scale, governance requirements and release process. Checks that touch permissions or identity carry the flag tag, because the factory flags them and does not change them. The release-pattern checks in the governance file (std-gov-05 to std-gov-07 and std-gov-10) complement these.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. What a change itself contains, such as a credential file, is not a change to a setting: it is a [gate] when a program can decide it.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| Lifecycle | https://learn.microsoft.com/fabric/cicd/best-practices-cicd | 2026-07-22 | 2026-11-01 |
| CICD concepts | https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd | 2026-09-09 | 2026-11-01 |
| WAF cost | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/cost-optimization | 2026-05-14 | 2026-11-01 |

## Git integration and branching

- `std-del-01` Ask: once item definitions exist in a feature-workspace project, does the change arrive by pull request from a feature branch, and does a policy on the integration branch permit updates only through pull requests? [review] Applies to: a change to item definitions under the feature-workspace process. Source: CICD concepts, "Feature workspaces"; CICD concepts, "Continuous integration development process".
- `std-del-02` Does the Git folder setting separate item definitions from workflow files, where the repository holds both, and does each workspace of a multi-workspace solution use its own folder on one shared branch? [review] Applies to: a Git connection or repository layout. Source: CICD concepts, "Git folder settings"; CICD concepts, "Continuous integration development process".
- `std-del-03` For an Azure Pipelines workflow, does the design consider a pull request validation pipeline that checks files, runs tests or validates item definitions before reviewers approve, kept separate from the release pipeline? [review] Applies to: an Azure Pipelines workflow definition. Source: CICD concepts, "Azure Pipelines workflows".

Note: the concepts page describes two development processes. With feature workspaces it says not to update items or commit directly in the dev workspace once the item definitions exist; for the simplest scenario with a deployment pipeline it describes direct updates and commits in the dev workspace, and offers feature workspaces as the scalable alternative. Source: CICD concepts, "Feature workspaces"; CICD concepts, "Release process options".

## Item definitions and dependencies

- `std-del-04` Does every item folder follow the pattern of display name, a period and item type, and contain the required .platform file with the item type, display name and logicalId? [gate] Applies to: a new or renamed item. Source: CICD concepts, "Git synchronization"; CICD concepts, "Item definitions".
- `std-del-05` Does the change leave every existing logicalId unchanged, since Fabric does not support modifying it and doing so can lead to unpredictable behavior? [gate] Applies to: a change to an existing item; a copied item folder is covered by std-del-06. Source: CICD concepts, "The role of the logicalId".
- `std-del-06` When an item is duplicated in Git, is the whole item folder copied, with a logicalId unique for that connected workspace and a new display name, and are dependencies updated where needed? [review] Applies to: a copied item. Source: Lifecycle, "Duplicate an item in a Git repository".
- `std-del-07` Does a new notebook with same-workspace dependencies include notebook-settings.json for auto-binding, and do items without auto-binding use a post-sync script to restore their relations? [review] Applies to: a new notebook, pipeline or other item with dependencies. Source: CICD concepts, "Auto-binding support"; CICD concepts, "Continuous integration development process".

Note: the concepts page says never to modify a logicalId, while the lifecycle page's steps for duplicating an item say to give the copy a unique logicalId; the pages do not say how the two fit together. Source: CICD concepts, "The role of the logicalId"; Lifecycle, "Duplicate an item in a Git repository".

## Environments and workspace layout

- `std-del-08` Does each environment have its own workspace or workspaces and, as the recommended practice, its own capacity, noting that all environments can share one capacity? [review] Applies to: a workspace layout or a deployment pipeline stage. Source: CICD concepts, "Fabric CI/CD projects".
- `std-del-09` Do development and test semantic models use their own databases, so production is not overloaded by their queries, with the test database as similar to production as possible when test simulates real-life data usage? [review] Applies to: a data source connection of a semantic model promoted through stages. Source: Lifecycle, "Connect different stages to different databases"; Lifecycle, "Use deployment rules with a real-life data source".
- `std-del-10` Flag a change to who can deploy to production; guidance: only specific people, through production workspace permissions, while other users can have the viewer role. [flag] Applies to: a workspace role or a pipeline permission. Source: Lifecycle, "Manage who can deploy to production".
- `std-del-23` Flag a change to access to the repository or the deployment pipeline; guidance: limit it to users who take part in content creation, probably including all BI creators of the workspace for the pipeline. [flag] Applies to: access to the repository or the deployment pipeline. Source: Lifecycle, "Manage who can deploy to production".

Note: the concepts page recommends a separate capacity for each environment, while the Well-Architected cost page says development and test workloads with similar requirements can share one capacity that is paused or downsized outside working hours. Source: CICD concepts, "Fabric CI/CD projects"; WAF cost, "Consolidate costs effectively".

## What to parameterize

- `std-del-11` Where the item type supports it, do environment-specific settings, such as database server and name, come from a variable library with value sets per environment, instead of being hardcoded? [review] Applies to: a notebook, pipeline, copy job or dataflow that connects to a data source. Source: CICD concepts, "Variable libraries"; CICD concepts, "Parameterization for environment-specific settings"; CICD concepts, "Workspace item types".
- `std-del-12` Where the item type supports variable libraries, are connections to external data sources held in connection reference variables, and are dependencies that cross workspaces held in item reference variables? [review] Applies to: a pipeline, a lakehouse shortcut or another item that connects to an external source, or a cross-workspace dependency. Source: CICD concepts, "Variable libraries"; CICD concepts, "Auto-binding support"; CICD concepts, "Workspace item types".
- `std-del-13` Ask: if a semantic model is promoted through a deployment pipeline, are production deployment rules set for its data sources and parameters? [review] Applies to: a semantic model in a deployment pipeline. Source: Lifecycle, "Set rules to ensure production stage availability".
- `std-del-14` Where an environment-specific value stays in a committed item definition, such as a semantic model's data-source path, is it updated per environment, for example by a deployment rule, fabric-cicd parameterization or a post-sync job? [review] Applies to: a committed connection string or data-source path. Source: CICD concepts, "Release process options"; CICD concepts, "The fabric-cicd library"; CICD concepts, "Deployment pipelines".
- `std-del-20` Ask: which value set is active in each workspace for a variable library, given that the item definition does not record it? [review] Applies to: a variable library promoted across environments. Source: CICD concepts, "Variable libraries".

Note: the lifecycle page uses parameter rules, and in another section deployment rules, for stage-specific settings, while the concepts page says deployment rules are still supported but variable libraries should usually be the first choice. Source: Lifecycle, "Use parameters for configurations that will change between stages"; Lifecycle, "Use deployment rules with a real-life data source"; CICD concepts, "Deployment pipelines".

## What belongs in a branch

- `std-del-15` Does the branch exclude files that hold sensitive credentials, for example terraform.tfvars with a service principal client secret, and reference workflow secrets from the Git provider instead of hardcoding them? [gate] Applies to: any file added to the repository, including workflow and infrastructure files. Source: CICD concepts, "Terraform for project infrastructure"; CICD concepts, "Security best practices"; CICD concepts, "Azure Pipelines workflows"; CICD concepts, "GitHub Actions workflows".

## Testing, release and rollback

- `std-del-16` For a change to a data item definition, do commit messages describe the change, and was its effect on existing data tried first in dev or test with test data? [review] Applies to: an item that stores data. Source: Lifecycle, "Updating data items".
- `std-del-17` When a lakehouse schema change is shipped as notebook logic, is the notebook also run in each target workspace, and are warehouse schema changes managed with SqlPackage and Data-tier Application Framework tooling? [review] Applies to: a table schema change. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".
- `std-del-18` Does a lakehouse solution expose one top-level item, such as a pipeline or notebook, that populates all lakehouses, with scheduled refresh jobs for its notebooks and pipelines kept in .schedules files in the item definitions? [review] Applies to: a lakehouse solution, or a scheduled refresh job of a notebook or pipeline. Source: CICD concepts, "Data orchestration"; CICD concepts, "Data orchestration strategy".
- `std-del-19` Flag automation that runs as a user principal; guidance: use a service principal whenever possible, noting that some item types, especially in public preview, may not support service principals yet. [flag] Applies to: a workflow or script that calls Fabric APIs. Source: CICD concepts, "Automation targets"; CICD concepts, "Workspace item types".
- `std-del-21` Does a post-deploy script avoid ETL logic, leaving it to workspace items built for ETL, for example notebooks, pipelines, copy jobs, user-defined functions or dataflows? [review] Applies to: a post-deploy script. Source: CICD concepts, "Automation targets".
- `std-del-22` If an app distributes the content, does the release update that app through the deployment pipelines API, since a deployment through the UI does not? [review] Applies to: a report or app in a deployment pipeline. Source: Lifecycle, "Update the production app".
