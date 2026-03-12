# Capacity Metrics App — Build Your Own Reports

A guide to building **custom Power BI reports** on top of the Fabric Capacity Metrics App semantic model—without modifying it.

## Why Build Custom Reports?

The built-in Capacity Metrics App gives you standard views — but you can't customize them, and only capacity admins can see them. By creating your own report connected to the same semantic model, you can:

- **Build exactly the views you need** — focus on what matters to your team
- **Share with non-admins** — give workspace owners, team leads, or finance visibility into capacity usage without granting admin access
- **Combine with other data** — overlay your own department/cost-center mappings
- **Pin to a dashboard** — create a single-pane-of-glass for capacity health

## Prerequisites

- The **Capacity Metrics App** must be installed in your tenant ([install guide](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-install))
- You need access to the app's workspace and semantic model

## How to Connect

1. Open **Power BI Desktop**
2. Select **Get Data** → **Power BI datasets** (or **Semantic models**)
3. Find **"Fabric Capacity Metrics"** in the list
4. Select it and click **Connect**
5. Build your report using the tables and measures below
6. Publish to a workspace and share

Alternatively, in the **Fabric portal**:
1. Go to the Capacity Metrics App workspace
2. Find the semantic model → **Create a report** → **From scratch**

## Data Model Reference

### Tables at a Glance

The semantic model contains **105 tables** (294 measures).

> **Note**: This schema was verified against the **v54** version of the Capacity Metrics App using the Scanner API on March 12, 2026. Column names use spaced format (e.g., `Capacity Id` not `capacityId`).

#### Dimension Tables

| Table | Columns | Description |
|---|---|---|
| **Capacities** | 9 | Fabric capacities — ID, name, SKU, region, state, owners |
| **Items** | 15 | Every Fabric item with workspace/capacity links |
| **Items Throttled** | 15 | Items affected by throttling events |
| **Workspaces** | 5 | Workspaces with capacity assignment |
| **Dates** | 4 | Calendar dimension (Date, Start of month, First day of week, Day) |
| **Datetime** | 4 | Date/time dimension with hour-level granularity |
| **Timepoints** | 8 | 30-second interval timestamps (last 14 days) — primary time axis |
| **TimePoints2** | 4 | 6-minute interval timestamps — aggregated time axis |
| **Billing Type** | 1 | Billable / Nonbillable filter dimension |
| **Item Kind** | 2 | Item type dimension |
| **Workloads** | 1 | Workload type dimension |
| **Workload For Storage** | 2 | Workload types for storage views |
| **Operation For Storage** | 2 | Operation types for storage views |
| **Operation Names** | 1 | Operation name dimension |
| **Metrics** | 2 | Internal placeholder table for DAX measures |
| **Date Start** | 1 | Start date parameter (new in v54) |
| **Date End** | 1 | End date parameter (new in v54) |

#### Fact Tables — Compute (30-second granularity)

| Table | Columns | Description |
|---|---|---|
| **Timepoint CU Detail** | 23 | CU utilization per 30-second timepoint with peak metrics |
| **Timepoint Interactive Detail** | 22 | Interactive operation detail per 30-second timepoint |
| **Timepoint Background Detail** | 22 | Background operation detail per 30-second timepoint |
| **Timepoint Overage Detail** | 11 | Overage/carryforward detail per timepoint |
| **Timepoint Overages By Workloads** | 9 | Overages broken down by workload type |
| **Timepoint Interactive Item Detail** | 13 | Per-operation-ID interactive detail within a timepoint *(new in v54)* |
| **Timepoint Background Item Detail** | 14 | Per-operation-ID background detail within a timepoint *(new in v54)* |
| **Timepoint Interactive Summary** | 7 | Aggregated interactive CU/duration/throttling per timepoint *(new in v54)* |
| **Timepoint Background Summary** | 7 | Aggregated background CU/duration/throttling per timepoint *(new in v54)* |

#### Fact Tables — Compute (6-minute granularity)

| Table | Columns | Description |
|---|---|---|
| **Timepoint2 CU Detail** | 23 | CU utilization per 6-minute timepoint |
| **Timepoint2 Interactive Detail** | 22 | Interactive operation detail (6-min aggregation) |
| **Timepoint2 Background Detail** | 22 | Background operation detail (6-min aggregation) |
| **Timepoint2 Overages By Workloads** | 9 | Overages by workload (6-min aggregation) |

#### Fact Tables — Item Metrics

| Table | Columns | Description |
|---|---|---|
| **CU Detail** | 25 | Core CU consumption with throttling percentages |
| **Metrics By Item** | 23 | Aggregated metrics (CU, duration, ops, users) per item |
| **Metrics By Item And Operation** | 24 | Metrics by item + operation type |
| **Metrics By Item Operation And Day** | 22 | Daily metrics by item + operation |
| **Max Memory By Item** | 5 | Peak memory consumption per item |
| **Max Memory By Item And Hour** | 6 | Peak memory per item per hour |
| **Items Operations** | 17 | Operation-level metadata per item with user counts and release type *(new in v54)* |

#### Fact Tables — Storage

| Table | Columns | Description |
|---|---|---|
| **Storage By Workspaces** | 5 | Current storage consumption per workspace |
| **Storage By Workspaces And Day** | 11 | Daily storage trends per workspace |
| **Storage By Workspaces And Hour** | 11 | Hourly storage per workspace |

#### Fact Tables — Usage Health *(new in v54)*

Pre-aggregated capacity health snapshots at multiple time windows.

