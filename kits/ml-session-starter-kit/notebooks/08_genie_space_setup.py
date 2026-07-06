# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:28px 32px; border-radius:8px">
# MAGIC   <div style="font-size:0.95em; letter-spacing:2px; opacity:0.85">NOTEBOOK 08 · GENIE SPACE · ✅ GUIDED SETUP</div>
# MAGIC   <div style="font-size:2.3em; font-weight:700; margin-top:6px">💬 Self-Serve Cohort Questions with Genie</div>
# MAGIC   <div style="font-size:1.15em; margin-top:10px; max-width:880px; opacity:0.95">
# MAGIC     Hand the finished pre-screening tables to a research coordinator who has never written SQL,
# MAGIC     and let them ask <i>"How many patients are eligible for Trial A?"</i> in plain English.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💬 What is a Genie space?
# MAGIC
# MAGIC A **Genie space** is a natural-language analytics surface over a set of **governed Unity Catalog
# MAGIC tables** you choose. A user types a question; Genie writes the SQL, runs it on a warehouse, and
# MAGIC shows the answer. The user never sees a `JOIN`, and every query still runs against your
# MAGIC permissioned tables.
# MAGIC
# MAGIC This notebook is **setup guidance + curated content**: prepare the tables, then stand up the space
# MAGIC in the UI and seed it with the questions, instructions, and trusted SQL in `genie/`.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🏷️ Step 1: Make the tables legible to Genie (PRE-BUILT)
# MAGIC
# MAGIC Genie reads your **table and column comments** as the primary signal for what each field means.
# MAGIC Good comments are the single highest-leverage accuracy lever, so we describe `gold_trial_prescreen`
# MAGIC before creating the space. (These run against the table you built in nb 06.)

# COMMAND ----------

