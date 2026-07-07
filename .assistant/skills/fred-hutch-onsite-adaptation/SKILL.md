---
name: fred-hutch-onsite-adaptation
description: Configure, deploy, and adapt ANY Fred Hutch onsite starter kit (Governance, Data Engineering, ML/Clinical-Trial-Pre-Screening, Admin) in the user's Databricks workspace. Install once at the workspace level; it adapts whichever kit is the active project. Use when the user is working in (or has imported) a fred-hutch onsite kit AND says any of "run in my workspace", "set this up", "configure for my workspace/catalog/schema", "deploy this kit/demo", "make this work in my workspace"; OR wants to rename tables / "use my naming convention"; OR wants to change a threshold, metric, formula, aggregation, grain, or segmentation rule, or swap synthetic data for real data.
---

# Fred Hutch Onsite Kit Adaptation (workspace-level, multi-kit)

<!-- SKILL_VERSION: 1.0.0 -->
`SKILL_VERSION: 1.0.0`

> This is ONE skill a **workspace admin installs once** at the **workspace level**
> (`/Workspace/.assistant/skills/`, via `databricks workspace import-dir`), so every builder has it.
> Installing the skill is separate from deploying a kit — `bundle deploy` does not install it.
> It is **kit-agnostic**: every per-kit value is read from the **`ADAPTATION_FACTS.json` that ships
> beside the active kit** (the folder the user cloned + is working in). It does NOT reconstruct a
> kit's shape by guessing. A wrong fact is worse than a missing one — when a value lives in
> `ADAPTATION_FACTS.unresolved[]`, HALT and ask the author/client.

## The build day you're part of [STORY]

Read this once. It is the context behind every rule below.

You are helping a **Fred Hutchinson Cancer Center** team during a **live, two-day onsite**. The
teams are building a **clinical-trial patient pre-screening** solution: given a trial's eligibility
rules, find the patients who might qualify. The data is **synthetic OMOP** (a standard clinical data
model), shaped to match Fred Hutch's real tables so the same work runs later on real data with no
rewrite. No real patient data is in play here.

Four teams build **in parallel**, each on its own track, and each **presents what they built** at the
end. Governance is the foundation everyone builds on, so it shows up in every track:
- **Governance** applies masking, row filters, lineage, and audit on the shared data.
- **Data Engineering** ingests and hardens the data, including a live trials feed.
- **ML / Pre-Screening** builds the models and the pre-screen logic that ranks patients.
- **Admin / Genie One** answers cost and usage questions in natural language.

Your job is to be a **build partner**, not a wizard that does it for them. Two things matter by the
end of the day: a **working result** they can demo, and a team that feels **capable of doing this
again** on their own data. Help them move fast, and help them understand what they just built.

**There is a reference path, and it is optional.** Each kit ships pre-built code plus a
`GENIE_CODE_PROMPTS.md` and often a `STRETCH.md`. That is a **menu, not a script.** A team may follow
it exactly, remix it, or invent a different solution. All three are wins. The gates and locks below
exist to protect the **shared foundation from silent breakage**, not to force one path. Inside a
team's own schema, encourage them to explore.

## Coaching posture [STORY]

How to help, especially when a team is stuck, exploring, or going off-script. These are habits, not
gates. Use judgment.

- **Lead with their goal, then offer directions.** Restate what they're trying to do in one line.
  Offer two or three ways forward and let them pick. Do not march them down a single path.
- **Support divergence; make it safe, don't steer it back.** When a team wants something the kit
  didn't pre-build, help them do it — while honoring the locks (§3) and keeping writes in their own
  schema. A different-but-working solution is a success, not a detour.
- **Hint before you hand over the answer.** If the next step is small and they're close, point at the
  idea (the table, the function, the prompt in `GENIE_CODE_PROMPTS.md`) and let them try it. Give the
  full solution when they're blocked, short on time, or ask for it directly.
- **Name the wins.** When a verify query passes or a table lands with the expected counts, say so
  plainly. Visible progress keeps a live room moving.
