# 💬 Genie Code — starter prompts (Data Engineering / governed OMOP ingest)

**Fred Hutch onsite · Data Engineering session · Genie Code over the OMOP source tables**

The build is **free-form**. The foundation is already up — the 6 OMOP source tables are present and
**read-only** in `source_schema`, `_config` gives you `fqn()` / `src()` helpers, and your writable
schema is `clinops_de`. From here **you design the ingestion hardening your team actually
needs.** These are **starter prompts** to get Genie Code moving — change them, combine them, reorder
them, or ignore them and ask your own. The four patterns below are independent; build them in any order.

> **How to drive Genie Code well:** paste one prompt at a time; **review the diff before you Accept**;
> let it **persist work as real notebooks/SQL files**, not scratch. This chat runs on a SQL warehouse
> (SQL inline); for Python cells create notebooks that run on serverless. Point it at the right notebook
> page when you want an edit to land there.

> **🔒 Read-only source, everything else lands in your schema.** Never modify the 6 tables in
> `source_schema`; everything you create goes in `clinops_de`. UC-scoped, no `hive_metastore`,
> synthetic data only, **config over code**.

---

### 1. Profile the source and plan the build (the warm-up)
> **"Profile the 6 read-only OMOP tables in my `source_schema` — row counts and schemas — and confirm my `client_schema` is writable. Then propose an ingest → verify → govern plan for a nightly clinical-data pipeline. Don't build yet."**

*Good looks like:* counts (person=300, condition_occurrence=300, measurement=720, observation=720,
drug_exposure=383, note=265), "your schema is writable," and a plan naming the four pains below.

---

### 2. Make the ingest survive a schema change  *(nb 01 · Chetan #15)*
> **"The source just added a `condition_source_name` column. Write the bronze append so the target table EVOLVES to absorb the new column instead of breaking — Delta `mergeSchema` on append. Show me the before/after schema and the row counts."**

*Good looks like:* the target gains `condition_source_name`; the verify cell reads **300 pre-evolution
(NULL) + 300 post-evolution (populated) = 600 rows**, no job broke, no data lost. If Genie Code reaches
for `overwriteSchema`, redirect — that *replaces* the schema; **`mergeSchema`** is the add-a-column-on-append path.

---

### 3. Prove you loaded every row  *(nb 02 · Chetan #17)*
> **"Build a reconciliation framework: compare source vs. target row counts per table, and for any mismatch run a LEFT ANTI JOIN to return the exact missing keys. Persist the results to a timestamped `recon_summary` audit table."**

*Good looks like:* `measurement` flagged **FAIL with delta = 7**; the anti-join returns exactly ids
**101, 202, 303, 404, 505, 606, 707**; every other table PASSes; `recon_summary` gets a row per table.
The #1 gotcha: qualify the **source schema** (`catalog.source_schema.measurement`) vs. your `USE`d
`bronze_measurement` — join bronze-to-bronze and you'll find nothing missing.

---

### 4. Block a restricted table from a config, not a hardcoded list  *(nb 03 · Jenn #16)*
> **"Write `assert_ingest_allowed(table)` that reads the `ingest_allowlist` UC config table and RAISES before any write if a table isn't allowed. Wrap it in a `safe_ingest()`. Prove it: `safe_ingest('person')` writes bronze; `safe_ingest('genomic_sequencing')` is blocked and creates NO table."**

*Good looks like:* `bronze_person` lands; `genomic_sequencing` raises `PermissionError` and no
`bronze_genomic_sequencing` table exists. If Genie Code hardcodes `if table in [...]`, that's **the
redirect** — the whole point is config-driven: a steward changes the UC allow-list with no deploy.

---

### 5. Don't hammer the source during the SLA window  *(nb 04 · Jennifer #9)*
> **"Write `in_sla_window(now)` — an overnight (midnight-wrapping) blackout check for 23:00–08:00 PT — and use it to skip an ingest that would run in-window. Add a truth-table self-test, and show me the Jobs schedule pattern that keeps scheduled runs out of the window too."**

*Good looks like:* the truth table is all ✅ (00/05/07 in-window, 08/12/22 out, 23 in) — the wrap-around
is right (`h >= 23 OR h < 8`, **not** `23 <= h < 8`, which is always False). The Jobs cron
(`0 0 8-22 * * ?`) never fires in-window; the runtime guard catches manual/backfill runs.

---

### 6. Ingest the LIVE trials feed — Auto Loader → VARIANT bronze → flat silver + quarantine  *(nb 05 · Chetan #15 · Jenn on bad data · the net-new feed)*

> **⚠️ First: the feed is live and presenter-controlled.** Your instructor starts the foundation
> `land_trial_feed` task; it drops one JSON file at a time into a **shared** `trial_landing` Volume
> (clean trials first, then a schema change, then bad records) and keeps running until cancelled. You
> read that shared Volume and write everything into **your** schema. If nothing has landed yet, ask the
> presenter to start (or Repair-run) the feed.

