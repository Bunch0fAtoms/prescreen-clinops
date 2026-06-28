# Fred Hutch Clinical Trial Pre-Screening — OMOP Data Foundation

| | |
|---|---|
| **Organization** | Fred Hutchinson Cancer Center |
| **Protagonist** | Dr. Sarah Okonkwo — Clinical Research Coordinator, Breast Oncology |
| **Challenge** | Researchers manually review hundreds of charts to identify eligible patients for breast cancer trials. Biomarker results (ER/PR/HER2 status) are split between structured EHR data and free-text pathology notes, forcing staff to read every report individually. Eligibility checks that should take minutes take days. |
| **Journey** | A Databricks-powered pre-screening pipeline ingests OMOP clinical data, extracts biomarker status from pathology notes using NLP/LLM, and aligns structured + unstructured signals. Genie Code surfaces eligible cohorts instantly. |
| **Resolution** | Trial A (HER2+) and Trial B (ER+/HER2-) eligible cohorts are identified in seconds. Notes-only patients — invisible to structured queries — are surfaced by NLP extraction, expanding each cohort by ~25%. |
| **Impact** | Screening time: **days → minutes**. Cohort completeness: **+25% patients recovered from notes alone**. Trial enrollment velocity: faster first-patient-in. |

## Overview

This project delivers the **OMOP data foundation** for the Fred Hutch clinical trial pre-screening solution. Six OMOP CDM tables — `person`, `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, `note` — are populated with 300 realistic breast cancer patients, designed specifically to power:

1. **Structured cohort queries** (SQL over `measurement` for known biomarker results)
2. **NLP/LLM extraction** from `note.note_text` pathology reports (the value story — ~25% of patients have biomarker status in notes only)
3. **MLflow evaluation** — `both-agree` patients provide structured ground truth against which note-extraction accuracy can be scored

Genie Code builds the actual cohort logic and agent on top of this foundation. This project owns the data and the bundle.

## Key Numbers

| Metric | Value |
|---|---|
| Total patients | 300 |
| OMOP tables | 6 (exact customer schema match) |
| **both-agree** patients (NLP ground truth) | ~150 (50%) |
| **notes-only** patients (NLP value story) | ~75 (25%) |
| **structured-only** patients | ~75 (25%) |
| Trial A eligible patients (HER2+) | 20 (person_ids 1–20) |
| Trial B eligible patients (ER+/HER2-, postmenopausal) | 20 (person_ids 31–50) |
| Known-ineligible controls per trial | 10 each |

## Planted Cohorts

Two trials with deterministic eligible/ineligible person_ids, documented in `PLANTED_COHORTS.md`:

**Trial A — HER2+ breast cancer:** breast cancer dx + HER2 Positive + age 18–75 + NO prior anti-HER2 therapy (trastuzumab/pertuzumab)

**Trial B — ER+/HER2- postmenopausal:** breast cancer dx + ER Positive + HER2 Negative + postmenopausal (observation) + age 18–75

## Synth → Real Toggle

The bundle is parameterized so the same downstream Genie/ML/dashboard assets work against either synthetic demo data or the customer's real `curated_omop.omop` tables — no query changes required:

| Variable | Default (synthetic) | Real mode |
|---|---|---|
| `run_with_synthetic_data` | `yes` | `no` |
| `source_catalog` | `curated_omop` | customer catalog |
| `source_schema` | `omop` | customer schema |

## Demo Walkthrough

1. **Open Genie** — query `measurement` for HER2-positive patients → returns ~50% of eligible Trial A patients
2. **Run NLP extraction** (Genie Code) — parse `note.note_text` pathology reports → recovers the other ~25% of Trial A patients whose HER2 status was notes-only
3. **Trial A cohort** — filter: breast cancer + HER2 Positive + age 18–75 + no trastuzumab/pertuzumab in `drug_exposure` → returns person_ids 1–20
4. **Trial B cohort** — filter: breast cancer + ER Positive + HER2 Negative + postmenopausal (`observation`) + age 18–75 → returns person_ids 31–50
5. **MLflow eval** — score NLP extraction accuracy using both-agree patients as ground truth
6. **Flip toggle** — point bundle at `curated_omop.omop` → exact same queries run against real patient data

## First Run (Client)

1. Unzip `fred-hutch-clinical-trial-prescreening-client-handoff.zip` and open `databricks.yml`. Edit the `targets.client.variables` block — set `client_catalog`, `client_schema`, and `warehouse_id` to your values (replace `<your_catalog>` / `<your_schema>` / `<your_warehouse_id>`).
2. Import the Genie Code adaptation skill: in Genie Code, use **Import skill from file** → `.assistant/skills/fred-hutch-clinical-trial-prescreening-adaptation/SKILL.md`. Or ask Genie Code: **"run in my workspace"** and it will guide you.
3. From a terminal at the project root:
   ```bash
   databricks bundle deploy --target client
   databricks bundle run data_generation_job --target client
   ```

See `ADAPTATION_GUIDE.md` for switching to real OMOP data.

## Products Showcased

| Product | Role in this demo |
|---|---|
| **Synthetic Data Gen** | 300 OMOP patients with realistic pathology notes, biomarker coherence, and planted cohorts |
| **Databricks Asset Bundles** | Deployable bundle with synth/real toggle via `run_with_synthetic_data` variable |
| **Unity Catalog** | Tables in `<client_catalog>.<client_schema>`, lineage, governance |
| **Genie** *(talking track)* | Natural-language cohort queries over OMOP tables |
| **Genie Code** *(talking track)* | NLP/LLM extraction from `note.note_text`, cohort pre-screening logic |
| **MLflow** *(talking track)* | Evaluation of NLP extraction accuracy using both-agree ground truth |
