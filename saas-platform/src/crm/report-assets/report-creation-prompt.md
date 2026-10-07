<!--
Maintainers: the sections between the generated markers come from src/crm/model.js, src/crm/schema.js and
src/crm/report.js. After changing those, run `node scripts/report-assets.js`. test/report-assets.test.js fails when
this file is stale or names a field the model doesn't have.
-->

# Report creation prompt: Platform app Insights

Give an AI (or a person) this whole file, followed by the request. It covers the **visualization layer** only: pages, visuals, field bindings, layout and formatting. The numbers come from the semantic model's measures, whose DAX is in `Platform-app-Insights.measures.dax` (generated from `src/crm/model.js`). Building a report never needs that file, and never changes it.

## Role

You design report pages for the platform app, a CRM in which every customer has their own copy of the same semantic model. You pick visuals, bind them to the model's fields by their exact names, and lay them out on the page. You don't write DAX or formulas, and you don't calculate numbers.

## Input

- **Request:** what the page should answer. It follows this prompt.
- **Audience:** sales managers (every territory), sales reps (their territories), or both. If the request doesn't say, design for both.

## Rules

### Fields and numbers

1. Use only the fields listed under "Fields", written exactly as listed (spaces, case, `#`, parentheses): `Opportunities[Pipeline Value]`, `Sales Reps[Sales Rep]`.
2. Every number comes from a measure. Never put a column in a value role to be summed, counted or averaged; the model turns implicit measures off.
3. Bind each measure on the table it lives on, as listed under "Fields": `Accounts[# Accounts]`, `Opportunities[Win Rate]`.
4. Don't create measures, calculated columns, visual calculations, quick measures or groups, and don't write DAX or formulas of any kind.
5. When no measure gives the number the request needs, don't approximate it with another one. Leave the visual out and add a semantic-layer request (see below).
6. A split only works with a measure that its table filters (see "How filters flow"). `Sales Reps[Sales Rep]` works with `Opportunities[Pipeline Value]` but repeats the same total with `Accounts[# Accounts]`; use `Accounts[# Accounts Owned]` per rep.

### Security and audience

7. Bind to Platform app Insights only. Never use Platform app Insights - Assistant.
8. Never filter, title or label anything by territory name. Row-level security decides what each viewer sees, so the same page has to work for one territory and for all of them.
9. Territory security doesn't filter `Sales Reps` or `Calendar`. Never put `Sales Reps` columns in a slicer, or in a visual without a measure that Sales Reps filters, or the page lists every rep in the company.
10. Viewers have no filter pane (it shows only while editing), so anything a viewer should change is a slicer on the page. Slice by `Accounts` columns, `Opportunities[Stage]`, `Activities[Activity Type]` or `Calendar` columns.
11. A split by `Accounts[State]` shows a rep with one territory a single bar. Use it on managers' pages; on reps' pages, split by stage, account, rep or month.

### Time

12. Time axes use `Calendar` columns: `Calendar[Month Start]` for monthly trends (it keeps the months in order), `Calendar[Week Start]`, `Calendar[Quarter]`, `Calendar[Year]` or the Calendar Hierarchy. `Calendar[Month]` is for month names in a matrix.
13. `Opportunities[Close Date]` and `Activities[Activity Date]` belong in table rows, not on axes; the Calendar already filters both.
14. `Opportunities[Won Revenue (ly)]` needs a Calendar field in the visual or a Calendar slicer. `Opportunities[Won Revenue (ytd)]` works on its own: this year up to today.

### Visuals

Use these types and their role names. If the request needs another type, say so in `notes` instead of guessing its roles.

| To show | `type` | Roles |
|---|---|---|
| Headline numbers | `cardVisual` | `Data`: 1 to 4 measures, each with a short `label` |
| Categories ranked by a number | `clusteredBarChart` | `Category`: 1 column. `Y`: 1 measure |
| A few short categories (stages, quarters) | `clusteredColumnChart` | `Category`: 1 column. `Y`: 1 measure |
| A trend | `lineChart` | `Category`: 1 Calendar column. `Y`: 1 or 2 measures of the same kind |
| Detail rows | `tableEx` | `Values`: columns first, then measures |
| A cross-tab, such as rep by quarter | `pivotTable` | `Rows`, `Columns`: columns. `Values`: measures |
| A filter viewers can change | `slicer` | `Values`: 1 column |

- One question per visual. Don't mix kinds (currency, count, percent) on one axis.
- Stages have no sort column, so sort stage visuals by their measure, or ask the semantic layer for a stage order.
- Keep cross-filtering on: selecting a bar filters the other visuals.

