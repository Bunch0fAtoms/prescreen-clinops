# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 07 · LLM EVALUATION · 🧠 YOU BUILD THE EVAL</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">📊 Evaluating the extraction: prompts &amp; models, scored</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Compare two prompts and two models on biomarker extraction quality against ground truth,
# MAGIC     tracked in MLflow so you can compare runs, pick a winner, and inspect where it goes wrong.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why evaluate an LLM extraction step at all?
# MAGIC
# MAGIC In nb 04, `ai_query` *worked* on a spot check, but "looks right on a few rows" is not how you ship
# MAGIC something a trial-eligibility decision leans on. You'd never ship an ML model without a test set and
# MAGIC a number. **The same discipline applies to an LLM prompt.** The prompt and the model are the two
# MAGIC knobs; small wording changes move accuracy in ways you can't eyeball.
# MAGIC
# MAGIC So we run a real experiment (**2 prompts × 2 models = 4 configurations**) and log each to MLflow:
# MAGIC
# MAGIC | Knob | Choices |
# MAGIC |---|---|
# MAGIC | **Prompt** | `v1` (terse) vs `v2` (careful, IHC/FISH-aware) |
# MAGIC | **Model**  | `LLM_FAST` (haiku) vs `LLM_STRONG` (sonnet) |
# MAGIC
# MAGIC <div style="background:#E3F2FD; border-left:6px solid #1565C0; padding:12px 16px; border-radius:4px">
# MAGIC <b>Where does the gold label come from?</b> Patients 1 to 180 are the <b>"both-agree"</b> cohort: a
# MAGIC structured <code>measurement</code> value <i>and</i> a note that says the same thing. The structured
# MAGIC value <b>is</b> the gold label; the note is what the model reads. Perfect for scoring an extractor.
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Build the ground-truth eval set (PRE-BUILT)
# MAGIC
# MAGIC One row per patient 1 to 180 carrying **both** the note text *and* the structured HER2/ER/PR labels.

# COMMAND ----------

# DBTITLE 1,eval_biomarker_goldset, note text + structured gold labels (person 1 to 180) (PRE-BUILT)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE eval_biomarker_goldset
# MAGIC COMMENT 'Both-agree cohort (person 1-180): pathology note text + structured HER2/ER/PR gold labels'
# MAGIC AS
# MAGIC WITH notes AS (
# MAGIC   SELECT person_id, MAX(note_text) AS note_text
# MAGIC   FROM note
# MAGIC   WHERE note_source_value = 'PATHOLOGY_REPORT' AND person_id BETWEEN 1 AND 180
# MAGIC   GROUP BY person_id
# MAGIC )
# MAGIC SELECT n.person_id, n.note_text,
# MAGIC   g.her2_status AS gold_her2, g.er_status AS gold_er, g.pr_status AS gold_pr
# MAGIC FROM notes n
# MAGIC JOIN silver_biomarker_profile g ON n.person_id = g.person_id
# MAGIC WHERE g.her2_status IS NOT NULL OR g.er_status IS NOT NULL OR g.pr_status IS NOT NULL;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Define the two prompts (YOU BUILD THESE)
# MAGIC
# MAGIC Both prompts must return the **same strict values** (`Positive`/`Negative`/`Unknown`) so the
# MAGIC scoring is apples-to-apples. The only thing that changes is *how much guidance* each gives the
# MAGIC model about reading IHC / FISH results. That contrast is the lesson.

# COMMAND ----------

# DBTITLE 1,TODO write PROMPT_V1 (terse) and PROMPT_V2 (careful), YOU BUILD THIS
# TODO (you build this): two prompt strings that BOTH ask for HER2 / ER / PR and constrain the answer
#   to exactly Positive / Negative / Unknown per marker.
#   • PROMPT_V1: minimal, just the ask. Trust the model to know what HER2/ER/PR mean.
#   • PROMPT_V2: spell out the clinical scoring rules, e.g. HER2 IHC 3+ OR FISH-amplified => Positive;
#     IHC 0/1+ OR FISH not-amplified => Negative; IHC 2+ without confirming FISH / equivocal => Unknown.
# WHY two prompts: you want to MEASURE whether the extra guidance actually buys accuracy, and whether
#   it's worth it on the cheap model vs the strong one. That's the whole point of the experiment.
PROMPT_V1 = "TODO: terse prompt"      # <- replace
PROMPT_V2 = "TODO: careful prompt"    # <- replace

