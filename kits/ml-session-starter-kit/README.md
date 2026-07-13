# 🧬 Applied AI Feature Extraction and Trial Pre-Screening: ML Reference Kit

**ML team · Applied AI · Genie Code (one Hugging Face notebook)**

> ### What this build is, and what it is not
> This is not a model-training build. There is no classifier to fit or tune. The work is
> **applied AI feature extraction**. You use a language model to pull biomarker facts out of
> free-text pathology notes, then feed those facts to a transparent, rules-based eligibility screen.
>
> | This build **is** | This build is **not** |
> |---|---|
> | Applied AI feature extraction. `ai_query` reads notes to pull HER2, ER, and PR status, and a Hugging Face model (ClinicalBERT) embeds the notes for similarity matching. | Training a predictive classifier. |
> | Rigorous evaluation. MLflow scores the extraction against a ground-truth set. | Hyperparameter tuning or feature engineering a model. |
> | A governed, auditable pre-screen. Deterministic rules, plus a plain-English reason per patient. | A black-box "probability of eligibility." |
> | The payoff. 31 notes-only patients recovered, 109 to 140. | A model metric like AUC. |
>
> The "model" here is a language model doing extraction, not a classifier doing prediction. The
> eligibility decision stays as auditable rules on purpose. In a clinical setting you want a decision a
> coordinator can defend, not a score they cannot explain. Want a real trained model? That lands as a
> patient-prioritization ranker in `STRETCH.md`, on top of the rules, never inside them.

This is a **build kit**, not a finished solution. The foundation is already in
place for you: synthetic OMOP data, the pipeline skeleton, Unity Catalog governance,
and the boilerplate. That frees you to build the learnable core: the eligibility SQL, the
biomarker pivot, the `ai_query` NLP extraction, and the MLflow evaluation. Look for
`# TODO (you build this)` markers. That is your work.

> Scaffold, don't hand-hold. The notebooks tell you *what* to build and *why*; you
> write the logic. If you get stuck, the worked reference solution (see `reference/`) and the full working
> notebooks are there to fall back on.

> 🛟 **These notebooks are the reference build.** The `notebooks/` and `reference/ANSWER_KEY.md`
> are the worked reference for the pre-screen on the governed foundation. Build with Genie Code
> and lean on the reference when you want the mechanism spelled out. See this kit's `RUNBOOK.md`
> for the clean step-by-step guide.

> 🖥️ **Genie Code drives the build.** The whole build is driven from Genie Code. The one step
> Genie Code cannot do is registering the Hugging Face model to Unity Catalog, which is a pre-built
> notebook you run. Everything else, including the Python EDA charts, is Genie Code.

---

## 🎯 The outcome you are shipping

This kit covers an end-to-end applied AI build. You build an app that uses a Hugging Face model
(ClinicalBERT) to pre-screen patients for clinical trials, and you register that model to Unity Catalog
so it stays governed and reproducible. You give Genie the context it needs (team docs, data background,
example queries) to answer accurately and do better exploratory data analysis. You set up MLflow
evaluation runs to compare prompts and models against ground truth. The build closes with a coordinator
app that lets a non-technical user review and act on the results.

### 🎯 The trials you are screening for, build to satisfy these

Your pre-screen has one job: decide correctly, for every patient and every trial, whether that
patient qualifies, and say why in plain English. **These are the criteria to solve for.** A patient
qualifies for a trial only when **all** of its conditions are met.

| Trial | A patient qualifies when… |
|---|---|
| **Trial A** (HER2-Positive Advanced Breast Cancer) | Breast cancer diagnosis · **HER2 Positive** · **Female** · age **18-75** · **no** prior anti-HER2 therapy (no Trastuzumab or Pertuzumab) |
| **Trial B** (ER+ / HER2− Postmenopausal) | Breast cancer diagnosis · **ER Positive** · **HER2 Negative** · **Postmenopausal** · **Female** · age **18-75** |
| **Trial C** (triple-negative) | Breast cancer diagnosis · **HER2 Negative** · **ER Negative** · **PR Negative** · **Female** · age **18-75**. Another row in your own `silver_trial_criteria` table, screened by the same one rule with **no code change**. |

The synthetic data is planted so you can check your work: persons **1 to 20** are eligible for Trial A
(21 to 30 are HER2+ controls who fail on prior anti-HER2 therapy), and persons **31 to 50** are eligible
for Trial B (51 to 60 are controls who fail on menopausal or ER status). Full spec in
`../../foundation/PLANTED_COHORTS.md`.

