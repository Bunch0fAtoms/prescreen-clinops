# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 05 · CLINICALBERT + MLFLOW + SERVING · COMPLETED</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧬 Bring your own model: ClinicalBERT, governed by Unity Catalog, served on an endpoint</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Register a domain HuggingFace encoder to Unity Catalog with MLflow, turn every pathology note
# MAGIC     into a meaningful vector at scale in Spark, deploy it to a Model Serving endpoint, and prove
# MAGIC     the embeddings find semantically similar reports. No data ever leaves the platform.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🎯 The lesson, up front
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:14px 18px; border-radius:4px">
# MAGIC <b>Your team can run its own model on governed Databricks, at scale, with full lineage, and never
# MAGIC move a byte of data off the platform.</b> We take a clinical HuggingFace model, register it to Unity
# MAGIC Catalog like a table, score every note in Spark, and serve it on an endpoint.
# MAGIC <br><br>
# MAGIC <b>What the model actually does:</b> it turns <i>one</i> pathology note into <i>one</i> 768-number
# MAGIC vector (an <b>embedding</b>). It does <b>not</b> compare notes. Finding similar patients is a
# MAGIC separate step that runs on the vectors afterward. <b>Embed first, compare second.</b>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## The five moves
# MAGIC
# MAGIC **ClinicalBERT** (`emilyalsentzer/Bio_ClinicalBERT`) is pre-trained on clinical text (MIMIC-III ICU
# MAGIC notes), so it reads pathology reports better than a general-purpose BERT. It stands in for a
# MAGIC **domain model a research team already owns**. We:
# MAGIC 1. **Wrap** its encoder as an MLflow `pyfunc` that turns a note into a 768-dim embedding.
# MAGIC 2. **Register** it to **Unity Catalog**: versioned, permissioned, lineage-tracked like a table.
# MAGIC 3. **Score** every note **in Spark** via `spark_udf`: distributed, no `toPandas()`, full UC lineage.
# MAGIC 4. **Deploy** it to a **Model Serving endpoint** so it is reachable online and from SQL via `ai_query`.
# MAGIC 5. **Show the value**: cosine-similarity search over the embeddings finds similar reports.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>Contrast with notebook 04.</b> nb 04's <code>ai_query</code> is the <b>managed-model</b> path: a
# MAGIC Foundation Model that <i>extracts</i> HER2/ER/PR. This notebook is the <b>bring-your-own-model</b>
# MAGIC path: your own model, governed and served the same way any custom model would be.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ### ⚙️ Compute note, read before running
# MAGIC
# MAGIC <div style="background:#E3F2FD; border-left:6px solid #1565C0; padding:12px 16px; border-radius:4px">
# MAGIC This notebook <b>downloads model weights from HuggingFace</b>, so it needs <b>serverless</b> or a
# MAGIC cluster <b>with outbound internet access</b>. The model is small (~110M params, ~440&nbsp;MB) and runs
# MAGIC fine on CPU. Each note is <b>one forward pass</b>. If your workspace blocks public internet, mirror
# MAGIC the model into a UC Volume first and point <code>from_pretrained</code> at that path.
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
# This notebook READS the read-only OMOP `note` table, which lives in your SOURCE schema, and WRITES
# its embeddings to your OWN schema. Reads follow the default catalog/schema; writes are pinned by fqn().
spark.sql(f"USE CATALOG {SOURCE_CATALOG}")
spark.sql(f"USE SCHEMA {SOURCE_SCHEMA}")
print(f"Reading OMOP source from {SOURCE_CATALOG}.{SOURCE_SCHEMA}")
print(f"Writing tables to {CATALOG}.{SCHEMA} (via fqn())")

# COMMAND ----------

# DBTITLE 1,Point MLflow at Unity Catalog as the model registry
import mlflow

mlflow.set_registry_uri("databricks-uc")

MODEL_NAME = fqn("clinicalbert_note_embedder")   # catalog.schema.model
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
# MAGIC variable-length note into a single fixed **768-dim vector**.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Why embeddings, not a classifier?</b> Bio_ClinicalBERT was never fine-tuned to call HER2/ER/PR.
# MAGIC <code>ai_query</code> (nb 04) owns accurate extraction. A pre-trained clinical encoder is excellent
# MAGIC at producing <b>meaningful representations</b> of clinical text, which power similarity search,
# MAGIC clustering, cohort discovery, and retrieval.
# MAGIC <br><br><b>Embeds, does not compare.</b> <code>predict()</code> takes one note and returns its
# MAGIC vector. It never sees two notes at once, so it cannot compare them. Comparison runs later, on the
# MAGIC stored vectors (step 6). Embed once, reuse the vectors for many comparisons.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,The pyfunc, mean-pooled note embeddings (PRE-BUILT)
import mlflow.pyfunc