| Table | Columns | Description |
|---|---|---|
| **Usage Summary (Last 1 hour)** | 17 | Minute-level CU %, throttling risk, cumulative debt, P95 metrics, usage variance |
| **Usage Operation (Last 1 hour)** | 19 | Per-operation second-level breakdown with rejection/failure counts |
| **Usage Summary (Last 24 hours)** | 17 | Hourly CU %, throttling risk, cumulative debt |
| **Usage Operation (Last 24 hours)** | 19 | Per-operation hourly breakdown |
| **Usage Summary (Last 7 days)** | 9 | Hourly CU %, throttling, average utilization |
| **Usage Operation (Last 7 days)** | 18 | Per-operation hourly breakdown (7 days) |

#### Fact Tables — Item History *(new in v54)*

Per-item CU/duration/throttling over a configurable date range.

| Table | Columns | Description |
|---|---|---|
| **Item History Main** | 8 | Dimension linking item/operation/workspace with unique key |
| **Item History Operation** | 6 | Aggregated CU/duration/throttling per item per day |
| **Item History Operation Detail** | 11 | Per-operation detail with status and time windows |
| **Item History Summary** | 15 | CU breakdown (interactive/background/preview) with 15-min peaks |

#### Fact Tables — Surge Protection *(new in v54)*

Workspace-level surge blocking events.

| Table | Columns | Description |
|---|---|---|
| **Surge Protection By Day** | 2 | Daily count of blocked workspaces per capacity |
| **Surge Protection By Hour** | 2 | Hourly count of blocked workspaces per capacity |
| **Surge Protection Blocked Workspaces Detail** | 12 | Blocked workspace detail: duration, affected users, rejection counts, how blocked |

#### Fact Tables — Workload Autoscale *(new in v54)*

Per-workload autoscale limit tracking.

| Table | Columns | Description |
|---|---|---|
| **CU Detail For Workload Autoscale** | 8 | CU consumption vs autoscale limit per workload |
| **Timepoint CU Detail For Workload Autoscale** | 8 | Timepoint-level CU vs autoscale limit |
| **Timepoint2 CU Detail For Workload Autoscale** | 8 | Timepoint2-level CU vs autoscale limit |
| **Timepoint Detail For Workload Autoscale** | 15 | Per-operation detail with autoscale context |
| **Timepoint2 Detail For Workload Autoscale** | 15 | Per-operation detail at Timepoint2 with autoscale context |
| **Metrics By Item For Workload Autoscale** | 17 | Item metrics with autoscale grouping |
| **Metrics By Item And Operation For Workload Autoscale** | 18 | Item + operation metrics with autoscale |
| **Metrics By Item And Day For Workload Autoscale** | 17 | Daily item metrics with autoscale |
| **Metrics By Item And Hour For Workload Autoscale** | 17 | Hourly item metrics with autoscale |
| **Metrics By Item And Operation And Hour For Workload Autoscale** | 19 | Hourly item + operation metrics with autoscale |
| **Metrics By Item And Operation And Day For Workload Autoscale** | 18 | Daily item + operation metrics with autoscale |

#### System

| Table | Columns | Measures | Description |
|---|---|---|---|
| **System Events** | 6 | — | Capacity state changes (pause, resume, throttle) |
| **All Measures** | 0 | 294 | Home table for all 294 DAX measures |

#### Timepoint Filter/Slicer Tables *(new in v54)*

| Table | Columns | Description |
|---|---|---|
| **Timepoint Workspace List** | 2 | Workspace filter for timepoint detail |
| **Timepoint Item List** | 2 | Item filter for timepoint detail |
| **Timepoint Operation Name List** | 1 | Operation name filter |
| **Timepoint Operation Id List** | 1 | Operation ID filter |
| **Timepoint User List** | 1 | User filter |
| **Timepoint Status List** | 1 | Status filter |
| **Item History Workspace List** | 2 | Workspace filter for Item History |
| **Item History Operation Name List** | 1 | Operation filter for Item History |
| **Item History User List** | 1 | User filter for Item History |
| **Item History Experience List** | 1 | Experience/workload filter for Item History |

#### Hidden Tables (internal use)

| Table | Description |
|---|---|
| Metrics By Item And Day | Item metrics by day |
| Metrics By Item And Hour | Item metrics by hour |
| Metrics By Item Operation And Hour | Item + operation metrics by hour |
| Performance Delta Snapshot | Performance delta comparison |
| Top N Selector | Top-N filter control |
| CU Threshold | CU threshold configuration |
| Filter Records | Pause event filter |
| Start / End | Date range bucket boundaries |
| Various "optional columns" tables | Column selector logic for dynamic report pages |

### Table Schema Details

#### Capacities

Your Fabric capacities and their properties.

| Column | Type | Description |
|---|---|---|
| `Capacity Id` | Text | Unique identifier for the capacity |
| `Capacity name` | Text | Display name (e.g., "prodcapacity-eastus") |
| `SKU` | Text | SKU tier (F2, F4, F8, ... F2048) |
| `Region` | Text | Azure region (e.g., "West US 3", "East US") |
| `Region without default` | Text | Region name excluding "default" label |
| `State` | Text | Capacity state |
| `Source` | Text | Source type |
| `Owners` | Text | Capacity admin(s) |
| `Uppercase capacity Id` | Text | Capacity ID in uppercase |

**Use for**: Filtering reports by capacity, showing SKU distribution, capacity inventory.

---

#### Items

All Fabric items (lakehouses, warehouses, reports, pipelines, etc.) across all capacities.

