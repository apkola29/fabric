# Fabric Monitoring — Build Your Own Reports

Guides for building **custom Power BI reports and Fabric-native cost reporting** on top of Microsoft Fabric's built-in monitoring apps and Azure Cost Management — without modifying the underlying semantic models.

## Available Guides

| Guide | App / Source | What you get |
|---|---|---|
| [**Capacity Metrics App**](capacity-metrics-app/) | [Capacity Metrics App](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app) | 110 tables / 349 measures covering compute utilization, throttling, storage, processed-overage and overage-billing-limit metrics, per-capacity rollups (Last 1h / 24h / 7d), surge protection, item history, P95 latency, and item-level performance — at 30-second granularity |
| [**Chargeback App**](chargeback-app/) | [Chargeback App](https://learn.microsoft.com/en-us/fabric/enterprise/chargeback-app) | 14 tables / 31 measures covering per-user, per-item, per-operation CU consumption with domain-based cost allocation — at daily granularity |
| [**Azure Cost Export**](azure-cost-export/) | [Azure Cost Management Exports](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-improved-exports) | Daily amortized-cost Parquet drop into ADLS Gen2 → mounted as a OneLake shortcut so you can join real Azure dollars (capacity SKU + reservations + OneLake storage + Copilot) to CU consumption and chargeback **inside Fabric** — no Azure portal hopping |

## When to Use Which

| Need | Use |
|---|---|
| Capacity utilization % over time | Capacity Metrics App |
| Throttling and overage analysis | Capacity Metrics App |
| Processed overage / overage billing limit (CU·hours) | Capacity Metrics App |
| Storage consumption trends | Capacity Metrics App |
| Per-user CU consumption | Chargeback App |
| Department/domain cost allocation | Chargeback App |
| Operation-level breakdown with user attribution | Chargeback App |
| 30-second granularity time-series | Capacity Metrics App |
| Daily rollups for cost reporting | Chargeback App |
| Both utilization + cost allocation | Use both apps together |
| **Actual $ cost per workspace / item / domain** | **Azure Cost Export + Chargeback (CU-share allocation)** |
| **Reservation savings + Copilot charges visibility in Fabric** | **Azure Cost Export** |
| **ISV per-customer billback (1 capacity, many workspaces)** | **Azure Cost Export + Chargeback** |

## How Custom Reports Work

Both apps deploy a **semantic model** (dataset) into your tenant when installed. You can create your own Power BI reports connected to these semantic models:

1. Install the app from AppSource (capacity admin required)
2. Open **Power BI Desktop** → **Get Data** → **Power BI datasets**
3. Select the app's semantic model
4. Build your report using the tables and measures documented in each guide
5. Publish and share with your team

The built-in reports are read-only and admin-only. Your custom reports can be shared with anyone.

## Disclaimer

These guides are provided **as-is** with no warranty of any kind. The semantic model schemas were discovered through testing and may change when Microsoft updates the apps. Use at your own risk.

## License

This project is licensed under the [MIT License](../LICENSE).
