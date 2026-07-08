# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 07 · LLM EVALUATION · COMPLETED</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">📊 Evaluating the extraction: prompts, models, traces, and judges</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Score the biomarker extraction against ground truth two ways: a transparent hand-computed
# MAGIC     accuracy, then the managed <code>mlflow.genai.evaluate()</code> path with per-row traces, an
# MAGIC     LLM-as-judge, and a custom metric.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why evaluate an LLM extraction step at all?
# MAGIC
# MAGIC In nb 04, `ai_query` *worked* on a spot check, but "looks right on a few rows" is not how you ship
# MAGIC something a trial-eligibility decision leans on. You'd never ship an ML model without a test set and
# MAGIC a number. **The same discipline applies to an LLM prompt.**
# MAGIC
# MAGIC This notebook has two halves:
# MAGIC 1. **Sections 1 to 5**: a transparent experiment (2 prompts × 2 models) where we compute accuracy
# MAGIC    ourselves and log each run to MLflow, so every number on screen is explainable.
# MAGIC 2. **Sections 6 to 8**: the managed **`mlflow.genai.evaluate()`** path, which auto-captures a
# MAGIC    **trace** per row, runs an **LLM-as-judge**, and lets us plug in a **custom metric**.

# COMMAND ----------

# DBTITLE 1,Ensure a recent MLflow (mlflow.genai lives here), then restart
# MAGIC %pip install -U "mlflow>=3.1"

# COMMAND ----------

# DBTITLE 1,Restart Python so the fresh MLflow loads
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Build the ground-truth eval set (PRE-BUILT)
# MAGIC
# MAGIC One row per patient 1 to 180 carrying **both** the note text *and* the structured HER2/ER/PR labels.
# MAGIC Patients 1 to 180 are the **both-agree** cohort: the structured value is the gold label, the note is
# MAGIC what the model reads.

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
# MAGIC ## 2️⃣ Define the two prompts (COMPLETED)
# MAGIC
# MAGIC Both return the **same strict values** (`Positive`/`Negative`/`Unknown`). The only difference is
# MAGIC how much clinical guidance each gives about reading IHC / FISH results. That contrast is the lesson.

# COMMAND ----------

# DBTITLE 1,PROMPT_V1 (terse) and PROMPT_V2 (careful) (COMPLETED)
PROMPT_V1 = (
    "Extract the HER2, ER (estrogen receptor), and PR (progesterone receptor) status from this breast "
    "cancer pathology report. Answer with exactly one of Positive, Negative, or Unknown for each."
)

PROMPT_V2 = (
    "You are a breast pathology expert. Extract HER2, ER (estrogen receptor), and PR (progesterone "
    "receptor) status from the pathology report using these rules. "
    "HER2: IHC 3+ OR FISH-amplified => Positive; IHC 0 or 1+ OR FISH not amplified => Negative; "
    "IHC 2+ without confirming FISH, or otherwise equivocal => Unknown. "
    "ER and PR: >= 1% nuclear staining => Positive; < 1% => Negative; not reported => Unknown. "
    "Answer with exactly one of Positive, Negative, or Unknown for each marker."
)

