# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 03 · EXPLORE · COMPLETED</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🔎 Exploratory data analysis</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Get to know the cohort in a few cells, and surface the exact gap that justifies the NLP work
# MAGIC     that follows.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## How easy is EDA on Databricks?
# MAGIC
# MAGIC Every query below returns a Spark DataFrame. Click **`+` → Visualization** on any result to chart
# MAGIC it: no matplotlib, no export. We explore in three passes:
# MAGIC 1. **Who are these patients?** demographics, stage, menopausal status
# MAGIC 2. **What do the biomarkers look like?** HER2 / ER / PR distribution
# MAGIC 3. **Where do the biomarkers live?** the structured-vs-notes gap (the punchline you'll quantify)

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Who are these patients? (try the suggested viz on each)

# COMMAND ----------

# DBTITLE 1,Age-at-diagnosis distribution (try a Histogram viz)
# MAGIC %sql
# MAGIC SELECT age_at_dx_years FROM silver_demographics WHERE age_at_dx_years IS NOT NULL;

# COMMAND ----------

# DBTITLE 1,AJCC stage mix (try a Bar viz)
# MAGIC %sql
# MAGIC SELECT ajcc_stage, COUNT(*) AS patients
# MAGIC FROM silver_demographics WHERE ajcc_stage IS NOT NULL
# MAGIC GROUP BY ajcc_stage ORDER BY ajcc_stage;

# COMMAND ----------

# DBTITLE 1,Menopausal status (matters for Trial B)
# MAGIC %sql
# MAGIC SELECT COALESCE(menopausal_status, '(unknown)') AS menopausal_status, COUNT(*) AS patients
# MAGIC FROM silver_demographics GROUP BY ALL ORDER BY patients DESC;

# COMMAND ----------

# DBTITLE 1,HER2 / ER / PR positive-vs-negative, structured only (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT 'HER2' AS marker, COALESCE(her2_status,'(missing)') AS status, COUNT(*) n FROM silver_biomarker_profile GROUP BY 2
# MAGIC UNION ALL SELECT 'ER', COALESCE(er_status,'(missing)'), COUNT(*) FROM silver_biomarker_profile GROUP BY 2
# MAGIC UNION ALL SELECT 'PR', COALESCE(pr_status,'(missing)'), COUNT(*) FROM silver_biomarker_profile GROUP BY 2
# MAGIC ORDER BY marker, status;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 3️⃣ Where do the biomarkers live? The gap 🎯
# MAGIC
# MAGIC This is the whole reason for the NLP work. Classify every patient by **where** their biomarker
# MAGIC evidence exists: **structured** (rows in `measurement`) vs **note** (a pathology report in `note`).
# MAGIC
# MAGIC <div style="background:#FFEBEE; border-left:6px solid #C62828; padding:12px 16px; border-radius:4px">
# MAGIC Patients with <b>a pathology note but NO structured measurement</b> are invisible to the silver
# MAGIC pipeline, and to every SQL cohort query. Real, potentially-eligible patients we would miss.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Classify every patient by biomarker evidence source (COMPLETED)
# MAGIC %sql
# MAGIC -- Two helper sets, then LEFT JOIN person to both and CASE on which side is NULL.
# MAGIC -- The 'notes-only' count is the number of patients a SQL-only pipeline silently misses.
# MAGIC WITH has_struct AS (
# MAGIC   SELECT DISTINCT person_id FROM measurement
# MAGIC   WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
# MAGIC ),
# MAGIC has_note AS (
# MAGIC   SELECT DISTINCT person_id FROM note WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC )
# MAGIC SELECT
# MAGIC   CASE
# MAGIC     WHEN s.person_id IS NOT NULL AND n.person_id IS NOT NULL THEN 'both'
# MAGIC     WHEN s.person_id IS NULL     AND n.person_id IS NOT NULL THEN 'notes-only'
# MAGIC     WHEN s.person_id IS NOT NULL AND n.person_id IS NULL     THEN 'structured-only'
# MAGIC     ELSE 'neither'
# MAGIC   END AS biomarker_evidence,
# MAGIC   COUNT(*) AS patients
# MAGIC FROM person p
# MAGIC LEFT JOIN has_struct s ON p.person_id = s.person_id
# MAGIC LEFT JOIN has_note   n ON p.person_id = n.person_id
# MAGIC GROUP BY ALL
# MAGIC ORDER BY patients DESC;

# COMMAND ----------

# MAGIC %md Expected: **both ≈ 180, notes-only ≈ 60, structured-only ≈ 60.**

# COMMAND ----------

# DBTITLE 1,Quantify the missed opportunity, in plain language (PRE-BUILT)
notes_only = spark.sql("""
  WITH has_struct AS (
    SELECT DISTINCT person_id FROM measurement
    WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
  )
  SELECT COUNT(*) n FROM note n
  WHERE n.note_source_value = 'PATHOLOGY_REPORT'
    AND n.person_id NOT IN (SELECT person_id FROM has_struct)
""").first()["n"]

total = spark.sql("SELECT COUNT(*) n FROM person").first()["n"]

show_md(f"""
<b>{notes_only} of {total} patients</b> ({100*notes_only/total:.0f}%) have their biomarker status
written <i>only</i> in a free-text pathology note. A structured cohort query returns <b>zero</b> of
them. Recovering them is the job of notebook 04 (ai_query) and notebook 05 (ClinicalBERT).
""")

# COMMAND ----------

# DBTITLE 1,Peek at a notes-only patient, see why SQL can't parse it (PRE-BUILT)
# MAGIC %sql
# MAGIC WITH has_struct AS (
# MAGIC   SELECT DISTINCT person_id FROM measurement
# MAGIC   WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
# MAGIC )
# MAGIC SELECT person_id, note_title, note_text
# MAGIC FROM note
# MAGIC WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC   AND person_id NOT IN (SELECT person_id FROM has_struct)
# MAGIC ORDER BY person_id LIMIT 3;

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Takeaway:</b> the notes phrase HER2/ER/PR a dozen ways (<i>"3+ by IHC"</i>, <i>"FISH ratio 3.1,
# MAGIC amplified"</i>, <i>"overexpression confirmed"</i>). No <code>LIKE</code> catches them all, but a
# MAGIC Foundation Model reads them like a clinician. That's next.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[04_nlp_biomarker_extraction]($./04_nlp_biomarker_extraction)** to recover the notes-only patients with `ai_query`.
