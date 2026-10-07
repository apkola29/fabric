# HiCRM: a multitenant SaaS app on Microsoft Fabric

A framework for multitenant applications on Microsoft Fabric, and a working sample built on it. The sample, **HiCRM**,
is a CRM sold as SaaS, with Fabric doing the data work behind the scenes. Every customer company gets its own Fabric
workspace, run through its own service principal that can reach nothing else, and its own address, logo and
sign-ins. The customers' people only ever see HiCRM:

- their accounts, opportunities and activities, in a SQL database in Fabric;
- a standard Power BI report, embedded ("app owns data") and filtered to their territories by row-level security;
- an assistant that answers questions about their data, through the customer's Fabric data agent and its MCP server.

They need no Microsoft Entra account and no Power BI license.

> **Disclaimer.** This is a sample for learning and experimentation, provided as-is with no warranty. Review it before
> using it for real customers ([MULTITENANCY.md](MULTITENANCY.md), section 5, lists what's left for production).

## What it shows

| Area | How |
| --- | --- |
| Isolation | One workspace per customer, and one service principal per customer that is Admin of that workspace only. A bug that mixes up customers meets a refusal from Fabric |
| Credentials | Federated credentials (a managed identity) or certificates, through MSAL. Nothing secret in the project: whatever is secret is asked for at runtime |
| Embedded reports | Generate Token V2 on the server, short-lived, with each person's row-level security roles; refreshed in the browser before they expire |
| Row-level security | Direct Lake with a fixed identity; static roles per territory; checked in a real browser, including that a report filter can't widen what a person sees |
| AI | The customer's data agent over MCP, called as the customer's service principal |
| Least privilege | The platform identity builds each workspace, hands it over and keeps no access |
| Proof | 34 controls ([FRAMEWORK.md](FRAMEWORK.md)), checked by `npm test`, by a validator against the Fabric emulator, and against a live deployment |

## Quick start: demo mode (no Azure needed)

Node.js 22.9 or later (24 recommended).

```powershell
npm install
npm run setup -- --mode demo --yes    # two customers, Fabrikam and Contoso, with four people each
npm start
```

Everything runs on your computer against a Fabric emulator that enforces workspace roles like Fabric does. The setup
prints each person's sign-in (also saved to `pilot-logins.md` in the data folder, outside the project). Then open:

- Fabrikam: http://fabrikam.localhost:3000
- Contoso: http://contoso.localhost:3000
- The back office: http://localhost:3000/admin

[PILOT.md](PILOT.md) walks through the story: a manager and a rep see different numbers in the same report, and the
assistant answers in each customer's own data.

## Run it on Microsoft Fabric

1. **Read [REQUIREMENTS.md](REQUIREMENTS.md).** It lists the roles needed and what each is for, the identities, the
   tenant settings, the capacity, and the exact rules for each customer's workspace.
2. **Create the identities** (an Entra admin):
   - the platform app registration, with a certificate (REQUIREMENTS.md, section 8, step 4);
   - one service account per customer, with a certificate, made Admin of the customer's workspace and registered with
     the platform:
     ```powershell
     az login --tenant <tenant-id>
     ./scripts/bootstrap-identities.ps1 -Customer Fabrikam -WorkspaceId <workspace-id> -Register
     ```
3. **Set up:** `npm run setup` asks for the tenant, the platform app and its certificate, and the capacity, then builds the
   customers: database, semantic models, report, data agent. Only non-secret settings go into `.env`.
4. **Start:** `npm start` asks for what it needs and keeps none of it:

   | You're asked for | Unless the environment provides it |
   | --- | --- |
   | The platform identity's certificate (a PEM file path) or, for development, its client secret | `AZURE_CLIENT_CERTIFICATE_PATH`, or `MANAGED_IDENTITY_CLIENT_ID` (nothing secret) |
   | The key to the customers' stored credentials | `SECRETS_KEY`, or Key Vault (`SECRETS_PROVIDER=keyvault`) |
   | A back-office key (or press Enter to make one for the run) | `ADMIN_KEY` |

5. **Validate:** `npm run validate -- --live --browser` checks every control against the deployment, read-only, including
   what each person sees in the report.

In production (`APP_ENV=production`), the app refuses settings that are only safe on a laptop: a client secret for the
platform identity, a shared identity for customer work, standing platform access to customer workspaces, credentials
outside Key Vault, or a back office without sign-in. [.env.example](.env.example) explains every setting, and
[DEPLOYMENT-ARCHITECTURES.md](DEPLOYMENT-ARCHITECTURES.md) three ways to host it.

**Licenses and capacity.** Service principals and the customers' people need no license. You need a Fabric F capacity
(F2 or larger for the data agent); a trial capacity runs everything else. On a trial, the data agent refuses with
`FT1 SKU Not Supported`, and the assistant answers managers from the CRM database instead.

## Operate it from the command line

```powershell
npm run cli -- --help
npm run cli -- add Fabrikam --plan enterprise --domain fabrikam.com
npm run cli -- status Fabrikam      # steps, service account and how it signs in, Fabric IDs
npm run cli -- audit Fabrikam       # least-privilege and drift check (exit code 1 on failures)
npm run cli -- crm Fabrikam         # CRM row counts and headline numbers
npm run cli -- model Fabrikam       # model version, connection binding, refreshes
npm run cli -- ask Fabrikam "win rate by sales rep this year"
npm run cli -- questions Fabrikam   # what people asked the assistant, the answers, and who answered
npm run cli -- usage Fabrikam       # who opened which reports, load and render times, token IDs
npm run cli -- user-access Fabrikam leah.thompson@fabrikam.com --reports edit   # report rights
npm run cli -- identity-register Fabrikam --app-id <id> --object-id <id> --certificate-file <pem>
npm run cli -- brand Fabrikam --logo logo.svg --color "#a8431c"
npm run cli -- provision Fabrikam   # idempotent; also how upgrades ship
```

The tenant registry is a JSON file with one writer: run commands that change data while the server is stopped, or use
the back office.

## Test it

```powershell
npm test
```

163 tests run in about three minutes, in-process, against the Fabric emulator: no network, no credentials. They cover:
- isolation: no customer's work can reach another customer's workspace, and the platform keeps no more access than it
  needs (`test/isolation.test.js`); sessions only work at their own customer's address (`test/tenancy.test.js`);
- credentials: certificate assertions (PS256, `x5t#S256`), federated credentials, typed credential storage, and the
  runtime prompts (`test/credential-types.test.js`, `test/runtime-secrets.test.js`, `test/identities.test.js`);
- embedding: token scope, lifetime and refresh, per-person report rights, the usage log;
- row-level security: roles in the model and in every token, and no measure that breaks under row-level security;
- robustness: failures injected at every provisioning step, 20 customers side by side, rate limits, the production
  profile and security headers (`test/robustness.test.js`);
- the framework: the core reaches HiCRM only through its workload contract, FRAMEWORK.md and the validator agree
  (`test/framework.test.js`), and the project holds no credentials (`test/publishing.test.js`).

## Validate it

```powershell
npm run validate                          # the framework's controls against two emulated tenants (no Azure)
npm run validate -- --live --browser      # against this deployment, read-only; opens the report as each person
```

The validator checks each control in [FRAMEWORK.md](FRAMEWORK.md#6-controls) and prints the evidence: each tenant's
service principal sees only its own workspace and is refused everywhere else (including the other tenant's SQL
database and data agent); the platform identity is refused too; embed tokens are scoped, short-lived and carry each
person's roles; the rendered report shows each person only their rows, matching the database, even with a report
filter asking for every territory. It exits with code 1 when a control fails.

## Before you publish

```powershell
npm run check:publish              # credentials anywhere, and this deployment's IDs (from the registry and .env)
npm run check:publish -- --fix     # replace those IDs with placeholders such as <fabrikam-workspace-id>
```

`.env`, the data folder and certificate files are ignored by git; `test/publishing.test.js` keeps credentials out of
the project in CI.

## Documentation

| Document | What's in it |
| --- | --- |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Roles and what they're for, identities, credentials, tenant settings, workspace rules, a checklist |
| [FRAMEWORK.md](FRAMEWORK.md) | The framework: principles, reference architecture, building blocks, design decisions, 34 controls, validation |
| [EMBEDDING.md](EMBEDDING.md) | How the embedded reports work: every credential, the token request, row-level security, refresh, best practices, and a comparison with Microsoft's App-Owns-Data samples |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diagrams of the system, identities, provisioning and the runtime flows |
| [MULTITENANCY.md](MULTITENANCY.md) | The multitenancy, least-privilege and robustness review, with evidence |
| [BUILDOUT.md](BUILDOUT.md) | How the pilot was built: identities and their counts, permissions, and the as-built record |
| [PILOT.md](PILOT.md) | The two pilot customers and the story to walk through |
| [DEPLOYMENT-ARCHITECTURES.md](DEPLOYMENT-ARCHITECTURES.md) | Hosting plans: hybrid, Azure, and on-premises |
| [REPORT-SPEC.md](REPORT-SPEC.md) | A specification for a fuller sales report |
| [PLAN.md](PLAN.md) | Decisions, phases and every finding with its evidence |

## Code map

| Path | What it does |
| --- | --- |
| `src/auth/tokens.js` | Microsoft Entra tokens through MSAL Node: per identity and scope, cached, long enough for embed tokens |
| `src/auth/credential-types.js`, `certificates.js` | Credential types (federated, certificate, secret), certificate bundles and self-signed certificates |
| `src/auth/runtime-secrets.js` | Asks for credentials at start (hidden input) instead of reading them from files |
| `src/platform/identities.js`, `secrets.js` | One service account per customer, its credential, and the encrypted credential store or Key Vault |
| `src/platform/provisioner.js` | Idempotent provisioning steps, hand-over and release, upgrades and removal |
| `src/platform/reporting.js`, `usage.js` | Generate Token V2 with effective identities and per-person rights; the report usage log |
| `src/platform/assistant.js`, `agent.js`, `src/fabric/mcp.js` | The data agent over MCP, quick answers scoped to territories, the question log |
| `src/platform/audit.js`, `validation.js`, `browser.js` | Drift audit, the framework's controls, the validator and its browser check of row-level security |
| `src/platform/tenancy.js`, `branding.js`, `sessions.js`, `operators.js` | Each customer's address, logo and color; sessions; back-office sign-in |
| `src/fabric/client.js`, `mock.js` | Fabric, Power BI and OneLake REST client (throttling, long-running operations), and the role-enforcing emulator |
| `src/crm/` | HiCRM itself: schema, semantic model and roles, starter report, data access, sample data. `workload.js` is all the framework uses |
| `src/routes/`, `public/` | The customer and back-office APIs; the HiCRM app and the back office |
| `src/util/publishing.js`, `scripts/check-publish.js` | The pre-publish check for credentials and environment IDs |
| `scripts/` | Setup, CLI, identity bootstrap, preflight check and validator |

## License

MIT, as the rest of [this repository](../LICENSE).
