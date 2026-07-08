# Applied AI review: presenter run-of-show

**Goal.** Walk Fred Hutch through the clinical-trial pre-screening solution we prepared, so they see
how it was planned and leave understanding the moving parts they can reuse. This is a teaching
review, not a live build. Open the completed notebooks in
`reference/completed_notebooks/` and narrate. The team already did the hard build on Day 1; today we
show the finished arc and the ideas behind it.

**The story in one line.** A structured SQL query misses the patients whose biomarker status was only
ever written into a free-text pathology note. We recover those patients with a Foundation Model,
fuse the two sources with a full audit trail, measure the extraction the way you would measure any
model, and hand a coordinator a plain-English app. The headline: **structured SQL found 109 Trial A
patients; adding NLP found 140, a gain of 31 real patients** who would otherwise be invisible.

**What to have open.** The completed notebooks in `reference/completed_notebooks/`, the app in
`app/`, and a browser tab on the workspace so you can show the MLflow Experiments and Traces tabs and
the Serving page.

---

## Segment 1: frame the problem (notebook 00, 2 minutes)

Open `00_START_HERE`. Show the three biomarker-source groups: 180 patients whose biomarkers live in
both the structured tables and the notes, 60 whose biomarkers live **only** in a note, and 60
structured-only. Say the plain sentence: "The 60 notes-only patients are real, potentially eligible
people. A query over the `measurement` table returns zero of them." That is the whole reason the rest
of the session exists.

## Segment 2: the data and the gap (notebooks 01 and 03, 3 minutes)

Open `01_data_foundation_omop`. Point out it reads the 6 OMOP tables read-only from the shared
foundation, the same shape as Fred Hutch's real `curated_omop.omop`. Run the planted-cohort counts so
the room sees the trial cohorts are really there.

Jump to `03_exploratory_data_analysis`, the classification cell. Land the number: about 60 patients
have a pathology note but no structured biomarker row. Then show the peek at a notes-only note so the
room reads the free text a pathologist actually wrote. This sets up why a keyword search fails.

(Notebook 02 builds the silver feature views. Mention it in passing; the pivot is a standard SQL
skill and not the headline.)

## Segment 3: ai_query, the GenAI core (notebook 04, 5 minutes) 🧠

This is the first big teaching beat. Open `04_nlp_biomarker_extraction`.

- Show the single-note `ai_query` call first. The point to make: **the model is called from SQL**.
  No model hosting, no Python serving code, and the call runs inside Unity Catalog with full lineage.
- Explain the one real gotcha, the `responseFormat` argument. Without it the model wraps its answer in
  markdown code fences and `from_json` returns NULL for every row. With it, you get clean typed columns.
  This is the kind of practical detail Fred Hutch will hit, so it is worth 30 seconds.
- Run the recovery-count cell. Say: "We just recovered the ~60 patients structured SQL could never see,
  in one SQL function."

## Segment 4: HuggingFace to Unity Catalog, then a serving endpoint (notebook 05, 6 minutes) 🧬🌐

Open `05_clinicalbert_mlflow_uc`. Frame it as the **bring-your-own-model** story, distinct from nb 04.

- Walk the pyfunc wrapper briefly: ClinicalBERT (a clinical HuggingFace model) becomes a mean-pooled
  note embedder. Weights are packaged as MLflow artifacts, so scoring nodes never re-download from the
  internet. That is the governance-friendly choice, no external calls at inference.
- Show the `spark_udf` batch scoring: the model runs on every executor, the note text never leaves
  Spark, and the read, the model, and the written table are all Unity Catalog objects, so lineage is
  automatic.
- **The serving-endpoint section is the second big beat.** Explain the distinction plainly: a model
  registered to Unity Catalog is not, by itself, callable from SQL. `ai_query` invokes a **serving
  endpoint** by name. The Foundation Models in nb 04 work from SQL because they are pre-provisioned
  endpoints. Your own model needs an endpoint created first. Show the `create_endpoint` cell, then the
  Serving page in the workspace. If an endpoint is already warm, query it live; if not, explain it
  provisions in a few minutes and scales to zero when idle.
- Close the loop: once served, ClinicalBERT is reachable from SQL via `ai_query` too. Batch and online
  are two front doors to one governed model version.

## Segment 5: fuse and audit (notebook 06, 4 minutes)

Open `06_gold_unified_prescreen`. Two ideas to land:

