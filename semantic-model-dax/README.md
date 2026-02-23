# Fabric Semantic Model - DAX Query Client

Interactive client to list semantic models (datasets) in a Fabric / Power BI workspace and run DAX queries against them using the Power BI REST API.

Supports two authentication methods:
- **Service Principal (SPN)** -- headless, for automation and CI
- **Interactive Browser** -- user login with MFA support

## Prerequisites

- **Python 3.10+**
- A Fabric workspace with at least one **Semantic Model** (dataset)

### Permissions

| Capability | Permission Required |
|---|---|
| List semantic models | **Viewer** (or higher) role on the workspace |
| Execute DAX queries | **Build** permission on the specific semantic model |

To grant Build permission:
> Fabric portal > Semantic Model > **Manage permissions** > Add user/SPN > **Build**

## Setup

```bash
cd semantic-model-dax
pip install -r requirements.txt
```

> **Note:** `azure-identity` is only needed for interactive browser auth. If using SPN auth only, `requests` is sufficient.

## Usage

```bash
python dax_query.py
```

### Step 1 -- Choose auth method

```
Authentication method:
  1. Service Principal (SPN)
  2. Interactive Browser (MFA)

  Select [1/2]:
```

**SPN** prompts for Tenant ID, Client ID, and Client Secret.
**Interactive** opens a browser window for Microsoft login (supports MFA).

### Step 2 -- List semantic models

```
Semantic Models in Workspace
------------------------------------------------------------
  1. sales_model  (ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
  2. hr_model     (ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

  Select model [1-2]:
```

### Step 3 -- Run DAX queries

```
  Dataset: sales_model
  Enter DAX queries below. Type 'quit' to stop.
  Example: EVALUATE TOPN(10, 'TableName')

DAX> EVALUATE TOPN(5, 'Products')
  Columns: ProductID, ProductName, Category, Price
  Rows: 5

    1 | Widget A | Electronics | 29.99
    2 | Widget B | Electronics | 49.99
    ...

DAX> EVALUATE ROW("Total", COUNTROWS('Orders'))
  Columns: Total
  Rows: 1

    1250
```

## API Reference

| Operation | Method | Endpoint |
|---|---|---|
| List datasets | `GET` | `https://api.powerbi.com/v1.0/myorg/groups/{workspaceId}/datasets` |
| Execute DAX | `POST` | `https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/executeQueries` |

### DAX Query Request Body

```json
{
  "queries": [
    { "query": "EVALUATE TOPN(10, 'TableName')" }
  ]
}
```

Docs:
- [Execute Queries](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/execute-queries)
- [List Datasets in Group](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/get-datasets-in-group)

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` on token | Bad SPN credentials | Verify Client ID/Secret in Azure portal |
| `PowerBINotAuthorizedException` on DAX | Missing Build permission | Grant Build permission on the semantic model |
| `403 Forbidden` on list | No workspace access | Grant Viewer (or higher) role on the workspace |
| No datasets found | Workspace has no semantic models | Verify the workspace ID and that models exist |
| `azure-identity` import error | Package not installed | Run `pip install azure-identity` |
