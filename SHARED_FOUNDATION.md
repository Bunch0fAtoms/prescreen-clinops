# 🧱 The data foundation the notebooks build on

**Goal: one governed data contract the ML pre-screen builds on.** This page is that contract. It
says exactly what data is present before you build, and what the ML notebooks produce from it.

## What the foundation provides

Standing up `foundation/` creates the six OMOP Common Data Model (CDM) tables, clean and ready to
build on:

| What | Detail |
|---|---|
| **Six OMOP CDM tables** | `person`, `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, `note`. 300 synthetic breast-cancer patients. Clean and ready to build on. |

The six tables are the seed. The ML build reads them read-only and layers its own silver and gold
tables on top, in its own writable schema.

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
| Eligible patients | **140** (109 from structured data, 31 recovered via NLP) | **70** (56 from structured data, 14 recovered via NLP) | **53** (40 from structured data, 13 recovered via NLP) |

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
- **Trials A, B, and C all live in the same seed.** Trial C (triple-negative) is simply another row in
  the ML build's own `silver_trial_criteria` table, screened by the same one rule. Adding a trial is
  adding a row, not writing code.

## The notes-only gap: why this build exists

About 60 of the 300 patients (person_ids 181-240) carry their biomarker status only in the free text
of a pathology note, not in a structured field. A SQL query over `measurement` alone silently misses
them. That gap is the reason the ML build recovers them with language-model extraction. It is the
value story the pre-screen demonstrates.

You can see the gap for yourself in the discovery step (`foundation/DISCOVERY.md`): interrogate the
six tables with Genie Code and, optionally, stand up a Genie space over them so anyone, including a
non-SQL clinical researcher, can question the data. Understand the foundation first, then build on it.

## What the ML build produces

The foundation stops at the six OMOP tables. Everything below is the ML build's own work, in its own
schema, reading the six tables read-only.

| Layer | What it produces |
|---|---|
| **Structured silver** | Biomarker pivot (HER2/ER/PR), demographics, and prior therapy, off the six OMOP tables. |
| **Gap analysis** | Classifies each patient by where their biomarker evidence lives: both structured and notes, structured-only, or notes-only. |
| **NLP extraction** | `ai_query` reads biomarker status out of `note_text`, recovering the ~60 notes-only patients. |
| **Gold pre-screen** | A data-driven `gold_trial_prescreen` (one row per patient per trial) that joins `silver_trial_criteria` with the one generic rule, plus a `biomarker_source` audit column. |
| **Genie space and app** | A self-serve Genie space over the cohort, and a coordinator/researcher app on top of the pre-screen. |

## The payoff, in numbers

When the pieces come together, the pre-screen produces one row per patient per trial and yields
**Trial A: 140 eligible, Trial B: 70, Trial C: 53**. Of the Trial A patients, **31 are found only
because language models recovered their biomarker status from pathology notes**, and NLP likewise
recovers **14 of Trial B's 70** and **13 of Trial C's 53**. Those are the patients a structured-only
filter would have missed. That is the headline, and the reason the notes-only gap matters.

## If you get stuck

The kit carries its own safety net in `reference/ANSWER_KEY.md`: the worked solution for every
build step. The build steps are plumbing-shaped on purpose, so you can reveal the mechanism early
and keep moving. The value is in the reasoning, not in typing the solution from memory.

Everything here is synthetic and Unity Catalog scoped. No patient health information.