# DBTITLE 1,Describe the gold_trial_prescreen table & its key columns (PRE-BUILT)
# MAGIC %sql
# MAGIC COMMENT ON TABLE gold_trial_prescreen IS
# MAGIC   'One row per patient with their final HER2/ER/PR biomarker status (structured + NLP-recovered) and a TRUE/FALSE eligibility flag for each breast-cancer trial. The pre-screening cohort a coordinator works from.';
# MAGIC
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN person_id            COMMENT 'OMOP person identifier, one patient.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN her2_status          COMMENT 'Final HER2 status: Positive, Negative, or Unknown.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN er_status            COMMENT 'Final estrogen-receptor (ER) status: Positive, Negative, or Unknown.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN pr_status            COMMENT 'Final progesterone-receptor (PR) status: Positive, Negative, or Unknown.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN biomarker_source     COMMENT 'Where the biomarker status came from: "structured" = from the measurement table; "nlp" = recovered from a free-text pathology note by a Foundation Model (invisible to plain SQL).';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN age_at_dx_years      COMMENT 'Patient age in years at the time of cancer diagnosis.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN menopausal_status    COMMENT 'Menopausal status, e.g. Premenopausal or Postmenopausal. Trial B requires Postmenopausal.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN had_anti_her2_therapy COMMENT 'TRUE if the patient already received anti-HER2 therapy (e.g. trastuzumab). Trial A excludes these.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN trial_a_eligible     COMMENT 'TRUE if the patient meets all Trial A criteria: HER2 Positive, age 18-75, no prior anti-HER2 therapy.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN trial_b_eligible     COMMENT 'TRUE if the patient meets all Trial B criteria: ER Positive, HER2 Negative, postmenopausal, age 18-75.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN trial_a_reason       COMMENT 'Human-readable explanation of why the patient is or is not eligible for Trial A.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN trial_b_reason       COMMENT 'Human-readable explanation of why the patient is or is not eligible for Trial B.';

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🛠️ Step 2: Create the Genie space (PRE-BUILT UI steps)
# MAGIC
# MAGIC This part happens in the Databricks UI (~2 min):
# MAGIC
# MAGIC 1. Left sidebar → **Genie** → **+ New**.
# MAGIC 2. Name it **`Clinical Trial Pre-Screening`**; describe it
# MAGIC    (*"Ask about patient eligibility for the HER2+ (Trial A) and ER+/HER2− (Trial B) trials."*).
# MAGIC 3. Pick the **SQL warehouse** from your `warehouse_id` widget (printed below).
# MAGIC 4. Under **Tables**, add the gold tables from `{catalog}.{schema}`:
# MAGIC    `gold_trial_prescreen`, `gold_unified_biomarker_profile`, `silver_demographics`.
# MAGIC 5. **Save**, the space is live.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>Keep the table count tight.</b> Genie is most accurate with a small, well-described set. Three
# MAGIC is plenty. Resist adding every silver table. The exact instructions, sample questions, and
# MAGIC trusted SQL to paste into the space are in <code>genie/genie_space.md</code>.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,Copy these values into the Genie space setup form (PRE-BUILT)
show_md(f"""
<div style='background:#f4f6f9; border-left:6px solid #C8102E; padding:14px 18px; border-radius:6px'>
<b>Warehouse ID</b> (Step 3): <code>{WAREHOUSE_ID}</code><br>
<b>Tables to add</b> (Step 4):<br>
&nbsp;&nbsp;• <code>{fqn('gold_trial_prescreen')}</code><br>
&nbsp;&nbsp;• <code>{fqn('gold_unified_biomarker_profile')}</code><br>
&nbsp;&nbsp;• <code>{fqn('silver_demographics')}</code>
</div>
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Step 3: Verify the answers before you demo (YOU BUILD THESE)
# MAGIC
# MAGIC Run the SQL you *expect* Genie to generate so you can confirm its number is right. The full set of
# MAGIC curated questions + trusted example SQL lives in `genie/genie_space.md`, add them to the space.

# COMMAND ----------

# DBTITLE 1,TODO, verify: how many patients are eligible for Trial A?
# MAGIC %sql
# MAGIC -- TODO (you build this): COUNT patients where trial_a_eligible = TRUE in gold_trial_prescreen.
# MAGIC -- This is the number Genie should return for "How many patients are eligible for Trial A?"

# COMMAND ----------

# DBTITLE 1,TODO, verify: Trial A-eligible patients found ONLY via pathology-note NLP (the headline)
# MAGIC %sql
# MAGIC -- TODO (you build this): COUNT where trial_a_eligible = TRUE AND biomarker_source = 'nlp'.
# MAGIC -- WHY this one matters most: it's the patients invisible to a structured query, the headline
# MAGIC --   demo question. Verify the number so you can trust Genie's answer live.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Step 4: Add instructions & trusted SQL to the space (content in genie/)
# MAGIC
# MAGIC Two settings turn a decent Genie into an accurate one, both under the space's
# MAGIC **Instructions / Knowledge** panel:
# MAGIC - **General instructions**: plain-language rules (what "eligible" means, that `biomarker_source =
# MAGIC   'nlp'` was recovered from a note, the valid status strings).
# MAGIC - **Trusted example SQL**: save 2 to 3 verified queries with plain-English titles; Genie generalizes
# MAGIC   from them. This is the strongest accuracy boost.
# MAGIC
# MAGIC **Both are written for you in `genie/genie_space.md`. Copy them into the space.**

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## ✅ Takeaway
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:16px 20px; border-radius:6px">
# MAGIC The trial coordinator can now <b>self-serve every cohort question</b>: counts, lists, eligibility,
# MAGIC even "who was found only in the notes", in plain English, on governed, permissioned data, with no
# MAGIC SQL and no engineer in the loop.
# MAGIC </div>
# MAGIC
# MAGIC <!-- EXTENSION (optional): manage the Genie space as code via the Databricks SDK / REST API so it's
# MAGIC      reproducible across teams/workspaces. See the databricks-genie skill and STRETCH.md. -->
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[09_app_TODO]($./09_app_TODO)** for the stretch goal: a coordinator app over the cohort.
