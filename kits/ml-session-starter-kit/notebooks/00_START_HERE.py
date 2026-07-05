# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:28px 32px; border-radius:8px">
# MAGIC   <div style="font-size:0.95em; letter-spacing:2px; opacity:0.85">FRED HUTCHINSON CANCER CENTER · ML SESSION · STARTER KIT</div>
# MAGIC   <div style="font-size:2.3em; font-weight:700; margin-top:6px">🧬 Clinical Trial Patient Pre-Screening on OMOP</div>
# MAGIC   <div style="font-size:1.15em; margin-top:10px; max-width:880px; opacity:0.95">
# MAGIC     Find every patient who might qualify for a breast-cancer trial — including the ones
# MAGIC     whose biomarker status lives only in free-text pathology notes — using SQL, Lakeflow,
# MAGIC     Foundation Models, MLflow, and Genie on the Databricks Data Intelligence Platform.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 👋 This is a starter kit — you build the core
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:14px 18px; border-radius:4px">
# MAGIC The <b>plumbing is wired for you</b> — the 6 OMOP tables (from the shared foundation), the
# MAGIC pipeline skeleton, Unity Catalog
# MAGIC governance, all the boilerplate. <b>You</b> write the learnable logic: the eligibility SQL, the
# MAGIC biomarker pivot, the <code>ai_query</code> NLP extraction, and the MLflow evaluation.<br><br>
# MAGIC Look for <b><code>&#35; TODO (you build this)</code></b> markers — that's your work. Hooks marked
# MAGIC <b><code>&#35; EXTENSION (optional)</code></b> are stretch goals (see <code>STRETCH.md</code>).
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🩺 The business problem
# MAGIC
# MAGIC A research coordinator needs to pre-screen patients for two breast-cancer trials:
# MAGIC
# MAGIC | Trial | Looking for |
# MAGIC |---|---|
# MAGIC | **Trial A** — HER2+ | Breast cancer · **HER2 Positive** · age 18–75 · **no** prior anti-HER2 therapy |
# MAGIC | **Trial B** — ER+/HER2− | Breast cancer · **ER Positive** · **HER2 Negative** · **postmenopausal** · age 18–75 |
# MAGIC
# MAGIC The catch: **biomarker status is not always in the structured tables.** For a large slice of
# MAGIC patients, HER2/ER/PR status was only ever written into the free-text pathology report. A SQL
# MAGIC query over `measurement` alone **silently misses them** — and a missed patient is a missed
# MAGIC chance at treatment.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## ✨ The value moment: structured query vs. NLP
# MAGIC
# MAGIC Our 300 synthetic patients fall into three groups by where their biomarkers live:
# MAGIC
# MAGIC <div style="display:flex; gap:14px; flex-wrap:wrap; margin-top:8px">
# MAGIC   <div style="flex:1; min-width:230px; background:#E8F5E9; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#2E7D32">180</div>
# MAGIC     <b>both-agree</b> (person 1–180)<br>biomarkers in <i>both</i> structured tables and notes.
# MAGIC     <br>→ our NLP <b>ground truth</b>.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:230px; background:#FFEBEE; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#C62828">60</div>
# MAGIC     <b>notes-only</b> (person 181–240)<br>biomarkers <i>only</i> in <code>note_text</code>.
# MAGIC     <br>→ <b>invisible to SQL</b>; recovered only by NLP.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:230px; background:#E3F2FD; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.6em; font-weight:700; color:#1565C0">60</div>
# MAGIC     <b>structured-only</b> (person 241–300)<br>biomarkers only in <code>measurement</code>.
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC The notes phrase the same fact a dozen different ways — *"HER2: Positive (3+ by IHC)"*,
# MAGIC *"Her-2/neu overexpression confirmed: 3+"*, *"HER2 amplification: DETECTED (FISH ratio 3.1)"*.
# MAGIC A keyword `LIKE` query breaks on that variety; a Foundation Model reads it like a clinician.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🏗️ Architecture & flow
# MAGIC
# MAGIC ```
# MAGIC  ┌─────────────────────────┐
# MAGIC  │  6 OMOP CDM tables       │   person · condition_occurrence · measurement
# MAGIC  │  (from shared           │   observation · drug_exposure · note
# MAGIC  │   foundation, 300 pts)   │
# MAGIC  └───────────┬─────────────┘   nb 01  (confirm + profile; read-only)
# MAGIC              │
# MAGIC      ┌───────┴────────┐
# MAGIC      ▼                ▼
# MAGIC  ┌─────────┐    ┌──────────────┐
# MAGIC  │ SILVER  │    │     EDA      │  nb 03  (explore the notes-only gap)
# MAGIC  │ pivots  │    └──────────────┘
# MAGIC  │ 🛠️ you  │  nb 02
# MAGIC  └────┬────┘
# MAGIC       │            ┌──────────────────────────────┐
# MAGIC       │            │ NLP biomarker extraction      │
# MAGIC       │            │  • ai_query + FMAPI 🧠 (nb 04)│
# MAGIC       │            │  • ClinicalBERT + MLflow(nb 05)│
# MAGIC       │            └───────────────┬──────────────┘
# MAGIC       ▼                            ▼
# MAGIC  ┌──────────────────────────────────────┐
# MAGIC  │ GOLD: unified biomarker profile +     │  nb 06  🛠️ you
# MAGIC  │ trial pre-screen  (data_source audit) │
# MAGIC  └───────────────┬──────────────────────┘
# MAGIC          ┌───────┴────────┐
# MAGIC          ▼                ▼
# MAGIC   ┌─────────────┐   ┌──────────────┐
# MAGIC   │ MLflow eval │   │ Genie space  │  nb 07 🧠 / nb 08
# MAGIC   │ (nb 07)     │   │ self-serve   │
# MAGIC   └─────────────┘   └──────────────┘            App → nb 09 (STRETCH)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📒 The notebooks
# MAGIC
# MAGIC Run them in order. Each one is self-contained and starts by `%run ./_config`.
# MAGIC
# MAGIC | # | Notebook | What it builds | Your job? |
# MAGIC |---|---|---|---|
# MAGIC | 01 | `01_data_foundation_omop` | Confirm & profile the 6 OMOP tables from the shared foundation | ✅ run + light TODO |
# MAGIC | 02 | `02_silver_feature_pipeline` | **Silver feature views** (HER2/ER/PR pivot, therapy, demographics) | 🛠️ build the pivots |
# MAGIC | 03 | `03_exploratory_data_analysis` | EDA — quantify & visualize the notes-only gap | 🛠️ light TODO |
# MAGIC | 04 | `04_nlp_biomarker_extraction` | `ai_query` + Foundation Models over `note_text` | 🧠 the GenAI core |
# MAGIC | 05 | `05_clinicalbert_mlflow_uc` | ClinicalBERT registered to Unity Catalog via MLflow | ✅ pre-built, optional |
# MAGIC | 06 | `06_gold_unified_prescreen` | Gold unified profile + Trial A/B pre-screen | 🛠️ build the fusion |
# MAGIC | 07 | `07_mlflow_evaluation_runs` | MLflow eval: prompt × model vs. ground truth | 🧠 build the eval |
# MAGIC | 08 | `08_genie_space_setup` | A Genie space for self-serve cohort questions | ✅ guided setup |
# MAGIC | 09 | `09_app_TODO` | Coordinator app (stretch) | 🚀 stretch |

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Prerequisites
# MAGIC
# MAGIC - A Unity Catalog–enabled workspace and permission to create a catalog/schema (your bundle's
# MAGIC   `client_catalog` / `client_schema`).
# MAGIC - **Serverless** notebook compute.
# MAGIC - Access to the **Foundation Model** endpoints (`databricks-claude-haiku-4-5`,
# MAGIC   `databricks-claude-sonnet-4-6`) — used by notebooks 04 and 07.
# MAGIC - The 6 OMOP tables already exist. They are stood up once by the shared foundation (the
# MAGIC   `foundation/` bundle, which lands them in `clinops_foundation`) and this kit reads them
# MAGIC   read-only from your `source_schema`.
# MAGIC - You ran `databricks bundle deploy --target client` to sync these notebooks. See the README.
# MAGIC - Set the widgets below to match your bundle, then open **`01_data_foundation_omop`**.

# COMMAND ----------

# DBTITLE 1,Set your targets here (these flow to every notebook)
# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## ▶️ Next step
# MAGIC
# MAGIC ### → Open **[01_data_foundation_omop]($./01_data_foundation_omop)** to generate the synthetic OMOP data.
