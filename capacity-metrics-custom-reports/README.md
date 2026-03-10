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

The semantic model contains **45 tables**:

#### Dimension Tables

| Table | Columns | Description |
|---|---|---|
| **Capacities** | 13 | All Fabric capacities — SKU, region, state, admins |
| **Items** | 15 | Every Fabric item (Lakehouse, Warehouse, Report, Notebook, etc.) |
| **ItemsThrottled** | 15 | Items that were affected by throttling events |
| **Workspaces** | 5 | All workspaces and which capacity they're assigned to |
| **Dates** | 4 | Calendar dimension for time intelligence |
| **DateTime** | 4 | Date/time dimension with hour-level granularity |
| **TimePoints** | 6 | 30-second interval timestamps (last 14 days) — primary time axis |
| **TimePoints2** | 3 | 6-minute interval timestamps — aggregated time axis |
| **Billing type** | 1 | Billable / Nonbillable filter dimension |
| **ItemKind** | 2 | Item type dimension (Lakehouse, Warehouse, Report, etc.) |
| **Workloads** | 1 | Workload type dimension (Power BI, Warehouse, Spark, etc.) |
| **WorkloadForStorage** | 2 | Workload types for storage-related views |
| **OperationForStorage** | 2 | Operation types for storage-related views |
| **OperationNames** | 1 | Operation name dimension |
| **Metrics** | 2 | Internal placeholder table for hosting DAX measures |
| **Dynamic Columns** | 3 | Column selector logic for dynamic report visuals |

#### Fact Tables — Compute (30-second granularity)

| Table | Columns | Description |
|---|---|---|
| **TimePointCUDetail** | 21 | CU utilization detail per 30-second timepoint |
| **TimePointInteractiveDetail** | 22 | Interactive operation detail per 30-second timepoint |
| **TimePointBackgroundDetail** | 22 | Background operation detail per 30-second timepoint |
| **TimePointOverageDetail** | 11 | Overage/carryforward detail per timepoint |
| **TimePointOveragesByWorkloads** | 9 | Overages broken down by workload type |

#### Fact Tables — Compute (6-minute granularity)

| Table | Columns | Description |
|---|---|---|
| **TimePoint2CUDetail** | 21 | CU utilization detail per 6-minute timepoint |
| **TimePoint2InteractiveDetail** | 22 | Interactive operation detail (6-min aggregation) |
| **TimePoint2BackgroundDetail** | 22 | Background operation detail (6-min aggregation) |
| **TimePoint2OveragesByWorkloads** | 9 | Overages by workload (6-min aggregation) |

#### Fact Tables — Item Metrics

| Table | Columns | Description |
|---|---|---|
| **CUDetail** | 25 | Detailed CU consumption with throttling percentages |
| **MetricsByItem** | 22 | Aggregated metrics (CU, duration, ops, users) per item |
| **MetricsByItemandOperation** | 23 | Metrics broken down by item + operation type |
| **MetricsByItemandOperationandDay** | 21 | Daily metrics by item + operation |
| **MaxMemoryByItem** | 5 | Peak memory consumption per item |
| **MaxMemoryByItemAndHour** | 6 | Peak memory per item per hour |

#### Fact Tables — Storage

| Table | Columns | Description |
|---|---|---|
| **StorageByWorkspaces** | 5 | Current storage consumption per workspace |
| **StorageByWorkspacesandDay** | 11 | Daily storage trends per workspace |
| **StorageByWorkspacesandHour** | 11 | Hourly storage per workspace |

#### System

| Table | Columns | Measures | Description |
|---|---|---|---|
| **SystemEvents** | 6 | 10 | Capacity state changes (pause, resume, throttle) |
| **All Measures** | 0 | 134 | Home table for all 134 DAX measures |

#### Hidden Tables (internal use)

| Table | Description |
|---|---|
| DynamicColumnsTimepoint2BackgroundOperations | Dynamic columns for background ops (6-min) |
| DynamicColumnsTimepoint2InteractiveOperations | Dynamic columns for interactive ops (6-min) |
| DynamicColumnsTimepointBackgroundOperations | Dynamic columns for background ops (30-sec) |
| DynamicColumnsTimepointInteractiveOperations | Dynamic columns for interactive ops (30-sec) |
| MetricsByItemandDay | Item metrics by day (hidden) |
| MetricsByItemandHour | Item metrics by hour (hidden) |
| MetricsByItemandOperationandHour | Item + operation metrics by hour (hidden) |
| Performance2daySnapshot | 2-day performance snapshot (hidden) |
| Top N Selector | Top-N filter control (hidden) |

### Table Schema Details

#### Capacities

Your Fabric capacities and their properties.

