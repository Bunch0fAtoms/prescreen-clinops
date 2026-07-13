# 🔑 Worked Reference Solution

> **The worked reference solution.** Fall back to a snippet if a team is genuinely stuck. Lean on it
> late for the learnable core, and early for plumbing or anything PHI/security-sensitive. The
> **complete, runnable solution** is the original working notebook series (referenced per item below);
> these are the intended approaches + the gotchas so you can unblock without hunting.

The full solution notebooks (the finished build this kit was decomposed from) live in
`../completed_notebooks/` (`00_START_HERE.ipynb` through `08_genie_space_setup.ipynb`), pre-run with their outputs. Point there for the complete solution.

---

## NB 01: planted-cohort validation SQL (light TODO)

**Intended Trial A count** (structured baseline):
```sql
SELECT COUNT(DISTINCT m.person_id) AS trial_a_eligible
FROM measurement m
JOIN condition_occurrence co
  ON m.person_id = co.person_id AND co.condition_source_value = 'Malignant neoplasm of breast'
WHERE m.measurement_source_value = 'HER2/neu' AND m.value_source_value = 'Positive'
  AND m.person_id NOT IN (
    SELECT person_id FROM drug_exposure WHERE drug_source_value IN ('Trastuzumab','Pertuzumab'));
```
**Trial B count:** self-join `measurement` (ER alias + HER2 alias) and join `observation` for
`Menopausal status = 'Postmenopausal'`. See nb 01 source cells "Trial A/Trial B".
- **Expected:** ≥ 20 each (person 1 to 20 / 31 to 50 guaranteed; incidental matches are fine, don't panic).
- **Gotcha:** teams may forget the `NOT IN (anti-HER2)` exclusion → count comes back too high; that's
  the teaching moment for the ineligible controls (person 21 to 30).

## NB 02: `silver_biomarker_profile` pivot (GUIDED TODO)

**Intended logic** (same in the pipeline source and the run-it-now cell):
```sql
WITH biomarkers AS (
  SELECT person_id,
    MAX(CASE WHEN measurement_source_value = 'HER2/neu'               THEN value_source_value END) AS her2_status,
    MAX(CASE WHEN measurement_source_value = 'Estrogen receptor'      THEN value_source_value END) AS er_status,
    MAX(CASE WHEN measurement_source_value = 'Progesterone receptor'  THEN value_source_value END) AS pr_status
  FROM measurement
  WHERE measurement_source_value IN ('HER2/neu','Estrogen receptor','Progesterone receptor')
  GROUP BY person_id)
SELECT person_id, her2_status, er_status, pr_status FROM biomarkers;
```
- **Why MAX(CASE…):** classic long→wide pivot; `MAX` collapses the per-marker rows into one.
- **Gotcha:** exact `measurement_source_value` strings matter (`'HER2/neu'`, not `'HER2'`). The
  worked examples (`silver_prior_therapy`, `silver_demographics`) already show the pattern.
- **Gotcha (pipeline):** in the `.sql` file, sources are `${source_catalog}.${source_schema}.measurement`;
  the run-it-now cell uses the bare name. Don't mix them up.

## NB 03: biomarker-evidence classification (light TODO)

Two `WITH` sets (`has_struct`, `has_note`), LEFT JOIN `person` to both, `CASE` on which side is NULL.
Full query in nb 03 source. **Expected:** both ≈ 180, notes-only ≈ 60, structured-only ≈ 60.

## NB 04: `ai_query` NLP extraction (🧠 SIGNPOSTED, the GenAI core)

**Intended single-note call:**
```sql
SELECT person_id, extracted.her2_status, extracted.er_status, extracted.pr_status, note_text
FROM (
  SELECT person_id, note_text,
    from_json(
      ai_query('databricks-claude-haiku-4-5',
        'Extract the HER2, ER (estrogen receptor), and PR (progesterone receptor) status from this '
        || 'breast cancer pathology report. Respond with exactly one of Positive, Negative, or Unknown '
        || 'for each. Use Unknown if equivocal or not stated. Report: ' || note_text,
        responseFormat => 'STRUCT<result:STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>>'),
      'STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>') AS extracted
  FROM note WHERE note_source_value = 'PATHOLOGY_REPORT' LIMIT 1);
```
Then `CREATE OR REPLACE TABLE silver_nlp_biomarkers AS …` (same call, no LIMIT, add
`'nlp' AS biomarker_source`).
- **⚠ THE #1 GOTCHA (reveal early, it's plumbing, not the lesson):** without `responseFormat`, the
  model wraps output in ```` ```json … ``` ```` fences and `from_json` returns **NULL for every row**.
  The whole column comes back empty and teams think the model failed. The fix is the
  `responseFormat` arg. The DDL form needs the single-top-field `STRUCT<result:STRUCT<…>>` wrapper;
  `from_json` parses the flat keys. This is the bug the original build hit. Give teams the two
  response shapes (they're already in the nb cheat-sheet) and let them write the prompt.
- **Expected:** silver_nlp_biomarkers = 240 rows, all 60 notes-only (181 to 240) recovered, ~100% fill.
- **Note:** this is the team's learnable "aha". Don't reveal the prompt wording; do reveal the
  `responseFormat` mechanic if they're stuck (it's plumbing).

## NB 05: ClinicalBERT note embeddings → UC (PRE-BUILT, optional)

Fully written. **This is the bring-your-own-model governance story, NOT the extraction path.** It
registers `Bio_ClinicalBERT`'s base `AutoModel` encoder as an MLflow pyfunc (mean-pooled 768-dim
embeddings), scores every pathology note in Spark via `spark_udf`, writes
`silver_clinicalbert_note_embeddings`, and closes with a cosine-similarity demo (cohort discovery).
Model registers as `fqn('clinicalbert_note_embedder')`.

