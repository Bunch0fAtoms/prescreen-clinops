# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:28px 32px; border-radius:8px">
# MAGIC   <div style="font-size:0.95em; letter-spacing:2px; opacity:0.85">FRED HUTCHINSON CANCER CENTER · DATA ENGINEERING SESSION · COMPLETED REFERENCE</div>
# MAGIC   <div style="font-size:2.3em; font-weight:700; margin-top:6px">🛠️ Governed, Reconciled OMOP Ingestion</div>
# MAGIC   <div style="font-size:1.15em; margin-top:10px; max-width:880px; opacity:0.95">
# MAGIC     Build the ingestion plumbing a clinical-data team actually has to get right: schema that
# MAGIC     evolves safely, row counts that reconcile to the source, a programmatic gate that blocks
# MAGIC     restricted tables, and a guard that keeps jobs out of the source's SLA window, all on the
# MAGIC     Databricks Data Intelligence Platform.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 📌 These are the completed reference notebooks
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:14px 18px; border-radius:4px">
# MAGIC These notebooks show the <b>completed solutions</b> for the Data Engineering session. The main build
# MAGIC is <b>notebook 05 (Trials Catalog Ingest)</b> which teaches:<br>
# MAGIC • <b>Incremental ingestion</b> with Auto Loader<br>
# MAGIC • <b>Schema evolution</b> with VARIANT columns<br>
# MAGIC • <b>Bad data quarantine</b> with clear reasons<br>
# MAGIC • <b>Latest-wins deduplication</b> with window functions<br><br>
# MAGIC
# MAGIC Notebooks 01 to 04 are optional reconciliation patterns that address specific Fred Hutch asks.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🩺 The business problem
# MAGIC
# MAGIC A clinical-data engineering team ingests OMOP tables from a source system into the lakehouse on a
# MAGIC nightly schedule. Four things keep going wrong, and each is a submitted Fred Hutch ask:
# MAGIC
# MAGIC | # | The pain | Notebook | Status |
# MAGIC |---|---|---|---|
# MAGIC | 1 | The source adds a column and the ingest job **breaks** (or silently drops it). | `01` schema evolution | Optional |
# MAGIC | 2 | Did we load **every** row? Which records are **missing**? Nobody can prove it. | `02` reconciliation | Optional |
# MAGIC | 3 | A **restricted** table gets ingested by accident, a governance incident. | `03` ingest gate | Optional |
# MAGIC | 4 | A job hammers the source **during the 11pm to 8am batch window** it must stay out of. | `04` SLA window | Optional |
# MAGIC | 5 | **Live trial feed** needs incremental ingest with bad data handling | `05` trials catalog | **MAIN BUILD** |
# MAGIC
# MAGIC This is a **security-first** customer: every answer is config-driven, Unity-Catalog-scoped, audited,
# MAGIC and uses **synthetic data only**.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## ✨ The value moment: ingestion you can defend in an audit
# MAGIC
# MAGIC <div style="display:flex; gap:14px; flex-wrap:wrap; margin-top:8px">
# MAGIC   <div style="flex:1; min-width:210px; background:#E8F5E9; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.4em; font-weight:700; color:#2E7D32">Evolves</div>
# MAGIC     Source adds a column → the table absorbs it. <b>No broken job, no dropped data.</b>
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:210px; background:#E3F2FD; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.4em; font-weight:700; color:#1565C0">Reconciles</div>
# MAGIC     Source count == target count, and the <b>exact missing keys</b> are named in a table.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:210px; background:#FFEBEE; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.4em; font-weight:700; color:#C62828">Gates</div>
# MAGIC     A restricted table is <b>blocked before a single row lands</b>, from a UC allow-list, not code.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:210px; background:#FFF3E0; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.4em; font-weight:700; color:#E65100">Respects SLA</div>
# MAGIC     A job that wakes up at 2am <b>skips the source</b> until the 8am window opens.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🏗️ Architecture & flow
# MAGIC
# MAGIC ```
# MAGIC  ┌──────────────────────────────┐
# MAGIC  │  Live Trial Feed (Volume)    │   JSON files landing continuously
# MAGIC  │  /trial_landing/trial_catalog│   Clean → Schema evolution → Bad records
# MAGIC  └───────────┬──────────────────┘
# MAGIC              │
# MAGIC   ┌──────────┴───────────────────────────────────────────────┐
# MAGIC   │  Auto Loader (cloudFiles)                                  │
# MAGIC   │  • Incremental ingestion (checkpoint tracking)              │
# MAGIC   │  • Schema-stable VARIANT bronze                            │
# MAGIC   └──────────┬───────────────────────────────────────────────┘
# MAGIC              │
# MAGIC              ├─────────────┐
# MAGIC              ▼             ▼
# MAGIC  ┌──────────────────┐  ┌──────────────────┐
# MAGIC  │  SILVER          │  │  QUARANTINE       │
# MAGIC  │  Good records    │  │  Bad records      │
# MAGIC  │  Latest-wins     │  │  With reasons     │
# MAGIC  └──────────────────┘  └──────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📒 The completed notebooks
# MAGIC
# MAGIC Each one is self-contained and starts by `%run ./_config`.
# MAGIC
# MAGIC | # | Notebook | What it demonstrates | FH ask |
# MAGIC |---|---|---|---|
# MAGIC | 00 | `00_START_HERE` | Setup and foundation check | All |
# MAGIC | 05 | **`05_trials_catalog_ingest`** | **MAIN BUILD: Incremental ingest + quarantine** | Chetan #15, Jenn |
# MAGIC | 01 | `01_schema_evolution` | Schema evolution with mergeSchema | Chetan #15 |
# MAGIC | 02 | `02_row_count_reconciliation` | Source↔target reconciliation | Chetan #17 |
# MAGIC | 03 | `03_restricted_table_ingest_gate` | UC-based allow-list guard | Jenn #16 |
# MAGIC | 04 | `04_sla_job_windows` | Time-based SLA window guard | Jennifer #9 |

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Prerequisites & foundation check
# MAGIC
# MAGIC - A Unity Catalog-enabled workspace and permission to create a schema (your `client_schema`).
# MAGIC - **Serverless** notebook compute.
# MAGIC - Read access to the 6 OMOP source tables in your `source_schema` (read-only, do **not** modify them).
# MAGIC - The foundation job is running (`land_trial_feed` task) to provide the live feed.
# MAGIC - Set the widgets below to match your bundle, then run the foundation check.

