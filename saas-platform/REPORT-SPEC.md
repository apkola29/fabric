# Platform app starter report: specification

**Report:** Platform app Sales Performance · **Status:** draft for approval · **Prepared:** 2026-10-02

This is the report spec that PLAN.md §0 waits on ("Starter report template for every customer: needs an approved
report spec"). Build it once in the template workspace and stamp it per customer. Every number below was verified
against the Fabrikam data in `saas-fabrikam`.

It replaces the three planned reports (Pipeline overview, Account health, Team activity) with one report of four
pages. Pages 1–2 cover pipeline, page 3 covers account health, and page 4 covers team activity. Split it into three
reports later if editions need that.

## 1. Source and verification

| Item | Value |
|---|---|
| Semantic model | Platform app Insights: Direct Lake on OneLake over `platform_app_db` |
| Verified against | Workspace `saas-fabrikam` (`<fabrikam-workspace-id>`), model `<fabrikam-semantic-model-id>` |
| Tables (rows) | Opportunities 331 · Accounts 120 · Contacts 358 · Activities 1,343 · Sales Reps 8 · Calendar 2024-01-01 to 2027-12-31 |
| Relationships | 8: Contacts, Opportunities and Activities → Accounts; Opportunities and Activities → Sales Reps; Opportunities (Close Date) and Activities (Activity Date) → Calendar; Accounts → Sales Reps (inactive) |
| Existing measures | 22, all kept |
| Security roles | All territories, Texas, New Mexico, Georgia (static filter on `Accounts[State]`) |
| Method | TMDL export plus about 60 read-only DAX queries through `executeQueries`. Every new measure in §8 was tested as a query-scoped measure. Nothing in the model was changed. |

## 2. Data findings that shape the design

| Finding (verified) | Impact | How the design handles it |
|---|---|---|
| `Accounts[Country]` has one value (United States); there are 3 states and 15 cities | "By country" analysis is empty | Use **Territory** (`Accounts[State]`) and **City**; never show Country |
| Open deals are related to Calendar by Close Date (Aug–Dec 2026) | A "last 12 months" date slicer hides future-dated pipeline | Pipeline KPIs use `Open Pipeline`, which ignores Calendar; a separate visual shows pipeline by expected close month |
| There's no pipeline snapshot or history table | Historical "pipeline value over time" can't be built | Show deal flow over time (`# Deals Created`, `# Won Deals`, `Win Rate`), plus pipeline by expected close month |
| 54 closed deals were created after their close date, so 25 won deals have a negative sales cycle (minimum −463 days) | A naive sales cycle reads 68.6 days instead of 112.0 | `Sales Cycle (days)` excludes them; data-quality counts in §8; fix upstream |
| 1 deal closed won with a future date (2026-11-10, $112,000); 4 deals created in the future | Existing `Won Revenue (ytd)` counts the future deal | New year-to-date measures stop at today |
| Existing `Won Revenue (ly)` at year level compares a full prior year with a partial current year | Shows −42% year over year; like-for-like is **−7.4%** | Use `Won Revenue PYTD` and `Won Revenue YoY %` |
| Existing `Won Revenue (ytd)` with no date filter evaluates the last Calendar date (2027-12-31) | Returns (Blank) on cards (see §11) | Use `Won Revenue YTD`, which caps at today |
| `Opportunity Created` (330 of 331 rows) and `Account Created` (120 of 120) include a time of day | They can't join to `Calendar[Date]` | Measures strip the time. Upstream fix: add date-only columns to the Delta tables (Direct Lake on OneLake doesn't support regular calculated columns) |
| No relationship between Activities and Opportunities; activity owner and account always match the deal's (0 mismatches) | Touches slice correctly by rep, account and date | Deal-level "last touch" uses `TREATAS`; no model change |
| Accounts → Sales Reps relationship is inactive; 43 deals are owned by a rep who isn't the account owner | The Sales Rep slicer doesn't filter account measures | Page 3 hides the Sales Rep slicer; rep views of accounts use `# Accounts Owned` |
| Roles filter `Accounts[State]` only | Rep lists show all 8 reps under a territory role | Add a `Sales Reps[Region]` filter to each role (§9); Region values equal State values |
| 275 distinct deal names across 331 deals | Detail tables could merge rows | Unhide `Opportunity ID` and include it in every deal table |
| Stage probability is fixed per stage: Prospecting 10, Qualification 25, Proposal 50, Negotiation 75, Closed Won 100, Closed Lost 0 | Stages can be ordered | Sort `Stage` by `Probability` (§9) |

**Insights the report must surface** (as of 2026-10-02):
- 30% of open pipeline is past due ($1.64M across 11 deals).
- 25 of 52 open deals have gone cold (no completed touch in 30 days); 14 of them are in Negotiation.
- Won revenue year to date is $6.81M, −7.4% vs the same period last year.

## 3. Personas

