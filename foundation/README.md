# 🧱 Foundation, stand this up first

**Goal: create the data foundation the ML pre-screen builds on.** Run this once. It produces the
six synthetic OMOP Common Data Model (CDM) tables, 300 breast-cancer patients across `person`,
`condition_occurrence`, `measurement`, `observation`, `drug_exposure`, and `note`. These are clean,
read-only, and shared. The ML notebooks read them and build on top.

The six tables follow the OMOP Common Data Model (OMOP CDM), a public open standard, so moving from
synthetic to real data later is a configuration change, not a rewrite. Because the tables are
OMOP-conformant, the same queries run unchanged against any OMOP source you point them at.

One column is an exception. The `person` table includes a synthetic high-profile / VIP flag,
`is_high_profile`, added as a target for the governance row-filter demo. A standard OMOP source
does not have this column. When you switch to real data, the adaptation skill removes references to
it from the downstream code it adapts, so nothing breaks. If your OMOP source has its own
high-profile indicator, the skill can point the row filter at that instead.

## How to stand it up

The foundation ships as a Databricks Asset Bundle (a bundle is a versioned, deployable unit of
jobs and code). Fill in your workspace values in `databricks.yml`, then deploy and run.

**In the workspace (no command line):**

1. Open `foundation/databricks.yml` in your workspace. The target selector at the top shows `client`.
2. Under `targets: client: variables:`, replace the three placeholders with your real values:
   - `client_catalog` → your Unity Catalog catalog (e.g. `main`)
   - `client_schema` → a schema name (default `clinops_foundation` is fine)
   - `warehouse_id` → your SQL Warehouse ID
3. **Save the file (Cmd/Ctrl+S) before deploying.** The Deploy button reads the file on disk, not
   your unsaved edits. If you deploy without saving, the job runs with the `<your_catalog>`
   placeholder and stops with a clear "set your real value, SAVE, then Deploy again" message.
4. Click **Deploy** (the rocket icon), target `client`.
5. Open the deployed **foundation_setup_job** in Jobs and click **Run now**.

**Or from the command line:**

```bash
cd foundation
# edit databricks.yml: set client_catalog, client_schema, warehouse_id (or use the skill below)
databricks bundle deploy --target client
databricks bundle run foundation_setup_job --target client
```

The job has one task, `generate_omop_data`, which builds the six tables. It is reproducible: a
fixed random seed (42) means every run produces the same 300 patients.

**Deploy to a shared team folder.** Deploy the foundation to a folder the ML team shares, so
everyone reads the same tables. The `client` target deploys the bundle under a shared path (a
sibling of any Git folder, not the deployer's personal home). One person runs this setup once, and
the team reads the result. The deployed code and files sit under that target's `files/` folder.

**Install the adaptation skill so Genie Code builds well.** The `prescreen-clinops-adaptation` skill
(in `.assistant/skills/`) is not a value-filler. It gives Genie Code the context to set up and run the
foundation cleanly the first time, and when you are ready to switch from synthetic to real OMOP data
(the `run_with_synthetic_data: no` toggle), it tells Genie Code exactly how to adapt. A workspace admin
installs it once, for everyone, separate from deploying the bundle:

Run this once in a **workspace web terminal** (it authenticates as you, nothing to edit); point it at
your imported copy of the repo:

```bash
databricks workspace import-dir \
  .assistant/skills/prescreen-clinops-adaptation \
  /Workspace/.assistant/skills/prescreen-clinops-adaptation
```

Then open Genie Code and ask: **"set up and run the foundation in my workspace."** See the repo
`README.md` (Step 2) for the full install note and the per-user fallback.

The admin also installs a second, community skill, `prompt-to-genie`, which builds the optional
discovery Genie space described below (see `genie/genie_space.md`). Create it as a Git folder at the
workspace skill path so it stays updatable from source:

```bash
databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
  --path /Workspace/.assistant/skills/prompt-to-genie
```

## Synthetic today, real tomorrow

`databricks.yml` has a `run_with_synthetic_data` switch. Leave it `yes` to run on synthetic data.
Set it to `no` and point `source_catalog` / `source_schema` at your real OMOP tables when you are
ready. The six table names are identical either way, so nothing downstream changes.

## Then: discovery, before building

Once the foundation is up, run the discovery step in `DISCOVERY.md`: interrogate the six tables with
Genie Code and, optionally, stand up a discovery Genie space (`genie/`) so anyone, including a
non-SQL clinical researcher, can question the data. Understand the foundation first, then build on it.

## What's here

| Path | What it is |
|---|---|
| `databricks.yml` | The bundle. Set your catalog, schema, and warehouse here. |
| `resources/foundation_job.yml` | The one-task setup job (generates the six OMOP tables). |
| `src/data_generation/generate_omop_data.py` | Builds the 6 OMOP CDM tables. |
| `DISCOVERY.md` | Data-discovery prompts the team runs first. |
| `genie/genie_space.md` | How to stand up a discovery Genie space over the 6 tables. |
| `PLANTED_COHORTS.md` | Which synthetic patients are clearly eligible or ineligible, and why. |

Everything here is synthetic and Unity Catalog scoped. No patient health information.
