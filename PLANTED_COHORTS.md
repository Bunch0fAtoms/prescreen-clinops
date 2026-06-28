# Planted Cohorts — Fred Hutch Clinical Trial Pre-Screening

Catalog: `<client_catalog>`
Schema: `<client_schema>`
Generated: 2025-06-15 (reference date, reproducible with seed 42)

These person_ids are **deterministically seeded**. Running `generate_omop_data.py`
with the same catalog/schema always produces the same rows for these IDs.

---

## Trial A — HER2-Positive Breast Cancer

**Eligibility criteria:**
- Breast cancer diagnosis (`condition_occurrence`)
- HER2 Positive (`measurement.measurement_source_value = 'HER2/neu'` AND `value_source_value = 'Positive'`)
- Age 18–75 at diagnosis
- **NO** prior anti-HER2 therapy (no `drug_exposure` row with `drug_source_value IN ('Trastuzumab','Pertuzumab')`)

### Eligible patients (person_ids 1–20)

| person_id | HER2 | ER | PR | Anti-HER2 prior? | Biomarker source |
|---|---|---|---|---|---|
| 1 | Positive | Negative | Negative | No | both-agree |
| 2 | Positive | Positive | Positive | No | both-agree |
| 3 | Positive | Negative | Negative | No | both-agree |
| 4 | Positive | Positive | Positive | No | both-agree |
| 5 | Positive | Negative | Negative | No | both-agree |
| 6 | Positive | Positive | Positive | No | both-agree |
| 7 | Positive | Positive | Negative | No | both-agree |
| 8 | Positive | Negative | Negative | No | both-agree |
| 9 | Positive | Positive | Positive | No | both-agree |
| 10 | Positive | Positive | Positive | No | both-agree |
| 11 | Positive | Negative | Negative | No | both-agree |
| 12 | Positive | Positive | Negative | No | both-agree |
| 13 | Positive | Negative | Negative | No | both-agree |
| 14 | Positive | Positive | Positive | No | both-agree |
| 15 | Positive | Positive | Positive | No | both-agree |
| 16 | Positive | Negative | Negative | No | both-agree |
| 17 | Positive | Positive | Positive | No | both-agree |
| 18 | Positive | Negative | Negative | No | both-agree |
| 19 | Positive | Positive | Positive | No | both-agree |
| 20 | Positive | Positive | Negative | No | both-agree |

**SQL to reproduce:**
```sql
SELECT DISTINCT m_her2.person_id
FROM <client_catalog>.<client_schema>.measurement m_her2
JOIN <client_catalog>.<client_schema>.condition_occurrence co
  ON m_her2.person_id = co.person_id
  AND co.condition_source_value = 'Malignant neoplasm of breast'
JOIN <client_catalog>.<client_schema>.person p
  ON m_her2.person_id = p.person_id
  AND (year(current_date()) - p.year_of_birth) BETWEEN 18 AND 75
WHERE m_her2.measurement_source_value = 'HER2/neu'
  AND m_her2.value_source_value = 'Positive'
  AND m_her2.person_id NOT IN (
    SELECT person_id FROM <client_catalog>.<client_schema>.drug_exposure
    WHERE drug_source_value IN ('Trastuzumab','Pertuzumab')
  )
ORDER BY person_id;
-- Expected: person_ids 1–20 (plus any incidental HER2+ patients in the general both-agree group)
```

### Known-ineligible controls (person_ids 21–30)

These patients are HER2-positive **but have prior anti-HER2 therapy** — they should NOT appear in the Trial A cohort.

| person_id | HER2 | Anti-HER2 drug | Disqualifier |
|---|---|---|---|
| 21–30 | Positive | Trastuzumab and/or Pertuzumab | Prior anti-HER2 therapy |

---

## Trial B — ER-Positive / HER2-Negative Postmenopausal

**Eligibility criteria:**
- Breast cancer diagnosis (`condition_occurrence`)
- ER Positive (`measurement_source_value = 'Estrogen receptor'` AND `value_source_value = 'Positive'`)
- HER2 Negative (`measurement_source_value = 'HER2/neu'` AND `value_source_value = 'Negative'`)
- Postmenopausal (`observation.observation_source_value = 'Menopausal status'` AND `value_source_value = 'Postmenopausal'`)
- Age 18–75 at diagnosis

### Eligible patients (person_ids 31–50)

| person_id | ER | HER2 | Menopausal status | Biomarker source |
|---|---|---|---|---|
| 31–50 | Positive | Negative | Postmenopausal | both-agree |

All 20 patients in this range have:
- ER = Positive (in `measurement`)
- HER2 = Negative (in `measurement`)
- Postmenopausal (in `observation`)
- Age 50–72 at diagnosis

**SQL to reproduce:**
```sql
SELECT DISTINCT m_er.person_id
FROM <client_catalog>.<client_schema>.measurement m_er
JOIN <client_catalog>.<client_schema>.measurement m_her2
  ON m_er.person_id = m_her2.person_id
  AND m_her2.measurement_source_value = 'HER2/neu'
  AND m_her2.value_source_value = 'Negative'
JOIN <client_catalog>.<client_schema>.observation obs
  ON m_er.person_id = obs.person_id
  AND obs.observation_source_value = 'Menopausal status'
  AND obs.value_source_value = 'Postmenopausal'
JOIN <client_catalog>.<client_schema>.condition_occurrence co
  ON m_er.person_id = co.person_id
  AND co.condition_source_value = 'Malignant neoplasm of breast'
JOIN <client_catalog>.<client_schema>.person p
  ON m_er.person_id = p.person_id
  AND (year(current_date()) - p.year_of_birth) BETWEEN 18 AND 75
WHERE m_er.measurement_source_value = 'Estrogen receptor'
  AND m_er.value_source_value = 'Positive'
ORDER BY person_id;
-- Expected: person_ids 31–50 (plus any ER+/HER2-/postmenopausal patients in the general both-agree group)
```

### Known-ineligible controls (person_ids 51–60)

| person_id | ER | HER2 | Menopausal status | Disqualifier |
|---|---|---|---|---|
| 51–55 | Positive | Negative | Premenopausal | Not postmenopausal |
| 56–60 | Negative | Negative | Mixed | ER-negative |

---

## NLP Value Story — Notes-Only Patients (person_ids 181–240)

These 60 patients have biomarker status **stated in `note.note_text`** but **absent from `measurement`**. A structured SQL query over `measurement` alone will miss them entirely.

An NLP/LLM extraction step over `note.note_text` recovers their biomarker status and expands both cohorts:

- **Notes-only patients eligible for Trial A** (HER2 Positive in note, no anti-HER2 drug): ~18 patients
- **Notes-only patients eligible for Trial B** (ER Positive + HER2 Negative in note, postmenopausal): ~15 patients

These are not pre-documented by exact person_id because the NLP extraction step is what discovers them — that is the demo's value moment.

---

## Biomarker Source Summary

| group | person_ids | `measurement` rows | note has biomarkers | Count |
|---|---|---|---|---|
| Trial A eligible | 1–20 | ✅ | ✅ | 20 |
| Trial A ineligible | 21–30 | ✅ | ✅ | 10 |
| Trial B eligible | 31–50 | ✅ | ✅ | 20 |
| Trial B ineligible | 51–60 | ✅ | ✅ | 10 |
| General both-agree | 61–180 | ✅ | ✅ | 120 |
| Notes-only | 181–240 | ❌ | ✅ | 60 |
| Structured-only | 241–300 | ✅ | ❌ / absent | 60 |
| **Total** | **1–300** | | | **300** |
