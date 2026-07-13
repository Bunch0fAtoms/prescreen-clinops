# 💬 Genie Code: starter prompts (ML / clinical-trial pre-screening)

**ML session · Genie Code over the governed OMOP foundation**

The build is **free-form**. The foundation is already up. The 6 OMOP tables are present and read-only.
From here **you design the pre-screening solution your team wants to build.** You start from those 6
tables and **build the structured silver features yourself** (that is part of your build, notebook 02),
then move to the notes-only gap and the `ai_query` recovery. These are **starter prompts**, the same
ones validated end-to-end, but they're a starting line, not a script. Change them, combine
them, or ask your own.

> **Genie Code is what you demonstrate here.** Drive the whole build from the Genie Code chat: paste one
> prompt at a time, **review the diff before you Accept** (never "Accept all"), and let it **persist work
> as real notebooks or pipeline SQL files**, not scratch. The chat runs on a SQL warehouse, so SQL runs
> inline. When a step needs Python, like the EDA charts, Genie Code writes and runs it in a serverless
> notebook it creates for you. That is still Genie Code doing the work, and it is still the thing you are
> showing. **The one thing Genie Code cannot do is register the Hugging Face model to Unity Catalog
> (notebook 05). For that single step you open the pre-built notebook yourself. See prompt 6a.** The
> pre-built notebooks in this kit are a safety net if a team stalls, not the demo. Point Genie Code at the
> right page for an edit to land.

> **The synthetic cohort buckets (authoritative, Genie Code reads these from `ADAPTATION_FACTS`):**
> both-agree = person_id 1-180, **notes-only = 181-240** (the ones structured SQL misses), structured-
> only = 241-300. Primary FM endpoint = `databricks-claude-haiku-4-5`.

> **Synthetic data only, everything UC-scoped, governance visible** (the gold layer carries a
> `biomarker_source` audit column). No `hive_metastore`, no real PHI.

---

### 0. Point Genie Code at your data (do this first, once)
A fresh Genie Code chat does not know your layout, so tell it once at the top of the chat. The 6 OMOP
tables were stood up by the shared foundation and are **read-only** in `<catalog>.clinops_foundation`.
Everything **you** build goes in **your own** schema, `<catalog>.clinops_ml`.
> **"For this whole session: the 6 read-only OMOP source tables (`person`, `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, `note`) live in `<catalog>.clinops_foundation`. Never write there. Create and write everything I build into my own schema `<catalog>.clinops_ml`. Start by running `USE CATALOG <catalog>; USE SCHEMA clinops_ml;`, and always reference the source tables fully-qualified as `<catalog>.clinops_foundation.<table>`."**

*Replace `<catalog>` with your team's catalog (the one the shared foundation landed the OMOP tables in).*
Everything below reads the foundation tables and writes to your own schema. The whole track is
self-contained on those 6 tables; you never depend on another group's output.

---

### 1. Explore the cohort with Python visuals, then name the gap  *(nb 01 / 03)*
Spend real time here. A team that can see its data asks better questions of it. This is also a teaching
moment. Databricks notebooks run Python, and Python draws clear, labeled charts with `matplotlib`,
`seaborn`, and `plotly`, not just R. If you think of charts as an R-only job, this is where that
changes. The pattern is simple: aggregate in SQL or Spark first, then pull the small result back
with `.toPandas()` and plot it. The cohort is tiny (300 patients), so the round-trip costs nothing.

> ⚙️ **Still Genie Code.** Charts are Python, and the Genie Code chat runs SQL inline, so Genie Code
> writes the charts into a serverless notebook it creates and runs for you. You are driving Genie Code
> the whole time, not hand-building a notebook. Python, right here through Genie Code, draws these
> visuals, not only R.

#### 1a. Profile the tables (quick first look)
> **"Profile the 6 OMOP tables: row counts, column names and types, and null rates on the key columns. Show me one sample row per table so I can see the shape of the data."**