| Column | Type | Description |
|---|---|---|
| `Capacity Id` | Text | Capacity the item belongs to |
| `Item Id` | Text | Unique item identifier |
| `Item kind` | Text | Item type — Lakehouse, Warehouse, Report, Notebook, SemanticModel, EventStream, Pipeline, etc. |
| `Item name` | Text | Display name of the item |
| `Workspace Id` | Text | Workspace the item belongs to |
| `Workspace name` | Text | Workspace display name |
| `Billable type` | Text | "Billable", "Nonbillable", or "Both" |
| `Timestamp` | DateTime | When this record was captured |
| `Users` | Int64 | User count |
| `Virtualised item` | Text | Virtualization status of the item |
| `Virtualised workspace` | Text | Virtualization status of the workspace |
| `Is virtual  item status` | Text | Whether the item is virtual |
| `Is virtual workspace status` | Text | Whether the workspace is virtual |
| `Unique key` | Text | Composite key (Capacity Id + Workspace Id) |
| `Item key` | Text | Composite key (Capacity Id + Item Id) |

**Use for**: Item inventory, filtering CU consumption by item/workspace, item type distribution.

---

#### Timepoints

30-second interval timestamps covering the last 14 days.

| Column | Type | Description |
|---|---|---|
| `TimePoint` | DateTime | The exact 30-second interval timestamp |
| `Date` | DateTime | Date portion only |
| `Start of Hour` | DateTime | Hour bucket for aggregation |
| `15 Minute Bucket` | DateTime | 15-minute bucket for aggregation |
| `Next` | Text | Navigation label |
| `Previous` | Text | Navigation label |

**Use for**: Time-axis for utilization visuals, filtering by date range, hourly/daily aggregation.

---

#### Workspaces

All workspaces assigned to capacities.

| Column | Type | Description |
|---|---|---|
| `Workspace Id` | Text | Unique workspace identifier |
| `Workspace name` | Text | Workspace display name |
| `Capacity Id` | Text | The capacity this workspace is assigned to |
| `Workspace provision state` | Text | "Active" or other states |
| `Workspace key` | Text | Composite key (Capacity Id + Workspace Id) |

**Use for**: Workspace-to-capacity mapping, filtering by workspace.

---

#### System Events

Capacity state change events (pause, resume, throttle, etc.).

| Column | Type | Description |
|---|---|---|
| `Capacity Id` | Text | Capacity identifier |
| `Capacity state` | Text | "Active", "Suspended", "Overloaded", "Deleted" |
| `Capacity state change reason` | Text | "ManuallyPaused", "ManuallyResumed", "InteractiveDelay", "AllRejected", etc. |
| `Capacity activation Id` | Text | Session identifier for the capacity activation period |
| `Capacity state transition time` | DateTime | Exact time of the state change |
| `Binned capacity state transition time` | DateTime | Rounded to nearest 30-second interval |

**State change reasons explained:**

| State | Reason | Meaning |
|---|---|---|
| Active | ManuallyResumed | Admin resumed a paused capacity |
| Active | NotOverloaded | Capacity recovered from throttling |
| Suspended | ManuallyPaused | Admin paused the capacity |
| Overloaded | InteractiveDelay | Interactive operations are being delayed (10-min smoothing > threshold) |
| Overloaded | InteractiveRejected | Interactive operations are being rejected (60-min smoothing > threshold) |
| Overloaded | AllRejected | Background + interactive operations rejected (24-hr smoothing > threshold) |
| Overloaded | SurgeProtectionActive | Surge protection threshold exceeded |
| Deleted | Deleted | Capacity was deleted |

**Use for**: Throttling timeline, pause/resume audit trail, capacity health history.

---

#### Dates

Calendar dimension table.

| Column | Type | Description |
|---|---|---|
| `Date` | DateTime | Calendar date |
| `Start of Month` | Text | First day of the month |
| `First Day of Week` | DateTime | Monday of that week |
| `Day` | DateTime | Same as Date |

**Use for**: Time intelligence, month-over-month comparisons, week filters.

---

#### Metrics

Placeholder table for measures. Used internally by the semantic model.

| Column | Type | Description |
|---|---|---|
| `Metric` | Text | Metric label/name |
| `SortID` | Number | Sort order |

---

#### Workloads

Workload types in the model.

| Column | Type | Description |
|---|---|---|
| `WorkloadKind` | Text | Workload type (e.g., Power BI, Warehouse, Spark, etc.) |

**Use for**: Filtering by workload type.

---

#### CUDetail

The core CU consumption fact table with throttling metrics per timepoint (25 columns).

| Column | Type | Description |
|---|---|---|
| `WindowStartTime` | DateTime | Start of the 30-second timepoint window |
| `WindowEndTime` | DateTime | End of the 30-second timepoint window |
| `Interactive` | Double | Interactive CU consumption (CU-seconds) |
| `Background` | Double | Background CU consumption (CU-seconds) |
| `InteractivePreview` | Double | Non-billable interactive CU |
| `BackgroundPreview` | Double | Non-billable background CU |
| `CUs` | Double | Total CU consumption |
| `Interactive Delay %` | Double | Interactive delay throttling percentage |
| `Interactive Rejection %` | Double | Interactive rejection throttling percentage |
| `Background Rejection %` | Double | Background rejection throttling percentage |
| `AutoScaleCapacityUnits` | Int64 | CU from autoscale |
| `BaseCapacityUnits` | Int64 | Base CU of the SKU |
| `StartOfHour` | DateTime | Hour bucket |
| `Start of Hour` | DateTime | Hour bucket (display) |
| `Threshold` | Double | Throttling threshold |
| `CU Limit` | Double | CU limit line value |
| `SKU` | Text | SKU name |
| `StartOf6min` | DateTime | 6-minute bucket |
| `Peak6minInteractive` | Double | Peak interactive CU in 6-min window |
| `Peak6minBackground` | Double | Peak background CU in 6-min window |
| `Peak6minInteractivePreview` | Double | Peak non-billable interactive in 6-min |
| `Peak6minBackgroundPreview` | Double | Peak non-billable background in 6-min |
| `Peak6min Interactive Delay %` | Double | Peak interactive delay % in 6-min |
| `Peak6min Interactive Rejection %` | Double | Peak interactive rejection % in 6-min |
| `Peak6min Background Rejection %` | Double | Peak background rejection % in 6-min |

