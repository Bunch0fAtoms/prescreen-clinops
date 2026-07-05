# 🚀 STRETCH — make it your own

Finished the core build (notebooks 01–05, all the `# TODO (you build this)` markers)? Pick an
extension. These map to the `# EXTENSION (optional)` hooks scattered through the notebooks. None are
required — they're for teams who want to push further or have a real FH ingestion pattern in mind.

Ground rules still apply: **Unity-Catalog-scoped, synthetic data only, read-only source, no hardcoded
secrets, no hive_metastore.**

---

## 1. Auto Loader end-to-end (nb 01) — the file/streaming variant

Notebook 01 evolves schema with batch `mergeSchema`. Do it the streaming way:
- Write a few OMOP rows out as **JSON files** into a UC volume (`/Volumes/<cat>/<schema>/landing/condition/`).
- Read them with **Auto Loader** (`cloudFiles`), `cloudFiles.schemaEvolutionMode = addNewColumns`, a
  `schemaLocation` checkpoint, and `.trigger(availableNow=True)`.
- Drop a *second* batch of files with an **extra column** and watch the stream pick it up on restart.
- Compare `addNewColumns` vs `rescue` (unknown columns captured in `_rescued_data` — nothing lost).

The reference snippet is in nb 01's markdown. Use the `databricks-spark-structured-streaming` skill.

## 2. Column-level reconciliation (nb 02)

Row counts catch *missing* rows but not *changed values*. Extend `02`:
- Add a per-column **checksum** to `recon_summary` (e.g. `SUM(value_as_number)` for `measurement`, a
  hash aggregate, or `COUNT(DISTINCT person_id)`) so value drift is caught even when counts match.
- Make the reconciliation a **job task that fails on FAIL** — wire it after an ingest task so the pipeline
  goes red the moment a table doesn't reconcile. (Hook: nb 02 `# EXTENSION`.)

## 3. Tag-driven ingest gate (nb 03)

The gate reads an allow-list *table*. Drive it from **Unity Catalog tags** instead:
- Tag the restricted source tables `classification = restricted` in Catalog Explorer.
- Rewrite `assert_ingest_allowed` to read `information_schema` tag assignments and block any source
  tagged `restricted` — no separate config table at all.
- Discuss the trade-off: a dedicated allow-list table (explicit, simple) vs tags (governance-native,
  reused by masking/RLS). (Hook: nb 03 `# EXTENSION`.) See the `databricks-unity-catalog` skill.

## 4. Config-driven SLA window (nb 04)

The blackout hours are constants. Make them governed config like nb 03's allow-list:
- Put `source_system, start_hour, end_hour, timezone` in a UC table so a steward changes the window
  without a deploy, and support a **per-source-system** window (each upstream has its own batch hours).
- Add the **WAIT** stance for real (compute seconds-to-window-close, sleep in capped chunks) on a job that
  must complete tonight. (Hook: nb 04 `# EXTENSION`.)

## 5. Promote bronze → silver as a Lakeflow pipeline

The kit lands **bronze**. Add a governed **silver** layer:
- Build a Lakeflow Declarative Pipeline (SQL) that cleans/typecasts the evolved bronze tables, with
  `CONSTRAINT … EXPECT` data-quality expectations (e.g. `person_id IS NOT NULL`, plausible dates).
- Run the reconciliation (nb 02) **between** bronze and silver too. Use the
  `databricks-spark-declarative-pipelines` skill.

## 6. Governance deep-cut (the security-first lens)

Lean into the dominant onsite theme:
- Inspect the **lineage graph** from `source.measurement` → `bronze_measurement` → `recon_summary` —
  recorded automatically because everything is UC.
- Add **column masking** (mask `person_id` for an analyst role) or a **row filter** on a bronze table and
  show it in Catalog Explorer.
- Grant a steward `MODIFY` on `ingest_allowlist` and show them flipping the gate live — the whole
  config-over-code story, made visible.

## 7. Live trials feed — continuous stream + criteria extraction (nb 05)

Notebook 05 ingests the live feed with `trigger(availableNow=True)` (re-run to pick up new files). Push it further:
- Switch to a **continuously-running stream** (`trigger(processingTime='30 seconds')`) or schedule the
  notebook every few minutes so `silver_trial_criteria` stays current with zero clicks while the feed runs.
- Add **Lakeflow EXPECTATIONS** so the bad-record rules (missing id, bad type) live in the pipeline
  definition and route to quarantine declaratively, instead of the hand-written `CASE`.
- Use **`ai_query`** to parse each trial's free-text `eligibility_text` into structured criteria, then
  reconcile the extracted values against the structured `req_*` columns — extraction on the *trial* side,
  mirroring the patient-side note extraction the Applied AI group does. See the
  `databricks-spark-structured-streaming` skill.

## 8. Make the four guards a reusable module

Each notebook builds a guard in isolation. Package them:
- Move `assert_ingest_allowed`, `in_sla_window`, and a `reconcile(table)` helper into a small shared
  module (a `%run`-able notebook or a UC Python wheel) and call all three from a single ingest task —
  guard → SLA check → ingest → reconcile, with a one-line `safe_pipeline_ingest(table)`.