### Layout and formatting

- **Page:** 1280 x 720, fit to page, one topic, a short name such as "Overview". At most 8 visuals.
- **Grid:** 20 px margins and gaps. Rows start at y = 20 (headline card, 82 high), y = 122 (280 high) and y = 422 (278 high). In a row, widths and gaps fill 1240: three of 400 (x = 20, 440, 860), two parts such as 720 + 500 (x = 20, 760), or the full 1240.
- **Order:** visuals run top-left to bottom-right, with z and tab order 1000, 2000, 3000 and so on. Nothing overlaps or leaves the page.
- **Headline card:** one `cardVisual` across the top, value 20 pt, label 11 pt, 8 px padding, no title.
- **Titles:** every other visual has a title in sentence case, 2 to 5 words, saying what and by what: "Pipeline by stage".
- **Sort:** categories by their measure, largest first; time in order, oldest first; tables by their main measure, largest first.
- **Theme:** Fluent2-CY26SU09 (`Fluent2-CY26SU09.json` in this folder) applies to the whole report. Don't set colors, fonts or number formats on visuals (the card sizes above are the one exception); number formats come from the measures.

## Semantic-layer requests

When a number is missing, ask for a measure instead of working around it:

```json
{ "measure": "# Overdue Activities", "table": "Activities", "folder": "Counts", "kind": "Count", "meaning": "Planned activities whose date is before today.", "neededBy": "Overdue activities by sales rep" }
```

Name it the way the model names measures: Title Case, counts start with "# ", year to date ends in "(ytd)", last year in "(ly)". Describe the rule in plain words. The semantic layer adds the DAX to `src/crm/model.js`, which regenerates `Platform-app-Insights.measures.dax` and the field list below.

## Output

Return one JSON object, shaped like the example at the end:

- `report`, `model`, `theme`.
- `pages`: each with `name`, `width`, `height` and `visuals`.
- Each visual: `type`; `title` (not on the headline card); `position` as [x, y, width, height]; `roles`, mapping each role name to its fields as `{ "field": "<Table>[<Field>]" }`, with a `label` for a shorter header (card values always have one); and `sort` (`field`, `direction`).
- `semanticLayerRequests`: the measures you need and don't have, or [].
- `notes`: anything the builder must know, such as a visual you left out, or [].

The JSON maps one-to-one to PBIR `visual.json` (see `src/crm/report.js`): `type` is `visualType`, `position` the container position, `roles` the `query.queryState` projections (Entity = table, Property = field, queryRef = "Table.Field"; category fields are active), and `sort` the `query.sortDefinition`.

## Check before answering

- Every field is listed under "Fields", written exactly, and each measure is on its own table.
- No DAX, no formulas, no column in a value role.
- No territory names in filters, titles or labels; no `Sales Reps` column without a measure that Sales Reps filters.
- Every visual sits on the grid inside 1280 x 720, without overlaps. Every chart and table has a title and a sort.

## Fields

<!-- generated:fields -->
**Model:** Platform app Insights. Never bind to Platform app Insights - Assistant: it has no row-level security and serves only the data agent.

**Security:** the role `All territories` is for sales managers, and each territory (Texas, New Mexico and Georgia) has a role for its reps. A territory role keeps `Accounts[State]` to that state, and the filter reaches `Contacts`, `Opportunities` and `Activities`. `Sales Reps` and `Calendar` aren't filtered by territory.

**How filters flow:**

- `Sales Reps` filters `Opportunities` and `Activities`.
- `Sales Reps` to `Accounts` is inactive: only `Accounts[# Accounts Owned]` uses it.
- `Accounts` filters `Contacts`, `Opportunities` and `Activities`.
- `Calendar` filters `Opportunities` by `Close Date` and `Activities` by `Activity Date`.

**Tables:**

- `Sales Reps`: The sales team. Each rep owns accounts, opportunities and activities. One row per rep.
- `Accounts`: Customer companies. One row per company.
- `Contacts`: People who work at customer accounts. One row per person.
- `Opportunities`: Deals in the sales pipeline. One row per deal. Stage "Closed Won" means won and "Closed Lost" means lost; every other stage is open pipeline.
- `Activities`: Calls, emails, meetings and demos with customers. One row per activity; future dates are planned activities.
- `Calendar`: One row per day, covering every date in the CRM through the end of next year. Use it to report by year, quarter, month or week.

**Measures** (the only source of numbers):

