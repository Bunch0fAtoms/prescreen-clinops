# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 01 · DATA FOUNDATION · PRE-BUILT</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧱 The OMOP data foundation</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Confirm and profile the 6 OMOP tables the shared foundation already stood up — 300
# MAGIC     breast-cancer patients with planted trial cohorts and a deliberate "biomarkers hide in
# MAGIC     the notes" gap. You read these tables; you do not create them.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗂️ What is OMOP, and what are we building?
# MAGIC
# MAGIC The **OMOP Common Data Model (CDM)** is a standard way to organize health records so the same
# MAGIC query works across hospitals and research networks. The shared foundation already stood up
# MAGIC **6 of those tables** with 300 synthetic breast-cancer patients — the same shape as Fred Hutch's
# MAGIC real `curated_omop.omop` data. This notebook reads them read-only from your `source_schema`
# MAGIC (synthetic default `clinops_foundation`), so every query you write here runs unchanged against
# MAGIC the real tables later: just point `source_schema` at `curated_omop.omop` in `databricks.yml`.
# MAGIC
# MAGIC | Table | Role in this demo |
# MAGIC |---|---|
# MAGIC | `person` | One row per patient — `person_id`, `year_of_birth`, `gender_source_value`. 300 rows. |
# MAGIC | `condition_occurrence` | Breast-cancer diagnoses. `condition_source_value = 'Malignant neoplasm of breast'`. |
# MAGIC | `measurement` | **Structured** biomarker results (HER2 / ER / PR), `value_source_value` = `'Positive'`/`'Negative'`. Absent for the notes-only patients. |
# MAGIC | `observation` | Menopausal status (Trial B) and AJCC tumor stage. |
# MAGIC | `drug_exposure` | Prior therapy. Trastuzumab / Pertuzumab flag prior anti-HER2 treatment — a Trial A disqualifier. |
# MAGIC | `note` | **Free-text** pathology reports in `note_text` — where the hidden biomarkers live. 300 rows. |

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🎯 Three biomarker-source groups — the whole point of the demo
# MAGIC
# MAGIC We plant every patient into one of three groups based on **where their biomarkers live**. This
# MAGIC is what lets notebooks 04–07 prove the NLP value story.
# MAGIC
# MAGIC <div style="display:flex; gap:14px; flex-wrap:wrap; margin-top:8px">
# MAGIC   <div style="flex:1; min-width:230px; background:#E8F5E9; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#2E7D32">180</div>
# MAGIC     <b>both-agree</b> (person 1–180)<br>biomarkers in <i>both</i> <code>measurement</code> and <code>note_text</code>.
# MAGIC     <br>→ the NLP <b>ground truth</b>.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:230px; background:#FFEBEE; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#C62828">60</div>
# MAGIC     <b>notes-only</b> (person 181–240)<br>biomarkers <i>only</i> in <code>note_text</code>.
# MAGIC     <br>→ <b>invisible to SQL</b>; recovered only by NLP.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:230px; background:#E3F2FD; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#1565C0">60</div>
# MAGIC     <b>structured-only</b> (person 241–300)<br>biomarkers only in <code>measurement</code>.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🛠️ Where the data comes from (the shared foundation — not this kit)
# MAGIC
# MAGIC The 6 OMOP tables are stood up **once** by the shared `foundation/` bundle, which lands them in
# MAGIC the `source_schema` (synthetic default `clinops_foundation`). Every team — including this ML
# MAGIC group — reads those same tables read-only and builds its own work on top. This kit does not
# MAGIC generate data; it **reads** the foundation's tables.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC To read the <b>real</b> OMOP data instead of the synthetic foundation, set
# MAGIC <code>source_schema</code> to <code>omop</code> (catalog <code>curated_omop</code>) in
# MAGIC <code>databricks.yml</code>. The 6 table names are identical, so nothing downstream changes.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔬 Confirm and profile the 6 OMOP tables (read from `source_schema`)
# MAGIC
# MAGIC These are read-only checks. `_config` pointed Spark at your writable schema; here we switch the
# MAGIC session to the read-only `source_schema` so the bare table names below resolve to the
# MAGIC foundation's OMOP tables. Notebooks 02+ read the same source tables in their pipelines.

# COMMAND ----------

# DBTITLE 1,Point this profiling session at the read-only source schema
# Read-only exploration only. We do NOT create anything in the source schema.
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SOURCE_SCHEMA}")
print(f"Reading the 6 OMOP tables from {CATALOG}.{SOURCE_SCHEMA}")

# COMMAND ----------

# DBTITLE 1,Confirm all 6 OMOP tables are present, with row counts
# MAGIC %sql
# MAGIC SELECT 'person' AS tbl, COUNT(*) AS n FROM person
# MAGIC UNION ALL SELECT 'condition_occurrence', COUNT(*) FROM condition_occurrence
# MAGIC UNION ALL SELECT 'measurement',          COUNT(*) FROM measurement
# MAGIC UNION ALL SELECT 'observation',          COUNT(*) FROM observation
# MAGIC UNION ALL SELECT 'drug_exposure',        COUNT(*) FROM drug_exposure
# MAGIC UNION ALL SELECT 'note',                 COUNT(*) FROM note
# MAGIC ORDER BY tbl;

