# 🛠️ Governed, Reconciled OMOP Ingestion — Data Engineering Session Starter Kit

**Fred Hutch onsite · Data Engineering session · Genie Code + notebooks**

This is a **starter build kit**, not a finished solution. The hard plumbing is already
wired for you — the 6 synthetic OMOP source tables, the bronze landing pattern, Unity
Catalog scoping, all the boilerplate. **You** build the learnable data-engineering core:
the schema-evolution wiring, the reconciliation anti-joins, the config-driven ingest gate,
and the SLA-window guard. Look for `# TODO (you build this)` markers — that is your work.

> Scaffold, don't hand-hold. The notebooks tell you *what* to build and *why*; you write
> the logic. If a team gets truly stuck, the mentor has an answer key (see `reference/`).

---

## 🎯 The outcome you are shipping

A clinical-data engineering team ingests OMOP tables from a source system on a nightly
schedule. Five things keep going wrong — the first four are submitted Fred Hutch asks — and you
build the answer to all of them:

| # | The pain | You build | FH ask |
|---|---|---|---|
| 1 | Source adds a column → the ingest **breaks** (or silently drops it). | schema evolution on ingest | Chetan #15 |
| 2 | Did we load **every** row? Which records are **missing**? | a reconciliation framework | Chetan #17 |
| 3 | A **restricted** table gets ingested by accident. | a config-driven ingest gate | Jenn #16 |
| 4 | A job hammers the source during its **11pm–8am SLA window**. | an SLA-window guard | Jennifer #9 |
| 5 | Trials are **hardcoded in SQL**; a **live** feed drips files with drift and bad rows. | an incremental trials-feed ingest + quarantine | ML/Sita ask |

By the end you will have built:
- a bronze ingest that **evolves** when the source schema changes (Delta `mergeSchema`; Auto Loader `cloudFiles` variant documented),
- a **reconciliation** framework — source↔target counts, missing-key anti-joins, a persisted `recon_summary` audit table,
- a reusable **ingest gate** that blocks restricted tables from a **Unity Catalog allow-list** (not hardcoded),
- an **SLA-window guard** that skips the overnight blackout, plus the Jobs schedule / `pause_status` pattern that prevents it at the scheduler level,
- a **live trials feed ingest** — an **Auto Loader (`cloudFiles`)** incremental read of a live Volume feed into a schema-stable `VARIANT` bronze, a flatten to `silver_trial_criteria` (latest-wins per trial), and a **quarantine** for bad records.

> 🔗 **Both groups build in parallel off the same 6 OMOP tables.** You and the Applied AI (ML) group
> both start from the shared foundation, the 6 read-only OMOP tables (see `../../SHARED_FOUNDATION.md`).
> Neither group waits on the other's data layer. Your cross-group contribution is the **trials catalog**:
> you ingest the live trials feed to `silver_trial_criteria` (nb 05), and that table is the
> **eligibility contract the ML pre-screen joins against**. If the ML group gets there first, they can
> read the same Volume themselves, so it is a hand-off, never a blocker.

> 🆕 **Net-new dataset: the LIVE trials feed (nb 05).** The four notebooks above harden the OMOP
> silver. Notebook `05` adds something **new** the room hasn't seen: a **live**, presenter-controlled
> clinical-trials feed. The foundation `land_trial_feed` task streams nested JSON files into a **shared
> Volume** over time; you ingest them **incrementally with Auto Loader** into a schema-stable
> **`VARIANT` bronze**, flatten the good records to `silver_trial_criteria`, and **quarantine** the bad
> ones (a missing id, a malformed line, a wrong-typed field). That table is the **eligibility contract
> the ML group's pre-screen joins against** — so **adding a trial is a file landing, not a code
> change**. Because bronze is `VARIANT`, a new `min_ecog` criterion flows through with no schema surgery.
> Same read-only-source, land-in-your-own-schema discipline as nb 01–04, on a live Volume feed.

---

## 🧱 What's pre-built vs. what you build

| Component | Status |
|---|---|
| 6 synthetic OMOP source tables (read-only) | ✅ **Pre-built** — you ingest *from* them |
| `_config` shared catalog/schema/warehouse, `fqn()` / `src()` helpers | ✅ **Pre-built** |
| Bronze landing writers, the v2 "new column" frame, the injected reconciliation gap | ✅ **Pre-built wiring** |
| The schema-evolution `mergeSchema` append (nb 01) | 🛠️ **You build** (one option) |
| The count comparison + missing-key anti-join (nb 02) | 🛠️ **You build** |
| The `assert_ingest_allowed()` UC-driven guard (nb 03) | 🛠️ **You build** |
| The `in_sla_window()` overnight-wrap guard (nb 04) | 🛠️ **You build** |
| The live trials feed (foundation `land_trial_feed`) + the Auto Loader ingest + flatten (nb 05) | ✅ **Pre-built wiring** — presenter starts the feed |
| The `bronze_trial_quarantine` routing of bad records with a reason (nb 05) | 🛠️ **You build** |
| Continuous `processingTime` streaming, `ai_query` criteria parsing, tag-driven gate, config-driven window, more | 🚀 **Stretch** — see `STRETCH.md` |

---

## 🚀 How to deploy

This kit ships as a **Databricks Asset Bundle (DAB)**, Unity-Catalog-scoped per team. The
**recommended** way to stand it up is the shared **`fred-hutch-onsite-adaptation`** Genie Code skill —
installed **once at the workspace level** (not per repo), it adapts whichever onsite kit you're working
in by reading that kit's `ADAPTATION_FACTS.json` (shipped beside this README). Manual CLI deploy is the
fallback.

