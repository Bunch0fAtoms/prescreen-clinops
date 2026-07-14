# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 06 · GOLD + PRE-SCREEN · 🛠️ YOU BUILD THE FUSION</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🏅 Gold layer: one audited cohort the coordinator can screen</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Fuse the structured biomarkers with the NLP-recovered ones into a single source of truth,
# MAGIC     then compute Trial A &amp; Trial B eligibility with a plain-English reason for every patient.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## The gold layer is the answer the coordinator actually reads
# MAGIC
# MAGIC | Gold table | What it is |
# MAGIC |---|---|
# MAGIC | `gold_unified_biomarker_profile` | One HER2/ER/PR row per patient, structured **or** NLP-recovered, with an audit column |
# MAGIC | `gold_trial_prescreen` | Eligibility for Trial A & Trial B + a human-readable reason per patient |
# MAGIC
# MAGIC ### The COALESCE-with-audit-column pattern (the heart of this notebook)
# MAGIC
# MAGIC Two sources of biomarker truth: structured `silver_biomarker_profile` and the notes read by
# MAGIC `ai_query` (`silver_nlp_biomarkers`). The rule is simple and defensible:
# MAGIC
# MAGIC 1. **Prefer the structured value**, it's the lab's recorded result.
# MAGIC 2. **Fall back to the NLP value** when no structured row exists (the notes-only patients).
# MAGIC 3. **Record which source we used** in a `biomarker_source` column, so any eligibility decision
# MAGIC    traces back to structured data or an AI reading of a note.
# MAGIC
# MAGIC That audit column is what makes this trustworthy in a clinical setting. The AI never silently
# MAGIC overwrites a lab value, and every notes-derived decision is flagged for human review.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ `gold_unified_biomarker_profile`: fuse structured + NLP, keep the audit trail
# MAGIC
# MAGIC A **FULL OUTER JOIN** on `person_id` keeps every patient in *either* source. For each marker,
# MAGIC `COALESCE(structured, nlp)`, structured wins, NLP fills the gap. `biomarker_source` is
# MAGIC `'structured'` whenever a structured row existed, else `'nlp'`.

# COMMAND ----------

# DBTITLE 1,TODO: gold_unified_biomarker_profile (COALESCE + source audit), YOU BUILD THIS
# MAGIC %sql
# MAGIC -- TODO (you build this): CREATE OR REPLACE TABLE gold_unified_biomarker_profile.
# MAGIC -- Inputs: silver_biomarker_profile (alias s, structured) FULL OUTER JOIN
# MAGIC --         silver_nlp_biomarkers   (alias n, nlp) ON s.person_id = n.person_id.
# MAGIC -- Produce one row per patient:
# MAGIC --   person_id        = COALESCE(s.person_id, n.person_id)
# MAGIC --   her2_status      = COALESCE(s.her2_status, n.her2_status)   -- structured wins
# MAGIC --   er_status, pr_status = same COALESCE pattern
# MAGIC --   biomarker_source = CASE WHEN s.person_id IS NOT NULL THEN 'structured' ELSE 'nlp' END
# MAGIC -- WHY FULL OUTER + COALESCE (not UNION): a union would make TWO rows for 'both' patients and force
# MAGIC --   a de-dup; the outer join gives exactly one row and lets you express the precedence rule in SQL.
# MAGIC --   The notes-only patients (181 to 240) arrive tagged biomarker_source='nlp'.

# COMMAND ----------