# COMMAND ----------

# DBTITLE 1,Set your targets here (these flow to every notebook)
# MAGIC %run ./_config

# COMMAND ----------

# DBTITLE 1,Foundation check: the 6 source tables exist & your schema is writable
from pyspark.sql import functions as F

rows = []
for t in OMOP_TABLES:
    try:
        n = spark.table(src(t)).count()
        rows.append((t, n, "✅" if n > 0 else "⚠ empty"))
    except Exception as e:
        rows.append((t, -1, f"❌ {str(e)[:60]}"))

display(spark.createDataFrame(rows, "source_table string, row_count long, status string"))

# A tiny write to prove YOUR schema is writable (then drop it).
spark.sql(f"CREATE TABLE IF NOT EXISTS {fqn('_foundation_check')} (ok int)")
spark.sql(f"INSERT OVERWRITE {fqn('_foundation_check')} VALUES (1)")
spark.sql(f"DROP TABLE {fqn('_foundation_check')}")
print(f"✅ Your schema {CATALOG}.{SCHEMA} is writable.")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Expected:</b> person=300, condition_occurrence=300, measurement=720, observation=720,
# MAGIC drug_exposure=383, note=265, all ✅, and "your schema is writable."<br>
# MAGIC If a source table is missing, fix your <code>source_schema</code> widget. If your write fails, you
# MAGIC don't have CREATE on your <code>schema</code>. Pull a mentor (this is plumbing, not your lesson).
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[05_trials_catalog_ingest]($./05_trials_catalog_ingest)** for the main DE build (incremental ingest with bad data handling).
# MAGIC
# MAGIC Optional reconciliation patterns are in notebooks 01 to 04.