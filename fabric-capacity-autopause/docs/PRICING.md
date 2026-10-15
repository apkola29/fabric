# Pricing and savings: time-based Fabric capacity auto-pause

**Verified and queried: 2026-10-15.** All monetary examples are USD retail list prices, not a quote. Check current pricing for your region and agreement.

## 1. Principle: pay for the capacity time you keep Active

This project schedules an Azure Automation runbook to pause Azure **F-SKU** `Microsoft.Fabric/capacities` resources at a configured time. It is **purely time-based**: it pauses at the scheduled time regardless of workload. An Active capacity has a provisioned compute cost even when nobody submits work.

For **pay-as-you-go (PAYG)** capacity, a successful pause stops the ongoing capacity-unit compute meter until the capacity resumes. It does not erase consumption already incurred, stop every other meter, or reduce a reservation commitment.

| State or charge | Billing consequence |
| --- | --- |
| Active PAYG capacity | Provisioned CUs are billed for the time the capacity is Active. |
| Paused PAYG capacity | No ongoing provisioned-capacity compute charge for the paused interval, after accounting for usage settled at pause. |
| Remaining smoothed usage and cumulative overage | Reconciled and added to the Azure bill when the capacity is paused; this can produce a utilization spike. |
| OneLake and other billable storage | Continues independently of pausing compute. Mirrored storage can lose its free allocation while the capacity is paused. |
| Other resources and licenses | Automation, monitoring, external storage, networking where applicable, gateways, and per-user licenses have their own charging rules. |
| Resumed capacity | Compute billing resumes. |
| Reserved CUs | The purchased commitment remains; pausing does not stop reservation payments or preserve unused hourly benefits. |