# DBTITLE 1,How many patients came from each source? (PRE-BUILT check)
# MAGIC %sql
# MAGIC SELECT biomarker_source, COUNT(*) AS patients
# MAGIC FROM gold_unified_biomarker_profile GROUP BY biomarker_source ORDER BY biomarker_source;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ `gold_trial_prescreen`: generic, catalog-driven eligibility + a reason
# MAGIC
# MAGIC Do NOT hardcode Trial A and Trial B as literal rules. Trials are **data** now, in
# MAGIC `silver_trial_criteria`, a small trials catalog we seed just below (PRE-BUILT) so this notebook is
# MAGIC self-contained. This pre-screen joins against whatever rows that table holds, so adding a trial is a
# MAGIC data change, not a code change here.
# MAGIC
# MAGIC **The generic rule.** A patient qualifies for a trial when, for every `req_*` criterion that is
# MAGIC NON-NULL, the patient's value matches, AND `age_at_dx_years` is BETWEEN `age_min` AND `age_max`. A
# MAGIC NULL `req_*` column means the trial does not constrain that field. One rule, every trial.
# MAGIC
# MAGIC **Shape: LONG (one row per person per trial).** Trials are data-driven and growing, so a wide
# MAGIC one-column-per-trial table would need a schema change per trial. The long shape
# MAGIC `(person_id, trial_id, eligible, reason, ...)` never changes as trials come and go, and the app
# MAGIC filters by `trial_id`. We also publish a small backward-compatible wide view so the current app
# MAGIC keeps working during the cutover.
# MAGIC
# MAGIC | Catalog `req_*` column | Patient field it matches |
# MAGIC |---|---|
# MAGIC | `req_sex` | `gender` |
# MAGIC | `req_her2` / `req_er` / `req_pr` | `her2_status` / `er_status` / `pr_status` |
# MAGIC | `req_menopausal` | `menopausal_status` |
# MAGIC | `req_no_prior_anti_her2 = true` | patient's `prior_anti_her2` must be `false` |
# MAGIC
# MAGIC `min_ecog` is carried through for the app to show, but not matched yet (patients have no ECOG field).

# COMMAND ----------

# DBTITLE 1,Seed the trials-as-data catalog: silver_trial_criteria (PRE-BUILT)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE silver_trial_criteria
# MAGIC COMMENT 'Trials-as-data catalog: one row per trial, one req_* column per criterion. NULL req_* = unconstrained.'
# MAGIC AS
# MAGIC SELECT * FROM VALUES
# MAGIC   -- trial_id, trial_name, status, req_sex, age_min, age_max, req_her2, req_er, req_pr,
# MAGIC   --   req_menopausal, req_no_prior_anti_her2, min_ecog, eligibility_text
# MAGIC   ('A', 'HER2-Positive Breast Cancer Study', 'Recruiting', 'Female', 18, 75,
# MAGIC    'Positive', CAST(NULL AS STRING), CAST(NULL AS STRING),
# MAGIC    CAST(NULL AS STRING), true, 1,
# MAGIC    'HER2-positive breast cancer, age 18-75, no prior anti-HER2 therapy.'),
# MAGIC   ('B', 'ER-Positive / HER2-Negative Study', 'Recruiting', 'Female', 18, 75,
# MAGIC    'Negative', 'Positive', CAST(NULL AS STRING),
# MAGIC    'Postmenopausal', CAST(NULL AS BOOLEAN), CAST(NULL AS INT),
# MAGIC    'ER-positive, HER2-negative, postmenopausal breast cancer, age 18-75.'),
# MAGIC   ('C', 'Triple-Negative Breast Cancer Study', 'Recruiting', 'Female', 18, 75,
# MAGIC    'Negative', 'Negative', 'Negative',
# MAGIC    CAST(NULL AS STRING), CAST(NULL AS BOOLEAN), CAST(NULL AS INT),
# MAGIC    'Triple-negative breast cancer (HER2-, ER-, PR-), age 18-75.')
# MAGIC AS t(trial_id, trial_name, status, req_sex, age_min, age_max, req_her2, req_er, req_pr,
# MAGIC       req_menopausal, req_no_prior_anti_her2, min_ecog, eligibility_text);

# COMMAND ----------