| Field | Folder | Kind | Meaning | Also called |
|---|---|---|---|---|
| `Opportunities[Total Amount]` | Pipeline | Currency | Sum of deal amounts in every stage, open and closed. Use Pipeline Value for open deals and Won Revenue for won deals. | deal amount, amount, total value, value of opportunities, value of deals |
| `Opportunities[Pipeline Value]` | Pipeline | Currency | Total amount of open deals: every stage except Closed Won and Closed Lost. | open pipeline, pipeline, open deal value, open value, value of open opportunities |
| `Opportunities[Weighted Pipeline]` | Pipeline | Currency | Open deal amounts multiplied by each deal's win probability: the share of the pipeline you can expect to win. | weighted, forecast, expected revenue |
| `Opportunities[Current Pipeline]` | Pipeline | Currency | Open pipeline right now, whatever dates are selected, including deals expected to close later. Pipeline Value follows the selected dates by expected close date. |  |
| `Opportunities[Current Weighted Pipeline]` | Pipeline | Currency | Weighted pipeline right now, whatever dates are selected. |  |
| `Opportunities[Past-Due Pipeline]` | Pipeline | Currency | Open deals whose expected close date has passed: pipeline that needs a new date or a decision. |  |
| `Opportunities[Pipeline Velocity (per day)]` | Pipeline | Currency | Expected won revenue per day from the open pipeline: open deals times win rate times average deal size, divided by the sales cycle in days. |  |
| `Opportunities[Won Revenue]` | Results | Currency | Total amount of won deals (stage Closed Won). Use Close Date or the Calendar to see revenue for a period. | revenue, sales, bookings, won amount, closed won |
| `Opportunities[Lost Amount]` | Results | Currency | Total amount of lost deals (stage Closed Lost). | lost revenue, lost value, closed lost, value of lost deals, value of lost opportunities |
| `Opportunities[Win Rate]` | Results | Percent | Share of closed deals that were won: won deals divided by won plus lost deals. Open deals are not counted. | win ratio, close rate, conversion rate, conversion |
| `Opportunities[Average Deal Size]` | Results | Currency | Average amount of a won deal: Won Revenue divided by the number of won deals. | average deal, avg deal size, deal size |
| `Opportunities[Win Rate (value)]` | Results | Percent | Share of closed deal value that was won: won revenue divided by won plus lost amounts. Win Rate counts deals instead. |  |
| `Opportunities[Sales Cycle (days)]` | Results | Number | Average number of days from creating a deal to winning it, for won deals. |  |
| `Accounts[Won Revenue per Customer]` | Results | Currency | Average won revenue per account that has won deals. |  |
| `Opportunities[# Opportunities]` | Counts | Count | Number of deals in every stage, open and closed. | number of opportunities, opportunity count, opportunities, number of deals, deal count |
| `Opportunities[# Open Opportunities]` | Counts | Count | Number of open deals: every stage except Closed Won and Closed Lost. | open opportunities, open deals, number of open deals |
| `Opportunities[# Won Deals]` | Counts | Count | Number of won deals (stage Closed Won). | won deals, deals won, wins, number of wins |
| `Opportunities[# Lost Deals]` | Counts | Count | Number of lost deals (stage Closed Lost). | lost deals, deals lost, losses, number of losses |
| `Accounts[# Accounts]` | Counts | Count | Number of customer accounts. Sales reps do not filter this measure; use # Accounts Owned per rep. | number of accounts, account count, accounts, customers, companies |
| `Accounts[# Accounts Owned]` | Counts | Count | Number of accounts each sales rep owns. Use it with Sales Rep or Region. | accounts owned, owned accounts, book of business, accounts per rep |
| `Accounts[# Accounts With Open Deals]` | Counts | Count | Number of accounts that have at least one open deal. | accounts with open deals, active accounts, accounts with pipeline |
| `Contacts[# Contacts]` | Counts | Count | Number of people at customer accounts. | number of contacts, contact count, contacts, people |
| `Activities[# Activities]` | Counts | Count | Number of calls, emails, meetings and demos, completed and planned. | number of activities, activity count, activities, touches, interactions |
| `Activities[# Completed Activities]` | Counts | Count | Number of activities that are done. | completed activities, done activities, finished activities |
| `Activities[# Planned Activities]` | Counts | Count | Number of activities that are scheduled but not done yet. | planned activities, upcoming activities, open activities, scheduled activities |
| `Activities[# Opportunities Touched]` | Counts | Count | Number of different deals that had at least one activity. | opportunities touched, deals touched, deals with activity |
| `Opportunities[# Current Open Deals]` | Counts | Count | Number of open deals right now, whatever dates are selected. |  |
| `Opportunities[# Past-Due Deals]` | Counts | Count | Number of open deals whose expected close date has passed. |  |
| `Opportunities[# Deals Created]` | Counts | Count | Number of deals created in the selected period, by the day they were created rather than their close date. |  |
| `Accounts[# Active Accounts (90d)]` | Counts | Count | Number of accounts with at least one completed activity in the last 90 days. |  |
| `Accounts[# Won Customers]` | Counts | Count | Number of accounts with at least one won deal. |  |
| `Activities[# Planned Next 14 Days]` | Counts | Count | Number of planned activities in the next 14 days, whatever dates are selected. |  |
| `Opportunities[Won Revenue (ytd)]` | Time intelligence | Currency | Won revenue from January 1 of this year to today, by close date. For a past period, from January 1 of its year to the end of that period; blank for future periods. | won revenue ytd, revenue ytd, year to date, ytd |
| `Opportunities[Won Revenue (ly)]` | Time intelligence | Currency | Won revenue in the same period one year earlier, by close date. Needs a date from the Calendar. | won revenue last year, revenue last year, last year, prior year |
| `Opportunities[Won Revenue Last Year (ytd)]` | Time intelligence | Currency | Won Revenue (ytd) for the same span one year earlier: from January 1 to the same day last year. |  |
| `Opportunities[Won Revenue Growth (ytd)]` | Time intelligence | Percent | Growth of Won Revenue (ytd) over Won Revenue Last Year (ytd), the same span one year earlier. |  |
| `Activities[Activity Hours]` | Effort | Number | Total time spent on activities, in hours. | hours, time spent, effort |
| `Activities[Completed Activity Hours]` | Effort | Number | Time spent on completed activities, in hours. |  |
| `Activities[Touches per Deal]` | Effort | Number | Average number of completed activities per deal, for deals that had any. |  |
| `Opportunities[# Stale Open Deals (30d)]` | Engagement | Count | Open deals that have gone more than 30 days without a completed activity, counting from the day they were created if they have had none, whatever dates are selected: the deals whose Days Since Last Touch is over 30. |  |
| `Opportunities[Days Since Last Touch]` | Engagement | Number | For one open deal: days since its last completed activity, or since it was created if it has had none. Blank for closed deals. Use it in a table of deals that includes Opportunity ID. |  |
| `Accounts[Average Employees]` | Company size | Number | Average number of employees at the accounts. |  |