### Recommended — drive it with the workspace-level onsite handoff skill ("run in my workspace")
Genie Code does **not** auto-load skills, so install the shared skill once per workspace, then drive it
from a fresh chat in this kit's folder:

1. **Install the skill once per workspace** (shared across all four onsite kits — skip if already done):
   ```bash
   databricks workspace import-dir \
     ../.assistant/skills/fred-hutch-onsite-adaptation \
     /Workspace/.assistant/skills/fred-hutch-onsite-adaptation --profile <profile>
   ```
2. **Open Genie Code in a fresh chat, in this kit's folder** (hard-refresh the tab first — skills cache
   per tab) and say:
   > run in my workspace

   The skill reads **this kit's `ADAPTATION_FACTS.json`**, auto-detects your workspace, current user,
   catalog/schema, and a running warehouse; asks synthetic-vs-real (here = which schema `source_schema`
   points at); and writes **only** `databricks.yml`'s `client` target variables
   (`client_catalog`, `client_schema` — writable, default `clinops_de`; `source_schema` —
   read-only OMOP, default `clinops_foundation`; `warehouse_id`). Review and **Accept** the diff.
   Nothing is hardcoded into the notebooks/SQL.
3. **Deploy from a Web Terminal** (Compute → Terminal, or ⌘+Shift+T) — the skill *outputs* the exact
   commands and stops (it never deploys from inside Genie Code, which is sandboxed):
   ```bash
   cd ~/<repo-folder>
   databricks bundle validate --target client
   databricks bundle deploy   --target client
   ```

### Also install the Genie-space skill (any team may want one)
The build is free-form — your team may decide a **self-serve Genie space** over your audit/recon tables
is part of the solution. Install the community `prompt-to-genie` skill once at the workspace level (it's
a multi-file skill repo, so clone then import the whole folder):
```bash
gh repo clone sean-zhang-dbx/prompt-to-genie /tmp/prompt-to-genie
databricks workspace import-dir \
  /tmp/prompt-to-genie \
  /Workspace/.assistant/skills/prompt-to-genie --profile <profile>
```
Then in a fresh Genie Code chat say **"create a Genie space"** over `recon_summary` / your ingest audit
so a steward can ask *"which tables failed reconciliation last night?"* in plain English. See
`GENIE_CODE_PROMPTS.md` for build starter prompts.

### Fallback — manual bundle deploy
Skip the skill and configure by hand: open `databricks.yml`, fill the `client` target's
`client_catalog`, `client_schema` (writable — default `clinops_de`), `source_schema`
(read-only OMOP — default `clinops_foundation`), and `warehouse_id` (all bundle variables), then
`databricks bundle deploy --target client`.

### Then (either path)
**Open the notebooks** in your workspace (the bundle syncs `notebooks/`). Start at
**`00_START_HERE`**, set the widgets to match your bundle targets, and run the foundation check. Then
work through `01` → `05`. Each notebook `%run ./_config` so they share one catalog/schema/warehouse
and the same source tables.

> **The five notebooks are independent** — you can build them in any order. `01`→`02` form a
> natural ingest→verify pair; `03` and `04` are reusable guards you'd call *before* any ingest; `05`
> is the net-new LIVE trials feed on a Volume source (ask the presenter to start the feed first).

---

## 🔒 Ground rules (security-first customer)

- **Read-only source.** The 6 OMOP tables in `source_schema` are shared and read-only — you
  never modify them. Same for the trials landing Volume (nb 05): you read files from it, you
  never edit them. Everything you create lands in **your own** `client_schema`.
- **Everything is Unity-Catalog-scoped** — catalog/schema come from bundle variables. No
  `hive_metastore`, ever.
- **Synthetic data only.** No real PHI in this kit.
- **Config over code.** The ingest gate (nb 03) and the SLA window (nb 04) are driven by UC
  config / explicit parameters — a steward changes behavior without a deploy, and every
  decision is auditable.
- **No hardcoded secrets.** No tokens, keys, or passwords in code — use bundle variables.

---

## 🗂️ Repo layout

```
data-eng-session-starter-kit/
  README.md            ← you are here
  databricks.yml       ← DAB: UC-scoped per-team target (writable schema + read-only source)
  RUNBOOK.md           ← MENTOR build-level facilitation (Checkpoints 1–5, failure modes)
  GENIE_CODE_PROMPTS.md ← ready-to-use Genie Code build prompts (free-form; starters, not a script)
  STRETCH.md           ← "make it your own" extension ideas
  notebooks/           ← the team scaffold (00–05): pre-built plumbing + your TODOs
  reference/           ← SA-ONLY answer key (mentor reveals only if a team is stuck)
  resources/           ← the DAB job: the SLA-window-aware ingest schedule
```

## 📒 The notebook arc

| # | Notebook | What it builds | Your job? |
|---|---|---|---|
| — | `_config` | shared catalog/schema/warehouse + `fqn()`/`src()` | ✅ pre-built |
| 00 | `00_START_HERE` | overview, the value story, foundation check | ✅ read + run |
| 01 | `01_schema_evolution` | append data with a NEW column; the table evolves safely | 🛠️ wire `mergeSchema` |
| 02 | `02_row_count_reconciliation` | source↔target counts + anti-joins + `recon_summary` | 🛠️ build the recon |
| 03 | `03_restricted_table_ingest_gate` | block restricted tables from a UC allow-list | 🛠️ build the guard |
| 04 | `04_sla_job_windows` | skip the 11pm–8am window + the Jobs schedule pattern | 🛠️ build the guard |
| 05 | `05_trials_catalog_ingest` | LIVE Volume feed → Auto Loader → `VARIANT` bronze → flatten to `silver_trial_criteria` + quarantine bad records | 🛠️ build the quarantine routing |