# DBTITLE 1,The patient + trial join is PRE-BUILT, you write the generic match + reason
# MAGIC %sql
# MAGIC -- The two CTEs below are given to you: `patient` (one row per patient with all comparable fields)
# MAGIC -- and `evaluated` (CROSS JOIN patient × silver_trial_criteria, with one boolean per criterion
# MAGIC -- already computed using the NULL-means-unconstrained rule). Your TODO is the final SELECT: the
# MAGIC -- `eligible` boolean (AND of all the ok_* flags) and the plain-English `reason`.
# MAGIC --
# MAGIC -- CREATE OR REPLACE TABLE gold_trial_prescreen
# MAGIC -- COMMENT 'Per-person per-trial eligibility via a generic join to silver_trial_criteria (NULL req_* = unconstrained). LONG shape. biomarker_source + min_ecog carried through.'
# MAGIC -- AS
# MAGIC -- WITH patient AS (
# MAGIC --   SELECT b.person_id, d.gender, d.age_at_dx_years,
# MAGIC --          b.her2_status, b.er_status, b.pr_status, b.menopausal_status, b.ajcc_stage,
# MAGIC --          b.biomarker_source, COALESCE(t.prior_anti_her2, false) AS prior_anti_her2
# MAGIC --   FROM gold_unified_biomarker_profile b
# MAGIC --   INNER JOIN silver_demographics d ON b.person_id = d.person_id
# MAGIC --   LEFT JOIN silver_prior_therapy t ON b.person_id = t.person_id
# MAGIC -- ),
# MAGIC -- evaluated AS (
# MAGIC --   SELECT p.*, c.trial_id, c.trial_name, c.status AS trial_status, c.eligibility_text, c.min_ecog,
# MAGIC --          c.age_min, c.age_max, c.req_sex, c.req_her2, c.req_er, c.req_pr, c.req_menopausal,
# MAGIC --          c.req_no_prior_anti_her2,
# MAGIC --          -- case-insensitive: raw OMOP stores 'FEMALE', the catalog says 'Female'
# MAGIC --          (c.req_sex        IS NULL OR UPPER(p.gender)     = UPPER(c.req_sex)) AS ok_sex,
# MAGIC --          (c.req_her2       IS NULL OR p.her2_status       = c.req_her2)       AS ok_her2,
# MAGIC --          (c.req_er         IS NULL OR p.er_status         = c.req_er)         AS ok_er,
# MAGIC --          (c.req_pr         IS NULL OR p.pr_status         = c.req_pr)         AS ok_pr,
# MAGIC --          (c.req_menopausal IS NULL OR p.menopausal_status = c.req_menopausal) AS ok_menopausal,
# MAGIC --          (c.req_no_prior_anti_her2 IS NULL
# MAGIC --             OR (c.req_no_prior_anti_her2 = true AND p.prior_anti_her2 = false)) AS ok_prior_anti_her2,
# MAGIC --          (p.age_at_dx_years BETWEEN c.age_min AND c.age_max) AS ok_age
# MAGIC --   FROM patient p CROSS JOIN silver_trial_criteria c
# MAGIC -- )
# MAGIC -- SELECT person_id, trial_id, trial_name, trial_status, gender, age_at_dx_years,
# MAGIC --        her2_status, er_status, pr_status, menopausal_status, ajcc_stage,
# MAGIC --        prior_anti_her2, biomarker_source, min_ecog, eligibility_text,
# MAGIC --
# MAGIC --   -- TODO (you build this): `eligible`, a BOOLEAN that is the AND of every ok_* flag:
# MAGIC --   --   ok_sex AND ok_her2 AND ok_er AND ok_pr AND ok_menopausal AND ok_prior_anti_her2 AND ok_age.
# MAGIC --   <expr> AS eligible,
# MAGIC --
# MAGIC --   -- TODO (you build this): `reason`, a CASE. When all ok_* pass, 'Eligible: ...' summarizing the
# MAGIC --   --   biomarkers the trial constrained (only the req_* that are NON-NULL) with the biomarker_source
# MAGIC --   --   in parens, e.g. 'Eligible: HER2 Positive (nlp), age 54, no prior anti-HER2 therapy'. Else name
# MAGIC --   --   the FIRST failing criterion, e.g. 'Excluded: HER2 is Negative (need Positive)'. Precedence:
# MAGIC --   --   biomarkers, then menopausal, then age, then prior therapy, then sex.
# MAGIC --   <case> AS reason
# MAGIC -- FROM evaluated;
# MAGIC --
# MAGIC -- WHY generic: Trials A and B carry criteria identical to the old hardcoded rules, so this MUST
# MAGIC -- reproduce Trial A = 140, Trial B = 70, +31 NLP-recovered for A and +14 for B. Trial C (triple-negative) is net-new.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Backward-compatible wide view (PRE-BUILT, runs once your table exists)
# MAGIC
# MAGIC The app today reads `trial_a_eligible` / `trial_b_eligible`. We pivot the long table back to a
# MAGIC one-row-per-patient view for that path; new trials stay available in the long table.

# COMMAND ----------