📋 **Canonical eligibility card:** every trial's `req_*` fields, the eligible counts (Trial A 140, Trial
B 70, Trial C 53), and the one matching rule live in one place, the card in `../../SHARED_FOUNDATION.md`.
That is the single source of truth; this table summarizes it. Read the card rather than re-deriving
criteria.

> 🔗 **Trials are data, not hardcoded rules.** Do not hardcode the Trial A/B/C conditions above.
> Build a small `silver_trial_criteria` table (one row per trial, a `req_*` column per condition) and
> have your pre-screen **join it** with one generic rule: a patient qualifies when **each non-NULL
> `req_*` matches and age is in range** (a NULL requirement means the trial does not constrain that
> field). This gets you to the 109→140 hero number, and it means **adding a trial is adding a row, not
> writing code.** Trial C (triple-negative) is simply another row in that same table, screened by the
> same rule.

**The catch, and the whole point of this build:** biomarker status is not always in
the structured tables. For ~60 of our 300 synthetic patients, HER2/ER/PR status was
only ever written into a **free-text pathology note**. A SQL query over `measurement`
alone **silently misses them**. You will recover them with a Foundation Model
(`ai_query`), prove the win, and *measure* how good the extraction is with MLflow.

**Where you start:** you build the **structured silver** layer (`silver_biomarker_profile`,
`silver_demographics`, `silver_prior_therapy`) yourself, off the 6 OMOP tables. That is notebook 02.
From there your build moves to the gap (notebook 03) and the `ai_query` transformation (notebook 04).

By the end you will have built:
- the **gap analysis** surfacing the ~60 notes-only patients structured SQL silently misses,
- ⭐ an **`ai_query`** NLP step that reads biomarkers out of the unstructured pathology notes (the hero),
- a **gold** unified cohort with a `biomarker_source` audit column,
- a **data-driven pre-screen** that joins your own `silver_trial_criteria` table, one LONG
  `gold_trial_prescreen` (row per person × trial) plus a backward-compat `gold_trial_prescreen_wide`
  view,
- an **MLflow evaluation** comparing prompts × models against ground truth,
- a **Hugging Face model (ClinicalBERT) registered to Unity Catalog** (a common ML-team ask), whose note
  embeddings drive **similarity matching** for cohort discovery (`gold_similar_patients`),
- a **Genie space** so a non-technical coordinator can self-serve the cohort,
- a **coordinator/researcher app**: patient timeline drill-down, an override write-back,
  and an in-app lightweight agent.

---

## 🧱 What's pre-built vs. what you build

| Component | Status |
|---|---|
| Synthetic OMOP data generator (6 tables, 300 patients, planted cohorts) | ✅ **Shared foundation** |
| `_config` shared catalog/schema/warehouse, helpers, FM endpoints | ✅ **Pre-built** |
| **Structured silver**: biomarker pivot (HER2/ER/PR), demographics, prior therapy | 🛠️ **You build** (notebook 02, off the 6 OMOP tables) |
| Gap analysis: classify patients by evidence location (both / structured-only / notes-only) | 🛠️ **You build** (notebook 03) |
| EDA visuals in Python (charts of the cohort, and the gap) | 🛠️ **You build** (Genie Code writes them into a serverless notebook) |
| Eligibility cohort and gold unified prescreen logic (COALESCE with a `biomarker_source` audit column) | 🛠️ **You build** |
| Data-driven pre-screen: join your own `silver_trial_criteria`, LONG `gold_trial_prescreen` plus a `_wide` view | 🛠️ **You build** (generic join, no hardcoded rules) |
| `gold_patient_measurements`: per-patient longitudinal test timeline (feeds the app) | 🛠️ **You build** |
| `ai_query` NLP biomarker extraction from `note_text` | 🧠 **You build** (heavily signposted) |
| MLflow evaluation run (prompt × model) | 🧠 **You build** (heavily signposted) |
| Hugging Face model (ClinicalBERT) registered to UC (a common ML-team ask) | ✅ **Pre-built notebook**, the one step Genie Code can't author; run it if HF egress allows |
| Similarity matching over the embeddings, `gold_similar_patients` cohort discovery | 🛠️ **You build** (Genie Code, in SQL) |
| Coordinator/researcher app (timeline, override, in-app agent) | 🖥️ **Included**, reference demo at `app/` (see below) |
| More trials, advanced evals, real-data toggle | 🚀 **Stretch**, see `STRETCH.md` |

