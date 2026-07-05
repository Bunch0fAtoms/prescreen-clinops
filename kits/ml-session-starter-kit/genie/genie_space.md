# Genie Space — Clinical Trial Pre-Screening

Copy/paste content for the Genie space you stand up in notebook 08. Everything here runs against
the **governed Unity Catalog gold tables** your team built — no PHI, synthetic data only.

---

## Space configuration

| Field | Value |
|---|---|
| **Name** | `Clinical Trial Pre-Screening` |
| **Description** | Ask about patient eligibility for the HER2+ (Trial A) and ER+/HER2− (Trial B) breast-cancer trials. |
| **SQL warehouse** | your `warehouse_id` (printed in nb 08) |
| **Tables** (keep it to 3) | `<catalog>.<schema>.gold_trial_prescreen` · `gold_unified_biomarker_profile` · `silver_demographics` |

> Keep the table count tight — Genie is most accurate with a small, well-described set. The column
> comments you applied in nb 08 are the primary signal Genie reads, so make sure that cell ran.

---

## General instructions (paste into the space's Instructions panel)

```
- "Eligible" for a trial means the corresponding trial_a_eligible / trial_b_eligible flag is TRUE.
- Trial A = HER2-positive cohort. Trial B = ER-positive / HER2-negative, postmenopausal cohort.
- biomarker_source = 'nlp' means the patient's biomarker status was recovered from a free-text
  pathology note by an AI model — these patients would be MISSED by a structured-data query alone.
  biomarker_source = 'structured' means it came from the measurement lab table.
- Biomarker statuses are the strings 'Positive', 'Negative', or 'Unknown'.
- When asked to "list patients," return person_id plus the relevant status / reason columns.
- This is synthetic data — there is no PHI.
```

---

## Sample questions (seed these as starter prompts)

1. **How many patients are eligible for Trial A?**
2. **List the patients eligible for Trial B who are postmenopausal.**
3. **How many Trial A–eligible patients were found only through pathology-note NLP?**
   *(the headline question — these patients are invisible to a structured SQL query)*
4. **What is the age distribution of HER2-positive patients?**
5. **Show patients who are HER2 positive but have already had anti-HER2 therapy.**
   *(the ineligible controls — eligible by biomarker, excluded by prior treatment)*
6. **List postmenopausal ER-positive patients who have not had endocrine therapy.**
7. **How many patients are eligible for Trial A vs Trial B?**
8. **What is the breakdown of patients by biomarker source (structured vs nlp)?**

---

## Trusted example SQL (the strongest accuracy boost — save 2–3 with a plain-English title)

| Example title | SQL |
|---|---|
| *Count patients eligible for Trial A* | `SELECT COUNT(*) FROM gold_trial_prescreen WHERE trial_a_eligible = TRUE` |
| *Trial A patients found only via NLP* | `SELECT COUNT(*) FROM gold_trial_prescreen WHERE trial_a_eligible = TRUE AND biomarker_source = 'nlp'` |
| *HER2+ patients already treated (ineligible)* | `SELECT person_id, trial_a_reason FROM gold_trial_prescreen WHERE her2_status = 'Positive' AND had_anti_her2_therapy = TRUE` |

After adding these, re-ask the sample questions — accuracy on the harder ones (especially the
NLP-recovery question) should jump.

---

## Metric-view hints (optional, for a more governed semantic layer)

If your team wants standardized KPIs instead of ad-hoc counts, define a UC **metric view** over
`gold_trial_prescreen` with measures like:
- `trial_a_eligible_count` = `COUNT(CASE WHEN trial_a_eligible THEN 1 END)`
- `trial_b_eligible_count` = `COUNT(CASE WHEN trial_b_eligible THEN 1 END)`
- `nlp_recovered_eligible` = `COUNT(CASE WHEN (trial_a_eligible OR trial_b_eligible) AND biomarker_source='nlp' THEN 1 END)`
with a dimension on `biomarker_source`. Point Genie at the metric view so every team gets the same
definition of "eligible." (See the `databricks-metric-views` skill — this is a stretch.)
