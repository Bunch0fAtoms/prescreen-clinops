# Clinical Trial Pre-Screening (ML Reference Build)

**This repo is a runnable reference for a machine learning (ML) team building a
clinical-trial patient pre-screening solution.** The goal is a working, governed pre-screen:
take clinical data, find the patients who match a trial's criteria, and give a coordinator a
trustworthy shortlist with a plain-English reason for every decision.

The scenario is breast cancer because it is a common, well-documented oncology use case. The
deliverable is the pattern you can reuse: structured features plus language-model extraction,
joined against data-driven trial criteria, all in Unity Catalog.

It runs on synthetic data by default, so there is no patient health information at any point. When
you are ready, one switch points the same build at your own OMOP source tables.

---

## What's in this repo

| Path | What it is |
|---|---|
| `foundation/` | A Databricks Asset Bundle (a versioned, deployable unit of jobs and code). It generates six synthetic OMOP Common Data Model (CDM) tables, or no-ops so you read your real OMOP tables instead. |
| `kits/ml-session-starter-kit/` | The reference notebooks, prompts, and app the ML team runs to build the pre-screen. Start with its `README.md`. |
| `SHARED_FOUNDATION.md` | The data contract: the six tables, the eligibility criteria, and the notes-only gap the build recovers. |
| `.assistant/skills/` | The in-repo Genie Code skill that adapts the build to your workspace. |

## How to use it

1. **Stand up the foundation** (or point at your real OMOP tables). Follow `foundation/README.md`.
   It creates the six OMOP tables from synthetic data, or reads your real ones.
2. **Install the two Genie Code skills** (Step 2 below). Genie Code is the in-workspace assistant
   that writes and runs code from plain-language prompts.
3. **Run and build the ML kit.** Open `kits/ml-session-starter-kit/README.md` and follow it. Most
   of the build is driven from Genie Code. One notebook, the Hugging Face model registration, you
   run as-is.

---

## Getting set up

**Prerequisites.** A Databricks workspace with Unity Catalog, permission to create a schema and a
SQL warehouse, and the Databricks command-line interface (CLI) configured for your workspace.

**Step 1, stand up the foundation.** Follow `foundation/README.md`. This runs once and creates the
six OMOP tables the notebooks read. To use real data instead, flip the toggle described there.

**Step 2, install two Genie Code skills, once.** Genie Code finds skills only under
`/Workspace/.assistant/skills/`, so import them there one time and everyone on the team has them.
This is a **separate action from deploying the foundation**. The `bundle deploy` command syncs
code, it does not install skills.

Run both of these once in a **workspace web terminal** (it authenticates as you automatically, so
there is no profile to fill in and nothing to edit):

```bash
# 1. The adaptation skill (ships in this repo). The wildcard finds your imported
#    copy under /Workspace/Users/<you>/prescreen-clinops, so run it from anywhere.
cd /Workspace/Users/*/prescreen-clinops && databricks workspace import-dir \
  .assistant/skills/prescreen-clinops-adaptation \
  /Workspace/.assistant/skills/prescreen-clinops-adaptation
```

```bash
# 2. The Genie-space skill (community). Create a Git folder for it directly at the
#    workspace skill path, so it stays updatable from the source repo.
databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
  --path /Workspace/.assistant/skills/prompt-to-genie
```

You can also create the `prompt-to-genie` Git folder from the UI: **Workspace → Create → Git folder**,
URL `https://github.com/sean-zhang-dbx/prompt-to-genie.git`, and set the destination to
`/Workspace/.assistant/skills/prompt-to-genie`.

If you cannot write to the workspace-level path, install per-user instead at
`/Workspace/Users/<you>/.assistant/skills/…`. The two skills:

| Skill | What it does | When you use it |
|---|---|---|
| `prescreen-clinops-adaptation` (in `.assistant/skills/`) | Reads the kit you are in and fills in its `databricks.yml` for your workspace, then gives you the deploy commands. | At deploy time, and when switching to real OMOP data. |
| `prompt-to-genie` ([github.com/sean-zhang-dbx/prompt-to-genie](https://github.com/sean-zhang-dbx/prompt-to-genie)) | Builds a self-serve Genie space from your tables. | When you want a Genie space over the cohort. |

**Step 3, open the ML kit** in `kits/ml-session-starter-kit/` and follow its `README.md` and
`RUNBOOK.md`.

**Standing up a kit, just say "run in my workspace."** In a fresh Genie Code chat opened in the
kit's folder, say `run in my workspace`. The `prescreen-clinops-adaptation` skill reads that kit's
`ADAPTATION_FACTS.json`, auto-detects your workspace, catalog, schema, and warehouse, asks
synthetic-vs-real, and **writes the `client` target variables (`client_catalog`, `client_schema`,
`warehouse_id`) into `databricks.yml` for you.** You review and Accept the diff, then it hands you
the deploy commands to paste into a Web Terminal. Editing `databricks.yml` by hand is only the
fallback if you would rather not use the skill.

## How to work with Genie Code well

- Paste one prompt at a time and review what it writes before you accept it.
- Let it save its work as real notebooks and files, not scratch.
- Drive edits from the right page: notebook edits from the notebook, pipeline files from the
  pipeline editor.

The kit prompts are starters, not a script. The value is in the solution you design. If you get
stuck, the kit has a worked reference solution in its `reference/` folder.

---

## Ground rules

- **Synthetic data only by default.** Everything generated here is fake and Unity Catalog scoped.
  No patient health information is used unless you deliberately toggle to real data.
- **Unity Catalog scoped.** All tables live in your catalog and schema. Nothing uses the older
  metastore.
- **Configuration over code.** Workspace values live in `databricks.yml` and Unity Catalog config
  tables, so behavior changes without editing code.

## Synthetic today, real tomorrow

The six tables follow the OMOP Common Data Model (OMOP CDM), a public open standard. When you
are ready, flip `run_with_synthetic_data` to `no` in `foundation/databricks.yml` and point it at
your own OMOP tables. Because the tables are OMOP-conformant, the same queries run unchanged
against any OMOP source you point them at.
