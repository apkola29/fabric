# OneLake security checks for Fabric changes

Checks drawn from four OneLake security pages (best practices, the access control model, table, column and row-level security, and the data security overview), and one note that sets the data security page beside the Fabric security fundamentals page, for use when a change touches OneLake security roles, shortcuts, workspace or item permissions, or the tables and queries that OneLake security rules protect. This file guides and never authorizes a change.
The factory does not create or change a OneLake security role, a row-level or column-level rule, a workspace role, an item permission or a tenant setting; it flags such a change to a person, so a flag check names the guidance that applies. A review check is a prompt for a reviewer, not a requirement. The data security page marks the use of authorized third-party engines to enforce OneLake security as preview; no check here depends on it.
Tags: [gate] a deterministic check could verify it; [review] needs a reviewer's judgement; [flag] flag it and name the guidance, never change it. A check that starts with Ask: needs knowledge of the tenant. A Note: line is not a check; it records where pages differ or leave a choice open.

## Sources

| Label | Page | Updated | Retrieved |
|---|---|---|---|
| Best practices | https://learn.microsoft.com/fabric/onelake/security/best-practices-secure-data-in-onelake | 2026-09-01 | 2026-11-04 |
| Access model | https://learn.microsoft.com/fabric/onelake/security/data-access-control-model | 2026-10-16 | 2026-11-04 |
| Table security | https://learn.microsoft.com/fabric/onelake/security/table-column-row-security | 2026-08-19 | 2026-11-04 |
| Data security | https://learn.microsoft.com/fabric/onelake/security/get-started-security | 2026-09-29 | 2026-11-04 |
| Fundamentals | https://learn.microsoft.com/fabric/security/security-fundamentals | 2026-02-12 | 2026-11-04 |

## Item permissions and write access

- `std-olk-01` Flag an item permission granted for data access; guidance: Read alone shows no SQL or OneLake data, ReadData shows SQL data only in Delegated mode, and ReadAll shows OneLake data only through DefaultReader. [flag] Applies to: an item share or an item permission. Source: Data security, "Share items and set item-level permissions".
- `std-olk-02` Flag giving a Viewer write access; guidance: ReadWrite roles cannot hold row-level or column-level security, and ReadWrite works through Spark notebooks, OneLake file explorer or OneLake APIs, not the Lakehouse UX at this time. [flag] Applies to: a OneLake security role or a permission that lets a Viewer write data on specific folders and tables. Source: Best practices, "Least privilege"; Access model, "ReadWrite permission".

## Roles and role members

- `std-olk-03` Flag a change that edits or deletes DefaultReader; guidance: in an item with OneLake security enabled, deleting it removes data access from users who relied on it, even if they still have ReadAll. [flag] Applies to: the DefaultReader role of a lakehouse or another item with OneLake security. Source: Access model, "OneLake security and workspace permissions".

Note: the data security page shows the Viewer workspace role as not reading OneLake data by default, with a footnote that OneLake security roles can grant it, while the access model page says a default role such as DefaultReader gives users with the required permission basic access to a new item's data and applies only to Viewers; neither section says whether the Viewer role carries ReadAll. Source: Data security, "Grant access with workspace roles"; Access model, "OneLake security and workspace permissions".

- `std-olk-04` Flag a guest user or distribution list in OneLake security roles; guidance: guests need Entra External ID's most inclusive Guest user access; SQL analytics endpoints and Direct Lake on SQL cannot resolve list members. [flag] Applies to: a member added to a OneLake security role. Source: Access model, "OneLake security limitations".
- `std-olk-05` Flag a change that hides data with OneLake security; guidance: roles are grant-only and cannot deny access granted through another role or permission model, so workspace Admins, Members and Contributors stay unrestricted. [flag] Applies to: a OneLake security role or workspace access that hides tables, rows or columns. Source: Table security, "Table, column, and row-level security in OneLake"; Access model, "OneLake security roles".
- `std-olk-06` Where a user holds several OneLake security roles, does the design expect a union of their access, OR across row rules for one table, and column rules intersected only in the SQL analytics endpoint? [review] Applies to: a lakehouse where a user can belong to several OneLake security roles. Source: Access model, "Combine access across roles".

## Rules on tables, rows and columns

- `std-olk-07` Flag a role change that splits row-level and column-level rules across roles; guidance: keep rules that must apply together in one role, since that combination is unsupported and causes query errors. [flag] Applies to: a OneLake security role with row-level or column-level rules. Source: Table security, "Combine row-level and column-level security"; Access model, "Combine access across roles".