> **"Ingest the live clinical-trials feed from the shared Volume `/Volumes/<cat>/<source_schema>/trial_landing/trial_catalog/` **incrementally with Auto Loader** (`cloudFiles`, format `text`, `trigger(availableNow=True)`, schemaLocation + checkpoint in MY schema). `try_parse_json` each line into ONE `VARIANT` column and append to a schema-stable `bronze_trial_catalog` — keep the raw `value` string and `_source_file`. Then flatten the GOOD records to `silver_trial_criteria` (real typed columns: trial_id, trial_name, status, req_sex, age_min, age_max, req_her2, req_er, req_pr, req_menopausal, req_no_prior_anti_her2, min_ecog, eligibility_text) keeping ONE row per trial_id by newest `load_ts` (`ROW_NUMBER() OVER (PARTITION BY trial_id ORDER BY load_ts DESC)`); a missing key reads NULL = 'this trial does not constrain that field.' Finally **quarantine** the bad rows into `bronze_trial_quarantine` with a `quarantine_reason`: `unparseable` (trial_raw IS NULL), `missing_trial_id` (no id), `bad_type_age` (min_age_years present but `::int` is NULL). Show me the bronze count, the clean silver, and the quarantine breakdown by reason."**

*Good looks like:* Auto Loader ingests only **new** files each run (re-run it and the bronze count
climbs); bronze stays **one `VARIANT` column** no matter how many keys arrive; silver holds the clean
trials deduped latest-wins (**Trial A carries `min_ecog=1`**, others `NULL`) and **grows as clean
trials land**; `bronze_trial_quarantine` collects the bad rows — one `unparseable`, one
`missing_trial_id`, one `bad_type_age` — **each with a reason, and the load never crashed**. Because
bronze is `VARIANT`, the new `min_ecog` criterion needs **no schema surgery** — the flatten already
projects the path. This is the **net-new dataset** this session builds; it never touches the read-only
OMOP source. The table is the contract the Applied AI section joins against — adding a trial is a file
landing, not a code change.

> **If Genie Code reaches for a one-shot `read_files(...)` batch read**, that's the redirect: it works,
> but it re-reads every file every time. The ask is **incremental** — `cloudFiles` with a checkpoint so
> each run appends only new files. That's the whole point of a *live* feed.
>
> **SQL-only flatten variant:** the VARIANT paths are `trial_raw:eligibility.her2_status::string`,
> `trial_raw:load_ts::timestamp`, etc. Dedup with `QUALIFY ROW_NUMBER() OVER (PARTITION BY
> trial_raw:trial_id::string ORDER BY trial_raw:load_ts::timestamp DESC) = 1`. (Bronze/flatten pattern
> validated on FEVM2; Trial A `min_ecog=1`, others NULL.)

---

### 6b. Prove the catalog is join-ready — the contract with Applied AI  *(cross-group payoff)*
> **"Show me that `silver_trial_criteria` is actually join-ready: CROSS JOIN a couple of patient
> biomarker profiles against it and, for each trial, evaluate every non-null `req_*` (NULL = the trial
> doesn't constrain that field) to a TRUE/FALSE eligible flag. Confirm one generic join serves all three
> trials — I shouldn't need per-trial SQL."**

*Good looks like:* a single query screens a patient against **every** trial at once — the proof that
"trials are data, not code." This is exactly the join the Applied AI group's `gold_trial_prescreen`
builds on top of (their long, one-row-per-person×trial pre-screen lands **A 140 / B 56 / C 53, +31
recovered only via NLP**). Handing them a clean, NULL-means-unconstrained catalog is what lets a new
trial flow all the way to the coordinator app with zero code change.

---

### 🧩 Now design your own (the open part)
You have a governed, reconciled ingest — extend it however a real clinical-data team would:

- *"Turn my re-runnable Auto Loader ingest (nb 05) into a continuously-running stream with `trigger(processingTime='30 seconds')`, or schedule the notebook every few minutes, so the trials catalog stays current hands-free."*
- *"Add Lakeflow data-quality EXPECTATIONS to the trials ingest and route violations to the quarantine table, so the bad-record rules live in the pipeline definition."*
- *"Make the SLA window and the allow-list fully config-driven from UC tables so ops changes behavior with zero deploys."*
- *"Use `ai_query` to parse each trial's free-text `eligibility_text` into structured criteria and reconcile it against the structured `req_*` columns."*

**Optional — expose it via a self-serve Genie space.** Any team can install the workspace-level
`prompt-to-genie` skill (see the README) and say **"create a Genie space"** over your `recon_summary` /
ingest-audit tables — a steward asks *"which tables failed reconciliation last night?"* in plain
English. A monitoring Genie space over your own audit tables is a clean thing to demo.

If a pattern misbehaves, the worked solution for every notebook is in `reference/ANSWER_KEY.md` — these
TODOs are plumbing-shaped, so reveal the *mechanism* early if a team is spinning; the value is in the
*why* (evolve-don't-break, anti-join-the-missing, config-driven gate, midnight-wrap).