PROMPTS = {"v1_terse": PROMPT_V1, "v2_careful": PROMPT_V2}
MODELS  = [LLM_FAST, LLM_STRONG]   # databricks-claude-haiku-4-5, databricks-claude-sonnet-4-6
print("Prompts:", list(PROMPTS.keys()))
print("Models :", MODELS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Run all four configurations and log to MLflow (COMPLETED)
# MAGIC
# MAGIC For each (prompt, model) pair: one `ai_query` pass over the goldset, compute per-marker accuracy
# MAGIC vs gold, and log **one MLflow run** so the Experiments UI lines the four up.

# COMMAND ----------

# DBTITLE 1,Score each config and log an MLflow run (COMPLETED)
import mlflow
from pyspark.sql import functions as F

mlflow.set_experiment(f"/Users/{spark.sql('SELECT current_user()').first()[0]}/clinops_biomarker_eval")
GOLDSET = fqn("eval_biomarker_goldset")


def run_config(model: str, prompt_name: str, prompt_text: str):
    """Score one (model, prompt) config on the goldset and log an MLflow run."""
    safe_prompt = prompt_text.replace("'", "''")  # SQL-escape single quotes

    # COMPLETED TODO #1, the scoring query. One ai_query pass over the goldset. We use the same
    # result-wrapper responseFormat as nb 04 (the DDL allows one top-level field) and read the nested
    # struct fields directly, aliasing them pred_her2 / pred_er / pred_pr.
    preds = spark.sql(f"""
        SELECT person_id, note_text, gold_her2, gold_er, gold_pr,
               x.result.her2_status AS pred_her2,
               x.result.er_status   AS pred_er,
               x.result.pr_status   AS pred_pr
        FROM (
          SELECT person_id, note_text, gold_her2, gold_er, gold_pr,
            ai_query(
              '{model}',
              '{safe_prompt}' || '\\n\\nReport:\\n' || note_text,
              responseFormat => 'STRUCT<result:STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>>'
            ) AS x
          FROM {GOLDSET}
        )
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

    # COMPLETED TODO #2, log this configuration as ONE MLflow run. Params + metrics per run are what
    # make the four configs comparable in the Experiments UI.
    with mlflow.start_run(run_name=f"{model}__{prompt_name}"):
        mlflow.log_params({"model": model, "prompt_name": prompt_name, "prompt_text": prompt_text})
        mlflow.log_metrics({"her2_acc": her2, "er_acc": er, "pr_acc": pr, "overall_acc": overall})

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
print(f"\n✅ {len(results)} configurations scored and logged to MLflow.")

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
# MAGIC (equivocal) and borderline ER. A miss that lands on <code>Unknown</code> is far safer than a
# MAGIC confident wrong call. The careful <code>v2</code> prompt was written to push ambiguous cases
# MAGIC toward <code>Unknown</code>.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC # ═══ The managed path: `mlflow.genai.evaluate()` ═══
# MAGIC
# MAGIC The sections above computed accuracy by hand so every number is transparent. In practice you'd
# MAGIC often reach for **`mlflow.genai.evaluate()`**, which gives you three things the hand path does not:
# MAGIC
# MAGIC <div style="display:flex; gap:14px; flex-wrap:wrap; margin-top:8px">
# MAGIC   <div style="flex:1; min-width:220px; background:#E3F2FD; border-radius:6px; padding:14px">
# MAGIC     <b>🔍 Traces</b><br>A full, inspectable record of each model call (input, output, latency) in
# MAGIC     the <b>Traces</b> tab, one per row. Click any patient to see exactly what the model saw and said.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:220px; background:#F3E5F5; border-radius:6px; padding:14px">
# MAGIC     <b>⚖️ LLM-as-judge</b><br>A built-in scorer that uses an LLM to grade each response against a
# MAGIC     plain-language rule, for quality dimensions you cannot check with an equality test.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:220px; background:#E8F5E9; border-radius:6px; padding:14px">
# MAGIC     <b>🧮 Custom metrics</b><br>Your own Python scorer (here, exact-match against the gold label),
# MAGIC     evaluated per row and aggregated automatically alongside the judge.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6️⃣ A traced prediction function, aimed at the hard cases
# MAGIC
# MAGIC `mlflow.genai.evaluate()` calls a `predict_fn` once per row and captures a **trace** of each call.
# MAGIC We decorate ours with `@mlflow.trace` and reuse the proven `ai_query` extraction.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>Where the learning is.</b> We point the eval at the <b>hard-case band</b> (person 61-90): notes
# MAGIC written with equivocal-but-resolvable phrasing (HER2 IHC 2+ with a reflex FISH ratio,
# MAGIC ER-low-positive), where the structured value is still the definite gold label. This is where a
# MAGIC terse prompt and a careful prompt <i>disagree</i>, so the traces show real, instructive misses
# MAGIC (not a wall of 100%). We build the extractor as a factory so we can evaluate two prompts and
# MAGIC compare them in the managed harness.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,The traced extractor + a compact eval dataset (COMPLETED)
import mlflow

# We evaluate on the HARD-CASE band (person 61-90): both-agree patients whose STRUCTURED value is
# the definite gold label, but whose pathology note is written equivocally (HER2 IHC 2+ with a
# reflex FISH ratio, ER-low-positive). That is exactly where a terse prompt and a careful prompt
# diverge, so the traces and metrics have something to show. We add a few clear cases (person 1-5)
# so the slice is not all-hard. Kept small so the two eval runs below stay snappy in a live demo.
gold_pdf = spark.sql(f"""
    SELECT person_id, note_text, gold_her2, gold_er, gold_pr,
           CASE WHEN person_id BETWEEN 61 AND 90 THEN 'hard' ELSE 'clear' END AS case_type
    FROM {GOLDSET}
    WHERE note_text IS NOT NULL
      AND (person_id BETWEEN 61 AND 80 OR person_id BETWEEN 1 AND 5)
    ORDER BY person_id
""").toPandas()
print(f"Eval rows: {len(gold_pdf)}  "
      f"(hard: {(gold_pdf.case_type == 'hard').sum()}, clear: {(gold_pdf.case_type == 'clear').sum()})")

# MLflow's eval dataset format: one dict per row with "inputs" and "expectations".
eval_data = [
    {
        "inputs": {"note_text": r.note_text},
        "expectations": {"her2": r.gold_her2, "er": r.gold_er, "pr": r.gold_pr},
    }
    for r in gold_pdf.itertuples()
]


def make_extractor(prompt_text: str, model: str = LLM_STRONG):
    """Build a traced predict_fn bound to a specific prompt and model, so we can evaluate more than
    one configuration and compare. @mlflow.trace records each call as a trace MLflow attaches to the
    evaluation run."""
    safe_prompt = prompt_text.replace("'", "''")

    @mlflow.trace
    def _extract(note_text: str) -> dict:
        safe_note = (note_text or "").replace("'", "''")
        row = spark.sql(f"""
            SELECT x.result.her2_status AS her2, x.result.er_status AS er, x.result.pr_status AS pr
            FROM (
              SELECT ai_query(
                '{model}',
                '{safe_prompt}' || '\\n\\nReport:\\n' || '{safe_note}',
                responseFormat => 'STRUCT<result:STRUCT<her2_status:STRING, er_status:STRING, pr_status:STRING>>'
              ) AS x
            )
        """).first()
        return {"her2": row["her2"], "er": row["er"], "pr": row["pr"]}

    return _extract


# Smoke-test the careful extractor on one HARD note (should resolve the equivocal FISH correctly).
_hard_note = gold_pdf[gold_pdf.case_type == "hard"].iloc[0]["note_text"]
print(make_extractor(PROMPT_V2)(_hard_note))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7️⃣ Scorers: a custom metric AND an LLM-as-judge (COMPLETED)
# MAGIC
# MAGIC - **`her2_exact_match`** and **`biomarker_agreement`** are **custom metrics**: plain Python
# MAGIC   functions decorated with `@scorer`, evaluated per row against the gold `expectations`.
# MAGIC - **`valid_status_values`** is a built-in **`Guidelines`** scorer: an **LLM-as-judge** that reads
# MAGIC   each response and grades it against a plain-language rule. This catches quality issues (a stray
# MAGIC   value like "equivocal" instead of "Unknown") that an equality test would miss.

# COMMAND ----------

# DBTITLE 1,Define the scorers (COMPLETED)
from mlflow.genai.scorers import scorer, Guidelines


@scorer
def her2_exact_match(outputs: dict, expectations: dict) -> bool:
    """Custom metric: did the predicted HER2 exactly match the gold HER2?"""
    return outputs.get("her2") == expectations.get("her2")


@scorer
def biomarker_agreement(outputs: dict, expectations: dict):
    """Custom metric: fraction of the three markers (that have a gold label) the model got right."""
    keys = ["her2", "er", "pr"]
    graded = [k for k in keys if expectations.get(k) is not None]
    if not graded:
        return None
    correct = sum(1 for k in graded if outputs.get(k) == expectations.get(k))
    return correct / len(graded)


# LLM-as-judge: grades each response against a plain-language rule. Uses a Databricks-hosted judge
# model by default; if your workspace has no judge model configured, drop this scorer from the list.
valid_status_values = Guidelines(
    name="valid_status_values",
    guidelines=(
        "The response must report her2, er, and pr. Each of those three values must be exactly one of "
        "'Positive', 'Negative', or 'Unknown'. Any other wording (for example 'equivocal', 'amplified', "
        "or a numeric score) fails."
    ),
)

print("Scorers ready: her2_exact_match (custom), biomarker_agreement (custom), valid_status_values (LLM judge).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8️⃣ Run `mlflow.genai.evaluate()` for both prompts (COMPLETED)
# MAGIC
# MAGIC We evaluate **two configurations** on the hard slice, the terse prompt and the careful prompt,
# MAGIC each as its own MLflow run. Every run applies all three scorers and records a trace per row.
# MAGIC Expect the **careful prompt to score higher** on `her2_exact_match` and `biomarker_agreement`,
# MAGIC because it resolves the equivocal FISH and ER-low-positive notes the terse prompt slips on. Open
# MAGIC each run in the **Experiments** UI, then the **Traces** tab, to click into a single patient's call.

# COMMAND ----------

# DBTITLE 1,Evaluate terse vs careful: traces + LLM judge + custom metrics (COMPLETED)
import mlflow

configs = {"v1_terse": PROMPT_V1, "v2_careful": PROMPT_V2}
genai_results = {}
for name, prompt_text in configs.items():
    with mlflow.start_run(run_name=f"genai_evaluate__{name}"):
        res = mlflow.genai.evaluate(
            data=eval_data,
            predict_fn=make_extractor(prompt_text),
            scorers=[her2_exact_match, biomarker_agreement, valid_status_values],
        )
        genai_results[name] = res.metrics

print("Managed-eval metrics by prompt (watch the careful prompt win on the hard cases):")
for name, metrics in genai_results.items():
    print(f"\n▶ {name}")
    for k, v in metrics.items():
        print(f"    {k}: {v}")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:16px 20px; border-radius:6px">
# MAGIC <b>What to show Fred Hutch here:</b>
# MAGIC <ol>
# MAGIC <li><b>The contrast</b>: the careful prompt beats the terse one on <code>her2_exact_match</code>
# MAGIC     and <code>biomarker_agreement</code>. Same model, same notes; only the instruction changed.</li>
# MAGIC <li><b>Traces tab</b>: open the terse run, find a hard case (a HER2 IHC 2+ note with a reflex FISH
# MAGIC     ratio around 2.1). You can see the model answered "Unknown" because it stopped at "equivocal".
# MAGIC     Open the same patient in the careful run and it resolved to the right call. That side-by-side is
# MAGIC     the audit trail for an AI-assisted clinical read.</li>
# MAGIC <li><b>The judge column</b>: <code>valid_status_values</code> is graded by an LLM, with a
# MAGIC     rationale per row, not by an equality test.</li>
# MAGIC <li><b>The custom metrics</b>: <code>her2_exact_match</code> and <code>biomarker_agreement</code>
# MAGIC     sit right beside the judge, aggregated over the eval set.</li>
# MAGIC </ol>
# MAGIC The equivocal cases are where the risk lives: a confident wrong call on an ambiguous note is the
# MAGIC thing you must catch. The traces, the judge, and the metrics together are how you catch and measure
# MAGIC it. <b>This is how you ship an LLM step responsibly.</b>
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[08_genie_space_setup]($./08_genie_space_setup)** to put a natural-language layer over the cohort with Genie.
