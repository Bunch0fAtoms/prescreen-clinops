# Executed notebooks (pre-run, with outputs)

These are the reference notebooks after a full end-to-end run, saved as `.ipynb` with their
outputs. GitHub renders them inline, so you can read the whole build, tables, charts, model
registration, and evaluation results, without running anything first.

They are a **read-only snapshot**, not the files you edit. The editable reference source lives
next door in [`../completed_notebooks/`](../completed_notebooks/) as `.py` notebooks. To run the
build yourself, follow the kit `README.md` and `RUNBOOK.md`.

## What you are looking at

| Notebook | What it shows |
|---|---|
| `00_START_HERE` | Widgets and the shared config. |
| `01_data_foundation_omop` | The six OMOP tables the build reads. |
| `02_silver_feature_pipeline` | Structured biomarker features. |
| `03_exploratory_data_analysis` | The notes-only gap the NLP step recovers. |
| `04_nlp_biomarker_extraction` | Foundation-model extraction of ER / PR / HER2 from notes. |
| `05_clinicalbert_mlflow_uc` | ClinicalBERT embeddings, registered to Unity Catalog and served. |
| `06_gold_unified_prescreen` | Trials-as-data join, per-patient eligibility with a plain-English reason. |
| `07_mlflow_evaluation_runs` | LLM-as-judge evaluation of the extraction. |
| `08_genie_space_setup` | The self-serve Genie space over the cohort. |
| `_config` | The shared config companion (`%run ./_config`). |

## Notes on the outputs

- The catalog, schema, and warehouse shown in the outputs (for example `clinops_catalog`,
  `clinops_ml`) are from one example run. Yours will show your own workspace values.
- In `05`, the serving-endpoint query cell shows an "endpoint still provisioning" message. Serving
  endpoints take about ten to fifteen minutes to come up, longer than the notebook's built-in wait.
  Everything before it is complete, including the registered model and the real embeddings. Re-run
  that one cell once the endpoint reports READY.
