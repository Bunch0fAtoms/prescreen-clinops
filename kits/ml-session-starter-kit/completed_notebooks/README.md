# Completed reference notebooks

This folder is the **filled-in, runnable** version of the starter kit in `../notebooks/`. Every
`TODO (you build this)` is completed and the notebooks are internally consistent, so the whole arc
runs top to bottom.

These are saved as `.ipynb` **with their outputs**, so they do two jobs at once:

- **Read them as-is.** GitHub renders them inline, and so does the workspace after import, so you can
  review the whole build, tables, charts, model registration, and evaluation results, without running
  anything first.
- **Run them yourself.** Import the folder, set the widgets on `00_START_HERE` (they surface from
  `_config`, so you do not edit any file), and Run All. The build re-runs against your own workspace.

The starter-kit skeletons the team builds during the session stay in `../notebooks/`. The worked
reference solution, per notebook, is in `../reference/ANSWER_KEY.md`. The run-of-show for the review session is
`../PRESENTATION_WALKTHROUGH.md`.

## Setting your workspace values (no config file to edit)

`_config` defines five widgets. Open `00_START_HERE`, run its first cell (`%run ./_config`), and the
widgets appear at the top of the notebook. Fill in the two placeholders and the rest have sensible
defaults:

| Widget | Default | What to set |
|---|---|---|
| `catalog` | `<your_catalog>` | your Unity Catalog catalog |
| `schema` | `clinops_ml` | the schema you write to (features, model, gold) |
| `warehouse_id` | `<your_wh_id>` | your SQL warehouse ID |
| `source_schema` | `clinops_foundation` | the schema holding the six read-only OMOP tables |
| `source_catalog` | *(blank)* | leave blank for synthetic; set it to point at your real OMOP catalog |

The outputs saved in these notebooks are from one example run, so they show an example catalog name.
Yours will show your own values once you run them.

## What runs where

| Notebook | State | Teaching moment |
|---|---|---|
| `00_START_HERE` | orientation | the arc and the three biomarker-source groups |
| `01_data_foundation_omop` | filled | planted cohorts, the notes-only gap |
| `02_silver_feature_pipeline` | filled | declarative SQL pipeline, the biomarker pivot |
| `03_exploratory_data_analysis` | filled | the gap that justifies NLP |
| `04_nlp_biomarker_extraction` | filled | **ai_query** over free text |
| `05_clinicalbert_mlflow_uc` | filled, plus serving | **HuggingFace to Unity Catalog, then a serving endpoint** |
| `06_gold_unified_prescreen` | filled | fuse, audit, trials-as-data |
| `07_mlflow_evaluation_runs` | filled, plus genai | **MLflow eval, traces, LLM-as-judge, custom metrics** |
| `08_genie_space_setup` | filled | natural-language self-serve |

The coordinator app is in `../app/`.

## Two reconciliations baked into this set (so it runs standalone)

1. **`silver_trial_criteria` is seeded inside notebook 06.** The pre-screen joins a trials catalog
   (trials-as-data): one row per trial, one `req_*` column per criterion, NULL meaning unconstrained.
   Notebook 06 seeds its own copy (Trials A, B, C), so the notebook runs standalone. Adding a trial
   is inserting a row, not changing code. Trial C (triple-negative) is simply one of those rows.

2. **The patient join in notebook 06 sources fields from the right silver views.** `menopausal_status`,
   `ajcc_stage`, and `gender` come from `silver_demographics`; `prior_anti_her2` comes from
   `silver_prior_therapy` (its `had_anti_her2_therapy` column, coalesced to `false`). Notebook 08's
   table comments describe the long shape of `gold_trial_prescreen` (one row per patient per trial).

## Run order and prerequisites

Run `00 → 08` in order on **serverless** notebook compute, with access to the Foundation Model
endpoints (`databricks-claude-haiku-4-5`, `databricks-claude-sonnet-4-6`). Notebook 05 needs outbound
internet for the HuggingFace download, and its serving-endpoint cell provisions for a few minutes.
Notebook 07 installs a recent MLflow and restarts Python at the top, so run it as its own pass.

Validated numbers to expect: **Trial A eligible = 140**, **Trial B = 70**, **31 recovered only via NLP for Trial A, 14 more for Trial B**.
