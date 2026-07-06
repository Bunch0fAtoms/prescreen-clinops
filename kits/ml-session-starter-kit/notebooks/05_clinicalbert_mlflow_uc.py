# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 05 · CLINICALBERT + MLFLOW · ✅ PRE-BUILT, OPTIONAL</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧬 Bring your own model: ClinicalBERT note embeddings, governed by Unity Catalog</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Register a domain HuggingFace encoder to Unity Catalog with MLflow, turn every pathology note
# MAGIC     into a meaningful vector at scale in Spark, and prove the embeddings find semantically similar
# MAGIC     reports, no data ever leaves the platform.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:16px 20px; border-radius:4px">
# MAGIC <div style="font-size:1.15em; font-weight:700; color:#7A4F00">✅ This notebook is PRE-BUILT. Running it is OPTIONAL.</div>
# MAGIC <div style="margin-top:8px">
# MAGIC The <code>ai_query</code> path you built in nb 04 is what the rest of the build needs. It produced
# MAGIC <code>silver_nlp_biomarkers</code>, the table nb 06 fuses into the gold view. <b>This notebook is a
# MAGIC separate value story</b>, not on the critical path: <i>"we have our OWN model / fine-tune, can we
# MAGIC run it on governed Databricks?"</i> It shows the <b>register-to-UC + score-in-Spark</b> mechanics
# MAGIC using ClinicalBERT for what it is genuinely good at, <b>embeddings</b> (not classification), and
# MAGIC closes with a similarity-search demo. The code is written for you; read it for the governance
# MAGIC story, and <b>run it only if</b> your workspace has HuggingFace egress.<br><br>
# MAGIC <b>Fallback:</b> if ClinicalBERT can't download or serve in your workspace, that's fine. Skip to
# MAGIC nb 06. Nothing downstream depends on the embeddings; they are an additive cohort-discovery primitive.
# MAGIC </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## What is this notebook for?
# MAGIC
# MAGIC **ClinicalBERT** (`emilyalsentzer/Bio_ClinicalBERT`) is a BERT model pre-trained on clinical text
# MAGIC (the MIMIC-III ICU notes), so it "speaks" the language of pathology reports far better than a
# MAGIC general-purpose BERT. It is a great example of a **domain model a research team might already own**.
# MAGIC
# MAGIC This notebook tells the **bring-your-own-model + governance** story in four moves:
# MAGIC 1. **Wrap** ClinicalBERT's base encoder as an MLflow `pyfunc` that turns a note into a 768-dim
# MAGIC    **embedding** (mean-pooled over the tokens).
# MAGIC 2. **Register** it to **Unity Catalog**: versioned, permissioned, lineage-tracked just like a table.
# MAGIC 3. **Score** every pathology note **in Spark** via `mlflow.pyfunc.spark_udf`: distributed, no
# MAGIC    `toPandas()` round-trip, full UC lineage from `note` → `silver_clinicalbert_note_embeddings`.
# MAGIC 4. **Demo the value**: cosine-similarity search over the embeddings surfaces the most similar
# MAGIC    pathology reports, the building block for cohort discovery and retrieval.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>How this relates to notebook 04.</b> The <code>ai_query</code> path in nb 04 is the
# MAGIC <b>managed-model extraction path</b>: one SQL function over a Foundation Model endpoint that
# MAGIC <i>accurately pulls HER2 / ER / PR</i> from the notes. ClinicalBERT here is the
# MAGIC <b>bring-your-own-model</b> path: it answers <i>"we have our own model, can we run it on governed
# MAGIC Databricks?"</i> We use ClinicalBERT for what it is genuinely good at, <b>embeddings</b>, not
# MAGIC classification, and register + score it with full UC governance and lineage.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### ⚙️ Compute note, read before running
# MAGIC
# MAGIC <div style="background:#E3F2FD; border-left:6px solid #1565C0; padding:12px 16px; border-radius:4px">
# MAGIC This notebook <b>downloads model weights from HuggingFace</b>, so it needs <b>serverless</b> or a
# MAGIC cluster <b>with outbound internet access</b>. The model is small (~110M params, ~440&nbsp;MB) and runs
# MAGIC fine on CPU. Each note is <b>one forward pass</b>, so embedding all the reports is fast. If your
# MAGIC workspace blocks public internet, mirror the model into a UC Volume first and point
# MAGIC <code>from_pretrained</code> at that path.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Install the model toolchain, then restart Python
# MAGIC %pip install -U transformers torch mlflow

