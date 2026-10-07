# HiCRM pilot

Two customer companies on the same HiCRM app, Fabrikam and Contoso. They're isolated from each other at every layer:

| Layer | Per customer |
| --- | --- |
| Web address | `http://fabrikam.localhost:3000` and `http://contoso.localhost:3000` (`https://<customer>.<APP_DOMAIN>` in production) |
| Look | Its own logo, accent color and browser-tab icon |
| Sign-ins | Four people: a sales manager who sees every territory, and one rep each for Texas, New Mexico and Georgia |
| Fabric | Its own workspace, Fabric SQL database, semantic models, starter report and data agent |
| Identities | Its own service account (a service principal that is Admin of that workspace only) and its own workspace identity |

In live mode, each customer's service account exists once an Entra admin has done one step (see
[BUILDOUT.md](BUILDOUT.md), "Per customer"). Until then, the shared platform identity stands in, with a warning in
every provisioning run. Demo mode simulates the accounts.

What each person can see is enforced by the server, not just hidden in the browser:
- the CRM screens, through SQL scoped to the person's territories;
- the embedded report, through row-level security in the embed token;
- the assistant, through the data agent for managers and scoped quick answers for reps.

What was built, which identities exist and why: [BUILDOUT.md](BUILDOUT.md).

## Set it up

```powershell
npm install
npm run setup                          # guided: Fabric or demo mode, capacity, customers
npm run setup -- --mode demo --yes     # everything on this computer, no Azure
npm start
```

Useful options:

| Option | What it does |
| --- | --- |
| `--workspace Contoso=<workspace id>` | Adopts a workspace an admin created (needed when the platform identity can't create workspaces on your capacity, for example a trial) |
| `--customer Northwind:northwind.example` | Other customers instead of the two pilot ones |
| `--reseed` | Replaces a customer's CRM data with fresh sample data |
| `--settings-file <path>` | Where the settings are written (default `.env`; no credential is ever written: they're asked for at start) |

The setup prints each person's email and password once, and writes them to `pilot-logins.md` in the data folder.
Passwords are stored only as hashes, so keep that file safe, then delete it. Running the setup again is safe: existing
customers are provisioned again (idempotent), people keep their passwords, and an operator's logo or color is kept.

`*.localhost` addresses work in Edge, Chrome and Firefox without any setup. For other clients, add `127.0.0.1
fabrikam.localhost contoso.localhost` to your hosts file.

## The people

| Company | Person | Role | Sees |
| --- | --- | --- | --- |
| Fabrikam | Leah Thompson | Sales manager | Every territory |
| Fabrikam | Drew Collins, Arjun Mehta, Amara Okoye | Sales reps | Texas, New Mexico, Georgia |
| Contoso | Maria Alvarez | Sales manager | Every territory |
| Contoso | Sam Rivera, Priya Nair, Grace Kim | Sales reps | Texas, New Mexico, Georgia |

## The story

1. **Fabrikam's address.**
   - Open `http://fabrikam.localhost:3000`. The page shows Fabrikam's logo and color, and asks you to sign in to
     Fabrikam.
   - Sign in as Leah, the manager. Home shows the whole pipeline.
2. **The standard report.**
   - Reports opens "Sales overview", the Power BI report embedded with an embed token that Fabrikam's service account
     requested, for this report only, for 30 minutes.
   - It's view-only. Customers building their own reports is the next phase (`REPORT_AUTHORING`).
3. **The assistant.**
   - Ask "pipeline by state". Leah's question goes to Fabrikam's data agent through its MCP server. The answer names
     the measures it used.
   - A chart of the same question comes from the CRM data Leah may see.
   - Try "won revenue by month this year" for a line.
4. **A rep.**
   - Sign out and sign in as Drew (Texas). The CRM, the report and the assistant show Texas only.
   - Opening another territory's account answers "not found", even by ID.
   - Drew's questions get quick answers scoped to Texas, with charts, and never reach the data agent, which sees
     every territory.
5. **Access changes at once.**
   - In the back office, move Drew to New Mexico. His session ends, and when he signs in again he sees New Mexico.
6. **Another company.**
   - Open `http://contoso.localhost:3000`: a different logo and color.
   - Leah's Fabrikam password doesn't work there: same answer as a wrong password.
   - Fabrikam's session cookie is never sent to Contoso's address, and the server checks the pair too.
   - Sign in as Maria: Contoso's own data, numbers and report.
7. **The platform's address.**
   - `http://localhost:3000` asks only for a work email ("Find your company"), then sends you to your company's
     address.
8. **Behind the scenes, in the back office** (`http://localhost:3000/admin`, with the back-office key you gave or were shown at start). For each
   customer:
   - **Overview:** its address, workspace, service account and provisioning steps.
   - **Check access:** compares who can reach the workspace with least privilege.
   - **Assistant:** shows the data agent's MCP endpoint and, on request, **the questions people asked and the
     answers they got**: who, their scope, and who answered (the data agent, or a quick answer plus why). Opening
     them is recorded in the customer's activity log. Where else chats are kept: ARCHITECTURE.md, "Where questions and
     answers are kept".
   - **License:** holds the logo and color.

## Change things

```powershell
npm run cli -- user-access Fabrikam drew.collins@fabrikam.com --role rep --territory "New Mexico"
npm run cli -- brand Contoso --logo contoso.svg --color "#3b3a98"
npm run cli -- questions Fabrikam
npm run cli -- reseed Fabrikam --confirm      # fresh sample data, dated from today
npm run pilot:remove                          # removes the pilot customers and their workspaces
```

The tenant registry is a JSON file with one writer. Run commands that change data while the server is stopped, or use
the back office.

## When something looks wrong

| You see | Why, and what to do |
| --- | --- |
| "There's no company at this address" | The subdomain belongs to no customer. Check the address, or the customer's address in the back office |
| A 421 error | The host name isn't the platform's (`APP_DOMAIN`). Use the addresses the setup printed |
| The report is blank | Reload the page; embed tokens last 30 minutes and are renewed automatically while the page is open |
| "Quick answer from your CRM records" for a manager | The data agent didn't answer. The question log (`npm run cli -- questions <customer>`) and the activity log say why; after a failure the agent rests for 15 minutes |
| The first question after a quiet spell is slow | The CRM database (SQL database in Fabric) pauses after 15 minutes without activity and resumes on the next connection, usually within seconds. The app waits and retries for up to 90 seconds; later questions are fast |
| No chart image from the agent | The code interpreter (`DATA_AGENT_CODE_INTERPRETER`) is a preview that needs a paid F2+ capacity. The app draws its own charts either way |