PROMPTS = {"v1_terse": PROMPT_V1, "v2_careful": PROMPT_V2}
MODELS  = [LLM_FAST, LLM_STRONG]   # databricks-claude-haiku-4-5, databricks-claude-sonnet-4-6
print("Prompts:", list(PROMPTS.keys()))
print("Models :", MODELS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Run all four configurations and log to MLflow (YOU BUILD THE CORE)
# MAGIC
# MAGIC For each (prompt, model) pair: one `ai_query` pass over the goldset, compute per-marker accuracy
# MAGIC vs gold, and log **one MLflow run** (params + metrics) so the Experiments UI lines the four up.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>Tip, the managed alternative.</b> In production you'd often reach for
# MAGIC <code>mlflow.genai.evaluate()</code> with a custom scorer and let MLflow build the comparison
# MAGIC table for you. Here we compute accuracy directly so every number on screen is transparent, same
# MAGIC idea, fewer moving parts to explain. (Trying <code>mlflow.genai.evaluate()</code> is a stretch, see STRETCH.md.)
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,The harness is PRE-BUILT, fill the two TODOs inside run_config()
import mlflow
from pyspark.sql import functions as F

mlflow.set_experiment(f"/Users/{spark.sql('SELECT current_user()').first()[0]}/clinops_biomarker_eval")
GOLDSET = fqn("eval_biomarker_goldset")


def run_config(model: str, prompt_name: str, prompt_text: str):
    """Score one (model, prompt) config on the goldset and log an MLflow run."""
    safe_prompt = prompt_text.replace("'", "''")  # SQL-escape single quotes

    # TODO (you build this) #1, the scoring query.
    #   Run ONE ai_query pass over GOLDSET. Prompt = '{safe_prompt}' || '\\n\\nReport:\\n' || note_text.
    #   Use responseFormat => 'STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>'.
    #   Select gold_her2/gold_er/gold_pr alongside the predicted x.her2_status/x.er_status/x.pr_status
    #   (alias them pred_her2 / pred_er / pred_pr). See nb 04 for the ai_query + responseFormat shape.
    preds = spark.sql(f"""
        SELECT person_id, note_text, gold_her2, gold_er, gold_pr,
               -- TODO: pred_her2, pred_er, pred_pr from ai_query('{model}', ... , responseFormat => ...)
               CAST(NULL AS STRING) AS pred_her2,
               CAST(NULL AS STRING) AS pred_er,
               CAST(NULL AS STRING) AS pred_pr
        FROM {GOLDSET}
    """)

    # Per-marker accuracy, PRE-BUILT (only scores rows where a gold label exists).
    def acc(gold_col, pred_col):
        return (
            F.sum(F.when(F.col(gold_col).isNotNull() & (F.col(gold_col) == F.col(pred_col)), 1).otherwise(0))
            / F.sum(F.when(F.col(gold_col).isNotNull(), 1).otherwise(0))
        )

    scored = preds.agg(
        acc("gold_her2", "pred_her2").alias("her2_acc"),
        acc("gold_er",   "pred_er").alias("er_acc"),
        acc("gold_pr",   "pred_pr").alias("pr_acc"),
    ).first()
    her2 = float(scored["her2_acc"] or 0.0)
    er   = float(scored["er_acc"]   or 0.0)
    pr   = float(scored["pr_acc"]   or 0.0)
    overall = (her2 + er + pr) / 3.0

    # TODO (you build this) #2, log this configuration as ONE MLflow run.
    #   with mlflow.start_run(run_name=f"{model}__{prompt_name}"):
    #       mlflow.log_params({"model": ..., "prompt_name": ..., "prompt_text": ...})
    #       mlflow.log_metrics({"her2_acc": her2, "er_acc": er, "pr_acc": pr, "overall_acc": overall})
    #   WHY: logging params+metrics per run is what makes the four configs comparable in the Experiments
    #   UI. That artifact turns "we picked this prompt" into a reproducible, defensible decision.

    return {
        "model": model, "prompt": prompt_name,
        "her2_acc": round(her2, 4), "er_acc": round(er, 4),
        "pr_acc": round(pr, 4), "overall_acc": round(overall, 4),
        "preds": preds,
    }


results = []
for model in MODELS:
    for prompt_name, prompt_text in PROMPTS.items():
        print(f"▶ scoring  {model}  ×  {prompt_name} …")
        results.append(run_config(model, prompt_name, prompt_text))
print(f"\n✅ {len(results)} configurations scored.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Compare the four runs and pick a winner (PRE-BUILT)

# COMMAND ----------

# DBTITLE 1,Leaderboard, 4 configs, sorted by overall accuracy (PRE-BUILT)
comparison = spark.createDataFrame(
    [{k: r[k] for k in ("model", "prompt", "her2_acc", "er_acc", "pr_acc", "overall_acc")} for r in results]
).orderBy(F.col("overall_acc").desc())
display(comparison)

# COMMAND ----------

# DBTITLE 1,Name the winning configuration (PRE-BUILT)
best = max(results, key=lambda r: r["overall_acc"])
show_md(f"""
<div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
🏆 <b>Winner:</b> <code>{best['model']}</code> with prompt <b>{best['prompt']}</b>,
overall accuracy <b>{best['overall_acc']*100:.1f}%</b>
(HER2 {best['her2_acc']*100:.1f}% · ER {best['er_acc']*100:.1f}% · PR {best['pr_acc']*100:.1f}%).
</div>
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5️⃣ Error patterns: where the winner disagreed with the gold label (PRE-BUILT)
# MAGIC
# MAGIC A headline accuracy number is necessary but not sufficient. Look at the rows the best config got
# MAGIC wrong to know whether the misses are *safe* misses.

# COMMAND ----------

# DBTITLE 1,Disagreements for the winning config, predicted vs actual + note snippet (PRE-BUILT)
winner_preds = best["preds"].withColumn("note_snippet", F.substring("note_text", 1, 220))
errors = (
    winner_preds
    .select(
        "person_id", "note_snippet",
        F.explode(F.array(
            F.struct(F.lit("HER2").alias("marker"), F.col("gold_her2").alias("actual"), F.col("pred_her2").alias("predicted")),
            F.struct(F.lit("ER").alias("marker"),   F.col("gold_er").alias("actual"),   F.col("pred_er").alias("predicted")),
            F.struct(F.lit("PR").alias("marker"),   F.col("gold_pr").alias("actual"),   F.col("pred_pr").alias("predicted")),
        )).alias("m"),
    )
    .where(F.col("m.actual").isNotNull() & (F.col("m.actual") != F.col("m.predicted")))
    .select("person_id", "m.marker", "m.predicted", "m.actual", "note_snippet")
    .orderBy("marker", "person_id")
)
print(f"Disagreements for {best['model']} × {best['prompt']}:")
display(errors)

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#FFEBEE; border-left:6px solid #C62828; padding:12px 16px; border-radius:4px">
# MAGIC <b>How to read the misses.</b> They should cluster on the genuinely hard cases: HER2 <b>IHC 2+</b>
# MAGIC (equivocal) and borderline ER with very low percent staining. A miss that lands on
# MAGIC <code>Unknown</code> is far safer than a confident wrong call. The careful <code>v2</code> prompt
# MAGIC was written to push ambiguous cases toward <code>Unknown</code>.
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just did:</b> treated an LLM prompt the way you'd treat a model, held it to a ground-
# MAGIC truth test set, scored 4 configs, logged every run to <b>MLflow</b>, picked the winner on a
# MAGIC measured number, and inspected where it slips. <b>This is how you ship an LLM step responsibly.</b>
# MAGIC </div>
# MAGIC
# MAGIC <!-- EXTENSION (optional): re-run nb 04's silver_nlp_biomarkers using the WINNING prompt/model,
# MAGIC      then re-run nb 06 and watch the cohort numbers move. Or add a 3rd prompt. See STRETCH.md. -->
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[08_genie_space_setup]($./08_genie_space_setup)** to put a natural-language layer over the cohort with Genie.
