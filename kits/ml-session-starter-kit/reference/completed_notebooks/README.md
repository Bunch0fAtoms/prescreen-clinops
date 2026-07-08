# Completed reference notebooks (SA / presenter use)

This folder is the **filled-in, runnable** version of the starter kit in `../../notebooks/`. Every
`TODO (you build this)` is completed and the notebooks are internally consistent so the whole arc
runs top to bottom. Use it to present the solution to Fred Hutch and as the mentor's known-good copy.

The starter-kit skeletons the team builds during the session stay in `../../notebooks/`. The intended
answers, per notebook, are in `../ANSWER_KEY.md`. The run-of-show for the review session is
`../../PRESENTATION_WALKTHROUGH.md`.

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

The coordinator app (Sita's ask) is in `../../app/`.

## Two reconciliations baked into this set (so it runs standalone)

1. **`silver_trial_criteria` is seeded inside notebook 06.** The pre-screen joins a trials catalog
   (trials-as-data). The Data Engineering team builds that same table from a live feed in their own
   schema. So the Applied AI section does not have to wait on them, notebook 06 seeds its own copy
   (Trials A, B, C). Repointing the join to the Data Engineering team's `silver_trial_criteria` is the
   documented cross-team stretch (`../../DE_INTEGRATION_STRETCH.md`).

2. **The patient join in notebook 06 sources fields from the right silver views.** `menopausal_status`,
   `ajcc_stage`, and `gender` come from `silver_demographics`; `prior_anti_her2` comes from
   `silver_prior_therapy` (its `had_anti_her2_therapy` column, coalesced to `false`). Notebook 08's
   table comments describe the long shape of `gold_trial_prescreen` (one row per patient per trial).

## Run order and prerequisites

Run `00 → 08` in order on **serverless** notebook compute, with access to the Foundation Model
endpoints (`databricks-claude-haiku-4-5`, `databricks-claude-sonnet-4-6`). Notebook 05 needs outbound
internet for the HuggingFace download, and its serving-endpoint cell provisions for a few minutes.
Notebook 07 installs a recent MLflow and restarts Python at the top, so run it as its own pass.

Validated numbers to expect: **Trial A eligible = 140**, **Trial B = 56**, **31 recovered only via NLP**.
