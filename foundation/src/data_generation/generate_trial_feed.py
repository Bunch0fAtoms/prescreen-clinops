#!/usr/bin/env python3
"""
Fred Hutch Clinical Trial Pre-Screening — LIVE trials landing feed simulator.

This is the `land_trial_feed` task of the shared foundation job. It does NOT drop a
couple of static files and exit. It runs as a long-lived, presenter-controlled STREAM:
it drops newline-delimited JSON files into a Unity Catalog Volume over time so the Data
Engineering group can build a genuinely incremental ingest (Auto Loader) and watch it
react to new files, schema drift, and bad records as they arrive.

How the Data Engineering group consumes it
-------------------------------------------
One shared producer, many independent consumers. This task lands files into ONE Volume
in the shared foundation schema. Each DE team points their own Auto Loader (`cloudFiles`)
at that Volume, keeps its OWN checkpoint, and writes bronze/silver into its OWN schema.
Nobody blocks anybody.

The feed is staged so failures teach instead of block (--stage)
---------------------------------------------------------------
The story lands in two presenter-controlled stages so a team always builds against a
clean, working feed first, then hardens once the presenter releases the bad data:

1. STAGE 1 "clean" (~35 min at speed=1.0): every VALID record — clean trials, net-new
   trials ("add a trial = drop a file"), a benign additive schema-evolution (a new
   `min_ecog` criterion), and a latest-wins conflict. This is the Build 1 target: teams
   build Auto Loader → VARIANT bronze → flatten → silver and confirm it WORKS. Then a
   HEARTBEAT keeps re-landing clean latest-version records indefinitely.
2. STAGE 2 "dirty": the bad records (missing key, malformed JSON, wrong type). The
   presenter releases these ON CUE (Run now with --stage dirty) once teams have a working
   pipeline. Each team's incremental Auto Loader picks up only the new files on the next
   run; teams watch silver stay clean and the bad rows route to quarantine, and harden
   their pipeline where it doesn't.

--stage all (the default) lands clean then dirty in one run — the original behavior, for
an unattended demo or a solo dry run.

Recommended workshop flow: START with `--stage clean` (optionally `--speed 6` to compress
the clean act to ~5 min). When teams have Build 1 working, cancel that run and Run now
with `--stage dirty` to release the bad records; teams re-run their pipeline and adjust.

Presenter control (this is why the feed is its own job task)
------------------------------------------------------------
- START:   Run the foundation job (or Repair-run just this task). The feed begins dropping.
- PAUSE:   Cancel the run. `generate_omop_data` has long since finished, so cancelling
           stops only this feed — nothing is lost.
- RESTART: Run now again (the OMOP generator is deterministic, seed=42, so it harmlessly
           rewrites identical tables), or Repair-run and select ONLY `land_trial_feed`.

Tuning (Jobs UI -> Run now with different parameters, or bundle vars)
---------------------------------------------------------------------
    generate_trial_feed.py <catalog> <schema> [--speed 1.0] [--heartbeat-seconds 300]
                                              [--max-runtime-min 0] [--reset]
  --speed             divides every delay. speed=2 runs the opening act in ~25 min;
                      speed=6 compresses it to ~8 min for a dry run.
  --heartbeat-seconds seconds between heartbeat drops once the opening act finishes.
  --max-runtime-min   0 = run until cancelled (default). >0 = self-stop after N minutes.
  --reset             clear the landing Volume before starting (fresh demo).

Everything written here is synthetic and Unity Catalog scoped. No PHI.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# ── Spark session (serverless job / notebook runtime, or Databricks Connect local) ─
from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()
if spark is None:
    try:
        spark = SparkSession.builder.getOrCreate()
    except Exception:
        from databricks.connect import DatabricksSession

        spark = DatabricksSession.builder.serverless(True).getOrCreate()


# ── Args ────────────────────────────────────────────────────────────────────────
def parse_args(argv):
    p = argparse.ArgumentParser(description="Live clinical-trials feed simulator")
    p.add_argument("catalog", nargs="?", default="your_catalog_here")
    p.add_argument("schema", nargs="?", default="clinops_foundation")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Divides every delay. >1 = faster. Default 1.0 (~35-min clean stage).")
    p.add_argument("--stage", choices=["clean", "dirty", "all"], default="all",
                   help="Which records to land. clean = only valid records (Build 1 target), "
                        "then heartbeat. dirty = only the bad records (presenter releases these "
                        "on cue, after teams have a working pipeline). all = clean then dirty "
                        "(default; the original single-run behavior).")
    p.add_argument("--heartbeat-seconds", type=int, default=300,
                   help="Seconds between heartbeat drops after the opening act. Default 300.")
    p.add_argument("--max-runtime-min", type=int, default=0,
                   help="0 = run until cancelled (default). >0 = self-stop after N minutes.")
    p.add_argument("--reset", action="store_true",
                   help="Clear the landing Volume before starting.")
    return p.parse_args(argv)


args = parse_args(sys.argv[1:])
CATALOG = args.catalog
SCHEMA = args.schema

# ── Guard: refuse to run with an unfilled template placeholder ───────────────────
# Ships as "<your_catalog>"; if left unreplaced the Volume path is invalid and the
# failure is cryptic. Catch it up front with a clear, actionable message.
for _name, _val in (("client_catalog", CATALOG), ("client_schema", SCHEMA)):
    if "<" in _val or ">" in _val:
        raise SystemExit(
            f"\n❌  {_name} is still the template placeholder: {_val!r}\n"
            "    Open foundation/databricks.yml (target: client), set your real value,\n"
            "    SAVE the file, then Deploy the bundle again before running this job.\n"
            "    client_catalog = your Unity Catalog catalog (e.g. main).\n"
            "    Nothing was created.\n"
        )
SPEED = max(args.speed, 0.01)
STAGE = args.stage
HEARTBEAT = max(args.heartbeat_seconds, 5)
MAX_RUNTIME_S = args.max_runtime_min * 60 if args.max_runtime_min > 0 else None

VOLUME = "trial_landing"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/trial_catalog"

spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
os.makedirs(VOLUME_PATH, exist_ok=True)


def log(msg):
    print(msg, flush=True)


if args.reset:
    for f in os.listdir(VOLUME_PATH):
        try:
            os.remove(os.path.join(VOLUME_PATH, f))
        except OSError:
            pass
    log(f"🧹 Reset: cleared {VOLUME_PATH}")

log(f"📡 Live trials feed → {VOLUME_PATH}")
log(f"   speed={SPEED}x · heartbeat={HEARTBEAT}s · max_runtime={'∞' if MAX_RUNTIME_S is None else args.max_runtime_min}m")


# ── Trial definitions ─────────────────────────────────────────────────────────────
# Trials A and B carry the criteria the validated pre-screen already uses, so the
# downstream numbers hold. C/D/E/F are net-new — "adding a trial is dropping a file."
def trial(trial_id, title, phase, eligibility, text, feed_version=1):
    return {
        "trial_id": trial_id,
        "title": title,
        "status": "Recruiting",
        "phase": phase,
        "eligibility": eligibility,
        "eligibility_text": text,
        "feed_version": feed_version,
        # load_ts is stamped at drop time so the dedup can keep the newest record per
        # trial by an actual timestamp, not by fragile filename sorting.
        "load_ts": None,
    }


TRIAL_A = trial(
    "A", "HER2-Positive Advanced Breast Cancer Study", "Phase 2",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
     "her2_status": "Positive", "no_prior_anti_her2": True},
    "Inclusion: histologically confirmed HER2-positive breast cancer; age 18-75; "
    "no prior anti-HER2 therapy. Exclusion: significant cardiac disease.")

TRIAL_A_V2 = trial(
    "A", "HER2-Positive Advanced Breast Cancer Study", "Phase 2",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
     "her2_status": "Positive", "no_prior_anti_her2": True, "min_ecog": 1},
    "Inclusion: histologically confirmed HER2-positive breast cancer; age 18-75; "
    "no prior anti-HER2 therapy; ECOG performance status 0-1. "
    "Exclusion: significant cardiac disease.", feed_version=2)

TRIAL_B = trial(
    "B", "ER-Positive / HER2-Negative Postmenopausal Study", "Phase 3",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
     "er_status": "Positive", "her2_status": "Negative", "menopausal_status": "Postmenopausal"},
    "Inclusion: ER-positive, HER2-negative breast cancer; postmenopausal; age 18-75. "
    "Exclusion: prior endocrine therapy within 6 months.")

# Conflicting re-land: same trial_id B, tightened age ceiling + a new min_ecog. Tests
# that latest-wins holds (newest load_ts supersedes) even when criteria disagree.
TRIAL_B_V2 = trial(
    "B", "ER-Positive / HER2-Negative Postmenopausal Study", "Phase 3",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 70,
     "er_status": "Positive", "her2_status": "Negative", "menopausal_status": "Postmenopausal",
     "min_ecog": 2},
    "Inclusion: ER-positive, HER2-negative breast cancer; postmenopausal; age 18-70; "
    "ECOG 0-2. Exclusion: prior endocrine therapy within 6 months.", feed_version=2)

TRIAL_C = trial(
    "C", "Triple-Negative Breast Cancer Screening Study", "Phase 2",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
     "er_status": "Negative", "pr_status": "Negative", "her2_status": "Negative"},
    "Inclusion: triple-negative (ER-, PR-, HER2-) breast cancer; age 18-75. "
    "Exclusion: prior chemotherapy for metastatic disease.")

TRIAL_D = trial(
    "D", "Node-Positive HER2-Positive Adjuvant Study", "Phase 3",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
     "her2_status": "Positive", "no_prior_anti_her2": True, "min_ecog": 1},
    "Inclusion: node-positive HER2-positive early breast cancer; age 18-75; "
    "no prior anti-HER2 therapy; ECOG 0-1.")

TRIAL_E = trial(
    "E", "BRCA-Associated Triple-Negative Study", "Phase 2",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 70,
     "er_status": "Negative", "pr_status": "Negative", "her2_status": "Negative"},
    "Inclusion: triple-negative breast cancer with a germline BRCA1/2 mutation; age 18-70.")

TRIAL_F = trial(
    "F", "Postmenopausal ER-Positive Extended Endocrine Study", "Phase 3",
    {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
     "er_status": "Positive", "her2_status": "Negative", "menopausal_status": "Postmenopausal"},
    "Inclusion: ER-positive, HER2-negative breast cancer; postmenopausal; age 18-75; "
    "candidate for extended adjuvant endocrine therapy.")

CLEAN_ROTATION = [TRIAL_A_V2, TRIAL_B_V2, TRIAL_C, TRIAL_D, TRIAL_E, TRIAL_F]


# ── File landing (atomic: write temp, then rename into the glob) ──────────────────
# Continue numbering after any files already in the Volume, so a later `--stage dirty`
# run keeps landing trials_NNN in sequence after the clean files (no name collisions,
# no confusing restart to 001). --reset clears the Volume first, so this is 0 then.
_seq = len([f for f in os.listdir(VOLUME_PATH)
            if f.startswith("trials_") and f.endswith(".json")])


def _stamp(records):
    """Stamp a fresh, monotonically-increasing load_ts on each record at drop time."""
    ts = datetime.now(timezone.utc).isoformat()
    out = []
    for r in records:
        r = dict(r)
        r["load_ts"] = ts
        out.append(r)
    return out


def land(records, label, raw_lines=None):
    """Land one file. `records` are dicts serialized to NDJSON. `raw_lines` (optional)
    are appended verbatim — used to inject a malformed (unparseable) line."""
    global _seq
    _seq += 1
    fname = f"trials_{_seq:03d}_{label}.json"
    tmp = os.path.join(VOLUME_PATH, f".{fname}.tmp")
    final = os.path.join(VOLUME_PATH, fname)
    lines = [json.dumps(r) for r in _stamp(records)]
    if raw_lines:
        lines.extend(raw_lines)
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.rename(tmp, final)  # atomic within the Volume; Auto Loader picks up the finished file
    log(f"  ↳ dropped {fname} ({len(lines)} line(s))")


def sleep_scaled(seconds):
    if seconds <= 0:
        return
    time.sleep(seconds / SPEED)


START = time.time()


def out_of_time():
    return MAX_RUNTIME_S is not None and (time.time() - START) >= MAX_RUNTIME_S


# ── Stage 1 (clean) — every VALID record: clean, net-new, additive schema evolution,
#    and a latest-wins conflict. This is the Build 1 target: a team builds its Auto
#    Loader → VARIANT bronze → flatten → silver here and validates it WORKS end to end.
#    No bad records land in this stage, so failures never block the initial build.
#    (delay_seconds BEFORE each drop, at speed=1.0)
CLEAN_SCRIPT = [
    (0,   "Trial A (clean) — build Auto Loader → VARIANT bronze → flatten",
     lambda: land([TRIAL_A], "A_clean")),
    (240, "Trial B (clean) — incremental pickup",
     lambda: land([TRIAL_B], "B_clean")),
    (240, "Trial C (clean) — validated baseline (A/B/C)",
     lambda: land([TRIAL_C], "C_clean")),
    (360, "Trial D (clean, net-new) — 'add a trial = drop a file'",
     lambda: land([TRIAL_D], "D_netnew")),
    (360, "Trial E (clean, net-new) — incremental keeps working",
     lambda: land([TRIAL_E], "E_netnew")),
    (360, "Trial A re-lands + min_ecog — additive schema evolution; dedup latest-wins",
     lambda: land([TRIAL_A_V2], "A_min_ecog")),
    (300, "Trial F (clean, net-new) — the catalog keeps growing",
     lambda: land([TRIAL_F], "F_netnew")),
    (240, "Trial B re-lands, conflicting criteria — latest-wins (newest load_ts) holds",
     lambda: land([TRIAL_B_V2], "B_conflict")),
]

# ── Stage 2 (dirty) — the BAD records. The presenter releases these ON CUE, only after
#    teams have a working pipeline, so they teach ("it worked… now dirty data arrived,
#    harden it") instead of blocking. Each team's incremental Auto Loader picks up only
#    these new files on the next run; a correct pipeline routes them to quarantine and
#    keeps silver clean.
DIRTY_SCRIPT = [
    (0,   "BAD: record missing trial_id — route to quarantine, don't crash",
     lambda: land([{"title": "Unknown Registry Export", "status": "Recruiting",
                    "eligibility": {"sex": "Female", "min_age_years": 18, "max_age_years": 75,
                                    "her2_status": "Positive"},
                    "eligibility_text": "Row with no trial_id — cannot be keyed.",
                    "feed_version": 1, "load_ts": None}], "bad_missing_id")),
    (240, "BAD: malformed JSON line — try_parse_json returns NULL → quarantine",
     lambda: land([], "bad_malformed",
                  raw_lines=['{"trial_id": "MALF1", "title": "Truncated record", "eligibility": {'])),
    (300, "BAD: wrong type (min_age_years:\"eighteen\") — validation gate quarantines it",
     lambda: land([{"trial_id": "G", "title": "Wrong-Typed Age Study", "status": "Recruiting",
                    "phase": "Phase 1",
                    "eligibility": {"sex": "Female", "min_age_years": "eighteen", "max_age_years": 75,
                                    "her2_status": "Positive"},
                    "eligibility_text": "min_age_years arrived as a string — uncastable to int.",
                    "feed_version": 1, "load_ts": None}], "bad_wrongtype")),
]


def run_script(script, header):
    log(header)
    for i, (delay, note, drop) in enumerate(script, start=1):
        if out_of_time():
            log("⏹ max-runtime reached; stopping.")
            sys.exit(0)
        sleep_scaled(delay)
        log(f"[{i:02d}/{len(script)}] {note}")
        drop()


# ── Run the requested stage(s) ────────────────────────────────────────────────────
if STAGE in ("clean", "all"):
    run_script(CLEAN_SCRIPT,
               "── Stage 1 (clean): valid records only — build & validate your pipeline here ──")
    log("✅ Clean stage complete: clean trials + net-new + additive schema evolution + latest-wins.")

if STAGE in ("dirty", "all"):
    if STAGE == "dirty":
        log("▶ Stage 2 released by presenter: landing the bad records now.")
    run_script(DIRTY_SCRIPT,
               "── Stage 2 (dirty): bad records — the quarantine reveal ──")
    log("✅ Dirty stage complete: missing-id, malformed, and wrong-type records landed.")

# ── Heartbeat — keep the stream alive with clean latest-version re-lands ────────────
log(f"── Heartbeat every {HEARTBEAT}s (clean re-lands). Cancel the run to stop. ──")
version = 3
beat = 0
while True:
    if out_of_time():
        log("⏹ max-runtime reached; stopping the heartbeat.")
        break
    sleep_scaled(HEARTBEAT)
    base = CLEAN_ROTATION[beat % len(CLEAN_ROTATION)]
    rec = dict(base)
    rec["feed_version"] = version
    rec["load_ts"] = None  # re-stamped in land()
    land([rec], f"heartbeat_{base['trial_id']}_v{version}")
    log(f"   ♥ heartbeat {beat + 1}: re-landed Trial {base['trial_id']} as feed_version {version}")
    beat += 1
    if beat % len(CLEAN_ROTATION) == 0:
        version += 1

log("Feed stopped.")
