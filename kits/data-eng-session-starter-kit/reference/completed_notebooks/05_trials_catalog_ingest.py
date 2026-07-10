# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 05 · TRIALS CATALOG · A LIVE FEED FROM A VOLUME · COMPLETED</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🛰️ Ingest a LIVE clinical-trials feed, incrementally, and survive bad data</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:940px; opacity:0.95">
# MAGIC     A trials registry drops nested JSON files into a Volume <b>continuously</b> while you build.
# MAGIC     Ingest them <b>incrementally with Auto Loader</b> into a schema-stable <code>VARIANT</code> bronze,
# MAGIC     flatten the good records to <code>silver_trial_criteria</code> (latest-wins per trial), and
# MAGIC     <b>quarantine the bad ones</b> so a malformed line never breaks the pipeline. New files keep
# MAGIC     arriving. Re-run the ingest and watch it pick up only what's new.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why this matters (FH ask: Chetan #15 · Jenn on bad data · feeds the Applied AI app)
# MAGIC
# MAGIC This is the **net-new dataset** this session builds. It is **not** OMOP. It is trial *reference
# MAGIC metadata*, the kind of export a registry (ClinicalTrials.gov) or a trial-management system (a CTMS
# MAGIC such as OnCore) produces. A real registry feed has three properties that make it the right vehicle
# MAGIC for the hard parts of ingestion:
# MAGIC
# MAGIC 1. **It arrives over time.** Files land continuously, not in one batch. So you ingest with
# MAGIC    **Auto Loader (`cloudFiles`)**, which tracks what it has already seen and picks up only new files.
# MAGIC 2. **It is nested and drifts.** Each trial carries an `eligibility` object; a later file adds a new
# MAGIC    criterion (`min_ecog`). Land the raw record in a **`VARIANT`** column and bronze never breaks on a
# MAGIC    new key. The new criterion just flows through the flatten.
# MAGIC 3. **It contains bad data.** Real feeds carry a record with no id, a truncated (malformed) line, a
# MAGIC    wrong-typed field. Those must be **quarantined**, not allowed to fail the whole load.
# MAGIC
# MAGIC <div style="background:#FFF3E0; border-left:6px solid #E65100; padding:12px 16px; border-radius:4px">
# MAGIC <b>The feed is live and presenter-controlled.</b> Your instructor started the foundation
# MAGIC <code>land_trial_feed</code> task. It drops one file at a time into a <b>shared</b> Volume: clean
# MAGIC trials first, then a schema change, then bad records. One producer, many consumers: <b>you</b> point
# MAGIC your own Auto Loader + checkpoint at it and write into <b>your</b> schema. It never stops until the
# MAGIC presenter cancels it, so re-running your ingest always has something new to pick up.
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px; margin-top:8px">
# MAGIC <b>Why the Applied AI group needs this.</b> Their pre-screen and the coordinator app screen patients
# MAGIC against <i>whatever trials exist in <code>silver_trial_criteria</code></i>. Adding a trial becomes a
# MAGIC file landing here, not a code change. This table is the contract between the two sections.
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Point at the shared landing Volume + your own ingest state (COMPLETED)
# MAGIC
# MAGIC The feed lands in the **shared foundation** schema (`source_schema`); you only **read** it. Auto
# MAGIC Loader needs two small pieces of **your own** writable state: a **schema location** and a
# MAGIC **checkpoint**. Both go in a Volume in **your** schema, so every team ingests the same feed
# MAGIC independently without stepping on each other.

# COMMAND ----------

# DBTITLE 1,Landing path (read-only, shared) + your ingest-state Volume (COMPLETED)
# The presenter's land_trial_feed task drops files here, in the SHARED foundation schema.
# This is the trials FEED (a workshop simulator), not the OMOP source, so it uses FEED_SCHEMA,
# which stays on the foundation even if you repoint SOURCE_SCHEMA at real OMOP (curated_omop.omop).
LANDING_PATH = f"/Volumes/{CATALOG}/{FEED_SCHEMA}/trial_landing/trial_catalog"

