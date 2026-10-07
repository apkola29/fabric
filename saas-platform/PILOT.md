# HiCRM pilot

Two customer companies on the same HiCRM app, Fabrikam and Contoso. They're isolated from each other at every layer:

| Layer | Per customer |
| --- | --- |
| Web address | `http://fabrikam.localhost:3000` and `http://contoso.localhost:3000` (`https://<customer>.<APP_DOMAIN>` in production) |
| Look | Its own logo, accent color and browser-tab icon |
| Sign-ins | Four people: a sales manager who sees every territory, and one rep each for Texas, New Mexico and Georgia |
| Fabric | Its own workspace, Fabric SQL database, semantic models, starter report and data agent |
| Identities | Its own service principal (Admin of that workspace only) and its own workspace identity |

In live mode, an Entra admin can register each customer's service principal (see [BUILDOUT.md](BUILDOUT.md), "Per
customer"), or the platform can create it if enabled. `TENANT_IDENTITY_MODE=required` refuses missing credentials;
only `preferred` mode lets the platform identity stand in, with a warning. The isolated pilot uses `required` and
`PLATFORM_WORKSPACE_ACCESS=release`. Demo mode simulates the accounts and uses a report placeholder, not Power BI.

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
The local sign-in page also shows clickable cards for that company's people, so you can pick a person without typing a
password. Password sign-in still works. Passwords are stored only as hashes, so keep that file safe, then delete it.
Running the setup again is safe: existing customers are provisioned again (idempotent), people keep their passwords,
and an operator's logo or color is kept.

`*.localhost` addresses work in Edge, Chrome and Firefox without any setup. For other clients, add `127.0.0.1
fabrikam.localhost contoso.localhost` to your hosts file.

## The people

| Company | Person | Role | Sees |
| --- | --- | --- | --- |
| Fabrikam | Leah Thompson | Sales manager | Every territory |
| Fabrikam | Drew Collins, Arjun Mehta, Amara Okoye | Sales reps | Texas, New Mexico, Georgia |
| Contoso | Maria Alvarez | Sales manager | Every territory |
| Contoso | Sam Rivera, Priya Nair, Grace Kim | Sales reps | Texas, New Mexico, Georgia |

## View as

`PERSONA_SWITCHER` is on by default in development with neither `TRUST_PROXY` nor `PUBLIC_ORIGIN`. It is a local
demo/testing aid for existing named sign-ins, not a production sign-in method or a feature limited to pilot customers.

How to use it:

1. Open a customer address, such as `http://fabrikam.localhost:3000` or `http://contoso.localhost:3000`.
2. On the sign-in page, choose one of that company's cards. The manager is first, followed by one rep for each
   territory. Password sign-in still works if you use the email and password from `pilot-logins.md`.
3. After sign-in, use **View as** in the top bar to switch to another person in the same company. An open report is
   discarded; Reports opens it with that person's new embed token. The assistant conversation and open account are
   cleared.
4. Use **Other companies** entries in the same menu to open another company's own address. A session works only at
   the address for its company.
5. Open `http://localhost:3000` to see the platform page with links to the companies.

| Company | Person | Email | Role | Sees | RLS role |
| --- | --- | --- | --- | --- | --- |
| Fabrikam | Leah Thompson | `leah.thompson@fabrikam.com` | Sales manager | Every state | `All territories` |
| Fabrikam | Drew Collins | `drew.collins@fabrikam.com` | Sales rep | Texas | `Texas` |
| Fabrikam | Arjun Mehta | `arjun.mehta@fabrikam.com` | Sales rep | New Mexico | `New Mexico` |
| Fabrikam | Amara Okoye | `amara.okoye@fabrikam.com` | Sales rep | Georgia | `Georgia` |
| Contoso | Maria Alvarez | `maria.alvarez@contoso.com` | Sales manager | Every state | `All territories` |
| Contoso | Sam Rivera | `sam.rivera@contoso.com` | Sales rep | Texas | `Texas` |
| Contoso | Priya Nair | `priya.nair@contoso.com` | Sales rep | New Mexico | `New Mexico` |
| Contoso | Grace Kim | `grace.kim@contoso.com` | Sales rep | Georgia | `Georgia` |

Safety rules:

- Production refuses `PERSONA_SWITCHER=true`.
- Outside safe local runs it is off by default, and it is refused if forced behind a proxy (`TRUST_PROXY`) or at a
  public address (`PUBLIC_ORIGIN`).
- It accepts only a loopback client address at a loopback or `*.localhost` host, and rejects `X-Forwarded-For`,
  `X-Forwarded-Host` and `Forwarded`.
- At a company's address, it signs in only that company's people. With no `APP_DOMAIN`, a shared local address can
  show every company's named sign-ins.
- State changes require the app's `x-platform-client: web` header.

## The story

1. **Fabrikam's address.**
   - Open `http://fabrikam.localhost:3000`. The page shows Fabrikam's logo and color, and asks you to sign in to
     Fabrikam.
   - Choose Leah's card, or sign in with her email and password. Home shows the whole pipeline.
2. **The standard report.**
   - Reports opens "Sales overview", the Power BI report embedded with an embed token that Fabrikam's service principal
     requested, for this report and its model only, with a default limit of 30 minutes, capped by the Entra token's
     expiry. The browser asks for a replacement before it expires.
   - It's view-only. Customers building their own reports is the next phase (`REPORT_AUTHORING`).
3. **The assistant.**
   - Ask "pipeline by state". In live mode on a supported paid capacity, Leah's question goes to Fabrikam's data agent
     through MCP. In demo mode, or when the agent is unavailable (as on the live trial), the CRM gives a quick answer.
   - A chart of the same question comes from the CRM data Leah may see.
   - Try "won revenue by month this year" for a line.
4. **A rep.**
   - Use **View as** to switch to Drew (Texas), or sign out and choose Drew's card. The CRM, the report and the
     assistant show Texas only.
   - Opening another territory's account answers "not found", even by ID.
   - Drew's questions get quick answers scoped to Texas, with charts, and never reach the data agent, which sees
     every territory.
5. **Access changes at once.**
   - In the back office, move Drew to New Mexico. His session ends, and when he signs in again he sees New Mexico.
6. **Another company.**
   - Open `http://contoso.localhost:3000`: a different logo and color.
   - Leah's Fabrikam password doesn't work there: same answer as a wrong password.
   - Fabrikam's session cookie is never sent to Contoso's address, and the server checks the pair too.
   - Choose Maria's card, or sign in with her email and password: Contoso's own data, numbers and report.
7. **The platform's address.**
   - `http://localhost:3000` asks only for a work email ("Find your company"), then sends you to your company's
     address.
8. **Behind the scenes, in the back office** (`http://localhost:3000/admin`, with the back-office key you gave or were shown at start). For each
   customer:
   - **Overview:** its address, workspace, service principal and provisioning steps.
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
