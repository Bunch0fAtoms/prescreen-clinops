# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 05 · TRIALS CATALOG · A NET-NEW FEED FROM A VOLUME</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🗂️ Ingest a clinical-trials catalog whose criteria drift over time</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:900px; opacity:0.95">
# MAGIC     A trials registry feed lands as <b>nested JSON files in a Volume</b>, in waves, to simulate a
# MAGIC     live pipeline. Land it in a schema-stable <code>VARIANT</code> bronze, then flatten it to the
# MAGIC     <code>silver_trial_criteria</code> table the pre-screen joins against. When a later wave adds a
# MAGIC     new eligibility field, the flatten must <b>evolve</b>, not break.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why this matters (FH ask: Chetan #15 · and it feeds the Applied AI app)
# MAGIC
# MAGIC This is the **net-new dataset** this session builds. It is **not** OMOP and not the clean silver the
# MAGIC other group owns — it is trial *reference metadata*, the kind of export a registry (ClinicalTrials.gov)
# MAGIC or an internal trial-management system (a CTMS such as OnCore) produces. Real trial data has two
# MAGIC properties that make it the right vehicle for schema evolution:
# MAGIC
# MAGIC 1. **It is nested and semi-structured.** Each trial carries an `eligibility` object plus a free-text
# MAGIC    criteria blob. So we land the raw record in a `VARIANT` column, which never breaks on a new key.
# MAGIC 2. **Its criteria drift.** Registries add eligibility fields over time (a `min_ecog`, a required
# MAGIC    biomarker). The pain Chetan described happens when that new field must become a **new column** in
# MAGIC    the flattened table a downstream join uses.
# MAGIC
# MAGIC So the schema-evolution problem moves to the **flatten step**: bronze (VARIANT) is stable, but the
# MAGIC append into the columnar `silver_trial_criteria` fails when a new criterion appears — unless you wire
# MAGIC `mergeSchema`. That is your TODO.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Why the Applied AI group needs this.</b> Their pre-screen and the coordinator app screen patients
# MAGIC against <i>whatever trials exist in this table</i>. Adding a trial becomes dropping a file here, not a
# MAGIC code change. This table is the contract between the two sections.
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Create the landing Volume (PRE-BUILT)
# MAGIC
# MAGIC A Unity Catalog **managed Volume** is where the "pipeline" drops trial files. Everything stays
# MAGIC UC-governed — no DBFS, no external storage to wire.

# COMMAND ----------

# DBTITLE 1,Create the trials landing Volume (PRE-BUILT)
import os, json

VOLUME       = "trial_landing"
VOLUME_PATH  = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/trial_catalog"

spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
os.makedirs(VOLUME_PATH, exist_ok=True)
print(f"✅ Landing path ready: {VOLUME_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Wave 1 — the pipeline drops three trials (PRE-BUILT)
# MAGIC
# MAGIC Realistic nested records: a few structured fields, an `eligibility` object, and a free-text
# MAGIC `eligibility_text` blob (exactly what a real registry exposes). **Trial A** and **Trial B** carry the
# MAGIC same criteria the validated pre-screen already uses, so the downstream numbers are unchanged. **Trial
# MAGIC C** is net-new: a triple-negative screen. Adding it later is just another file.

# COMMAND ----------

# DBTITLE 1,Write wave 1 — three nested trial JSON files (PRE-BUILT)
wave1 = [
    {
        "trial_id": "A", "title": "HER2-Positive Advanced Breast Cancer Study", "status": "Recruiting",
        "phase": "Phase 2",
        "eligibility": {
            "sex": "Female", "min_age_years": 18, "max_age_years": 75,
            "her2_status": "Positive", "no_prior_anti_her2": True,
        },
        "eligibility_text": ("Inclusion: histologically confirmed HER2-positive breast cancer; age 18-75; "
                             "no prior anti-HER2 therapy. Exclusion: significant cardiac disease."),
    },
    {
        "trial_id": "B", "title": "ER-Positive / HER2-Negative Postmenopausal Study", "status": "Recruiting",
        "phase": "Phase 3",
        "eligibility": {
            "sex": "Female", "min_age_years": 18, "max_age_years": 75,
            "er_status": "Positive", "her2_status": "Negative", "menopausal_status": "Postmenopausal",
        },
        "eligibility_text": ("Inclusion: ER-positive, HER2-negative breast cancer; postmenopausal; age 18-75. "
                             "Exclusion: prior endocrine therapy within 6 months."),
    },
    {
        "trial_id": "C", "title": "Triple-Negative Breast Cancer Screening Study", "status": "Recruiting",
        "phase": "Phase 2",
        "eligibility": {
            "sex": "Female", "min_age_years": 18, "max_age_years": 75,
            "er_status": "Negative", "pr_status": "Negative", "her2_status": "Negative",
        },
        "eligibility_text": ("Inclusion: triple-negative (ER-, PR-, HER2-) breast cancer; age 18-75. "
                             "Exclusion: prior chemotherapy for metastatic disease."),
    },
]

with open(f"{VOLUME_PATH}/trials_2026Q1.json", "w") as f:
    for rec in wave1:
        f.write(json.dumps(rec) + "\n")   # newline-delimited JSON, one trial per line

print(f"✅ Wave 1 landed: {len(wave1)} trials → trials_2026Q1.json")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Land bronze as VARIANT — schema-stable by design (PRE-BUILT)
# MAGIC
# MAGIC We read the raw file text and `parse_json` it into a single **`VARIANT`** column. This is the
# MAGIC modern pattern for semi-structured feeds: the bronze schema is `(trial_raw VARIANT, _source_file,
# MAGIC _ingested_at)` and it **never changes**, no matter how many keys the JSON gains. That is the point —
# MAGIC nested landing does not break on new fields.

# COMMAND ----------

# DBTITLE 1,Read the files, parse to VARIANT, write bronze (PRE-BUILT)
from pyspark.sql import functions as F

def land_bronze(path_glob: str):
    raw = (spark.read.text(path_glob, wholetext=False)          # one JSON object per line
             .withColumn("trial_raw", F.parse_json(F.col("value")))
             .withColumn("_source_file", F.col("_metadata.file_path"))
             .withColumn("_ingested_at", F.current_timestamp())
             .drop("value"))
    (raw.write.mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(fqn("bronze_trial_catalog")))

land_bronze(f"{VOLUME_PATH}/trials_2026Q1.json")

print("Bronze schema (stable — one VARIANT column):")
spark.table(fqn("bronze_trial_catalog")).printSchema()
display(spark.sql(f"""
  SELECT trial_raw:trial_id::string   AS trial_id,
         trial_raw:title::string      AS title,
         trial_raw:eligibility        AS eligibility
  FROM {fqn('bronze_trial_catalog')}
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Flatten to `silver_trial_criteria` — the join-ready table (PRE-BUILT for wave 1)
# MAGIC
# MAGIC A downstream eligibility join wants **real columns**, not a blob. We extract each criterion out of
# MAGIC the `VARIANT` into a typed column. A missing key reads as `NULL`, which we treat as "this trial does
# MAGIC not constrain that field." That NULL-means-unconstrained rule is what lets one generic join serve
# MAGIC every trial.
# MAGIC
# MAGIC Two things the flatten must handle:
# MAGIC 1. **Latest wave wins.** Bronze holds every file ever landed, so a re-landed trial appears twice. We
# MAGIC    keep one row per `trial_id` — the record from the newest `_source_file` — with a `ROW_NUMBER`
# MAGIC    window. Q2 supersedes Q1.
# MAGIC 2. **Wave 1 has no `min_ecog` yet.** That field does not exist in the feed until wave 2, so the
# MAGIC    wave-1 projection does not extract it. Silver starts without a `min_ecog` column. Wave 2 adds it
# MAGIC    (`include_ecog=True`), which is what forces the schema-growth decision in cell 7.

# COMMAND ----------

# DBTITLE 1,Flatten wave 1 → silver_trial_criteria (PRE-BUILT)
def flatten(bronze_table: str, include_ecog: bool = False):
    # min_ecog only exists in the feed from wave 2 on, so wave 1 leaves it out entirely.
    ecog_col = ",\n          trial_raw:eligibility.min_ecog::int                AS min_ecog" if include_ecog else ""
    return spark.sql(f"""
        WITH ranked AS (
          SELECT
            *,
            ROW_NUMBER() OVER (
              PARTITION BY trial_raw:trial_id::string
              ORDER BY _source_file DESC
            ) AS rn
          FROM {bronze_table}
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
          trial_raw:eligibility_text::string                AS eligibility_text{ecog_col},
          _ingested_at
        FROM ranked
        WHERE rn = 1
    """)

silver_v1 = flatten(fqn("bronze_trial_catalog"))  # wave 1: no min_ecog, deduped to latest per trial
(silver_v1.write.mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(fqn("silver_trial_criteria")))

spark.sql(f"COMMENT ON TABLE {fqn('silver_trial_criteria')} IS "
          f"'Flattened, join-ready trial eligibility criteria. NULL in a req_* column means the trial does not constrain that field.'")

print("Wave-1 silver_trial_criteria:")
display(spark.table(fqn("silver_trial_criteria")))

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 5️⃣ Wave 2 — the registry adds a NEW criterion (PRE-BUILT)
# MAGIC
# MAGIC Next quarter's feed adds **`min_ecog`** to Trial A (an ECOG performance-status ceiling — a very common
# MAGIC real eligibility field). The new file lands, bronze absorbs it with **no schema change** (VARIANT!).
# MAGIC Wave 2 re-lands BOTH files, so bronze now holds two Trial A records. The flatten dedups to the latest
# MAGIC record per `trial_id` (Q2 wins over Q1), and the wave-2 projection now extracts `min_ecog` — a **new
# MAGIC column** the target table does not have yet.

# COMMAND ----------

# DBTITLE 1,Write wave 2 — Trial A gains min_ecog (PRE-BUILT)
wave2 = [
    {
        "trial_id": "A", "title": "HER2-Positive Advanced Breast Cancer Study", "status": "Recruiting",
        "phase": "Phase 2",
        "eligibility": {
            "sex": "Female", "min_age_years": 18, "max_age_years": 75,
            "her2_status": "Positive", "no_prior_anti_her2": True,
            "min_ecog": 1,                       # <- the NEW criterion this wave introduces
        },
        "eligibility_text": ("Inclusion: histologically confirmed HER2-positive breast cancer; age 18-75; "
                             "no prior anti-HER2 therapy; ECOG performance status 0-1. "
                             "Exclusion: significant cardiac disease."),
    },
]
with open(f"{VOLUME_PATH}/trials_2026Q2.json", "w") as f:
    for rec in wave2:
        f.write(json.dumps(rec) + "\n")

# Re-land bronze over BOTH files. Bronze schema is unchanged — that's the VARIANT payoff.
land_bronze(f"{VOLUME_PATH}/trials_*.json")
print("Bronze still has one VARIANT column after the new field arrived:")
spark.table(fqn("bronze_trial_catalog")).printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6️⃣ Classify the change: additive vs breaking (PRE-BUILT decision gate)
# MAGIC
# MAGIC Before we touch the target we compare the incoming flattened schema to the existing one. `min_ecog` is
# MAGIC an **added** column with no drops or type changes → **additive** → safe to auto-evolve. A dropped or
# MAGIC retyped column would be **breaking** → require approval / a deliberate full reload. This is the
# MAGIC "when to auto-reload vs. require manual approval" decision Chetan asked about.

# COMMAND ----------

# DBTITLE 1,Classify incoming vs target schema (PRE-BUILT)
def classify_change(incoming_df, target_table: str) -> str:
    inc = {f.name: f.dataType for f in incoming_df.schema.fields}
    tgt = {f.name: f.dataType for f in spark.table(target_table).schema.fields}
    added   = set(inc) - set(tgt)
    dropped = set(tgt) - set(inc)
    retyped = {c for c in set(inc) & set(tgt) if inc[c] != tgt[c]}
    if not (added or dropped or retyped):
        return "none"
    if added and not dropped and not retyped:
        return "additive"
    return "breaking"

silver_v2 = flatten(fqn("bronze_trial_catalog"), include_ecog=True)  # wave 2: ADDS min_ecog
change = classify_change(silver_v2, fqn("silver_trial_criteria"))
print(f"Detected schema change: {change}")
print("New column(s):", set(silver_v2.columns) - set(spark.table(fqn('silver_trial_criteria')).columns))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7️⃣ 🛠️ TODO — apply the evolution safely (YOU BUILD THIS)
# MAGIC
# MAGIC The change is **additive**. Overwrite `silver_trial_criteria` from `silver_v2` and turn on the ONE
# MAGIC option that lets the write add the new `min_ecog` column instead of failing. Then, only if the change
# MAGIC were **breaking**, you'd gate it behind an approval flag instead of auto-applying — wire that branch
# MAGIC too.

# COMMAND ----------

# DBTITLE 1,TODO — evolve the silver table on an additive change (YOU BUILD THIS)
# TODO (you build this): when `change == "additive"`, write `silver_v2` over silver_trial_criteria with
#   the ONE option that lets the schema grow. When `change == "breaking"`, DO NOT auto-apply — raise or
#   log for manual approval unless an explicit AUTO_FULL_RELOAD_ALLOWED flag is set.
# WHY: additive drift (a new criterion) should flow through untouched; a breaking change (a dropped/retyped
#   column) must be a human decision, not a silent reload. This is the auto-vs-approve gate.
# PATTERN:
#   AUTO_FULL_RELOAD_ALLOWED = False
#   if change in ("none", "additive"):
#       (silver_v2.write.mode("overwrite")
#           .option("<the option>", "true")     # <- lets the schema grow
#           .saveAsTable(fqn("silver_trial_criteria")))
#   elif change == "breaking" and AUTO_FULL_RELOAD_ALLOWED:
#       ...  # deliberate full reload
#   else:
#       raise Exception("Breaking schema change needs manual approval")
# HINT: for an overwrite that changes the schema, it's the option that *replaces* the schema.

# ---- your code below ----


# COMMAND ----------

# MAGIC %md
# MAGIC ## 8️⃣ Verify the catalog evolved (PRE-BUILT — runs once your TODO writes)
# MAGIC
# MAGIC `silver_trial_criteria` should now have a `min_ecog` column, Trial A should carry `1`, and the other
# MAGIC trials should read `NULL` (they don't constrain ECOG). Three trials, ready for the pre-screen to join.

# COMMAND ----------

# DBTITLE 1,Verify (PRE-BUILT)
cols = spark.table(fqn("silver_trial_criteria")).columns
assert "min_ecog" in cols, "min_ecog not present yet — complete the TODO in cell 7."
display(spark.sql(f"""
  SELECT trial_id, trial_name, req_her2, req_er, req_pr, req_menopausal,
         req_no_prior_anti_her2, age_min, age_max, min_ecog
  FROM {fqn('silver_trial_criteria')} ORDER BY trial_id
"""))
print("✅ Catalog evolved. The Applied AI pre-screen and the coordinator app now screen against 3 trials.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚩 Checkpoint 5 — Trials catalog is live and evolvable
# MAGIC
# MAGIC - Wave 1 landed 3 trials; bronze is a single stable `VARIANT` column.
# MAGIC - Wave 2 added `min_ecog`; bronze schema **did not change**; the flatten surfaced the new column.
# MAGIC - The decision gate classified it **additive** and your TODO evolved the silver table safely.
# MAGIC - `silver_trial_criteria` (Trials A / B / C) is the contract the Applied AI section joins against.
# MAGIC
# MAGIC **Stretch:** wire this as a true **Auto Loader** stream (`cloudFiles`) so new files ingest
# MAGIC incrementally; use `ai_query` to parse the free-text `eligibility_text` into structured criteria
# MAGIC (extraction on the *trial* side, mirroring the patient-side note extraction). See `STRETCH.md`.
