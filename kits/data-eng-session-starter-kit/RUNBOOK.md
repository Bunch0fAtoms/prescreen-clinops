# 🧭 RUNBOOK — Data Engineering Session (build-level facilitation)

**Mentor-facing. Build-level only.** Event-level facilitation (agenda, room dynamics, the security-first
framing, the parallel-track structure, debrief) lives in the onsite agenda docs — don't duplicate it here.
This runbook is the per-build-block detail: what's pre-built, what the team builds, the named
**Checkpoints**, common failures, and the answer-key fallback.

**Customer:** Fred Hutch · Data Engineering track of the 2-day onsite (one of four parallel sections).
**Team:** comfortable with SQL + notebooks; this track is **ingestion plumbing** — practical DE patterns,
not GenAI. The four TODOs are small and high-leverage, so reveal sooner than on the ML track.
**Outcome:** a governed, reconciled OMOP ingest — schema that evolves, counts that reconcile, a gate that
blocks restricted tables, a guard that respects the SLA window, plus a net-new LIVE Volume-fed trials
feed ingested incrementally to `silver_trial_criteria` with bad records quarantined. **Security-first:** synthetic data only,
everything UC-scoped, the source schema is read-only, config over code.

**Reveal ladder:** nudge → hint (point at the `# TODO`) → **point at the matching prompt in
`GENIE_CODE_PROMPTS.md`** → pair → reveal (`reference/ANSWER_KEY.md`). These TODOs are plumbing-shaped —
reveal the *mechanism* early if a team is spinning; the value is in understanding *why*
(evolve-don't-break, anti-join-the-missing, config-driven gate, midnight-wrap), not in guessing syntax.

**Free-form build.** This session is intentionally open — the team designs their own ingestion-hardening
solution on the read-only source tables. `GENIE_CODE_PROMPTS.md` holds ready-to-use Genie Code build
prompts (numbered to the notebooks, each with a "good looks like"); treat them as *starters the team can
adapt*, not a script.

**The five notebooks are independent.** You can run them in any order. `01`→`02` are a natural
ingest→verify pair; `03`/`04` are reusable guards; `05` is the net-new LIVE trials feed on a Volume
source. If a team stalls on one, move to another and circle back.

**Net-new dataset in nb 05: the LIVE trials feed.** Notebooks 01–04 harden the OMOP silver. Notebook
05 builds something new: a **live**, presenter-controlled clinical-trials feed (the foundation
`land_trial_feed` task streams files into a shared Volume) ingested **incrementally with Auto Loader**
into `silver_trial_criteria`, with bad records **quarantined**. That table is the **eligibility contract
the ML group's pre-screen joins against** — adding a trial is a file landing, not a code change. Same
read-only-source discipline as 01–04, on a live Volume feed instead of tables.

**Cross-group: both groups build in parallel off the 6 OMOP tables.** This DE track and the Applied AI
(ML) track both start from the shared foundation, the 6 read-only OMOP tables (see
`../../SHARED_FOUNDATION.md`). Neither group waits on the other's data layer. This track's cross-group
contribution is the **trials catalog** `silver_trial_criteria` (nb 05), the **eligibility contract the
ML pre-screen joins against**. If the ML group is ahead, they can flatten the same Volume themselves, so
it is a hand-off, never a blocker. Don't let the team think they're blocking ML.

---

## Block 0 · Setup & foundation (pre-build)

- **Pre-built:** the DAB (`databricks.yml`), `_config`, the 6 read-only OMOP source tables, the foundation check.
- **Team does:** fill `client_catalog` / `client_schema` / `source_schema` / `warehouse_id` in
  `databricks.yml`; `databricks bundle deploy --target client`; open `00_START_HERE`, set the widgets, run
  the foundation check.
- **🚩 Checkpoint 0 — Foundation up.** `00` shows all 6 source tables ✅ (person=300, condition_occurrence=300,
  measurement=720, observation=720, drug_exposure=383, note=265) and "your schema is writable."
- **Common failures:**
  - *`CREATE CATALOG` permission denied* → `_config` tolerates this (the catalog is usually pre-provisioned).
    If the schema create also fails, the team lacks rights on their catalog — **plumbing, escalate**, not their lesson.
  - *Source table not found* → wrong `source_schema` widget (should be the read-only OMOP schema).
  - *`hive_metastore` muscle memory* → redirect to the UC catalog/schema from the bundle.

## Block 1 · Schema evolution (nb 01) — 🛠️ GUIDED TODO

- **Pre-built:** the v1 bronze writer, the incoming v2 DataFrame (with the new `condition_source_name`),
  the **naive append that deliberately FAILS**, and the before/after schema diff.
- **Team builds:** the one-option `mergeSchema` append that lets the table evolve instead of breaking.
- **🚩 Checkpoint 1 — Schema evolved.** The target now has `condition_source_name`; the verify cell shows
  **300 pre-evolution (NULL) + 300 post-evolution (populated) = 600 rows**. No job broke, no data lost.
- **Common failures:**
  - *They reach for `overwriteSchema`* → that *replaces* the schema (and on overwrite would clobber rows).
    For *adding a column on append* it's **`mergeSchema`**. (ANSWER_KEY nb 01.)
  - *"Why did the naive cell fail?"* → that's the point: `[DELTA_METADATA_MISMATCH]` is the broken nightly
    job. The fix is the one option. (The failure is reliable on serverless Delta — confirmed.)
  - *They want Auto Loader* → great instinct, but `cloudFiles` needs a file source in a volume; it's
    documented in the notebook markdown + `STRETCH.md`. The `mergeSchema` batch path is the serverless lesson.

## Block 2 · Row-count reconciliation (nb 02) — 🛠️ GUIDED TODO

- **Pre-built:** the bronze copies (with a deliberate **7-row gap injected into `measurement`**), the
  `recon_summary` audit-table writer, and the headline verdict cell.
- **Team builds:** the per-table count comparison (`count_recon`) and the missing-key **anti-join**.
- **🚩 Checkpoint 2 — Reconciliation flags the gap.** `count_recon` shows `measurement` FAIL with delta=7;
  the anti-join returns exactly ids **101, 202, 303, 404, 505, 606, 707**; all other tables PASS;
  `recon_summary` has a timestamped row per table.
- **Common failures:**
  - *Anti-join finds nothing missing* → they joined bronze to bronze, or didn't qualify the source schema.
    The source is in a **different schema** — `catalog.source_schema.measurement` vs the `USE`d
    `bronze_measurement`. (ANSWER_KEY nb 02 — the #1 gotcha here.)
  - *`NOT IN` returns weird results* → NULL semantics; steer to `LEFT ANTI JOIN`.
  - *Counts all match (no FAIL)* → they counted source vs source, or skipped the injected-gap cell. Re-run
    the pre-built copy cell.

## Block 3 · Restricted-table ingest gate (nb 03) — 🛠️ GUIDED TODO

- **Pre-built:** the `ingest_allowlist` UC config table (6 OMOP allowed, 2 restricted denied), the
  `safe_ingest()` wrapper that calls the guard first, and the allowed/blocked proof cells.
- **Team builds:** `assert_ingest_allowed(table)` — reads the UC allow-list, raises before any write.
- **🚩 Checkpoint 3 — Restricted table blocked.** `safe_ingest('person')` writes `bronze_person`;
  `safe_ingest('genomic_sequencing')` raises `PermissionError` and **no** `bronze_genomic_sequencing`
  table is created (the proof cell asserts this).
- **Common failures:**
  - *They hardcode an `if table in ['genomic_sequencing', ...]:` list* → **this is the redirect.** The whole
    ask is config-driven: read `ingest_allowlist` so a steward changes behavior with no deploy. Hint at the
    pre-built config table they're meant to query.
  - *Guard runs but the table still lands* → they checked *after* the write, or didn't `raise`. The guard
    must raise so `safe_ingest` never reaches the write.
  - *"Where's the deny-list?"* → one-line flip (invert the boolean + default). Mention it, don't rebuild it.

## Block 4 · SLA job windows (nb 04) — 🛠️ GUIDED TODO

- **Pre-built:** the window config (23:00–08:00 PT), the timezone-aware `source_now()`, the truth-table
  self-test, the skip/wait usage patterns, and the Jobs schedule (`resources/sla_ingest_job.yml`).
- **Team builds:** `in_sla_window(now)` — the overnight (midnight-wrapping) window check.
- **🚩 Checkpoint 4 — Guard correct across the clock.** The truth-table cell is all ✅: 00/05/07 → in-window,
  08/12/22 → out, 23 → in. The guard cell prints skip-or-proceed for the current time without hanging.
- **Common failures:**
  - *`start <= h < end` returns always-False* → **THE gotcha.** With start=23 > end=8 that range is empty;
    the window wraps midnight → `h >= 23 OR h < 8`. (ANSWER_KEY nb 04.)
  - *They try to set a Spark/Delta conf for the window* → no; the window is plain config + a clock check.
  - *"Does this stop scheduled runs too?"* → yes, the bundle's cron (`0 0 8-22 * * ?`) never fires in-window;
    the runtime guard catches manual/backfill runs. Defense in depth — point at `resources/sla_ingest_job.yml`.
    (It ships `pause_status: PAUSED` so the kit never fires unattended.)

## Block 5 · Trials catalog — LIVE feed ingest (nb 05) — 🛠️ GUIDED TODO (net-new dataset)

> **Presenter action:** start the feed. In the deployed **foundation** job, run (or Repair-run)
> the `land_trial_feed` task at the top of this segment. It streams trial files into the shared
> `trial_landing` Volume — clean trials first, a `min_ecog` change next, then bad records, then a
> clean heartbeat — and runs until you cancel it. Compress with `--speed 6` for a dry run. To pause,
> cancel the run; to resume, Run now (OMOP regen is harmless) or Repair-run just `land_trial_feed`.

- **Pre-built:** the incremental **Auto Loader** ingest (`cloudFiles` text → `try_parse_json` → a
  schema-stable `VARIANT` bronze, checkpointed in the team's own `_ingest_state` Volume) and the flatten
  of GOOD records to `silver_trial_criteria` (latest-wins per `trial_id` by `load_ts`, `min_ecog`
  projected from the VARIANT).
- **Team builds:** the **quarantine** — `bronze_trial_quarantine` with a `quarantine_reason` per bad row
  (`unparseable`, `missing_trial_id`, `bad_type_age`), so a malformed record is routed aside instead of
  failing the load. The `# TODO` is: **separate good from bad, keep good flowing.**
- **🚩 Checkpoint 5 — Live feed ingests incrementally and survives bad data.** Re-running the ingest picks
  up only NEW files (the bronze count climbs). `silver_trial_criteria` holds the clean trials, deduped
  latest-wins, with `min_ecog` present (Trial A = 1, others NULL, no rows lost). `bronze_trial_quarantine`
  holds the three bad records with reasons. Because the feed is live, **counts grow** — the signal is that
  good and bad are cleanly separated and nothing crashed, not a fixed total.
- **Common failures:**
  - *They use `parse_json`, and the malformed line fails the whole batch* → **the redirect.**
    `try_parse_json` returns NULL on a bad line; route the NULLs to quarantine. (ANSWER_KEY nb 05.)
  - *They do a one-shot `read_files(...)` batch read* → works, but re-reads everything each run. The
    lesson is **incremental**: `cloudFiles` + checkpoint appends only new files.
  - *They point Auto Loader's checkpoint at the shared Volume* → it must live in the team's OWN schema
    (`_ingest_state`); the landing Volume is read-only shared.
  - *They try to `mergeSchema` for `min_ecog`* → not needed here. Bronze is `VARIANT`; the flatten already
    projects the path. (The `mergeSchema` lesson is nb 01, on an OMOP append — don't cross the wires.)
  - *`bad_type_age` confuses them* → `min_age_years` is present in the VARIANT but `::int` is NULL. Present
    + uncastable ≠ absent; that two-part check is the reason. (ANSWER_KEY nb 05.)

---

## Quick reference — checkpoint summary

| # | Checkpoint | Signal it's met |
|---|---|---|
| 0 | Foundation up | 6 source tables ✅ (300/300/720/720/383/265), schema writable |
| 1 | Schema evolved | `condition_source_name` added; 300 NULL + 300 populated = 600 rows |
| 2 | Reconciliation flags the gap | measurement FAIL delta=7; anti-join returns ids 101–707; `recon_summary` written |
| 3 | Restricted table blocked | `bronze_person` lands; `genomic_sequencing` raises; no bronze table created |
| 4 | SLA guard correct | truth-table all ✅ (wrap-around right); guard cell doesn't hang |
| 5 | Live trials feed ingests + quarantines | Auto Loader picks up only new files (bronze grows); `silver_trial_criteria` deduped latest-wins with `min_ecog` (A=1, others NULL); `bronze_trial_quarantine` holds the bad rows (unparseable / missing_trial_id / bad_type_age); load never fails |

**Validation note:** all five notebooks were run green on FEVM2 (`a reference workspace`,
catalog `<your_catalog>`, writing `clinops_de`, reading `clinops_foundation`)
with the `reference/ANSWER_KEY.md` solutions. The answer key reproduces every artifact.