class ClinicalBertEmbedder(mlflow.pyfunc.PythonModel):
    """Mean-pooled sentence embeddings from Bio_ClinicalBERT's base encoder.

    This model EMBEDS a single note (text in, one 768-dim vector out). It does NOT
    compare notes; comparison happens downstream on the stored vectors (step 6).

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
# Pull the encoder + tokenizer to a local path so we can package them AS MLflow artifacts. This makes
# the registered model self-contained: scoring nodes load weights from UC, not the public internet.
# NOTE: save_pretrained(safe_serialization=False) writes pytorch_model.bin. safetensors triggered an
# executor-side "SafetensorError: header too large" on spark_udf load.
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
# MAGIC dependencies, and records an `input_example`. We then `register_model` into our UC namespace.

# COMMAND ----------

# DBTITLE 1,Log the pyfunc and register a new UC version
import numpy as np
import pandas as pd
from mlflow.models.signature import infer_signature

input_example = pd.DataFrame(
    {"note_text": ["IHC shows HER2 3+ with strong complete membrane staining; ER negative."]}
)
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

mv = mlflow.register_model(
    model_uri=f"runs:/{run_id}/clinicalbert_note_embedder",
    name=MODEL_NAME,
)
version = mv.version
print(f"✅ Registered {MODEL_NAME} version {version}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 4️⃣ Score every pathology note with the governed model
# MAGIC
# MAGIC We load the registered Unity Catalog model and embed every pathology note. The encoder is small
# MAGIC (~110M params) and runs on CPU, so the note set scores quickly. On very large note volumes you
# MAGIC would push the forward passes onto Spark executors; here the governed model and the governed
# MAGIC write are the point.
# MAGIC
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Why this matters for governance:</b> the read (<code>note</code>), the model, and the write
# MAGIC (<code>silver_clinicalbert_note_embeddings</code>) are all Unity Catalog objects, so Databricks
# MAGIC records the <b>lineage</b> automatically, model included.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Load the governed UC model and embed every note
import pandas as pd
from pyspark.sql import functions as F

model_uri = f"models:/{MODEL_NAME}/{version}"
model = mlflow.pyfunc.load_model(model_uri)   # load the governed model straight from Unity Catalog
print(f"✅ Loaded governed model {model_uri}")

# Read the pathology notes and embed them with the model. The read is from the read-only OMOP source.
notes_pdf = (
    spark.table(src("note"))
         .where("note_source_value = 'PATHOLOGY_REPORT'")
         .select("person_id", "note_id", "note_text")
         .toPandas()
)
emb = model.predict(pd.DataFrame({"note_text": notes_pdf["note_text"].tolist()}))
notes_pdf["embedding"] = [list(map(float, row)) for row in emb]

print(f"scored notes  : {len(notes_pdf)}")
print(f"embedding dim : {len(notes_pdf['embedding'].iloc[0])}")
print(f"degenerate?   : {notes_pdf['embedding'].iloc[0] == notes_pdf['embedding'].iloc[1]}  (distinct notes should give distinct vectors)")

# COMMAND ----------

# DBTITLE 1,Write the note embeddings back to Unity Catalog
from pyspark.sql import types as T

notes_pdf["model_source"] = "clinicalbert"
_schema = T.StructType([
    T.StructField("person_id",    T.LongType()),
    T.StructField("note_id",      T.LongType()),
    T.StructField("embedding",    T.ArrayType(T.FloatType())),
    T.StructField("model_source", T.StringType()),
])
_rows = [
    (int(r.person_id), int(r.note_id), [float(x) for x in r.embedding], r.model_source)
    for r in notes_pdf.itertuples(index=False)
]
scored = spark.createDataFrame(_rows, _schema)

(
    scored.write
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(fqn("silver_clinicalbert_note_embeddings"))
)
print(f"✅ Wrote {fqn('silver_clinicalbert_note_embeddings')}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 5️⃣ Deploy the model to a Model Serving endpoint 🌐 (COMPLETED)
# MAGIC
# MAGIC `spark_udf` is the right tool for **batch** scoring. But sometimes you want the model reachable
# MAGIC **online**: from a SQL query via `ai_query`, from a Genie space, from an app, or from any REST
# MAGIC client, one note at a time, low latency. That is what a **Model Serving endpoint** is for.
# MAGIC
# MAGIC <div style="background:#E3F2FD; border-left:6px solid #1565C0; padding:12px 16px; border-radius:4px">
# MAGIC <b>Why this is the key distinction to show your stakeholders.</b> A UC-registered model is not, by itself,
# MAGIC callable from SQL. <code>ai_query</code> invokes a <b>serving endpoint</b> by name. The Foundation
# MAGIC Models in nb 04 work from SQL because they are <b>pre-provisioned endpoints</b>. Your own model
# MAGIC needs an endpoint created first. Below we create one from the UC model version. It provisions in a
# MAGIC few minutes and, with <code>scale_to_zero_enabled</code>, costs nothing while idle.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Create (or update) a serving endpoint from the UC model version (COMPLETED)
from mlflow.deployments import get_deploy_client

deploy_client = get_deploy_client("databricks")
ENDPOINT_NAME = "clinicalbert_note_embedder"   # workspace-level endpoint name

endpoint_config = {
    "served_entities": [
        {
            "name": "clinicalbert",
            "entity_name": MODEL_NAME,      # the UC model: catalog.schema.model
            "entity_version": str(version),
            "workload_size": "Small",       # smallest CPU workload; fine for a ~110M encoder
            "scale_to_zero_enabled": True,  # no cost while idle
        }
    ]
}

# Create the endpoint, or update it if a previous run already made it. Provisioning (container build
# with transformers + torch) takes several minutes; the cell returns immediately and the endpoint
# reports NOT_READY until the build finishes.
try:
    ep = deploy_client.create_endpoint(name=ENDPOINT_NAME, config=endpoint_config)
    print(f"🚀 Creating endpoint '{ENDPOINT_NAME}' from {MODEL_NAME} v{version} (provisioning...)")
except Exception as e:
    if "already exists" in str(e).lower() or "resource_conflict" in str(e).lower():
        deploy_client.update_endpoint(endpoint=ENDPOINT_NAME, config=endpoint_config)
        print(f"🔁 Endpoint '{ENDPOINT_NAME}' exists, updated to v{version} (provisioning...)")
    else:
        raise

print("Watch it come up under Serving in the left nav. Wait for state READY before the query below.")

# COMMAND ----------

# DBTITLE 1,Wait for the endpoint to be READY (optional, polls for a few minutes)
import time

def endpoint_ready(name, timeout_s=1200, poll_s=20):
    """Poll until the endpoint's served model is READY, or time out."""
    waited = 0
    while waited < timeout_s:
        ep = deploy_client.get_endpoint(name)
        state = (ep.get("state") or {})
        ready = state.get("ready")
        cfg_update = state.get("config_update")
        print(f"  [{waited:>4}s] ready={ready} config_update={cfg_update}")
        if ready == "READY":
            return True
        time.sleep(poll_s)
        waited += poll_s
    return False