# DBTITLE 1,gold_trial_prescreen_wide, pivot back to trial_a_/trial_b_ columns (PRE-BUILT)
# MAGIC %sql
# MAGIC CREATE OR REPLACE VIEW gold_trial_prescreen_wide
# MAGIC COMMENT 'Backward-compatible wide view: one row per patient with trial_a_/trial_b_ columns, from the long table.'
# MAGIC AS
# MAGIC SELECT
# MAGIC   person_id,
# MAGIC   FIRST(gender)            AS gender,
# MAGIC   FIRST(age_at_dx_years)   AS age_at_dx_years,
# MAGIC   FIRST(her2_status)       AS her2_status,
# MAGIC   FIRST(er_status)         AS er_status,
# MAGIC   FIRST(pr_status)         AS pr_status,
# MAGIC   FIRST(menopausal_status) AS menopausal_status,
# MAGIC   FIRST(ajcc_stage)        AS ajcc_stage,
# MAGIC   FIRST(prior_anti_her2)   AS prior_anti_her2,
# MAGIC   FIRST(biomarker_source)  AS biomarker_source,
# MAGIC   MAX(CASE WHEN trial_id = 'A' THEN eligible END) AS trial_a_eligible,
# MAGIC   MAX(CASE WHEN trial_id = 'A' THEN reason   END) AS trial_a_reason,
# MAGIC   MAX(CASE WHEN trial_id = 'B' THEN eligible END) AS trial_b_eligible,
# MAGIC   MAX(CASE WHEN trial_id = 'B' THEN reason   END) AS trial_b_reason,
# MAGIC   MAX(CASE WHEN trial_id = 'C' THEN eligible END) AS trial_c_eligible,
# MAGIC   MAX(CASE WHEN trial_id = 'C' THEN reason   END) AS trial_c_reason
# MAGIC FROM gold_trial_prescreen
# MAGIC GROUP BY person_id;

# COMMAND ----------

# DBTITLE 1,Peek at the screened cohort, long shape (PRE-BUILT, runs once your table exists)
# MAGIC %sql
# MAGIC SELECT person_id, trial_id, trial_name, her2_status, er_status, menopausal_status,
# MAGIC        age_at_dx_years, biomarker_source, eligible, reason
# MAGIC FROM gold_trial_prescreen ORDER BY person_id, trial_id LIMIT 15;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 3️⃣ The payoff: the unified cohort is *bigger* than structured-only 🎯 (PRE-BUILT)
# MAGIC
# MAGIC If the coordinator had only the structured pipeline, every eligible patient tagged
# MAGIC `biomarker_source = 'nlp'` would be **invisible**. Count eligibility split by source.

# COMMAND ----------

# DBTITLE 1,Eligible counts, split by where the biomarker came from (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT biomarker_source,
# MAGIC   SUM(CASE WHEN trial_id = 'A' AND eligible THEN 1 ELSE 0 END) AS trial_a_eligible,
# MAGIC   SUM(CASE WHEN trial_id = 'B' AND eligible THEN 1 ELSE 0 END) AS trial_b_eligible,
# MAGIC   SUM(CASE WHEN trial_id = 'C' AND eligible THEN 1 ELSE 0 END) AS trial_c_eligible
# MAGIC FROM gold_trial_prescreen GROUP BY biomarker_source ORDER BY biomarker_source;

# COMMAND ----------

# DBTITLE 1,State the win in plain language (PRE-BUILT)
nlp = spark.sql("""
  SELECT
    SUM(CASE WHEN trial_id = 'A' AND eligible AND biomarker_source = 'nlp' THEN 1 ELSE 0 END) AS a_nlp,
    SUM(CASE WHEN trial_id = 'B' AND eligible AND biomarker_source = 'nlp' THEN 1 ELSE 0 END) AS b_nlp,
    SUM(CASE WHEN trial_id = 'A' AND eligible THEN 1 ELSE 0 END)                              AS a_total,
    SUM(CASE WHEN trial_id = 'B' AND eligible THEN 1 ELSE 0 END)                              AS b_total
  FROM gold_trial_prescreen
""").first()