# Auto Loader's own bookkeeping lives in YOUR schema (never in the shared, read-only Volume):
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}._ingest_state")
SCHEMA_LOC = f"/Volumes/{CATALOG}/{SCHEMA}/_ingest_state/trial_catalog_schema"
CHECKPOINT = f"/Volumes/{CATALOG}/{SCHEMA}/_ingest_state/trial_catalog_bronze_ckpt"

try:
    n_files = len([f for f in dbutils.fs.ls(LANDING_PATH) if f.name.endswith(".json")])
except Exception:
    n_files = 0  # Volume/path not there yet, the feed hasn't started
print(f"📡 Reading the live feed from : {LANDING_PATH}")
print(f"   files landed so far        : {n_files}  (this number grows as the feed runs)")
print(f"   your schema location       : {SCHEMA_LOC}")
print(f"   your checkpoint            : {CHECKPOINT}")
if n_files == 0:
    print("⏳ No files yet. Ask the presenter to start (or Repair-run) the foundation land_trial_feed task.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Auto Loader → VARIANT bronze, incremental + schema-stable (COMPLETED)
# MAGIC
# MAGIC We read the files as **text** (one JSON object per line) and `try_parse_json` each line into a single
# MAGIC **`VARIANT`** column. Two payoffs:
# MAGIC
# MAGIC - **`cloudFiles` is incremental.** The checkpoint remembers which files were already ingested, so each
# MAGIC   run appends only the **new** files. `trigger(availableNow=True)` grabs everything currently landed,
# MAGIC   then stops. Re-run it later and it picks up whatever arrived since.
# MAGIC - **Bronze never breaks.** The schema is `(value, trial_raw VARIANT, _source_file, _ingested_at)` and
# MAGIC   it does **not** change no matter how many keys the JSON gains. We keep the raw `value` string too,
# MAGIC   which is what lets us quarantine a line that would not parse. `try_parse_json` returns `NULL` on a
# MAGIC   malformed line instead of failing the batch.

# COMMAND ----------

# DBTITLE 1,Incremental Auto Loader ingest to bronze_trial_catalog (COMPLETED)
from pyspark.sql import functions as F

def ingest_new_files():
    """Pick up only files not yet seen, parse to VARIANT, append to bronze. Re-runnable."""
    stream = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "text")          # one JSON object per line
        .option("cloudFiles.schemaLocation", SCHEMA_LOC)
        .load(LANDING_PATH)
        .withColumn("trial_raw", F.expr("try_parse_json(value)"))  # NULL on a malformed line
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_ingested_at", F.current_timestamp())
    )
    q = (
        stream.writeStream
        .option("checkpointLocation", CHECKPOINT)
        .option("mergeSchema", "true")
        .trigger(availableNow=True)                   # ingest what's here now, then stop
        .toTable(fqn("bronze_trial_catalog"))
    )
    q.awaitTermination()

ingest_new_files()