*Good looks like:* person 300, note 300, all 6 tables present, and the team can say what each table holds.

#### 1b. Build the cohort visuals in Python (the teaching moment)
> **"Create a serverless notebook that builds a small set of labeled Python charts so I can understand the cohort. Aggregate each one in SQL or Spark first, then `.toPandas()` and plot with matplotlib or seaborn. Title every chart and label the axes. Build four: (1) a histogram of age at diagnosis; (2) a bar chart of AJCC stage mix, Stage I through Stage IV; (3) a bar chart of menopausal status; (4) a grouped bar of HER2, ER, and PR showing Positive vs Negative counts. Add a one-line takeaway under each chart."**

*Good looks like:* four clean, titled Python charts in the notebook. The team can read the cohort at a
glance: the age skew, the stage mix, the menopausal split, and the biomarker balance. State it plainly:
Python drew these, in the same notebook as the SQL, with no R required.

#### 1c. Name the gap, and chart it (the punchline)
> **"Classify every patient by where their biomarker evidence lives: `both` (a structured measurement and a pathology note), `structured-only`, or `notes-only` (a note but no structured measurement). Count patients per bucket, then plot the three buckets as a bar chart. Tell me the notes-only number, that is the gap we are about to close."**

*Good looks like:* the three buckets read ≈ **180 / 60 / 60**, and the bar chart makes the ~60 notes-only
patients impossible to ignore. The team can say it out loud: *"~60 patients are invisible to SQL."* That
chart is the motivation for everything that follows. Make sure it lands before moving on.

---

### 🔐 Governance checkpoint (right after EDA): create a Genie space and watch the controls flow  *(uses the `prompt-to-genie` skill)*
Do this early, right after the EDA. Have Genie Code stand up a
Genie space now, over the OMOP foundation tables and any structured silver you have built. The value is
not the space itself. It is that you get to watch how Unity Catalog (UC) permissions reach the
end user through it.

**The governance lesson:** a Genie space does not add a new place to secure. It inherits the
permissions of the tables it sits on, which you already set. When a user asks a question, Genie
generates SQL and runs it as that user. UC then applies that user's grants, column masks, and row
filters at query time. So each person sees only what the source tables already allow.
Keep two controls straight:
- **Who can open the space** is space-level sharing, a Genie setting.
- **What data they see inside it** is inherited from the source tables and validated at runtime by UC, on
  every query. This is the governance-relevant one, and it is already handled upstream.

> **"Read and follow the `prompt-to-genie` skill, then create a Genie space over my OMOP foundation tables (and the structured silver, if built) so a non-technical user can ask questions in plain language. Add a few sample questions about the cohort. Keep it read-only and Unity-Catalog-scoped."**

> 🔎 **What to look for at runtime.** Ask the space a question, then confirm the query ran
> with the asking user's identity, and that a column mask or row filter set on a source table still
> applies inside the space. If you later tighten a grant or add a mask on a source table, the
> space reflects it on the next question, with no change to the space. That is the whole idea: govern the
> tables, and every consumer, Genie included, follows.

*Good looks like:* a working Genie space you can query, and a takeaway said out loud:
"Genie spaces are not a separate governance burden. They inherit the source permissions we already set,
enforced at runtime by the caller's credentials." This is the same skill you use in section 7 to build
the polished coordinator space over the final gold cohort. Building one now lets you study the
access model early, before the `ai_query` work.

---

### 2. Recover the notes-only patients with `ai_query`  *(nb 04 · the hero moment)*
> **"Extract HER2 / ER / PR / menopausal status / AJCC stage from `note.note_text` using `ai_query` with `databricks-claude-haiku-4-5`, and write the results to `silver_nlp_biomarkers` with a `'nlp'` source literal. Use constrained decoding so the output is clean JSON, and recover the notes-only patients (181-240)."**

