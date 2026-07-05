# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 02 · RECONCILIATION · YOU BUILD THE ANTI-JOINS</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🔢 Prove every source row actually landed</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     A reconciliation framework: source↔target row counts, an anti-join that names the <b>exact
# MAGIC     missing keys</b>, and one <b>reconciliation summary table</b> you can put in front of an auditor.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why this matters (FH ask: Chetan #17)
# MAGIC
# MAGIC "Did we load everything?" is a question a clinical-data team must answer with **evidence**, not a
# MAGIC shrug. A row-count match is necessary but not sufficient — you also need to know **which records are
# MAGIC missing** when counts disagree. This notebook builds a reusable reconciliation framework over all 6
# MAGIC OMOP tables:
# MAGIC
# MAGIC 1. **Counts** — source vs. target, per table, with a delta and a pass/fail flag.
# MAGIC 2. **Anti-join** — the source keys with **no match** in the target (the missing records).
# MAGIC 3. **Summary table** — `recon_summary`, one persisted row per table per run, timestamped for audit.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The harness is pre-built; the reconciliation logic is yours.</b> We pre-build the bronze copies
# MAGIC (one with an <b>injected mismatch</b>), the summary-table writer, and the reporting. <b>You</b> write
# MAGIC the count comparison and the missing-key anti-join.
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Land bronze copies — with one deliberate mismatch (PRE-BUILT)
# MAGIC
# MAGIC We copy each source table into your schema as `bronze_<table>`. For **`measurement`** we deliberately
# MAGIC **drop 7 rows** to simulate a dropped-record incident — your reconciliation must catch it and name
# MAGIC the missing keys. The other tables copy clean (counts should match exactly).

# COMMAND ----------

# DBTITLE 1,Copy source → bronze; inject a 7-row gap in measurement (PRE-BUILT)
from pyspark.sql import functions as F

DROPPED_MEASUREMENT_IDS = [101, 202, 303, 404, 505, 606, 707]  # the planted "missing" rows

for t in OMOP_TABLES:
    df = spark.table(src(t))
    if t == "measurement":
        df = df.filter(~F.col("measurement_id").isin(DROPPED_MEASUREMENT_IDS))  # inject the gap
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(fqn(f"bronze_{t}"))

print("✅ Bronze copies written. measurement is short by", len(DROPPED_MEASUREMENT_IDS), "rows on purpose.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ 🛠️ TODO — count reconciliation (source vs. target, per table)
# MAGIC
# MAGIC Build a DataFrame with one row per OMOP table: the **source count**, the **target count**, the
# MAGIC **delta**, and a `match` boolean. This is the top-line "did the counts agree?" answer.

# COMMAND ----------

# DBTITLE 1,TODO — build the per-table count comparison (YOU BUILD THIS)
# TODO (you build this): produce `count_recon` — a DataFrame with columns
#   table_name, source_count, target_count, delta, match (boolean)
#   for every table in OMOP_TABLES.
# PATTERN: loop OMOP_TABLES, count spark.table(src(t)) and spark.table(fqn("bronze_"+t)), assemble rows,
#   then spark.createDataFrame(rows, schema). delta = source_count - target_count; match = (delta == 0).
# WHY: this is the headline number a steward checks first; the anti-join below explains any non-zero delta.

# rows = []
# for t in OMOP_TABLES:
#     s = spark.table(src(t)).count()
#     g = spark.table(fqn("bronze_"+t)).count()
#     rows.append((t, s, g, s - g, s - g == 0))
# count_recon = spark.createDataFrame(rows, "table_name string, source_count long, target_count long, delta long, match boolean")

# ---- your code below ----


display(count_recon.orderBy("match"))   # mismatches float to the top

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ 🛠️ TODO — find the MISSING keys (anti-join)
# MAGIC
# MAGIC A count delta tells you *how many* are missing; an **anti-join** tells you *which*. Find the
# MAGIC `measurement_id`s present in the **source** `measurement` but absent from your **bronze** copy.

# COMMAND ----------

# DBTITLE 1,TODO — anti-join to list the missing measurement keys (YOU BUILD THIS)
# MAGIC %sql
# MAGIC -- TODO (you build this): return the measurement_id (and person_id) of every row that is in the
# MAGIC --   SOURCE measurement but NOT in your bronze_measurement copy.
# MAGIC -- PATTERN (a LEFT ANTI JOIN is the cleanest):
# MAGIC --   SELECT s.measurement_id, s.person_id
# MAGIC --   FROM <source_schema>.measurement s
# MAGIC --   LEFT ANTI JOIN bronze_measurement b ON s.measurement_id = b.measurement_id;
# MAGIC -- TIP: your source is in a DIFFERENT schema — qualify it. _config exposes it as the `src()` helper
# MAGIC --   in Python; in SQL, reference ${...} via the source_schema widget, e.g.
# MAGIC --   serverless..._catalog.clinops_foundation.measurement  (use your own catalog/source_schema).
# MAGIC -- EXPECTED: exactly the 7 planted ids (101, 202, 303, 404, 505, 606, 707).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Persist a reconciliation summary table (PRE-BUILT — runs on your `count_recon`)
# MAGIC
# MAGIC The counts are ephemeral; the **audit trail** is not. We append `count_recon` to a persisted
# MAGIC `recon_summary` table with a run timestamp, so every reconciliation run is queryable later.

# COMMAND ----------

# DBTITLE 1,Append count_recon to the audit summary table (PRE-BUILT)
summary = (count_recon
           .withColumn("recon_ts", F.current_timestamp())
           .withColumn("status", F.when(F.col("match"), F.lit("PASS")).otherwise(F.lit("FAIL"))))

(summary.write.mode("append").option("mergeSchema", "true").saveAsTable(fqn("recon_summary")))

print("✅ recon_summary written. Latest run:")
display(spark.table(fqn("recon_summary")).orderBy(F.col("recon_ts").desc(), F.col("status").desc()))

# COMMAND ----------

# DBTITLE 1,The headline reconciliation verdict (PRE-BUILT)
fails = count_recon.filter(~F.col("match")).count()
if fails == 0:
    print("✅ RECONCILED: every table's source and target counts agree.")
else:
    print(f"❌ {fails} table(s) FAILED reconciliation — see the missing keys above. "
          "(measurement is expected to fail by exactly 7 in this kit.)")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you built:</b> a reusable reconciliation framework — counts, the exact missing keys, and a
# MAGIC timestamped audit table. When a steward asks "did we load everything?", you don't guess; you query
# MAGIC <code>recon_summary</code> and name the 7 missing <code>measurement</code> rows.
# MAGIC </div>
# MAGIC
# MAGIC <!-- EXTENSION (optional): add a column-level checksum (e.g. SUM(value_as_number)) to catch
# MAGIC      value drift even when counts match; or schedule this as a post-ingest job task that fails on FAIL. -->
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[03_restricted_table_ingest_gate]($./03_restricted_table_ingest_gate)** to block restricted tables before they ever land.