| Persona | Role in the V2 embed token | Pages | Data |
|---|---|---|---|
| Sales manager / executive | All territories | 1–4, Account 360 | Everything |
| Territory manager | Texas, New Mexico or Georgia | 1–4, Account 360 | Own state |
| Sales rep (optional, later) | New role "Own deals" (§9) | 1–4, Account 360 | Own deals and activities; accounts in own territory |

Pass the user's email as the effective identity username so `USERPRINCIPALNAME()` returns it. That's what makes `Viewing As`
work, and the optional rep role.

## 4. Layout grid (every page, 1280 × 720)

```
┌────┬──────────────────────────────────────────────────────────────────────────────┐
│NAV │ Title (x80 y12 w640 h44)        [page button]       Viewing as · Latest activity│
│ 64 ├──────────────────────────────────────────────────────────────────────────────┤
│ px │ Date │ Territory │ Industry │ Sales Rep │ Account search │ Reset   (y64 h40)   │
│    ├──────────────────────────────────────────────────────────────────────────────┤
│    │ KPI card: one Card visual, 6–7 callouts           (x80 y112 w1184 h104)      │
│    ├───────────────────────────────────────────────┬──────────────────────────────┤
│    │ A1 (x80 y228 w704 h230)                       │ A2 (x796 y228 w468 h230)     │
│    ├───────────────┬───────────────┬───────────────┴──────────────────────────────┤
│    │ B1 x80 w386   │ B2 x478 w387  │ B3 x877 w387                    (y470 h230)  │
└────┴───────────────┴───────────────┴──────────────────────────────────────────────┘
```

| Slot | x | y | w | h |
|---|---|---|---|---|
| Nav rail (page navigator buttons, icons; back button on drillthrough) | 0 | 0 | 64 | 720 |
| Title | 80 | 12 | 640 | 44 |
| Page button (page 2 only) | 732 | 20 | 108 | 28 |
| Header label (`Header Subtitle`) | 852 | 12 | 412 | 44 |
| Date slicer | 80 | 64 | 220 | 40 |
| Territory slicer | 312 | 64 | 320 | 40 |
| Industry slicer | 644 | 64 | 170 | 40 |
| Sales Rep slicer | 826 | 64 | 190 | 40 |
| Account search | 1028 | 64 | 166 | 40 |
| Reset button | 1206 | 64 | 54 | 40 |
| KPI card | 80 | 112 | 1184 | 104 |
| A1 | 80 | 228 | 704 | 230 |
| A2 | 796 | 228 | 468 | 230 |
| B1 | 80 | 470 | 386 | 230 |
| B2 | 478 | 470 | 387 | 230 |
| B3 | 877 | 470 | 387 | 230 |
| Tooltip pages | canvas 320 × 240 | | | |

Gaps are 12 px. Margins are 16 px right and 20 px bottom.

## 5. Theme and formatting

- Page background `#F5F7FA`. Visuals are white cards with an 8 px radius, a subtle shadow and an `#E2E8F0` border.
  The nav rail is `#0B1F3A`.
- Colors have fixed meanings: open/pipeline `#2563EB`, won `#15803D`, lost `#B91C1C`, at risk `#F59E0B`.
  Text is `#0F172A` / `#334155` / `#64748B`. Use at most 5 colors per page.
- Fonts are Segoe UI: title 20 semibold, visual titles 12 semibold, KPI values 26, labels 10.
- Values in $K/$M with **1 decimal**. The current render's "$6M" rounds $5.51M up; don't do that. Percentages
  have 1 decimal.
- Every visual title is a business question. No default "Sum of…" titles; minimal gridlines; data labels only
  where they add value.
- Accessibility: text contrast at least 4.5:1; never use color alone (icons plus labels); alt text on every
  visual; logical tab order.

Starting theme JSON (validate it in Desktop under View → Themes):

```json
{
  "name": "Platform app Executive",
  "dataColors": ["#2563EB", "#15803D", "#B91C1C", "#F59E0B", "#0EA5E9", "#7C3AED", "#64748B", "#0F766E"],
  "background": "#FFFFFF",
  "foreground": "#334155",
  "tableAccent": "#2563EB",
  "good": "#15803D",
  "neutral": "#F59E0B",
  "bad": "#B91C1C",
  "textClasses": {
    "callout": { "fontFace": "Segoe UI Semibold", "fontSize": 26, "color": "#0F172A" },
    "title": { "fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#0F172A" },
    "header": { "fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#334155" },
    "label": { "fontFace": "Segoe UI", "fontSize": 10, "color": "#64748B" }
  },
  "visualStyles": {
    "page": { "*": { "background": [{ "color": { "solid": { "color": "#F5F7FA" } }, "transparency": 0 }] } }
  }
}
```