- **The audit column.** We prefer the structured lab value, fall back to the note-derived value, and
  record which one we used in `biomarker_source`. The model never silently overwrites a lab result,
  and every note-derived decision is flagged for a human to confirm. That is what makes this defensible
  in a clinical setting.
- **Trials are data, not code.** The pre-screen joins a trials catalog, one row per trial, one column
  per criterion, NULL meaning "unconstrained". Adding a trial is a data change, not a code change. Note
  that the Data Engineering team builds this same catalog from a live feed; repointing to their table
  is the cross-team stretch.

Run the payoff cell. Land the numbers again: Trial A = 140, Trial B = 56, and 31 patients recovered
only from the notes.

## Segment 6: evaluation, traces, judges, custom metrics (notebook 07, 7 minutes) 🧠📊

This is the third big beat, and the one Fred Hutch cares about given their test-before-expand posture
on AI. Open `07_mlflow_evaluation_runs`.

The contrast comes from a **hard-case band** the foundation plants (person 61-90): both-agree patients
whose structured value is the definite gold label, but whose pathology note is written equivocally
(HER2 IHC 2+ with a reflex FISH ratio, ER-low-positive). Those are the cases where a careful prompt and
a terse prompt disagree, so the eval has something real to show. No cohort count changes (140 / 56 / +31
all hold), because the structured value still wins in the gold layer.

- **Sections 1 to 5, the transparent path.** We treat the prompt like a model: hold it to a
  ground-truth test set (the 180 both-agree patients), score 2 prompts against 2 models, log every run
  to MLflow, and pick a winner on a measured number. Show the leaderboard (a real spread now, not a
  tie) and the error table (it has rows). Make the clinical point: the misses cluster on the equivocal
  HER2 IHC 2+ cases, and a miss that lands on "Unknown" is far safer than a confident wrong call.
- **Sections 6 to 8, the managed path with `mlflow.genai.evaluate()`.** This is where traces, the
  LLM-as-judge, and the custom metrics live. The eval runs on the hard-case band, once for the terse
  prompt and once for the careful prompt. Run both, then open the workspace:
  - **The contrast**: the careful prompt scores higher on `her2_exact_match` and `biomarker_agreement`.
    Same model, same notes, only the instruction changed. That is the point Sita wants to see.
  - **Traces tab**: open the terse run, find a HER2 IHC 2+ patient (reflex FISH ratio near 2.1). Show
    that the model answered "Unknown" because it stopped at "equivocal". Open the same patient in the
    careful run: it resolved to the correct call. That side-by-side is the audit trail.
  - **The LLM-as-judge**: the `valid_status_values` scorer is graded by an LLM against a plain-language
    rule, with a rationale per row. It catches quality issues a simple equality test cannot.
  - **The custom metrics**: `her2_exact_match` and `biomarker_agreement` are plain Python functions we
    plugged in, aggregated right beside the judge.

The message: you can start with numbers you compute by hand for full transparency, and graduate to a
managed harness that gives you per-row traceability, LLM judges, and your own metrics, all in one tool.
The equivocal cases are where the risk lives, and this is how you catch and measure it.

## Segment 7: self-serve with Genie (notebook 08, 2 minutes)

Open `08_genie_space_setup`. Show the table comments (Genie's main accuracy signal) and the verified
queries. If a Genie space is already built, ask it the headline question live: "How many patients are
eligible for Trial A, and how many were found only in the notes?" Confirm it returns 140 and 31.

## Segment 8: the coordinator app (Sita's ask, 4 minutes) 🚀

Open the deployed app (or run `app/` locally). Walk it as a coordinator would:

- Pick a trial from the sidebar.
- Read the header: total eligible, the count recovered via NLP, and the structured-only baseline,
  framed as the uplift.
- Point at the **provenance badge** on each patient: green "Structured" versus amber "NLP-recovered".
  Say: "This badge is the whole solution, made visible. A coordinator sees exactly which patients came
  from a note and should have that note confirmed before enrolling."
- Drill into one patient to show the test timeline.

## Closing and the governance thread

Tie it back to what Fred Hutch asked for. Every step ran inside Unity Catalog: the model calls, the
embeddings, the gold tables, the app. Nothing left the platform, lineage is automatic, and every
AI-derived biomarker is flagged for human review. The solution recovered real patients a structured
pipeline would miss, and we can prove the extraction quality with a test set, traces, and an LLM judge.
That is a mature, measurable, governed pattern, not a demo that only works on slides.

**Numbers to have memorized:** 300 patients, 60 notes-only, Trial A 109 structured to 140 with NLP
(a gain of 31), Trial B 56.
