# Requirements: roles, identities, credentials and workspace rules

What has to exist before HiCRM runs against Microsoft Fabric, who creates it, and why. Use it as the checklist for
setting up an environment: each table says which role does what, and section 5 says exactly what goes into each
customer's workspace.

**Who's who.** "You" is the provider that runs the platform: HiCRM in the sample. "Customers" are the companies that
subscribe, such as Fabrikam and Contoso; they need none of this ([README.md](README.md#whos-who)).

**Demo mode needs none of this.** `npm install`, `npm run setup -- --mode demo --yes` and `npm start` run everything on
your computer against a Fabric emulator: no Azure, no credentials.

| Section | Covers |
| --- | --- |
| [1. People and the roles they need](#1-people-and-the-roles-they-need) | Who does what, once or per customer |
| [2. Identities](#2-identities) | The service principals, workspace identities and groups, and their permissions |
| [3. Credentials](#3-credentials) | What is secret, and how it's given at runtime (never in a file) |
| [4. Tenant settings](#4-tenant-settings) | The Fabric admin portal switches |
| [5. Workspace rules](#5-workspace-rules) | One workspace per customer: roles, items, capacity |
| [6. Capacity and licenses](#6-capacity-and-licenses) | SKUs, and who needs a license (nobody, to view) |
| [7. Software](#7-software) | What the operator's computer needs |
| [8. Checklist](#8-checklist) | In order, from an empty tenant to a running customer |

## 1. People and the roles they need

| Role | Where it's granted | Needed for | When | Not needed if |
| --- | --- | --- | --- | --- |
| **Application Administrator** (or Cloud Application Administrator) | Microsoft Entra ID | Creating the platform app registration and one service account per customer, and giving them a certificate or a federated credential (`scripts/bootstrap-identities.ps1`) | Once, then once per customer | The platform creates service accounts itself (next row) |
| **Privileged Role Administrator** (or Global Administrator) | Microsoft Entra ID | Granting the platform app the Microsoft Graph application permission `Application.ReadWrite.OwnedBy`, so it creates (and can only manage) its own service accounts | Once, optional | An admin creates each customer's service account |
| **Groups Administrator** (or the group's owner) | Microsoft Entra ID | A security group holding the platform identity and every service account, so the tenant settings in section 4 apply to them only | Once, recommended | You accept the settings for the whole organization (the validator warns, IDN-06) |
| **Fabric Administrator** | Microsoft Entra ID role, used in the Fabric admin portal | The tenant settings in section 4 | Once | They're already on for the group |
| **Capacity administrator** | The Fabric capacity | Making the platform identity Contributor on the capacity, so it can create customer workspaces and assign them to it | Once per capacity | An admin creates each workspace and the platform adopts it (section 5) |
| **Workspace creator** (a person with Contributor on the capacity) | The Fabric capacity | Creating a customer's workspace and adding the customer's service account and the platform identity as Admin, when the platform can't create workspaces. Remove yourself afterwards (IDN-04) | Per customer, optional | The platform identity is Contributor on the capacity |
| **Operator** | HiCRM back office (`/admin`) | Running the setup, adding customers and people, support. No Entra or Fabric role | Ongoing | |
| **Report author** | Power BI Pro or Premium Per User license, Contributor on the workspace | Building report pages in the Fabric portal, for example with Copilot | Optional | Customers use the standard report |
| **Azure contributor** | An Azure subscription or resource group | Production hosting: App Service or Container Apps, the user-assigned managed identity, Key Vault (with the Key Vault Secrets Officer role for the managed identity) | Production | Running on your own computer |

In a pilot, one person can hold every role. In production, separate them: no single person should be able to both change
the tenant settings and create credentials.

### Only if a customer opts in

Letting a customer's people sign in with their work accounts, and the data integration add-on, need roles in the
**customer's** Entra tenant too. The customer's own admins act; you never hold these roles
([IDENTITIES.md](IDENTITIES.md#6-who-does-what-on-each-side)).

| Role | Where | Needed for |
| --- | --- | --- |
| **Cloud Application Administrator** or **Application Administrator** | The customer's Entra tenant | Admitting your sign-in app (admin consent) and assigning people to Manager and Rep; admitting the customer's reader (`<customer>reader`), which asks for no API permissions |
| **Owner**, **User Access Administrator** or **Role Based Access Control Administrator** | The customer's storage account | Giving the reader's service principal Storage Blob Data Reader on one container |
| The server's **Microsoft Entra admin** | The customer's Azure SQL database | A database user for the reader, with `SELECT` |
| **System Administrator** | The customer's Dataverse environment | The reader as an application user with a read-only security role |
| **Fabric Administrator**, then someone with Read and Reshare on the item | The customer's Fabric | Turning on External data sharing, and sharing named tables to the customer's service account |
| The customer's IT | The customer's network | An on-premises data gateway, and read-only accounts in the source systems |
| One of your engineers, with an account in your tenant | Your Entra tenant | Registering that gateway to your tenant, which needs a person's account |

## 2. Identities

| Identity | Kind | Created by | How it signs in | Permissions | Count |
| --- | --- | --- | --- | --- | --- |
| **Platform identity** (control plane) | App registration and service principal | An Entra admin | Development: a certificate (or a client secret), asked for at start. Production: a federated credential trusting the app's managed identity | Fabric APIs (tenant setting); Contributor on the capacity; Admin of a customer workspace only until it hands it over. Optional: `Application.ReadWrite.OwnedBy` in Microsoft Graph | 1 |
| **Customer service account** `<customer>sa`, for example `fabrikamsa` | App registration and service principal, in **your** Entra tenant, not the customer's | An Entra admin (`bootstrap-identities.ps1`), or the platform with `Application.ReadWrite.OwnedBy` | A certificate (default) kept encrypted by the platform, or a federated credential trusting the app's managed identity | Admin of that customer's workspace, and nothing else | 1 per customer |
| **Workspace identity** | Fabric-managed service principal; nobody holds its secret | Fabric, when provisioning asks for it | Fabric | Contributor of its own workspace; the semantic models read OneLake as it | 1 per customer |
| **User-assigned managed identity** | Azure managed identity | An Azure contributor | Azure | Nothing in Fabric itself: the platform app and the service accounts trust it (federated identity credentials), and it reads Key Vault | 1, production |
| **Security group for service principals** | Entra security group | Groups Administrator | | Scopes the tenant settings to HiCRM's identities | 1, recommended |
| **Support group** | Entra security group (`FABRIC_OPS_PRINCIPAL_ID`) | Groups Administrator | | Viewer of every customer workspace | 0 or 1 |
| **Sign-in app** (only for work-account sign-in) | Multi-tenant app registration, with a service principal in each customer tenant that admits it | An Entra admin, once | A certificate, or a federated credential trusting the app's managed identity | Sign-in only (`openid`, `profile`, `email`), and the app roles Manager and Rep | 0 or 1 |
| **Customer reader** `<customer>reader`, for example `fabrikamreader` (only for the add-on) | Multi-tenant app registration, with a service principal in that customer's tenant only. The customer's connections to its own systems sign in as it | The platform, or an Entra admin | A client secret held only by that customer's Fabric connections, which take a secret for a service principal | What the customer grants that service principal in its own tenant, read-only; nothing in yours | 1 per customer with the add-on |

The customers' own people need **no** Entra account and **no** Power BI license: they sign in to HiCRM, and the
platform embeds reports for them with tokens it creates ("app owns data"). A customer can instead let its people sign
in with their own work accounts; they still get nothing in your tenant ([IDENTITIES.md](IDENTITIES.md)).

Why one service account per customer: every call made for a customer runs as that customer's service account, which
can reach only that customer's workspace. A bug that mixes up customers meets a refusal from Fabric, not another
customer's data ([MULTITENANCY.md](MULTITENANCY.md)).

## 3. Credentials

Nothing secret is kept in the project, in `.env` or in the tenant registry. Whatever is secret is **asked for when the
app starts** (`npm start`, `npm run setup`, the CLI and the validator), with hidden input, and used for that run only.
Without a terminal (a hosted app, CI) it comes from the environment instead, and in production there is ideally nothing
secret at all.

| Credential | Unlocks | Development (on your computer) | Production |
| --- | --- | --- | --- |
| Platform identity's certificate or client secret | The control plane | Asked for at start: a PEM file path (recommended) or a client secret. `AZURE_CLIENT_CERTIFICATE_PATH` can remember the path | None: `MANAGED_IDENTITY_CLIENT_ID`, the platform app trusting the app's managed identity. Production refuses client secrets |
| Each customer service account's credential | That customer's workspace | A certificate the bootstrap script creates (or the platform, in auto-create mode), stored encrypted in the data folder; the clear-text file is deleted | None: a federated credential trusting the app's managed identity. Or a certificate in Key Vault |
| `SECRETS_KEY` | The data folder's encrypted credential store | Asked for at start; you choose it the first time | Not used: `SECRETS_PROVIDER=keyvault` |
| `ADMIN_KEY` | The back office (`/admin`) | Asked for at start, or made for the run and shown once | From the hosting platform's settings (a Key Vault reference); better, sign operators in with Entra ID |
| `SESSION_SECRET` | Customer sign-in cookies | Made at each start (sign-ins end when the server stops) | From the hosting platform's settings, shared by every instance |
| Customer people's passwords | The CRM app | Made by `npm run setup`, shown once and kept in `pilot-logins.md` in the data folder, outside the project | Your identity provider, for example Microsoft Entra External ID |

Credential types, best first, as Microsoft recommends: a **federated credential** (nothing to store, leak or rotate),
then a **certificate** ("We recommend that you secure your back-end services by using certificates, rather than secret
keys", [Embed with a service principal](https://learn.microsoft.com/power-bi/developer/embedded/embed-service-principal)),
then a **client secret** for development only. Tokens are acquired with MSAL Node; certificate assertions are signed
PS256 with an `x5t#S256` header and live 10 minutes.

## 4. Tenant settings

In the Fabric admin portal (Tenant settings), by a Fabric Administrator. Apply each to the security group from section 2
rather than the whole organization.

| Setting | Section | Needed for |
| --- | --- | --- |
| Service principals can call Fabric public APIs | Developer | Every Fabric and Power BI call by the platform identity and the service accounts |
| Service principals can create workspaces, connections, and deployment pipelines | Developer | Creating customer workspaces (platform identity) and each model's cloud connection (service account) |
| Embed content in apps | Developer | Embed tokens for the customers' people |
| Users can use Copilot and other features powered by Azure OpenAI | Copilot and Azure OpenAI Service | The data agent |
| Data sent to Azure OpenAI can be processed outside your capacity's geographic region | Copilot and Azure OpenAI Service | Only when the capacity is outside the US and the EU Data Boundary |
| Service principals can access read-only admin APIs | Admin API settings | Optional: lets the validator read these settings (IDN-06). Allow it for a group holding only the platform identity |
| Service principals can access admin APIs used for updates | Admin API settings | Never for HiCRM's identities |
| Users can accept external data shares | Export and sharing settings | Only for the data integration add-on, when a customer shares data from its own Fabric. Allow it for the service accounts' group only |

## 5. Workspace rules

Every customer gets exactly this, and nothing else. Provisioning creates it and the validator checks it
(`npm run validate -- --live`); an admin can also create the workspace by hand and let the platform adopt it.

**The workspace**

| Rule | Value |
| --- | --- |
| How many | One per customer. Customers never share a workspace, a model or a connection |
| Name | `saas-<customer>-<short id>` when the platform creates it (prefix `FABRIC_WORKSPACE_PREFIX`); any name when an admin creates it and the platform adopts it |
| Capacity | A Fabric F capacity (F2 or larger for the data agent), or a trial for development. Choose the region for the customer's data residency: items can't move across regions |
| Workspace identity | On (provisioning turns it on) |

**Who has which role in it**

| Principal | Role | Why |
| --- | --- | --- |
| The customer's service account | **Admin** | Every call for this customer runs as it; Admin lets it hand the workspace over and take it back |
| The workspace identity | **Contributor** | The semantic models read OneLake as it (Direct Lake needs read access to the data) |
| The platform identity | **None** after the hand-over (`PLATFORM_WORKSPACE_ACCESS=release`); Admin only while it builds the workspace | Least privilege: it keeps no standing access to any customer |
| The support group | Viewer, optional | Read-only troubleshooting in the Fabric portal |
| People | **None**. If you need break-glass access, use a group that people join through Privileged Identity Management | Nobody should be able to read a customer's data outside the app (IDN-04) |

**What's in it** (built by provisioning, from code)

| Item | Name | What it's for |
| --- | --- | --- |
| SQL database | `hicrm_db` | The customer's CRM data; replicated to OneLake automatically |
| Semantic model | `HiCRM Insights` | Direct Lake on OneLake, with one row-level security role per territory; every embedded report reads it |
| Semantic model | `HiCRM Insights - Assistant` | The same model without roles, for the data agent only (service principals can't query a model with roles) |
| Report | `Sales overview` | The standard report every person sees, filtered to their territories |
| Data agent | `HiCRM Assistant` | Answers managers' questions over its MCP endpoint |
| Lakehouse, warehouse | Optional | The data integration add-on |

**Outside the workspace:** one cloud connection per customer, owned by the customer's service account, that signs in as
the workspace identity with single sign-on off. The semantic models are bound to it ("fixed identity"), so Direct Lake
reads data without any person's credentials, and row-level security comes only from the embed token.

**Creating a workspace by hand** (when the platform identity can't create workspaces): create a workspace for the
customer on the capacity, add the customer's service account and the platform identity as Admin, then
`npm run setup -- --workspace <Customer>=<workspace-id>` adopts it. Provisioning does the rest, then removes the
platform identity's role. Remove your own access afterwards.

## 6. Capacity and licenses

| What | Needed |
| --- | --- |
| Capacity | An F SKU. F2 or larger for the data agent and its code interpreter; a trial capacity runs everything else |
| Licenses for the customers' people | None ("app owns data") |
| Licenses for the service principals | None |
| Pro or Premium Per User | Only for people who author in the Fabric portal |

## 7. Software

| Where | What |
| --- | --- |
| The operator's computer | Node.js 22.9 or later (24 recommended); `npm install` |
| Creating identities | The Azure CLI (`az login`) and PowerShell (Windows PowerShell 5.1 or PowerShell 7) for `scripts/bootstrap-identities.ps1` |
| Browser validation | Microsoft Edge or Google Chrome (`npm run validate -- --live --browser`) |
| Production hosting | See [DEPLOYMENT-ARCHITECTURES.md](DEPLOYMENT-ARCHITECTURES.md) |

## 8. Checklist

1. **Capacity:** an F capacity (or a trial for development) in the region you need.
2. **Security group** for HiCRM's service principals (Groups Administrator).
3. **Tenant settings** from section 4, applied to that group (Fabric Administrator).
4. **Platform identity:** an app registration with a certificate (Application Administrator):
   ```powershell
   az ad app create --display-name "HiCRM platform"          # note the appId
   az ad sp create --id <appId>
   az ad app credential reset --id <appId> --create-cert --append --years 1   # prints the PEM file's path
   ```
   Move the PEM file outside the project, and add the service principal to the group from step 2.
5. **Capacity access:** make the platform identity Contributor on the capacity (capacity administrator), or plan to
   create each customer's workspace by hand (section 5).
6. **Per customer:** the service account, with a certificate, made Admin of the customer's workspace and registered with
   the platform (Application Administrator):
   ```powershell
   ./scripts/bootstrap-identities.ps1 -Customer Fabrikam -WorkspaceId <workspace-id> -Register
   ```
   Or let the platform create them: `-GrantPlatformAppCreation` once (Privileged Role Administrator), then
   `TENANT_IDENTITY_AUTO_CREATE=true`.
7. **Setup:** `npm run setup` asks for the tenant, the platform app, its certificate and the capacity, then builds the
   customers. It writes only non-secret settings to `.env`.
8. **Run:** `npm start` asks for the credentials it needs, then prints each customer's address.
9. **Validate:** `npm run validate -- --live --browser` checks every control in [FRAMEWORK.md](FRAMEWORK.md) against the
   deployment, read-only, including what each person sees in the report.