**Don't use:**
- The Q&A visual (retired February 2027).
- Map or filled map (Bing). Use Azure Maps; the tenant setting must be on.
- `Accounts[Country]`.
- `Calendar[Quarter]` without Year.
- The existing `Won Revenue (ytd)` and `Won Revenue (ly)` on visuals.
- `Pipeline Value` in KPIs (it's fine for the close-month visual).
- The Copilot narrative visual (not confirmed for app-owns-data embedding).

## 6. Global filters and interactions

| Filter | Field | Type | Default | Synced pages |
|---|---|---|---|---|
| Date | `Calendar[Date]` | Slicer, relative date | Last 12 months | 1–4 |
| Territory | `Accounts[State]` | Button slicer, multi-select | All | 1–4 |
| Industry | `Accounts[Industry]` | Dropdown | All | 1–4 |
| Sales Rep | `Sales Reps[Sales Rep]` | Dropdown with search; visual-level filter `[# Opportunities]` is not blank | All | 1, 2, 4 (hidden on 3) |
| Account | `Accounts[Account]` | Input slicer, "contains" | Empty | 1–4 |
| Reset | Button → bookmark "Default filters" (data on, all pages) | | | 1–4 |

- **The date slicer must not filter** (Edit interactions → None): page 1 B1 (pipeline by close month) and page 4 B3
  (deals going cold). The `Open Pipeline` family of measures ignores Calendar by design.
- Cross-filtering is the default. Time-axis visuals filter rather than highlight.
- Report-page tooltips are assigned explicitly (Format → Tooltips → Report page), so they don't depend on matching
  tooltip fields.

## 7. Pages

### Page 1: Executive Overview ("Where do we stand?")

| Slot | Visual | Fields | Formatting and behavior |
|---|---|---|---|
| KPI | Card, 6 callouts | `Open Pipeline` (reference labels: `# Open Deals (now)`, `Past-Due Pipeline`) · `Open Weighted Pipeline` · `Won Revenue YTD` (reference label: `Won Revenue YoY %`) · `Win Rate` (reference label: `Win Rate (value)`) · `Average Deal Size` · `Pipeline Velocity` | YoY % red when negative, green when positive |
| A1 | Line and clustered column | X `Calendar[Month Start]`; columns `# Deals Created`, `# Won Deals`; line (secondary axis) `Win Rate` | Visual filter: `Calendar[Date]` in the last 24 months up to today. Title "Is deal flow converting?" |
| A2 | Funnel | Category `Opportunities[Stage]`; value `Open Pipeline` | Visual filter: Stage not in Closed Won, Closed Lost. Order Prospecting → Negotiation (sort by Stage). Tooltip fields: `# Open Opportunities`, `Open Weighted Pipeline`, `Past-Due Pipeline`, `# Stale Open Deals (30d)`. Title "Where is the pipeline sitting?" |
| B1 | Stacked column | X `Calendar[Month Start]`; legend `Opportunities[Stage]`; value `Pipeline Value` | Open stages only; date slicer interaction None. Title "When will it land?"; subtitle "Months before this one are past due" |
| B2 | Decomposition tree | Analyze `Open Pipeline`; explain by `Accounts[State]`, `Accounts[Industry]`, `Sales Reps[Sales Rep]`, `Accounts[Account]` | AI splits on. Title "What drives the pipeline?" |
| B3 | Matrix | Rows `Sales Reps[Sales Rep]`; values `Won Revenue YTD`, `Win Rate`, `Open Pipeline`, `Pipeline Velocity`; sparkline `Won Revenue` by `Calendar[Month Start]` | Win Rate icons: ≥ 60% green, ≥ 50% amber, otherwise red. Data bars on Open Pipeline. Tooltip page "Rep". Title "Rep scoreboard" |

### Page 2: Wins & Losses ("Why do we win and lose?")

| Slot | Visual | Fields | Formatting and behavior |
|---|---|---|---|
| Page button | Button "Explain wins" | Bookmark toggles the overlay | Position in §4 |
| KPI | Card, 6 callouts | `Won Revenue` · `Lost Amount` · `Win Rate (value)` · `# Won Deals` · `Average Deal Size` · `Sales Cycle (days)` | |
| A1 slicer (x80 y228 w704 h36) | Button slicer | `Breakdown[Breakdown]` (field parameter, §9) | Single select; default Industry |
| A1 chart (x80 y268 w704 h190) | Clustered bar | Y `Breakdown`; values `Won Revenue`, `Lost Amount` | Won `#15803D`, lost `#B91C1C`. Title from measure `Title Won vs Lost`. Tooltip page "Segment" |
| A2 | Azure Maps, bubble layer | Location `Accounts[City]` (with `Accounts[State]`); size `Won Revenue`; color gradient `Win Rate` | Tooltip: `Won Revenue`, `Lost Amount`, `Win Rate`, `# Won Deals`. Title "Where do we win?" |
| B1 | Clustered bar | Y `Accounts[Industry]`; values `Won Revenue YTD`, `Won Revenue PYTD` | Tooltip `Won Revenue YoY %`. Title "Are we ahead of last year?" |
| B2 | Scatter | Details `Sales Reps[Sales Rep]`; X `Average Deal Size`; Y `Win Rate`; size `Won Revenue`; legend `Sales Reps[Region]` | Average lines on X and Y (quadrants). Title "Who wins big?" |
| B3 | Table | `Opportunity ID`, `Opportunity`, `Accounts[Account]`, `Close Date`, `Lost Amount`, `Sales Reps[Sales Rep]` | Top 10 by `Lost Amount`; data bars; drillthrough to Account 360. Title "Largest losses" |
| Overlay (x80 y112 w1184 h588, hidden by default) | Key influencers | Analyze `Opportunities[Stage]` (visual filter: Closed Won, Closed Lost); explain by `Accounts[Industry]`, `Accounts[City]`, `Accounts[Employees]`, `Accounts[Annual Revenue]`, `Sales Reps[Sales Rep]` | Close button top right. Only 279 closed deals, so expect few significant influencers |

### Page 3: Customers ("Who are our customers and are they growing?")

The Sales Rep slicer is hidden on this page (account measures use the inactive owner relationship).

| Slot | Visual | Fields | Formatting and behavior |
|---|---|---|---|
| KPI | Card, 7 callouts | `# Accounts` · `# Active Accounts (90d)` · `# Won Customers` · `Won Revenue per Customer` · `Avg Employees` · `Avg Relationship Age (yrs)` · `Contacts per Account` | |
| A1 | Treemap | Category `Accounts[Industry]`; values `Won Revenue` | Tooltip: `# Accounts`, `Avg Employees`, `# Executive Contacts`. Title "Which industries pay?" |
| A2 | Azure Maps, bubble layer | Location `Accounts[City]` (with `Accounts[State]`); size `# Accounts`; legend `Accounts[Industry]` (pie overlay) | Title "Where are our customers?" |
| B1 | Line and clustered column | X `Relationship Age Band[Age Band]` (sorted by `Band Order`); columns `# Accounts by Age Band`; line `Won Revenue by Age Band` | Title "Does tenure pay off?" |
| B2 | Scatter | Details `Accounts[Account]`; X `Avg Employees` (log scale); Y `Won Revenue`; size `Avg Company Revenue`; legend `Accounts[Industry]` | Title "Upsell whitespace" (large companies, small wallet) |
| B3 | Matrix | Rows `Accounts[Industry]` → `Accounts[City]`; values `# Accounts`, `# Won Customers`, `Won Revenue`, `Avg Employees`, `# Executive Contacts` | Data bars on Won Revenue. Title "Portfolio by industry and city" |

### Page 4: Sales Activity ("Is the team doing the right work?")

| Slot | Visual | Fields | Formatting and behavior |
|---|---|---|---|
| KPI | Card, 6 callouts | `# Completed Activities` · `Completed Activity Hours` · `Opportunity Touches` · `Touches per Deal` · `# Stale Open Deals (30d)` (amber) · `# Planned Next 14 Days` | |
| A1 | Line and stacked column | X `Calendar[Week Start]`; columns `# Completed Activities`, legend `Activities[Activity Type]`; line (secondary axis) `Completed Activity Hours` | Visual filter: the last 26 weeks up to today. Title "Is the team active?" |
| A2 | Matrix (heatmap) | Rows `Sales Reps[Sales Rep]`; columns `Calendar[Month Start]`; values `Completed Activity Hours` | Background color scale white → `#2563EB`. Visual filter: the last 6 months up to today. Title "Effort by rep and month" |
| B1 | Clustered bar | Y `Sales Reps[Sales Rep]`; X `Touches per Deal` | Average line (Analytics pane). Title "How often do reps touch each deal?" |
| B2 | Scatter | Details `Sales Reps[Sales Rep]`; X `Completed Activity Hours`; Y `Won Revenue`; size `# Won Deals` | Title "Effort vs outcome" |
| B3 | Table | `Opportunity ID`, `Opportunity`, `Stage`, `Pipeline Value`, `Close Date`, `Days Since Last Touch`, `Sales Reps[Sales Rep]` | Open stages only; sorted by Days Since Last Touch descending; red when ≥ 30. Date slicer interaction None. Drillthrough to Account 360. Title "Deals going cold" |

### Hidden page: Account 360 (drillthrough)

The drillthrough field is `Accounts[Account]`; keep all filters on. Back button at the top of the nav rail.

| Slot | Visual | Fields |
|---|---|---|
| Title | Text from measure `Title Account 360`; subtitle from measure `Account Profile` | |
| KPI | Card, 6 callouts | `Won Revenue` · `Open Pipeline` · `Win Rate` · `# Contacts` · `# Completed Activities` · `Avg Relationship Age (yrs)` |
| A1 | Table "Deals" | `Opportunity ID`, `Opportunity`, `Stage`, `Total Amount`, `Close Date`, `Days Since Last Touch`, `Sales Reps[Sales Rep]` |
| A2 | Table "Contacts" | `First Name`, `Last Name`, `Job Title`, `Contact Email`, `Phone` |
| B (x80 y470 w1184 h230) | Stacked column "Engagement timeline" | X `Calendar[Month Start]`; legend `Activities[Activity Type]`; value `# Completed Activities` |

### Tooltip pages (320 × 240, "Allow use as tooltip")

| Page | Title (x8 y8 w304 h24) | Card (x8 y36 w304 h96) | Mini chart (x8 y140 w304 h92) |
|---|---|---|---|
| Rep | `SELECTEDVALUE('Sales Reps'[Sales Rep])` | `Won Revenue YTD`, `Win Rate`, `Open Pipeline`, `# Stale Open Deals (30d)` | Line: `Won Revenue` by `Calendar[Month Start]`, last 12 months up to today |
| Segment | Hovered category | `Won Revenue`, `Lost Amount`, `Win Rate`, `Average Deal Size`, `# Accounts` | Clustered column: `Won Revenue` vs `Lost Amount` |

## 8. Measures to add

Each measure below was tested against the live model unless it's marked *untested*. Expected values are in §10.

```DAX
-- Home table Opportunities, folder Pipeline
Open Pipeline = CALCULATE ( [Pipeline Value], REMOVEFILTERS ( 'Calendar' ) )
Open Weighted Pipeline = CALCULATE ( [Weighted Pipeline], REMOVEFILTERS ( 'Calendar' ) )
# Open Deals (now) = CALCULATE ( [# Open Opportunities], REMOVEFILTERS ( 'Calendar' ) )
Past-Due Pipeline =
    CALCULATE ( [Pipeline Value], REMOVEFILTERS ( 'Calendar' ), KEEPFILTERS ( 'Opportunities'[Close Date] < TODAY () ) )
# Past-Due Deals =
    CALCULATE ( [# Open Opportunities], REMOVEFILTERS ( 'Calendar' ), KEEPFILTERS ( 'Opportunities'[Close Date] < TODAY () ) )
# Deals Created =
    VAR _dates = VALUES ( 'Calendar'[Date] )
    RETURN
        CALCULATE (
            [# Opportunities],
            REMOVEFILTERS ( 'Calendar' ),
            FILTER (
                ALL ( 'Opportunities'[Opportunity Created] ),
                DATE ( YEAR ( 'Opportunities'[Opportunity Created] ), MONTH ( 'Opportunities'[Opportunity Created] ), DAY ( 'Opportunities'[Opportunity Created] ) ) IN _dates
            )
        )
Pipeline Velocity = DIVIDE ( [# Open Deals (now)] * [Win Rate] * [Average Deal Size], [Sales Cycle (days)] )

-- Folder Results
Win Rate (value) = DIVIDE ( [Won Revenue], [Won Revenue] + [Lost Amount] )
Sales Cycle (days) =
    AVERAGEX (
        FILTER (
            'Opportunities',
            'Opportunities'[Stage] = "Closed Won"
                && INT ( 'Opportunities'[Opportunity Created] ) <= INT ( 'Opportunities'[Close Date] )
        ),
        INT ( 'Opportunities'[Close Date] ) - INT ( 'Opportunities'[Opportunity Created] )
    )

-- Folder Time intelligence
Won Revenue YTD =
    VAR _first = MIN ( 'Calendar'[Date] )
    VAR _last = MIN ( MAX ( 'Calendar'[Date] ), TODAY () )
    RETURN
        IF (
            NOT ISBLANK ( _first ) && _first <= TODAY (),
            CALCULATE ( [Won Revenue], DATESBETWEEN ( 'Calendar'[Date], DATE ( YEAR ( _last ), 1, 1 ), _last ) )
        )
Won Revenue PYTD =
    VAR _first = MIN ( 'Calendar'[Date] )
    VAR _pyLast = EDATE ( MIN ( MAX ( 'Calendar'[Date] ), TODAY () ), -12 )
    RETURN
        IF (
            NOT ISBLANK ( _first ) && _first <= TODAY (),
            CALCULATE ( [Won Revenue], DATESBETWEEN ( 'Calendar'[Date], DATE ( YEAR ( _pyLast ), 1, 1 ), _pyLast ) )
        )
Won Revenue YoY % =
    VAR _py = [Won Revenue PYTD]
    RETURN IF ( NOT ISBLANK ( _py ), DIVIDE ( [Won Revenue YTD] - _py, _py ) )

-- Home table Accounts, folder Accounts
# Active Accounts (90d) =
    CALCULATE (
        DISTINCTCOUNT ( 'Activities'[Activity Account ID] ),
        REMOVEFILTERS ( 'Calendar' ),
        KEEPFILTERS ( 'Activities'[Completed] = TRUE () ),
        KEEPFILTERS ( 'Activities'[Activity Date] > TODAY () - 90 )
    )
# New Accounts =
    VAR _dates = VALUES ( 'Calendar'[Date] )
    RETURN
        CALCULATE (
            [# Accounts],
            FILTER (
                ALL ( 'Accounts'[Account Created] ),
                DATE ( YEAR ( 'Accounts'[Account Created] ), MONTH ( 'Accounts'[Account Created] ), DAY ( 'Accounts'[Account Created] ) ) IN _dates
            )
        )
# Won Customers =
    CALCULATE ( DISTINCTCOUNT ( 'Opportunities'[Opportunity Account ID] ), KEEPFILTERS ( 'Opportunities'[Stage] = "Closed Won" ) )
Won Revenue per Customer = DIVIDE ( [Won Revenue], [# Won Customers] )
Avg Employees = AVERAGE ( 'Accounts'[Employees] )
Avg Company Revenue = AVERAGE ( 'Accounts'[Annual Revenue] )
Avg Relationship Age (yrs) = DIVIDE ( AVERAGEX ( 'Accounts', INT ( TODAY () - 'Accounts'[Account Created] ) ), 365.25 )
# Accounts by Age Band =
    VAR _min = MIN ( 'Relationship Age Band'[Min Years] )
    VAR _max = MAX ( 'Relationship Age Band'[Max Years] )
    RETURN
        CALCULATE (
            [# Accounts],
            FILTER ( 'Accounts', VAR _age = DIVIDE ( TODAY () - 'Accounts'[Account Created], 365.25 ) RETURN _age >= _min && _age < _max )
        )
Won Revenue by Age Band =
    VAR _min = MIN ( 'Relationship Age Band'[Min Years] )
    VAR _max = MAX ( 'Relationship Age Band'[Max Years] )
    RETURN
        CALCULATE (
            [Won Revenue],
            FILTER ( 'Accounts', VAR _age = DIVIDE ( TODAY () - 'Accounts'[Account Created], 365.25 ) RETURN _age >= _min && _age < _max )
        )

-- Home table Contacts, folder Contacts
Contacts per Account = DIVIDE ( [# Contacts], [# Accounts] )
# Executive Contacts = CALCULATE ( [# Contacts], KEEPFILTERS ( 'Contacts'[Job Title] IN { "CEO", "CFO", "VP Sales" } ) )

-- Home table Activities, folder Engagement
Opportunity Touches = CALCULATE ( [# Completed Activities], KEEPFILTERS ( NOT ISBLANK ( 'Activities'[Activity Opportunity ID] ) ) )
# Deals Touched = CALCULATE ( DISTINCTCOUNTNOBLANK ( 'Activities'[Activity Opportunity ID] ), KEEPFILTERS ( 'Activities'[Completed] = TRUE () ) )
Touches per Deal = DIVIDE ( [Opportunity Touches], [# Deals Touched] )
Completed Activity Hours = CALCULATE ( [Activity Hours], KEEPFILTERS ( 'Activities'[Completed] = TRUE () ) )
# Planned Next 14 Days =
    CALCULATE (
        [# Planned Activities],
        REMOVEFILTERS ( 'Calendar' ),
        KEEPFILTERS ( 'Activities'[Activity Date] >= TODAY () ),
        KEEPFILTERS ( 'Activities'[Activity Date] < TODAY () + 14 )
    )

-- Home table Opportunities, folder Engagement
# Stale Open Deals (30d) =
    VAR _openDeals =
        CALCULATETABLE (
            VALUES ( 'Opportunities'[Opportunity ID] ),
            REMOVEFILTERS ( 'Calendar' ),
            KEEPFILTERS ( NOT 'Opportunities'[Stage] IN { "Closed Won", "Closed Lost" } )
        )
    RETURN
        COUNTROWS (
            FILTER (
                _openDeals,
                VAR _id = 'Opportunities'[Opportunity ID]
                VAR _last =
                    CALCULATE (
                        MAX ( 'Activities'[Activity Date] ),
                        REMOVEFILTERS ( 'Calendar' ),
                        REMOVEFILTERS ( 'Sales Reps' ),
                        'Activities'[Completed] = TRUE (),
                        'Activities'[Activity Opportunity ID] = _id
                    )
                RETURN ISBLANK ( _last ) || _last < TODAY () - 30
            )
        )
Days Since Last Touch =
    VAR _last =
        CALCULATE (
            MAX ( 'Activities'[Activity Date] ),
            REMOVEFILTERS ( 'Calendar' ),
            REMOVEFILTERS ( 'Sales Reps' ),
            'Activities'[Completed] = TRUE (),
            TREATAS ( VALUES ( 'Opportunities'[Opportunity ID] ), 'Activities'[Activity Opportunity ID] )
        )
    RETURN IF ( HASONEVALUE ( 'Opportunities'[Opportunity ID] ) && NOT ISBLANK ( _last ), INT ( TODAY () - _last ) )

-- Home table Opportunities, folder Labels
Viewing As =
    VAR _upn = USERPRINCIPALNAME ()
    RETURN COALESCE ( LOOKUPVALUE ( 'Sales Reps'[Sales Rep], 'Sales Reps'[Rep Email], _upn ), _upn )
Latest Activity = CALCULATE ( MAX ( 'Activities'[Activity Date] ), REMOVEFILTERS ( 'Calendar' ), KEEPFILTERS ( 'Activities'[Completed] = TRUE () ) )
Header Subtitle = "Viewing as " & [Viewing As] & "  ·  Latest activity " & FORMAT ( [Latest Activity], "d mmm yyyy" )
Title Won vs Lost = "Won vs lost by " & LOWER ( SELECTEDVALUE ( 'Breakdown'[Breakdown], "segment" ) )
Title Account 360 = "Account 360: " & SELECTEDVALUE ( 'Accounts'[Account] )
Account Profile =
    SELECTEDVALUE ( 'Accounts'[Industry] ) & "  ·  " & SELECTEDVALUE ( 'Accounts'[City] ) & ", " & SELECTEDVALUE ( 'Accounts'[State] )
        & "  ·  " & FORMAT ( SELECTEDVALUE ( 'Accounts'[Employees] ), "#,0" ) & " employees"
        & "  ·  company revenue " & FORMAT ( SELECTEDVALUE ( 'Accounts'[Annual Revenue] ), "$#,0.0,," ) & "M"

-- Home table Opportunities, folder Data quality
# DQ Created After Close = COUNTROWS ( FILTER ( 'Opportunities', INT ( 'Opportunities'[Opportunity Created] ) > INT ( 'Opportunities'[Close Date] ) ) )
# DQ Created In Future = COUNTROWS ( FILTER ( 'Opportunities', 'Opportunities'[Opportunity Created] > NOW () ) )
```

| Measure | Format string | Notes |
|---|---|---|
| Open Pipeline, Open Weighted Pipeline, Past-Due Pipeline, Won Revenue YTD, Won Revenue PYTD, Won Revenue per Customer, Avg Company Revenue, Won Revenue by Age Band | `$#,0` | |
| Pipeline Velocity | `$#,0" per day"` | Expected value of open pipeline closing per day |
| # Open Deals (now), # Past-Due Deals, # Deals Created, # Active Accounts (90d), # New Accounts, # Won Customers, Avg Employees, # Accounts by Age Band, # Executive Contacts, Opportunity Touches, # Deals Touched, # Planned Next 14 Days, # Stale Open Deals (30d), Days Since Last Touch, # DQ Created After Close, # DQ Created In Future | `#,0` | |
| Win Rate (value) | `0.0%` | |
| Won Revenue YoY % | `+0.0%;-0.0%;0.0%` | |
| Sales Cycle (days), Completed Activity Hours | `#,0.0` | |
| Avg Relationship Age (yrs), Contacts per Account, Touches per Deal | `0.0` | |
| Viewing As, Latest Activity (date `d mmm yyyy`), Header Subtitle, Title Won vs Lost, Title Account 360, Account Profile | text | *Untested*: Header Subtitle, Title Won vs Lost, Title Account 360, Account Profile (string concatenation only) |

Give every new measure a one-line description, as the existing 22 have, so the model stays ready for the assistant.

## 9. Model changes

1. **Calculated table.** Supported on Direct Lake on OneLake because it doesn't reference lake tables. Sort `Age Band`
   by `Band Order`, and hide `Min Years` and `Max Years`. Bands stop at 2+ years because the oldest account is about
   2.7 years old.
   ```DAX
   Relationship Age Band = DATATABLE ( "Age Band", STRING, "Band Order", INTEGER, "Min Years", DOUBLE, "Max Years", DOUBLE,
       { { "Under 1 year", 1, 0, 1 }, { "1–2 years", 2, 1, 2 }, { "2+ years", 3, 2, 99 } } )
   ```
2. **Field parameter `Breakdown`.** Create it as a field parameter (`ParameterMetadata` kind 2, or Modeling → New
   parameter → Fields), not as a plain calculated table:
   ```DAX
   Breakdown = {
       ( "Territory", NAMEOF ( 'Accounts'[State] ), 0 ),
       ( "Industry", NAMEOF ( 'Accounts'[Industry] ), 1 ),
       ( "City", NAMEOF ( 'Accounts'[City] ), 2 ),
       ( "Sales Rep", NAMEOF ( 'Sales Reps'[Sales Rep] ), 3 ),
       ( "Account", NAMEOF ( 'Accounts'[Account] ), 4 )
   }
   ```
3. **Sort `Opportunities[Stage]` by `Opportunities[Probability]`.** Each stage has exactly one probability. If that
   ever changes, add a stage-order column upstream instead.
4. **Unhide `Opportunities[Opportunity ID]`.**
5. **Roles.** Add a Sales Reps filter to each territory role so rep lists match the territory:
   `tablePermission 'Sales Reps' = 'Sales Reps'[Region] = "Texas"`, and the same for New Mexico and Georgia.
6. **Optional role "Own deals"** for sales reps. All of a rep's deals are in their own territory (verified: 0
   exceptions), so the account filter hides none of their deals:
   ```
   tablePermission 'Sales Reps' = 'Sales Reps'[Rep Email] = USERPRINCIPALNAME()
   tablePermission Accounts = 'Accounts'[State] = LOOKUPVALUE ( 'Sales Reps'[Region], 'Sales Reps'[Rep Email], USERPRINCIPALNAME () )
   ```
