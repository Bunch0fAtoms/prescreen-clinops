# Coordinator Pre-Screening App

A Streamlit app for a research coordinator. Pick a breast-cancer trial and see
which patients are eligible, the plain-English reason each patient qualifies,
and a data-provenance badge on every patient.

The provenance badge is the point of the whole solution. Some patients are
eligible only because natural language processing (NLP) recovered a biomarker
from a clinical note. Structured lab and pathology data alone would have missed
them. The app makes that uplift visible: it shows how many patients structured
data would have found, and how many more NLP recovered.

## What the app does

- **Trial selector** in the sidebar. Trial A is HER2+, Trial B is
  ER+/HER2-/postmenopausal, Trial C is triple-negative.
- **Header metrics** for the selected trial: total eligible, the count recovered
  only via NLP, and the structured-only baseline, framed as an uplift.
- **Eligible-patient table** with person ID, age, HER2/ER/PR status, menopausal
  status, the eligibility reason, and a provenance badge. Green means the
  biomarker came from structured data. Amber means NLP recovered it from a note.
- **Patient drill-down.** Pick a person ID and see that patient's test timeline.

## Tables it reads

Both tables live in `{CLINOPS_CATALOG}.{CLINOPS_SCHEMA}` and are built by the
notebooks in this kit.

1. `gold_trial_prescreen_wide`, one row per patient. Holds demographics,
   biomarker status, the `biomarker_source` provenance column (`structured` or
   `nlp`), and per-trial eligibility (`trial_a_eligible` / `trial_a_reason`, and
   the same for trials B and C).
2. `gold_patient_measurements`, a longitudinal per-patient test timeline, used
   for the drill-down. Columns: `person_id`, `measurement_date`, `test_name`,
   `value`, `unit`.

## Configure the environment variables

The app reads three environment variables. They are declared in `app.yaml` with
placeholder values.

| Variable | What it is | Example |
| --- | --- | --- |
| `CLINOPS_CATALOG` | Unity Catalog (UC) catalog holding the gold tables | `my_team_catalog` |
| `CLINOPS_SCHEMA` | Schema inside that catalog | `clinops_ml` |
| `DATABRICKS_WAREHOUSE_HTTP_PATH` | HTTP path of the SQL warehouse to query | `/sql/1.0/warehouses/abc123` |

Find the warehouse HTTP path in the SQL warehouse's Connection details tab.

## Run locally

You need a Databricks personal access token (PAT) or a configured CLI profile so
`Config()` can authenticate. Set the environment variables, then run Streamlit.

```bash
pip install -r requirements.txt

export DATABRICKS_HOST="https://<your-workspace>.cloud.databricks.com"
export DATABRICKS_TOKEN="<your-personal-access-token>"   # or use a CLI profile
export CLINOPS_CATALOG="<your_catalog>"
export CLINOPS_SCHEMA="clinops_ml"
export DATABRICKS_WAREHOUSE_HTTP_PATH="/sql/1.0/warehouses/<your_warehouse_id>"

streamlit run app.py
```

The app authenticates with `databricks.sdk.core.Config`. Running locally, it
reads your `DATABRICKS_HOST` and `DATABRICKS_TOKEN` (or a CLI profile). In
Databricks Apps, the same `Config()` call picks up the app service principal
credentials automatically, so no token is needed there.

## Deploy as a Databricks App

1. Upload this `app/` folder's source to your workspace, for example under
   `/Workspace/Users/<you>/prescreen-app`.
2. Edit `app.yaml` and set `CLINOPS_CATALOG`, `CLINOPS_SCHEMA`, and
   `DATABRICKS_WAREHOUSE_HTTP_PATH` to your values.
3. Create the app and deploy it from the uploaded workspace source.
4. Grant the app service principal the access it needs:
   - `CAN_USE` on the SQL warehouse.
   - `USE CATALOG` on the catalog and `USE SCHEMA` on the schema.
   - `SELECT` on `gold_trial_prescreen_wide` and `gold_patient_measurements`.

Once granted, the app queries the warehouse as its own service principal. All
access is governed by Unity Catalog, so the app can only read what the service
principal is allowed to read.

## Notes

- Query results are cached for 300 seconds with `st.cache_data`, so clicking
  around the app does not hammer the warehouse.
- The app reads only the two gold tables listed above. It does not write
  anything back.
