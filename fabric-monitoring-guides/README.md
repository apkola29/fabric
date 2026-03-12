# Fabric Monitoring — Build Your Own Reports

Guides for building **custom Power BI reports** on top of Microsoft Fabric's built-in monitoring apps — without modifying the underlying semantic models.

## Available Guides

| Guide | App | What you get |
|---|---|---|
| [**Capacity Metrics App**](capacity-metrics-app/) | [Capacity Metrics App](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app) | 45 tables covering compute utilization, throttling, storage, overages, and item-level performance — at 30-second granularity |
| [**Chargeback App**](chargeback-app/) | [Chargeback App](https://learn.microsoft.com/en-us/fabric/enterprise/chargeback-app) | 7 tables covering per-user, per-item, per-operation CU consumption with domain-based cost allocation — at daily granularity |

## When to Use Which

| Need | Use |
|---|---|
| Capacity utilization % over time | Capacity Metrics App |
| Throttling and overage analysis | Capacity Metrics App |
| Storage consumption trends | Capacity Metrics App |
| Per-user CU consumption | Chargeback App |
| Department/domain cost allocation | Chargeback App |
| Operation-level breakdown with user attribution | Chargeback App |
| 30-second granularity time-series | Capacity Metrics App |
| Daily rollups for cost reporting | Chargeback App |
| Both utilization + cost allocation | Use both apps together |

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
