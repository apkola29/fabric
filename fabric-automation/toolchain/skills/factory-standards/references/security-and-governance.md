# Security and governance checks for Fabric changes

Checks drawn from Fabric security fundamentals, Security in Microsoft Fabric, the Azure security baseline for Fabric, two governance pages and the Well-Architected security page, for use when a change touches identity, boundaries, network, data protection, logging or ownership. This file guides and never authorizes a change.
The factory does not implement security, permission, network, sensitivity-label or tenant-setting changes; it refuses and escalates them, so these checks say to flag a change and name the guidance that applies. The baseline page is based on version 1.0 of the Microsoft cloud security benchmark and may contain outdated guidance, and the Well-Architected security page calls the baseline a starting point, not a checklist. The adoption roadmap page says it is not a comprehensive reference for data governance.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. Baseline controls are cited by section and title, without their control codes.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| Fundamentals | https://learn.microsoft.com/fabric/security/security-fundamentals | 2026-02-12 | 2026-11-01 |
| Security overview | https://learn.microsoft.com/fabric/security/security-overview | 2026-09-29 | 2026-11-01 |
| Baseline | https://learn.microsoft.com/security/benchmark/azure/baselines/fabric-security-baseline | 2026-08-25 | 2026-11-01 |
| CAF governance | https://learn.microsoft.com/azure/cloud-adoption-framework/data/fabric-governance-unified-data-platform | 2026-10-27 | 2026-11-01 |
| Roadmap governance | https://learn.microsoft.com/power-bi/guidance/fabric-adoption-roadmap-governance | 2026-01-02 | 2026-11-01 |
| WAF security | https://learn.microsoft.com/azure/well-architected/microsoft-fabric/security | 2026-05-14 | 2026-11-01 |
| CICD concepts | https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd | 2026-09-09 | 2026-11-01 |

## Identity and access

- `std-sec-05` Flag a workspace role change; the guidance says to assign roles to Microsoft Entra security groups, not individuals, to restrict Admin and Member because they can manage or share content, and to grant least privilege. [flag] Applies to: a workspace role assignment. Source: CAF governance, "2. Fabric data security"; Baseline, "Asset Management" (control "Limit access to asset management").
- `std-sec-06` Ask: are workspace and tenant administrator assignments limited, with care when delegating settings, and is privileged identity management used so elevated rights are active only when needed? [flag] Applies to: a change that adds an administrator or delegates settings. Source: WAF security, "Harden workload assets"; Baseline, "Privileged access" (control "Separate and limit highly privileged/administrative users").
- `std-sec-17` Flag a change to who may create workspaces; guidance: restrict workspace creation to admins to prevent sprawl and misconfigurations. [flag] Applies to: a tenant setting for workspace creation. Source: WAF security, "Harden workload assets".

## Workspace and item boundaries

- `std-sec-07` Flag a request to give someone access to one item; guidance: use item permissions, and remember that sharing an item does not necessarily allow querying its underlying OneLake data. [flag] Applies to: item sharing or an item permission. Source: CAF governance, "2. Fabric data security"; Fundamentals, "Item security".
- `std-sec-08` Flag a change where audiences sharing one data product must not see the same records or tables; guidance: OneLake security or an experience-specific control, such as row-level, column-level or object-level security for viewers. [flag] Applies to: a lakehouse, warehouse or semantic model with several audiences. Source: CAF governance, "2. Fabric data security"; Security overview, "Limit access".
- `std-sec-09` Flag a workspace created only to mirror boundaries that item permissions or OneLake security can enforce reliably; the guidance applies separate workspaces when data products need materially different administration, deployment or network controls. [flag] Applies to: a new workspace or a workspace layout. Source: CAF governance, "2. Fabric data security".

Note: the governance page advises against extra workspaces that only reproduce boundaries which item permissions or OneLake security can enforce reliably, while the CI/CD concepts page says that splitting a medallion solution into a staging workspace and a presentation workspace is the best way to keep business users away from staging data, because a workspace role grants access to everything in the workspace. Source: CAF governance, "2. Fabric data security"; CICD concepts, "Fabric solutions".

## Network

