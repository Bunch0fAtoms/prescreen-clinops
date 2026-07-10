# Genie Space: Clinical Trial Pre-Screening

Copy/paste content for the Genie space you stand up in notebook 08. Everything here runs against
the **governed Unity Catalog gold tables** your team built, no PHI, synthetic data only.

The strongest signals Genie reads, in order: (1) Unity Catalog **table and column comments**,
(2) the space **instructions**, (3) **trusted example SQL** and **join relationships**. Notebook 08
sets the comments; the rest you paste into the space. A fully built space has all three.

---

## Space configuration

| Field | Value |
|---|---|
| **Name** | `Breast Cancer Biomarker & Trial Eligibility` |
| **Description** | Natural-language pre-screening across Trial A (HER2+), Trial B (ER+/HER2−/postmenopausal), and Trial C (triple-negative), with the reason and biomarker provenance. |
| **SQL warehouse** | your `warehouse_id` (printed in nb 08) |
| **Tables** (keep it to 3) | `<catalog>.<schema>.gold_trial_prescreen` · `gold_unified_biomarker_profile` · `silver_demographics` |

> Keep the table count tight. Genie is most accurate with a small, well-described set. `gold_trial_prescreen`
> is **LONG**: one row per (`person_id`, `trial_id`), with `eligible`, `reason`, and `biomarker_source`.
> Turn on entity matching for the categorical string columns (`trial_id`, `her2_status`, `er_status`,
> `pr_status`, `menopausal_status`, `biomarker_source`, `ajcc_stage`) so Genie can match values like
> `Positive` or `Postmenopausal`.

---

## General instructions (paste into the space's Instructions panel)

```
You answer questions about breast-cancer clinical-trial PRE-SCREENING over governed Unity Catalog
gold tables. Synthetic data only, there is no PHI.

PRIMARY TABLE gold_trial_prescreen is LONG: one row per (person_id, trial_id). A patient has one row
per trial. To count DISTINCT patients use COUNT(DISTINCT person_id); to count eligible for a trial use
COUNT(*) with a trial_id filter and eligible = TRUE.

TRIALS (trial_id): A = HER2-positive; B = ER-positive / HER2-negative / postmenopausal;
C = triple-negative (ER-, PR-, HER2-). trial_name holds the full name.

ELIGIBILITY: eligible is a boolean; reason gives the plain-English explanation. A patient qualifies
when every trial criterion matches (biomarkers, age, sex, and for Trial A no prior anti-HER2 therapy).

BIOMARKER PROVENANCE is the headline story. biomarker_source = 'structured' means the biomarker came
from coded lab data. biomarker_source = 'nlp' means it was recovered from a free-text pathology note by
an AI model, so those patients are INVISIBLE to a structured-only query. Validated eligible counts:
Trial A 140 (109 structured + 31 recovered via NLP), Trial B 70 (56 + 14), Trial C 53 (40 + 13).

BIOMARKER STATUS values are the strings 'Positive', 'Negative', or 'Unknown' for her2_status,
er_status, pr_status.

When asked to "list patients", return person_id plus the relevant status/reason columns. Join
gold_trial_prescreen, gold_unified_biomarker_profile, and silver_demographics on person_id.
```

---

## Sample questions (seed these as starter prompts)

1. **How many patients are eligible for each trial?**
2. **How many Trial A-eligible patients were found only through pathology-note NLP?**
   *(the headline question, answer is 31, these patients are invisible to a structured-only query)*
3. **What is the breakdown of eligible patients by biomarker source (structured vs NLP)?**
4. **List Trial B eligible patients who are postmenopausal.**
5. **Show HER2-positive patients who are ineligible because of prior anti-HER2 therapy.**
   *(eligible by biomarker, excluded by prior treatment)*
6. **What is the age distribution of Trial A eligible patients?**

---

## Trusted example SQL (the strongest accuracy boost, save each with a plain-English title)

| Example title | SQL |
|---|---|
| *Eligible patients per trial* | `SELECT trial_id, trial_name, COUNT(*) AS eligible_patients FROM gold_trial_prescreen WHERE eligible = TRUE GROUP BY trial_id, trial_name ORDER BY trial_id` |
| *Trial A patients found only via NLP* | `SELECT COUNT(*) AS nlp_recovered_eligible FROM gold_trial_prescreen WHERE trial_id = 'A' AND eligible = TRUE AND biomarker_source = 'nlp'` |
| *Eligible breakdown by biomarker source* | `SELECT trial_id, biomarker_source, COUNT(*) AS eligible_patients FROM gold_trial_prescreen WHERE eligible = TRUE GROUP BY trial_id, biomarker_source ORDER BY trial_id, biomarker_source` |
| *HER2+ excluded by prior therapy (ineligible)* | `SELECT person_id, her2_status, prior_anti_her2, reason FROM gold_trial_prescreen WHERE trial_id = 'A' AND her2_status = 'Positive' AND prior_anti_her2 = TRUE AND eligible = FALSE ORDER BY person_id` |
| *Eligible Trial A patients with diagnosis date (join)* | `SELECT p.person_id, p.reason, d.dx_date, d.age_at_dx_years FROM gold_trial_prescreen p JOIN silver_demographics d ON p.person_id = d.person_id WHERE p.trial_id = 'A' AND p.eligible = TRUE ORDER BY d.dx_date` |

---

## Join relationships (define these so Genie can combine the tables)

All three tables join on `person_id` (many-to-one from the long pre-screen table to the per-patient tables):

- `gold_trial_prescreen.person_id` → `silver_demographics.person_id`
- `gold_trial_prescreen.person_id` → `gold_unified_biomarker_profile.person_id`

---

## Building the space programmatically (optional)

The space can be authored end to end with the Genie spaces API instead of the UI. `PATCH
/api/2.0/genie/spaces/{space_id}` takes a `serialized_space` JSON (version 2) with
`config.sample_questions`, `data_sources.tables[].column_configs`, `instructions.text_instructions`,
`instructions.example_question_sqls`, and `instructions.join_specs`. Every id-bearing list must be
sorted by `id`. This is how the reference space was built; the same content is mirrored above so you
can paste it into the UI if you prefer.

---

## Metric-view hints (optional, for a more governed semantic layer)

If your team wants standardized KPIs instead of ad-hoc counts, define a UC **metric view** over
`gold_trial_prescreen` with measures like:
- `eligible_count` = `COUNT(CASE WHEN eligible THEN 1 END)` with a dimension on `trial_id`
- `nlp_recovered_eligible` = `COUNT(CASE WHEN eligible AND biomarker_source = 'nlp' THEN 1 END)`
Point Genie at the metric view so every team gets the same definition of "eligible." (See the
`databricks-metric-views` skill, this is a stretch.)
