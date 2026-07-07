# 🧭 RUNBOOK: Data Engineering Session (build-level facilitation)

**Mentor-facing. Build-level only.** Event-level facilitation (agenda, room dynamics, the security-first
framing, the parallel-track structure, debrief) lives in the onsite agenda docs. Don't duplicate it here.
This runbook is the per-block detail: what the team builds, how the feed is staged, the named
**Checkpoints**, common failures, and the backup path.

**Customer:** Fred Hutch · Data Engineering track of the 2-day onsite (one of four parallel sections).
**Team:** comfortable with SQL and notebooks; this track is **ingestion plumbing**, practical DE patterns,
not GenAI.
**Outcome:** one governed pipeline that turns a **live, messy clinical-trials feed** into a clean,
deduplicated `silver_trial_criteria` table the Applied AI group joins against, with bad records
quarantined instead of crashing the load. **Security-first:** synthetic data only, everything
UC-scoped, the source and the landing Volume are read-only, config over code.

## One build, two tracks

The team builds the pipeline **live with Genie Code**, choosing the framework they want to learn.
`GENIE_CODE_PROMPTS.md` has the full starter prompts for both:

- **Track 1, Spark Structured Streaming.** Auto Loader `readStream` into a VARIANT bronze, a
  `foreachBatch` MERGE to silver, then scheduled as a Job. Built as a notebook.
- **Track 2, Lakeflow Declarative Pipeline (LDP).** The same tables declaratively: streaming tables,
  `@dlt.expect_all_or_drop` expectations, and AUTO CDC (`apply_changes`). Built as pipeline source.

Both land the identical `bronze_trial_catalog` → `silver_trial_criteria` + `quarantine_trial_criteria`.
A team runs one track. There is **no bundle to deploy** for this kit; the shared foundation already
stood up the source tables and the live feed, and the first Genie Code prompt creates the team's
writable schema.

## The four Fred Hutch DE asks live inside this one pipeline

There is nothing special about applying these patterns to the OMOP tables, so the team learns all four
in one realistic build instead of four separate exercises:

- **Schema evolution (Chetan #15)** is free: the VARIANT bronze absorbs a new criterion (a trial that
  starts sending `min_ecog`) with no schema change and no failed job.
- **SLA window (Jennifer #9)** is Prompt 3: schedule the ingest as a Job with an SLA-aware cron (Track
  1) or set the pipeline schedule (Track 2), with `pause_status: PAUSED` so it never fires unattended.
