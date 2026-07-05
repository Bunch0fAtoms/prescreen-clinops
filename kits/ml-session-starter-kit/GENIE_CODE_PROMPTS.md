# 💬 Genie Code — starter prompts (ML / clinical-trial pre-screening)

**Fred Hutch onsite · ML session · Genie Code over the governed OMOP foundation**

The build is **free-form**. The foundation is already up — the 6 OMOP tables are present and read-only.
From here **you design the pre-screening solution your team wants to build.** You start from those 6
tables and **build the structured silver features yourself** (that is part of your build, notebook 02),
then move to the notes-only gap and the `ai_query` recovery. These are **starter prompts** — the same
ones proven end-to-end in the dry run — but they're a starting line, not a script. Change them, combine
them, or ask your own.

> **How to drive Genie Code well:** paste one prompt at a time; **review the diff before you Accept**
> (never "Accept all"); let it **persist work as real notebooks / pipeline SQL files**, not scratch.
> This chat runs on a SQL warehouse — inline work is SQL-only; for Python (MLflow, ClinicalBERT) have it
> **create a notebook that runs on serverless compute**. Point it at the right page for an edit to land.

> **The synthetic cohort buckets (authoritative — Genie Code reads these from `ADAPTATION_FACTS`):**
> both-agree = person_id 1–180, **notes-only = 181–240** (the ones structured SQL misses), structured-
> only = 241–300. Primary FM endpoint = `databricks-claude-haiku-4-5`.

> **Synthetic data only, everything UC-scoped, governance visible** (the gold layer carries a
> `biomarker_source` audit column). No `hive_metastore`, no real PHI.

---

### 1. Profile the data and name the gap (the warm-up)  *(nb 01 / 03)*
> **"Profile the 6 OMOP tables. Crucially, count how many patients have HER2 status in the structured `measurement` table vs. ONLY in the free-text `note.note_text`. Classify every patient as both / structured-only / notes-only, and tell me the notes-only number — that's the gap we're about to close."**

*Good looks like:* the three buckets read ≈ **180 / 60 / 60** and the team can say it out loud: *"~60
patients are invisible to SQL."* That number is the motivation for everything that follows — make sure
it lands before moving on.

---

### 2. Recover the notes-only patients with `ai_query`  *(nb 04 · the hero moment)*
> **"Extract HER2 / ER / PR / menopausal status / AJCC stage from `note.note_text` using `ai_query` with `databricks-claude-haiku-4-5`, and write the results to `silver_nlp_biomarkers` with a `'nlp'` source literal. Use constrained decoding so the output is clean JSON, and recover the notes-only patients (181–240)."**

*Good looks like:* `silver_nlp_biomarkers` = **240 rows**, all ~60 notes-only patients recovered, ~100%
fill rate.