print("Bronze schema (stable, one VARIANT column plus lineage):")
spark.table(fqn("bronze_trial_catalog")).printSchema()
print(f"Bronze rows so far: {spark.table(fqn('bronze_trial_catalog')).count()}")
display(spark.sql(f"""
  SELECT trial_raw:trial_id::string AS trial_id,
         trial_raw:load_ts::string  AS load_ts,
         trial_raw:feed_version::int AS feed_version,
         _source_file
  FROM {fqn('bronze_trial_catalog')}
  ORDER BY _source_file
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Flatten the GOOD records → `silver_trial_criteria` (COMPLETED)
# MAGIC
# MAGIC A downstream eligibility join wants **real columns**, not a blob. We extract each criterion out of the
# MAGIC `VARIANT`. A missing key reads as `NULL`, meaning "this trial does not constrain that field", which is what
# MAGIC lets one generic join serve every trial. Two rules the flatten enforces:
# MAGIC
# MAGIC 1. **Latest wins.** Bronze keeps every file ever landed, so a re-landed trial appears more than once.
# MAGIC    We keep one row per `trial_id`, the newest by `load_ts`, with a `ROW_NUMBER` window.
# MAGIC 2. **Good rows only.** A record with no `trial_id`, or one that would not parse, is **not** eligible
# MAGIC    for silver. We select only well-formed rows here; the bad ones are handled in cell 4.
# MAGIC
# MAGIC Because bronze is `VARIANT`, the `min_ecog` criterion a later file adds needs **no schema surgery**.
# MAGIC We already project the path, so Trial A picks it up automatically and trials without it read `NULL`.

# COMMAND ----------

# DBTITLE 1,Flatten latest-wins per trial → silver_trial_criteria (COMPLETED)
def rebuild_silver():
    spark.sql(f"""
      CREATE OR REPLACE TABLE {fqn('silver_trial_criteria')} AS
      WITH good AS (
        SELECT * FROM {fqn('bronze_trial_catalog')}
        WHERE trial_raw IS NOT NULL                       -- parsed cleanly
          AND trial_raw:trial_id::string IS NOT NULL      -- has a dedup key
      ),
      ranked AS (
        SELECT *, ROW_NUMBER() OVER (
                   PARTITION BY trial_raw:trial_id::string
                   ORDER BY trial_raw:load_ts::timestamp DESC
                 ) AS rn
        FROM good
      )
      SELECT
        trial_raw:trial_id::string                        AS trial_id,
        trial_raw:title::string                           AS trial_name,
        trial_raw:status::string                          AS status,
        trial_raw:eligibility.sex::string                 AS req_sex,
        trial_raw:eligibility.min_age_years::int          AS age_min,
        trial_raw:eligibility.max_age_years::int          AS age_max,
        trial_raw:eligibility.her2_status::string         AS req_her2,
        trial_raw:eligibility.er_status::string           AS req_er,
        trial_raw:eligibility.pr_status::string           AS req_pr,
        trial_raw:eligibility.menopausal_status::string   AS req_menopausal,
        trial_raw:eligibility.no_prior_anti_her2::boolean AS req_no_prior_anti_her2,
        trial_raw:eligibility.min_ecog::int               AS min_ecog,
        trial_raw:eligibility_text::string                AS eligibility_text,
        trial_raw:feed_version::int                       AS feed_version,
        trial_raw:load_ts::timestamp                      AS load_ts
      FROM ranked WHERE rn = 1
    """)
    spark.sql(f"COMMENT ON TABLE {fqn('silver_trial_criteria')} IS "
              f"'Flattened, join-ready trial eligibility criteria (latest wins per trial_id). "
              f"NULL in a req_* column means the trial does not constrain that field.'")

rebuild_silver()
print("silver_trial_criteria (good, deduped, latest-wins):")
display(spark.sql(f"""
  SELECT trial_id, trial_name, req_her2, req_er, req_pr, req_menopausal,
         req_no_prior_anti_her2, age_min, age_max, min_ecog, feed_version
  FROM {fqn('silver_trial_criteria')} ORDER BY trial_id
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Quarantine the bad records (COMPLETED)
# MAGIC
# MAGIC A real feed carries bad rows, and a good pipeline **routes them aside instead of crashing**. Bronze
# MAGIC already captured every line (that is why we kept the raw `value`). Build
# MAGIC `quarantine_trial_criteria` holding every row that is **not** fit for silver, each tagged with a
# MAGIC `quarantine_reason`. The three reasons the live feed will send you:
# MAGIC
# MAGIC | reason | how to detect it |
# MAGIC |---|---|
# MAGIC | `unparseable` | `trial_raw IS NULL`, `try_parse_json` failed on a malformed line |
# MAGIC | `missing_trial_id` | parsed OK but `trial_raw:trial_id::string IS NULL`, no dedup key |
# MAGIC | `bad_type_age` | `min_age_years` is present in the raw JSON but `::int` casts to `NULL` (e.g. `"eighteen"`) |
# MAGIC
# MAGIC **Good rows still flow.** Cell 3 already wrote clean trials to silver. Quarantine is the complement,
# MAGIC not a replacement. Rebuild it (`CREATE OR REPLACE`) each run so re-ingesting keeps it in sync.

# COMMAND ----------

# DBTITLE 1,Build quarantine_trial_criteria with a reason per bad row (COMPLETED)
spark.sql(f"""
  CREATE OR REPLACE TABLE {fqn("quarantine_trial_criteria")} AS
  SELECT value AS raw_line, trial_raw, _source_file, _ingested_at,
         CASE
           WHEN trial_raw IS NULL                          THEN 'unparseable'
           WHEN trial_raw:trial_id::string IS NULL         THEN 'missing_trial_id'
           WHEN trial_raw:eligibility.min_age_years IS NOT NULL
                AND trial_raw:eligibility.min_age_years::int IS NULL THEN 'bad_type_age'
           ELSE NULL
         END AS quarantine_reason
  FROM {fqn("bronze_trial_catalog")}
  WHERE
    trial_raw IS NULL
    OR trial_raw:trial_id::string IS NULL
    OR (trial_raw:eligibility.min_age_years IS NOT NULL
        AND trial_raw:eligibility.min_age_years::int IS NULL)
""")

spark.sql(f"COMMENT ON TABLE {fqn('quarantine_trial_criteria')} IS "
          f"'Bad records quarantined from the trials feed, each tagged with a reason. "
          f"These rows are unfit for silver but preserved for audit and debugging.'")

print(f"✅ Quarantine table built with {spark.table(fqn('quarantine_trial_criteria')).count()} bad rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5️⃣ Verify: good rows in silver, bad rows quarantined (COMPLETED)
# MAGIC
# MAGIC Silver should hold the clean trials (Trial A carrying `min_ecog=1`, others `NULL`), and
# MAGIC `quarantine_trial_criteria` should hold the bad rows with a reason each. Exact counts depend on how far
# MAGIC the live feed has progressed. The point is **good and bad are separated**, and nothing crashed.

# COMMAND ----------

# DBTITLE 1,Verify the split (COMPLETED)
from pyspark.sql.utils import AnalysisException

assert "min_ecog" in spark.table(fqn("silver_trial_criteria")).columns, "silver missing min_ecog"
try:
    q = spark.table(fqn("quarantine_trial_criteria"))
except AnalysisException:
    raise Exception("quarantine_trial_criteria not built yet: complete the TODO in cell 4.")

print("Quarantine breakdown by reason:")
display(spark.sql(f"""
  SELECT quarantine_reason, COUNT(*) AS n
  FROM {fqn('quarantine_trial_criteria')}
  GROUP BY quarantine_reason ORDER BY quarantine_reason
"""))
print("Clean, join-ready trials in silver:")
display(spark.sql(f"""
  SELECT trial_id, trial_name, req_her2, req_er, req_pr, min_ecog, feed_version
  FROM {fqn('silver_trial_criteria')} ORDER BY trial_id
"""))
print("✅ Good rows flow to silver; bad rows are quarantined with a reason. The load never broke.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔁 Keep it live: re-run to pick up new files
# MAGIC
# MAGIC The feed is still running. To ingest whatever landed since your last run, re-run **cell 2** (Auto
# MAGIC Loader appends only new files via the checkpoint), then **cell 3** and **cell 4** to rebuild silver +
# MAGIC quarantine. Watch the bronze count climb and new trials appear. When the presenter cancels the
# MAGIC foundation run, the feed freezes and re-running simply finds nothing new.
# MAGIC
# MAGIC <div style="background:#E3F2FD; border-left:6px solid #1565C0; padding:10px 14px; border-radius:4px">
# MAGIC <b>Want it hands-free?</b> Wrap cells 2 to 4 in a loop, or schedule this notebook to run every few
# MAGIC minutes, or switch the trigger to <code>processingTime</code> for a continuously-running stream.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🔄 Automated re-run example (COMPLETED)
# MAGIC
# MAGIC This shows how to continuously ingest new files as they arrive:

# COMMAND ----------

# DBTITLE 1,Automated incremental ingestion loop (COMPLETED)
import time

def run_incremental_ingest(iterations=3, wait_seconds=30):
    """Run the ingest pipeline multiple times to pick up new files."""
    for i in range(iterations):
        print(f"\n📡 Iteration {i+1}/{iterations} - checking for new files...")

        # Count files before
        try:
            files_before = len([f for f in dbutils.fs.ls(LANDING_PATH) if f.name.endswith(".json")])
        except:
            files_before = 0

        # Run the ingest
        ingest_new_files()

        # Rebuild silver and quarantine
        rebuild_silver()
        spark.sql(f"""
          CREATE OR REPLACE TABLE {fqn("quarantine_trial_criteria")} AS
          SELECT value AS raw_line, trial_raw, _source_file, _ingested_at,
                 CASE
                   WHEN trial_raw IS NULL                          THEN 'unparseable'
                   WHEN trial_raw:trial_id::string IS NULL         THEN 'missing_trial_id'
                   WHEN trial_raw:eligibility.min_age_years IS NOT NULL
                        AND trial_raw:eligibility.min_age_years::int IS NULL THEN 'bad_type_age'
                   ELSE NULL
                 END AS quarantine_reason
          FROM {fqn("bronze_trial_catalog")}
          WHERE
            trial_raw IS NULL
            OR trial_raw:trial_id::string IS NULL
            OR (trial_raw:eligibility.min_age_years IS NOT NULL
                AND trial_raw:eligibility.min_age_years::int IS NULL)
        """)

        # Report stats
        bronze_count = spark.table(fqn('bronze_trial_catalog')).count()
        silver_count = spark.table(fqn('silver_trial_criteria')).count()
        quarantine_count = spark.table(fqn('quarantine_trial_criteria')).count()

        print(f"  Bronze rows: {bronze_count} | Silver trials: {silver_count} | Quarantined: {quarantine_count}")

        if i < iterations - 1:
            print(f"  Waiting {wait_seconds} seconds for more files...")
            time.sleep(wait_seconds)

    print("\n✅ Incremental ingestion complete!")

# Uncomment to run:
# run_incremental_ingest(iterations=3, wait_seconds=30)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚩 Checkpoint 5: Trials catalog is live, incremental, and bad-data-safe
# MAGIC
# MAGIC - Auto Loader ingests the live feed **incrementally**; each run picks up only new files.
# MAGIC - Bronze is a single stable `VARIANT` column; a new criterion (`min_ecog`) flows through with no
# MAGIC   schema surgery.
# MAGIC - Good records land in `silver_trial_criteria` (latest-wins per trial); bad records are
# MAGIC   **quarantined with a reason**, so a malformed line never breaks the load.
# MAGIC - `silver_trial_criteria` is the contract the Applied AI section joins against; adding a trial is a
# MAGIC   file landing, not a code change.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:14px 18px; border-radius:4px">
# MAGIC <b>✅ Success metrics:</b><br>
# MAGIC • Bronze table exists with VARIANT schema<br>
# MAGIC • Silver has clean, flattened trials with latest-wins deduplication<br>
# MAGIC • Quarantine captures all bad records with clear reasons<br>
# MAGIC • Re-running picks up only new files (incremental)<br>
# MAGIC • Schema evolution handled automatically (min_ecog added with no code change)
# MAGIC </div>
# MAGIC
# MAGIC **Stretch:** use `ai_query` to parse the free-text `eligibility_text` into structured criteria
# MAGIC (extraction on the *trial* side, mirroring the patient-side note extraction); add Lakeflow
# MAGIC EXPECTATIONS to the pipeline. See `STRETCH.md`.