# COMMAND ----------

# MAGIC %md
# MAGIC Expected: **`person` = 300**, **`note` = 300**, `condition_occurrence` ≈ 300, and `measurement`,
# MAGIC `observation`, `drug_exposure` all > 0. If a table is missing or empty, confirm the shared
# MAGIC foundation has run and that your `source_schema` points at it (synthetic default
# MAGIC `clinops_foundation`, or `curated_omop.omop` for the real data).

# COMMAND ----------

# DBTITLE 1,Classify every patient by where their biomarkers live (PRE-BUILT)
# MAGIC %sql
# MAGIC WITH has_struct AS (
# MAGIC   SELECT DISTINCT person_id FROM measurement
# MAGIC   WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
# MAGIC ),
# MAGIC has_note AS (
# MAGIC   SELECT DISTINCT person_id FROM note WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC )
# MAGIC SELECT
# MAGIC   CASE
# MAGIC     WHEN s.person_id IS NOT NULL AND n.person_id IS NOT NULL THEN 'both-agree (structured + note)'
# MAGIC     WHEN s.person_id IS NULL     AND n.person_id IS NOT NULL THEN 'notes-only  ⟵ invisible to SQL'
# MAGIC     WHEN s.person_id IS NOT NULL AND n.person_id IS NULL     THEN 'structured-only'
# MAGIC     ELSE 'neither'
# MAGIC   END AS biomarker_source_group,
# MAGIC   COUNT(*) AS patients
# MAGIC FROM person p
# MAGIC LEFT JOIN has_struct s ON p.person_id = s.person_id
# MAGIC LEFT JOIN has_note   n ON p.person_id = n.person_id
# MAGIC GROUP BY ALL
# MAGIC ORDER BY patients DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC Expected: **both-agree ≈ 180**, **notes-only ≈ 60**, **structured-only ≈ 60**. The 60 notes-only
# MAGIC patients (person 181–240) are the ones a SQL-only pipeline silently misses — the gap that
# MAGIC notebooks 04–05 close with NLP.

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Your first build — planted-cohort validation SQL
# MAGIC
# MAGIC Before building on the data, confirm the two planted trial cohorts are present. This is a gentle
# MAGIC warm-up for the eligibility logic you'll write properly in notebooks 02 and 06. **Trial A** is
# MAGIC seeded on person 1–20; **Trial B** on person 31–50.

# COMMAND ----------

# DBTITLE 1,TODO — Trial A count: HER2+ breast cancer, no prior anti-HER2 therapy
# MAGIC %sql
# MAGIC -- TODO (you build this): count DISTINCT patients who are eligible for Trial A from
# MAGIC --   the RAW OMOP tables (measurement + condition_occurrence + drug_exposure).
# MAGIC -- WHY: this is the structured-only baseline — it will MISS the notes-only patients,
# MAGIC --   which is exactly the gap your NLP step (nb 04) later closes. You need this number
# MAGIC --   first so you can prove the cohort grew.
# MAGIC -- Eligibility (Trial A):
# MAGIC --   • condition_occurrence.condition_source_value = 'Malignant neoplasm of breast'
# MAGIC --   • measurement.measurement_source_value = 'HER2/neu' AND value_source_value = 'Positive'
# MAGIC --   • NOT IN drug_exposure where drug_source_value IN ('Trastuzumab','Pertuzumab')
# MAGIC -- Expected: >= 20 (person 1–20 are guaranteed; a few incidental matches are fine).
# MAGIC --
# MAGIC -- SELECT COUNT(DISTINCT ...) AS trial_a_eligible
# MAGIC -- FROM measurement m
# MAGIC -- JOIN condition_occurrence co ON ...
# MAGIC -- WHERE ...
# MAGIC --   AND m.person_id NOT IN (SELECT person_id FROM drug_exposure WHERE ...);

# COMMAND ----------

# DBTITLE 1,TODO — Trial B count: ER+ / HER2− / postmenopausal
# MAGIC %sql
# MAGIC -- TODO (you build this): count DISTINCT patients eligible for Trial B from the raw tables.
# MAGIC -- Eligibility (Trial B):
# MAGIC --   • measurement: 'Estrogen receptor' = 'Positive'  AND  'HER2/neu' = 'Negative'
# MAGIC --   • observation: 'Menopausal status' = 'Postmenopausal'
# MAGIC -- HINT: you'll self-join measurement to itself (one alias for ER, one for HER2) and join
# MAGIC --   observation for menopausal status.
# MAGIC -- Expected: >= 20 (person 31–50 are guaranteed).

# COMMAND ----------

# DBTITLE 1,Peek at one pathology note — the free text we'll mine in nb 04 (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT person_id, note_title, note_text
# MAGIC FROM note
# MAGIC WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC LIMIT 1;

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Takeaway:</b> 6 OMOP tables, 300 patients, two planted trial cohorts, and 60 patients whose
# MAGIC biomarkers hide in free text. Everything downstream queries these exact table and column names.
# MAGIC Next, <b>notebook 02</b> reshapes raw OMOP into clean silver feature views — and that's where
# MAGIC you write the biomarker pivot.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[02_silver_feature_pipeline]($./02_silver_feature_pipeline)** to build the silver feature views.
