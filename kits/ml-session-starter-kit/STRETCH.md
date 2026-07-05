# 🚀 STRETCH — make it your own

Finished the core build (notebooks 01–08, all the `# TODO (you build this)` markers)? Pick an
extension. These map to the `# EXTENSION (optional)` hooks scattered through the notebooks. None are
required — they're for teams who want to push further or have a real FH use case in mind.

Ground rules still apply: **Unity-Catalog-scoped, synthetic data only, no hardcoded secrets, no
hive_metastore.**

---

## ⭐ Want a trained model? Build a patient-prioritization ranker

The baseline session does applied AI extraction plus rules-based eligibility, on purpose. There is no
trained classifier, because a trial coordinator needs a decision they can defend, not a score they
cannot explain. If your team wants to train a real model, add one **on top of** the eligibility rules,
never inside them.

Build a **prioritization ranker**: given the patients the rules already marked eligible, predict which
ones a coordinator should contact first. Reasonable synthetic features, all UC-scoped:
- recency of the last visit or note, from `note` / `visit` dates,
- biomarker provenance from `biomarker_source` (a structured lab result outranks an NLP-recovered one),
- tumor stage from `ajcc_stage`, and age from `silver_demographics`.

Fit something simple (logistic regression or gradient-boosted trees), log and register it to Unity
Catalog with MLflow, then score with `mlflow.pyfunc.spark_udf` so you stay in Spark and keep UC
lineage. Add the predicted rank as a column on the eligible list and sort the coordinator app by it.

Why this is the honest place for a model: eligibility stays a transparent, auditable rule with a
reason per patient, and the model only orders the people who already passed. The model helps a human
work the list faster. It never decides who is eligible.

## 1. The coordinator App (nb 09) — the obvious last mile

Build a Databricks App over `gold_trial_prescreen`:
- A **trial-selector dropdown** (Trial A / Trial B) filtering on `trial_a_eligible` / `trial_b_eligible`.
- A sortable **eligible-patient list** with the `trial_*_reason` string.
- A **provenance badge** from `biomarker_source`: green *"Structured"* vs amber *"NLP-recovered"* —
  the whole story of the solution, made visible to a non-technical user.
- Optionally **embed the Genie space** (nb 08) for free-text follow-ups inside the app.

Use the `databricks-apps` / `databricks-apps-python` skill. Deploy by uploading source to the
workspace and deploying from there, scoped to your UC catalog. Keep it thin — a CDN-served React or a
small Streamlit app, no heavy build step.

## 2. Add a third trial

Extend `gold_trial_prescreen` with another cohort, e.g. **triple-negative** (ER−, PR−, HER2−) or a
**Stage III/IV** trial using `ajcc_stage` from `silver_demographics`. Add a `trial_c_eligible` boolean
+ `trial_c_reason`, then add it to the Genie space. (Hook: nb 06 `# EXTENSION`.)

## 3. Advanced evaluation with `mlflow.genai.evaluate()`

Notebook 07 computes accuracy by hand for transparency. Reach for the managed path instead:
- Build an eval dataset from the goldset, define a custom **scorer** (or use built-in
  `Correctness` / `Guidelines`), and let `mlflow.genai.evaluate()` produce the per-row results and
  comparison table.
- Add a **third prompt** or a third model and see if the winner changes.
- Re-run nb 04's `silver_nlp_biomarkers` with the **winning** prompt/model, then re-run nb 06 and
  watch the cohort numbers move. (Hooks: nb 04 + nb 07 `# EXTENSION`.)
- The `databricks-mlflow-evaluation` / `agent-evaluation` skills cover this.

## 4. Fine-tune ClinicalBERT for real

Notebook 05 uses ClinicalBERT's base encoder for **mean-pooled note embeddings** to show the
*governance mechanics* (register-to-UC + score-in-Spark) honestly — the model doing what it's good at.
The next step: **fine-tune** it on labeled pathology reports with a real sequence-classification head,
register **that** to UC, and compare it head-to-head with `ai_query` in the nb 07 eval. The
log → register → `spark_udf` flow barely changes. (Hook: nb 05 `# EXTENSION`.) A second stretch: index
`silver_clinicalbert_note_embeddings` in **Vector Search** and turn the cosine-similarity demo into a
real cohort-retrieval endpoint.

## 5. Exercise the synthetic → real toggle

The whole kit runs on synthetic data. Prove the toggle works the way FH will use it:
- In `databricks.yml`, set `run_with_synthetic_data: "no"` and point `source_catalog` /
  `source_schema` at a *second synthetic schema* (stand in for `curated_omop.omop`).
- Re-deploy and confirm every silver/gold/NLP query runs **unchanged** — the 6 OMOP table names are
  identical in both modes. This is the security-first payoff: nothing breaks if real PHI is gated.
- **Never** point it at real PHI in the workshop; the toggle exists so you don't have to.

## 6. Governance deep-cut

Lean into the security-first lens:
- Add **column masking** (e.g. mask `person_id` for an analyst role) or a **row filter** on
  `gold_trial_prescreen` and show it in Catalog Explorer.
- Inspect the **lineage graph** from `note` → `silver_nlp_biomarkers` → `gold_trial_prescreen` (and,
  if you ran nb 05, through the registered model) — it's recorded automatically because everything is UC.
- Grant `EXECUTE` on the ClinicalBERT model to a team group and show the permission in the UI.

## 7. Metric view for governed KPIs

Define a UC **metric view** over `gold_trial_prescreen` (eligible counts, NLP-recovered count,
dimensioned by `biomarker_source`) so every team shares one definition of "eligible," and point the
Genie space at it. See `genie/genie_space.md` and the `databricks-metric-views` skill.