> ⚠️ **The classic gotcha (plumbing — reveal early):** without `responseFormat` the model wraps its
> answer in ```` ```json ```` fences and `from_json` returns NULL for **every** row. Fixes: pass
> `responseFormat` (constrained decoding) and parse with the **flat** schema via `from_json`; the
> DDL form allows only one top-level field, so wrap as `STRUCT<result:STRUCT<...>>`. And because this is
> a STREAMING TABLE, **full-refresh** it after fixing the SQL or the earlier NULL rows persist. The
> prompt *wording* is your learnable bit — the response-shape fix is on the cheat-sheet in nb 04.

---

### 3. Fuse structured + NLP into an audited gold cohort  *(nb 06)*
> **"Build `gold_unified_biomarker_profile`: FULL OUTER JOIN the structured silver and `silver_nlp_biomarkers` (dedup NLP to one row per person via ROW_NUMBER on note_id) on person_id, `COALESCE` each biomarker, and add a `biomarker_source` audit column = both / structured / nlp. Then build `gold_trial_prescreen` by JOINING the unified profile + demographics + prior therapy against the DE group's `silver_trial_criteria` catalog — a GENERIC eligibility match, NOT hardcoded Trial A/B. The rule: a patient qualifies for a trial when, for every non-NULL `req_*` criterion the patient's value matches, AND age BETWEEN `age_min` AND `age_max`. A NULL `req_*` means that trial does not constrain that field, so it passes. Emit one row per (patient, trial) with an eligible boolean and a plain-English reason. Show me the files before you run them."**

*Good looks like:* unified profile by source = **both 180 / nlp 60 / structured 60**. The generic join
reproduces the validated numbers with **no per-trial code**: **Trial A still 140**, **Trial B still 56**,
the **+31 NLP-recovered** patients preserved — and a **net-new Trial C (triple-negative)** appears in the
output the moment it exists in `silver_trial_criteria`, with zero code change. **Schema facts to feed it:**
`menopausal_status` + `ajcc_stage` live on the biomarker tables (not `silver_demographics`, which has only
`gender`, `age_at_dx_years`); prior-therapy column is `prior_anti_her2`; join `silver_trial_criteria`'s
`req_sex`/`req_her2`/`req_er`/`req_pr`/`req_menopausal`/`req_no_prior_anti_her2` against the matching
patient columns. Use `CREATE OR REFRESH MATERIALIZED VIEW`. If Genie Code reaches for `CASE WHEN trial =
'A' …`, that's **the redirect** — the whole point is that the catalog drives eligibility, so adding a
trial is a new catalog row, not new SQL.

---

### 3b. Build the per-patient test timeline the app drills into  *(nb 06 · feeds Sita's app)*
> **"Build `gold_patient_measurements`: a per-patient longitudinal test timeline from the OMOP `measurement` table. One row per (person_id, test, date) with the measured value and unit, ordered by date, so a coordinator can open a patient and see their tests over time to verify eligibility. Use the human-readable `measurement_source_value` for the test name and `measurement_date` for the timeline. Show me the file before you run it."**

*Good looks like:* one tidy longitudinal table keyed by `person_id`, sortable by `measurement_date`, with
test name + value + unit per row — the coordinator app opens a patient and renders their HER2 / ER / PR
tests as a dated timeline. This is Sita's "interrogate a patient" ask (#10): the app drills into THIS
table. Confirm `measurement` has usable dates in the synthetic data; if a patient has no dated rows the
timeline is simply empty, not an error. Use `CREATE OR REFRESH MATERIALIZED VIEW`.

---

### 4. Show the payoff (the reveal)
> **"Run the numbers that prove the NLP step mattered: how many patients are Trial A–eligible WITHOUT the NLP-recovered ones vs. WITH them, and how many eligible patients exist only because we read the notes?"**

*Good looks like:* **109 eligible without NLP → 140 with NLP = +31 patients (+28.4%)**, of which
`biomarker_source = 'nlp'` are invisible to structured-only screening. This is the headline — say these
numbers in the room.

---

### 5. Measure the extraction with MLflow  *(nb 07 · signposted)*
> **"In a serverless notebook, score the `ai_query` extraction against the structured biomarkers as ground truth across two prompts (terse vs. careful) × two models, logging accuracy to MLflow so I can compare prompts, models, and error patterns."**

*Good looks like:* 4 runs (2 prompts × 2 models) in the Experiments UI, a leaderboard, and an error
table. On the clean both-agree goldset the runs may all score ~100% (ties) — to get real contrast, seed
a few **ambiguous notes** (IHC 2+, borderline ER) first. MLflow Python needs a notebook on serverless,
not this SQL chat.

---

### 6. (Optional) Register a clinical model to UC  *(nb 05)*
> **"In a serverless notebook, register `emilyalsentzer/Bio_ClinicalBERT` to Unity Catalog via MLflow as a note-embedding model, score the notes with `mlflow.pyfunc.spark_udf` (stay in Spark), and demo cosine-similarity 'find similar notes'."**

*Good looks like:* `clinicalbert_note_embedder` in UC + 768-dim embeddings + a sensible top-3 similar
notes. **If HF egress or serving is blocked, skip it** — nothing downstream depends on it (the gold
fusion uses `ai_query`, not ClinicalBERT). Expected in a gated/security-first workspace; don't let it
block the track.

---

### 7. Let a coordinator self-serve — build a Genie space  *(nb 08)*
> **"Read and follow the `prompt-to-genie` skill, then build a Genie space over `gold_trial_prescreen` + `gold_unified_biomarker_profile` so a non-technical coordinator can ask trial-eligibility questions in natural language."**

*Good looks like:* the space answers *"How many Trial A–eligible patients were found only through
pathology-note NLP?"* → **31**, matching your verify SQL. If the number is off, add the trusted example
SQL and confirm the table/column comments ran (comments are Genie's main signal). Any team can install
`prompt-to-genie` at the workspace level — see the README.

---

### 🧩 Now design your own (the open part)
You have an audited, self-serve pre-screen — take it further:

- *"Add a third trial with its own eligibility rules and regenerate the cohort."*
- *"Seed ambiguous pathology notes and rerun the MLflow eval so the prompt/model contrast is real."*
- *"Build a coordinator app (or an agent) over `gold_trial_prescreen` that shows the eligible list with a provenance badge per patient — structured / both / NLP-recovered."* (See `09_app_TODO.py` + `STRETCH.md`.)

If the team stalls, the safety net is this kit's `notebooks/` and `reference/ANSWER_KEY.md` — reveal
them late on the learnable core (`ai_query` prompt, the fusion), and lead with what the team builds.