show_md(f"""
<div style="background:#FFEBEE; border-left:6px solid #C8102E; padding:12px 16px; border-radius:4px">
<b>Structured SQL alone would have missed {nlp['a_nlp'] + nlp['b_nlp']} eligible patients.</b><br>
Trial A: {nlp['a_nlp']} of {nlp['a_total']} eligible patients were recovered only from the notes.<br>
Trial B: {nlp['b_nlp']} of {nlp['b_total']} eligible patients were recovered only from the notes.
</div>
<div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px; margin-top:10px">
Those <b>{nlp['a_nlp'] + nlp['b_nlp']} patients</b> are now in the unified cohort, each flagged
<code>biomarker_source = 'nlp'</code> so a coordinator knows to confirm the note before enrolling.
</div>
""")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you built:</b> a single audited gold cohort, <code>gold_trial_prescreen</code>, the
# MAGIC coordinator can query for "who is eligible, and why?", every decision traceable via
# MAGIC <code>biomarker_source</code>, and computed by one generic join so adding a trial is a data change.
# MAGIC Fusing the two biomarker sources <b>grew the eligible cohort</b>. <b>This is the end-to-end payoff.</b>
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Verify the validated numbers are preserved (PRE-BUILT: A 140 / B 70 / NLP +31 for A, +14 for B)
# MAGIC %sql
# MAGIC -- Trials A and B carry catalog criteria identical to the old hardcoded rules, so the generic join
# MAGIC -- MUST reproduce Trial A = 140, Trial B = 70, +31 NLP-recovered for A and +14 for B. Trial C is net-new.
# MAGIC SELECT trial_id,
# MAGIC        SUM(CASE WHEN eligible THEN 1 ELSE 0 END) AS eligible_patients,
# MAGIC        SUM(CASE WHEN eligible AND biomarker_source = 'nlp' THEN 1 ELSE 0 END) AS nlp_recovered
# MAGIC FROM gold_trial_prescreen GROUP BY trial_id ORDER BY trial_id;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5️⃣ `gold_patient_measurements`: a per-patient test timeline for the app (PRE-BUILT)
# MAGIC
# MAGIC The coordinator app interrogates one patient: "what tests did this patient have, and when?" This longitudinal
# MAGIC view is built straight from the raw OMOP `measurement` table, one row per result, ordered by date,
# MAGIC so the app can render a timeline. `test_name` comes from `measurement_source_value`, `value` from
# MAGIC `value_source_value` (falling back to `value_as_number` for numeric labs). `measurement_date` is
# MAGIC populated in this data, so we order by it; if a feed left it NULL we fall back to
# MAGIC `measurement_datetime`.

# COMMAND ----------

# DBTITLE 1,gold_patient_measurements, longitudinal per-patient test timeline (PRE-BUILT)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE gold_patient_measurements
# MAGIC COMMENT 'Longitudinal per-patient test timeline for the coordinator app drill-down. One row per measurement, from the raw OMOP measurement table.'
# MAGIC AS
# MAGIC SELECT
# MAGIC   person_id,
# MAGIC   COALESCE(measurement_date, CAST(measurement_datetime AS DATE)) AS measurement_date,
# MAGIC   measurement_source_value                                       AS test_name,
# MAGIC   COALESCE(value_source_value, CAST(value_as_number AS STRING))  AS value,
# MAGIC   unit_source_value                                              AS unit
# MAGIC FROM measurement
# MAGIC WHERE person_id IS NOT NULL
# MAGIC ORDER BY person_id, measurement_date;

# COMMAND ----------

# DBTITLE 1,Peek at one patient's timeline (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT person_id, measurement_date, test_name, value, unit
# MAGIC FROM gold_patient_measurements ORDER BY person_id, measurement_date LIMIT 20;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚩 Checkpoint 6: gold cohort is catalog-driven and app-ready
# MAGIC
# MAGIC - `gold_trial_prescreen` is now **LONG** (one row per person per trial), computed by a single generic
# MAGIC   join to `silver_trial_criteria`. Adding a trial is a data change: insert a row into that catalog.
# MAGIC - Trials A and B reproduce the validated numbers (**A = 140**, **B = 70**, **+31 NLP-recovered for A, +14 for B**);
# MAGIC   Trial C (triple-negative) is net-new.
# MAGIC - `gold_trial_prescreen_wide` keeps the old `trial_a_eligible` / `trial_b_eligible` shape.
# MAGIC - `gold_patient_measurements` gives the app a per-patient test timeline for the drill-down.
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[07_mlflow_evaluation_runs]($./07_mlflow_evaluation_runs)** to score the NLP extractor against ground truth with MLflow.