- **Explain the "why" in one sentence.** These teams present their work. A one-line reason ("VARIANT
  lets new fields arrive without a schema change") is worth more than a wall of detail.
- **Read the room's time.** This is time-boxed. If they're behind, offer the shortest path to a
  working result and flag the stretch ideas as "after the demo."

## 0. Which kit am I adapting? — resolve FIRST [GENERIC]

1. Locate `ADAPTATION_FACTS.json` in the **active project root** (beside `databricks.yml`). If none is
   found, ask the user which kit folder they're in / to open it. Do not proceed without a facts file.
2. Read `demo_slug` / `demo_name` — that identifies the kit. The shared foundation plus the four onsite kits:

   | Kit | Has DAB? | `deploy_target.kind` | Stand-up shape |
   |---|---|---|---|
   | Shared Foundation (`fred-hutch-prescreen-foundation`) | yes | `job` (`foundation_setup_job`) | deploy → run the job: `generate_omop_data` writes the 6 OMOP tables (one-time), `land_trial_feed` is a **long-running, presenter-controlled live trials feed** (streams files until the run is cancelled; the run stays RUNNING by design). Stand this up FIRST — the other kits read from it. |
   | Governance (`fred-hutch-governance-session`) | **no bundle** | `none` | **No bundle, no clone.** Governance is Genie-Code-driven policy on the **shared foundation** tables, governed in place. Set classification and a tag-based policy at the catalog and schema level so it inherits to every child asset. Setup = confirm the foundation's 6 OMOP tables exist, then point Genie Code at the shared foundation schema. Do NOT create a per-team clone. `notebooks/` are optional facilitator backup. |
   | Data Engineering (`fred-hutch-omop-data-eng-session`) | **no bundle** | `none` | **No bundle to deploy.** The team builds the trials-feed ingest LIVE with Genie Code (see the kit's `GENIE_CODE_PROMPTS.md`: Track 1 Structured Streaming notebook → Job, or Track 2 Lakeflow Declarative Pipeline). Setup = confirm the foundation source tables and live feed Volume are up, then point Genie Code at the read-only `source_schema` and a writable `client_schema` (the first prompt creates it). No `databricks.yml`, no widget defaults to write. `notebooks/` are optional facilitator backup. |
   | ML / Pre-Screening (`fred-hutch-clinical-trial-prescreening`) | **no bundle** | `none` | **No bundle to run.** ML reads the **shared foundation's** 6 OMOP tables and builds via Genie Code. The ONE pre-built notebook that MUST run is `05` (ClinicalBERT → UC), which Genie Code cannot author. Setup = confirm the foundation tables exist, then point Genie Code at the foundation schema (reads) and a writable `client_schema` (writes). `notebooks/` are the facilitator backup. |
   | Admin / Genie One | **no bundle** | n/a | **No adaptation needed** — SQL + Genie One over `system.billing`. If asked, point the user at the kit's `sql/` + `GENIE_ONE_PROMPTS.md`; there is nothing to deploy. |

3. Everything below is driven by the active kit's facts — never hardcode a kit's tables, deploy
   command, or variables from memory.

## 1. Entry gate — run IN ORDER before ANY edit [GENERIC]

| # | Gate | Fail action |
|---|---|---|
| G1 | Load the active kit's `ADAPTATION_FACTS.json`. If `skill_version` != `1.0.0` → package is stale. | Tell the user to re-import the fresh kit. **HALT.** |
| G2 | **T-preflight** (run even if the user says it's set up): confirm `current_user`; the target catalog/schema reachable; warehouse up; for a `job` deploy_target, the resource exists. | Name the exact failed check (auth / catalog / schema / warehouse). **HALT.** |
| G3 | Classify intent: `setup` \| `rename` \| `transform`. | If ambiguous, ask one question. |
| G4 | Emit a short confirmation block: kit + intent + the facts fields you'll read + files you may touch. | — |
| G5 | Wait for the user's confirmation. | Do not edit before "yes". |

**Any gate failure → HALT and name the exact missing fact or check.** Whenever a needed value is in
`unresolved[]` → HALT and ask; never guess.

## 2. Read facts, don't reconstruct [GENERIC]

| Task needs… | Read from facts |
|---|---|
| Deploy / run command | `deploy_target.run_command` (+ `deploy_target.kind`) |
| Editable DAB variable names | `name_vars` (`catalog_var`, `schema_var`, `warehouse_var`, and kit-specific extras like `group_var`, `source_catalog_var`, `source_schema_var`) |
| Synthetic ↔ real switch | `toggle` (a boolean var AND/OR source-repointing via `source_catalog_var` + `source_schema_var`; read `real_source_catalog`/`real_source_schema`). Real OMOP is a DIFFERENT catalog, so set BOTH. |
| Notebook widget defaults to rewrite | `widget_config` (`file` + `widgets` map). Notebooks read widgets, not DAB vars — rewrite these defaults so a run inherits the chosen values. |
| How to finish a real-data switch | `real_mode` (`how` + `rebuild_assets`) — repoint, then rebuild anything already materialized from synthetic |
| What each table is / expected counts | `tables[]` |
| Upstream/downstream + dashboard/genie refs | `dependency_map[]` |
| Valid grain columns, min partition size | `grain_constraints[]` |
| Where raw data enters + its type | `source_inputs[]` (`source_type`, `locator`) |
| Verify SQL after setup/transform | `verify_queries[]` (templated with `${client_catalog}`/`${client_schema}`) |
| Files off-limits per task | `lock_targets[]` |
| Kit-specific governance vocabulary etc. | any extra facts blocks (e.g. `governed_tag_policy`, `phi_columns`) |

## 3. Global hard locks [GENERIC]

> These locks protect the **shared foundation and this skill** from silent breakage. They are not a
> brake on the team's own build. Inside a team's own schema, explore freely (see Coaching posture).

- `MUST NOT EDIT` anything under `.assistant/**` — including this skill file. The adaptation skill MUST NOT modify itself or any skill. (This prohibition always binds.)
- Locks are keyed by `lock_targets[].task_class`, which is GRANULAR and operation-specific (`rename_table` vs `rename_column`, `add_metric`, `change_grain`, `setup`). Match your intent to the SPECIFIC operation, never a substring. Treat every path in a matching entry as `MUST NOT EDIT \`<exact-path>\``. Only when the operation is genuinely ambiguous, fall back to the UNION of all `lock_targets[].paths` as a safe floor. Writing to a locked path is a reasoning defect — STOP.
- **Never deploy from inside Genie Code.** The CLI is sandboxed in `executeCode` and can't `cd` to the bundle root. Always OUTPUT web-terminal commands and stop.
- **Governance governs the SHARED foundation, on purpose** (governance kit): set classification and policy at the catalog and schema level on the shared foundation tables so it inherits to every child asset. Policies change what *everyone* sees, and that is the point, they are group-gated (data office sees raw, researchers see masked). Do NOT create a per-team clone and do NOT steer the team toward an isolated schema.
- **Rewriting widget DEFAULTS is allowed (it is setup, not a rename).** During setup you MAY edit the default value (the 2nd arg of `dbutils.widgets.text`) in the `widget_config.file` for the widgets named in `widget_config.widgets`. That is how the chosen catalog/schema/warehouse/source values reach an interactive run. This is distinct from a `rename_table` lock, which forbids changing table-identifier strings — do NOT touch table identifiers, SQL logic, or the trials-feed path.

## 4. Setup flow — "run in my workspace" [GENERIC]

1. **Auto-detect** workspace, current user, current catalog/schema, and a running serverless warehouse.
2. **Decide use vs ask**, ONE question at a time:
   | Detected value | Action |
   |---|---|
   | workspace url present | trust; confirm only |
   | catalog is a shared/sample/empty default | ASK which catalog |
   | catalog is user-owned | use, but confirm |
   | schema is empty/default | ASK; offer the kit's default (`client_schema` default in facts) |
   | a running warehouse found | use; confirm |
   | none running | ASK which to use |
3. **Synthetic vs real**, driven by the kit's `toggle`. Ask "start with synthetic data (recommended —
   runs end-to-end immediately) or your own OMOP data?" Then, for **real**:
   - **Boolean toggle** (ML, Foundation): set `toggle.variable` to `real_value`. For the Foundation
     this also no-ops the generator (real OMOP already exists); the trials feed still runs.
   - **Source-repointing (ALWAYS set BOTH vars).** Real OMOP lives in a **different catalog**
     (`curated_omop.omop`), so setting `source_schema` alone is not enough — you MUST set
     `source_catalog_var` **and** `source_schema_var` (read `real_source_catalog` /
     `real_source_schema` from `toggle`). This applies to ML and DE (read/ingest FROM) and Governance
     (which governs those tables **in place**, no clone). For synthetic, `source_catalog` = the shared
     foundation catalog (or blank) and `source_schema` = `clinops_foundation`.
   - **Do NOT repoint the DE trials feed.** The trials feed (`feed_schema`) is a synthetic workshop
     simulator on the foundation. It is independent of `source_schema` — leave it on the foundation
     even in real mode, or nb 05's Volume path breaks.
4. **Write `databricks.yml` AND the notebook widget defaults.**
   - **`databricks.yml`** — update `targets.client.variables` (`name_vars` + kit extras, incl. both
     source vars for real mode).
   - **Widget defaults** — the notebooks read from `dbutils.widgets`, NOT from DAB vars, so a
     `databricks.yml` change alone never reaches an interactive run. Using `widget_config`, rewrite
     each named widget's DEFAULT (2nd arg of `dbutils.widgets.text`) in `widget_config.file` to match
     the chosen values (catalog, schema, warehouse, and for source-repointing kits `source_catalog` /
     `source_schema`; leave DE `feed_schema` on the foundation). This is the step that makes the
     synth/real choice actually reach the build. It is allowed setup — see §3.
   - NEVER hardcode catalog/schema/warehouse/group as literals in SQL logic or elsewhere; only the
     widget DEFAULTS named in `widget_config` may be set. A hardcoded constant anywhere else is a
     packaging bug → surface and stop. Present as Accept/Reject; don't auto-write.
5. **Deploy from a web terminal — NOT from Genie Code.** Output the kit's exact commands (from
   `deploy_target`) and stop. Shapes by `deploy_target.kind`:
   > Open a Web Terminal (Compute → Terminal, or ⌘+Shift+T) and paste:
   > ```bash
   > cd ~/<your-unzipped-kit-folder>
   > databricks bundle validate --target client
   > databricks bundle deploy   --target client
   > # kind=job → also run the job that lands data. ONLY the Foundation runs a job:
   > #   databricks bundle run foundation_setup_job --target client
   > # Governance, Data Engineering, and ML → NO bundle to deploy. All three build live with Genie Code
   > #   on the SHARED foundation tables. Governance governs them in place (classify, then policy at the
   > #   catalog and schema level, no clone). DE ingests the live trials feed (Track 1 Structured
   > #   Streaming notebook to Job, or Track 2 Lakeflow Declarative Pipeline). ML reads the foundation
   > #   tables and builds the pre-screen (plus the one pre-built HF notebook 05). Setup is just: confirm
   > #   the foundation's 6 OMOP tables (and DE's live trials Volume) exist, then point Genie Code at the
   > #   foundation schema and a writable client_schema. Nothing to deploy or run for these three.
   > ```
   > **Foundation note:** `foundation_setup_job` includes `land_trial_feed`, a long-running live
   > feed that runs until cancelled — so the job run stays RUNNING by design. Tell the presenter to
   > start it at the top of the trials segment; pause = cancel the run; restart = Run now (OMOP
   > regen is harmless) or Repair-run selecting only `land_trial_feed`. Never deploy or run from Genie Code.
   Triage failures: "variable not found" → a `${var.*}` rename was missed (grep + fix);
   `permission denied` on catalog → user lacks `CREATE SCHEMA`; serverless not available → change job
   environment client id to a cluster policy; DE/ML "source table not found" → wrong `source_catalog`
   **or** `source_schema` (real OMOP is a different catalog — check both, in the widget defaults too).
A **pre-built notebook that reads OMOP by bare name** (e.g. `FROM note`) fails with
`TABLE_OR_VIEW_NOT_FOUND` in onsite mode: bare reads resolve against the notebook's DEFAULT schema,
which `_config` sets to the WRITE schema (`clinops_ml`), but the OMOP source lives in a DIFFERENT
schema (`clinops_foundation`). Fix: add an explicit `USE CATALOG {SOURCE_CATALOG}; USE SCHEMA
{SOURCE_SCHEMA}` right after `%run ./_config` so reads hit the source; writes stay pinned by `fqn()`,
so they still land in the write schema. The ML **HuggingFace notebook `05` ships with this section**,
it is the one pre-built notebook that MUST run in the onsite because Genie Code cannot register a
Hugging Face model to Unity Catalog. Validated this session: with HF egress, `05` runs end to end on
serverless (pip install, ~440 MB weight download, register to UC, `spark_udf` embed), and the UC
registration happens BEFORE the note reads, so a mis-scoped notebook still registers the model,
only the embeddings table and similarity break.
6. **Idempotency:** if `databricks.yml` already matches the workspace + chosen targets, say "no edits
   needed, ready to redeploy" and point at the run command.
7. **Real mode is more than a var flip — rebuild what was built on synthetic.** If the team is
   switching to real data AFTER already building on synthetic, read `real_mode.rebuild_assets` and
   walk them through it. Everything that reads source (silver/gold tables, NLP output, the model, the
   Genie space, the app; or, for Governance, the classification and masks/filters/policy on the shared foundation) was materialized from
   synthetic and must be re-run so it reflects real data. Repointing the vars alone leaves those
   assets stale. Name the specific re-runs from `real_mode` / `dependency_map`; the DE trials segment
   is unaffected (it keeps reading the foundation feed).

## 5. Rename flow — "use my naming convention" [GENERIC]

Separate intent from setup. Assumes setup ran. If you detect drift between code table names and
materialized UC tables at ANY time → STOP, run R1.5, wait.

**OMOP CDM caution (all kits):** the 6 OMOP table names (`person`, `condition_occurrence`,
`measurement`, `observation`, `drug_exposure`, `note`) are OMOP standard. The synth→real switch works
because real `curated_omop.omop` tables share these exact names. Before any rename, confirm whether the
user is renaming synthetic-only demo tables or matching a non-standard real schema. If the latter, the
fix belongs in `source_catalog`/`source_schema` variables, not table names.

**R1 — Parse + reconcile** against `tables[]` / `table_contract`; if the mapping omits defined tables,
list them and ask. Ambiguous → ask, don't guess.

**R1.5 — UC scope question (EMIT VERBATIM, then HALT until a/b/c).** Skip only if nothing is materialized.
```
Tables already exist in <catalog>.<schema>. Renaming code makes the next
deploy create new (empty) tables under the new names. What should happen
to the old tables?

  (a) Code-only rename        — safest; old tables orphaned; drop later manually
  (b) Code + ALTER TABLE      — preserves data + history; needs MODIFY privilege
  (c) Code + post-deploy DROP — clean schema; only run after pipeline succeeds

Mixed answers are fine. I will not edit any files until you reply.
```

**R2 — Pre-edit confirmation** (marker-wrapped table: Layer · Old · New · Files affected · R1.5 strategy; no writes until "yes").

**R3 — Atomic identifier rename (HARD SCOPE).** Rename ONLY bare table-identifier strings, in files
NOT locked under a `rename_table` lock_target. No SQL-logic refactors, no column renames, no
catalog/schema edits. Show a per-file diff. For (b) emit `ALTER TABLE … RENAME TO …` (run before
redeploy); for (c) emit a post-deploy `DROP TABLE IF EXISTS …` (run only after success).

**R4 — Redeploy.** Same shape as §4 step 5.

**Column-rename rule:** rename a column only if it is *factually wrong*. OMOP CDM column names are
standard — if a real source uses different names, alias at the source edge.

## 6. Transformation Playbook — T0–T5 [GENERIC]

**Routing rule (MUST FOLLOW):** changing gates / eligibility criteria / metric formulas / policy logic
→ do NOT edit on sight. Run the playbook first.

- **T0 — Read the source.** Open the target transform; record the exact expression you'll change.
- **T0.5 — Partition-key audit** (`grain_constraints`): the grain key exists, reaches the target
  un-dropped, is non-null, has sane cardinality.
- **T1 — Parse intent:** absolute gate vs relative gate. Relative (percentile/rank) ⇒ requires T3.
- **T2 — Dependency scan:** READ `dependency_map` for the target — emit downstream tables,
  `dashboard_refs`, `genie_refs`. Check each downstream for `SELECT *`.
- **T3 — Distribution check (relative gates ONLY):** run the matching `verify_queries[]` entry.
- **T3.5 — Observable threshold:** expose the computed threshold in the output.
- **T4 — Pre-edit confirmation block** (Target table · Expression changing · Old · New · Downstream ·
  Dashboard edit? · Genie edit?; no writes until confirmed).
- **T4.5 — Verify patches:** re-read every edited file; confirm the change landed, no stray edits.
- **T5 — Narrative audit:** grep Genie instructions + dashboard/notebook text for hardcoded numbers
  from the OLD logic. Update or mark `[updates after refresh]`.

**Redeploy scope:** a data-only change → re-run the kit's data/setup job (`deploy_target.run_command`);
a policy/logic change (governance masks, DE guards) → re-run the affected notebook.

## 7. Halt / continue matrix [GENERIC]

| Situation | Decision |
|---|---|
| Missing source, or a needed fact in `unresolved[]` | HALT — ask author/client |
| Schema mismatch WITH a clear alias path | CONTINUE with confirmation |
| `dependency_map` incomplete for the target | HALT |
| A `verify_queries` check fails | HALT + propose rollback scope |
| Governance binding policy on the shared foundation | CONTINUE, that is the design (govern in place, group-gated). Do NOT clone into a per-team schema |

## 8. Post-edit evidence contract [GENERIC]

After every write batch, emit: (1) files changed; (2) residual-identifier grep result (zero old
identifiers = consistent); (3) verify-query output; (4) redeploy-scope decision + reason.

## 9. Token-budget note (meta) [GENERIC]

Keep this skill lean and kit-agnostic. Every per-kit specific belongs in that kit's
`ADAPTATION_FACTS.json`, not here. Do not append unbounded "gotchas"; read the matching facts field on
demand rather than inlining it. **One sanctioned exception:** §10's build-patterns list. It is not
per-kit facts, it is current-API knowledge (Lakeflow/DLT + VARIANT) that helps any builder write code
Genie Code otherwise gets wrong on a first pass. Keep it short and prune an item the moment Genie
Code's own defaults handle it.

## 10. Build patterns, pre-load so Genie Code builds clean the first time [DE]

> These are current Lakeflow/DLT + VARIANT API details Genie Code sometimes gets wrong on a first
> pass. Pre-loading them is the "harden the skill" strategy in the project plan: an API-friction
> failure teaches nothing about the customer's problem, so we fix it once here rather than in the
> room. Apply these when a builder is assembling the **Data Engineering trials-feed ingest** (either
> framework). Suggest them as you help; do not silently rewrite a builder's code.

**Both frameworks:**
- **VARIANT reads are null-safe, always.** Extract every field with
  `try_variant_get(col, '$.path', 'TYPE')`, including the nested `eligibility.*` ones. Never a strict
  `::` cast: it throws `INVALID_VARIANT_CAST` the moment a trial legitimately omits a field. This
  applies in the flatten step AND inside any data-quality predicate.
- **Latest-wins, one row per `trial_id`.** LDP: use an `apply_changes` (AUTO CDC) flow with
  `keys=["trial_id"]`, `sequence_by="load_ts"`. Structured Streaming: dedup the source to one row per
  key (`row_number()` newest by `load_ts`) BEFORE the `foreachBatch` MERGE, or the first batch inserts
  every version of a re-landed trial.

**LDP-specific (each cost a full pipeline run in dry-run testing):**
- **`apply_changes` uses `column_list`, not `columns`.** The keyword is `column_list=[...]`.
- **CDC quality expectations go on the SOURCE view, not `create_streaming_table`.** Decorate the
  flow's source view with `@dlt.expect_all_or_drop({...})` and read it via `dlt.read_stream`.
  Expectations placed on `create_streaming_table` are validated against the post-`column_list` target
  columns, so they cannot see raw/helper columns you projected out, and you get `UNRESOLVED_COLUMN`.
  Keep the raw flattened view separate so the quarantine table can still read the bad rows.
