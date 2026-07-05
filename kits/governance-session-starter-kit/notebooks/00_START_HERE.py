# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:28px 32px; border-radius:8px">
# MAGIC   <div style="font-size:0.95em; letter-spacing:2px; opacity:0.85">FRED HUTCHINSON CANCER CENTER · GOVERNANCE SESSION · STARTER KIT</div>
# MAGIC   <div style="font-size:2.3em; font-weight:700; margin-top:6px">🛡️ Governing PHI on OMOP with Unity Catalog</div>
# MAGIC   <div style="font-size:1.15em; margin-top:10px; max-width:900px; opacity:0.95">
# MAGIC     Classify the sensitive columns, mask patient identifiers, filter rows by OCDO researcher
# MAGIC     group, and prove who can see what — then answer the hard governance questions: where does a
# MAGIC     patient identifier appear, what limits exist on AI features, and who hasn't logged in for 90 days.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 👋 This is a starter kit — you build the governance
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:14px 18px; border-radius:4px">
# MAGIC The <b>plumbing is wired for you</b> — six synthetic OMOP tables (deep-cloned into your own
# MAGIC schema so you can't break anyone else's data), the PHI column map, helper functions, and the
# MAGIC verification harness that proves a policy actually changed what a user sees. <b>You</b> write the
# MAGIC learnable governance core: the masking UDFs, the row-filter functions, and the group-gating logic
# MAGIC that decides who sees a patient identifier and who sees <code>***MASKED***</code>.<br><br>
# MAGIC Look for <b><code>&#35; TODO (you build this)</code></b> markers — that's your work. Hooks marked
# MAGIC <b><code>&#35; EXTENSION (optional)</code></b> are stretch goals (see <code>STRETCH.md</code>).
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🩺 The business problem
# MAGIC
# MAGIC Fred Hutch's data office (OCDO/DASL) curates an OMOP clinical warehouse of breast-cancer patients.
# MAGIC Researchers need it to find trial cohorts — but **most of them must never see a patient identifier
# MAGIC or read a raw pathology note.** A breach, a SOC2 finding, or one over-broad grant is a
# MAGIC multi-million-dollar problem. So the data office's job is: **let researchers do science on this
# MAGIC data without ever exposing PHI they don't need.**
# MAGIC
# MAGIC Unity Catalog gives you the controls to do exactly that, *in the data layer* — so the policy holds
# MAGIC no matter who queries (notebook, SQL, Genie, an app, BI). This session builds them:
# MAGIC
# MAGIC | Control | What it does | Notebook |
# MAGIC |---|---|---|
# MAGIC | **Tags / classification** | Label every PHI column so policy & audit can find it | `01` |
# MAGIC | **Column masks** | A researcher sees `***MASKED***` where the owner sees `person_id` / `note_text` | `02` |
# MAGIC | **Row filters + ABAC** | A group only sees the *rows* (patients) it's entitled to | `03` |
# MAGIC | **Identifier search** | Find everywhere a patient identifier appears across catalogs | `04` |
# MAGIC | **AI-feature governance** | Know the limits before you turn on Genie / AI functions on PHI | `05` |
# MAGIC | **Inactive-user audit** | Surface accounts dormant >90 days (least-privilege hygiene) | `06` |

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## ✨ The value moment: same query, different eyes
# MAGIC
# MAGIC The whole point of UC governance is that **the policy lives with the data, not the query.** After
# MAGIC you build nb 02 and nb 03, the *exact same* `SELECT * FROM person` returns:
# MAGIC
# MAGIC <div style="display:flex; gap:14px; flex-wrap:wrap; margin-top:8px">
# MAGIC   <div style="flex:1; min-width:260px; background:#E3F2FD; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.2em; font-weight:700; color:#1565C0">👩‍⚕️ Data owner (you)</div>
# MAGIC     sees <code>person_id = 1042</code>, the full <code>note_text</code>, every row.<br>
# MAGIC     → the office that <i>governs</i> the data.
# MAGIC   </div>
# MAGIC   <div style="flex:1; min-width:260px; background:#FFEBEE; border-radius:6px; padding:14px">
# MAGIC     <div style="font-size:1.2em; font-weight:700; color:#C62828">🔬 OCDO researcher</div>
# MAGIC     sees <code>person_id = ***MASKED***</code>, a redacted note, and only the rows their group is
# MAGIC     entitled to.<br>→ does the science, never touches raw PHI.
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC The gate is <code>is_account_group_member('ocdo_data_scientists')</code> evaluated <b>inside</b> the
# MAGIC mask / filter function. You write that logic — that's the learnable "aha" of this session.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🏗️ Architecture & flow
# MAGIC
# MAGIC ```
# MAGIC  ┌─────────────────────────────┐
# MAGIC  │  6 OMOP CDM tables           │  person · condition_occurrence · measurement
# MAGIC  │  (synthetic, deep-cloned)    │  observation · drug_exposure · note
# MAGIC  └──────────────┬──────────────┘  (PRE-BUILT — your own clinops_gov schema)
# MAGIC                 │
# MAGIC                 ▼
# MAGIC  ┌─────────────────────────────┐
# MAGIC  │ 01 · DISCOVER & CLASSIFY     │  scan the 6 tables, apply UC tags to every PHI column
# MAGIC  │     (Day-1 shared anchor)    │  → information_schema now KNOWS what's sensitive
# MAGIC  └──────────────┬──────────────┘
# MAGIC       ┌─────────┴─────────┐
# MAGIC       ▼                   ▼
# MAGIC  ┌──────────┐        ┌──────────────┐
# MAGIC  │ 02 MASKS │        │ 03 ROW FILTER│   gate by is_account_group_member(...)
# MAGIC  │  🧠 you  │        │  + ABAC 🧠 you│
# MAGIC  └────┬─────┘        └──────┬───────┘
# MAGIC       └──────────┬──────────┘
# MAGIC                  ▼  PROVE IT: owner view vs. masked/filtered projection
# MAGIC  ┌─────────────────────────────────────────────────────────────┐
# MAGIC  │ The governance questions (system tables / information_schema) │
# MAGIC  │  04 where does an identifier appear?  05 AI-feature limits     │
# MAGIC  │  06 inactive users > 90 days                                  │
# MAGIC  └─────────────────────────────────────────────────────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📒 The notebooks
# MAGIC
# MAGIC Run them in order. Each one is self-contained and starts by `%run ./_config`.
# MAGIC
# MAGIC | # | Notebook | What it builds | Your job? |
# MAGIC |---|---|---|---|
# MAGIC | 01 | `01_discover_and_classify` | Scan 6 tables, apply UC **tags** to every PHI column | 🛠️ classify the columns |
# MAGIC | 02 | `02_column_masks` | **Column masks** on `person_id` / `note_text` by OCDO group | 🧠 the masking core |
# MAGIC | 03 | `03_row_filters_abac` | **Row filters** + tag-based **ABAC** by group | 🧠 the filter core |
# MAGIC | 04 | `04_phi_identifier_search` | Where does a patient identifier appear across catalogs? | 🛠️ build the search |
# MAGIC | 05 | `05_ai_feature_governance` | Genie / AI-function restrictions & limits on PHI | ✅ guided + light TODO |
# MAGIC | 06 | `06_inactive_users_report` | Users inactive > 90 days via system tables | 🛠️ build the audit |

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Prerequisites
# MAGIC
# MAGIC - A Unity Catalog–enabled workspace; you are an **owner/admin** of the catalog/schema you'll govern
# MAGIC   (you must own a table to put a mask or row filter on it).
# MAGIC - **Serverless** notebook compute (or a UC-enabled SQL warehouse for the `%sql` cells).
# MAGIC - The 6 OMOP tables exist in your `schema` (deep-cloned by the setup step — see README).
# MAGIC - An **account group** to gate on — default `ocdo_data_scientists`. It does **not** need members for
# MAGIC   the build; `is_account_group_member()` returns FALSE for you (the owner) if you're not in it, which
# MAGIC   is exactly how you'll *prove* a mask works. Set the `ocdo_group` widget to a real group if you have one.
# MAGIC - For nb 06: read access to **`system.access.audit`** (enable the `system.access` schema if it isn't).
# MAGIC - Set the widgets below to match your bundle, then open **`01_discover_and_classify`**.

# COMMAND ----------

# DBTITLE 1,Set your targets here (these flow to every notebook)
# MAGIC %run ./_config

# COMMAND ----------

# DBTITLE 1,Foundation check — confirm the 6 governed tables are present
missing = [t for t in OMOP_TABLES if not spark.catalog.tableExists(fqn(t))]
if missing:
    raise Exception(
        f"❌ Missing tables in {CATALOG}.{SCHEMA}: {missing}. "
        "Run the deep-clone setup from the README first (see README → 'How to deploy')."
    )
counts = {t: spark.table(fqn(t)).count() for t in OMOP_TABLES}
show_md(
    "<b>✅ Foundation present.</b> Row counts: "
    + " · ".join(f"<code>{t}</code>={n}" for t, n in counts.items())
    + "<br>Expected ≈ person 300 · condition_occurrence 300 · measurement 720 · "
      "observation 720 · drug_exposure 383 · note 265."
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ▶️ Next step
# MAGIC
# MAGIC ### → Open **[01_discover_and_classify]($./01_discover_and_classify)** to scan the tables and tag every PHI column.
