# 🧱 Shared foundation: what every group inherits

**Goal: one shared, governed foundation that lets all four groups build in parallel.** This page
is the contract. It says exactly what is present before the groups split, and what each group
builds from there.

## What the foundation provides

Standing up `foundation/` on Day 1 creates two things, shared and read-only for every group:

| What | Detail |
|---|---|
| **Six OMOP CDM tables** | `person`, `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, `note`. 300 synthetic breast-cancer patients. Clean and ready to build on. |
| **A live trials feed** | A presenter-controlled `land_trial_feed` task streams nested clinical-trials JSON files into a shared `trial_landing` Volume over time (clean trials, then a schema change, then bad records, then a clean heartbeat). The live feed the Data Engineering group ingests incrementally. |

The six tables are the seed. Both the Data Engineering and the Applied AI groups start from the
same six tables and build independently. Neither group waits on the other to produce a data layer,
so they run fully in parallel.

## ⭐ Clinical-trial eligibility criteria (the one card, do not re-derive)

**These are the eligibility rules the pre-screen uses. The single source of truth is the
`silver_trial_criteria` table (trials are data: one row per trial, one `req_*` column per criterion).
This card summarizes those rows so no one has to hunt for them mid-build.**

| Field | Trial A (HER2+) | Trial B (ER+/HER2−) | Trial C (triple-negative) |
|---|---|---|---|
| `req_sex` | Female | Female | Female |
| age (`age_min` to `age_max`) | 18 to 75 | 18 to 75 | 18 to 75 |
| `req_her2` | **Positive** | **Negative** | **Negative** |
| `req_er` | (unconstrained) | **Positive** | **Negative** |
| `req_pr` | (unconstrained) | (unconstrained) | **Negative** |
| `req_menopausal` | (unconstrained) | **Postmenopausal** | (unconstrained) |
| `req_no_prior_anti_her2` | **true** (excludes prior anti-HER2 therapy) | (unconstrained) | (unconstrained) |
| `min_ecog` | 1 (carried, not matched) | (unconstrained) | (unconstrained) |
| Eligible patients | **140** (109 from structured data, 31 recovered via NLP) | **70** (56 from structured data, 14 recovered via NLP) | net-new triple-negative cohort, 53 (40 structured, 13 recovered via NLP) |

**The one rule to remember:** a patient qualifies for a trial when every non-null `req_*` matches the
patient's value AND age is within range. A NULL `req_*` means the trial does not constrain that field.
One rule, every trial.

Read the fine print once, so nobody re-derives it under time pressure:
- `min_ecog` is **carried through but not matched**. The patients have no ECOG performance-status field,
  so the pre-screen shows the threshold but does not filter on it.
- `req_sex` (Female) and age (18 to 75) are **constant across all three trials** today. They still must
  match; they just do not distinguish the trials from one another.
- **Source of truth:** the rows of `silver_trial_criteria`. This card, the notebook prose, and the app
  all summarize that one table. To add or change a trial, change the data, not code.
- **Data Engineering feed nuance (so the two numbers reconcile):** the live trials feed deliberately
  re-lands a **tightened Trial B** (age ceiling 70, ECOG 2) as a "latest-wins" teaching case. The
  validated count of 70 (56 from structured data plus 14 recovered via NLP) is against the base Trial B
  (age 18 to 75), which is what the pre-screen's own
  `silver_trial_criteria` seed uses. If a team repoints the pre-screen to the DE group's catalog, Trial
  B reflects that newest record, so its criteria and count shift. That is the DE lesson, not a defect.

## How the code is packaged: one foundation bundle, plus a bundle only where a group needs one

Expect to see **three** Databricks Asset Bundles (DABs). This is intentional. The `foundation/` bundle
is deployed and run **once** to stand up the shared six tables and the trials feed. Two groups then
deploy their own bundle into their **own** schema, reading the foundation tables read-only:
**Governance** (`governance-session-starter-kit`) and **ML** (`ml-session-starter-kit`). The other two
groups build with **no bundle at all**: **Data Engineering** builds its trials-feed ingest live with
Genie Code on top of the foundation (Track 1 Structured Streaming notebook to Job, or Track 2 a
Lakeflow Declarative Pipeline), and **Admin / Genie One** works in SQL and Genie One over
`system.billing`. Both create whatever they write in their own schema from the build itself.

| Bundle | Who deploys it | When | Writes to |
|---|---|---|---|
| `foundation/` | Whoever stands up Day 1 (DE SSA shadows) | Once, before groups split | The shared foundation schema |
| `governance-session-starter-kit` | The Governance group | During the build | The Governance group's schema |
| `ml-session-starter-kit` | The ML group | During the build | The ML group's schema |
| (none) Data Engineering | Built live with Genie Code | During the build | The DE group's own schema |
| (none) Admin / Genie One | SQL and Genie One | During the build | n/a |

The split exists so the groups stay independent. A group that has a bundle deploys, redeploys, and
iterates on its own without touching the foundation or the other groups, so a mistake has a
**contained blast radius** and never disturbs the shared tables. Each `databricks.yml` asks a group for
only its own handful of values (for example, Governance needs a group name, ML needs a source schema),
which keeps setup short and relevant. The packaging mirrors the data model: one shared source everyone
reads, one writable schema per team.

## Discovery comes first

Before anyone builds, the whole room runs the discovery step in `foundation/DISCOVERY.md`. All four
groups interrogate the six tables with Genie Code and stand up a shared Genie space over them. The
point is a shared understanding of the data before anyone extends it. One thing discovery surfaces
matters for the whole day: about 60 of the 300 patients carry their biomarker status only in the
free text of a pathology note, not in a structured field. That gap motivates the Data Engineering
and Applied AI builds.

This same session doubles as the Governance group's requirements-gathering. As the room asks real
questions of the data, Governance sees which columns identify a patient and which questions imply
that one group should see more than another. That becomes the control set it applies next, so the
governance is grounded in how the room actually uses the data.

## What each group builds (not pre-built)

The foundation intentionally stops at the six tables and the live trials feed. Everything below is the
groups' own work, because building it is the point.

| Group | Builds | On top of |
|---|---|---|
| **Data Engineering** | A hardened ingest: schema evolution, row-count reconciliation, a restricted-table gate, service-level windows. Plus the live trials feed: an incremental Auto Loader ingest of the streaming Volume into `silver_trial_criteria` (with bad records quarantined), the eligibility contract the pre-screen joins against. | The six tables and the live `trial_landing` Volume. |
| **Applied AI** | Patient features, then language-model extraction that recovers the ~60 notes-only patients, then the trial pre-screen (`gold_trial_prescreen`), then a Genie space researchers can question. | The six tables directly. |
| **Governance** | The tag, classify, mask, and row-filter pattern, applied to the foundation and then re-applied to what the other groups produce. | The six tables, then everything downstream. |
| **Admin** | Cost, usage, and budget answers in plain language with Genie One. | The workspace billing system tables. |

## How the trials feed connects the groups

Trials are data, not hardcoded rules. The feed streams JSON files into the `trial_landing` Volume
over time. Clean trials arrive first, then a file re-lands Trial A with a new `min_ecog` field
(a schema change the ingest absorbs), then a few bad records arrive (a missing id, a malformed line,
a wrong-typed field). The Data Engineering group ingests the feed **incrementally with Auto Loader**,
flattens the good records to `silver_trial_criteria`, one row per trial (latest wins), where a missing
value means the trial does not constrain that field, and routes the bad records to a quarantine table
so the load never breaks.

`silver_trial_criteria` is the contract the Applied AI pre-screen joins against. Trials A and B
carry the same criteria as the reference rules, so the validated numbers hold, and Trial C
(triple-negative) is net-new. **Adding a trial is a file landing, not a code change.** One producer,
many consumers: if the Applied AI group is ready before the trials catalog is, they can read the same
Volume themselves, so this connection is a hand-off, never a hard blocker.

## The payoff, in numbers

When the pieces come together, the pre-screen produces one row per patient per trial and yields
**Trial A: 140 eligible, Trial B: 70, Trial C: 53**. Of the Trial A patients, **31 are found only
because language models recovered their biomarker status from pathology notes**, and NLP likewise
recovers **14 of Trial B's 70**. Those are the patients a structured-only filter would have missed.
That is the headline the Applied AI group demonstrates, and the reason the notes-only gap matters.

## Governance is the foundation everyone builds on

The Governance group sets its requirements in the Day 1 whole-room Genie session, then applies its
controls to the foundation the same day. On Day 2 it rotates across the Data Engineering and Applied
AI tracks, re-applying masks and row filters to the tables and models those groups compose. Every
section's output ends up governed, so the solution respects who is allowed to see what. Because the
data is synthetic, the full control set is exercised with no risk to real patient information.

Admin runs alongside on Day 1, using Genie One to answer cost and usage questions and set budget
alerts in plain language over the workspace billing system tables.

## If a group gets stuck

Each kit carries its own safety net in its `reference/ANSWER_KEY.md`: the worked solution for every
build step. The build steps are plumbing-shaped on purpose, so a facilitator can reveal the
mechanism early and keep the group moving. The value is in the reasoning, not in typing the
solution from memory.

Everything here is synthetic and Unity Catalog scoped. No PHI.
