# Adapting the Fred Hutch Clinical Trial Pre-Screening Demo to Your Data

This project bundles the Fred Hutch Clinical Trial Pre-Screening demo with a synthetic OMOP dataset so you can run it end-to-end immediately. When you're ready to run it on your own clinical data, this guide walks you through the conversion.

## What this demo does

A Databricks-powered clinical trial pre-screening solution that ingests OMOP CDM data, extracts biomarker status (ER/PR/HER2) from both structured measurements and free-text pathology notes using NLP/LLM, and surfaces eligible cohorts for two breast cancer trials. Researchers can query `measurement` for structured results and Genie Code extracts biomarker status from `note.note_text` — recovering ~25% of patients whose results live only in pathology notes.

## What's bundled

- **6 OMOP CDM tables** (`person`, `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, `note`) populated with 300 synthetic breast cancer patients.
- **Planted cohorts**: person_ids 1–20 eligible for Trial A (HER2+); person_ids 31–50 eligible for Trial B (ER+/HER2-, postmenopausal). Verified controls for each.
- **NLP value story**: person_ids 181–240 have biomarker status in `note.note_text` only — invisible to structured queries, discoverable by Genie Code NLP extraction.
- **A Genie Code skill** (in `.assistant/skills/`) that knows how to help you adapt this project. Open Genie Code and ask **"run in my workspace"** — it'll guide you through the configuration.

## First run (with synthetic data)

```bash
databricks bundle deploy --target client
databricks bundle run data_generation_job --target client
```

No edits needed. Default `run_with_synthetic_data: "yes"` in `databricks.yml` runs the data generator and creates all 6 tables in your catalog/schema.

## Switching to your data

The handoff package uses the Databricks Asset Bundle `targets:` pattern. All workspace-specific config lives under `targets.client.variables` in `databricks.yml`.

1. Open `databricks.yml` and find the `targets: client: variables:` block.
2. Set `run_with_synthetic_data: "no"`.
3. Set `source_catalog` to your OMOP source catalog (e.g., `curated_omop` or your hospital's catalog).
4. Set `source_schema` to your OMOP source schema (e.g., `omop`).
5. Set `client_catalog` and `client_schema` to where you want Databricks to create any new assets (replace the `<your_catalog>` / `<your_schema>` placeholders).
6. (Optional) Set `warehouse_id` to the SQL warehouse you want to use.
7. Verify your data has the expected OMOP columns — ask Genie Code: **"what columns does the measurement table need for the HER2 query?"**
8. Re-deploy:
   ```bash
   databricks bundle deploy --target client
   ```
   *(No need to re-run the data generation job — downstream queries now read from your real OMOP tables.)*

**Tip:** ask Genie Code **"run in my workspace"** — it can detect your current catalog/schema and propose the YAML edits for you.

## Schema compatibility

Your real OMOP tables must have these columns (matching `curated_omop.omop` at Fred Hutch):

| Table | Required columns for this demo |
|---|---|
| `measurement` | `person_id`, `measurement_source_value`, `value_source_value` |
| `condition_occurrence` | `person_id`, `condition_source_value` |
| `observation` | `person_id`, `observation_source_value`, `value_source_value` |
| `drug_exposure` | `person_id`, `drug_source_value` |
| `note` | `person_id`, `note_text`, `note_date` |
| `person` | `person_id`, `year_of_birth`, `gender_source_value` |

If your OMOP tables use different source_value strings (e.g., your HER2 measurement uses `HER2` instead of `HER2/neu`), ask Genie Code to help you adapt the cohort queries.

## Where to get help

- **Genie Code** in your workspace knows this project — ask it specific adaptation questions.
- **`README.md`** describes the demo's story and walkthrough.
- **`PLANTED_COHORTS.md`** documents the exact person_ids and SQL for each trial cohort.
- **`ADAPTATION_FACTS.json`** is the machine-readable facts file the Genie Code skill uses — don't edit it.

## Compatibility contract — what the adaptation skill guarantees

The bundled Genie Code skill (`.assistant/skills/fred-hutch-clinical-trial-prescreening-adaptation/`) reads `ADAPTATION_FACTS.json` and can, for THIS demo:

- **Guarantees:** detect your workspace/catalog/schema/warehouse and write `databricks.yml`; deploy on synthetic data; switch to real OMOP data by updating toggle variables; confirm planted cohort queries return expected counts; triage deployment failures.
- **Cannot do automatically (will tell you + hand off):** migrate existing data between tables; refactor OMOP source_value mappings if your schema diverges significantly; create the Genie space or Knowledge Assistant (those are not owned by `bundle deploy`).
- **Halts and asks when:** a needed fact is unresolved in `ADAPTATION_FACTS.json`; a source table/column is missing; a verify query fails. A wrong change is worse than a paused one.

## Refreshing after an SA update (stale-skill detection)

When the SA pushes a new version of this repo:
1. `git pull` in this folder.
2. Re-import the updated skill to your workspace (see README "First Run (Client)" Step 2).
3. **Hard-refresh the Genie Code browser tab** (skills are cached per tab; a new chat thread alone is not enough) and start a NEW chat.
4. The skill compares its `SKILL_VERSION` against `ADAPTATION_FACTS.skill_version` on entry — if they differ it will tell you the package is stale and to re-import. Don't proceed past that warning.
