# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 04 · NLP EXTRACTION · 🧠 THE GENAI CORE · COMPLETED</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧠 Reading the notes with <code>ai_query</code></div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Recover HER2 / ER / PR status from free-text pathology reports with a Foundation Model,
# MAGIC     and pull the ~60 "notes-only" patients back into the cohort that structured SQL never sees.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why SQL can't do this, but a Foundation Model can
# MAGIC
# MAGIC Notebook 03 surfaced the gap: ~**60 patients** (person 181 to 240) have their biomarker status
# MAGIC written *only* in a free-text pathology note. They have **zero** rows in `measurement`, so the
# MAGIC silver pivot (and every SQL cohort query) returns nothing for them.
# MAGIC
# MAGIC Pathologists write HER2/ER/PR a dozen different ways:
# MAGIC
# MAGIC | What the note says | Means |
# MAGIC |---|---|
# MAGIC | `HER2: Positive (3+ by IHC)` | HER2 **Positive** |
# MAGIC | `Her-2/neu overexpression confirmed: 3+` | HER2 **Positive** |
# MAGIC | `HER2/neu amplification: NOT detected (FISH ratio 1.4)` | HER2 **Negative** |
# MAGIC | `HER2 (c-erbB-2): 2+ (equivocal by IHC; FISH reflex recommended)` | HER2 **Unknown / equivocal** |
# MAGIC
# MAGIC No `LIKE '%positive%'` survives that ("NOT detected" even contains "detected"). But a Foundation
# MAGIC Model reads the line like a clinician. We call it **from SQL** with **`ai_query`**: no model
# MAGIC hosting, no Python serving code, full Unity Catalog lineage.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🔑 The pattern (read this before the calls below)
# MAGIC
# MAGIC `ai_query(endpoint, prompt, responseFormat => ...)` calls a model on each row. Two pieces work
# MAGIC together so the output is parseable:
# MAGIC
# MAGIC 1. **`responseFormat`** turns on *constrained decoding* so the model emits **clean JSON**, not
# MAGIC    `` ```json … ``` `` markdown fences. Without it, `from_json` silently returns **NULL** for every
# MAGIC    fenced row and your whole column comes back empty. (This was a real bug in the original build.)
# MAGIC 2. **`from_json`** turns that JSON string into typed columns you can select.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The one gotcha:</b> the <code>responseFormat</code> DDL form allows only <b>one</b> top-level
# MAGIC field, so it is wrapped as <code>STRUCT&lt;result:STRUCT&lt;...&gt;&gt;</code>. The model still emits the
# MAGIC flat keys, which the <code>from_json</code> schema (<code>STRUCT&lt;her2_status:STRING, er_status:STRING,
# MAGIC pr_status:STRING&gt;</code>) matches.
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC responseFormat: 'STRUCT<result:STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>>'
# MAGIC from_json schema: 'STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>'
# MAGIC endpoint (the _config var):  LLM_FAST  ==  'databricks-claude-haiku-4-5'
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ First, just ask the model about ONE note (prove the call works) (COMPLETED)

# COMMAND ----------

# DBTITLE 1,One note, one model call → typed columns (COMPLETED)
# MAGIC %sql
# MAGIC SELECT person_id, extracted.her2_status, extracted.er_status, extracted.pr_status, note_text
# MAGIC FROM (
# MAGIC   SELECT person_id, note_text,
# MAGIC     from_json(
# MAGIC       ai_query(
# MAGIC         'databricks-claude-haiku-4-5',
# MAGIC         'Extract the HER2, ER (estrogen receptor), and PR (progesterone receptor) status from this '
# MAGIC         || 'breast cancer pathology report. Respond with exactly one of Positive, Negative, or Unknown '
# MAGIC         || 'for each. Use Unknown if equivocal or not stated. Report: ' || note_text,
# MAGIC         responseFormat => 'STRUCT<result:STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>>'
# MAGIC       ),
# MAGIC       'STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>'
# MAGIC     ) AS extracted
# MAGIC   FROM note
# MAGIC   WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC   LIMIT 1
# MAGIC );

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Run it across every pathology note → `silver_nlp_biomarkers` (COMPLETED)
# MAGIC
# MAGIC Same call, no `LIMIT`. Materialize the result as **`silver_nlp_biomarkers`**: one row per patient
# MAGIC with a pathology report, the three extracted statuses, and a literal `biomarker_source = 'nlp'` so
# MAGIC it sits cleanly alongside the structured `silver_biomarker_profile` from nb 02.

# COMMAND ----------

