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

## NB 05 — trials catalog schema evolution (🛠️ evolve the silver write + gate breaking changes)

**Intended TODO** — additive change auto-evolves via `overwriteSchema`; breaking change gates on approval:
```python
AUTO_FULL_RELOAD_ALLOWED = False
if change in ("none", "additive"):
    (silver_v2.write.mode("overwrite")
        .option("overwriteSchema", "true")     # lets the overwrite add the new min_ecog column
        .saveAsTable(fqn("silver_trial_criteria")))
elif change == "breaking" and AUTO_FULL_RELOAD_ALLOWED:
    (silver_v2.write.mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(fqn("silver_trial_criteria")))
else:
    raise Exception("Breaking schema change needs manual approval")
```
- **Why `overwriteSchema`, not `mergeSchema`:** the write is a full `mode("overwrite")` (the flatten
  reproduces every trial from bronze each run), so the option that *replaces* the schema is the right
  one. NB 01's append uses `mergeSchema`; this overwrite uses `overwriteSchema`. Same lesson, opposite
  write mode — don't let a team cross the wires.
- **The gate is the point:** additive drift (a new `min_ecog` criterion) flows through untouched; a
  breaking change (a dropped or retyped column) must be a human decision, not a silent reload. `classify_change`
  returns `additive` here, so the write auto-applies; the `AUTO_FULL_RELOAD_ALLOWED=False` branch is the
  guardrail for the breaking case.
- **Two flatten defects to know about (already fixed in the kit):** the shared `flatten()` (a) dedups to
  the latest record per `trial_id` with `ROW_NUMBER() OVER (PARTITION BY trial_id ORDER BY _source_file DESC)`
  so wave 2 (Q2) supersedes wave 1 (Q1) — otherwise bronze's two Trial A rows both survive; and (b) takes
  `include_ecog` so wave 1 flattens WITHOUT `min_ecog` and wave 2 flattens WITH it. Without that split the
  "new column arrives" story never happens and `classify_change` sees no additive change.
- **Validated:** 3 trials (A/B/C), no duplicate A; `silver_trial_criteria` gains `min_ecog`; Trial A=1,
  B/C NULL.

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