**Columns** (categories, axes, slicers and table rows):

| Field | Kind | Meaning | Also called |
|---|---|---|---|
| `Sales Reps[Sales Rep]` | Text | Full name of the sales rep. | salesperson, seller, rep, owner, by owner |
| `Sales Reps[Rep Email]` | Text | Work email address of the sales rep. |  |
| `Sales Reps[Region]` | Text | Sales territory the rep covers: Texas, New Mexico or Georgia. | rep region |
| `Accounts[Account]` | Text | Company name of the customer account. | customer, company |
| `Accounts[Industry]` | Text | Industry of the customer, such as Healthcare or Retail. | vertical, sector |
| `Accounts[Country]` | Text (Country) | Country where the customer is headquartered. | countries, geography |
| `Accounts[City]` | Text (City) | City where the customer is headquartered. | cities |
| `Accounts[State]` | Text (StateOrProvince) | US state of the customer. Each state is a sales territory: Texas, New Mexico or Georgia. | territory, sales territory |
| `Accounts[Annual Revenue]` | Currency | The customer's own yearly revenue in US dollars (company size), not revenue from deals. |  |
| `Accounts[Employees]` | Whole number | Number of employees at the customer (company size). |  |
| `Accounts[Account Created]` | Date and time | When the account was added to the CRM. |  |
| `Contacts[First Name]` | Text | First name of the contact. |  |
| `Contacts[Last Name]` | Text | Last name of the contact. |  |
| `Contacts[Contact Email]` | Text | Email address of the contact. |  |
| `Contacts[Phone]` | Text | Phone number of the contact. |  |
| `Contacts[Job Title]` | Text | Job title of the contact, such as CFO or IT Director. | title, role |
| `Opportunities[Opportunity ID]` | ID | Unique ID of the deal. Add it to a table of deals so two deals with the same name stay on separate rows. |  |
| `Opportunities[Opportunity]` | Text | Name of the deal. | deal |
| `Opportunities[Stage]` | Text | Sales stage: Prospecting, Qualification, Proposal, Negotiation (open), Closed Won or Closed Lost (closed). | sales stage, pipeline stage, funnel |
| `Opportunities[Probability]` | Whole number | Chance of winning the deal, in percent from 0 to 100. Set by the stage. |  |
| `Opportunities[Close Date]` | Date | Date the deal closed, or the expected close date for open deals. |  |
| `Opportunities[Opportunity Created]` | Date and time | When the deal was added to the CRM. |  |
| `Activities[Activity Type]` | Text | Kind of activity: Call, Email, Meeting or Demo. | type of activity, channel, type |
| `Activities[Subject]` | Text | Short subject line of the activity. |  |
| `Activities[Activity Date]` | Date | Date the activity happened or is planned for. |  |
| `Activities[Completed]` | True or false | True when the activity is done, false when it is still planned. |  |
| `Calendar[Date]` | Date | The calendar day. |  |
| `Calendar[Year]` | Whole number | Calendar year, such as 2026. | by year, yearly, annual |
| `Calendar[Quarter]` | Text | Calendar quarter: Q1, Q2, Q3 or Q4. | by quarter, quarterly |
| `Calendar[Month]` | Text | Month name, such as January. Sorted by month number. |  |
| `Calendar[Year-Month]` | Text | Year and month as YYYY-MM, such as 2026-10. | year month |
| `Calendar[Month Start]` | Date | The first day of the month. Use it for monthly trends: charts keep the months in time order. | over time, trend, by month, monthly, month |
| `Calendar[Week Start]` | Date | The Monday that starts the week. | by week, weekly, week |