# Uncomment to block until ready (endpoint container builds can take 5-15 min the first time):
# endpoint_ready(ENDPOINT_NAME)

# COMMAND ----------

# DBTITLE 1,Query the serving endpoint on a single note (COMPLETED, waits for READY)
# The online path: send one note, get its 768-dim embedding back over REST. This is what an app or a
# SQL ai_query call hits. Endpoints provision asynchronously (first container build can take 5-15 min),
# so we wait for READY, then query. If it is still building, re-run this cell once it reports READY.
if endpoint_ready(ENDPOINT_NAME, timeout_s=600, poll_s=20):
    sample_note = spark.sql("""
        SELECT note_text FROM note WHERE note_source_value = 'PATHOLOGY_REPORT' LIMIT 1
    """).first()["note_text"]

    response = deploy_client.predict(
        endpoint=ENDPOINT_NAME,
        inputs={"dataframe_records": [{"note_text": sample_note}]},
    )
    vec = response["predictions"][0]
    print(f"Endpoint returned an embedding of length {len(vec)}; first 5 dims: {vec[:5]}")
else:
    print("⏳ Endpoint still provisioning. Re-run this cell once it reports READY under Serving in the left nav.")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>Now it is callable from SQL too.</b> With the endpoint READY, the same model answers from a SQL
# MAGIC cell via <code>ai_query('clinicalbert_note_embedder', note_text)</code>, the identical mechanism
# MAGIC nb 04 used for the Foundation Model. Batch (<code>spark_udf</code>) and online (endpoint) are two
# MAGIC front doors to <b>one governed model version</b> in Unity Catalog.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 6️⃣ The value: semantic similarity search over the embeddings
# MAGIC
# MAGIC Embeddings are only useful if "close in vector space" means "clinically similar". We take one
# MAGIC pathology note, compute its **cosine similarity** to every other note, and surface the **top-3 most
# MAGIC similar** reports. This is the primitive behind cohort discovery ("find patients like this one").

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
# MAGIC <b>What we just did:</b> took a HuggingFace clinical encoder, registered it to <b>Unity Catalog</b>
# MAGIC as a versioned, permissioned asset, embedded every pathology note <b>at scale in Spark</b> with full
# MAGIC lineage, <b>deployed it to a Model Serving endpoint</b> so it is reachable online and from SQL, and
# MAGIC showed the embeddings are semantically meaningful. That is the "bring your own model onto governed
# MAGIC Databricks" story end to end. The same log → register → <code>spark_udf</code> → serve flow is what
# MAGIC you would use for any custom model.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[06_gold_unified_prescreen]($./06_gold_unified_prescreen)** to fuse the structured + NLP biomarkers into one gold pre-screening view.