7. **Upstream, in `platform_app_db` or the lake:**
   - add date-only `created_date` columns to opportunities and accounts;
   - fix the 54 deals created after their close date and the 4 created in the future;
   - review the closed-won deal dated 2026-11-10.

## 10. Validation

Run this in DAX query view after adding the measures:

```DAX
EVALUATE ROW ( "Open", [Open Pipeline], "PastDue", [Past-Due Pipeline], "WinRate", [Win Rate], "Cycle", [Sales Cycle (days)],
    "YTD", [Won Revenue YTD], "PYTD", [Won Revenue PYTD], "YoY", [Won Revenue YoY %], "Created", [# Deals Created],
    "Active90", [# Active Accounts (90d)], "Touches", [Opportunity Touches], "PerDeal", [Touches per Deal], "Stale", [# Stale Open Deals (30d)] )
```

Expected values on 2026-10-02 with no filters, under the All territories role. Measures that use `TODAY()` (YTD and
PYTD, past due, stale, active in 90 days, relationship age, planned in 14 days) drift daily.

| Measure | Expected | Measure | Expected |
|---|---|---|---|
| Open Pipeline | $5,512,500 (52 deals) | Won Revenue YTD / PYTD | $6,807,000 / $7,352,000 |
| Open Weighted Pipeline | $2,859,100 | Won Revenue YoY % | −7.4% |
| Past-Due Pipeline | $1,640,500 (11 deals) | # Deals Created | 331 (2024: 23 · 2025: 165 · 2026: 143) |
| Win Rate / Win Rate (value) | 54.8% / 55.0% | # New Accounts | 120 (2024: 50 · 2025: 51 · 2026: 19) |
| Average Deal Size | $123,402 | # Active Accounts (90d) | 64 |
| Sales Cycle (days) | 112.0 | # Won Customers / Won Revenue per Customer | 98 / $192,658 |
| Pipeline Velocity | ≈ $31,430 per day | Avg Employees / Avg Relationship Age (yrs) | 310.7 / 1.6 |
| # Stale Open Deals (30d) | 25 (Prospecting 3 · Qualification 3 · Proposal 5 · Negotiation 14) | # Accounts by Age Band | 25 · 54 · 41 |
| Opportunity Touches / # Deals Touched / Touches per Deal | 1,099 / 324 / 3.4 | Won Revenue by Age Band | $4,357,000 · $8,922,000 · $5,601,500 |
| Completed Activity Hours | 663.6 | Contacts per Account / # Executive Contacts | 3.0 / 124 |
| # Planned Next 14 Days | 33 | # DQ Created After Close / In Future | 54 / 4 |
| Latest Activity | 2026-09-30 | Pipeline Value by close month | Aug $570,500 · Sep $710,000 · Oct $1,999,500 · Nov $1,710,500 · Dec $522,000 |

