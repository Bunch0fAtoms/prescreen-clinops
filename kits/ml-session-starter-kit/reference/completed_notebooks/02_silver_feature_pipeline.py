# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 02 · FEATURE ENGINEERING · COMPLETED</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🥈 Silver layer: a Lakeflow pipeline in SQL</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Reshape the raw OMOP tables into three analytics-ready, per-patient feature views,
# MAGIC     declared entirely in SQL.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why a *declarative* pipeline, and why SQL?
# MAGIC
# MAGIC **Lakeflow Declarative Pipelines** let you describe *what* each table should contain; Databricks
# MAGIC works out the dependency graph, the incremental refresh, and the data-quality enforcement. We
# MAGIC write it in **SQL** on purpose. It's the simplest thing a clinical-data team can read, review,
# MAGIC and own.
# MAGIC
# MAGIC Three silver feature views, one per concept the trial criteria care about:
# MAGIC
# MAGIC | View | Grain | Feeds |
# MAGIC |---|---|---|
# MAGIC | `silver_biomarker_profile` | one row / patient | HER2 / ER / PR pivoted from `measurement` |
# MAGIC | `silver_prior_therapy` | one row / patient | anti-HER2 & endocrine therapy flags from `drug_exposure` |
# MAGIC | `silver_demographics` | one row / patient | age-at-diagnosis, menopausal status, AJCC stage |
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>The biomarker pivot is filled in below</b> (both in the pipeline source file and in the
# MAGIC run-it-now path), alongside the two worked-example views. The pivot is the classic long → wide
# MAGIC <code>MAX(CASE WHEN ...)</code> pattern.
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## ▸ Option A: the Lakeflow Declarative Pipeline (workshop path)
# MAGIC
# MAGIC In a pipeline, `${source_catalog}` / `${source_schema}` are supplied as pipeline **configuration**
# MAGIC parameters, and `CONSTRAINT … EXPECT` clauses become enforced **data-quality expectations**.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Creating & running the pipeline (the reproducible click-path)
# MAGIC
# MAGIC 1. Run the next cell to write `silver_layer.sql` to your workspace.
# MAGIC 2. **Pipelines → Create pipeline → ETL pipeline.**
# MAGIC 3. Name: `clinops_silver_biomarker_pipeline`. Serverless ✔, Photon ✔.
# MAGIC 4. **Source code:** add the `silver_layer.sql` file.
# MAGIC 5. **Destination:** Default catalog = your `catalog` widget value; Default schema = your `schema`.
# MAGIC 6. **Configuration** (Advanced → Add): `source_catalog` = your catalog, `source_schema` = your schema.
# MAGIC 7. **Create**, then **Run**. Watch the three views build in the pipeline graph.

# COMMAND ----------

# DBTITLE 1,Write the pipeline source file: all three views (COMPLETED)
import os

# All three materialized views, including the completed silver_biomarker_profile pivot.
SILVER_LAYER_SQL = """
-- ── silver_biomarker_profile (COMPLETED: long → wide pivot) ────────────────
-- One row per patient with her2_status / er_status / pr_status, pivoted from the
-- long measurement table. MAX(CASE WHEN ...) collapses the per-marker rows into one.
CREATE OR REFRESH MATERIALIZED VIEW silver_biomarker_profile (
  CONSTRAINT person_id_not_null EXPECT (person_id IS NOT NULL)
) COMMENT "Per-person structured biomarker pivot: HER2, ER, PR from the measurement table"
TBLPROPERTIES ("quality" = "silver") AS
WITH biomarkers AS (
  SELECT person_id,
    MAX(CASE WHEN measurement_source_value = 'HER2/neu'              THEN value_source_value END) AS her2_status,
    MAX(CASE WHEN measurement_source_value = 'Estrogen receptor'     THEN value_source_value END) AS er_status,
    MAX(CASE WHEN measurement_source_value = 'Progesterone receptor' THEN value_source_value END) AS pr_status
  FROM ${source_catalog}.${source_schema}.measurement
  WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
  GROUP BY person_id
)
SELECT person_id, her2_status, er_status, pr_status FROM biomarkers;

-- ── silver_prior_therapy (PRE-BUILT worked example) ───────────────────────
CREATE OR REFRESH MATERIALIZED VIEW silver_prior_therapy (
  CONSTRAINT person_id_not_null EXPECT (person_id IS NOT NULL)
) COMMENT "Per-person prior-therapy flags derived from drug_exposure"
TBLPROPERTIES ("quality" = "silver") AS
SELECT person_id,
  MAX(CASE WHEN drug_source_value IN ('Trastuzumab','Pertuzumab') THEN 1 ELSE 0 END) = 1 AS had_anti_her2_therapy,
  MAX(CASE WHEN drug_source_value IN ('Letrozole','Tamoxifen')   THEN 1 ELSE 0 END) = 1 AS had_endocrine_therapy
FROM ${source_catalog}.${source_schema}.drug_exposure
GROUP BY person_id;

-- ── silver_demographics (PRE-BUILT worked example) ────────────────────────
CREATE OR REFRESH MATERIALIZED VIEW silver_demographics (
  CONSTRAINT person_id_not_null EXPECT (person_id IS NOT NULL),
  CONSTRAINT age_plausible      EXPECT (age_at_dx_years BETWEEN 18 AND 110)
) COMMENT "Per-person demographics + diagnosis context for trial eligibility"
TBLPROPERTIES ("quality" = "silver") AS
WITH dx AS (
  SELECT person_id, MIN(condition_start_date) AS dx_date
  FROM ${source_catalog}.${source_schema}.condition_occurrence
  WHERE condition_source_value = 'Malignant neoplasm of breast'
  GROUP BY person_id
),
meno AS (
  SELECT person_id, MAX(value_source_value) AS menopausal_status
  FROM ${source_catalog}.${source_schema}.observation
  WHERE observation_source_value = 'Menopausal status'
  GROUP BY person_id
),
stage AS (
  SELECT person_id, MAX(value_source_value) AS ajcc_stage
  FROM ${source_catalog}.${source_schema}.observation
  WHERE observation_source_value = 'AJCC stage'
  GROUP BY person_id
)
SELECT p.person_id, p.gender_source_value,
  (year(dx.dx_date) - p.year_of_birth) AS age_at_dx_years,
  dx.dx_date, meno.menopausal_status, stage.ajcc_stage
FROM ${source_catalog}.${source_schema}.person p
JOIN dx         ON p.person_id = dx.person_id
LEFT JOIN meno  ON p.person_id = meno.person_id
LEFT JOIN stage ON p.person_id = stage.person_id;
""".strip()

out_dir = f"/Workspace/Users/{spark.sql('SELECT current_user()').first()[0]}/clinops_pipeline"
os.makedirs(out_dir, exist_ok=True)
with open(f"{out_dir}/silver_layer.sql", "w") as f:
    f.write(SILVER_LAYER_SQL)
print(f"✅ Pipeline source written to {out_dir}/silver_layer.sql")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ▸ Option B: run the same logic now (no pipeline required)
# MAGIC
# MAGIC Identical SELECTs, materialized as tables right here so downstream notebooks have their inputs
# MAGIC immediately.

# COMMAND ----------

# DBTITLE 1,silver_biomarker_profile (HER2 / ER / PR pivot) (COMPLETED)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE silver_biomarker_profile
# MAGIC COMMENT 'Per-person structured biomarker pivot: HER2, ER, PR from measurement'
# MAGIC AS
# MAGIC WITH biomarkers AS (
# MAGIC   SELECT person_id,
# MAGIC     MAX(CASE WHEN measurement_source_value = 'HER2/neu'              THEN value_source_value END) AS her2_status,
# MAGIC     MAX(CASE WHEN measurement_source_value = 'Estrogen receptor'     THEN value_source_value END) AS er_status,
# MAGIC     MAX(CASE WHEN measurement_source_value = 'Progesterone receptor' THEN value_source_value END) AS pr_status
# MAGIC   FROM measurement
# MAGIC   WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
# MAGIC   GROUP BY person_id
# MAGIC )
# MAGIC SELECT person_id, her2_status, er_status, pr_status FROM biomarkers;

# COMMAND ----------

# DBTITLE 1,silver_prior_therapy: anti-HER2 & endocrine flags (PRE-BUILT example)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE silver_prior_therapy
# MAGIC COMMENT 'Per-person prior-therapy flags derived from drug_exposure'
# MAGIC AS
# MAGIC SELECT person_id,
# MAGIC   MAX(CASE WHEN drug_source_value IN ('Trastuzumab','Pertuzumab') THEN 1 ELSE 0 END) = 1 AS had_anti_her2_therapy,
# MAGIC   MAX(CASE WHEN drug_source_value IN ('Letrozole','Tamoxifen')   THEN 1 ELSE 0 END) = 1 AS had_endocrine_therapy
# MAGIC FROM drug_exposure
# MAGIC GROUP BY person_id;

# COMMAND ----------

# DBTITLE 1,silver_demographics: age-at-dx, menopausal status, stage (PRE-BUILT example)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE silver_demographics
# MAGIC COMMENT 'Per-person demographics + diagnosis context for trial eligibility'
# MAGIC AS
# MAGIC WITH dx AS (
# MAGIC   SELECT person_id, MIN(condition_start_date) AS dx_date
# MAGIC   FROM condition_occurrence
# MAGIC   WHERE condition_source_value = 'Malignant neoplasm of breast'
# MAGIC   GROUP BY person_id
# MAGIC ),
# MAGIC meno AS (
# MAGIC   SELECT person_id, MAX(value_source_value) AS menopausal_status
# MAGIC   FROM observation WHERE observation_source_value = 'Menopausal status' GROUP BY person_id
# MAGIC ),
# MAGIC stage AS (
# MAGIC   SELECT person_id, MAX(value_source_value) AS ajcc_stage
# MAGIC   FROM observation WHERE observation_source_value = 'AJCC stage' GROUP BY person_id
# MAGIC )
# MAGIC SELECT p.person_id, p.gender_source_value,
# MAGIC   (year(dx.dx_date) - p.year_of_birth) AS age_at_dx_years,
# MAGIC   dx.dx_date, meno.menopausal_status, stage.ajcc_stage
# MAGIC FROM person p
# MAGIC JOIN dx         ON p.person_id = dx.person_id
# MAGIC LEFT JOIN meno  ON p.person_id = meno.person_id
# MAGIC LEFT JOIN stage ON p.person_id = stage.person_id;

# COMMAND ----------

# DBTITLE 1,Verify the silver layer
# MAGIC %sql
# MAGIC SELECT 'silver_biomarker_profile' AS view, COUNT(*) AS rows,
# MAGIC        SUM(CASE WHEN her2_status IS NOT NULL THEN 1 ELSE 0 END) AS has_her2
# MAGIC FROM silver_biomarker_profile
# MAGIC UNION ALL SELECT 'silver_prior_therapy',  COUNT(*), SUM(CASE WHEN had_anti_her2_therapy THEN 1 ELSE 0 END) FROM silver_prior_therapy
# MAGIC UNION ALL SELECT 'silver_demographics',   COUNT(*), SUM(CASE WHEN menopausal_status='Postmenopausal' THEN 1 ELSE 0 END) FROM silver_demographics;

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What we built:</b> three clean per-patient silver views. Note that
# MAGIC <code>silver_biomarker_profile</code> only has biomarkers for the ~240 patients with structured
# MAGIC <code>measurement</code> rows. The 60 <b>notes-only</b> patients are still missing. That gap is
# MAGIC exactly what notebook 03 quantifies and notebook 04 fills with NLP.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[03_exploratory_data_analysis]($./03_exploratory_data_analysis)** to explore the data and see the gap.
