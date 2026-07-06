# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 01 · SCHEMA EVOLUTION · YOU WIRE THE EVOLUTION MODE</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧬 Ingest a table whose schema changes under you</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     The source adds a new column next quarter. Make the ingest <b>absorb it safely</b>, with no broken
# MAGIC     job and no silently-dropped data, using Delta <code>mergeSchema</code> (and the Auto Loader
# MAGIC     <code>cloudFiles</code> variant for file/stream sources).
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why this matters (FH ask: Chetan #15)
# MAGIC
# MAGIC OMOP source systems are not frozen. A vendor adds `condition_source_name`, a new lab value column
# MAGIC appears, an extract gains a `birth_date`. With a naive `append`, Delta **rejects** the write
# MAGIC (`AnalysisException: A schema mismatch detected`) and the nightly job fails. Or, worse, a mode that
# MAGIC drops unknown columns loses the new data **silently**.
# MAGIC
# MAGIC Delta gives you two switches:
# MAGIC
# MAGIC | Switch | What it does | When |
# MAGIC |---|---|---|
# MAGIC | `.option("mergeSchema", "true")` | **Adds** new columns to the target on append | additive evolution (the common case) |
# MAGIC | `.option("overwriteSchema", "true")` | **Replaces** the schema entirely on overwrite | type changes / drops (rare, deliberate) |
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The wiring is pre-built; the option is yours.</b> We pre-build the bronze landing, the "v2" source
# MAGIC DataFrame that has a brand-new column, and the before/after schema diff. <b>You</b> add the one
# MAGIC option that lets the append evolve the table instead of failing.
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Land a v1 bronze table (PRE-BUILT)
# MAGIC
# MAGIC We read the read-only source `condition_occurrence`, keep a slim **v1** projection (no
# MAGIC `condition_source_name`), and write it to your schema as `bronze_condition_occurrence`. This is the
# MAGIC "table already in production" you're about to evolve.

# COMMAND ----------

# DBTITLE 1,Write the v1 bronze table: slim projection, no new column (PRE-BUILT)
from pyspark.sql import functions as F

V1_COLS = ["condition_occurrence_id", "person_id", "condition_start_date", "condition_source_value"]

v1 = spark.table(src("condition_occurrence")).select(*V1_COLS)
(v1.write.mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(fqn("bronze_condition_occurrence")))

print("v1 bronze schema:")
spark.table(fqn("bronze_condition_occurrence")).printSchema()
print(f"v1 rows: {spark.table(fqn('bronze_condition_occurrence')).count()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ The source ships a NEW column (PRE-BUILT)
# MAGIC
# MAGIC Next quarter's extract adds **`condition_source_name`**, a human-readable condition label. Here's
# MAGIC the incoming **v2** DataFrame: the same rows, plus that one new column. We do **not** write it yet.

# COMMAND ----------

# DBTITLE 1,Build the incoming v2 DataFrame with an extra column (PRE-BUILT)
v2 = (spark.table(src("condition_occurrence"))
        .select(*V1_COLS, "condition_source_name"))  # <- the NEW column

print("Incoming v2 columns:", v2.columns)
print("New column not yet in the target:",
      "condition_source_name" not in spark.table(fqn("bronze_condition_occurrence")).columns)
display(v2.select("person_id", "condition_source_value", "condition_source_name").limit(5))

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 3️⃣ Prove the naive append FAILS (PRE-BUILT, see the error you must fix)
# MAGIC
# MAGIC Append v2 with **no** schema option. Delta refuses, because the incoming frame has a column the
# MAGIC target doesn't. This is the broken nightly job. (We catch the error so the notebook keeps running.)

# COMMAND ----------

# DBTITLE 1,Naive append → expect a schema-mismatch failure (PRE-BUILT)
try:
    v2.write.mode("append").saveAsTable(fqn("bronze_condition_occurrence"))
    print("⚠ Unexpected: the append succeeded without a schema option.")
except Exception as e:
    msg = str(e)
    print("❌ As expected, the naive append FAILED:")
    print("   " + msg.splitlines()[0][:160])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ 🛠️ TODO: make the append EVOLVE the table
# MAGIC
# MAGIC Append the same `v2` DataFrame, but this time turn on **schema merge** so Delta adds
# MAGIC `condition_source_name` to the target instead of failing. One option does it.

# COMMAND ----------

# DBTITLE 1,TODO: append v2 with schema evolution turned on (YOU BUILD THIS)
# TODO (you build this): write `v2` in append mode to fqn("bronze_condition_occurrence") with the ONE
#   option that lets Delta add the new column automatically.
# WHY: the source will keep adding columns; the ingest must absorb them, not break, and not drop data.
# PATTERN:
#   (v2.write.mode("append")
#       .option("<the option>", "true")          # <- this is the whole lesson
#       .saveAsTable(fqn("bronze_condition_occurrence")))
# HINT: it is the option in the table at the top of this notebook that *adds* columns on append.

# ---- your code below ----


# COMMAND ----------

# MAGIC %md
# MAGIC ## 5️⃣ Verify the table evolved (PRE-BUILT, runs once your TODO appends)
# MAGIC
# MAGIC The target should now have the new column, the old rows should read it as `NULL`, and the new rows
# MAGIC should carry the value.

# COMMAND ----------

# DBTITLE 1,Before/after: the column was added, no job broke, no data lost (PRE-BUILT)
cols = spark.table(fqn("bronze_condition_occurrence")).columns
assert "condition_source_name" in cols, (
    "condition_source_name is NOT in the target yet. Finish the TODO in the previous cell.")

print("✅ Target schema now includes the new column:")
spark.table(fqn("bronze_condition_occurrence")).printSchema()

# COMMAND ----------

# DBTITLE 1,Old rows = NULL for the new column, new rows populated (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT
# MAGIC   CASE WHEN condition_source_name IS NULL THEN 'pre-evolution (NULL)' ELSE 'post-evolution (populated)' END AS cohort,
# MAGIC   COUNT(*) AS rows
# MAGIC FROM bronze_condition_occurrence
# MAGIC GROUP BY 1 ORDER BY 1;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 📁 The Auto Loader (`cloudFiles`) variant, for file / streaming sources
# MAGIC
# MAGIC When the source is **files landing in a volume** (the classic OMOP-extract drop), Auto Loader does
# MAGIC the same evolution incrementally, tracking the schema in a checkpoint. The mode that matters is
# MAGIC `cloudFiles.schemaEvolutionMode`:
# MAGIC
# MAGIC | `schemaEvolutionMode` | Behavior |
# MAGIC |---|---|
# MAGIC | `addNewColumns` (default) | new columns are added; the stream restarts to pick them up |
# MAGIC | `rescue` | unknown columns are captured into a `_rescued_data` column (nothing lost) |
# MAGIC | `none` | ignore new columns |
# MAGIC | `failOnNewColumns` | fail the stream (force a human to decide) |
# MAGIC
# MAGIC ```python
# MAGIC # Reference pattern (needs a file source in a UC volume; mergeSchema above is the serverless-friendly path):
# MAGIC (spark.readStream.format("cloudFiles")
# MAGIC    .option("cloudFiles.format", "json")
# MAGIC    .option("cloudFiles.schemaLocation", f"/Volumes/{CATALOG}/{SCHEMA}/checkpoints/condition")
# MAGIC    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")   # <- the evolution switch
# MAGIC    .load(f"/Volumes/{CATALOG}/{SCHEMA}/landing/condition/")
# MAGIC  .writeStream
# MAGIC    .option("mergeSchema", "true")
# MAGIC    .option("checkpointLocation", f"/Volumes/{CATALOG}/{SCHEMA}/checkpoints/condition_write")
# MAGIC    .trigger(availableNow=True)
# MAGIC    .toTable(fqn("bronze_condition_occurrence")))
# MAGIC ```
# MAGIC
# MAGIC Same idea, two delivery shapes: **batch `mergeSchema`** (you built it above) and **streaming
# MAGIC `cloudFiles.schemaEvolutionMode`** (drop OMOP files in a volume and run the snippet, see `STRETCH.md`).

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you built:</b> an append that <b>evolves</b> the table when the source adds a column. The
# MAGIC nightly job survives the change and every new field is captured. That's the difference between a
# MAGIC 2am page and a clean morning.
# MAGIC </div>
# MAGIC
# MAGIC <!-- EXTENSION (optional): land OMOP rows as JSON files in a UC volume and run the Auto Loader
# MAGIC      cloudFiles snippet end-to-end; or evolve a TYPE (overwriteSchema) and discuss when that's safe. -->
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[02_row_count_reconciliation]($./02_row_count_reconciliation)** to prove every source row actually landed.
