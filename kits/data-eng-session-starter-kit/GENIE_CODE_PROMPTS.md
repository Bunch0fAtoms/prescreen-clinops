# 💬 Genie Code, starter prompts (Data Engineering / live trials-feed ingest)

**Fred Hutch onsite · Data Engineering session · Genie Code building a Volume-fed pipeline**

Your goal is one pipeline that turns a **live, messy clinical-trials feed** into a clean, queryable
`silver_trial_criteria` table the Applied AI group can join against, while routing bad records to a
quarantine table instead of crashing. You build it with Genie Code as a **notebook**, then schedule
that notebook as a **Job**. There is no bundle to deploy for this kit; the shared foundation already
gave you the source feed and a writable schema (see this kit's `README.md`).

> **Two tracks, one pipeline. Pick the framework your team wants to learn.** Both build the identical
> `bronze_trial_catalog` → `silver_trial_criteria` + `quarantine_trial_criteria`, off the same staged
> feed, with the same rules. Only the authoring style differs, and a team runs just one track.
> - **Track 1, Spark Structured Streaming** (Auto Loader `readStream` → `foreachBatch` MERGE), built as
>   a notebook you then schedule as a Job. This is the default path below (Prompts 0 to 3).
> - **Track 2, Lakeflow Declarative Pipeline (LDP)**, the same tables expressed declaratively with
>   streaming tables, `EXPECT` expectations, and AUTO CDC. Starter prompts are in the "Track 2, LDP"
>   section further down. Both tracks are validated; Prompt 0 (profile the source) applies to either.

> **How to drive Genie Code well:** send one prompt at a time; **read the diff it proposes and Accept
> deliberately** (don't blanket-accept); let it persist work as a **real notebook**, not scratch. Open
> the notebook so it is visible before asking for edits, so changes land on the open editor. This is a
> free-form build: these prompts are starters your team adapts, not a script.

> **🔒 Read-only source, everything else lands in your schema.** You read the shared `trial_landing`
> Volume; you never write to it. Everything you create goes in your writable schema (default
> `clinops_de`). Unity-Catalog-scoped, no `hive_metastore`, synthetic data only.

---

## 🎢 The build arc: clean first, then dirty (this is how the feed is staged)

The foundation feed (`land_trial_feed`) is **staged** so you build against a working stream first,
then harden once the bad data arrives. The presenter controls it:

- **Build 1, clean stage.** The presenter runs the feed with `--stage clean`. It lands only **valid**
  records (clean trials, net-new trials, one additive schema change, one latest-wins conflict). You
  build the whole pipeline here and confirm it **works end to end**.
- **Build 2, dirty stage.** When your Build 1 works, the presenter releases `--stage dirty`, landing
  three **bad** records (a missing key, a malformed line, a wrong-typed field). Because your ingest is
  **incremental**, re-running picks up only those new files. You watch what breaks and **harden** the
  pipeline so bad rows go to quarantine and good rows keep flowing.

Ask the presenter which stage is live before you start. If nothing has landed yet, ask them to start
the feed.

---

## 🔎 Prompt 0, Profile the source and plan (warm-up, no build yet)

> **"Profile the shared foundation for the Data Engineering session. My read-only source is catalog
> `<catalog>`, schema `<source_schema>`: the 6 OMOP tables plus a live clinical-trials feed landing
> JSON files in the Volume `/Volumes/<catalog>/<source_schema>/trial_landing/trial_catalog/`. Give me
> row counts and schemas for the tables, list the files in the Volume, and peek at one clean record
> and one bad record so I understand the JSON shape. Confirm I can create a writable schema
> `<client_schema>`. Then propose an incremental Auto Loader pipeline: raw JSON → VARIANT bronze →
> flatten good records to `silver_trial_criteria` → quarantine bad records with a reason. Don't build
> yet."**

*Good looks like:* Genie Code reports the tables, lists the Volume files, shows the nested JSON shape
(`trial_id`, `title`, `status`, `phase`, a nested `eligibility` object, `eligibility_text`,
`feed_version`, `load_ts`), confirms write access, and lays out a bronze → silver + quarantine plan.

---

## 🥉 Prompt 1, Build the bronze layer (incremental Auto Loader → VARIANT)

> **🖱️ UI first:** create (or open) a notebook named `trials_feed_ingest` in your workspace so Genie
> Code edits land in a real, visible notebook.

> **"Build this as ONE notebook I'll later schedule as a Databricks Job (not a declarative pipeline).
> Step 1, the bronze layer only, show me the cells before running anything. Create my writable schema
> if needed, then an incremental Auto Loader read (`cloudFiles`, format `text`, trigger
> `availableNow`) of the `trial_catalog` Volume feed. `try_parse_json` each line into ONE `VARIANT`
> column `trial_raw`, appended to `bronze_trial_catalog`, keeping the raw text and the source file
> path. Put the schemaLocation and checkpoint in a Unity Catalog Volume under my writable schema,
> never in the source Volume."**

*Good looks like:* a `bronze_trial_catalog` with a single `VARIANT` column plus `_raw_value`,
`_source_file`, `_ingestion_ts`; `try_parse_json` returns NULL (not an error) on a malformed line, so
**every** file lands regardless of validity; re-running ingests only new files (checkpoint), so bronze
grows as the feed drops files.

> **⚠️ Redirect, checkpoints belong in Unity Catalog, not DBFS.** If Genie Code reaches for a
> `dbfs:/…` checkpoint path, redirect it to a **UC Volume** under your writable schema (e.g.
> `CREATE VOLUME … clinops_de._ops`, checkpoint at `/Volumes/…/clinops_de/_ops/checkpoints/…`). For a
> governance-first customer, all state stays UC-governed.

---

## 🥈 Prompt 2, Silver + quarantine (latest-wins, and route the bad rows)

> **"Now add the silver and quarantine steps, reading from `bronze_trial_catalog`. GOOD records go to
> `silver_trial_criteria` with typed columns pulled from the `trial_raw` VARIANT: `trial_id`, `title`,
> `status`, `phase`, `sex` (from `eligibility.sex`), `min_age_years`, `max_age_years`, `her2_status`,
> `er_status`, `menopausal_status`, `no_prior_anti_her2`, `min_ecog`, `eligibility_text`,
> `feed_version`, `load_ts`, plus `_source_file`. Keep exactly ONE row per `trial_id`, newest by
> `load_ts` (latest-wins), use `MERGE INTO` so re-runs upsert. BAD records go to
> `quarantine_trial_criteria` with a `quarantine_reason`: `malformed_json` when `trial_raw` is NULL,
> else `missing_trial_id` when the id is null, else `invalid_type` when `min_age_years` can't be an
> int; keep the raw text and source file for replay. Show me the cells, don't run yet."**

*Good looks like:* `silver_trial_criteria` has one row per trial, and when a trial re-lands with a
newer `load_ts` (a heartbeat or a conflicting update) the **newest** version wins;
`quarantine_trial_criteria` collects bad rows each tagged with a reason; the load never crashes.
Because bronze is `VARIANT`, a new criterion (a trial that adds `min_ecog`) flows through with **no
schema change**.

### The three things that will bite you, and the fixes (all validated)

These are the real failure modes this build hits. Let them happen, then guide the fix, that is the
lesson.

1. **`INVALID_VARIANT_CAST` on absent fields (shows up on clean data).** A strict cast like
   `trial_raw:eligibility:er_status::STRING` **throws** when a trial legitimately omits that field.
   *Fix:* use the null-safe extractor everywhere:
   `try_variant_get(trial_raw, '$.eligibility.er_status', 'STRING')` returns NULL instead of raising.
   Do this for **every** field, including the nested `eligibility.*` ones.

2. **Duplicate rows per `trial_id` after the first run.** A `foreachBatch` MERGE only dedups *across*
   batches; within one batch the target starts empty, so every version of a trial gets inserted (a
   trial that re-landed shows up 2 to 3 times). *Fix:* **deduplicate the source to one row per `trial_id`
   before the MERGE**, `row_number() over (partition by trial_id order by load_ts desc)`, keep row 1.
   This also prevents the later "multiple source rows matched the same target row" error.

3. **The same strict-cast trap hiding in your quality check (only shows up on dirty data).** If your
   bad-row rule tests `min_age_years::INT IS NULL`, that strict cast **throws** on the wrong-typed
   record (`"eighteen"`) instead of flagging it. *Fix:* test with the null-safe extractor too:
   `try_variant_get(trial_raw, '$.eligibility.min_age_years', 'INT') IS NULL`. This one stays hidden
   until the presenter releases the dirty stage, which is exactly why we build clean-first.

---

## ⏰ Prompt 3, Schedule the notebook as a Job (the SLA-window guard)

> **🖱️ This step is UI-driven** (the workshop schedules through the Jobs UI):
> 1. **Workflows → Create Job.**
> 2. Add a **task** → type **Notebook** → point it at your `trials_feed_ingest` notebook → serverless.
> 3. Add a **Schedule** with a cron that respects Fred Hutch's overnight SLA window, e.g. run hourly
>    only between 08:00 and 22:00 so the job never hammers the source during the 23:00 to 08:00 blackout
>    (`0 0 8-22 * * ?`, timezone America/Los_Angeles).
> 4. **Run now** once to confirm it succeeds, then let the schedule drive it.

> **"Explain how `trigger(availableNow=True)` plus the checkpoint makes this notebook safe to run on a
> schedule, each run should process only files that landed since the last run, then stop."**

*Good looks like:* the Job runs the notebook to completion each time; because the streams use
`availableNow` + a checkpoint, a run processes only new files and then stops (no always-on cluster).
The cron keeps scheduled runs out of the SLA blackout; the incremental design means a manual catch-up
run is always safe.

---

## 🧪 Build 2, release the dirty stage and harden

> **🖱️ Ask the presenter to run the feed with `--stage dirty`.** Three bad files land: a record with no
> `trial_id`, a truncated/malformed line, and one with `min_age_years: "eighteen"`.

> **"Re-run my ingest. It should pick up only the three new files. Show me the bronze count, the silver
> rows, and the quarantine breakdown by reason."**

*Good looks like:* the incremental read grabs only the new files; **all three bad records land in
`quarantine_trial_criteria`**, one each tagged `missing_trial_id`, `malformed_json`, `invalid_type`;
**silver is unchanged** (still one clean row per valid trial); the run does not crash. If it does crash,
it's almost certainly gotcha #3 above, the strict cast in your quality rule.

---

## 🛤️ Track 2, LDP, build the same pipeline as a Lakeflow Declarative Pipeline

This is the declarative alternative to Prompts 0 to 3. Same three tables, same staged clean-then-dirty
arc, same rules. You express the pipeline as definitions (streaming tables, views, expectations, AUTO
CDC) and let Lakeflow run it, instead of writing `readStream` and `foreachBatch` by hand. Pick this
track if your team wants pipeline-as-definition with built-in data-quality metrics. Run Prompt 0
(profile the source) first either way.

> **🖱️ UI first:** create a notebook named `trials_feed_ldp` for the pipeline source. You attach it to
> a Lakeflow Declarative Pipeline in the UI after the code is written (LDP Prompt 3).

### 🥉 LDP Prompt 1, bronze streaming table (Auto Loader → VARIANT)

> **"Build a Lakeflow Declarative Pipeline in Python (`import dlt`). Step 1 is the bronze streaming
> table only. Create `bronze_trial_catalog` with `@dlt.table`, reading the `trial_catalog` Volume feed
> incrementally with Auto Loader (`spark.readStream.format('cloudFiles')`, option `cloudFiles.format`
> `text`). Keep the raw line, parse it with `try_parse_json` into ONE VARIANT column `trial_raw`, and
> capture `_metadata.file_path` as `_source_file`. A malformed line must still land (`try_parse_json`
> returns NULL), never fail the pipeline. Show me the code, don't run yet."**

*Good looks like:* a `bronze_trial_catalog` streaming table with the raw line, a `VARIANT` `trial_raw`,
and `_source_file`. Every file lands regardless of validity, so bad lines are caught downstream, not here.

### 🥈 LDP Prompt 2, flatten view, quality-gated source, silver CDC, quarantine

> **"Add the rest declaratively, reading from `bronze_trial_catalog`. First a `@dlt.view`
> `vw_trial_flattened` that pulls every typed field out of `trial_raw` with
> `try_variant_get(col,'$.path','TYPE')`: `trial_id`, `title`, `status`, `phase`, `sex` (from
> `eligibility.sex`), `min_age_years`, `max_age_years`, `her2_status`, `er_status`, `menopausal_status`,
> `no_prior_anti_her2`, `min_ecog`, `eligibility_text`, `feed_version`, `load_ts`, plus a helper
> `_min_age_years_raw` (the raw string) so I can tell 'field absent' from 'field present but wrong
> type'. Then a second view `vw_trial_good` decorated with `@dlt.expect_all_or_drop` (rules: `trial_raw
> IS NOT NULL`; `trial_id IS NOT NULL`; `_min_age_years_raw IS NULL OR min_age_years IS NOT NULL`)
> reading `vw_trial_flattened`. Create the silver with
> `dlt.create_streaming_table('silver_trial_criteria')` fed by
> `dlt.apply_changes(target='silver_trial_criteria', source='vw_trial_good', keys=['trial_id'],
> sequence_by=F.col('load_ts'), column_list=[the 15 typed columns])`, so it keeps one latest-wins row
> per trial. Finally a `@dlt.table` `quarantine_trial_criteria` reading `vw_trial_flattened` where the
> record is bad, tagged with a `quarantine_reason` (`malformed_json` / `missing_trial_id` /
> `invalid_type`)."**

*Good looks like:* `silver_trial_criteria` has one row per trial, newest by `load_ts` (AUTO CDC does the
dedup for you); the expectations drop bad rows from silver; `quarantine_trial_criteria` collects them
with a reason. Because bronze is `VARIANT`, a new criterion (a trial that adds `min_ecog`) flows through
with no schema change.

**Two LDP API details this build needs.** These are now pre-loaded in the workspace adaptation skill, so
Genie Code should get them right on the first pass. If it slips, this is the fix:

1. **The AUTO CDC parameter is `column_list`, not `columns`.** Use
   `dlt.apply_changes(..., column_list=[...])`.
2. **CDC quality expectations live on the SOURCE view, not on `create_streaming_table`.** Decorate
   `vw_trial_good` with `@dlt.expect_all_or_drop` and feed it to `apply_changes`. Expectations placed on
   `create_streaming_table` are validated against the post-`column_list` target columns, so they cannot
   see `trial_raw` or the `_min_age_years_raw` helper, and you get `UNRESOLVED_COLUMN`. Keeping
   `vw_trial_flattened` separate also lets the quarantine table still read the bad rows.

### ⏰ LDP Prompt 3, create and run the pipeline (UI)

> **🖱️ UI-driven** (the workshop creates pipelines through the Lakeflow UI):
> 1. **Pipelines → Create pipeline**, choose **serverless** and **Unity Catalog**.
> 2. Default catalog = your `<catalog>`, default schema = your writable `<client_schema>`.
> 3. Add source file = your `trials_feed_ldp` notebook. **Create**, then **Run**.
> 4. Watch the graph reach **COMPLETED**, then open `vw_trial_good` to see the **expectation metrics**
>    (how many rows were dropped) right on the node.

*Good looks like:* the pipeline graph shows `bronze_trial_catalog` → `vw_trial_flattened` →
`vw_trial_good` → `silver_trial_criteria`, with `quarantine_trial_criteria` alongside; expectation
metrics show on `vw_trial_good`; silver is deduped to one row per trial. On the clean stage, quarantine
is empty.

### 🧪 LDP Build 2, release the dirty stage and harden

> **🖱️ Ask the presenter to run the feed with `--stage dirty`** (same gate as Track 1). Then re-run the
> pipeline (or, if you set it continuous, let it pick the new files up).

*Good looks like:* the three bad records are **dropped from silver by the expectations** and land in
`quarantine_trial_criteria`, one each `missing_trial_id` / `malformed_json` / `invalid_type`; the
expectation panel on `vw_trial_good` shows the three drops; **silver is unchanged** (still one clean row
per valid trial); the pipeline stays green. This is the declarative mirror of Track 1's Build 2.

---

## 🤝 Prove the catalog is join-ready, the contract with Applied AI

> **"Show me `silver_trial_criteria` is join-ready: cross join a couple of patient biomarker profiles
> against it and, for each trial, evaluate every non-null criterion (NULL means the trial doesn't
> constrain that field) to a TRUE/FALSE eligible flag. Confirm one generic query screens a patient
> against every trial at once, no per-trial SQL."**

*Good looks like:* a single query screens a patient against every trial, proof that "trials are data,
not code." This is the table the Applied AI group's pre-screen builds on, so **adding a trial is a file
landing, not a code change**.

---

## 🧩 The four Fred Hutch DE asks all live in this one pipeline

The trials feed exercises every pattern the four submitted asks are about, so the team learns them in
one realistic build instead of four separate toy ones. Applying the same patterns to the OMOP tables
would teach nothing new. Two of the four are already in the base build above; two are short hardening
steps to add next.

**Already covered by the base build:**
- **Schema evolution (Chetan #15).** The VARIANT bronze means a trial that adds a new criterion (a
  `min_ecog` that wasn't there before) flows straight through with no schema change and no failed job.
  That is schema evolution handled at the source, stronger than a `mergeSchema` retrofit on a typed table.
- **SLA window (Jennifer #9).** Scheduling the ingest as a Job with an SLA-aware cron (Prompt 3 on
  Track 1, or the pipeline schedule on Track 2) keeps runs out of the overnight blackout, and
  `pause_status: PAUSED` stops it firing unattended.

**Add these next (short hardening steps on the same pipeline):**
- **Reconciliation (Chetan #17):** *"Add a step that reconciles the feed: for each source file, did
  every record land in either silver or quarantine? Persist a per-run `recon_summary` so nothing is
  silently dropped."*
- **Config-driven gate (Jenn #16):** *"Drive which trials or fields are allowed from a UC config table,
  so a steward changes behavior with no code change and every decision is auditable."*

**Make it your own (optional extras):**
- **Continuous mode:** *"Turn the `availableNow` batch into a continuous stream with
  `trigger(processingTime='30 seconds')` so the catalog stays current hands-free."* On Track 2, set the
  pipeline to continuous for the same effect.
- **`ai_query` on `eligibility_text`:** *"Parse each trial's free-text eligibility into structured
  criteria and reconcile against the typed columns."*

**Optional, a self-serve Genie space.** Install the workspace-level `prompt-to-genie` skill (see the
README) and say **"create a Genie space"** over your `recon_summary` / quarantine tables so a steward
can ask *"which records failed to load last night, and why?"* in plain English.

---

*If a team gets truly stuck, the facilitator has the worked notebook and the answer key in
`reference/`. These prompts teach the mechanism, the value is in the **why**: read-every-line into
VARIANT, extract null-safe, dedup latest-wins, quarantine-don't-crash, schedule incrementally.*