**Use for**: Utilization analysis over time, throttling tracking, autoscale monitoring.

---

#### TimePointCUDetail

Detailed CU breakdown per 30-second timepoint — the data behind the utilization chart (21 columns).

| Column | Type | Description |
|---|---|---|
| `WindowStartTime` | DateTime | Start of the 30-second window |
| `WindowEndTime` | DateTime | End of the 30-second window |
| `Interactive` | Double | Interactive CU-seconds |
| `Background` | Double | Background CU-seconds |
| `InteractivePreview` | Double | Non-billable interactive CU |
| `BackgroundPreview` | Double | Non-billable background CU |
| `CUs` | Double | Total CU consumption |
| `StartOfHour` | DateTime | Hour bucket |
| `AutoScaleCapacityUnits` | Int64 | Autoscale CU |
| `CU Limit` | Double | CU limit line value |
| `Interactive Delay %` | Double | Interactive delay throttling % |
| `Interactive Rejection %` | Double | Interactive rejection throttling % |
| `Background Rejection %` | Double | Background rejection throttling % |
| `BaseCapacityUnits` | Int64 | Base CU of the SKU |
| `PeakHourInteractive` | Double | Peak interactive CU in the hour |
| `PeakHourBackground` | Double | Peak background CU in the hour |
| `PeakHourInteractivePreview` | Double | Peak non-billable interactive in the hour |
| `PeakHourBackgroundPreview` | Double | Peak non-billable background in the hour |
| `PeakHour Interactive Delay %` | Double | Peak interactive delay % in the hour |
| `PeakHour Interactive Rejection %` | Double | Peak interactive rejection % in the hour |
| `PeakHour Background Rejection %` | Double | Peak background rejection % in the hour |

**Use for**: Building custom utilization charts, calculating utilization percentages.

---

#### TimePointInteractiveDetail / TimePointBackgroundDetail

Per-operation detail for interactive or background operations at 30-second granularity (22 columns each).

| Column | Type | Description |
|---|---|---|
| `OperationStartTime` | DateTime | When the operation started |
| `OperationEndTime` | DateTime | When the operation ended |
| `Status` | Text | Operation status |
| `Item` | Text | Item name that performed the operation |
| `Operation` | Text | Operation type (e.g., Interactive query, Semantic model refresh) |
| `OperationId` | Text | Unique operation identifier |
| `User` | Text | User who triggered the operation |
| `Start` | DateTime | Start timestamp |
| `End` | DateTime | End timestamp |
| `Duration (s)` | Int64 | Duration in seconds |
| `Throttling (s)` | Int64 | Time spent throttled (seconds) |
| `% of Capacity` | Double | Operation's share of total capacity |
| `Total CU (s)` | Double | Total CU-seconds consumed by the operation |
| `Timepoint CU (s)` | Double | CU-seconds attributed to this timepoint |
| `Capacity CU (s)` | Int64 | Capacity CU-seconds |
| `Base Capacity CU (s)` | Int64 | Base capacity CU-seconds |
| `% of Base Capacity` | Double | Operation's share of base capacity |
| `Billing type` | Text | Billable or Nonbillable |
| `CapacityActivationId` | Text | Capacity activation session |
| `WorkspaceId` | Text | Workspace identifier |
| `PremiumCapacityId` | Text | Capacity identifier |
| `UniqueKey` | Text | Composite key (hidden) |

**Use for**: Identifying which specific operations consumed the most CU at a given timepoint.

---

#### MetricsByItem

Aggregated metrics per item over the 14-day window (22 columns).

| Column | Type | Description |
|---|---|---|
| `ItemId` | Text | Item identifier |
| `ArtifactKind` | Text | Item type |
| `sum_CU` | Double | Total CU-seconds consumed |
| `sum_duration` | Double | Total duration in seconds |
| `count_users` | Int64 | Unique user count |
| `count_operations` | Int64 | Total operation count |
| `percentile_DurationMs_50` | Int64 | Median operation duration (ms) |
| `percentile_DurationMs_90` | Int64 | P90 operation duration (ms) |
| `avg_DurationMs` | Int64 | Average operation duration (ms) |
| `PremiumCapacityId` | Text | Capacity identifier |
| `Billing type` | Text | Billable or Nonbillable |
| `Throttling (min)` | Double | Minutes affected by throttling |
| `count_rejected_operations` | Int64 | Rejected operation count |
| `count_successful_operations` | Int64 | Successful operation count |
| `count_failure_operations` | Int64 | Failed operation count |
| `count_InProgress_operations` | Int64 | In-progress operation count |
| `count_cancelled_operations` | Int64 | Cancelled operation count |
| `count_Invalid_operations` | Int64 | Invalid operation count |
| `emptyOperationIdCount` | Int64 | Operations without an ID |
| `validOperationIdCount` | Int64 | Operations with a valid ID |
| `WorkspaceId` | Text | Workspace identifier |
| `UniqueKey` | Text | Composite key (hidden) |