# COMMAND ----------

# DBTITLE 1,Restart Python so the fresh libraries load
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# DBTITLE 1,Set the working context: read OMOP from the source schema
# This notebook READS the read-only OMOP `note` table, which lives in your SOURCE schema
# (e.g. clinops_foundation), and WRITES its embeddings to your OWN schema. `_config` set the
# default catalog/schema to your write schema; here we point the default at the SOURCE so the
# `note` reads resolve by bare name (same pattern as notebook 01). Everything this notebook
# CREATES is written fully-qualified through fqn(), so it still lands in your write schema
# regardless of the default. The two schemas are usually different, so one default cannot
# cover both; reads follow the default, writes are pinned by fqn().
spark.sql(f"USE CATALOG {SOURCE_CATALOG}")
spark.sql(f"USE SCHEMA {SOURCE_SCHEMA}")
print(f"Reading OMOP source from {SOURCE_CATALOG}.{SOURCE_SCHEMA}")
print(f"Writing tables to {CATALOG}.{SCHEMA} (via fqn())")

# COMMAND ----------

# DBTITLE 1,Point MLflow at Unity Catalog as the model registry
import mlflow

# Register models into UC (three-level namespace) rather than the legacy workspace registry.
mlflow.set_registry_uri("databricks-uc")

# The model's governed name: catalog.schema.model, lives right beside our tables.
MODEL_NAME = fqn("clinicalbert_note_embedder")
HF_MODEL   = "emilyalsentzer/Bio_ClinicalBERT"

print(f"Registry  : databricks-uc")
print(f"Model name: {MODEL_NAME}")
print(f"Source    : {HF_MODEL}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 1️⃣ to 2️⃣ Wrap ClinicalBERT's encoder as an MLflow pyfunc
# MAGIC
# MAGIC We load the **base encoder** (`AutoModel`, not the masked-LM head) and, for each note, run **one
# MAGIC forward pass** then **mean-pool** the final hidden states over the attention mask. That collapses a
# MAGIC variable-length note into a single fixed **768-dim vector** that captures what the report is about.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Why embeddings, not a classifier?</b> Bio_ClinicalBERT was never fine-tuned to call HER2/ER/PR, so
# MAGIC asking it to classify is unreliable. <code>ai_query</code> (nb 04) owns accurate extraction. What a
# MAGIC pre-trained clinical encoder <i>is</i> excellent at is producing <b>meaningful representations</b> of
# MAGIC clinical text. Those power similarity search, clustering, cohort discovery and retrieval, and they
# MAGIC let us tell the governance story cleanly with a model doing what it's actually good at.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,The pyfunc, mean-pooled note embeddings (PRE-BUILT)
import mlflow.pyfunc


class ClinicalBertEmbedder(mlflow.pyfunc.PythonModel):
    """Mean-pooled sentence embeddings from Bio_ClinicalBERT's base encoder.

    For each note we run ONE forward pass through the encoder (AutoModel, not
    MaskedLM), then mean-pool the last_hidden_state over the attention mask to
    produce a single 768-dim vector. predict() returns a (n, 768) float32 ndarray
    so spark_udf(result_type="array<float>") unpacks cleanly.
    """

    def load_context(self, context):
        import torch
        from transformers import AutoTokenizer, AutoModel

        self._torch = torch
        # Weights are packaged as MLflow artifacts (see log_model below) so scoring
        # nodes never re-download from the internet.
        path = context.artifacts["model"]
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModel.from_pretrained(path)
        self.model.eval()

    def _embed_one(self, note_text):
        torch = self._torch
        text = note_text or ""
        enc = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=512
        )
        with torch.no_grad():
            out = self.model(**enc)
        last_hidden = out.last_hidden_state                  # (1, seq, 768)
        mask = enc["attention_mask"].unsqueeze(-1).float()   # (1, seq, 1)
        summed = (last_hidden * mask).sum(dim=1)             # (1, 768)
        counts = mask.sum(dim=1).clamp(min=1e-9)             # (1, 1)
        mean_pooled = (summed / counts)[0]                   # (768,)
        return [float(x) for x in mean_pooled.tolist()]

    def predict(self, context, model_input):
        """model_input: a pandas DataFrame with a 'note_text' column (spark_udf passes this).

        Returns a (n, 768) float32 ndarray, one row per note. We return a 2D ndarray
        (not a Series of lists) so mlflow's spark_udf maps it cleanly to
        result_type="array<float>". A Series-of-lists is not coerced and trips
        "did not produce values compatible with FloatType()".
        """
        import numpy as np
        import pandas as pd

        if isinstance(model_input, pd.DataFrame):
            notes = model_input.iloc[:, 0].tolist()
        else:
            notes = list(model_input)
        return np.array([self._embed_one(n) for n in notes], dtype=np.float32)