Note: the table, column and row page describes the unsupported role combination as one role with row-level rules and another with column-level rules, while the access model page describes it as two roles that allow different columns where either also applies row-level rules; the check above says to keep rules that must apply together in one role. Source: Table security, "Combine row-level and column-level security"; Access model, "Combine access across roles".

- `std-olk-08` Flag row-level or column-level rules; guidance: OneLake denies access unless the table is in `Tables/` (in a valid schema folder for schema-enabled items), has a `_delta_log` folder with metadata JSON files and no child shortcuts. [flag] Applies to: a table or a shortcut in a lakehouse that gets row-level or column-level rules. Source: Access model, "Table-level security".
- `std-olk-09` Flag a column change to a table with row-level or column-level rules; guidance: a rule mismatched with its table, such as one naming a missing column, makes queries fail and return no data. [flag] Applies to: a change to the columns of a table that has row-level or column-level rules. Source: Table security, "Column-level and row-level security".
- `std-olk-10` Does a select-all query expect, for a user with access to only some columns, Spark notebooks to return the allowed columns but the SQL analytics endpoint and semantic models to return an error? [review] Applies to: a notebook, SQL query, test or semantic model that reads a table with column-level security. Source: Table security, "Column-level security".

## Shortcuts and identity

- `std-olk-11` Flag a change to a SQL analytics endpoint's identity mode; guidance: user's identity mode evaluates OneLake security per user, while delegated identity mode uses the owner identity of the consumer item or data source. [flag] Applies to: a SQL analytics endpoint of a lakehouse that uses OneLake security. Source: Best practices, "Primary pattern"; Access model, "OneLake security in passthrough shortcuts".
- `std-olk-12` Does a new shortcut state passthrough (normally the user's identity, the default between OneLake locations) or delegated (a configured connection, always used for external systems), noting that query engine identity is a separate setting? [review] Applies to: a new shortcut, or a semantic model or SQL analytics endpoint that reads through one; Direct Lake over SQL, and SQL analytics endpoints whose identity mode is delegated, use the owner identity of the consumer item or data source. Source: Access model, "Shortcuts"; Access model, "OneLake security in passthrough shortcuts".
- `std-olk-13` Does a test of access through a shortcut to another OneLake location open the shortcut, not only list the directory, since listing returns every internal shortcut whatever the user's access to the target? [review] Applies to: a test or verification of access through a shortcut. Source: Access model, "Folder permission inheritance and traversal".
- `std-olk-14` Ask: for a shortcut that uses OneLake security, is the OneLake tenant setting "Users can access data stored in OneLake with apps external to Fabric" turned on, since shortcuts with OneLake security require it? [flag] Applies to: a new shortcut in a lakehouse that uses OneLake security. Source: Data security, "Allow apps running outside of Fabric to access data".

## Architecture and environment

- `std-olk-15` Does the design follow the recommended baseline for OneLake security at scale: one primary workspace holding the data and its rules, shared to downstream workspaces through shortcuts, though some scenarios might need another approach? [review] Applies to: a lakehouse and downstream workspaces that use OneLake security. Source: Best practices, "Primary pattern".

Note: the best practices page calls the primary workspace pattern the recommended baseline for OneLake security at scale and says some scenarios might need another approach because of current network security constraints, without naming the constraints or the approach; the page leaves open whether a given deployment is affected, and it gives data consumption, additional workloads and domain-specific use cases as the reasons for downstream workspaces. Source: Best practices, "Primary pattern".

- `std-olk-16` Does a Spark notebook that works with OneLake security run in an environment of 3.5 or higher on Fabric runtime 1.3, which the page's limitations require? [review] Applies to: a Spark notebook that works with a lakehouse that uses OneLake security; std-eng-01 asks a new Spark workload to start on the latest runtime, and the pages do not say how that fits this limitation. Source: Access model, "OneLake security limitations".

## Encryption in transit

Note: this page says that when Fabric communicates outward to customer-owned infrastructure it prefers secure protocols, yet might fall back to older, insecure ones (the page names TLS 1.0) if newer ones are unsupported, while inbound OneLake communication enforces TLS 1.2; the Fundamentals page says that such outbound communication now needs TLS 1.2 or later and no longer supports TLS 1.0 or TLS 1.1; `std-sec-11` of the security and governance file asks whether a customer-owned source supports TLS 1.2 or later; the pages differ, this file does not rank them, and that question still applies. Source: Data security, "Encrypt data in transit by using TLS"; Fundamentals, "Data in transit".
