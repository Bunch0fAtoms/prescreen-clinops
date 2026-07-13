# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:28px 32px; border-radius:8px">
# MAGIC   <div style="font-size:0.95em; letter-spacing:2px; opacity:0.85">NOTEBOOK 08 · GENIE SPACE · COMPLETED</div>
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
# MAGIC This notebook **teaches you to build the space**: prepare the tables, stand up the space, then
# MAGIC teach it the vocabulary and trusted SQL that make it accurate. Step 4 also shows a one-prompt way
# MAGIC to have Genie Code build the whole space for you.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🏷️ Step 1: Make the tables legible to Genie (COMPLETED)
# MAGIC
# MAGIC Genie reads your **table and column comments** as the primary signal for what each field means.
# MAGIC Good comments are the single highest-leverage accuracy lever. `gold_trial_prescreen` is **LONG**
# MAGIC (one row per patient per trial), so we describe that shape: a `trial_id`, an `eligible` flag, and a
# MAGIC `reason`, plus the biomarker fields.

# COMMAND ----------

# DBTITLE 1,Describe the gold_trial_prescreen table & its key columns (COMPLETED, long shape)
# MAGIC %sql
# MAGIC COMMENT ON TABLE gold_trial_prescreen IS
# MAGIC   'Clinical-trial pre-screening cohort. LONG shape: one row per patient per trial. Each row says whether that patient is eligible for that trial and why, with the final HER2/ER/PR status (structured or NLP-recovered) and a data-provenance flag.';
# MAGIC
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN person_id         COMMENT 'OMOP person identifier, one patient.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN trial_id          COMMENT 'Trial code: A = HER2-positive, B = ER-positive/HER2-negative/postmenopausal, C = triple-negative.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN trial_name        COMMENT 'Human-readable trial name.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN eligible          COMMENT 'TRUE if this patient meets every criterion for this trial.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN reason            COMMENT 'Plain-English explanation of why the patient is or is not eligible for this trial.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN her2_status       COMMENT 'Final HER2 status: Positive, Negative, or Unknown.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN er_status         COMMENT 'Final estrogen-receptor (ER) status: Positive, Negative, or Unknown.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN pr_status         COMMENT 'Final progesterone-receptor (PR) status: Positive, Negative, or Unknown.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN biomarker_source  COMMENT 'Where the biomarker status came from: "structured" = from the measurement table; "nlp" = recovered from a free-text pathology note by a Foundation Model (invisible to plain SQL).';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN age_at_dx_years   COMMENT 'Patient age in years at the time of cancer diagnosis.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN menopausal_status COMMENT 'Menopausal status, e.g. Premenopausal or Postmenopausal. Trial B requires Postmenopausal.';
# MAGIC ALTER TABLE gold_trial_prescreen ALTER COLUMN prior_anti_her2   COMMENT 'TRUE if the patient already received anti-HER2 therapy (e.g. trastuzumab). Trial A excludes these.';

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🛠️ Step 2: Create the Genie space (PRE-BUILT UI steps)
# MAGIC
# MAGIC This part happens in the Databricks UI (~2 min):
# MAGIC
# MAGIC 1. Left sidebar → **Genie** → **+ New**.
# MAGIC 2. Name it **`Clinical Trial Pre-Screening`**; describe it
# MAGIC    (*"Ask about patient eligibility for the HER2+ (Trial A), ER+/HER2− (Trial B), and triple-negative (Trial C) trials."*).
# MAGIC 3. Pick the **SQL warehouse** from your `warehouse_id` widget (printed below).
# MAGIC 4. Under **Tables**, add the gold tables from `{catalog}.{schema}`:
# MAGIC    `gold_trial_prescreen`, `gold_unified_biomarker_profile`, `silver_demographics`.
# MAGIC 5. **Save**, the space is live.
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>Keep the table count tight.</b> Genie is most accurate with a small, well-described set. Three
# MAGIC is plenty. Step 4 below walks you through the instructions and trusted SQL that make the space
# MAGIC accurate, including a one-prompt way to have Genie Code build the whole space for you.
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
# MAGIC ## 🎯 Step 3: Verify the answers before you demo (COMPLETED)
# MAGIC
# MAGIC Run the SQL you *expect* Genie to generate so you can confirm its number is right.

# COMMAND ----------

# DBTITLE 1,Verify: how many patients are eligible for Trial A? (COMPLETED)
# MAGIC %sql
# MAGIC -- The number Genie should return for "How many patients are eligible for Trial A?"
# MAGIC SELECT COUNT(*) AS trial_a_eligible
# MAGIC FROM gold_trial_prescreen
# MAGIC WHERE trial_id = 'A' AND eligible = TRUE;

# COMMAND ----------

# DBTITLE 1,Verify: Trial A-eligible patients found ONLY via pathology-note NLP (the headline) (COMPLETED)
# MAGIC %sql
# MAGIC -- The patients invisible to a structured query. The headline demo question.
# MAGIC SELECT COUNT(*) AS trial_a_eligible_via_nlp
# MAGIC FROM gold_trial_prescreen
# MAGIC WHERE trial_id = 'A' AND eligible = TRUE AND biomarker_source = 'nlp';

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Step 4: Teach the space to answer accurately (instructions + trusted SQL)
# MAGIC
# MAGIC The space works now, but two settings turn a decent Genie into an accurate one. Both live under
# MAGIC the space's **Instructions / Knowledge** panel. You are teaching Genie the vocabulary of your data.
# MAGIC
# MAGIC - **General instructions**: plain-language rules. What "eligible" means, that `biomarker_source =
# MAGIC   'nlp'` was recovered from a note, the valid status strings, and that the table is one row per
# MAGIC   patient per trial so you filter by `trial_id`.
# MAGIC - **Trusted example SQL**: two or three verified queries, each saved with a plain-English title.
# MAGIC   Genie generalizes from them, so this is the single strongest accuracy boost.