| Column | Type | Description |
|---|---|---|
| `capacityId` | Text | Unique identifier for the capacity |
| `Capacity Name` | Text | Display name (e.g., "prodcapacity-eastus") |
| `sku` | Text | SKU tier (F2, F4, F8, ... F2048, or P1-P5, A1-A6) |
| `capacityPlan` | Text | Capacity plan type |
| `region` | Text | Azure region (e.g., "West US 3", "East US") |
| `state` | Number | Capacity state code |
| `capacityNumberOfVCores` | Number | vCores allocated |
| `capacityMemoryInGB` | Number | Memory allocated (GB) |
| `creationDate` | DateTime | When the capacity was created |
| `Owners` | Text | Capacity admin(s) |
| `source` | Number | Source type |
| `mode` | Number | Capacity mode |
| `o365AddonId` | Text | Microsoft 365 add-on identifier |

**Use for**: Filtering reports by capacity, showing SKU distribution, capacity inventory.

---

#### Items

All Fabric items (lakehouses, warehouses, reports, pipelines, etc.) across all capacities.

| Column | Type | Description |
|---|---|---|
| `capacityId` | Text | Capacity the item belongs to |
| `ItemId` | Text | Unique item identifier |
| `ItemKind` | Text | Item type — Lakehouse, Warehouse, Report, Notebook, SemanticModel, EventStream, Pipeline, etc. |
| `ItemName` | Text | Display name of the item |
| `WorkspaceId` | Text | Workspace the item belongs to |
| `WorkspaceName` | Text | Workspace display name |
| `Billable type` | Text | "Billable", "Nonbillable", or "Both" |
| `Timestamp` | DateTime | When this record was captured |
| `IsVirtualArtifactName` | Boolean | Whether the item is a virtual artifact (e.g., Copilot) |
| `IsVirtualWorkspaceName` | Boolean | Whether the workspace is virtual |
| `IsVirtualArtifactStatus` | Number | Virtual artifact status code |
| `IsVirtualWorkspaceStatus` | Number | Virtual workspace status code |
| `UniqueKey` | Text | Composite key (capacityId + WorkspaceId) |
| `ItemKey` | Text | Composite key (capacityId + ItemId) |

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
| `WorkspaceId` | Text | Unique workspace identifier |
| `WorkspaceName` | Text | Workspace display name |
| `PremiumCapacityId` | Text | The capacity this workspace is assigned to |
| `WorkspaceProvisionState` | Text | "Active" or other states |
| `WorkspaceKey` | Text | Composite key (capacityId + WorkspaceId) |

**Use for**: Workspace-to-capacity mapping, filtering by workspace.

---

#### SystemEvents

Capacity state change events (pause, resume, throttle, etc.).

| Column | Type | Description |
|---|---|---|
| `PremiumCapacityId` | Text | Capacity identifier |
| `PremiumCapacityState` | Text | "Active", "Suspended", "Overloaded", "Deleted" |
| `PremiumCapacityStateChangeReason` | Text | "ManuallyPaused", "ManuallyResumed", "InteractiveDelay", "AllRejected", etc. |
| `CapacityActivationId` | Text | Session identifier for the capacity activation period |
| `CapacityStateTransitionTime` | DateTime | Exact time of the state change |
| `BinnedCapacityStateTransitionTime` | DateTime | Rounded to nearest 30-second interval |

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

### Key Measures

The semantic model exposes several measures that calculate utilization metrics. These measures require **filter context** (they work inside report visuals, not in standalone DAX queries).

| Measure | What it calculates | Notes |
|---|---|---|
| `CU (s)` | Capacity Units consumed in seconds | Works in ADDCOLUMNS on Items table |
| `Duration (s)` | Processing time in seconds | Works in ADDCOLUMNS on Items table |
| `Interactive %` | Interactive CU utilization as % of capacity | Requires Timepoint filter context |
| `Background %` | Background CU utilization as % of capacity | Requires Timepoint filter context |
| `CU %` | Total CU utilization as % of capacity | Requires Timepoint filter context |

> **Important**: The `%` measures only resolve inside Power BI report visuals with proper filter context (capacity + timepoint). They will error if you try to evaluate them in standalone DAX queries via the API. The `CU (s)` and `Duration (s)` measures work when added to the Items table context.

### Example DAX Queries

These work via the `executeQueries` API or in DAX Studio connected to the model:

**Top items by CU consumption:**
```dax
EVALUATE
TOPN(10,
    ADDCOLUMNS(
        Items,
        "CU", [CU (s)]
    ),
    [CU (s)], DESC
)
```

**Capacity inventory:**
```dax
EVALUATE Capacities
```

**Throttling event history:**
```dax
EVALUATE
FILTER(
    SystemEvents,
    SystemEvents[PremiumCapacityState] = "Overloaded"
)
```

**Items by workspace:**
```dax
EVALUATE
SUMMARIZECOLUMNS(
    Items[WorkspaceName],
    Items[ItemKind],
    "ItemCount", COUNTROWS(Items)
)
```

**All workspaces on a capacity:**
```dax
EVALUATE
FILTER(
    Workspaces,
    Workspaces[PremiumCapacityId] = "your-capacity-id-here"
)
```

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

This project is licensed under the [MIT License](../LICENSE).