print("✅ ClinicalBertEmbedder pyfunc defined.")

# COMMAND ----------

# DBTITLE 1,Download the HF weights once into a local artifact dir
# Pull the encoder + tokenizer to a local path so we can package them AS MLflow
# artifacts. This makes the registered model self-contained: scoring nodes load
# weights from UC, not from the public internet.
# NOTE: save_pretrained(safe_serialization=False) writes pytorch_model.bin.
# safetensors triggered an executor-side "SafetensorError: header too large" on
# spark_udf load.
import tempfile, os
from transformers import AutoTokenizer, AutoModel

local_dir = os.path.join(tempfile.mkdtemp(), "bio_clinicalbert")
AutoTokenizer.from_pretrained(HF_MODEL).save_pretrained(local_dir)
AutoModel.from_pretrained(HF_MODEL).save_pretrained(local_dir, safe_serialization=False)
print(f"✅ ClinicalBERT cached to {local_dir}")
print(f"   files: {os.listdir(local_dir)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Log + register to Unity Catalog
# MAGIC
# MAGIC One `log_model` call captures the wrapper code, packages the weights as artifacts, pins the Python
# MAGIC dependencies, and records an `input_example`. We then `register_model` into our UC namespace. From
# MAGIC here it is governed: grant `EXECUTE` to a team, see it in Catalog Explorer, track its lineage.

# COMMAND ----------

# DBTITLE 1,Log the pyfunc and register a new UC version
import numpy as np
import pandas as pd
from mlflow.models.signature import infer_signature

# A tiny, representative input/output example for the model signature.
input_example = pd.DataFrame(
    {"note_text": ["IHC shows HER2 3+ with strong complete membrane staining; ER negative."]}
)
# Output is a (1, 768) float32 array -> the signature infers an array output, which
# is exactly what spark_udf result_type="array<float>" expects.
output_example = np.zeros((1, 768), dtype=np.float32)
signature = infer_signature(input_example, output_example)

with mlflow.start_run(run_name="clinicalbert_note_embedder") as run:
    mlflow.pyfunc.log_model(
        artifact_path="clinicalbert_note_embedder",
        python_model=ClinicalBertEmbedder(),
        artifacts={"model": local_dir},     # weights ride along as artifacts
        pip_requirements=["transformers", "torch"],
        signature=signature,
        input_example=input_example,
    )
    run_id = run.info.run_id

# Register the logged model into Unity Catalog and capture the version.
mv = mlflow.register_model(
    model_uri=f"runs:/{run_id}/clinicalbert_note_embedder",
    name=MODEL_NAME,
)
version = mv.version
print(f"✅ Registered {MODEL_NAME} version {version}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 4️⃣ Score every pathology note, in Spark, no round-trip
# MAGIC
# MAGIC `mlflow.pyfunc.spark_udf` loads the UC model onto **every executor** and returns a Spark UDF. We
# MAGIC apply it to a Spark DataFrame of notes and write the result straight back to a UC table. The note
# MAGIC text is **never collected to the driver**. This is the same pattern you would use on 10 million
# MAGIC notes, not 240.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Why this matters for governance:</b> because the read (<code>note</code>), the model
# MAGIC (<code>clinicalbert_note_embedder</code>), and the write
# MAGIC (<code>silver_clinicalbert_note_embeddings</code>) are all UC objects, Databricks records the
# MAGIC <b>lineage</b> automatically. No <code>toPandas()</code>, no data leaving Spark, nothing to explain
# MAGIC to your compliance team. We <code>repartition</code> the notes so the forward passes parallelize
# MAGIC across executors.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Quick check, embeddings on a 10-note sample
from pyspark.sql import functions as F

model_uri = f"models:/{MODEL_NAME}/{version}"
embed_udf = mlflow.pyfunc.spark_udf(spark, model_uri=model_uri, result_type="array<float>")
print(f"✅ spark_udf ready from {model_uri}")

_sample = spark.sql("""
    SELECT person_id, note_id, note_text
    FROM note
    WHERE note_source_value = 'PATHOLOGY_REPORT'
    LIMIT 10
""").withColumn("embedding", embed_udf(F.col("note_text"))).collect()

_v0, _v1 = _sample[0]["embedding"], _sample[1]["embedding"]
print(f"embedding dim : {len(_v0)}")
print(f"v0[:5]        : {_v0[:5]}")
print(f"v1[:5]        : {_v1[:5]}")
print(f"degenerate?   : {_v0 == _v1}  (distinct notes should give distinct vectors)")

# COMMAND ----------

# DBTITLE 1,Embed all pathology notes and write the silver table
notes_df = spark.sql("""
    SELECT person_id, note_id, note_text
    FROM note
    WHERE note_source_value = 'PATHOLOGY_REPORT'
""").repartition(8)   # parallelize the forward passes across executors

scored = (
    notes_df
    .withColumn("embedding", embed_udf(F.col("note_text")))   # one 768-d vector per note, on executors
    .select(
        "person_id",
        "note_id",
        "embedding",
        F.lit("clinicalbert").alias("model_source"),
    )
)

(
    scored.write
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(fqn("silver_clinicalbert_note_embeddings"))
)

print(f"✅ Wrote {fqn('silver_clinicalbert_note_embeddings')}")

# COMMAND ----------

# DBTITLE 1,Peek at the embeddings table
# The default schema points at the SOURCE, so we read our write-schema table via fqn().
display(spark.sql(f"""
    SELECT person_id, note_id, size(embedding) AS embedding_dim, model_source
    FROM {fqn('silver_clinicalbert_note_embeddings')}
    ORDER BY person_id
    LIMIT 10
"""))

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 5️⃣ The value: semantic similarity search over the embeddings
# MAGIC
# MAGIC Embeddings are only useful if "close in vector space" means "clinically similar". Here we take one
# MAGIC pathology note, compute its **cosine similarity** to every other note, and surface the **top-3 most
# MAGIC similar** reports. This is the primitive behind cohort discovery ("find patients like this one"),
# MAGIC de-duplication, and retrieval-augmented search over the clinical corpus.

# COMMAND ----------

# DBTITLE 1,Cosine similarity, find the most similar pathology notes
import numpy as np

emb_pdf = spark.sql(f"""
    SELECT e.person_id, e.note_id, e.embedding, n.note_text
    FROM {fqn('silver_clinicalbert_note_embeddings')} e
    JOIN note n ON e.note_id = n.note_id
""").toPandas()

mat = np.array(emb_pdf["embedding"].tolist(), dtype=np.float32)
unit = mat / np.clip(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9, None)

query_idx = 0
sims = unit @ unit[query_idx]
top = [i for i in np.argsort(-sims) if i != query_idx][:3]

q = emb_pdf.iloc[query_idx]
show_md(
    f"<b>Query note</b>, person {q['person_id']}, note {q['note_id']}<br>"
    f"<span style='color:#555'>{q['note_text'][:200]}…</span>"
)
for rank, i in enumerate(top, 1):
    r = emb_pdf.iloc[i]
    show_md(
        f"<b>#{rank} · cosine {sims[i]:.4f}</b>, person {r['person_id']}, note {r['note_id']}<br>"
        f"<span style='color:#555'>{r['note_text'][:200]}…</span>"
    )

# COMMAND ----------

# DBTITLE 1,Final verification, row count + embedding dimension
display(spark.sql(f"""
    SELECT COUNT(*) AS n_notes, MIN(size(embedding)) AS min_dim, MAX(size(embedding)) AS max_dim
    FROM {fqn('silver_clinicalbert_note_embeddings')}
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just did:</b> took a HuggingFace clinical encoder, registered it to <b>Unity Catalog</b>
# MAGIC as a versioned, permissioned asset, and embedded every pathology note <b>at scale in Spark</b> with
# MAGIC full lineage (no data round-trips, no ungoverned model files), then showed the embeddings are
# MAGIC <b>semantically meaningful</b> via similarity search. That is the "bring your own model onto governed
# MAGIC Databricks" story end-to-end.<br><br>
# MAGIC The <code>ai_query</code> path (nb 04) stays the managed-model extraction path for HER2/ER/PR;
# MAGIC ClinicalBERT proves the platform governs and runs a team's own model just as cleanly, and the same
# MAGIC log → register → <code>spark_udf</code> flow is exactly what you'd use for any custom model.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[06_gold_unified_prescreen]($./06_gold_unified_prescreen)** to fuse the structured + NLP biomarkers into one gold pre-screening view.
