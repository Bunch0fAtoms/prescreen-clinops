# 🔑 Answer Key — SA / MENTOR ONLY

> **For the mentor. Reveal a snippet only if a team is genuinely stuck** (after the nudge → hint →
> pair ladder in `RUNBOOK.md`). This is a Data Engineering track — the TODOs are *plumbing-shaped*, so
> reveal sooner than you would on a GenAI "aha." These are the intended approaches + the gotchas so you
> can unblock without hunting. Every solution below was validated green on serverless.

All four notebooks are **independent**. Each writes to YOUR `schema` (default `clinops_de`) and
reads the 6 OMOP tables read-only from `source_schema` (default `clinops_foundation`). The `src()` and
`fqn()` helpers in `_config` enforce that split.

---

## NB 01 — schema evolution (🛠️ wire the evolution mode)

**Intended TODO** — append `v2` (which has the new `condition_source_name` column) with schema merge on:
```python
(v2.write.mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(fqn("bronze_condition_occurrence")))
```
- **Why it works:** `mergeSchema=true` tells Delta to *add* the unknown column to the target on append,
  rather than rejecting the write. Old rows read `NULL` for the new column; new rows carry the value.
- **The teaching beat:** the pre-built "naive append" cell (no option) FAILS with
  `[DELTA_METADATA_MISMATCH] A metadata mismatch was detected…` — that's the broken nightly job. The
  one-option fix is the whole lesson. (Confirmed: a plain `saveAsTable(...).mode("append")` with a
  superset schema *does* fail on serverless Delta — the failure is reliable.)
- **Gotcha:** `mergeSchema` (additive, on append) vs `overwriteSchema` (full replace, on overwrite) —
  teams reach for `overwriteSchema` and clobber the table. For *adding a column*, it's `mergeSchema`.
- **Auto Loader variant (markdown only):** `cloudFiles.schemaEvolutionMode=addNewColumns` (or `rescue`).
  Needs a file source in a UC volume — off the serverless-batch path, so it's documented, not run. Point
  a team there only as a stretch (see `STRETCH.md`).
- **Validated:** column added; 300 pre-evolution (NULL) + 300 post-evolution (populated) = 600 rows.

## NB 02 — row-count reconciliation (🛠️ build the anti-joins)

**Intended count-recon TODO:**
```python
rows = []
for t in OMOP_TABLES:
    s = spark.table(src(t)).count()
    g = spark.table(fqn("bronze_"+t)).count()
    rows.append((t, s, g, s - g, s - g == 0))
count_recon = spark.createDataFrame(
    rows, "table_name string, source_count long, target_count long, delta long, match boolean")
```
**Intended missing-key anti-join** (the cleanest is a `LEFT ANTI JOIN`):
```sql
SELECT s.measurement_id, s.person_id
FROM <catalog>.<source_schema>.measurement s
LEFT ANTI JOIN bronze_measurement b ON s.measurement_id = b.measurement_id
ORDER BY s.measurement_id;
```
- **Gotcha (the big one):** the source is in a **different schema** than the bronze copy. In the `%sql`
  cell teams must fully-qualify the source (`catalog.source_schema.measurement`) while `bronze_measurement`
  is in the `USE`d schema. Mixing them up → "table not found" or a self-join that finds nothing missing.
- **Why anti-join, not `NOT IN`:** `NOT IN` breaks on NULLs and is slow; `LEFT ANTI JOIN` is the
  idiomatic "rows in A with no match in B."
- **Expected:** measurement is short by **exactly 7** — ids `101, 202, 303, 404, 505, 606, 707` (the
  planted gap in the pre-built copy cell). All other tables reconcile (delta 0, PASS). `recon_summary`
  gets one PASS/FAIL row per table per run, timestamped.
- **Validated:** measurement delta=7, the 7 ids returned exactly, summary table written.

## NB 03 — restricted-table ingest gate (🛠️ build the guard)

