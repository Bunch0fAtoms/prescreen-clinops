# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 04 · PHI IDENTIFIER SEARCH · FH ASK (GINA #4)</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🔦 Where does this identifier appear?</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     A researcher built a derived table from a cohort. Did a patient identifier leak into something
# MAGIC     they shared? Answer it two ways: <b>structurally</b> (which columns named/typed like an
# MAGIC     identifier exist anywhere) and <b>by value</b> (does <i>this specific</i> person_id appear).
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## The governance question
# MAGIC
# MAGIC OCDO researchers create their own silver/gold tables from the governed bronze. The data office needs
# MAGIC to answer, on demand: **"Does patient identifier X show up anywhere a researcher can read it?"** Two
# MAGIC complementary searches, both driven from metadata you already created in nb 01:
# MAGIC
# MAGIC 1. **Structural**: every column tagged `phi=other_identifier`, or *named* `person_id` / `note_text`,
# MAGIC    across all schemas the data office can see (`information_schema` + `system.information_schema`).
# MAGIC    This catches a researcher who copied `person_id` into a new table without tagging it.
# MAGIC 2. **By value**: given a concrete identifier, scan the candidate columns and report which
# MAGIC    tables/columns actually contain it. This is the "did it leak into *this* shared table?" check.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Structural search: every PHI-shaped column (PRE-BUILT)
# MAGIC
# MAGIC `system.information_schema.columns` spans the whole metastore. We find columns that are either
# MAGIC **tagged** as direct identifiers (your nb 01 work) or **named/typed** like one, the union catches
# MAGIC both the governed tables and untagged copies a researcher may have made.

# COMMAND ----------

# DBTITLE 1,Tagged direct-identifier columns across the metastore (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT catalog_name, schema_name, table_name, column_name, tag_value
# MAGIC FROM system.information_schema.column_tags
# MAGIC WHERE tag_name = 'phi' AND tag_value = 'other_identifier'
# MAGIC ORDER BY catalog_name, schema_name, table_name, column_name;

# COMMAND ----------

# DBTITLE 1,Identifier-SHAPED columns even if untagged (PRE-BUILT, catches leaks)
# MAGIC %sql
# MAGIC -- A researcher who SELECT person_id INTO my_cohort created a new identifier column with no tag.
# MAGIC -- Name/type heuristics find it. Scope to your catalog; widen to all catalogs for a full sweep.
# MAGIC SELECT table_catalog, table_schema, table_name, column_name, data_type
# MAGIC FROM system.information_schema.columns
# MAGIC WHERE table_catalog = '${catalog}'
# MAGIC   AND (lower(column_name) IN ('person_id','note_text')
# MAGIC        OR lower(column_name) LIKE '%mrn%'
# MAGIC        OR lower(column_name) LIKE '%patient_id%')
# MAGIC ORDER BY table_schema, table_name, column_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ By-value search: does THIS identifier appear? 🛠️
# MAGIC
# MAGIC Pick a real `person_id`, then check which candidate tables actually contain it. The structural
# MAGIC search (step 1) gives you the **candidate columns**; this step confirms the **value** is present:
# MAGIC the difference between "a table has a person_id column" and "a table has *this patient*."

# COMMAND ----------

# DBTITLE 1,Pick an identifier to hunt for (PRE-BUILT)
TARGET_PERSON_ID = spark.sql(f"SELECT MIN(person_id) AS pid FROM {fqn('person')}").first()["pid"]
print(f"Hunting for person_id = {TARGET_PERSON_ID} across the governed tables.")

# COMMAND ----------

# DBTITLE 1,TODO: scan the candidate tables for the target identifier
# TODO (you build this): for each table in OMOP_TABLES that has a person_id column, count rows where
#   person_id = TARGET_PERSON_ID, and collect (table, hit_count). Return a tidy result showing which
#   tables contain the identifier. (Bonus: union the per-table counts into one DataFrame and display it.)
#
# Skeleton:
# hits = []
# for t in OMOP_TABLES:
#     n = spark.sql(f"SELECT COUNT(*) AS n FROM {fqn(t)} WHERE person_id = {TARGET_PERSON_ID}").first()["n"]
#     hits.append((t, n))
# display(spark.createDataFrame(hits, ["table", "rows_with_identifier"]))
#
# EXTENSION (optional): make it generic: accept a list of (catalog.schema.table, column) candidates from
#   the structural search above and scan all of them, so it works against researcher-created tables too.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Bonus, lineage: where did the identifier flow? (PRE-BUILT)
# MAGIC
# MAGIC `system.access.table_lineage` records which tables were read to produce which others. If a researcher
# MAGIC built a derived table from `person`, this shows the edge, a second angle on "where did PHI go."
# MAGIC (Lineage is captured automatically for UC tables; may be empty if no downstream tables exist yet.)

# COMMAND ----------

# DBTITLE 1,Downstream of person / note (PRE-BUILT, read-only audit)
# MAGIC %sql
# MAGIC SELECT source_table_full_name, target_table_full_name, event_time
# MAGIC FROM system.access.table_lineage
# MAGIC WHERE source_table_schema = '${schema}'
# MAGIC   AND source_table_name IN ('person','note')
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 50;

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just did:</b> answered "where does this patient identifier live?" three ways, by tag,
# MAGIC by column shape, and by value, plus a lineage trace. That's exactly the audit the data office runs
# MAGIC when a researcher shares a derived dataset. <b>This answers Gina and Ty's identifier-search ask (#4).</b>
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[05_ai_feature_governance]($./05_ai_feature_governance)** for the limits on enabling AI features over PHI.