**Billing granularity is not the rate unit.** The [Fabric licensing documentation](https://learn.microsoft.com/fabric/enterprise/licenses#capacity) explicitly says Azure bills F capacities **per second, with a one-minute minimum**. The Retail Prices API expresses the compute rate as `1 Hour`; the calculations below therefore use **USD per CU-hour**, prorated by elapsed Active time, not whole-hour rounding.

The project does **not** automatically resume capacities. The schedules below are cost-model examples, not a claim that the runbook implements resume scheduling or weekend calendars. They require appropriate pause configuration and an independent/manual resume process that actually delivers those Active hours.

## 2. Verified facts and sources

| Claim | Source URL | Date verified |
| --- | --- | --- |
| Azure F capacities support PAYG without a usage commitment; billing is per second with a one-minute minimum. | <https://learn.microsoft.com/fabric/enterprise/licenses#capacity> | 2026-10-15 |
| Fabric capacity is an Azure resource; the suspend endpoint uses the resource type `Microsoft.Fabric/capacities`. | <https://learn.microsoft.com/fabric/enterprise/azure-billing>; <https://learn.microsoft.com/rest/api/microsoftfabric/fabric-capacities/suspend> | 2026-10-15 |
| Pausing enables compute cost savings; resuming resumes billing. Remaining cumulative overages and smoothed operations are summed and added to the bill at pause. | <https://learn.microsoft.com/fabric/enterprise/pause-resume> | 2026-10-15 |
| Paused-capacity monitoring exposes Suspended/Active events and the billed reconciliation spike. | <https://learn.microsoft.com/fabric/enterprise/monitor-paused-capacity> | 2026-10-15 |
| Storage has separate meters; OneLake and mirrored-storage charges are not eliminated by pausing compute. The mirroring free-storage allowance does not apply while paused. | <https://learn.microsoft.com/fabric/enterprise/azure-billing#storage-meters>; <https://azure.microsoft.com/pricing/details/microsoft-fabric/> | 2026-10-15 |
| A one-year Fabric CU reservation is available; the pricing page states approximately 41% savings versus PAYG. It also now lists a three-year option, outside this document's comparison. | <https://learn.microsoft.com/azure/cost-management-billing/reservations/fabric-capacity>; <https://azure.microsoft.com/pricing/details/microsoft-fabric/> | 2026-10-15 |
| Reservation benefits apply hourly; unused reserved hours cannot be carried forward. Storage and networking are not covered. | <https://learn.microsoft.com/azure/cost-management-billing/reservations/fabric-capacity#how-reservation-discounts-apply-to-microsoft-fabric-capacity> | 2026-10-15 |
| F2/F4/F8/F16/F32/F64 contain 2/4/8/16/32/64 CUs. F64+ permits Free-license Power BI viewers with the appropriate Viewer role; smaller F SKUs require a qualifying paid/trial per-user license for Power BI viewing. | <https://learn.microsoft.com/fabric/enterprise/licenses> | 2026-10-15 |
| Queried base-compute PAYG rates are $0.18/CU-hour in westus2/eastus and $0.19 in northeurope. | [westus2 PAYG API][payg-westus2]; [eastus PAYG API][payg-eastus]; [northeurope PAYG API][payg-northeurope] | 2026-10-15 |
| Queried one-year reservation amounts are $938/CU in westus2/eastus and $990/CU in northeurope. See the normalization and nonprimary-meter caveat below. | [westus2 reservation API][reservation-westus2]; [eastus reservation API][reservation-eastus]; [northeurope reservation API][reservation-northeurope] | 2026-10-15 |
| Automation process automation is charged by job-execution minute; the free allocation is 500 minutes per subscription per calendar month, shared across its Automation accounts. | <https://azure.microsoft.com/pricing/details/automation/>; <https://learn.microsoft.com/azure/automation/automation-subscription-limits-faq#service-and-subscription-limits> | 2026-10-15 |
| Monitor metric alerts are priced by monitored time series. The pricing page includes 10 monitored metric time series/month and 1,000 email notifications/month as free units; additional features/volume can cost extra. | <https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-types>; <https://azure.microsoft.com/pricing/details/monitor/> | 2026-10-15 |
| Activity Log is retained for 90 days without charge. Its CLI list command defaults to only 50 records unless `--max-events` is set. | <https://learn.microsoft.com/azure/azure-monitor/fundamentals/activity-log>; <https://learn.microsoft.com/cli/azure/monitor/activity-log#az-monitor-activity-log-list> | 2026-10-15 |
| The Retail Prices API is public/unauthenticated, returns USD retail prices, supports case-sensitive filters, and paginates with `NextPageLink`. | <https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices> | 2026-10-15 |

## 3. Retail meter snapshot and SKU prices

### Exact meters used

Every lookup used `serviceName eq 'Microsoft Fabric'`, `currencyCode=USD`, and `api-version=2023-01-01-preview`.

| Purpose | Exact `productName` | Exact `meterName` | Exact `skuName` | `armSkuName` | Response `type` / term | API unit |
| --- | --- | --- | --- | --- | --- | --- |
| Base provisioned-capacity PAYG rate | `Fabric Capacity` | `Compute Pool Capacity Usage CU` | `Compute Pool Capacity Usage` | `Compute Pool` | `Consumption` | `1 Hour` |
| CU reservation | `Fabric Capacity Reservation` | `Fabric Capacity CU` | `Fabric Capacity` | `Fabric_Capacity_CU_Hour` | `Reservation` / `1 Year` | `1 Hour` |

The [billing reference](https://learn.microsoft.com/fabric/enterprise/azure-billing) identifies **Compute Pool** as the base provisioned capacity. Workload meters apportion capacity charges; do not add a full SKU-hour charge again on top of all its workload-attribution charges. The document's PAYG model excludes separately billed overage and on-demand compute.

**Important API selection details:**

- All three selected PAYG records have `isPrimaryMeterRegion=true`.
- All three returned reservation records have `isPrimaryMeterRegion=false`. They are explicitly included here because reservation pricing was requested. A primary-only filter would omit them. Treat the derived reservation comparison as indicative retail data, and confirm the eligible region, scope, quantity, and purchase quote before committing.
- Reservation records are under **`Fabric Capacity Reservation`**, not `Fabric Capacity`; filtering only on the latter cannot return them.
- Both selected record types have `effectiveStartDate=2023-11-01T00:00:00Z`. That is the price's effective-start field, **not** the query date.
- The API also returned `3 Years` reservation rows ($2,814/CU in westus2/eastus, $2,970/CU in northeurope). They are deliberately excluded from the one-year calculations.
- The reservation `retailPrice` is the term purchase amount per reserved CU, **not $938 or $990 per CU-hour**, despite the API's `1 Hour` unit label. Normalize the one-year amount over **8,760 hours = 365 x 24** for this comparison; confirm the actual term and quote at purchase.

| Region (`armRegionName`) | PAYG USD/CU-hour | 1-year USD/reserved CU | Effective reservation USD/CU-hour | Derived discount versus 24x7 PAYG |
| --- | ---: | ---: | ---: | ---: |
| West US 2 (`westus2`) | $0.180000 | $938.00 | $0.10707763 | 40.5124% |
| East US (`eastus`) | $0.180000 | $938.00 | $0.10707763 | 40.5124% |
| North Europe (`northeurope`) | $0.190000 | $990.00 | $0.11301370 | 40.5191% |

These calculated discounts are consistent with the pricing page's **approximately 41%** statement; they are not exactly 41%.

### F-SKU hourly rates

**List price, retail, USD, queried 2026-10-15; check current pricing for your region and agreement.** Each cell is `CUs x regional PAYG USD/CU-hour`, not a per-user license price.

| SKU | CUs | West US 2 ($0.18/CU-hour) | East US ($0.18/CU-hour) | North Europe ($0.19/CU-hour) |
| --- | ---: | ---: | ---: | ---: |
| F2 | 2 | $0.36/hour | $0.36/hour | $0.38/hour |
| F4 | 4 | $0.72/hour | $0.72/hour | $0.76/hour |
| F8 | 8 | $1.44/hour | $1.44/hour | $1.52/hour |
| F16 | 16 | $2.88/hour | $2.88/hour | $3.04/hour |
| F32 | 32 | $5.76/hour | $5.76/hour | $6.08/hour |
| F64 | 64 | $11.52/hour | $11.52/hour | $12.16/hour |

**The F64 cost threshold is also a licensing threshold.** F64 and larger capacities support Power BI consumption by users with a Fabric Free license and the required Viewer role. On smaller F SKUs, Power BI viewers need Pro, PPU, or an applicable individual trial; authors/sharing users still need the appropriate licenses. Do not compare F32 with F64 solely on compute cost and assume identical viewer licensing. Non-Power-BI Fabric access and app-owns-data embedding have different rules; see the [licensing reference](https://learn.microsoft.com/fabric/enterprise/licenses).

## 4. Savings formula and worked schedules

Let:

| Symbol | Meaning |
| --- | --- |
| `C` | Provisioned CUs; constant SKU assumed |
| `p` | Regional PAYG price in USD/CU-hour |
| `H` | Total elapsed hours in the comparison period |
| `A`, `P` | Actual Active and paused hours, with `A + P = H` |
| `d` | Active duty cycle, `A / H` |

```text
Always-Active base compute cost = C x p x H
Scheduled base compute cost    = C x p x A
Gross avoided base compute     = C x p x P
Gross savings percentage       = P / H x 100 = (1 - d) x 100

Net realized savings = comparable baseline bill - actual post-change bill
```

The last expression must include pause-settled usage, overage, storage changes, and automation/monitoring overhead. The gross formula alone does not predict the invoice. For SKU changes, split the timeline and sum `C x p x hours` for each interval.

### Schedule assumptions

Use a **730-hour average month** (`8,760 / 12`) to normalize weekly duty cycles. Separately, a literal **30-day month has 720 hours**, not 730. For the 30-day examples assume **22 weekdays and 8 weekend days**; actual calendar months vary.

| Schedule | Assumed Active window | Active hours/week | Paused hours/week | Active duty cycle | Gross savings | Active / paused hours in 730-hour normalization | Active / paused hours in assumed 30-day month |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nightly 8-hour pause | Every day 08:00-24:00; paused 00:00-08:00 | 112 | 56 | 66.67% | 33.33% | 486.67 / 243.33 | 480 / 240 |
| Nights + weekends | Weekdays 08:00-24:00; all weekend paused | 80 | 88 | 47.62% | 52.38% | 347.62 / 382.38 | 352 / 368 |
| Only 10 hours on weekdays | Weekdays 08:00-18:00; otherwise paused | 50 | 118 | 29.76% | 70.24% | 217.26 / 512.74 | 220 / 500 |

Weekends mean Saturday and Sunday in these examples. No holidays, daylight-saving transitions, retries, operation latency, extra resumes, or unavailable-time requirements are included. A local 00:00-08:00 window can contain seven or nine elapsed hours on a daylight-saving transition; use actual timestamps when measuring.

### 730-hour monthly examples

West US 2 and East US have identical queried rates, so **US** below means either region; **NE** means North Europe. Dollar figures are rounded only after calculation.

| SKU | Always-Active US/month | Always-Active NE/month |
| --- | ---: | ---: |
| F2 | $262.80 | $277.40 |
| F8 | $1,051.20 | $1,109.60 |
| F64 | $8,409.60 | $8,876.80 |

| SKU | Schedule | US scheduled cost/month | US gross saved/month | NE scheduled cost/month | NE gross saved/month |
| --- | --- | ---: | ---: | ---: | ---: |
| F2 | Nightly 8-hour pause | $175.20 | $87.60 | $184.93 | $92.47 |
| F8 | Nightly 8-hour pause | $700.80 | $350.40 | $739.73 | $369.87 |
| F64 | Nightly 8-hour pause | $5,606.40 | $2,803.20 | $5,917.87 | $2,958.93 |
| F2 | Nights + weekends | $125.14 | $137.66 | $132.10 | $145.30 |
| F8 | Nights + weekends | $500.57 | $550.63 | $528.38 | $581.22 |
| F64 | Nights + weekends | $4,004.57 | $4,405.03 | $4,227.05 | $4,649.75 |
| F2 | Only 10 hours on weekdays | $78.21 | $184.59 | $82.56 | $194.84 |
| F8 | Only 10 hours on weekdays | $312.86 | $738.34 | $330.24 | $779.36 |
| F64 | Only 10 hours on weekdays | $2,502.86 | $5,906.74 | $2,641.90 | $6,234.90 |

For example, US F8 with nights + weekends saves `8 x $0.18 x 730 x (88 / 168) = $550.63/month` in base compute, before the caveats below.

### Literal 30-day cross-check: 720 hours, 22 weekdays, 8 weekend days

The always-Active 30-day baselines are **US:** F2 $259.20, F8 $1,036.80, F64 $8,294.40; **NE:** F2 $273.60, F8 $1,094.40, F64 $8,755.20. Subtract these savings to obtain the corresponding scheduled cost.

| Schedule | US F2 saved | US F8 saved | US F64 saved | NE F2 saved | NE F8 saved | NE F64 saved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nightly 8-hour pause: 240 paused hours | $86.40 | $345.60 | $2,764.80 | $91.20 | $364.80 | $2,918.40 |
| Nights + weekends: 368 paused hours | $132.48 | $529.92 | $4,239.36 | $139.84 | $559.36 | $4,474.88 |
| Only 10 hours on weekdays: 500 paused hours | $180.00 | $720.00 | $5,760.00 | $190.00 | $760.00 | $6,080.00 |

## 5. Break-even against a one-year reservation

The [reservation documentation](https://learn.microsoft.com/azure/cost-management-billing/reservations/fabric-capacity#reservation-discount-application) states:

> "The Fabric capacity reservation discount is applied to CUs on an hourly basis. If you don't have workloads consuming CUs for a full hour, you don't receive the full discount benefit of the reservation. It doesn't carry over."

It also states:

> "You can't carry forward unused reserved hours."

The [pricing page](https://azure.microsoft.com/pricing/details/microsoft-fabric/) states:

> "Committing to a 1 or 3 year reservation can help you save ~41% when compared to pay-as-you-go."

A reservation is a **term commitment with an hourly benefit**, not a PAYG capacity that becomes free to own while paused. It can be paid upfront or monthly, but monthly payment is not a month-to-month cancellation right. Pausing a reserved capacity does not reduce the commitment. Eligible usage on another capacity can consume the benefit within the reservation's region/scope; otherwise that hour's unused benefit is lost.

For a constant `C` CUs and a 365-day comparison, let `R` be the one-year retail term amount per CU and `r = R / 8,760`:

```text
1-year reservation cost          = C x R
PAYG-with-pausing annual cost    = C x p x 8,760 x d
Break-even Active duty cycle     = r / p = R / (8,760 x p)
Equivalent average Active h/day = 24 x r / p
Derived reservation discount    = (1 - r / p) x 100
```

| Region | One-year `R` per CU | Effective `r` per CU-hour | Break-even Active duty cycle | Equivalent average Active hours/day |
| --- | ---: | ---: | ---: | ---: |
| westus2 | $938.00 | $0.10707763 | 59.4876% | 14.2770 |
| eastus | $938.00 | $0.10707763 | 59.4876% | 14.2770 |
| northeurope | $990.00 | $0.11301370 | 59.4809% | 14.2754 |

**Above roughly 59.49% Active time, or 14.28 hours/day averaged across all calendar days, the one-year reservation is cheaper in this base-compute model. Below it, PAYG with actual pausing is cheaper.** Equal cost occurs at the threshold. The threshold is independent of SKU because CUs cancel in the formula.

| Modeled schedule | Active duty cycle | Lower base-compute cost, assuming the commitment is acceptable |
| --- | ---: | --- |
| Nightly 8-hour pause | 66.67% | One-year reservation |
| Nights + weekends | 47.62% | PAYG with pausing |
| Only 10 hours on weekdays | 29.76% | PAYG with pausing |
| Steady 24x7 | 100.00% | One-year reservation |

This is not a purchase recommendation: negotiated rates, eligibility, commitment risk, future resizing/retirement, hour-by-hour reservation utilization, pause reconciliation, and separately billed consumption can change the result. Confirm the nonprimary reservation retail records against the current purchase quote. A reservation and pause automation are not mutually exclusive, but pausing alone does not save the already-committed reservation charge.

## 6. Automation and alerting overhead

| Component | Cost basis | Planning assumption, not a measured guarantee |
| --- | --- | --- |
| Automation account / cloud runbook | Process automation is priced by execution minute, not by the number of schedules. The first 500 job-minutes per subscription per calendar month are free, shared across accounts. | At an **assumed 2-5 minutes/run**, one nightly job for 30 days consumes **60-150 minutes**; adding one similarly sized nightly backstop consumes **120-300 minutes** total. Discovery, target count, polling, retries, dry runs, and other Automation workloads affect consumption. |
| Paid Automation runtime | Public API `serviceName=Automation`, `productName=Process Automation`, `meterName=Basic Runtime`, `skuName=Basic`, `armRegionName=Global`, `1 Minute`: $0 at tier 0 and **$0.002/minute beyond tier 500**, queried 2026-10-15. | If the shared free allowance is exhausted, an additional 150 minutes at that retail rate is $0.30. Check agreement/free-unit eligibility; the pricing page lists exclusions for some discounted or credit-based plans. |
| Failed-job metric alert and action group | Metric alerts charge by monitored time series; the [Monitor pricing page](https://azure.microsoft.com/pricing/details/monitor/) includes 10 monitored metric time series/month and 1,000 emails/month as free units. | One simple, low-volume static-threshold alert is approximately negligible relative to the example capacity costs, and may fit within available free units. This is conditional, **not a universal $0 claim**; existing usage, dimensions, dynamic thresholds, notification channels, and query frequency matter. |
| Diagnostics and longer retention | Log Analytics ingestion/retention, exported logs, and destinations can have separate charges. Native Activity Log retention is 90 days free. | Not required merely to read recent suspend/resume events; price any added diagnostics separately. |

Sources: [Automation pricing](https://azure.microsoft.com/pricing/details/automation/), [free-runtime limit](https://learn.microsoft.com/azure/automation/automation-subscription-limits-faq#service-and-subscription-limits), [Automation runtime retail query][automation-runtime], [alert types](https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-types), [Monitor pricing](https://azure.microsoft.com/pricing/details/monitor/).

## 7. Who benefits

| Situation | Fit and qualification |
| --- | --- |
| Organizations that cannot or do not want to commit to reservations | PAYG avoids a term commitment; scheduled pauses remove otherwise-Active hours. |
| Test/dev/demo/training environments | Often have explicit unavailable windows; coordinate with users and scheduled jobs. |
| Variable or spiky workloads | Useful when complete paused intervals exist. Spiky consumption while the capacity remains Active does not itself stop its base charge. |
| Periodic processing: nightly, weekly, or month-end | Keep the capacity Active for required processing and consumption windows; allow for smoothing and resume lead time. |
| Small teams and proofs of concept | Can avoid paying for unused calendar hours; include any per-user Power BI licenses in the comparison. |
| Steady 24x7 production | Usually not a good pause candidate: availability requirements leave few removable hours. Evaluate reservations and sizing instead. |
| Fully reserved capacity with no other matching usage | Pausing cannot eliminate the committed charge and may waste hourly reservation benefits. |

## 8. Hidden costs and operational caveats

| Caveat | Effect on savings |
| --- | --- |
| Smoothed consumption and cumulative overage settle immediately at pause | These charges are not forgiven. A pause after a large job can produce an immediate billable reconciliation spike. Do not count all paused hours as guaranteed invoice savings. |
| OneLake storage continues | Stored data remains billable. The [pricing page](https://azure.microsoft.com/pricing/details/microsoft-fabric/) specifically says mirrored OneLake storage is billed when provisioned capacity is paused, even where it otherwise fits the free mirroring allowance. SQL/backup/cache and other storage meters can also remain. |
| Capacity overage | Opt-in capacity overage is separately priced relative to PAYG and is not eligible for reservation discounts. The pricing page warns that five-minute limit checks can permit charges above a configured limit. In eastus, the queried `Capacity Overage Capacity Usage CU` / `Capacity Overage Capacity Usage` retail meter was $0.54/CU-hour, not the $0.18 base rate; verify before enabling it. |
| Other paid features/resources | On-demand compute, external source systems, gateways/VMs, storage, log ingestion, notifications, licenses, and applicable data-transfer charges are outside the base-capacity calculation. Do not assume Fabric or all networking charges vanish while paused. |
| Resume restarts the meter | Manual or other automated resumes can shorten the intended paused interval. Measure actual transitions rather than counting scheduled jobs. |
| Failures, exclusions, dry runs, or asynchronous pause completion | A configured schedule is not proof of a completed pause. Retries add run minutes; failure to pause leaves compute billing Active. |
| Workload availability | Pausing can make content unavailable. Coordinate refreshes, pipelines, interactive use, dependencies, and recovery needs before choosing windows. |
| Reservations and cost views | An upfront reservation purchase and a zero-cost covered usage line do not imply zero economic cost. Examine amortized costs and unused reservation benefits as well as actual cash charges. |

## 9. Measure real savings

| Step | What to measure |
| --- | --- |
| 1. Establish a comparable baseline | Record SKU/CUs, region, price/discount, calendar hours, workload, and storage footprint before enabling enforcement. Use the same period definition afterward. |
| 2. Inspect Azure Cost Management | Open **Cost Management > Cost analysis** at the appropriate scope. Filter to the **capacity resource/resource ID** and **Microsoft Fabric** service; set the date range and **group by Meter**. Use actual costs for PAYG invoice comparison. |
| 3. Keep the full meter breakdown | Include Compute Pool and workload `Capacity Usage CU` meters, pause reconciliation/overage, on-demand compute, and separate storage. Do not filter to Compute Pool alone and treat the result as total capacity spend. Review other project resources separately. |
| 4. Account for reservations | Add an amortized-cost/reservation-utilization view. A capacity-resource-only filter can omit the reservation purchase and unused benefit; reconcile those at the applicable billing/reservation scope. |
| 5. Measure elapsed paused intervals | Read Activity Log successful `Microsoft.Fabric/capacities/suspend/action` and `Microsoft.Fabric/capacities/resume/action` events. Reconstruct state at the period start, sort timestamps, and clip intervals to the period. Corroborate with Suspended/Active events in Capacity Metrics. |
| 6. Compare estimate and bill | Apply `C x p x paused hours` as a gross avoided-base-compute estimate. Compare normalized baseline spend with actual post-change spend after billing data has arrived; explain reconciled usage and other meter differences. |

References: [Cost analysis](https://learn.microsoft.com/azure/cost-management-billing/costs/quick-acm-cost-analysis), [Fabric bill reconciliation](https://learn.microsoft.com/fabric/enterprise/azure-billing), [paused-capacity monitoring](https://learn.microsoft.com/fabric/enterprise/monitor-paused-capacity).

### Small PowerShell measurement example

This **read-only** example is for an operator to run later with Azure CLI authentication and permission to read Activity Log. No authenticated Azure call was used to prepare this document.

Replace placeholders and set `$pausedAtStart` from the last successful transition **before** `$from`, corroborated with known capacity state/metrics; do not infer it from today's state. The half-open window is `[from, to)`. An empty event list is meaningful only if you know the starting state and have complete log coverage.

```powershell
$capacityId = '<capacity-resource-id>'
$from = [datetimeoffset]'<start-UTC-ISO8601>'
$to = [datetimeoffset]'<end-UTC-ISO8601>'
$pausedAtStart = $null # Replace with the verified $true (paused) or $false (Active).
$cu = 8; $rate = 0.18 # Example F8 in eastus/westus2; use your CUs and CU-hour rate.
if ($to -le $from -or $pausedAtStart -isnot [bool]) { throw 'Set a valid window and starting state.' }
$limit = 10000
$raw = az monitor activity-log list --resource-id $capacityId `
    --start-time ($from.ToString('o')) --end-time ($to.ToString('o')) `
    --status Succeeded --max-events $limit --output json
if ($LASTEXITCODE -ne 0) { throw 'Activity Log query failed.' }
$events = @(($raw -join "`n") | ConvertFrom-Json -ErrorAction Stop)
if ($events.Count -ge $limit) { throw 'Possible truncation: split the query into smaller windows.' }
$suspend = 'Microsoft.Fabric/capacities/suspend/action'
$resume = 'Microsoft.Fabric/capacities/resume/action'
$cursor = $from; $paused = $pausedAtStart; $pausedHours = 0.0
foreach ($event in ($events | Where-Object { $_.operationName.value -in @($suspend, $resume) } |
        Sort-Object { [datetimeoffset]$_.eventTimestamp })) {
    $at = [datetimeoffset]$event.eventTimestamp
    if ($at -lt $from -or $at -ge $to) { continue }
    if ($paused) { $pausedHours += ($at - $cursor).TotalHours }
    $paused = $event.operationName.value -eq $suspend
    $cursor = $at
}
if ($paused) { $pausedHours += ($to - $cursor).TotalHours }
[pscustomobject]@{
    PausedHours = [math]::Round($pausedHours, 4)
    EstimatedAvoidedBaseComputeUSD = [math]::Round($cu * $rate * $pausedHours, 2)
}
```

The CLI defaults to 50 events; the example raises the limit and refuses a potentially capped result. Query only within available retention, split larger/busy windows and reconcile their boundary states, and preserve/export logs if you need more than the native 90 days. Failed events are excluded; repeated successful suspend/resume events do not double-count time. Missing events, creation/deletion, or SKU changes need separate handling.

Activity Log timestamps describe control-plane operations, not an exact billing ledger. A suspend can be asynchronous; use Capacity Metrics and billed usage to confirm the actual state transitions. The example is not a substitute for invoice reconciliation.

## 10. Pricing changes - always verify

Refresh prices before a purchase or a savings decision. Public retail prices can change, and your agreement, currency, tax treatment, eligibility, and region can differ. Recheck billing rules as well as numbers.

The following **unauthenticated** PowerShell query reproduces the base meter selection in all three regions, then retrieves the reservation product. It follows pagination, keeps primary PAYG meters, and deliberately displays the reservation's primary flag rather than silently dropping nonprimary reservation records.

```powershell
$base = 'https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter='
foreach ($region in @('westus2', 'eastus', 'northeurope')) {
    foreach ($product in @('Fabric Capacity', 'Fabric Capacity Reservation')) {
        $filter = "serviceName eq 'Microsoft Fabric' and productName eq '$product' and armRegionName eq '$region'"
        $url = $base + [uri]::EscapeDataString($filter)
        do {
            $page = Invoke-RestMethod -Uri $url -ErrorAction Stop
            $page.Items | Where-Object {
                ($_.type -eq 'Consumption' -and $_.isPrimaryMeterRegion -eq $true -and
                 $_.meterName -eq 'Compute Pool Capacity Usage CU') -or
                ($_.type -eq 'Reservation' -and $_.reservationTerm -eq '1 Year' -and
                 $_.meterName -eq 'Fabric Capacity CU')
            } | Select-Object armRegionName, productName, meterName, skuName, armSkuName,
                type, reservationTerm, retailPrice, currencyCode, unitOfMeasure,
                isPrimaryMeterRegion, effectiveStartDate
            $url = $page.NextPageLink
        } while ($url)
    }
}
```

After refreshing, recalculate `hourly SKU price = CUs x PAYG rate`, `effective reservation rate = one-year term price / 8,760`, and the duty-cycle threshold. Keep the query date and exact meter/product/SKU fields with the estimate. An empty or changed record is a reason to investigate, not to assume a $0 price.

### Verification boundaries

| Not verified by this research | Treatment in this document |
| --- | --- |
| Actual runbook duration on a particular deployment | 2-5 minutes/run is a planning assumption, not an observed result or service guarantee. |
| A deployment's exact Monitor/Automation invoice or remaining shared free allowance | Conditional estimates only; verify its time series, notifications, job minutes, and pricing-plan eligibility. |
| Agreement-specific pricing, reservation purchase eligibility/quote, or realized invoice savings | Retail modeling only. Reservation records returned as nonprimary are disclosed; confirm at purchase. Reconcile measured costs after deployment. |
| Live suspend/resume Activity Log event completeness and precise billing transition times | Measurement example only; validate against Capacity Metrics and cost data in the target environment. |

[payg-westus2]: https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter=serviceName%20eq%20%27Microsoft%20Fabric%27%20and%20productName%20eq%20%27Fabric%20Capacity%27%20and%20armRegionName%20eq%20%27westus2%27%20and%20meterName%20eq%20%27Compute%20Pool%20Capacity%20Usage%20CU%27%20and%20priceType%20eq%20%27Consumption%27
[payg-eastus]: https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter=serviceName%20eq%20%27Microsoft%20Fabric%27%20and%20productName%20eq%20%27Fabric%20Capacity%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20meterName%20eq%20%27Compute%20Pool%20Capacity%20Usage%20CU%27%20and%20priceType%20eq%20%27Consumption%27
[payg-northeurope]: https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter=serviceName%20eq%20%27Microsoft%20Fabric%27%20and%20productName%20eq%20%27Fabric%20Capacity%27%20and%20armRegionName%20eq%20%27northeurope%27%20and%20meterName%20eq%20%27Compute%20Pool%20Capacity%20Usage%20CU%27%20and%20priceType%20eq%20%27Consumption%27
[reservation-westus2]: https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter=serviceName%20eq%20%27Microsoft%20Fabric%27%20and%20productName%20eq%20%27Fabric%20Capacity%20Reservation%27%20and%20armRegionName%20eq%20%27westus2%27%20and%20priceType%20eq%20%27Reservation%27
[reservation-eastus]: https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter=serviceName%20eq%20%27Microsoft%20Fabric%27%20and%20productName%20eq%20%27Fabric%20Capacity%20Reservation%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20priceType%20eq%20%27Reservation%27
[reservation-northeurope]: https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter=serviceName%20eq%20%27Microsoft%20Fabric%27%20and%20productName%20eq%20%27Fabric%20Capacity%20Reservation%27%20and%20armRegionName%20eq%20%27northeurope%27%20and%20priceType%20eq%20%27Reservation%27
[automation-runtime]: https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&currencyCode=USD&$filter=serviceName%20eq%20%27Automation%27%20and%20productName%20eq%20%27Process%20Automation%27%20and%20armRegionName%20eq%20%27Global%27%20and%20meterName%20eq%20%27Basic%20Runtime%27