**Use for**: Top CU consumers, item-level cost analysis, operation success/failure tracking.

---

#### MetricsByItemandOperation

Same as MetricsByItem but with an additional `OperationName` column for per-operation breakdown (23 columns).

| Column | Type | Description |
|---|---|---|
| `OperationName` | Text | Operation type (e.g., Interactive query, Semantic model refresh) |
| *(plus all 22 columns from MetricsByItem)* | | |

**Use for**: Understanding what types of operations (queries vs. refreshes) drive CU consumption per item.

---

#### StorageByWorkspacesandDay

Daily storage consumption per workspace (11 columns).

| Column | Type | Description |
|---|---|---|
| `WorkspaceId` | Text | Workspace identifier |
| `PremiumCapacityId` | Text | Capacity identifier |
| `Date` | DateTime | Date |
| `Utilization (GB)` | Double | Current utilization (GB) |
| `StaticStorageInGb` | Double | Billed storage (GB) |
| `Hours` | Int64 | Hours of storage usage |
| `OperationName` | Text | Storage operation type |
| `WorkloadKind` | Text | Workload type |
| `Billing type` | Text | Billable or Nonbillable |
| `WorkspaceKey` | Text | Composite workspace key |
| `WorkloadOperationKey` | Text | Composite workload + operation key |

**Use for**: Storage trending, workspace storage chargeback, identifying storage growth.

---

#### TimePointOverageDetail

Overage and carryforward data per timepoint (11 columns).

| Column | Type | Description |
|---|---|---|
| `WindowStartTime` | DateTime | Start of the 30-second window |
| `CumulativeCarryForward` | Double | Cumulative carryforward total |
| `CarryForwardAdd` | Double | Carryforward added this period |
| `CarryForwardBurndown` | Double | Carryforward burned down this period |
| `BaseCapacityUnits` | Int64 | Base CU of the SKU |
| `AutoScaleCapacityUnits` | Int64 | Autoscale CU |
| `StartOfHour` | DateTime | Hour bucket |
| `StartOf20min` | DateTime | 20-minute bucket |
| `Peak20minCumulativeCarryForward` | Double | Peak cumulative carryforward in 20-min window |
| `Peak20minCarryForwardAdd` | Double | Peak carryforward add in 20-min window |
| `Peak20minCarryForwardBurndown` | Double | Peak carryforward burndown in 20-min window |

**Use for**: Understanding overage patterns and how long throttling lasts.

---

#### Items Operations *(new in v54)*

Operation-level metadata per item with user counts and release type information.

| Column | Type | Description |
|---|---|---|
| `Item Id` | Text | Item identifier |
| `Workspace Id` | Text | Workspace identifier |
| `Capacity Id` | Text | Capacity identifier |
| `Operation name` | Text | Operation type |
| `Timestamp` | DateTime | When this record was captured |
| `Item name` | Text | Item display name |
| `Virtualised item` | Text | Virtualization status |
| `Virtualised workspace` | Text | Workspace virtualization status |
| `Workspace name` | Text | Workspace display name |
| `Item kind` | Text | Item type |
| `Users` | Int64 | User count |
| `TIMESTAMP 2` | DateTime | Secondary timestamp |
| `Release type` | Text | Release type (GA, Preview, etc.) |
| `Distinct count release type` | Int64 | Number of release types |
| `Operation unique key` | Text | Composite key (hidden) |
| `Billing type` | Text | Billable or Nonbillable |
| `Operation name V2` | Text | Updated operation name |

**Use for**: Understanding which operations exist per item, identifying preview vs GA operations.

---

#### Usage Summary (Last 1 hour / 24 hours) *(new in v54)*

Pre-aggregated capacity health snapshot with risk indicators and percentile metrics.

| Column | Type | Description |
|---|---|---|
| `Timestamp` | DateTime | Timestamp for the data point |
| `Capacity Id` | Text | Capacity identifier |
| `CU (s)` | Double | CU consumption in seconds |
| `Average CU %` | Double | Average CU utilization percentage |
| `Maximum CU %` | Double | Peak CU utilization percentage |
| `Interactive rejection (s)` | Int64 | Interactive rejection duration in seconds |
| `Background rejection (s)` | Int64 | Background rejection duration in seconds |
| `Interactive delay (s)` | Int64 | Interactive delay duration in seconds |
| `Background rejection risk` | Int64 | Background rejection risk indicator *(1hr/24hr only)* |
| `Interactive rejection risk` | Int64 | Interactive rejection risk indicator *(1hr/24hr only)* |
| `Interactive delay risk` | Int64 | Interactive delay risk indicator *(1hr/24hr only)* |
| `Cumulative debt` | Double | Cumulative CU debt *(1hr/24hr only)* |
| `P95 interactive delay` | Double | 95th percentile interactive delay *(1hr/24hr only)* |
| `P95 interactive rejection` | Double | 95th percentile interactive rejection *(1hr/24hr only)* |
| `P95 background rejection` | Double | 95th percentile background rejection *(1hr/24hr only)* |
| `Usage variance` | Double | Variance in usage *(1hr/24hr only)* |
| `Average utilization` | Double | Average utilization |

> The 7-day and longer variants have a subset of these columns (9 columns — no risk/P95/variance fields).

**Use for**: Quick capacity health assessment, trend analysis over multiple time windows.

---

#### Usage Operation (Last 1 hour / 24 hours / 7 days) *(new in v54)*

