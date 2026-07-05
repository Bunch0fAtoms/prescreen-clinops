# 🧱 Foundation — stand this up first, on Day 1

**Goal: create the one shared foundation every group builds on.** Run this once, in the
whole-room block at the start, before the groups split. It produces two things:

1. **Six synthetic OMOP CDM tables** — 300 breast-cancer patients across `person`,
   `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, and `note`. These are
   clean, read-only, and shared. Both the Data Engineering and the Applied AI groups start from
   the same six tables.
2. **A clinical-trials JSON feed** landed into a `trial_landing` Volume. This is the net-new feed
   the Data Engineering group ingests during their section.

The six tables match the column names and types of Fred Hutch's real `curated_omop.omop` schema,
so moving from synthetic to real data later is a configuration change, not a rewrite.

## How to stand it up

The foundation ships as a Databricks Asset Bundle (a bundle is a versioned, deployable unit of
jobs and code). Fill in your workspace values in `databricks.yml`, then deploy and run:

```bash
cd foundation
# edit databricks.yml: set client_catalog, client_schema, warehouse_id (or use the skill below)
databricks bundle deploy --target client
databricks bundle run foundation_setup_job --target client
```

The job has two tasks. `generate_omop_data` builds the six tables. `land_trial_feed` drops the
trials JSON into the Volume. Both are reproducible: a fixed random seed means every run produces
the same 300 patients.

**Let Genie Code fill in your workspace values.** The `fred-hutch-onsite-adaptation` skill (in
`../.assistant/skills/`) reads your bundle and writes the `databricks.yml` variables for you. A
workspace admin installs it once, for everyone — this is separate from deploying the bundle:

```bash
databricks workspace import-dir \
  ../.assistant/skills/fred-hutch-onsite-adaptation \
  /Workspace/.assistant/skills/fred-hutch-onsite-adaptation --profile <profile>
```

Then open Genie Code and ask: **"set up and run the foundation in my workspace."** See the repo
`README.md` (Step 2) for the full install note and the per-user fallback.

## Synthetic today, real tomorrow

`databricks.yml` has a `run_with_synthetic_data` switch. Leave it `yes` for the onsite. Set it to
`no` and point `source_catalog` / `source_schema` at your real OMOP tables when you are ready. The
six table names are identical either way, so nothing downstream changes.

## Then: discovery, before building

Once the foundation is up, both groups run the discovery step in `DISCOVERY.md`: interrogate the
six tables with Genie Code and, optionally, stand up a discovery Genie space (`genie/`) so anyone,
including a non-SQL clinical researcher, can question the data. Understand the foundation first,
then build on it.

## What's here

| Path | What it is |
|---|---|
| `databricks.yml` | The bundle. Set your catalog, schema, and warehouse here. |
| `resources/foundation_job.yml` | The two-task setup job (OMOP tables + trials feed). |
| `src/data_generation/generate_omop_data.py` | Builds the 6 OMOP CDM tables. |
| `src/data_generation/generate_trial_feed.py` | Lands the trials JSON feed into the Volume. |
| `DISCOVERY.md` | Shared data-discovery prompts both groups run first. |
| `genie/genie_space.md` | How to stand up a discovery Genie space over the 6 tables. |
| `PLANTED_COHORTS.md` | Which synthetic patients are clearly eligible or ineligible, and why. |

Everything here is synthetic and Unity Catalog scoped. No PHI.
