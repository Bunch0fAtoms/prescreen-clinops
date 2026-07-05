#!/usr/bin/env python3
"""
Fred Hutch Clinical Trial Pre-Screening — trials landing feed generator.

Lands a nested clinical-trials JSON feed into a Unity Catalog Volume, in two waves.
This is the raw feed the Data Engineering group ingests during their section:
files in a Volume, not a finished table. Their job is to read it, parse it into a
schema-stable VARIANT bronze, and flatten it to `silver_trial_criteria`.

The feed arrives in waves, and wave 2 adds a new field (`min_ecog`) to Trial A, so
the ingest has to handle schema evolution. A trial can appear in more than one wave,
so the flatten step must keep one row per trial from the newest file.

Run via:
    python generate_trial_feed.py [catalog] [schema]

When run via `databricks bundle run`, catalog/schema come from bundle variables.
Everything written here is synthetic and Unity Catalog scoped. No PHI.
"""

import sys
import json

# ── CLI args (passed by the bundle job) ─────────────────────────────────────────
CATALOG = sys.argv[1] if len(sys.argv) > 1 else "your_catalog_here"
SCHEMA  = sys.argv[2] if len(sys.argv) > 2 else "demo_clinical_trial_pre_screening_omop"

# ── Spark session (serverless job / notebook runtime, or Databricks Connect local) ─
from pyspark.sql import SparkSession
spark = SparkSession.getActiveSession()
if spark is None:
    try:
        spark = SparkSession.builder.getOrCreate()
    except Exception:
        from databricks.connect import DatabricksSession
        spark = DatabricksSession.builder.serverless(True).getOrCreate()

# ── Landing location ─────────────────────────────────────────────────────────────
VOLUME = "trial_landing"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/trial_catalog"
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
dbutils.fs.mkdirs(VOLUME_PATH)  # noqa: F821  (dbutils is injected by the runtime)

# ── Wave 1 — three trials ───────────────────────────────────────────────────────
# Trials A and B carry the same criteria the reference pre-screen already uses, so
# the validated numbers hold. Trial C (triple-negative) is net-new.
wave1 = [
    {"trial_id": "A", "title": "HER2-Positive Advanced Breast Cancer Study", "status": "Recruiting",
     "phase": "Phase 2",
     "eligibility": {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
                     "her2_status": "Positive", "no_prior_anti_her2": True},
     "eligibility_text": "Inclusion: histologically confirmed HER2-positive breast cancer; age 18-75; "
                         "no prior anti-HER2 therapy. Exclusion: significant cardiac disease."},
    {"trial_id": "B", "title": "ER-Positive / HER2-Negative Postmenopausal Study", "status": "Recruiting",
     "phase": "Phase 3",
     "eligibility": {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
                     "er_status": "Positive", "her2_status": "Negative", "menopausal_status": "Postmenopausal"},
     "eligibility_text": "Inclusion: ER-positive, HER2-negative breast cancer; postmenopausal; age 18-75. "
                         "Exclusion: prior endocrine therapy within 6 months."},
    {"trial_id": "C", "title": "Triple-Negative Breast Cancer Screening Study", "status": "Recruiting",
     "phase": "Phase 2",
     "eligibility": {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
                     "er_status": "Negative", "pr_status": "Negative", "her2_status": "Negative"},
     "eligibility_text": "Inclusion: triple-negative (ER-, PR-, HER2-) breast cancer; age 18-75. "
                         "Exclusion: prior chemotherapy for metastatic disease."},
]
with open(f"{VOLUME_PATH}/trials_2026Q1.json", "w") as f:
    for rec in wave1:
        f.write(json.dumps(rec) + "\n")

# ── Wave 2 — the registry adds min_ecog to Trial A next quarter (schema evolution) ─
wave2 = [
    {"trial_id": "A", "title": "HER2-Positive Advanced Breast Cancer Study", "status": "Recruiting",
     "phase": "Phase 2",
     "eligibility": {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
                     "her2_status": "Positive", "no_prior_anti_her2": True, "min_ecog": 1},
     "eligibility_text": "Inclusion: histologically confirmed HER2-positive breast cancer; age 18-75; "
                         "no prior anti-HER2 therapy; ECOG performance status 0-1. "
                         "Exclusion: significant cardiac disease."},
]
with open(f"{VOLUME_PATH}/trials_2026Q2.json", "w") as f:
    for rec in wave2:
        f.write(json.dumps(rec) + "\n")

print(f"✅ Landed 2 trial-catalog waves in {VOLUME_PATH}")
print("   Wave 1: Trials A / B / C. Wave 2: Trial A re-lands with a new min_ecog field.")
print("   The Data Engineering group ingests these into a VARIANT bronze, then flattens to silver_trial_criteria.")