Per-operation breakdown of CU consumption, throttling, and operation status counts.

| Column | Type | Description |
|---|---|---|
| `Capacity Id` | Text | Capacity identifier |
| `Utilization type` | Text | Type of utilization (Interactive, Background) |
| `Seconds` / `Hours` | DateTime | Time bucket (seconds for 1hr, hours for 24hr/7d) |
| `CU (s)` | Double | CU consumed in seconds |
| `Duration (s)` | Int64 | Duration in seconds |
| `Throttling (s)` | Double | Throttling duration in seconds |
| `Users` | Int64 | User count |
| `TIMESTAMP` | DateTime | Data timestamp |
| `Region` | Text | Azure region *(1hr/24hr only)* |
| `SKU` | Text | SKU tier *(1hr only)* |
| `Failure operations` | Int64 | Failed operation count |
| `Rejected operations` | Int64 | Total rejected operations |
| `Interactive rejected operations` | Int64 | Interactive rejected count |
| `Background rejected operations` | Int64 | Background rejected count |
| `Successful operations` | Int64 | Successful operation count |
| `Inprogress operations` | Int64 | In-progress count |
| `Cancelled operations` | Int64 | Cancelled count |
| `Invalid operations` | Int64 | Invalid count |
| `Stopped operations` | Int64 | Stopped count |

**Use for**: Identifying which operation types cause throttling, comparing interactive vs background load.

---

#### Item History Main *(new in v54)*

Dimension table linking items to their operations for the Item History page.

| Column | Type | Description |
|---|---|---|
| `WorkspaceName` | Text | Workspace name |
| `ArtifactName` | Text | Item name |
| `OperationName` | Text | Operation type |
| `UtilizationType` | Text | Interactive or Background |
| `ArtifactKind` | Text | Item type |
| `Billing type` | Text | Billable or Nonbillable |
| `Experience` | Text | Workload code (PBI, DW, DE, etc.) |
| `ItemHistoryUniquKey` | Text | Unique key for joining (hidden) |

---

#### Item History Operation *(new in v54)*

Aggregated CU/duration/throttling per item per day.

| Column | Type | Description |
|---|---|---|
| `Day` | DateTime | Date |
| `Operations` | Int64 | Operation count |
| `CU (s)` | Double | CU consumed in seconds |
| `Duration (s)` | Double | Duration in seconds |
| `Throttling (s)` | Int64 | Throttling in seconds |
| `ItemHistoryUniquKey` | Text | Unique key for joining (hidden) |

**Use for**: Trending CU consumption and throttling per item over time.

---

#### Item History Operation Detail *(new in v54)*

Per-operation detail within Item History with time windows and status.

| Column | Type | Description |
|---|---|---|
| `Day` | DateTime | Date |
| `CU (s)` | Double | CU consumed |
| `Duration (s)` | Int64 | Duration in seconds |
| `Throttling (s)` | Int64 | Throttling in seconds |
| `WindowStartTime` | DateTime | Start of the compute window |
| `WindowEndTime` | DateTime | End of the compute window |
| `OperationStartTime` | DateTime | When the operation started |
| `OperationEndTime` | DateTime | When the operation ended |
| `Status` | Text | Operation status |
| `ItemHistoryUniquKey` | Text | Unique key for joining (hidden) |
| `Operations` | Int64 | Operation count |

---

#### Item History Summary *(new in v54)*

CU breakdown (interactive/background/preview) with 15-minute peak metrics.

| Column | Type | Description |
|---|---|---|
| `WindowStartTime` | DateTime | Start time |
| `WindowEndTime` | DateTime | End time |
| `StartOf15min` | DateTime | 15-minute bucket |
| `Interactive` | Double | Interactive CU |
| `Background` | Double | Background CU |
| `InteractivePreview` | Double | Non-billable interactive CU |
| `BackgroundPreview` | Double | Non-billable background CU |
| `AutoScaleCapacityUnits` | Int64 | Autoscale CU |
| `StartOfHour` | DateTime | Hour bucket |
| `Peak15minInteractive` | Double | Peak interactive CU in 15-min window |
| `Peak15minBackground` | Double | Peak background CU in 15-min window |
| `Peak15minInteractivePreview` | Double | Peak non-billable interactive in 15-min |
| `Peak15minBackgroundPreview` | Double | Peak non-billable background in 15-min |
| `CpuTimeMs` | Double | CPU time in milliseconds |
| `BaseCapacityUnits` | Int64 | Base CU of the SKU |

---

#### Surge Protection Blocked Workspaces Detail *(new in v54)*

Detailed information about workspaces blocked by surge protection.

| Column | Type | Description |
|---|---|---|
| `Workspace Id` | Text | Blocked workspace identifier |
| `Workspace name` | Text | Blocked workspace name |
| `Blocked date` | DateTime | When the block started |
| `Blocked end` | DateTime | When the block ended |
| `Blocked duration (hours)` | Int64 | Duration of the block in hours |
| `How blocked` | Text | Specific blocking mechanism |
| `How Blocked Category` | Text | Category of blocking |
| `Affected users` | Int64 | Number of users affected |
| `Timepoint start` | DateTime | Timepoint when surge started |
| `Capacity Id` | Text | Capacity identifier |
| `Interactive rejected operations` | Int64 | Interactive operations rejected during block |
| `Background rejected operations` | Int64 | Background operations rejected during block |

**Use for**: Identifying which workspaces were blocked by surge protection, understanding impact and duration.

---

#### CU Detail For Workload Autoscale *(new in v54)*

