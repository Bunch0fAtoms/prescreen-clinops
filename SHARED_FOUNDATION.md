# 🧱 Shared foundation — what every group inherits

**Goal: one shared, governed foundation that lets all four groups build in parallel.** This page
is the contract. It says exactly what is present before the groups split, and what each group
builds from there.

## What the foundation provides

Standing up `foundation/` on Day 1 creates two things, shared and read-only for every group:

| What | Detail |
|---|---|
| **Six OMOP CDM tables** | `person`, `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, `note`. 300 synthetic breast-cancer patients. Clean and ready to build on. |
| **A trials landing feed** | A nested clinical-trials JSON feed dropped into a `trial_landing` Volume, in two waves. The raw feed the Data Engineering group ingests. |

The six tables are the seed. Both the Data Engineering and the Applied AI groups start from the
same six tables and build independently. Neither group waits on the other to produce a data layer,
so they run fully in parallel.

## Discovery comes first

Before either group builds, both run the discovery step in `foundation/DISCOVERY.md`. They
interrogate the six tables with Genie Code and, optionally, stand up a Genie space over them. The
point is a shared understanding of the data before anyone extends it. One thing discovery surfaces
matters for the whole day: about 60 of the 300 patients carry their biomarker status only in the
free text of a pathology note, not in a structured field. That gap motivates both builds.

## What each group builds (not pre-built)

The foundation intentionally stops at the six tables and the trials feed. Everything below is the
groups' own work, because building it is the point.

| Group | Builds | On top of |
|---|---|---|
| **Data Engineering** | A hardened ingest: schema evolution, row-count reconciliation, a restricted-table gate, service-level windows. Plus the trials catalog: the Volume feed flattened to `silver_trial_criteria`, the eligibility contract the pre-screen joins against. | The six tables and the `trial_landing` Volume. |
| **Applied AI** | Patient features, then language-model extraction that recovers the ~60 notes-only patients, then the trial pre-screen (`gold_trial_prescreen`), then a Genie space researchers can question. | The six tables directly. |
| **Governance** | The tag, classify, mask, and row-filter pattern, applied to the foundation and then re-applied to what the other groups produce. | The six tables, then everything downstream. |
| **Admin** | Cost, usage, and budget answers in plain language with Genie One. | The workspace billing system tables. |

## How the trials feed connects the groups

Trials are data, not hardcoded rules. The feed lands as JSON in the `trial_landing` Volume in two
waves. Wave 2 re-lands Trial A with a new `min_ecog` field, so the Data Engineering ingest has to
handle a schema change without breaking or dropping rows. The Data Engineering group flattens the
feed to `silver_trial_criteria`, one row per trial, where a missing value means the trial does not
constrain that field.

`silver_trial_criteria` is the contract the Applied AI pre-screen joins against. Trials A and B
carry the same criteria as the reference rules, so the validated numbers hold, and Trial C
(triple-negative) is net-new. **Adding a trial is dropping a file, not a code change.** If the
Applied AI group is ready before the trials catalog is, they can flatten the same Volume
themselves, so this connection is a hand-off, never a hard blocker.

## The payoff, in numbers

When the pieces come together, the pre-screen produces one row per patient per trial and yields
**Trial A: 140 eligible, Trial B: 56, Trial C: 53**. Of the Trial A patients, **31 are found only
because language models recovered their biomarker status from pathology notes.** Those 31 are the
patients a structured-only filter would have missed. That is the headline the Applied AI group
demonstrates, and the reason the notes-only gap matters.

## Governance is the spine

The Governance group applies its controls to the foundation on Day 1, then rotates across the
Data Engineering and Applied AI tracks, re-applying masks and row filters to the tables and models
they compose. Every section's output ends up governed, so the solution respects who is allowed to
see what. Because the data is synthetic, the full control set is exercised with no risk to real
patient information.

## If a group gets stuck

Each kit carries its own safety net in its `reference/ANSWER_KEY.md`: the worked solution for every
build step. The build steps are plumbing-shaped on purpose, so a facilitator can reveal the
mechanism early and keep the group moving. The value is in the reasoning, not in typing the
solution from memory.

Everything here is synthetic and Unity Catalog scoped. No PHI.