- `std-sec-10` Flag a notebook, lakehouse or Spark job definition that must reach a data source behind a private endpoint; the guidance says to create and use managed private endpoints for supported workloads and data sources. [flag] Applies to: a new connection from a notebook, lakehouse or Spark job. Source: Baseline, "Network Security" (control "Establish network segmentation boundaries"); CAF governance, "3. Fabric networking".
- `std-sec-11` Ask: does the customer-owned data source in the change support TLS 1.2 or later, since outbound communication no longer supports older protocols such as TLS 1.0 and TLS 1.1? [flag] Applies to: a new connection to customer-owned infrastructure. Source: Fundamentals, "Data in transit".
- `std-sec-16` Flag a tenant-level private link or network restriction; guidance: use workspace-level private links where supported for selected workspaces, tenant-level links when requirements apply across Fabric, and assess the broader operational effect before tenant-level restrictions. [flag] Applies to: a private link or network access setting for Fabric. Source: CAF governance, "3. Fabric networking".

## Data protection

- `std-sec-12` Ask: will a new item that holds sensitive data carry a Microsoft Purview sensitivity label, which follows the data from item to item and into supported exports? [flag] Applies to: a new lakehouse, warehouse, semantic model or report. Source: Security overview, "Protect data"; Baseline, "Data Protection" (control "Discover, classify, and label sensitive data").
- `std-sec-15` Flag a customer-managed key for a workspace; guidance: not every Fabric artifact currently supports it, so workspace segmentation may be needed, and workspace data becomes inaccessible until a disabled or deleted key is restored. [flag] Applies to: an encryption or key setting for a workspace. Source: WAF security, "Data encryption".

## Auditing and logging

- `std-sec-13` Ask: are the default activity and audit logs enough for the data the change touches, or does a high-value asset need the optional workspace-level logging and monitoring? [flag] Applies to: a change that adds or alters a high-value asset. Source: Baseline, "Logging and Threat Detection" (control "Enable logging for security investigation").

## Governance and ownership

- `std-gov-01` Flag a change to access, data sensitivity level, network configuration or administrative privilege assignment on a tenant, capacity or workspace, a potentially high-impact modification that the baseline wants security policy or process to cover. [flag] Applies to: a change to access, data sensitivity level, network configuration or administrative privileges on a tenant, capacity or workspace. Source: Baseline, "Asset Management" (control "Ensure security of asset lifecycle management").
- `std-gov-02` Flag a change that resizes a shared capacity, alters overage settings or weakens surge protection; guidance: central administration, and an approval process for changes that can raise cost or affect other domains. [flag] Applies to: settings or permissions for a shared capacity. Source: CAF governance, "1.2 Permissions".
- `std-gov-03` Does each production data product name an operational owner accountable for monitoring and response, and does a business-critical one normally have automated failure alerts and an escalation path? [review] Applies to: a new production pipeline, model or report. Source: CAF governance, "4. Fabric monitoring".
- `std-gov-04` Does the monitoring plan confirm which of the items in use workspace monitoring supports, rather than assuming complete coverage, and avoid relying only on the Monitor hub capacity view, which is currently in preview? [review] Applies to: a monitoring or alerting change. Source: CAF governance, "4. Fabric monitoring".
- `std-gov-05` Does the change say which release pattern applies, chosen from the business effect of a failed release and not from criticality alone, with a repeatable release process for the production data product? [review] Applies to: a release process or a new production data product. Source: CAF governance, "5. Deployment".
- `std-gov-06` For a lower-risk release, are the deployed version and the recovery process documented? [review] Applies to: a release where failure has limited business effect and restoring is easy. Source: CAF governance, "5. Deployment".
- `std-gov-07` Does a medium-risk release require source control, development isolation and validation before production, and a high-risk release require source control, production isolation, validation by an independent person or automated control, and a tested recovery process? [review] Applies to: a release with several contributors, frequent releases, or an important business process or organizational reporting. Source: CAF governance, "5. Deployment".
- `std-gov-10` Where a Fabric item does not support Git integration or deployment pipelines, does the release use an approved alternative to the pattern that needs them? [review] Applies to: a release of an item that cannot use Git integration or deployment pipelines. Source: CAF governance, "5. Deployment".
- `std-gov-08` Ask: does the organization's data ownership policy require an owner for the new data asset, and is one named? [review] Applies to: a new lakehouse, semantic model or report. Source: Roadmap governance, "Data policies".
- `std-gov-09` Ask: does the change involve personally identifiable or regulated data, which should face stricter governance, or critical data, which usually does, with additional requirements such as data quality verifications and documentation? [review] Applies to: a change that handles sensitive or business-critical content. Source: Roadmap governance, "Decision criteria"; Roadmap governance, "Key Fabric governance decisions".
