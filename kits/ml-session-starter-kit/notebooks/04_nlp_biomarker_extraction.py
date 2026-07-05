# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 04 · NLP EXTRACTION · 🧠 THE GENAI CORE — YOU BUILD THIS</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧠 Reading the notes with <code>ai_query</code></div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Recover HER2 / ER / PR status from free-text pathology reports with a Foundation Model —
# MAGIC     and pull the ~60 "notes-only" patients back into the cohort that structured SQL never sees.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why SQL can't do this, but a Foundation Model can
# MAGIC
# MAGIC Notebook 03 surfaced the gap: ~**60 patients** (person 181–240) have their biomarker status
# MAGIC written *only* in a free-text pathology note. They have **zero** rows in `measurement`, so the
# MAGIC silver pivot — and every SQL cohort query — returns nothing for them.
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
# MAGIC Model reads the line like a clinician. We call it **from SQL** with **`ai_query`** — no model
# MAGIC hosting, no Python serving code, full Unity Catalog lineage.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🔑 The pattern you need to know (read this before you build)
# MAGIC
# MAGIC `ai_query(endpoint, prompt, responseFormat => ...)` calls a model on each row. Two pieces work
# MAGIC together so the output is parseable:
# MAGIC
# MAGIC 1. **`responseFormat`** turns on *constrained decoding* so the model emits **clean JSON** — not
# MAGIC    `` ```json … ``` `` markdown fences. Without it, `from_json` silently returns **NULL** for every
# MAGIC    fenced row and your whole column comes back empty. (This was a real bug in the original build.)
# MAGIC 2. **`from_json`** turns that JSON string into typed columns you can select.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The one gotcha:</b> the <code>responseFormat</code> DDL form allows only <b>one</b> top-level
# MAGIC field, so it is wrapped as <code>STRUCT&lt;result:STRUCT&lt;her2_status:STRING, er_status:STRING,
# MAGIC pr_status:STRING&gt;&gt;</code>. The model still emits the flat keys, which your <code>from_json</code>
# MAGIC schema (<code>STRUCT&lt;her2_status:STRING, er_status:STRING, pr_status:STRING&gt;</code>) matches.
# MAGIC These two response shapes are <b>given to you below</b> — your job is the prompt and wiring them up.
# MAGIC </div>
# MAGIC
# MAGIC ```
# MAGIC responseFormat (use verbatim): 'STRUCT<result:STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>>'
# MAGIC from_json schema (use verbatim): 'STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>'
# MAGIC endpoint (use the _config var):  LLM_FAST  ==  'databricks-claude-haiku-4-5'
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ First, just ask the model about ONE note (prove the call works)

# COMMAND ----------

# DBTITLE 1,TODO — one note, one model call → typed columns
# MAGIC %sql
# MAGIC -- TODO (you build this): call ai_query on a SINGLE pathology note and parse the result into
# MAGIC --   her2_status / er_status / pr_status columns. Get this working on ONE row before scaling.
# MAGIC -- YOUR PROMPT must instruct the model to:
# MAGIC --   • extract HER2, ER (estrogen receptor), and PR (progesterone receptor) status, and
# MAGIC --   • answer with EXACTLY one of Positive / Negative / Unknown for each (Unknown if equivocal).
# MAGIC -- Build it like this (fill the prompt + the two response shapes from the cheat-sheet above):
# MAGIC --
# MAGIC -- SELECT person_id, extracted.her2_status, extracted.er_status, extracted.pr_status, note_text
# MAGIC -- FROM (
# MAGIC --   SELECT person_id, note_text,
# MAGIC --     from_json(
# MAGIC --       ai_query(
# MAGIC --         'databricks-claude-haiku-4-5',
# MAGIC --         '<YOUR PROMPT>' || note_text,
# MAGIC --         responseFormat => '<responseFormat from cheat-sheet>'
# MAGIC --       ),
# MAGIC --       '<from_json schema from cheat-sheet>'
# MAGIC --     ) AS extracted
# MAGIC --   FROM note
# MAGIC --   WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC --   LIMIT 1
# MAGIC -- );

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Run it across every pathology note → `silver_nlp_biomarkers`
# MAGIC
# MAGIC Same call, no `LIMIT`. Materialize the result as **`silver_nlp_biomarkers`** — one row per patient
# MAGIC with a pathology report, the three extracted statuses, and a literal `biomarker_source = 'nlp'` so
# MAGIC it sits cleanly alongside the structured `silver_biomarker_profile` from nb 02.

# COMMAND ----------

# DBTITLE 1,TODO — silver_nlp_biomarkers (HER2 / ER / PR read from the notes)
# MAGIC %sql
# MAGIC -- TODO (you build this): CREATE OR REPLACE TABLE silver_nlp_biomarkers from the same ai_query
# MAGIC --   call as above, over ALL pathology notes (no LIMIT). Add a literal column biomarker_source = 'nlp'.
# MAGIC -- WHY 'nlp' literal: nb 06 FULL OUTER JOINs this against the structured pivot and uses the source
# MAGIC --   tag for the audit column — so a reviewer always knows whether a call came from a lab value or a note.
# MAGIC -- Columns to produce: person_id, her2_status, er_status, pr_status, biomarker_source.

# COMMAND ----------

# DBTITLE 1,Peek at what the model pulled out (PRE-BUILT — runs after your table exists)
# MAGIC %sql
# MAGIC SELECT person_id, her2_status, er_status, pr_status, biomarker_source
# MAGIC FROM silver_nlp_biomarkers ORDER BY person_id LIMIT 10;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 3️⃣ Did we recover the invisible patients? 🎯  (PRE-BUILT proof)
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

# MAGIC %md
# MAGIC ## 4️⃣ Quick accuracy gut-check (PRE-BUILT — the rigorous eval is nb 07)
# MAGIC
# MAGIC For the "both" patients we can hold the model's reading up against the structured ground truth.
# MAGIC This is a sanity check; the full scored evaluation lives in **notebook 07**.

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
# MAGIC <b>What you just did:</b> turned unstructured pathology text into typed HER2/ER/PR columns with a
# MAGIC single <code>ai_query</code> — no model serving, no Python, full lineage in Unity Catalog. That
# MAGIC recovered the notes-only patients SQL could never see. <b>This is the NLP value moment.</b>
# MAGIC </div>
# MAGIC
# MAGIC <!-- EXTENSION (optional): try a second prompt variant or LLM_STRONG here and eyeball the diff —
# MAGIC      then make it rigorous in nb 07. Or extract a 4th field (e.g. Ki-67) and carry it downstream. -->
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[05_clinicalbert_mlflow_uc]($./05_clinicalbert_mlflow_uc)** to register a domain ClinicalBERT extractor to Unity Catalog (pre-built, optional).