- **Reconciliation (Chetan #17)** and the **config-driven gate (Jenn #16)** are the two short hardening
  steps in the "Harden further" section of `GENIE_CODE_PROMPTS.md`.

**Cross-group.** This DE track and the Applied AI (ML) track both build in parallel off the shared
foundation (see `../../SHARED_FOUNDATION.md`). This track's cross-group contribution is
`silver_trial_criteria`, the **eligibility contract the ML pre-screen joins against**. If ML is ahead,
they can flatten the same Volume themselves, so it is a hand-off, never a blocker.

**Reveal ladder:** nudge → hint → **point at the matching prompt in `GENIE_CODE_PROMPTS.md`** → pair →
reveal (`notebooks/` worked reference, then `reference/ANSWER_KEY.md`). The value is in the *why*
(read-every-line into VARIANT, extract null-safe, dedup latest-wins, quarantine-don't-crash, schedule
incrementally), not in guessing syntax. Reveal the mechanism early if a team is spinning.

---

## 🗺️ Build surface map: Genie Code builds it, the UI schedules and stages it

**The rule:** the pipeline is built **live in Genie Code**, on whichever of the two tracks the team
picks. Genie Code authors the artifact itself, a notebook for Track 1 or pipeline source for Track 2.
The **UI** does the two things Genie Code does not: the presenter stages the live feed from the Jobs
UI, and the team schedules the finished pipeline from the Jobs or Pipelines UI. There is **no bundle
to deploy for this kit**. The `notebooks/` are worked reference for a stalled team, not the path.
Note the contrast with the ML kit: Genie Code *authors* the Track 1 notebook here, you do not open a
pre-built notebook and run it.

| Block | The work | Build surface | Fallback / notes |
|---|---|---|---|
| Block 0 | Confirm the source and feed Volume, create a writable team schema | **Genie Code** (SQL check, `CREATE SCHEMA`) | n/a |
| Block 1 (Track 1) | Auto Loader `readStream` → VARIANT bronze → `foreachBatch` MERGE to silver and quarantine | **Genie Code authors a notebook** | `notebooks/` backup |
| Block 1 (Track 2) | The same tables as a Lakeflow Declarative Pipeline: streaming tables, `expect_all_or_drop`, `apply_changes` CDC | **Genie Code authors pipeline source**, run as a pipeline | `notebooks/` backup |
| Feed staging (presenter) | Release `--stage clean`, then `--stage dirty` on cue | **Jobs UI** ("Run now with different parameters" on the foundation `land_trial_feed` task) | Not a redeploy, run-time parameters only |
| Block 2 | Re-run incrementally on the dirty stage, route bad rows to quarantine | **Genie Code** (re-run the notebook or pipeline) | n/a |
| Block 3 · SLA schedule | Schedule the ingest in the 08:00 to 22:00 window, `pause_status: PAUSED` | **Jobs UI** (Track 1 Job) or the **pipeline schedule** (Track 2) | n/a |
| Block 3 · reconciliation | Per-file recon into a timestamped `recon_summary` | **Genie Code** (SQL step) | n/a |
| Block 3 · config-driven gate | Drive allowed trials or fields from a UC config table | **Genie Code** (SQL and a UC config table) | n/a |

**No notebook to open and run, and no bundle to deploy.** Genie Code builds the pipeline; the Jobs or
Pipelines UI stages the feed and schedules the result.

---

## 🎢 The staged feed: clean first, then dirty (presenter-controlled)

The foundation feed (`land_trial_feed`) is **staged** so teams build against a working stream first,
then harden once the bad data arrives. This is how the presenter progresses the feed:

> **First, the key distinction: you deploy ONCE, then RUN as many times as you like.**
> `databricks bundle deploy` uploads the code and creates the foundation job. You do this a single
> time when you stand up the foundation. `--stage clean` and `--stage dirty` are NOT redeploys. They
> are two separate *runs* of that same already-deployed job, and the only difference between them is
> the parameter you pass at run time. Nothing is rebuilt or re-uploaded between stages.
>
> **How to pass a stage:** the `land_trial_feed` task ships with just `<catalog> <schema>` as its
> parameters (so a plain run uses `--stage all`, the default). To stage by hand, use the Jobs UI
> **"Run now with different parameters"** button (the dropdown next to Run now) and set the
> `land_trial_feed` parameters for that one run. This overrides the parameters for that run only; it
> does not change the deployed job.
>
> 1. **Release the clean stage (Build 1).** In the deployed **foundation** job, use **Run now with
>    different parameters** (or Repair-run) on the `land_trial_feed` task with parameters
>    **`<catalog> <schema> --reset --stage clean --speed 6`** (`--speed 6` compresses a dry run to about
>    5 minutes; `--reset` clears any leftover files from a prior run so the stream starts fresh). This
>    lands only valid records: clean trials, net-new trials, an additive `min_ecog` change, and a
>    latest-wins conflict, then heartbeats. Teams build and confirm their whole pipeline against this.
> 2. **Release the dirty stage on cue (Build 2).** Once teams have Build 1 working, cancel the clean run,
>    then use **Run now with different parameters** again with **`<catalog> <schema> --stage dirty`**
>    (no `--reset`, so it continues numbering after the clean files). This lands the three bad records
>    (missing key, malformed line, wrong-typed field) so teams re-run incrementally and harden.
>    (`--stage all`, the default of a plain Run now, lands clean then dirty in one run if you are not
>    staging by hand.)
>
> To pause, cancel the run; to resume, Run now again (OMOP regen is harmless) or Repair-run just
> `land_trial_feed`. Again, cancelling and re-running never needs a redeploy. The same `--stage` /
> `--speed` / `--reset` knobs are documented on the `land_trial_feed` task description in
> `foundation/resources/foundation_job.yml`.

---

## Block 0 · Foundation up (pre-build)

- **Pre-built by the foundation:** the 6 read-only OMOP source tables and the live trials-feed Volume.
- **Team does:** confirm the source is reachable, open a fresh Genie Code chat, and tell it their
  read-only source schema plus a writable team schema (default `clinops_de`).
- **🚩 Checkpoint 0, Foundation up.** The six OMOP tables are present with expected counts (person=300,
  condition_occurrence=300, measurement=720, observation=720, drug_exposure=383, note=265) and the feed
  Volume `/Volumes/<catalog>/clinops_foundation/trial_landing/trial_catalog/` exists.
- **Common failures:**
  - *`CREATE SCHEMA` permission denied* → the team lacks rights on their catalog; **plumbing, escalate**.
  - *Source table or Volume not found* → wrong source schema, or the foundation job has not been run yet.
  - *`hive_metastore` muscle memory* → redirect to the UC catalog/schema.

## Block 1 · Build the pipeline against the clean stage · 🛠️ the main build

- **Team builds (Genie Code, one track):** the incremental **Auto Loader** ingest (`cloudFiles` text →
  `try_parse_json` → a schema-stable **VARIANT** bronze, checkpointed in the team's OWN schema), the
  flatten of GOOD records to `silver_trial_criteria` (latest-wins per `trial_id` by `load_ts`, every
  field read null-safe with `try_variant_get`), and the **quarantine** of bad records with a reason.
- **🚩 Checkpoint 1, Clean pipeline works end to end.** Bronze grows as files land; `silver_trial_criteria`
  holds one clean row per trial, deduped latest-wins, `min_ecog` present for Trial A and NULL where a
  trial doesn't set it, no rows lost; quarantine is empty on the clean stage.
- **Common failures (all pre-loaded into the adaptation skill so Genie Code should avoid them):**
  - *A strict `::` cast throws `INVALID_VARIANT_CAST` on a field a clean trial legitimately omits.* Use
    `try_variant_get(col, '$.path', 'TYPE')` everywhere, including nested `eligibility.*`.
  - *Duplicate rows per `trial_id` after the first run (Track 1).* A `foreachBatch` MERGE only dedups
    across batches; dedup the source to one row per key (`row_number` newest by `load_ts`) before the
    MERGE. Track 2 gets this free via `apply_changes` `sequence_by`.
  - *Checkpoint pointed at the shared Volume.* It must live in the team's OWN schema (`_ingest_state`
    Volume); the landing Volume is read-only shared.
  - *(Track 2) `apply_changes(columns=...)` or expectations on `create_streaming_table`.* The parameter
    is `column_list`; CDC expectations go on the source view. Both are covered in `GENIE_CODE_PROMPTS.md`.

## Block 2 · Release the dirty stage and harden · 🛠️ where quarantine earns its keep

- **Presenter:** release `--stage dirty` (see the staged-feed section above).
- **Team does:** re-run the ingest (Track 1) or the pipeline (Track 2). Because the read is incremental,
  it picks up only the three new files. Watch what breaks, then route bad rows to quarantine so good
  rows keep flowing.
- **🚩 Checkpoint 2, Live feed survives bad data.** The three bad records land in
  `quarantine_trial_criteria`, one each `missing_trial_id` / `malformed_json` / `invalid_type` (Track 2
  drops them via the expectations); **silver is unchanged** (still one clean row per valid trial); the
  load never crashes. Counts grow because the feed is live, so the signal is clean separation, not a
  fixed total.
- **Common failures:**
  - *They use `parse_json`, and the malformed line fails the whole batch.* `try_parse_json` returns NULL
    on a bad line; route the NULLs to quarantine.
  - *The strict-cast trap hiding in the quality rule (only shows up on dirty data).* Testing
    `min_age_years::INT IS NULL` throws on the wrong-typed record (`"eighteen"`); test with
    `try_variant_get(...,'INT') IS NULL` instead. This is exactly why we build clean-first.

## Block 3 · Weave in the four asks · 🛠️ hardening, on the same pipeline

Two of the four are already done by Block 1 and 2 (schema evolution via VARIANT; the malformed-row
quarantine). The other two are short additions:

- **SLA-aware schedule (Jennifer #9).** Track 1: create a Job on the notebook with cron
  `0 0 8-22 * * ?` (America/Los_Angeles) so it never fires in the 23:00 to 08:00 blackout, and ship it
  `pause_status: PAUSED`. Track 2: set the pipeline schedule the same way. `trigger(availableNow=True)`
  plus the checkpoint means each run processes only new files and stops.
- **Reconciliation (Chetan #17).** Add a step that, per source file, confirms every record reached
  either silver or quarantine, and persist a timestamped `recon_summary`.
- **Config-driven gate (Jenn #16).** Drive which trials or fields are allowed from a UC config table, so
  a steward changes behavior with no code change and every decision is auditable.
- **🚩 Checkpoint 3, Governed and auditable.** The schedule respects the SLA window; `recon_summary` shows
  every file fully accounted for; the gate blocks a disallowed entry from a config change alone.

---

## Quick reference · checkpoint summary

| # | Checkpoint | Signal it's met |
|---|---|---|
| 0 | Foundation up | 6 source tables ✅ (300/300/720/720/383/265); feed Volume present |
| 1 | Clean pipeline works | bronze grows; `silver_trial_criteria` one deduped row per trial, `min_ecog` present (A=1, others NULL); quarantine empty |
| 2 | Survives bad data | 3 rows quarantined (`missing_trial_id` / `malformed_json` / `invalid_type`); silver unchanged; load never crashes |
| 3 | Governed and auditable | SLA-aware schedule + `pause_status`; `recon_summary` accounts for every file; config-driven gate blocks a disallowed entry |

**Backup path.** `notebooks/` holds worked reference versions of these patterns (including OMOP-table
variants of schema evolution, reconciliation, the ingest gate, and the SLA window) and `reference/`
holds the answer key. They are the facilitator's fallback if a team stalls, not the path the team
follows. The live Genie Code build is the session.

**Validation note.** Both tracks were run green on a reference FEVM workspace (source `clinops_foundation`,
writing `clinops_de`). Clean stage: bronze 9 / silver 6 / quarantine 0. Dirty stage (released via the
real `--stage dirty` gate): quarantine 3, one per reason, silver still 6, latest-wins holding.