CU consumption vs workload-level autoscale limits.

| Column | Type | Description |
|---|---|---|
| `Window start time` | DateTime | Start time |
| `Capacity Id` | Text | Capacity identifier |
| `CU (s)` | Double | CU consumed |
| `Peak 6min CU` | Double | Peak CU in 6-minute window |
| `Utilization type` | Text | Interactive or Background |
| `Billing type` | Text | Billable or Nonbillable |
| `Workload autoscale capacity units limit` | Int64 | Autoscale limit for this workload |
| `ConsumptionStartTime` | DateTime | When consumption started |

**Use for**: Monitoring per-workload CU consumption against autoscale thresholds.

---

The semantic model uses a star-schema pattern with **Items** as the central hub. Most fact tables join to Items via `UniqueKey`.

#### Item & Capacity Relationships

| From Table (Column) | To Table (Column) | Notes |
|---|---|---|
| Items (capacityId) | Capacities (capacityId) | Links items to their capacity |
| Workspaces (PremiumCapacityId) | Capacities (capacityId) | Links workspaces to capacity |
| MetricsByItem (UniqueKey) | Items (UniqueKey) | 14-day aggregate metrics per item |
| MetricsByItemandDay (UniqueKey) | Items (UniqueKey) | Daily metrics pedetails/6741112c-52c2-42e4-8e6f-5e5159d28111/dataset/1df83a07-9420-4ac3-9e7c-90853fb6d238/r item |
| MetricsByItemandHour (UniqueKey) | Items (UniqueKey) | Hourly metrics per item |
| MetricsByItemandOperation (UniqueKey) | Items (UniqueKey) | Metrics per item + operation |
| MetricsByItemandOperationandDay (UniqueKey) | Items (UniqueKey) | Daily metrics per item + operation |
| MetricsByItemandOperationandHour (UniqueKey) | Items (UniqueKey) | Hourly metrics per item + operation |
| Performance2daySnapshot (UniqueKey) | Items (UniqueKey) | 2-day performance delta |
| TimePointInteractiveDetail (UniqueKey) | Items (UniqueKey) | Interactive ops at selected timepoint |
| TimePointBackgroundDetail (UniqueKey) | Items (UniqueKey) | Background ops at selected timepoint |
| TimePoint2InteractiveDetail (UniqueKey) | Items (UniqueKey) | Interactive ops at 2nd timepoint |
| TimePoint2BackgroundDetail (UniqueKey) | Items (UniqueKey) | Background ops at 2nd timepoint |
| MaxMemoryByItem (ItemKey) | Items (ItemKey) | Many-to-many, memory per item |
| MaxMemoryByItemAndHour (ItemKey) | Items (ItemKey) | Many-to-many, hourly memory |
| ItemKind (ItemKind) | Items (ItemKind) | Many-to-many, bidirectional cross-filter |

#### Time Slicer Relationships

| From Table (Column) | To Table (Column) | Notes |
|---|---|---|
| CUDetail (WindowStartTime) | TimePoints (TimePoint) | Main timepoint chart |
| CUDetail (WindowStartTime) | TimePoints2 (TimePoint) | Second timepoint chart |
| TimePointOverageDetail (WindowStartTime) | TimePoints (TimePoint) | Overage at selected timepoint |
| TimePointOveragesByWorkloads (WindowStartTime) | TimePoints2 (TimePoint) | Overage by workload (TP2) |
| TimePoint2OveragesByWorkloads (WindowStartTime) | TimePoints (TimePoint) | Overage by workload (TP1) |
| TimePoint2CUDetail (WindowStartTime) | TimePoints (TimePoint) | CU detail at 2nd timepoint |
| TimePointCUDetail (WindowStartTime) | TimePoints2 (TimePoint) | CU detail at 1st timepoint |
| SystemEvents (BinnedCapacityStateTransitionTime) | TimePoints (TimePoint) | Pause/resume events |
| SystemEvents (BinnedCapacityStateTransitionTime) | TimePoints2 (TimePoint) | Pause/resume events (TP2) |
| TimePoints (Start of Hour) | DateTime (Hour Start) | Hour-level filtering |
| MaxMemoryByItemAndHour (Timestamp) | DateTime (Hour Start) | Memory hour alignment |

#### Date & Time Relationships

| From Table (Column) | To Table (Column) | Notes |
|---|---|---|
| DateTime (Date) | Dates (Date) | Links hour table to date dimension |
| MetricsByItemandDay (Date) | Dates (Date) | Daily metric filtering |
| MetricsByItemandOperationandDay (Date) | Dates (Date) | Daily operation metric filtering |
| MetricsByItemandHour (DateTime) | DateTime (Hour Start) | Hourly metric filtering |
| MetricsByItemandOperationandHour (DateTime) | DateTime (Hour Start) | Hourly operation metric filtering |

#### Operation Name Relationships

| From Table (Column) | To Table (Column) | Notes |
|---|---|---|
| MetricsByItemandOperation (OperationName) | OperationNames (OperationName) | Operation slicer |
| MetricsByItemandOperationandDay (OperationName) | OperationNames (OperationName) | Daily operation slicer |
| MetricsByItemandOperationandHour (OperationName) | OperationNames (OperationName) | Hourly operation slicer |

#### Storage Relationships