---

## 🚀 How to start

**There is no bundle to deploy and no data to generate for this kit.** The shared **foundation** already
stood up the six OMOP tables (300 patients, planted cohorts) that this build reads. You build the
pre-screen with **Genie Code**; the pre-built notebooks are the reference. Exactly **one**
notebook is meant to run as-is, the ClinicalBERT registration Genie Code can't author. Everything else,
including the Python EDA, is Genie Code.

### The adaptation skill helps Genie Code build well
The workspace-level **`prescreen-clinops-adaptation`** skill is not a value-filler. It gives Genie Code
the context to build the pre-screen cleanly (the shared-foundation table names, the FM endpoints, the
build order), and when your team is ready to point at your own OMOP data, it tells Genie Code
exactly how to adapt. A workspace admin installs it once, for everyone:

```bash
databricks workspace import-dir \
  /Workspace/prescreen-clinops/prescreen/repo/.assistant/skills/prescreen-clinops-adaptation \
  /Workspace/.assistant/skills/prescreen-clinops-adaptation
```

Then open Genie Code in a fresh chat in this kit's folder (hard-refresh first, skills cache per tab)
and start building. `GENIE_CODE_PROMPTS.md` has the proven starter prompts.

### The one notebook you run: ClinicalBERT → Unity Catalog
Genie Code drives the whole build except registering a Hugging Face model to UC. Run the pre-built
`05_clinicalbert_mlflow_uc` notebook for that step (serverless: it pip-installs, downloads the weights,
registers ClinicalBERT to UC, and embeds the notes for similarity). Everything up- and downstream of it
is Genie Code.

### Then
1. Confirm the foundation is up: the six shared OMOP tables exist. For a reference scaffold, open
   `00_START_HERE`.
2. Set the widgets: the shared foundation `catalog`/`schema` for reads, a running `warehouse_id`, and
   your own writable schema for what you build.
3. Build with Genie Code: **`02` structured silver** off the 6 OMOP tables, then `03` (the gap and the
   Python EDA), then `04` (`ai_query`), then the `05` HF notebook, then `06` → `08`.
   (See `../../SHARED_FOUNDATION.md` for what the shared foundation provides vs. what you build.)

