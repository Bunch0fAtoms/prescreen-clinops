# 🛠️ Live Trials-Feed Ingestion · Data Engineering Session Starter Kit

**Fred Hutch onsite · Data Engineering session · built live with Genie Code**

This is a **starter build kit**, not a finished solution. The shared foundation already stood up the
hard parts for you: the 6 synthetic OMOP tables, a live clinical-trials feed, and Unity Catalog
scoping. **Your team builds one real pipeline** that turns that messy, live feed into a clean,
queryable `silver_trial_criteria` table the Applied AI group joins against, while routing bad records
to a quarantine table instead of crashing. You build it with **Genie Code**, in whichever framework
you want to learn.

> Scaffold, don't hand-hold. The starter prompts tell you *what* to build and *why*; Genie Code writes
> the code, you review each diff and Accept deliberately. If a team gets truly stuck, the facilitator
> has worked notebooks and an answer key (see `reference/` and `notebooks/`).

---

## 🎯 The outcome you are shipping

One incremental pipeline: a **live, presenter-controlled trials feed** (nested JSON dripping into a
Volume) becomes a governed, deduplicated `silver_trial_criteria` table, with bad rows quarantined and
nothing lost. You choose the framework:

- **Track 1, Spark Structured Streaming.** Auto Loader `readStream` into a VARIANT bronze, a
  `foreachBatch` MERGE to silver, scheduled as a Job.
- **Track 2, Lakeflow Declarative Pipeline (LDP).** The same tables expressed declaratively with
  streaming tables, `EXPECT` expectations, and AUTO CDC.

Both land the identical `bronze_trial_catalog` → `silver_trial_criteria` + `quarantine_trial_criteria`.
A team runs one track. Full starter prompts for both are in `GENIE_CODE_PROMPTS.md`.

### The four submitted Fred Hutch asks all live in this one pipeline

The trials feed exercises every pattern the four DE asks are about, so the team learns them in one
realistic build. Applying the same patterns to the OMOP tables separately would teach nothing new.

| # | The ask | Where it shows up in this build | FH ask |
|---|---|---|---|
| 1 | Source adds a field → the ingest must not **break**. | The **VARIANT bronze** absorbs a new criterion (e.g. `min_ecog`) with no schema change. Schema evolution handled at the source. | Chetan #15 |
| 2 | Did **every** record land? Which are **missing**? | A **reconciliation** step: for each file, did every record reach silver or quarantine? Persist `recon_summary`. | Chetan #17 |
| 3 | A **restricted** trial/field gets ingested by accident. | A **config-driven gate** reads a UC allow-list, so a steward changes behavior with no code change. | Jenn #16 |
| 4 | A job **hammers the source** during the 11pm to 8am window. | Scheduling the ingest as a **Job with an SLA-aware cron** (plus `pause_status`) keeps runs out of the blackout. | Jennifer #9 |
| 5 | Trials are **hardcoded in SQL**; a **live** feed drifts and drops bad rows. | The whole pipeline: incremental Auto Loader ingest and quarantine, latest-wins silver. | ML / Sita ask |

Asks #1 and #4 are already covered by the base build; #2 and #3 are short hardening steps you add next.
See the "Harden further" section of `GENIE_CODE_PROMPTS.md`.

> 🔗 **Both groups build in parallel off the shared foundation.** You and the Applied AI (ML) group
> both start from the 6 read-only OMOP tables plus the shared trials feed (see `../../SHARED_FOUNDATION.md`).
> Neither group waits on the other's data layer. Your cross-group contribution is the **trials catalog**:
> you ingest the live feed to `silver_trial_criteria`, and that table is the **eligibility contract the
> ML pre-screen joins against**. If the ML group gets there first, they can read the same Volume
> themselves, so it is a hand-off, never a blocker. Adding a trial becomes a file landing, not a code
> change.

---

## 🧱 What's pre-built vs. what you build