| From Table (Column) | To Table (Column) | Notes |
|---|---|---|
| StorageByWorkspaces (WorkspaceKey) | Workspaces (WorkspaceKey) | Current storage per workspace |
| StorageByWorkspacesandDay (WorkspaceKey) | Workspaces (WorkspaceKey) | Daily storage per workspace |
| StorageByWorkspacesandHour (WorkspaceKey) | Workspaces (WorkspaceKey) | Hourly storage per workspace |
| StorageByWorkspacesandDay (WorkloadKind) | Workloads (WorkloadKind) | Filter by workload type |
| StorageByWorkspacesandHour (WorkloadKind) | Workloads (WorkloadKind) | Filter by workload type |
| StorageByWorkspacesandDay (OperationName) | OperationForStorage (OperationName) | Storage operation type |
| StorageByWorkspacesandHour (OperationName) | OperationForStorage (OperationName) | Storage operation type |
| StorageByWorkspacesandDay (Billing type) | Billing type (Billing type) | Billable vs non-billable |
| StorageByWorkspacesandHour (Billing type) | Billing type (Billing type) | Billable vs non-billable |
| StorageByWorkspacesandDay (Date) | Dates (Date) | Daily storage date filter |
| StorageByWorkspacesandHour (DateTime) | DateTime (Hour Start) | Hourly storage time filter |

#### UI Helper Relationships

| From Table (Column) | To Table (Column) | Notes |
|---|---|---|
| Dynamic Columns (Dynamic Columns) | ItemKind (Measure) | Many-to-many, powers column picker slicer |

> **Key pattern**: The model uses dual timepoints (TimePoints and TimePoints2) to enable side-by-side comparison of two different 30-second windows in the app's UI. Both CUDetail and SystemEvents have relationships to both timepoint tables.

---

### Key Measures

The semantic model exposes **294 measures** that calculate utilization, throttling, and health metrics. These measures require **filter context** (they work inside report visuals, not in standalone DAX queries).

**Core measures:**

| Measure | What it calculates |
|---|---|
| `CU (s)` | Capacity Units consumed in seconds |
| `Duration (s)` | Processing time in seconds |
| `Interactive %` | Interactive CU utilization as % of capacity |
| `Background %` | Background CU utilization as % of capacity |
| `CU %` | Total CU utilization as % of capacity |

**New in v54:**

| Measure | What it calculates |
|---|---|
| `Autoscale CU usage` / `Autoscale CU usage %` | CU consumption under autoscale |
| `Cumulative CU usage (s)` / `Cumulative CU usage % preview` | Cumulative CU tracking |
| `Blocked workspaces (Day)` / `(hour)` / `(details)` | Surge protection block counts |
| `xInteractive item history` / `xBackground item history` | Item History CU by type |
| `Item history operation detail count` | Item History row counts |
| `Usage variance (last 24 hours)` | 24-hour usage variance |
| `Is item kind has autoscale` | Whether item type supports autoscale |

> **Important**: The `%` measures only resolve inside Power BI report visuals with proper filter context (capacity + timepoint). They will error if you try to evaluate them in standalone DAX queries via the API. The `CU (s)` and `Duration (s)` measures work when added to the Items table context.

> **Note**: The semantic model cannot be opened or edited directly. DAX queries cannot be run against it via DAX Studio or the executeQueries API. The schema and measures documented here are for understanding the model structure when building custom reports connected to it.

## Custom Report Ideas

Here are some reports you can build that the built-in app doesn't provide:

| Report | What it shows | Value |
|---|---|---|
| **Capacity Inventory Dashboard** | All capacities with SKU, region, state, workspace count | Quick overview for management |
| **Item Census** | All items grouped by type, workspace, billable status | Find what's deployed where |
| **Throttling Timeline** | SystemEvents filtered to Overloaded states, plotted over time | See when and why throttling happened |
| **Pause/Resume Audit** | When capacities were paused and resumed, by whom | Track operational patterns |
| **Workspace Density** | Items per workspace, workspaces per capacity | Identify overcrowded workspaces |
| **Billable vs Non-Billable** | Items split by billing type across workspaces | Understand preview feature exposure |
| **Top CU Consumers** | Items ranked by CU (s) consumption | Find your most expensive items |
| **Surge Protection Dashboard** | Blocked workspaces with duration, affected users, rejection counts | Understand surge protection impact *(v54)* |
| **Item History Trends** | Per-item CU and throttling over time | Identify items with growing problems *(v54)* |
| **Capacity Health Scorecard** | Usage Summary with P95 metrics, risk indicators, cumulative debt | Executive health overview *(v54)* |
| **Workload Autoscale Monitor** | Per-workload CU vs autoscale limits | Track autoscale effectiveness *(v54)* |

## Limitations

- **Do not modify** the semantic model — Microsoft explicitly states this is unsupported and changes may break the app
- **Utilization percentages** (`Interactive %`, `Background %`, `CU %`) only work inside report visuals with proper filter context — they cannot be queried standalone via DAX API
- **14-day data retention** — the model only holds the last 14 days of data
- **DMV queries** (`INFO.TABLES()`, `INFO.COLUMNS()`) are not supported on this model
- **SPN auth** does not work for DAX queries — use interactive browser authentication
- **Schema may change** without notice when the app is updated

## Related Resources

- [What is the Capacity Metrics App?](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app)
- [Install the Capacity Metrics App](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-install)
- [Understand the Compute Page](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-compute-page)
- [Metrics App Calculations](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-calculations)
- [Fabric Operations Reference](https://learn.microsoft.com/en-us/fabric/enterprise/fabric-operations)

## Disclaimer

This guide is provided **as-is** with no warranty of any kind. The semantic model schema was discovered through testing and may change when Microsoft updates the app. Use at your own risk.

## License

This project is licensed under the [MIT License](../../LICENSE).
