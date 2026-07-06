# Fred Hutch — Clinical Trial Pre-Screening Onsite

**This repo is everything your team needs to run the two-day onsite.** The goal is a working
clinical-trial patient pre-screening solution, built by your team, on your workspace, using
synthetic data that matches your real OMOP schema. You build it, you own it, and each group
presents its part.

The scenario is breast cancer because it maps to a real Fred Hutch need, but the deliverable is
the pattern: take clinical data, find the patients who match a trial's criteria, and give a
coordinator a trustworthy, governed shortlist.

---

## How the two days flow

**One shared foundation on Day 1, real building both days, and the whole room together on Day 2.**
By the end you have a working, governed pre-screening solution that your team built and owns.

1. **Day 1, whole room: stand up the foundation.** Run the `foundation/` bundle once. It creates
   six shared OMOP tables and lands a clinical-trials feed. See `foundation/README.md`.
2. **Day 1, whole room: discovery, and Governance sets its requirements.** Everyone interrogates the
   same six tables with Genie Code, and the whole room stands up a shared Genie space over them, so
   the build is grounded in the data. This same session doubles as the Governance group's
   requirements-gathering. As the room asks real questions of the data, Governance sees which fields
   are sensitive and who needs to see what, and captures that as the controls it will apply. See
   `foundation/DISCOVERY.md`.
3. **Day 1: Governance and Admin start building.** Governance turns the requirements it just captured
   into real column masks and row filters on the shared tables. Admin uses Genie One to answer cost
   and usage questions and set budget alerts, all in plain language. Both groups walk away from Day 1
   with a working result in hand.
4. **Day 2: Data Engineering and Applied AI build, with the whole room together.** These two groups
   design and build their sections on Day 2, grounded in what Day 1 discovery taught them. Governance
   rotates across both, re-applying its controls to the new tables and models as they appear. Everyone
   is in the room, so groups compare notes and hand work across.
5. **Day 2: everyone presents.** Each group shows what it built. Four sections, one governed
   solution, built and owned by your team.

## The four sections

Each kit is self-contained: a runbook, ready-to-adapt Genie Code prompts, pre-built plumbing,
open build steps, and an answer key for the facilitator.

| Section | Kit | What the group builds |
|---|---|---|
| **Governance** | `kits/governance-session-starter-kit/` | Tag and classify sensitive data, apply column masks and row filters, search for identifiers, and govern the data used for artificial intelligence (AI). This is the spine the other sections inherit. |
| **Data Engineering** | `kits/data-eng-session-starter-kit/` | Harden the ingest of the six tables: absorb schema changes, reconcile row counts, gate restricted tables, respect service-level windows, and bring in the net-new trials feed from the Volume. |
| **Applied AI** | `kits/ml-session-starter-kit/` | Build the patient features, recover notes-only patients with language models, produce the trial pre-screen, and stand up a Genie space clinical researchers can question in plain English. |
| **Admin** | `kits/admin-session-starter-kit/` | Use Genie One to answer cost and usage questions and set budget alerts, in plain language over the billing system tables. |

## Governance is the spine

The Governance group sets its requirements in the Day 1 whole-room Genie session. Watching what the
room asks of the data shows what is sensitive and who should see it, and that becomes the control
set. The group then applies the tag, classify, mask, and row-filter pattern to the shared tables on
Day 1, then re-applies it to the tables and models the other groups produce as they build. The
result is that every section's work respects who is allowed to see what. Because the data is
synthetic, you exercise the full control set with no risk to real patient information.

---

## Getting set up

**Prerequisites.** A Databricks workspace with Unity Catalog, permission to create a schema and a
SQL warehouse, and the Databricks command-line interface (CLI) configured for your workspace.

**Step 1 — stand up the foundation.** Follow `foundation/README.md`. This is the only thing that
must run before the groups split.

**Step 2 — a workspace admin installs two Genie Code skills, once, for everyone.** Genie Code is the
in-workspace assistant that writes and runs code from plain-language prompts. It finds skills only
under `/Workspace/.assistant/skills/`, so an admin imports them there one time and every builder then
has them. This is a **separate action from deploying a kit** — `bundle deploy` syncs a kit's code, it
does not install skills.

Run both of these once in a **workspace web terminal** (it authenticates as you automatically, so
there is no profile to fill in and nothing to edit):

```bash
# 1. The adaptation skill (ships in this repo). The wildcard finds your imported
#    copy under /Workspace/Users/<you>/prescreen-clinops, so run it from anywhere.
cd /Workspace/Users/*/prescreen-clinops && databricks workspace import-dir \
  .assistant/skills/fred-hutch-onsite-adaptation \
  /Workspace/.assistant/skills/fred-hutch-onsite-adaptation
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

| Skill | What it does | Who uses it |
|---|---|---|
| `fred-hutch-onsite-adaptation` (in `.assistant/skills/`) | Reads the kit you are in and fills in its `databricks.yml` for your workspace, then gives you the deploy commands. | Every group at deploy time. |
| `prompt-to-genie` ([github.com/sean-zhang-dbx/prompt-to-genie](https://github.com/sean-zhang-dbx/prompt-to-genie)) | Builds a self-serve Genie space from your tables. | Any group that wants a Genie space. |

**Step 3 — each group opens its kit** in `kits/` and follows that kit's `README.md` and
`RUNBOOK.md`.

**Standing up a kit — just say "run in my workspace."** In a fresh Genie Code chat opened in the
kit's folder, say `run in my workspace`. The `fred-hutch-onsite-adaptation` skill reads that kit's
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

The kit prompts are starters, not a script. The value is in the solution your group designs. If a
group gets stuck, each kit has an answer key in its `reference/` folder.

---

## Ground rules

- **Synthetic data only.** Everything generated here is fake and Unity Catalog scoped. No patient
  health information is used at any point.
- **Unity Catalog scoped.** All tables live in your catalog and schema. Nothing uses the legacy
  metastore.
- **Configuration over code.** Workspace values live in `databricks.yml` and Unity Catalog config
  tables, so behavior changes without editing code.

## Synthetic today, real tomorrow

The six tables match the column names and types of your real `curated_omop.omop` schema. When you
are ready, flip `run_with_synthetic_data` to `no` in `foundation/databricks.yml` and point it at
your real tables. The table names are identical, so the solution you built carries straight over.
