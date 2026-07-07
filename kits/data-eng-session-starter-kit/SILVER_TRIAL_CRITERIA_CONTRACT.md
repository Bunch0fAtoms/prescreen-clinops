# 📋 silver_trial_criteria Table Contract

**CRITICAL: This is the exact table structure the Applied AI team expects. Column names and types must match EXACTLY.**

## What this table is

`silver_trial_criteria` is the clinical trials eligibility catalog that the Applied AI pre-screen joins against. Each row represents one trial with its eligibility requirements. When a patient's profile is evaluated, the pre-screen checks if they meet ALL non-null requirements for each trial.

## The exact schema you must produce

```sql
CREATE OR REPLACE TABLE silver_trial_criteria (
  -- Core identifiers
  trial_id                STRING NOT NULL,    -- Unique trial identifier (dedup key)
  trial_name              STRING,              -- Human-readable trial name
  status                  STRING,              -- Trial status (e.g., "recruiting")

  -- Eligibility requirements (NULL = trial doesn't constrain this field)
  req_sex                 STRING,              -- "Female" / "Male" / NULL
  age_min                 INT,                 -- Minimum age in years / NULL
  age_max                 INT,                 -- Maximum age in years / NULL
  req_her2                STRING,              -- "Positive" / "Negative" / NULL
  req_er                  STRING,              -- "Positive" / "Negative" / NULL
  req_pr                  STRING,              -- "Positive" / "Negative" / NULL
  req_menopausal          STRING,              -- "Postmenopausal" / "Premenopausal" / NULL (pass the feed value through unchanged)
  req_no_prior_anti_her2  BOOLEAN,             -- TRUE = excludes prior HER2 therapy / NULL
  min_ecog                INT,                 -- ECOG threshold from the feed / NULL (carried through; the pre-screen does not match on it yet)

  -- Metadata
  eligibility_text        STRING,              -- Free-text eligibility description
  feed_version            INT,                 -- Version from the feed
  load_ts                 TIMESTAMP            -- When this record was loaded
)
COMMENT = 'Flattened, join-ready trial eligibility criteria (latest wins per trial_id). NULL in a req_* column means the trial does not constrain that field.';
```

## Critical field mappings from source JSON

The trials feed has nested JSON. Here's how you must map it:

| Source JSON Path | → | Target Column | Notes |
|---|---|---|---|
| `trial_id` | → | `trial_id` | Direct map |
| `title` | → | `trial_name` | **Rename to trial_name** |
| `status` | → | `status` | Direct map |
| `eligibility.sex` | → | `req_sex` | **Prefix with req_** |
| `eligibility.min_age_years` | → | `age_min` | **Rename** |
| `eligibility.max_age_years` | → | `age_max` | **Rename** |
| `eligibility.her2_status` | → | `req_her2` | **Prefix with req_** |
| `eligibility.er_status` | → | `req_er` | **Prefix with req_** |
| `eligibility.pr_status` | → | `req_pr` | **Prefix with req_** |
| `eligibility.menopausal_status` | → | `req_menopausal` | **Prefix with req_** |
| `eligibility.no_prior_anti_her2` | → | `req_no_prior_anti_her2` | **Prefix with req_** |
| `eligibility.min_ecog` | → | `min_ecog` | Direct map |
| `eligibility_text` | → | `eligibility_text` | Direct map |
| `feed_version` | → | `feed_version` | Direct map |
| `load_ts` | → | `load_ts` | Direct map |

## Business rules

1. **Latest wins per trial_id**: If the same trial lands multiple times, keep only the newest record by `load_ts`
2. **NULL semantics**: NULL in any requirement field means "this trial does not filter on this criterion"
3. **All fields are nullable except trial_id**: Missing fields in source JSON should become NULL, not fail the pipeline

## Example records to validate against

After building, your table should contain records like these:

```sql
-- Trial A: HER2+ breast cancer trial
trial_id: 'TRIAL_A'
trial_name: 'HER2-Positive Breast Cancer Study'
req_sex: 'Female'
age_min: 18
age_max: 75
req_her2: 'Positive'
req_er: NULL                    -- Doesn't care about ER
req_pr: NULL                    -- Doesn't care about PR
req_menopausal: NULL            -- Doesn't care about menopausal status
req_no_prior_anti_her2: TRUE   -- Excludes prior HER2 therapy
min_ecog: NULL                  -- No ECOG requirement

-- Trial B: ER+/HER2- postmenopausal trial
trial_id: 'TRIAL_B'
trial_name: 'ER-Positive Postmenopausal Study'
req_sex: 'Female'
age_min: 18
age_max: 75
req_her2: 'Negative'
req_er: 'Positive'
req_pr: NULL                    -- Doesn't care about PR
req_menopausal: 'Postmenopausal'  -- Requires postmenopausal (exact feed value; ML joins on equality)
req_no_prior_anti_her2: NULL   -- Doesn't care about prior therapy
min_ecog: NULL

-- Trial C (if it arrives): Triple-negative trial
trial_id: 'TRIAL_C'
trial_name: 'Triple-Negative Breast Cancer Study'
req_sex: 'Female'
age_min: 18
age_max: NULL                  -- No upper age limit
req_her2: 'Negative'
req_er: 'Negative'
req_pr: 'Negative'
req_menopausal: NULL
req_no_prior_anti_her2: NULL
min_ecog: NULL                  -- Feed's triple-negative trial sets no ECOG; carried through, not matched
```

## How the ML team will use this

The Applied AI team's pre-screen will:
1. JOIN patient profiles against this table
2. Check if each patient meets ALL non-null requirements for each trial
3. Generate a `gold_trial_prescreen` table with eligible/not-eligible and a reason

Example of their join logic:
```sql
-- A patient qualifies for a trial when ALL non-null requirements match
SELECT
  p.person_id,
  t.trial_id,
  CASE
    WHEN (t.req_her2 IS NULL OR p.her2_status = t.req_her2)
     AND (t.req_er IS NULL OR p.er_status = t.req_er)
     AND (t.req_pr IS NULL OR p.pr_status = t.req_pr)
     AND (t.age_min IS NULL OR p.age >= t.age_min)
     AND (t.age_max IS NULL OR p.age <= t.age_max)
     AND ... -- other conditions
    THEN 'Eligible'
    ELSE 'Not Eligible'
  END as eligibility
FROM patient_profiles p
CROSS JOIN silver_trial_criteria t
```

## Success criteria

✅ Your `silver_trial_criteria` table is correct when:
1. Column names match this contract EXACTLY (especially the `req_*` prefixes)
2. Latest-wins deduplication works (newest `load_ts` per `trial_id`)
3. New trials that land in the feed automatically appear after pipeline refresh
4. Bad records go to quarantine, not into this table
5. The Applied AI pre-screen can join against it without column name errors