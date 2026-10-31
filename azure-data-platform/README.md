# Azure-Based Enterprise Data Engineering Platform

A simple, end-to-end base project implementing the **medallion architecture** on Azure:

```
 Source CSV ──► ADLS Gen2 (landing)
                    │   Azure Data Factory (orchestration, daily trigger)
                    ▼
              Databricks notebooks
        Bronze (raw Delta) ─► Silver (clean Delta) ─► Gold (Parquet aggregates)
                                                          │
                                                          ▼
                                            Synapse serverless SQL views ─► Power BI / SQL
```

| Layer | Service | Purpose |
|---|---|---|
| Storage | ADLS Gen2 | `landing`, `bronze`, `silver`, `gold` containers |
| Orchestration | Azure Data Factory | Runs the 3 notebooks in order, daily schedule |
| Processing | Azure Databricks (PySpark + Delta) | Ingest, clean, aggregate |
| Serving | Synapse serverless SQL | Views over Gold for BI |
| Security | Key Vault + Managed Identity + RBAC | No secrets in code |
| IaC | Bicep | One-command infra deployment |

## Project structure

```
azure-data-platform/
├── infra/main.bicep                 # Storage, ADF, Databricks, Synapse, Key Vault, RBAC
├── data/generate_sample_data.py     # Creates messy sample_sales.csv
├── src/
│   ├── transforms.py                # Bronze/Silver/Gold logic (pandas, testable)
│   ├── local_run.py                 # Run the whole pipeline locally, no Azure needed
│   └── upload_to_adls.py            # Upload raw files to the landing container
├── databricks/
│   ├── 01_bronze_ingest.py          # PySpark notebooks (same rules as transforms.py)
│   ├── 02_silver_transform.py
│   └── 03_gold_aggregate.py
├── adf/
│   ├── pipeline_sales_medallion.json
│   └── trigger_daily.json
├── synapse/create_views.sql
└── tests/test_transforms.py
```

## 1. Try it locally (no Azure account needed)

```bash
pip install -r requirements.txt
python data/generate_sample_data.py     # creates data/sample_sales.csv
python src/local_run.py                 # writes ./local_lake/{bronze,silver,gold}
pytest -q                               # unit tests for the business rules
```

## 2. Deploy to Azure

```bash
az login
az group create -n rg-dataplatform-dev -l centralindia
az deployment group create -g rg-dataplatform-dev -f infra/main.bicep \
    -p sqlAdminPassword='<StrongPassword!>'
```

Note the `storageAccountName` output, then:

1. **Service principal for Databricks -> ADLS:** create an app registration, grant it
   *Storage Blob Data Contributor* on the storage account, store `sp-client-id`,
   `sp-client-secret`, `sp-tenant-id` in Key Vault, and create a Databricks
   Key Vault-backed secret scope named `kv-data-platform`.
2. **Import notebooks** from `databricks/` into the workspace at `/Shared/data-platform/`.
3. **ADF:** create a linked service `ls_databricks` (access token or managed identity),
   then import `adf/pipeline_sales_medallion.json` and `adf/trigger_daily.json`.
4. **Upload data:**
   ```bash
   cp .env.example .env     # set AZURE_STORAGE_ACCOUNT
   python src/upload_to_adls.py --file data/sample_sales.csv
   ```
5. **Run** the `pl_sales_medallion` pipeline in ADF (parameter `storage_account`).
6. **Serve:** open `synapse/create_views.sql` in Synapse Studio (serverless pool), replace
   `<storage_account>`, run it, then connect Power BI to the `sales_dw` database.

## Data-quality rules (Silver)

- Trim/standardise `country` (upper) and `status` (lower)
- Drop rows with null `order_id`, `customer_id`, invalid date, or non-positive quantity/price
- De-duplicate on `order_id` (keep latest ingested)
- Derive `total_amount = quantity * unit_price`

## Gold tables

- `daily_sales` - orders and revenue per day
- `sales_by_category` - units and revenue per category and country
- `top_customers` - top 10 customers by lifetime value
(All exclude `cancelled` orders.)

## Ideas to extend

Delta Lake `MERGE` for incremental upserts, Auto Loader for streaming ingestion,
Great Expectations / Delta constraints for quality checks, Unity Catalog for governance,
CI/CD with GitHub Actions (`pytest` + `az deployment group what-if`), Azure Monitor alerts on ADF failures.
