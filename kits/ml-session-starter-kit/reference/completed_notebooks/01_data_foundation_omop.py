# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 01 · DATA FOUNDATION · COMPLETED</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧱 The OMOP data foundation</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Confirm and profile the 6 OMOP tables the shared foundation already stood up. 300
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
# MAGIC **6 of those tables** with 300 synthetic breast-cancer patients, following the OMOP CDM (a
# MAGIC public open standard). This notebook reads them read-only from your `source_schema`
# MAGIC (synthetic default `clinops_foundation`), so every query you write here runs unchanged against
# MAGIC any OMOP-conformant source later: just point `source_catalog` / `source_schema` at your own
# MAGIC OMOP tables in `databricks.yml`.
# MAGIC
# MAGIC | Table | Role in this demo |
# MAGIC |---|---|
# MAGIC | `person` | One row per patient: `person_id`, `year_of_birth`, `gender_source_value`. 300 rows. |
# MAGIC | `condition_occurrence` | Breast-cancer diagnoses. `condition_source_value = 'Malignant neoplasm of breast'`. |
# MAGIC | `measurement` | **Structured** biomarker results (HER2 / ER / PR), `value_source_value` = `'Positive'`/`'Negative'`. Absent for the notes-only patients. |
# MAGIC | `observation` | Menopausal status (Trial B) and AJCC tumor stage. |
# MAGIC | `drug_exposure` | Prior therapy. Trastuzumab / Pertuzumab flag prior anti-HER2 treatment, a Trial A disqualifier. |
# MAGIC | `note` | **Free-text** pathology reports in `note_text`, where the hidden biomarkers live. 300 rows. |

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🎯 Three biomarker-source groups, the whole point of the demo
# MAGIC
# MAGIC We plant every patient into one of three groups based on **where their biomarkers live**. This
# MAGIC is what lets notebooks 04 to 07 prove the NLP value story.
# MAGIC
# MAGIC <div style="display:flex; gap:14px; flex-wrap:wrap; margin-top:8px">
# MAGIC   <div style="flex:1; min-width:230px; background:#E8F5E9; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#2E7D32">180</div>
# MAGIC     <b>both-agree</b> (person 1 to 180)<br>biomarkers in <i>both</i> <code>measurement</code> and <code>note_text</code>.
# MAGIC     <br>→ the NLP <b>ground truth</b>.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:230px; background:#FFEBEE; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#C62828">60</div>
# MAGIC     <b>notes-only</b> (person 181 to 240)<br>biomarkers <i>only</i> in <code>note_text</code>.
# MAGIC     <br>→ <b>invisible to SQL</b>; recovered only by NLP.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:230px; background:#E3F2FD; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#1565C0">60</div>
# MAGIC     <b>structured-only</b> (person 241 to 300)<br>biomarkers only in <code>measurement</code>.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🛠️ Where the data comes from (the shared foundation, not this kit)
# MAGIC
# MAGIC The 6 OMOP tables are stood up **once** by the shared `foundation/` bundle, which lands them in
# MAGIC the `source_schema` (synthetic default `clinops_foundation`). Every team, including this ML
# MAGIC group, reads those same tables read-only and builds its own work on top. This kit does not
# MAGIC generate data; it **reads** the foundation's tables.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC To read your <b>own</b> OMOP data instead of the synthetic foundation, set
# MAGIC <code>source_catalog</code> / <code>source_schema</code> to your OMOP catalog and schema in
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
# Use the SOURCE catalog+schema so bare table names resolve to your own OMOP too. Your
# OMOP source is typically a different catalog, so switching only the schema would miss it.
spark.sql(f"USE CATALOG {SOURCE_CATALOG}")
spark.sql(f"USE SCHEMA {SOURCE_SCHEMA}")
print(f"Reading the 6 OMOP tables from {SOURCE_CATALOG}.{SOURCE_SCHEMA}")

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
# MAGIC `clinops_foundation`, or your own OMOP catalog and schema for the real data).

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
# MAGIC patients (person 181 to 240) are the ones a SQL-only pipeline silently misses, the gap that
# MAGIC notebooks 04 to 05 close with NLP.

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Planted-cohort validation SQL (COMPLETED)
# MAGIC
# MAGIC Before building on the data, confirm the two planted trial cohorts are present. This is a gentle
# MAGIC warm-up for the eligibility logic written properly in notebooks 02 and 06. **Trial A** is
# MAGIC seeded on person 1 to 20; **Trial B** on person 31 to 50.

# COMMAND ----------

# DBTITLE 1,Trial A count: HER2+ breast cancer, no prior anti-HER2 therapy (COMPLETED)
# MAGIC %sql
# MAGIC -- Structured-only baseline for Trial A. It counts patients who are HER2 Positive by a lab
# MAGIC -- measurement AND have a breast-cancer diagnosis AND have NOT had anti-HER2 therapy.
# MAGIC -- This number MISSES the notes-only patients, which is exactly the gap nb 04 closes.
# MAGIC SELECT COUNT(DISTINCT m.person_id) AS trial_a_eligible
# MAGIC FROM measurement m
# MAGIC JOIN condition_occurrence co
# MAGIC   ON m.person_id = co.person_id
# MAGIC  AND co.condition_source_value = 'Malignant neoplasm of breast'
# MAGIC WHERE m.measurement_source_value = 'HER2/neu'
# MAGIC   AND m.value_source_value       = 'Positive'
# MAGIC   AND m.person_id NOT IN (
# MAGIC     SELECT person_id FROM drug_exposure
# MAGIC     WHERE drug_source_value IN ('Trastuzumab','Pertuzumab')
# MAGIC   );

# COMMAND ----------

# MAGIC %md Expected: **≥ 20** (person 1 to 20 are guaranteed; a few incidental matches are fine).
# MAGIC The `NOT IN (anti-HER2)` exclusion is what keeps the ineligible controls (person 21 to 30) out.

# COMMAND ----------

# DBTITLE 1,Trial B count: ER+ / HER2− / postmenopausal (COMPLETED)
# MAGIC %sql
# MAGIC -- Self-join measurement to itself (one alias for ER, one for HER2), then join observation for
# MAGIC -- menopausal status and condition_occurrence for the breast-cancer diagnosis.
# MAGIC SELECT COUNT(DISTINCT er.person_id) AS trial_b_eligible
# MAGIC FROM measurement er
# MAGIC JOIN measurement her2
# MAGIC   ON er.person_id = her2.person_id
# MAGIC JOIN observation o
# MAGIC   ON er.person_id = o.person_id
# MAGIC JOIN condition_occurrence co
# MAGIC   ON er.person_id = co.person_id
# MAGIC  AND co.condition_source_value = 'Malignant neoplasm of breast'
# MAGIC WHERE er.measurement_source_value  = 'Estrogen receptor' AND er.value_source_value  = 'Positive'
# MAGIC   AND her2.measurement_source_value = 'HER2/neu'          AND her2.value_source_value = 'Negative'
# MAGIC   AND o.observation_source_value   = 'Menopausal status'  AND o.value_source_value   = 'Postmenopausal';

# COMMAND ----------

# MAGIC %md Expected: **≥ 20** (person 31 to 50 are guaranteed).

# COMMAND ----------

# DBTITLE 1,Peek at one pathology note, the free text we'll mine in nb 04 (PRE-BUILT)
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
# MAGIC Next, <b>notebook 02</b> reshapes raw OMOP into clean silver feature views, and that's where
# MAGIC you write the biomarker pivot.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[02_silver_feature_pipeline]($./02_silver_feature_pipeline)** to build the silver feature views.