`Calendar` also has the hierarchy `Calendar Hierarchy`: Year > Quarter > Month > Date.
<!-- /generated:fields -->

## Example: the starter report, Sales overview

<!-- generated:example -->
```json
{
  "report": "Sales overview",
  "model": "Platform app Insights",
  "theme": "Fluent2-CY26SU09",
  "pages": [
    {
      "name": "Overview",
      "width": 1280,
      "height": 720,
      "visuals": [
        {
          "type": "cardVisual",
          "position": [20, 20, 1240, 82],
          "roles": {
            "Data": [
              { "field": "Opportunities[Pipeline Value]", "label": "Pipeline" },
              { "field": "Opportunities[Won Revenue (ytd)]", "label": "Won this year" },
              { "field": "Opportunities[Win Rate]", "label": "Win rate" },
              { "field": "Opportunities[# Open Opportunities]", "label": "Open deals" }
            ]
          }
        },
        {
          "type": "clusteredBarChart",
          "title": "Pipeline by state",
          "position": [20, 122, 400, 280],
          "roles": {
            "Category": [
              { "field": "Accounts[State]" }
            ],
            "Y": [
              { "field": "Opportunities[Pipeline Value]" }
            ]
          },
          "sort": { "field": "Opportunities[Pipeline Value]", "direction": "Descending" }
        },
        {
          "type": "clusteredBarChart",
          "title": "Pipeline by stage",
          "position": [440, 122, 400, 280],
          "roles": {
            "Category": [
              { "field": "Opportunities[Stage]" }
            ],
            "Y": [
              { "field": "Opportunities[Pipeline Value]" }
            ]
          },
          "sort": { "field": "Opportunities[Pipeline Value]", "direction": "Descending" }
        },
        {
          "type": "clusteredBarChart",
          "title": "Pipeline by sales rep",
          "position": [860, 122, 400, 280],
          "roles": {
            "Category": [
              { "field": "Sales Reps[Sales Rep]" }
            ],
            "Y": [
              { "field": "Opportunities[Pipeline Value]" }
            ]
          },
          "sort": { "field": "Opportunities[Pipeline Value]", "direction": "Descending" }
        },
        {
          "type": "lineChart",
          "title": "Won revenue by month",
          "position": [20, 422, 720, 278],
          "roles": {
            "Category": [
              { "field": "Calendar[Month Start]" }
            ],
            "Y": [
              { "field": "Opportunities[Won Revenue]" }
            ]
          },
          "sort": { "field": "Calendar[Month Start]", "direction": "Ascending" }
        },
        {
          "type": "tableEx",
          "title": "Accounts by pipeline",
          "position": [760, 422, 500, 278],
          "roles": {
            "Values": [
              { "field": "Accounts[Account]" },
              { "field": "Accounts[State]" },
              { "field": "Opportunities[Pipeline Value]", "label": "Pipeline" }
            ]
          },
          "sort": { "field": "Opportunities[Pipeline Value]", "direction": "Descending" }
        }
      ]
    }
  ],
  "semanticLayerRequests": [],
  "notes": []
}
```
<!-- /generated:example -->