**Why embeddings, not cloze/classification:** Bio_ClinicalBERT was never fine-tuned to call HER2/ER/PR;
so classifying with it is unreliable AND slow (the earlier masked-LM cloze approach hung ~5h). `ai_query`
(nb 04) owns accurate extraction; ClinicalBERT does what it's actually good at, representations.

**Nothing downstream depends on this notebook.** nb 06 fuses `silver_biomarker_profile` (nb 02) +
`silver_nlp_biomarkers` (nb 04). If HF download/egress fails or serving isn't approved by the hard stop,
**skip to nb 06**. The gold path is unaffected; the embeddings are an additive cohort-discovery primitive.
Gotchas: needs serverless / outbound internet for the HF pull; `save_pretrained(safe_serialization=False)`
(pytorch_model.bin) avoids the executor-side "SafetensorError: header too large" on `spark_udf` load;
`predict()` returns a 2-D float32 ndarray so `result_type="array<float>"` coerces cleanly.

## NB 06: gold fusion + eligibility (GUIDED TODO)

**Unified profile,** FULL OUTER JOIN + COALESCE (structured wins) + source CASE:
```sql
SELECT COALESCE(s.person_id, n.person_id) AS person_id,
  COALESCE(s.her2_status, n.her2_status) AS her2_status,
  COALESCE(s.er_status, n.er_status)     AS er_status,
  COALESCE(s.pr_status, n.pr_status)     AS pr_status,
  CASE WHEN s.person_id IS NOT NULL THEN 'structured' ELSE 'nlp' END AS biomarker_source
FROM silver_biomarker_profile s FULL OUTER JOIN silver_nlp_biomarkers n ON s.person_id = n.person_id;
```
**Eligibility booleans** (the `joined` CTE is given in the notebook):
```sql
(her2_status = 'Positive' AND age_at_dx_years BETWEEN 18 AND 75 AND had_anti_her2_therapy = false) AS trial_a_eligible,
(er_status = 'Positive' AND her2_status = 'Negative' AND menopausal_status = 'Postmenopausal'
   AND age_at_dx_years BETWEEN 18 AND 75) AS trial_b_eligible,
```
Reasons are a `CASE` returning `'Eligible: …'` (interpolate `biomarker_source`) else the failed
criterion. Full CASE blocks in nb 06 source.
- **Gotcha:** use FULL OUTER + COALESCE, **not** UNION (union double-rows the "both" patients).
- **Gotcha:** `COALESCE(t.had_anti_her2_therapy, false)`, patients with no therapy row are NULL, not
  false; without the COALESCE the boolean goes NULL and they drop out of Trial A.
- **Payoff:** eligible cohort split by source shows the `'nlp'` patients SQL-only would have missed.

## NB 07: MLflow eval (🧠 SIGNPOSTED)

Two TODOs inside `run_config()`:
1. **Scoring query:** one `ai_query('{model}', '{safe_prompt}' || '\n\nReport:\n' || note_text,
   responseFormat => 'STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>')` over the
   goldset; alias predicted columns `pred_her2/pred_er/pred_pr`. (Note: here the eval `responseFormat`
   uses the flat 3-field form, no `result` wrapper, because there's no `from_json` step. `ai_query`
   returns a struct directly when given a flat DDL. See nb 07 source.)
2. **MLflow logging:** `mlflow.log_params({model, prompt_name, prompt_text})` +
   `mlflow.log_metrics({her2_acc, er_acc, pr_acc, overall_acc})` inside `mlflow.start_run(...)`.

Prompts: V1 terse, V2 spells out IHC 3+/FISH-amplified ⇒ Positive, IHC 0/1+ ⇒ Negative, IHC 2+/
equivocal ⇒ Unknown. Full text in nb 07 source.
- **Gotcha:** `safe_prompt = prompt_text.replace("'", "''")`, single quotes in the prompt break the
  interpolated SQL otherwise.
- **Expected outcome:** the foundation now plants a **hard-case band** (person 61-90) with
  equivocal-but-resolvable notes (HER2 IHC 2+ with a reflex FISH ratio, ER-low-positive), so the
  leaderboard shows a real spread (careful prompt and stronger model win) and the error table has rows.
  The misses cluster on HER2 IHC 2+, a *safe* miss (Unknown), which is the teaching point. Structured
  values stay the definite gold label, so no cohort count changes (Trial A 140, Trial B 70, and the NLP uplift of +31 for A / +14 for B all hold).
- **The GenAI eval (completed notebook sections 6-8):** `mlflow.genai.evaluate()` with per-row
  **traces**, an **LLM-as-judge** (`Guidelines`), and **custom `@scorer` metrics**, run for the terse
  and careful prompts on the hard band so the managed harness shows the same contrast. The
  `Guidelines` judge needs a workspace judge model; drop that one scorer if unavailable.

## NB 08: Genie verify SQL (light TODO)

`SELECT COUNT(*) FROM gold_trial_prescreen WHERE trial_a_eligible = TRUE` and `… AND biomarker_source
= 'nlp'`. The comments + UI steps + curated content are pre-built (`genie/genie_space.md`).

## NB 09: coordinator app (STRETCH)

No reference solution, open-ended. Point teams at the `databricks-apps` skill and `STRETCH.md`.