## 11. Known issues in the current render (`render-manager.html`, 2026-10-02)

- **"Won this year" shows (Blank).** It uses `Won Revenue (ytd)` (`TOTALYTD`). With no date filter, that evaluates
  at the last Calendar date (2027-12-31) and returns 2027 year-to-date, which is empty. Replace it with
  `Won Revenue YTD` (expected $6,807,000).
- **"Pipeline Value $6M"** rounds $5.51M. Use 1 decimal ($5.5M), and use `Open Pipeline` so a date filter can't
  hide future-dated deals.

## 12. Not verified yet

- Layout, tooltip and drillthrough behavior. These can only be checked by building and rendering the report.
- Role changes and the "Own deals" role under View as / effective identity.
- Azure Maps and Key influencers inside app-owns-data embedding.
- The four text measures marked *untested* in §8, and the blank-date guard on the two YTD measures. The YTD logic
  was tested; the validation query covers the rest.

## 13. Sources (Microsoft Learn, retrieved 2026-10-02)

- [Direct Lake overview: field parameters and calculated tables supported, calculated columns limited](https://learn.microsoft.com/fabric/fundamentals/direct-lake-overview)
- [Card visual (GA, up to 10 callouts)](https://learn.microsoft.com/power-bi/visuals/power-bi-visualization-card)
- [Slicers overview (button slicer GA)](https://learn.microsoft.com/power-bi/visuals/power-bi-visualization-slicers)
- [Input slicer (GA)](https://learn.microsoft.com/power-bi/visuals/power-bi-visualization-input-slicer)
- [Map visualizations: Azure Maps replaces Bing maps](https://learn.microsoft.com/power-bi/visuals/power-bi-map-visualizations-overview)
- [Q&A retirement](https://learn.microsoft.com/power-bi/natural-language/q-and-a-intro)
- [Calculation group limitations (calculation groups avoided)](https://learn.microsoft.com/analysis-services/tabular-models/calculation-groups)