# COMMAND ----------

# MAGIC %md
# MAGIC ### ⚡ The fast way: let Genie Code build the space for you
# MAGIC
# MAGIC A community skill, **`prompt-to-genie`**, stands up a whole Genie space from one plain-English
# MAGIC prompt: tables, descriptions, sample questions, and trusted SQL. Install it once at the workspace
# MAGIC level, then just describe the space you want.
# MAGIC
# MAGIC **Install once** (in a workspace **web terminal**, it authenticates as you):
# MAGIC
# MAGIC ```bash
# MAGIC databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
# MAGIC   --path /Workspace/.assistant/skills/prompt-to-genie
# MAGIC ```
# MAGIC
# MAGIC Or from the UI: **Workspace → Create → Git folder**, URL
# MAGIC `https://github.com/sean-zhang-dbx/prompt-to-genie.git`, destination
# MAGIC `/Workspace/.assistant/skills/prompt-to-genie`.
# MAGIC
# MAGIC **Then open a Genie Code chat and paste a starter prompt like this:**
# MAGIC
# MAGIC > Build a Genie space named **"Breast Cancer Biomarker & Trial Eligibility"** over my
# MAGIC > `gold_trial_prescreen`, `gold_unified_biomarker_profile`, and `silver_demographics` tables.
# MAGIC > `gold_trial_prescreen` is LONG: one row per (`person_id`, `trial_id`) with an `eligible` flag, a
# MAGIC > `reason`, and a `biomarker_source` that is `'structured'` or `'nlp'`. Add clear table and column
# MAGIC > descriptions, seed these sample questions, and save trusted SQL for them: (1) how many patients
# MAGIC > are eligible for each trial, (2) how many Trial A patients were found only via pathology-note
# MAGIC > NLP, (3) the eligible breakdown by biomarker source.
# MAGIC
# MAGIC A good follow-up prompt, once the space exists:
# MAGIC
# MAGIC > Turn on entity matching for `trial_id`, `her2_status`, `er_status`, `pr_status`, and
# MAGIC > `biomarker_source`, and add a join on `person_id` between the three tables.
# MAGIC
# MAGIC Review each proposal before you accept it, the same as any Genie Code edit. That one prompt gets
# MAGIC you a space with all three accuracy levers already in place.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🔍 What "good" looks like (so you can check the result, or build it by hand)
# MAGIC
# MAGIC Whether Genie Code built it or you are doing it in the UI, this is the content that makes the
# MAGIC space accurate. Paste this into the **Instructions** panel. It is the vocabulary Genie needs:
# MAGIC
# MAGIC ```text
# MAGIC You answer questions about breast-cancer clinical-trial PRE-SCREENING over governed Unity Catalog
# MAGIC gold tables. Synthetic data only, there is no PHI.
# MAGIC
# MAGIC gold_trial_prescreen is LONG: one row per (person_id, trial_id). To count distinct patients use
# MAGIC COUNT(DISTINCT person_id); to count eligible for a trial, filter trial_id and eligible = TRUE.
# MAGIC
# MAGIC TRIALS: A = HER2-positive; B = ER-positive / HER2-negative / postmenopausal; C = triple-negative.
# MAGIC ELIGIBILITY: eligible is a boolean; reason gives the plain-English explanation.
# MAGIC PROVENANCE: biomarker_source = 'structured' came from coded lab data; 'nlp' was recovered from a
# MAGIC free-text pathology note by an AI model, so those patients are invisible to a structured-only query.
# MAGIC STATUS values are the strings 'Positive', 'Negative', or 'Unknown' for her2_status, er_status, pr_status.
# MAGIC ```
# MAGIC
# MAGIC Then save two or three **trusted queries**, each with a plain-English title. Genie learns the most
# MAGIC from these:
# MAGIC
# MAGIC | Save it with this title | The SQL |
# MAGIC |---|---|
# MAGIC | *Eligible patients per trial* | `SELECT trial_id, trial_name, COUNT(*) AS eligible_patients FROM gold_trial_prescreen WHERE eligible = TRUE GROUP BY trial_id, trial_name ORDER BY trial_id` |
# MAGIC | *Trial A patients found only via NLP* | `SELECT COUNT(*) AS nlp_recovered_eligible FROM gold_trial_prescreen WHERE trial_id = 'A' AND eligible = TRUE AND biomarker_source = 'nlp'` |
# MAGIC | *Eligible breakdown by biomarker source* | `SELECT trial_id, biomarker_source, COUNT(*) AS eligible_patients FROM gold_trial_prescreen WHERE eligible = TRUE GROUP BY trial_id, biomarker_source ORDER BY trial_id, biomarker_source` |
# MAGIC
# MAGIC The pattern to learn: describe the table shape and the vocabulary in the instructions, then show
# MAGIC Genie two or three correct queries. Those two levers, on top of the column comments from Step 1,
# MAGIC are what make a Genie space trustworthy.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## ✅ Takeaway
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:16px 20px; border-radius:6px">
# MAGIC The trial coordinator can now <b>self-serve every cohort question</b>: counts, lists, eligibility,
# MAGIC even "who was found only in the notes", in plain English, on governed, permissioned data, with no
# MAGIC SQL and no engineer in the loop.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open the **[coordinator app]($../../app/README)** (`app/`) for the point-and-click pre-screening UI.