### Optional: build the Genie space with the `prompt-to-genie` skill (notebook 08)
Notebook `08_genie_space_setup` stands up the self-serve Genie space. You can point-and-click it
in the UI, or drive it conversationally with the community **`prompt-to-genie`** Genie Code skill
([sean-zhang-dbx/prompt-to-genie](https://github.com/sean-zhang-dbx/prompt-to-genie)), it walks you
through requirements → data sources → sample questions → validated `serialized_space` JSON → API
deploy → benchmark. Install it **once at the workspace level** as a Git folder at the skill path, so
it stays updatable from source:

```bash
databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
  --path /Workspace/.assistant/skills/prompt-to-genie
```

Then open a fresh Genie Code chat (hard-refresh, skills cache per tab) and say **"create a Genie
space"**; it reads your gold `gold_trial_prescreen` cohort and builds the space over it. It's a
conversational, checkpoint-driven flow (confirm each step), and prompt-matching is off by default on
API-created spaces, enable it in the UI after creation.

---

## 🔄 The synth to real toggle

The whole build runs on **synthetic data by default** (no PHI, security-first by design).
The synthetic tables follow the OMOP Common Data Model (OMOP CDM), a public open standard. When you
are ready to point it at your own OMOP data, you do not rewrite queries. The 6 OMOP table names are
**identical** in synthetic and real modes, so every silver / gold / NLP query you build runs
unchanged against any OMOP-conformant source you point it at.

To switch, ask Genie Code (with the `prescreen-clinops-adaptation` skill installed) to repoint the reads
from the shared foundation schema to your own OMOP catalog and schema:

- source catalog → `<your_omop_catalog>`
- source schema  → `<your_omop_schema>`

The skill walks Genie Code through the repoint and the re-runs it implies (anything already built on
synthetic gets rebuilt so it reflects real data). Trying the toggle is a stretch exercise, see
`STRETCH.md`.

---

## 🖥️ The coordinator/researcher app

This kit includes a researcher-facing app on top of the pre-screen, provided as the kit's app
deliverable. It is a **reference demo**, a working thing that shows the value, not a required
build. It lives in this kit's `app/` folder.
Three capabilities:

- **Patient timeline drill-down.** A coordinator picks a patient and sees their tests over time.
  Reads `gold_patient_measurements` (the per-patient longitudinal test timeline).
- **Override / disagree write-back.** A coordinator can disagree and remove a patient from a trial
  with a reason. **The model output stays immutable**. The app never edits `gold_trial_prescreen`.
  Human decisions go to a separate `eligibility_override` table; the app shows **effective
  eligibility** (`COALESCE(human_says, model_says)`). Auditable and reversible. Retraining the model
  is out of scope.
- **In-app lightweight agent.** A small agent runs inside the app and calls the
  `databricks-claude-sonnet-4-6` FM endpoint directly. Authored with the MLflow **`ResponsesAgent`**
  pattern (so graduating to a served endpoint later is a lift, not a rewrite), with three tools:
  **patient timeline**, **check-a-patient-against-all-trials**, and **screen-a-subset**. This is how
  a coordinator personalizes across trials: pull a subset and check them against other criteria.

The similarity table `gold_similar_patients`, built in the applied AI step with Genie Code, can feed a
"find similar patients" view here as a natural next add.

---

## 🔒 Ground rules (security-first by design)

- **Everything is Unity-Catalog-scoped**: catalog/schema come from notebook widgets.
  No `hive_metastore`, ever.
- **Synthetic data only.** No real PHI in this kit. The toggle exists so you never have
  to improvise on real data to land a demo.
- **No hardcoded secrets.** No tokens, keys, or passwords in code, use widgets
  (and `dbutils.secrets` for any external call, though this kit needs none).
- **Governance is visible, not hidden.** Models register to UC, lineage is automatic,
  the gold layer carries a `biomarker_source` audit column so every eligibility decision
  is traceable to structured data or an AI reading of a note.

---

## 🗂️ Repo layout

```
ml-session-starter-kit/
  README.md            ← you are here
  databricks.yml       ← optional bundle config (the foundation provides the data; not run per team)
  RUNBOOK.md           ← build-level reference (checkpoints, failure modes)
  GENIE_CODE_PROMPTS.md ← ready-to-use Genie Code build prompts (free-form; the validated set)
  STRETCH.md           ← "make it your own" extension ideas
  notebooks/           ← reference scaffold (00-09); the build is Genie Code, 05 is the one you run
  genie/               ← Genie space definition (instructions, prompts, trusted SQL)
  reference/           ← worked reference solution (fall back to it if a team is stuck)
  src/data_generation/ ← the synthetic OMOP generator (used by the foundation; do not edit)
  resources/           ← optional bundle job (the foundation already lands the data)
```

## 📒 The notebook arc

| # | Notebook | What it builds | Your job? |
|---|---|---|---|
| · | `_config` | shared catalog/schema/warehouse | ✅ pre-built |
| 00 | `00_START_HERE` | overview, the value story | ✅ read it |
| 01 | `01_data_foundation_omop` | profile the 6 shared OMOP tables the foundation provides | ✅ read, light TODO |
| 02 | `02_silver_feature_pipeline` | silver feature views (SQL pipeline) | 🛠️ build the pivots |
| 03 | `03_exploratory_data_analysis` | quantify the notes-only gap, Python EDA visuals | 🛠️ light TODO |
| 04 | `04_nlp_biomarker_extraction` | `ai_query` over `note_text` | 🧠 the GenAI core |
| 05 | `05_clinicalbert_mlflow_uc` | Hugging Face model (ClinicalBERT) → UC, then embeddings for similarity | ✅ pre-built (the Genie Code exception); feeds `gold_similar_patients` |
| 06 | `06_gold_unified_prescreen` | gold unified and data-driven prescreen (joins `silver_trial_criteria`; LONG plus `_wide` view) plus `gold_patient_measurements` | 🛠️ build the fusion and the generic join |
| 07 | `07_mlflow_evaluation_runs` | MLflow eval: prompt × model | 🧠 build the eval |
| 08 | `08_genie_space_setup` | self-serve Genie space | ✅ guided setup |
| 09 | `09_app` | coordinator/researcher app: timeline drill-down, override write-back, in-app agent | 🚀 reference demo (included; `app/`) |
```
