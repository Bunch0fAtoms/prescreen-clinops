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

### 6. Build the trials catalog from a Volume — nested JSON → VARIANT bronze → flat silver  *(nb 05 · Chetan #15 · the net-new feed)*
> **"Land a nested clinical-trials JSON feed from my `trial_landing` Volume. Read the newline-delimited files, `parse_json` each record into ONE `VARIANT` column, and write a schema-stable `bronze_trial_catalog` (keep a `_source_file` column). Then flatten to `silver_trial_criteria` with real typed columns (trial_id, trial_name, status, req_sex, age_min, age_max, req_her2, req_er, req_pr, req_menopausal, req_no_prior_anti_her2, eligibility_text) — a missing key reads NULL, meaning 'this trial does not constrain that field.' The feed re-lands files, so a trial can appear in more than one wave: keep ONE row per `trial_id` from the newest file (`ROW_NUMBER() OVER (PARTITION BY trial_id ORDER BY _source_file DESC)`). Now a later wave adds a `min_ecog` criterion: classify the change additive-vs-breaking, and only if additive evolve the silver write so it GAINS the column instead of failing. Show me the bronze schema before/after and the flattened silver."**

*Good looks like:* wave 1 lands **3 trials (A / B / C)**; wave 2 re-lands so `bronze_trial_catalog`
holds **4 rows** but stays **one `VARIANT` column** (a new JSON key never changes bronze); the dedup
keeps the latest per trial (Q2 wins over Q1); the gate reads **additive** and `silver_trial_criteria`
ends at **3 rows** and **gains `min_ecog`** — Trial A carries `1`, B and C read `NULL`. This is the
**net-new dataset** this session builds; it lands in your schema, never touching the read-only source.
The schema-evolution decision moves to the FLATTEN step: for an overwrite that adds a column use the
option that lets the schema grow (`overwriteSchema` here, since the whole table is rewritten from the
re-landed bronze); a dropped or retyped column is **breaking** and must gate behind approval, not
auto-apply. This table is the contract the Applied AI section joins against — adding a trial is dropping
a file, not a code change.

> **SQL-only variant (Genie Code often prefers SQL):** the whole bronze step is one statement —
> `SELECT parse_json(value) AS trial_raw, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at FROM read_files('/Volumes/<cat>/<sch>/trial_landing/trial_catalog/trials_*.json', format => 'text')`.
> `read_files(..., format => 'text')` gives one row per line, so newline-delimited JSON parses cleanly
> without any Python. Flatten with `trial_raw:eligibility.her2_status::string` VARIANT paths. (Validated
> on FEVM2: bronze 4 rows, silver 3 trials, Trial A `min_ecog=1`.)

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

- *"Convert the batch ingest to Auto Loader `cloudFiles` reading files from a UC Volume, keeping schema evolution on."*
- *"Add Lakeflow data-quality EXPECTATIONS to the pipeline and route violations to a quarantine table."*
- *"Make the SLA window and the allow-list fully config-driven from UC tables so ops changes behavior with zero deploys."*

**Optional — expose it via a self-serve Genie space.** Any team can install the workspace-level
`prompt-to-genie` skill (see the README) and say **"create a Genie space"** over your `recon_summary` /
ingest-audit tables — a steward asks *"which tables failed reconciliation last night?"* in plain
English. A monitoring Genie space over your own audit tables is a clean thing to demo.

If a pattern misbehaves, the worked solution for every notebook is in `reference/ANSWER_KEY.md` — these
TODOs are plumbing-shaped, so reveal the *mechanism* early if a team is spinning; the value is in the
*why* (evolve-don't-break, anti-join-the-missing, config-driven gate, midnight-wrap).
