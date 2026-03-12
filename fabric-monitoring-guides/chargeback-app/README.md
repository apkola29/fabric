# Chargeback App — Build Your Own Reports

A guide to building **custom Power BI reports** on top of the Fabric Chargeback App semantic model — without modifying it.

## Why Build Custom Reports?

The built-in Chargeback App shows utilization by workspace, item, and domain — but the views are fixed and only capacity admins can see them. By creating your own report connected to the same semantic model, you can:

- **Build department-level chargeback reports** — group workspaces by cost center, team, or business unit
- **Share with finance and team leads** — give non-admins visibility into who's consuming what
- **Track per-user consumption** — see which users drive the most CU usage
- **Create daily/weekly cost trends** — the built-in app only shows current state, not trends over time
- **Combine both apps** — use Chargeback data alongside Capacity Metrics data for a complete picture

## Prerequisites

- The **Fabric Chargeback App** must be installed in your tenant ([install guide](https://learn.microsoft.com/en-us/fabric/enterprise/chargeback-app-install))
- You need access to the app's workspace and semantic model

## How to Connect

1. Open **Power BI Desktop**
2. Select **Get Data** → **Power BI datasets** (or **Semantic models**)
3. Find **"Fabric Chargeback Reporting"** in the list
4. Select it and click **Connect**
5. Build your report using the tables and measures below
6. Publish to a workspace and share

Alternatively, in the **Fabric portal**:
1. Go to the Chargeback App workspace
2. Find the semantic model → **Create a report** → **From scratch**

## Data Model Reference

### Tables at a Glance

The semantic model contains **10 tables** (31 measures).

> **Note**: This schema was verified against the latest version of the Chargeback App using the Scanner API on March 12, 2026.

| Table | Columns | Description |
|---|---|---|
| **Chargeback** | 12 | The main fact table — CU consumption per item, user, operation, and day |
| **Capacities** | 5 | Capacity inventory — ID, name, SKU, region, core count |
| **Items** | 5 | Fabric items — ID, name, type, virtualization status |
| **Workspaces** | 2 | Workspace ID and name |
| **Dates** | 9 | Calendar dimension — day, week, month, quarter, year |
| **Domains** | 5 | Domain and subdomain mapping for organizational grouping |
| **All Measures** | 0 | Home table for 31 DAX measures |
| **Top N Selector** | 1 | Top-N filter control (hidden) |
| **Days Ago to Start** | 1 | Configurable date range parameter (hidden) *(new)* |
| **Export page optional columns** | 3 | Column selector for the built-in export page *(new)* |

### Table Schema Details

#### Chargeback

The main fact table. Each row represents CU consumption for a specific item + operation + user + day combination.

| Column | Type | Description |
|---|---|---|
| `Capacity Id` | Text | Capacity identifier |
| `Date` | DateTime | The day the consumption occurred |
| `Item Id` | Text | Fabric item identifier |
| `Billing type` | Text | "Billable" or "Nonbillable" |
| `Operation name` | Text | The Fabric operation (e.g., "Interactive query", "Semantic model refresh", "Eventstream Per Hour") |
| `User` | Text | The user who triggered the operation (blank for system/service operations) |
| `Workspace Id` | Text | Workspace where the item resides |
| `CU (s)` | Double | Capacity Units consumed in seconds |
| `Duration (s)` | Double | Total duration in seconds |
| `Operations` | Int64 | Number of operations |
| `Experience` | Text | Workload type code (e.g., "PBI" for Power BI, "ES" for EventStream, "DW" for Warehouse) |
| `Domain unique key` | Text | Key linking to the Domains table (blank if workspace has no domain) |

**This is the key table.** It has what the Capacity Metrics App doesn't: per-user, per-operation, per-day granularity with domain mapping.

---

#### Capacities

Capacity inventory (simplified compared to the Capacity Metrics App version).

| Column | Type | Description |
|---|---|---|
| `Capacity Id` | Text | Unique capacity identifier |
| `Capacity name` | Text | Display name |
| `SKU` | Text | SKU tier (F2, F8, F64, etc.) |
| `Region` | Text | Azure region |
| `Core count` | Int64 | Number of cores |

---

#### Items

Fabric items with virtualization status.

| Column | Type | Description |
|---|---|---|
| `Item Id` | Text | Unique item identifier |
| `Item kind` | Text | Item type (Dataset, Lakehouse, Warehouse, EventStream, etc.) |
| `Item name` | Text | Display name |
| `Virtualised item` | Text | "Non-virtualized item" or virtualization status |
| `Virtualised workspace` | Text | "Non-virtualized workspace" or virtualization status |

---

#### Workspaces

Workspace dimension.

| Column | Type | Description |
|---|---|---|
| `Workspace Id` | Text | Unique workspace identifier |
| `Workspace name` | Text | Display name |

---

#### Dates

Rich calendar dimension.

| Column | Type | Description |
|---|---|---|
| `Date` | DateTime | Calendar date |
| `Day` | Int64 | Day of month (1-31) |
| `Year` | Int64 | Year |
| `Quarter` | Text | Quarter label (Q1, Q2, Q3, Q4) |
| `Week number` | Int64 | ISO week number |
| `First Day of Week` | DateTime | Monday of that week |
| `Month` | Text | Month name (January, February, etc.) |
| `Day Month` | DateTime | Date (display format) |
| `Month Year` | DateTime | First day of the month |

---

#### Domains

Domain and subdomain mapping for organizational chargeback grouping.

| Column | Type | Description |
|---|---|---|
| `Domain unique key` | Text | Key linking to the Chargeback table |
| `Domain Id` | Text | Domain identifier *(new)* |
| `Domain` | Text | Domain name (or "No domain" if unassigned) |
| `Subdomain Id` | Text | Subdomain identifier |
| `Subdomain` | Text | Subdomain name (or "No subdomain" if unassigned) |

**Use for**: Grouping chargeback by organizational unit. Domains are configured in the Fabric admin portal.

---

### Experience Codes

The `Experience` column in the Chargeback table uses short codes for workload types:

| Code | Workload |
|---|---|
| PBI | Power BI |
| DW | Data Warehouse |
| ES | EventStream |
| DE | Data Engineering (Spark) |
| DS | Data Science |
| DF | Data Factory |
| KQL | KQL Database / Real-Time Intelligence |
| OL | OneLake |

### Example DAX Queries

**Top 10 items by CU consumption:**
```dax
EVALUATE
TOPN(10,
    SUMMARIZECOLUMNS(
        Items[Item name],
        Items[Item kind],
        "Total CU", SUM(Chargeback[CU (s)])
    ),
    [Total CU], DESC
)
```

**CU consumption by workspace:**
```dax
EVALUATE
SUMMARIZECOLUMNS(
    Workspaces[Workspace name],
    "Total CU", SUM(Chargeback[CU (s)]),
    "Total Ops", SUM(Chargeback[Operations])
)
```

**CU consumption by user:**
```dax
EVALUATE
TOPN(10,
    SUMMARIZECOLUMNS(
        Chargeback[User],
        "Total CU", SUM(Chargeback[CU (s)])
    ),
    [Total CU], DESC
)
```

**CU by domain (for chargeback):**
```dax
EVALUATE
SUMMARIZECOLUMNS(
    Domains[Domain],
    Domains[Subdomain],
    "Total CU", SUM(Chargeback[CU (s)]),
    "Total Duration", SUM(Chargeback[Duration (s)])
)
```

**Daily CU trend:**
```dax
EVALUATE
SUMMARIZECOLUMNS(
    Dates[Date],
    "Daily CU", SUM(Chargeback[CU (s)])
)
```

**CU by workload type (Experience):**
```dax
EVALUATE
SUMMARIZECOLUMNS(
    Chargeback[Experience],
    "Total CU", SUM(Chargeback[CU (s)]),
    "Total Ops", SUM(Chargeback[Operations])
)
```

**Capacity inventory:**
```dax
EVALUATE Capacities
```

## Custom Report Ideas

| Report | What it shows | Value |
|---|---|---|
| **Department Chargeback** | CU consumption grouped by domain/subdomain with daily trends | Bill teams for their actual usage |
| **Top Users** | Users ranked by CU consumption across all workspaces | Identify heavy users |
| **Workload Mix** | CU breakdown by Experience (Power BI vs. Warehouse vs. Spark) | Understand which workloads drive cost |
| **Daily Cost Trend** | Daily CU consumption with week-over-week comparison | Spot usage spikes and growth |
| **Operation Breakdown** | CU by operation type (queries vs. refreshes vs. pipelines) | Identify optimization targets |
| **Billable vs Non-Billable** | Split consumption by billing type | Understand preview feature exposure |
| **Cross-Capacity View** | Compare CU consumption across multiple capacities | Multi-capacity management |

## Chargeback App vs Capacity Metrics App

| Feature | Chargeback App | Capacity Metrics App |
|---|---|---|
| **Per-user data** | Yes | No |
| **Per-operation name** | Yes | Yes (in timepoint detail tables) |
| **Domain/subdomain grouping** | Yes | No |
| **Daily granularity** | Yes | 30-second granularity |
| **Throttling data** | No | Yes |
| **Storage data** | No | Yes |
| **Overage/carryforward** | No | Yes |
| **Memory data** | No | Yes |
| **Surge protection** | No | Yes *(new in v54)* |
| **Item history trending** | No | Yes *(new in v54)* |
| **Usage health (P95, risk)** | No | Yes *(new in v54)* |
| **Workload autoscale** | No | Yes *(new in v54)* |
| **Data retention** | 14 or 30 days (configurable) | 14 days |
| **Tables** | 10 | 105 |
| **Measures** | 31 | 294 |

**Best combination**: Use the Chargeback App for cost allocation (who/what consumed CU) and the Capacity Metrics App for performance monitoring (utilization, throttling, overages).

## Limitations

- **Do not modify** the semantic model — Microsoft explicitly states this is unsupported
- **Data retention** — 14 or 30 days depending on configuration during install
- **User masking** — if the admin setting "Show user data in the Fabric Capacity Metrics app and reports" is disabled, usernames appear as "Masked user"
- **Service operations** — operations triggered by service principals show as "Power BI Service" instead of a user
- **Schema may change** without notice when the app is updated
- **Preview status** — the Chargeback App is currently in preview

## Related Resources

- [What is the Chargeback App?](https://learn.microsoft.com/en-us/fabric/enterprise/chargeback-app)
- [Install the Chargeback App](https://learn.microsoft.com/en-us/fabric/enterprise/chargeback-app-install)
- [Fabric Operations Reference](https://learn.microsoft.com/en-us/fabric/enterprise/fabric-operations)

## Disclaimer

This guide is provided **as-is** with no warranty of any kind. The semantic model schema was discovered through testing and may change when Microsoft updates the app. Use at your own risk.

## License

This project is licensed under the [MIT License](../../LICENSE).