# DBTITLE 1,silver_nlp_biomarkers (HER2 / ER / PR read from the notes) (COMPLETED)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE silver_nlp_biomarkers
# MAGIC COMMENT 'HER2/ER/PR read from free-text pathology notes by a Foundation Model (ai_query). biomarker_source = nlp.'
# MAGIC AS
# MAGIC SELECT person_id,
# MAGIC        extracted.her2_status AS her2_status,
# MAGIC        extracted.er_status   AS er_status,
# MAGIC        extracted.pr_status   AS pr_status,
# MAGIC        'nlp'                 AS biomarker_source
# MAGIC FROM (
# MAGIC   SELECT person_id,
# MAGIC     from_json(
# MAGIC       ai_query(
# MAGIC         'databricks-claude-haiku-4-5',
# MAGIC         'Extract the HER2, ER (estrogen receptor), and PR (progesterone receptor) status from this '
# MAGIC         || 'breast cancer pathology report. Respond with exactly one of Positive, Negative, or Unknown '
# MAGIC         || 'for each. Use Unknown if equivocal or not stated. Report: ' || note_text,
# MAGIC         responseFormat => 'STRUCT<result:STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>>'
# MAGIC       ),
# MAGIC       'STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>'
# MAGIC     ) AS extracted
# MAGIC   FROM note
# MAGIC   WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC );

# COMMAND ----------

# DBTITLE 1,Peek at what the model pulled out (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT person_id, her2_status, er_status, pr_status, biomarker_source
# MAGIC FROM silver_nlp_biomarkers ORDER BY person_id LIMIT 10;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 3️⃣ Did we recover the invisible patients? 🎯 (PRE-BUILT proof)
# MAGIC
# MAGIC The whole point. A "notes-only" patient has a `PATHOLOGY_REPORT` note but **no** structured
# MAGIC `measurement` rows. Count how many now have an NLP biomarker call.

# COMMAND ----------

# DBTITLE 1,Count the notes-only patients NLP just recovered (PRE-BUILT)
# MAGIC %sql
# MAGIC WITH has_struct AS (
# MAGIC   SELECT DISTINCT person_id FROM measurement
# MAGIC   WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
# MAGIC ),
# MAGIC notes_only AS (
# MAGIC   SELECT DISTINCT person_id FROM note
# MAGIC   WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC     AND person_id NOT IN (SELECT person_id FROM has_struct)
# MAGIC )
# MAGIC SELECT
# MAGIC   COUNT(*)                                                          AS notes_only_patients,
# MAGIC   SUM(CASE WHEN nlp.person_id IS NOT NULL THEN 1 ELSE 0 END)        AS recovered_by_nlp,
# MAGIC   SUM(CASE WHEN nlp.her2_status IN ('Positive','Negative') THEN 1 ELSE 0 END) AS with_definite_her2
# MAGIC FROM notes_only n
# MAGIC LEFT JOIN silver_nlp_biomarkers nlp ON n.person_id = nlp.person_id;

# COMMAND ----------

# MAGIC %md Expected: **60 notes-only patients, ~60 recovered, ~100% with a definite HER2 call.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Quick accuracy gut-check (PRE-BUILT, the rigorous eval is nb 07)
# MAGIC
# MAGIC For the "both" patients we can hold the model's reading up against the structured ground truth.
# MAGIC This is a sanity check; the full scored evaluation lives in **notebook 07**.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:10px 14px; border-radius:4px">
# MAGIC Agreement here is <b>high but not 100%</b>, and that is by design. The foundation plants a
# MAGIC hard-case band (person 61-90) whose notes are written equivocally (HER2 IHC 2+ with a reflex FISH
# MAGIC ratio, ER-low-positive). A quick prompt reads some of those as "Unknown", so they show up as
# MAGIC disagreements. That is exactly the contrast notebook 07 measures.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Headline agreement rate on the overlap (PRE-BUILT)
# MAGIC %sql
# MAGIC WITH struct_her2 AS (
# MAGIC   SELECT person_id, MAX(value_source_value) AS her2_structured
# MAGIC   FROM measurement WHERE measurement_source_value = 'HER2/neu' GROUP BY person_id
# MAGIC )
# MAGIC SELECT
# MAGIC   COUNT(*)                                                                  AS both_patients,
# MAGIC   SUM(CASE WHEN s.her2_structured = nlp.her2_status THEN 1 ELSE 0 END)       AS agree,
# MAGIC   ROUND(100.0 * AVG(CASE WHEN s.her2_structured = nlp.her2_status THEN 1 ELSE 0 END), 1) AS agree_pct
# MAGIC FROM struct_her2 s
# MAGIC JOIN silver_nlp_biomarkers nlp ON s.person_id = nlp.person_id;

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What we just did:</b> turned unstructured pathology text into typed HER2/ER/PR columns with a
# MAGIC single <code>ai_query</code>: no model serving, no Python, full lineage in Unity Catalog. That
# MAGIC recovered the notes-only patients SQL could never see. <b>This is the NLP value moment.</b>
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[05_clinicalbert_mlflow_uc]($./05_clinicalbert_mlflow_uc)** to register a domain ClinicalBERT model to Unity Catalog and serve it on an endpoint.