| Component | Status |
|---|---|
| 6 synthetic OMOP source tables (read-only) | ✅ **Pre-built by the foundation** |
| The live trials feed (`land_trial_feed`), staged clean-then-dirty | ✅ **Pre-built by the foundation**, the presenter starts and stages it |
| Unity Catalog scoping, your writable team schema | ✅ **You create it from the first Genie Code prompt** |
| Bronze VARIANT ingest (Auto Loader `cloudFiles`) | 🛠️ **You build** with Genie Code |
| Silver flatten, latest-wins per trial | 🛠️ **You build** |
| Quarantine routing with a reason | 🛠️ **You build** |
| Scheduling as a Job / pipeline with an SLA-aware window | 🛠️ **You build** (Prompt 3 / pipeline schedule) |
| Reconciliation, config-driven gate, continuous mode, `ai_query` on eligibility text | 🚀 **Harden further**, see `GENIE_CODE_PROMPTS.md` and `STRETCH.md` |

---

## 🚀 How to start

**There is no bundle to deploy for this kit.** The shared **foundation** (stood up once by an admin,
see `foundation/README.md`) already created the six read-only OMOP source tables and the live
trials-feed Volume. Your team builds on top of it **through Genie Code**.

1. **Confirm the foundation is up.** In your catalog you should have the six OMOP tables in the
   read-only source schema (default `clinops_foundation`) and a live trials-feed Volume at
   `/Volumes/<catalog>/clinops_foundation/trial_landing/trial_catalog/`, plus a running SQL warehouse.
   If they are not there, an admin runs the `foundation/` bundle first, and the presenter starts the
   feed.
2. **Build through Genie Code.** Open a fresh Genie Code chat and work the starter prompts in
   `GENIE_CODE_PROMPTS.md`, one at a time. Tell it your read-only source schema and a writable team
   schema (default `clinops_de`); the first prompt creates that schema. Review each diff before you
   **Accept**, and let it persist work as a real notebook (Track 1) or pipeline source (Track 2). The
   prompts are starters your team adapts, not a script.
3. **Backup path (facilitator).** If a team stalls, `notebooks/` holds worked reference versions of the
   same patterns and `reference/` holds the answer key. They are secondary to the live Genie Code
   build, not the path the team follows.

### Optional: a self-serve Genie space (any team may want one)
The build is free-form, so your team may decide a **self-serve Genie space** over your audit/recon
tables is part of the solution. Install the community `prompt-to-genie` skill once at the workspace
level as a Git folder at the skill path, so it stays updatable from source:
```bash
databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
  --path /Workspace/.assistant/skills/prompt-to-genie
```
Then in a fresh Genie Code chat say **"create a Genie space"** over `recon_summary` / your quarantine
table so a steward can ask *"which records failed to load last night, and why?"* in plain English. See
`GENIE_CODE_PROMPTS.md` for build starter prompts.

---

## 🔒 Ground rules (security-first customer)

- **Read-only source.** The 6 OMOP tables in `source_schema` and the trials landing Volume are shared
  and read-only. You read from them, you never modify them. Everything you create lands in **your own**
  `client_schema`, including the Auto Loader checkpoint (in a Volume you own).
- **Everything is Unity-Catalog-scoped.** Catalog and schema are yours; no `hive_metastore`, ever.
- **Synthetic data only.** No real PHI in this kit.
- **Config over code.** The ingest gate and the quality rules are driven by UC config / explicit
  parameters, so a steward changes behavior without a deploy and every decision is auditable.
- **No hardcoded secrets.** No tokens, keys, or passwords in code.

---

## 🗂️ Repo layout

```
data-eng-session-starter-kit/
  README.md             ← you are here
  GENIE_CODE_PROMPTS.md ← the build: Track 1 (SSS) + Track 2 (LDP) starter prompts, free-form
  RUNBOOK.md            ← MENTOR build-level facilitation (the staged feed, checkpoints, failure modes)
  STRETCH.md            ← "make it your own" extension ideas
  notebooks/            ← worked reference versions of the same patterns (facilitator backup, not the path)
  reference/            ← SA-ONLY answer key (mentor reveals only if a team is stuck)
```

There is no `databricks.yml` here: only the shared **foundation** deploys a bundle. This kit is built
live with Genie Code on top of what the foundation already stood up.
