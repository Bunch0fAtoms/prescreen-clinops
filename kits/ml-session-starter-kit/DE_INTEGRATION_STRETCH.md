# 🔗 STRETCH GOAL: Integrate with Data Engineering's Live Trials Catalog

**This is an optional enhancement if both teams finish their core builds.**

## Context

Your pre-screen already joins your own `trial_criteria` table (Trial A and Trial B, one row per trial, a `req_*` column per condition). Meanwhile, the Data Engineering team is building a live trials catalog that:
- Ingests trial definitions from a streaming JSON feed
- Lands them in a table called `silver_trial_criteria`
- Updates automatically when new trials arrive

If you integrate with their catalog, **adding Trial C (or any new trial) requires zero code changes** - it just appears when DE's feed picks it up.

## What DE provides: `silver_trial_criteria` table

The DE team creates this table in their schema (`clinops_de` or similar):

```sql
-- Each row is one trial with its eligibility requirements
-- NULL in a req_* column means "this trial doesn't constrain that field"

trial_id                STRING       -- 'TRIAL_A', 'TRIAL_B', 'TRIAL_C'
trial_name              STRING       -- 'HER2-Positive Breast Cancer Study'
req_sex                 STRING       -- 'Female' / NULL
age_min                 INT          -- 18 / NULL
age_max                 INT          -- 75 / NULL
req_her2                STRING       -- 'Positive' / 'Negative' / NULL
req_er                  STRING       -- 'Positive' / 'Negative' / NULL
req_pr                  STRING       -- 'Positive' / 'Negative' / NULL
req_menopausal          STRING       -- 'Postmenopausal' / 'Premenopausal' / NULL
req_no_prior_anti_her2  BOOLEAN      -- TRUE (excludes) / NULL
min_ecog                INT          -- ECOG threshold from the feed / NULL (carried through, not matched)
```

## How to integrate (if DE has finished)

### Option 1: Repoint to DE's catalog (recommended if DE is done)

Point your existing generic join at their catalog instead of your own `trial_criteria`:

```sql
-- Repoint the CROSS JOIN from your own trial_criteria to DE's silver_trial_criteria:
CREATE OR REPLACE TABLE gold_trial_prescreen AS
WITH patient_profiles AS (
  -- Your existing unified patient data
  SELECT person_id, her2_status, er_status, pr_status, age, gender, ...
  FROM gold_unified_biomarker_profile ...
),
evaluated AS (
  SELECT
    p.*,
    t.trial_id,
    t.trial_name,
    -- Check each criterion (NULL means unconstrained)
    (t.req_her2 IS NULL OR p.her2_status = t.req_her2) AS ok_her2,
    (t.req_er IS NULL OR p.er_status = t.req_er) AS ok_er,
    (t.req_pr IS NULL OR p.pr_status = t.req_pr) AS ok_pr,
    (t.age_min IS NULL OR p.age >= t.age_min) AS ok_age_min,
    (t.age_max IS NULL OR p.age <= t.age_max) AS ok_age_max,
    -- ... other criteria
  FROM patient_profiles p
  CROSS JOIN ${DE_CATALOG}.clinops_de.silver_trial_criteria t
)
SELECT
  person_id,
  trial_id,
  trial_name,
  -- Patient is eligible when ALL criteria pass
  (ok_her2 AND ok_er AND ok_pr AND ok_age_min AND ok_age_max ...) AS eligible,
  -- Generate a reason
  CASE
    WHEN (ok_her2 AND ok_er AND ...) THEN 'Eligible'
    WHEN NOT ok_her2 THEN 'Excluded: HER2 status mismatch'
    WHEN NOT ok_er THEN 'Excluded: ER status mismatch'
    -- ...
  END AS reason
FROM evaluated
```

### Option 2: Union approach (safer for demo)

Keep your own trials and ADD the DE catalog:

```sql
-- Your existing own trial_criteria (Trial A and B)
WITH my_trials AS (
  SELECT 'TRIAL_A' as trial_id, 'HER2+ Study' as trial_name,
         'Positive' as req_her2, NULL as req_er, ...
  UNION ALL
  SELECT 'TRIAL_B' as trial_id, 'ER+/HER2- Study' as trial_name,
         'Negative' as req_her2, 'Positive' as req_er, ...
),
-- Union with DE's catalog if it exists
all_trials AS (
  SELECT * FROM my_trials
  UNION ALL
  SELECT * FROM ${DE_CATALOG}.clinops_de.silver_trial_criteria
  WHERE trial_id NOT IN ('TRIAL_A', 'TRIAL_B')  -- Avoid duplicates
)
-- Then CROSS JOIN with all_trials instead of my_trials
```

## When to attempt this

✅ **Try the integration when:**
- Your core ML build is complete and working (Phases 1-8 done)
- The DE team signals their `silver_trial_criteria` table is ready
- You have 15-30 minutes to test the integration

❌ **Skip it if:**
- Either team is still working on core functionality
- Time is running short for presentations
- The DE catalog isn't populated yet

## How to test if it worked

1. Check that Trial A and B still return the same counts (140 and 70 eligible)
2. Look for Trial C in your results:
   ```sql
   SELECT trial_id, COUNT(*) as eligible_count
   FROM gold_trial_prescreen
   WHERE eligible = TRUE
   GROUP BY trial_id
   ```
3. If Trial C shows up with ~53 eligible patients, the integration worked!

## The payoff statement

If you complete this integration, you can say:

> "Our pre-screen now reads from the Data Engineering team's live trials catalog. When they added Trial C to their feed, our pipeline automatically picked it up with zero code changes. We went from screening 2 trials to 3 trials just by refreshing the data."

## Fallback if DE isn't ready

No problem, your own `trial_criteria` table works fine for the demo. You can still explain the concept:

> "Our pre-screen is built to be data-driven, joining a trial_criteria table. Once the DE team's catalog is ready, we can repoint that join from our own table to their live feed, and new trials will flow through automatically."