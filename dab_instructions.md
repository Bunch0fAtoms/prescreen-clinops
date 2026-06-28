# DAB Deployment Instructions — Fred Hutch Clinical Trial Pre-Screening

## Prerequisites

- Databricks CLI installed (`pip install databricks-cli` or `brew install databricks`)
- Authenticated: `databricks auth login --host https://<your-workspace>.cloud.databricks.com`
- Unity Catalog enabled with `CREATE SCHEMA` privilege on your target catalog
- A running SQL Warehouse (serverless or pro)

## Quick Start

```bash
# 1. Edit databricks.yml — set your workspace values under targets.client.variables:
#    client_catalog:  <your Unity Catalog catalog>
#    client_schema:   <your target schema name>
#    warehouse_id:    <your SQL Warehouse ID>

# 2. Validate the bundle
databricks bundle validate --target client

# 3. Deploy
databricks bundle deploy --target client

# 4. Run the synthetic data generator (creates all 6 OMOP tables)
databricks bundle run data_generation_job --target client
```

## Bundle Variables

| Variable | Default | Description |
|---|---|---|
| `run_with_synthetic_data` | `yes` | `yes` = generate synthetic OMOP data; `no` = read from `source_catalog.source_schema` |
| `source_catalog` | `curated_omop` | Your real OMOP source catalog (only used when `run_with_synthetic_data=no`) |
| `source_schema` | `omop` | Your real OMOP source schema (only used when `run_with_synthetic_data=no`) |
| `client_catalog` | `<your_catalog>` | Catalog where demo tables are created |
| `client_schema` | `<your_schema>` | Schema where demo tables are created |
| `warehouse_id` | `<your_warehouse_id>` | SQL Warehouse ID |

## Resources Deployed

| Resource | Type | Description |
|---|---|---|
| `data_generation_job` | Databricks Job | Generates 300 synthetic OMOP patients into 6 tables |

## What Gets Created

After `bundle deploy` + `bundle run data_generation_job`:

- `<client_catalog>.<client_schema>.person` — 300 patients
- `<client_catalog>.<client_schema>.condition_occurrence` — breast cancer diagnoses
- `<client_catalog>.<client_schema>.measurement` — ER/PR/HER2 structured biomarkers
- `<client_catalog>.<client_schema>.observation` — menopausal status + AJCC stage
- `<client_catalog>.<client_schema>.drug_exposure` — prior therapy including anti-HER2 drugs
- `<client_catalog>.<client_schema>.note` — free-text pathology reports

## Switching to Real OMOP Data

1. In `databricks.yml`, set `run_with_synthetic_data: "no"` under `targets.client.variables`.
2. Set `source_catalog` and `source_schema` to your real OMOP catalog/schema.
3. Run `databricks bundle deploy --target client` (no need to re-run the data generation job).
4. Downstream tools (Genie, Genie Code) now read from your real tables — no query changes needed.

## Talking Track Resources (not owned by this bundle)

The following are **not deployed by `bundle deploy`** — they are demonstration components that the SA creates separately for the full demo experience:

- **AI/BI Genie space** — structured cohort queries over `measurement`, `condition_occurrence`, `person`
- **Genie Code** — NLP/LLM biomarker extraction from `note.note_text`
- **MLflow evaluation run** — scores NLP extraction accuracy using `both-agree` patients as ground truth

## Troubleshooting

| Error | Fix |
|---|---|
| `variable not defined: client_catalog` | Update `targets.client.variables` in `databricks.yml` |
| `SCHEMA_NOT_FOUND` | Run with `CREATE SCHEMA` privilege on `client_catalog` |
| `Permission denied` on catalog | Request `USE CATALOG` + `CREATE SCHEMA` from your admin |
| Job fails with `ModuleNotFoundError` | The job uses serverless env `client: "2"` with Faker/Numpy/Pandas — check if serverless is enabled |
| `python_script_task` warning during validate | Schema warning only; functional at runtime. Ignore. |