*Good looks like:* `silver_nlp_biomarkers` = **240 rows**, all ~60 notes-only patients recovered, ~100%
fill rate.

> ⚠️ **The classic gotcha (plumbing, reveal early):** without `responseFormat` the model wraps its
> answer in ```` ```json ```` fences and `from_json` returns NULL for **every** row. Fixes: pass
> `responseFormat` (constrained decoding) and parse with the **flat** schema via `from_json`; the
> DDL form allows only one top-level field, so wrap as `STRUCT<result:STRUCT<...>>`. And because this is
> a STREAMING TABLE, **full-refresh** it after fixing the SQL or the earlier NULL rows persist. The
> prompt *wording* is your learnable bit. The response-shape fix is on the cheat-sheet in nb 04.

---

### 3a. Build your own trials catalog: trials are data, not code  *(nb 06)*
> **"Create a small `trial_criteria` table in my schema that holds the trials as DATA, one row per trial, so adding a trial later is a new row and not new SQL. Columns: `trial_id`, `trial_name`, `req_sex`, `age_min`, `age_max`, `req_her2`, `req_er`, `req_pr`, `req_menopausal`, `req_no_prior_anti_her2`. Seed two rows: Trial A, HER2-positive (`req_her2='Positive'`, `req_no_prior_anti_her2=true`, age 18-75); Trial B, ER+/HER2−/postmenopausal (`req_er='Positive'`, `req_her2='Negative'`, `req_menopausal='Postmenopausal'`, age 18-75). Leave every criterion a trial does not constrain as NULL. Show me the table before you run it."**

*Good looks like:* a 2-row `trial_criteria` table in **your** schema, where a NULL `req_*` means "this
trial does not constrain that field." This is your eligibility contract. The pre-screen in 3b joins it
**generically**, so it never hardcodes Trial A or Trial B. Adding a trial is a new row here, full stop.

---

### 3b. Fuse structured and NLP, then screen against your catalog  *(nb 06)*
> **"Build `gold_unified_biomarker_profile`: FULL OUTER JOIN the structured silver and `silver_nlp_biomarkers` (dedup NLP to one row per person via ROW_NUMBER on note_id) on person_id, `COALESCE` each biomarker, and add a `biomarker_source` audit column = both / structured / nlp. Then build `gold_trial_prescreen` by JOINING the unified profile, demographics, and prior therapy against MY OWN `trial_criteria` table (from 3a), a GENERIC eligibility match, NOT hardcoded Trial A/B. The rule: a patient qualifies for a trial when, for every non-NULL `req_*` criterion the patient's value matches, AND age BETWEEN `age_min` AND `age_max`. A NULL `req_*` means that trial does not constrain that field, so it passes. Sex match is case-insensitive (the data stores `FEMALE`). Emit one row per (patient, trial) with an eligible boolean and a plain-English reason. Show me the files before you run them."**

*Good looks like:* unified profile by source = **both 180 / nlp 60 / structured 60**. The generic join
reproduces the validated numbers with **no per-trial code**: **Trial A 140**, **Trial B 70**, and the
**NLP-recovered patients preserved (+31 for Trial A, +14 for Trial B)**. **Schema facts to feed it:** `menopausal_status` and `ajcc_stage`
live on the biomarker tables (not `silver_demographics`, which has only `gender`, `age_at_dx_years`);
prior-therapy column is `prior_anti_her2`; join `trial_criteria`'s
`req_sex`/`req_her2`/`req_er`/`req_pr`/`req_menopausal`/`req_no_prior_anti_her2` against the matching
patient columns. Use `CREATE OR REFRESH MATERIALIZED VIEW`. If Genie Code reaches for `CASE WHEN trial_id
= 'A' …`, that's **the redirect**. The whole point is that the criteria table drives eligibility, so
adding a trial is a new row in `trial_criteria`, not new SQL. Trial C (triple-negative) is exactly that,
one more row screened by the same rule.

---

### 3c. Build the per-patient test timeline the app drills into  *(nb 06 · feeds the coordinator app)*
> **"Build `gold_patient_measurements`: a per-patient longitudinal test timeline from the OMOP `measurement` table. One row per (person_id, test, date) with the measured value and unit, ordered by date, so a coordinator can open a patient and see their tests over time to verify eligibility. Use the human-readable `measurement_source_value` for the test name and `measurement_date` for the timeline. Show me the file before you run it."**

*Good looks like:* one tidy longitudinal table keyed by `person_id`, sortable by `measurement_date`, with
test name, value, and unit per row. The coordinator app opens a patient and renders their HER2 / ER / PR
tests as a dated timeline. This is the "interrogate a patient" capability: the app drills into THIS
table. Confirm `measurement` has usable dates in the synthetic data; if a patient has no dated rows the
timeline is simply empty, not an error. Use `CREATE OR REFRESH MATERIALIZED VIEW`.

---

### 4. Show the payoff (the reveal)
> **"Run the numbers that prove the NLP step mattered: how many patients are Trial A-eligible WITHOUT the NLP-recovered ones vs. WITH them, and how many eligible patients exist only because we read the notes? Then, in the serverless notebook, plot a before-and-after bar chart in Python: eligible without NLP vs eligible with NLP."**

*Good looks like:* **109 eligible without NLP → 140 with NLP = +31 patients (+28.4%)**, of which
`biomarker_source = 'nlp'` are invisible to structured-only screening, plus a two-bar Python chart that
drives the +31 home. This is the headline. Say these numbers, and show that chart.

---

### 5. Measure the extraction, with Genie Code  *(the SQL accuracy check)*
> **"Score the `ai_query` extraction against the structured biomarkers as ground truth. Compare two prompts (terse vs. careful) side by side, and show me each prompt's accuracy plus the rows where they disagree, all in SQL."**

*Good looks like:* a small accuracy table Genie Code builds inline, one row per prompt, showing which
prompt reads the notes better and where the misses cluster (HER2 IHC 2+ is the usual culprit). The
foundation plants a **hard-case band** (person 61-90) with equivocal-but-resolvable notes (HER2 IHC 2+
with a reflex FISH ratio, ER-low-positive), so the careful prompt visibly beats the terse one and the
disagreement rows are real. Point the accuracy check at those patients to make the contrast pop.

> ⚙️ **Want the full logged MLflow experiment (runs, leaderboard, traces)?** That part is Python on
> serverless, and it is heavier than the Genie Code chat authors reliably. For the live demonstration,
> the Genie Code SQL accuracy check above makes the point: you can measure the extraction, compare
> prompts, and see the error pattern, all in the chat. (If you do want the logged experiment as a deeper
> artifact, notebook `07` builds it; treat it like the Hugging Face step, a notebook you run, not a Genie
> Code build.)

---

### 6. Bring your own Hugging Face model to Unity Catalog, then use it for similarity matching  *(a common ML-team ask · notebook 05, then Genie Code)*
Running your own models from Hugging Face is a first-class part of the build,
not a side trip. The teaching moment has two halves. First, a language model from Hugging Face becomes a
**governed Unity Catalog asset**, versioned, permissioned, and lineage-tracked like a table. Second, its
output does real work: the team uses the model's embeddings for **similarity matching**, to find patients
whose pathology notes are clinically similar. That is a cohort-discovery signal layered on top of the
`ai_query` pre-screen, and the team builds it with Genie Code.

#### 6a. Register the Hugging Face model to UC (the bring-your-own-model teaching moment)  *(the notebook, not Genie Code)*
> **"In a serverless notebook, register `emilyalsentzer/Bio_ClinicalBERT` to Unity Catalog via MLflow as a note-embedding model, score every pathology note with `mlflow.pyfunc.spark_udf` (stay in Spark), and write the 768-dim vectors to `silver_clinicalbert_note_embeddings`."**

*Good looks like:* `clinicalbert_note_embedder` registered in UC (visible in Catalog Explorer, with
lineage from `note` to the embeddings table), and `silver_clinicalbert_note_embeddings` written with one
768-dim vector per note. The takeaway to say out loud: a Hugging Face model is now a governed UC asset,
and no note text left the platform to produce it.

> ⚙️ **UI or notebook? Use the notebook, not Genie Code.** This registration is the one step Genie Code
> cannot do. Because the chat runs on a SQL warehouse, it **cannot import a Hugging Face model and
> register it to Unity Catalog as an MLflow model**. That flow needs Python on serverless with
> `%pip install transformers torch` and a `restartPython`, as validated: Genie Code will not
> build it. So open the pre-built **`05_clinicalbert_mlflow_uc`** notebook, attach **serverless**, and
> **Run All** (or run it as a job). **Run it only if your workspace has Hugging Face egress and model
> serving.** If egress is blocked, you lose the similarity-matching enrichment in 6b, but not the core
> pre-screen, which runs on `ai_query`.

#### 6b. Use the embeddings for similarity matching (Genie Code, back in SQL)
> **"Using `silver_clinicalbert_note_embeddings`, build a note-similarity search: for a given patient, return the top-5 other patients whose pathology notes are most similar by cosine similarity over the embedding vectors. Then materialize `gold_similar_patients` (one row per patient with their nearest neighbors and similarity scores) so we can find more candidates like a known-eligible patient."**

*Good looks like:* once the embeddings exist, Genie Code does this **entirely in SQL**, no Python needed,
using array math for the cosine similarity. The team can ask "who looks like patient X?" and get
clinically sensible matches. This is how the Hugging Face output earns its place in the applied AI build:
it powers cohort discovery that extends the pre-screen, surfacing patients a rules match alone would
miss. (Our coordinator app can then read `gold_similar_patients` to offer "find similar patients," but
the team produces the table here, with Genie Code.)

---

### 7. Let a coordinator self-serve: build a Genie space  *(nb 08)*
> **"Read and follow the `prompt-to-genie` skill, then build a Genie space over `gold_trial_prescreen` + `gold_unified_biomarker_profile` so a non-technical coordinator can ask trial-eligibility questions in natural language."**

*Good looks like:* the space answers *"How many Trial A-eligible patients were found only through
pathology-note NLP?"* → **31**, matching your verify SQL. If the number is off, add the trusted example
SQL and confirm the table/column comments ran (comments are Genie's main signal). Any team can install
`prompt-to-genie` at the workspace level, see the README.

---

### 🧩 Now design your own (the open part)
You have an audited, self-serve pre-screen. Take it further:

- ⭐ **Point the whole build at your own OMOP data.** With the `prescreen-clinops-adaptation` skill
  installed, ask Genie Code to flip the reads from the synthetic foundation schema to your own OMOP
  catalog and schema. The tables follow the OMOP Common Data Model (a public open standard), so the
  6 table names are identical and the silver/gold/NLP queries run unchanged; the skill also strips
  the synthetic-only `person.is_high_profile` references. See
  `STRETCH.md`.
- *"Add another trial by inserting a row into my `trial_criteria` (e.g. triple-negative: ER−/PR−/HER2−), then re-run the pre-screen and watch the cohort update with no SQL change."*
- *"Seed ambiguous pathology notes and rerun the MLflow eval so the prompt/model contrast is real."*
- *"Build a coordinator app (or an agent) over `gold_trial_prescreen` that shows the eligible list with a provenance badge per patient: structured / both / NLP-recovered."* (See `09_app_TODO.py` + `STRETCH.md`.)

If the team stalls, the safety net is this kit's `notebooks/` and `reference/ANSWER_KEY.md`. Reveal
them late on the learnable core (`ai_query` prompt, the fusion), and lead with what the team builds.
