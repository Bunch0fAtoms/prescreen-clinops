# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:14px 18px; border-radius:4px">
# MAGIC <b>📌 These notebooks are optional facilitator backup reference.</b> The Data Engineering session
# MAGIC is built <b>live with Genie Code</b> following <code>GENIE_CODE_PROMPTS.md</code> (Track 1 Spark
# MAGIC Structured Streaming notebook scheduled as a Job, or Track 2 a Lakeflow Declarative Pipeline). The
# MAGIC one pipeline the team builds there teaches all four Fred Hutch asks, so there is nothing special
# MAGIC about running them separately on the OMOP tables. Pull these up only if a team stalls.<br><br>
# MAGIC <b>There is no bundle to deploy for this kit</b> anymore: only the shared foundation deploys a DAB.
# MAGIC Ignore any "deploy the bundle" or <code>resources/sla_ingest_job.yml</code> mentions below; they
# MAGIC describe an earlier design. TODO (package author): fully reconcile or retire notebooks 01 to 04
# MAGIC against the trials-feed build, and align notebook 05 with the validated Genie Code pipeline.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:28px 32px; border-radius:8px">
# MAGIC   <div style="font-size:0.95em; letter-spacing:2px; opacity:0.85">FRED HUTCHINSON CANCER CENTER · DATA ENGINEERING SESSION · STARTER KIT</div>
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
# MAGIC ## 👋 This is a starter kit: you build the core
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:14px 18px; border-radius:4px">
# MAGIC The <b>plumbing is wired for you</b>: the 6 synthetic OMOP source tables, the bronze landing
# MAGIC pattern, Unity Catalog scoping, and all the boilerplate. <b>You</b> write the learnable data-engineering
# MAGIC logic: the schema-evolution wiring, the reconciliation anti-joins, the ingest-gate guard, and the
# MAGIC SLA-window guard.<br><br>
# MAGIC Look for <b><code>&#35; TODO (you build this)</code></b> markers. That's your work. Hooks marked
# MAGIC <b><code>&#35; EXTENSION (optional)</code></b> are stretch goals (see <code>STRETCH.md</code>).
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🩺 The business problem
# MAGIC
# MAGIC A clinical-data engineering team ingests OMOP tables from a source system into the lakehouse on a
# MAGIC nightly schedule. Four things keep going wrong, and each is a submitted Fred Hutch ask:
# MAGIC
# MAGIC | # | The pain | Notebook |
# MAGIC |---|---|---|
# MAGIC | 1 | The source adds a column and the ingest job **breaks** (or silently drops it). | `01` schema evolution |
# MAGIC | 2 | Did we load **every** row? Which records are **missing**? Nobody can prove it. | `02` reconciliation |
# MAGIC | 3 | A **restricted** table gets ingested by accident, a governance incident. | `03` ingest gate |
# MAGIC | 4 | A job hammers the source **during the 11pm to 8am batch window** it must stay out of. | `04` SLA window |
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
# MAGIC  │  6 OMOP CDM source tables    │   person · condition_occurrence · measurement
# MAGIC  │  (read-only, synthetic)      │   observation · drug_exposure · note
# MAGIC  └───────────┬──────────────────┘   src('<table>')  (you do NOT modify these)
# MAGIC              │
# MAGIC   ┌──────────┴───────────────────────────────────────────────┐
# MAGIC   │  nb 03  INGEST GATE  : allow/deny-list guard (UC table)    │  🛠️ you
# MAGIC   │  nb 04  SLA-WINDOW GUARD : skip 11pm to 8am batch window   │  🛠️ you
# MAGIC   └──────────┬───────────────────────────────────────────────┘
# MAGIC              │  (guards pass)
# MAGIC              ▼
# MAGIC  ┌──────────────────────────────┐
# MAGIC  │  BRONZE landing (your schema) │  nb 01  mergeSchema / Auto Loader evolution  🛠️ you
# MAGIC  │  schema EVOLVES on new column │
# MAGIC  └───────────┬──────────────────┘
# MAGIC              ▼
# MAGIC  ┌──────────────────────────────┐
# MAGIC  │  RECONCILIATION              │  nb 02  counts + anti-joins + summary table  🛠️ you
# MAGIC  │  source ↔ bronze, missing keys│
# MAGIC  └──────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC The four notebooks are **independent**. You can build them in any order. `01`→`02` form a natural
# MAGIC ingest→verify pair; `03` and `04` are reusable guards you'd call *before* any ingest.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📒 The notebooks
# MAGIC
# MAGIC Each one is self-contained and starts by `%run ./_config`.
# MAGIC
# MAGIC | # | Notebook | What it builds | Your job? | FH ask |
# MAGIC |---|---|---|---|---|
# MAGIC | 01 | `01_schema_evolution` | Append data with a NEW column; the Delta table evolves safely | 🛠️ wire the evolution mode | Chetan #15 |
# MAGIC | 02 | `02_row_count_reconciliation` | Source↔target counts + anti-joins for missing keys + summary table | 🛠️ build the reconciliation | Chetan #17 |
# MAGIC | 03 | `03_restricted_table_ingest_gate` | A reusable guard that blocks restricted tables from a UC allow-list | 🛠️ build the guard | Jenn #16 |
# MAGIC | 04 | `04_sla_job_windows` | A runtime guard that skips the 11pm to 8am SLA window + the Jobs schedule pattern | 🛠️ build the guard | Jennifer #9 |

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Prerequisites & foundation check
# MAGIC
# MAGIC - A Unity Catalog-enabled workspace and permission to create a schema (your `client_schema`).
# MAGIC - **Serverless** notebook compute.
# MAGIC - Read access to the 6 OMOP source tables in your `source_schema` (read-only, do **not** modify them).
# MAGIC - You deployed the bundle (`databricks bundle deploy --target client`). See the README.
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
# MAGIC ### → Open **[01_schema_evolution]($./01_schema_evolution)** to ingest data whose schema changes under you.