**Intended `assert_ingest_allowed`:**
```python
def assert_ingest_allowed(table: str) -> None:
    row = (spark.table(fqn("ingest_allowlist"))
               .filter(F.col("table_name") == table).limit(1).collect())
    if not row or not row[0]["allowed"]:
        cls = row[0]["classification"] if row else "unknown"
        rsn = row[0]["reason"] if row else "not in allow-list"
        raise PermissionError(f"🚫 Ingest BLOCKED for '{table}' (classification={cls}): {rsn}")
```
- **The whole point (don't let them hardcode it):** the rule reads from the **UC `ingest_allowlist`
  table**, not an in-code `if table in [...]:`. A steward changes a row → behavior changes with no deploy,
  and it's auditable. If a team writes a Python list, that's the redirect — "make it config-driven."
- **Why it raises BEFORE the write:** the pre-built `safe_ingest()` calls the guard on line 1, so a
  blocked table never lands a row. The proof cell asserts `bronze_genomic_sequencing` does **not** exist.
- **Deny-list variant:** invert — block when a matching row has `denied = true`; default-allow. One-line flip.
- **Tag-driven variant (stretch):** read `information_schema` tag assignments and block any source tagged
  `classification=restricted`. See `STRETCH.md`.
- **Validated:** `person` (allowed) ingested; `genomic_sequencing` (allowed=false) raised PermissionError;
  no bronze table created for the blocked source.

## NB 04 — SLA job windows (🛠️ build the guard)

**Intended `in_sla_window`** (the overnight window WRAPS past midnight):
```python
def in_sla_window(now, start_hour=SLA_START_HOUR, end_hour=SLA_END_HOUR) -> bool:
    h = now.hour
    if start_hour <= end_hour:          # same-day window (general case)
        return start_hour <= h < end_hour
    return h >= start_hour or h < end_hour   # wrapping window: 23:00–08:00
```
- **THE gotcha:** with `start=23, end=8`, a naive `start <= h < end` is always False (empty range). The
  window is `h >= 23 OR h < 8`. The pre-built truth-table cell catches a wrong implementation
  (00/05/07 → in; 08/12/22 → out; 23 → in).
- **Two usage stances (pre-built):** *skip* (`dbutils.notebook.exit(...)` so the scheduler retries — best
  for idempotent ingests) vs *wait* (sleep until the window closes — reference only, never run live).
- **Scheduler half:** `resources/sla_ingest_job.yml` ships a Jobs schedule whose quartz cron
  `0 0 8-22 * * ?` (America/Los_Angeles) only fires 08:00–22:00, plus `pause_status` to halt all runs.
  Defense in depth: cron prevents scheduled in-window runs; the runtime guard catches manual/backfill ones.
  The job ships `pause_status: PAUSED` so the kit never fires unattended.
- **Validated:** guard correct across all tested hours; the guard cell runs without hanging (gated on the
  window check, demos *skip*).

## NB 05 — LIVE trials feed: incremental Auto Loader + quarantine (🛠️ route bad records aside)

**The feed is live.** The presenter starts the foundation `land_trial_feed` task; it streams files into
the SHARED `trial_landing` Volume (in `source_schema`) — clean trials first, then a `min_ecog` schema
change, then the bad records, then an indefinite clean heartbeat. Each team reads that Volume and writes
into its own schema. If a team sees "no files yet," the presenter hasn't started (or needs to Repair-run)
the feed.

**Intended TODO** — build `bronze_trial_quarantine` with a reason per bad row (good rows already flow to
silver in cell 3):
```python
spark.sql(f"""
  CREATE OR REPLACE TABLE {fqn('bronze_trial_quarantine')} AS
  SELECT value AS raw_line, trial_raw, _source_file, _ingested_at, quarantine_reason
  FROM (
    SELECT value, trial_raw, _source_file, _ingested_at,
      CASE
        WHEN trial_raw IS NULL                          THEN 'unparseable'
        WHEN trial_raw:trial_id::string IS NULL         THEN 'missing_trial_id'
        WHEN trial_raw:eligibility.min_age_years IS NOT NULL
             AND trial_raw:eligibility.min_age_years::int IS NULL THEN 'bad_type_age'
        ELSE NULL
      END AS quarantine_reason
    FROM {fqn('bronze_trial_catalog')}
  )
  WHERE quarantine_reason IS NOT NULL
""")
```
- **Why keep the raw `value`:** a malformed line has `trial_raw IS NULL` (from `try_parse_json`), so the
  only record of it is the raw text. Bronze keeps `value` precisely so quarantine can capture it. If a
  team used `parse_json` (not `try_parse_json`) the whole batch would fail on the bad line — that's the
  redirect: `try_parse_json` returns NULL instead of throwing.
- **`bad_type_age` is the subtle one:** `trial_raw:eligibility.min_age_years` is still present in the
  VARIANT (it's `"eighteen"`), but `::int` casts to NULL. "Present in the raw but uncastable" ≠ "absent."
  That two-part condition is what distinguishes a wrong type from an unconstrained field.
- **Incremental is the point:** Auto Loader (`cloudFiles` + checkpoint, `trigger(availableNow=True)`)
  appends only NEW files each run. Re-run cell 2 and the bronze count climbs; re-run cells 3–4 and silver +
  quarantine stay in sync. A one-shot `read_files(...)` re-reads everything every time — works, but misses
  the incremental lesson.
- **Schema evolution is free here:** because bronze is `VARIANT` and the flatten always projects
  `trial_raw:eligibility.min_ecog::int`, the new criterion needs NO schema surgery — Trial A picks up
  `min_ecog=1`, others read NULL. (The `mergeSchema`-on-append lesson lives in nb 01; don't cross the
  wires — nb 05 is about incremental ingest + quarantine, not the merge option.)
- **Dedup latest-wins on `load_ts`:** the feed re-lands trials (Trial A + min_ecog, Trial B conflicting,
  and the heartbeat). `ROW_NUMBER() OVER (PARTITION BY trial_id ORDER BY load_ts DESC)` keeps the newest.
  Ordering by `load_ts` (stamped at drop time) is more robust than filename order in the heartbeat phase.
- **Counts grow (it's live):** don't assert fixed totals. After the ~50-min opening act, expect the clean
  trials in silver (A/B/C/D/E/F, A with min_ecog=1) and 3 quarantined rows (`unparseable`,
  `missing_trial_id`, `bad_type_age`). Before that, counts are partial — that's correct.
- **Validated on FEVM2:** bronze VARIANT stable across new keys; silver deduped latest-wins with
  `min_ecog`; the three bad categories route to quarantine with reasons; the load never fails.

---

## Mentor quick-facts

- **Source (read-only):** `clinops_foundation` — person 300, condition_occurrence 300, measurement 720,
  observation 720, drug_exposure 383, note 265. Do **not** let a team write here.
- **Write target:** `clinops_de` (the `schema` widget). All bronze/recon/config tables land here.
- **`CREATE CATALOG` note:** `_config` *tries* to create the catalog but tolerates "no CREATE CATALOG"
  (most workspaces pre-provision it). If a team's catalog is missing AND they lack the grant, that's a
  plumbing escalation, not their lesson.
- **Backup:** the validated solved notebooks were run on FEVM2 (`a reference workspace`). If you
  need a full reveal, the solutions above reproduce every artifact green.
