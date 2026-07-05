# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 05 · AI-FEATURE GOVERNANCE · FH ASK (GINA #5)</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🤖 Governing AI over PHI</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     What limits exist when you enable AI features (Genie, AI functions, model serving) on a PHI
# MAGIC     warehouse — and how do the controls you already built (masks, filters, tags) carry into them?
# MAGIC     "Test before expand": prove the guardrails hold before you widen access.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## The question Gina and Ty are really asking
# MAGIC
# MAGIC Fred Hutch is AI-cautious by policy (post-breach, mid-SOC2, co-founder of the Cancer AI Alliance's
# MAGIC "AI without sharing patient data"). So before turning on Genie or `ai_query` over OMOP, the data
# MAGIC office needs to know: **what guardrails apply, and what's the blast radius if we're wrong?**
# MAGIC
# MAGIC The reassuring answer — and the thing to *prove* in this notebook — is that **AI features are
# MAGIC governed by the same UC controls you already built.** Genie and `ai_query` run *as the calling user*,
# MAGIC through the same column masks and row filters. They are not a side door around governance.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ The limits, concretely (PRE-BUILT reference)
# MAGIC
# MAGIC | AI feature | What governs it | The limit / guardrail |
# MAGIC |---|---|---|
# MAGIC | **Genie spaces** | Runs SQL **as the user**; honors masks + row filters; scoped to tables you grant | A researcher's Genie sees masked `person_id`; can't query tables they lack `SELECT` on |
# MAGIC | **`ai_query` / AI functions** | Run in-engine as the user; need `SELECT` on the data + access to the FM endpoint | Sends column values to the model endpoint — so **mask first**, then let AI read the masked view |
# MAGIC | **Model serving / FM API** | Endpoint-level `CAN_QUERY` grants; per-endpoint rate limits & logging | Access is a UC/permission grant, not implicit; usage is auditable in system tables |
# MAGIC | **Vector Search** | Index inherits source-table grants | Don't index a column that should be masked — the index would expose it |
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The key design rule:</b> AI reads what the <i>user</i> can read. So if <code>note_text</code> is
# MAGIC masked for researchers (nb 02), a researcher's <code>ai_query</code> over <code>note_text</code>
# MAGIC sees the redaction — <b>not</b> the raw note. Govern the data once; the AI features inherit it. The
# MAGIC failure mode to avoid: a privileged service principal running AI over <i>raw</i> PHI and writing the
# MAGIC output to a table researchers can read. Govern the <i>output</i> too.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Prove it — AI reads through the mask (PRE-BUILT)
# MAGIC
# MAGIC `ai_query` runs as you. Whatever the mask gives *you* for `note_text` is what the model receives. Run
# MAGIC this; if you've added yourself to the OCDO group, the model literally cannot see the raw note — the
# MAGIC mask redacted it before `ai_query` ran. (Uses a small FM endpoint; skip if FM access is gated.)

# COMMAND ----------

# DBTITLE 1,What does ai_query actually receive for a masked column? (PRE-BUILT)
# MAGIC %sql
# MAGIC -- We feed note_text to the model. With nb 02's mask in force for an OCDO researcher, the input the
# MAGIC -- model sees is the redaction literal, not PHI. For the data office, it's the real note.
# MAGIC SELECT
# MAGIC   person_id,
# MAGIC   LEFT(note_text, 60)                                    AS what_ai_would_receive,
# MAGIC   ai_query('databricks-claude-haiku-4-5',
# MAGIC            'In 5 words, what kind of document is this: ' || LEFT(note_text, 400)) AS ai_says
# MAGIC FROM note
# MAGIC WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC ORDER BY note_id
# MAGIC LIMIT 3;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Who can call the AI endpoints? 🛠️ (light TODO — make access auditable)
# MAGIC
# MAGIC Enabling AI responsibly means knowing **who can call which model endpoint**. System tables record
# MAGIC serving-endpoint usage; grants are visible per endpoint. Surface it so "test before expand" has data.

# COMMAND ----------

# DBTITLE 1,TODO — surface model-serving usage from system tables
# TODO (you build this): query system.serving.endpoint_usage (or system.access.audit filtered to
#   serving actions) to show WHO called WHICH model endpoint, how often, in the last 30 days. Group by
#   user + endpoint. This is the "who is using AI on our data" report.
#
# Skeleton (endpoint_usage shape varies by workspace — adapt columns; fall back to audit if absent):
# display(spark.sql("""
#   SELECT requester AS user, served_entity_name AS endpoint, COUNT(*) AS calls
#   FROM system.serving.endpoint_usage
#   WHERE usage_start_time >= current_date() - INTERVAL 30 DAYS
#   GROUP BY requester, served_entity_name
#   ORDER BY calls DESC
# """))
#
# EXTENSION (optional): join to your masked tables' lineage so you can say "this endpoint was called
#   against a table that still contains direct identifiers" — a true test-before-expand red flag.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ A checklist before you flip AI on for FH (PRE-BUILT)
# MAGIC
# MAGIC 1. **Classify first (nb 01)** — you can't decide what AI may touch until PHI is tagged.
# MAGIC 2. **Mask + filter first (nb 02/03)** — so AI inherits redaction; never enable AI on raw PHI for a
# MAGIC    broad group.
# MAGIC 3. **Grant FM endpoints explicitly** — `CAN_QUERY` per group, not workspace-wide; log usage (step 3).
# MAGIC 4. **Govern AI *outputs*** — a derived table from `ai_query` over notes can re-introduce PHI; tag &
# MAGIC    mask it like any other (run nb 01's classify over the new table).
# MAGIC 5. **Start narrow, expand on evidence** — pilot with one group + masked data, watch the audit, widen.

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just established:</b> AI features are not a governance bypass — they ride the same UC
# MAGIC masks, row filters, and grants. The limits are real and they're the <i>right</i> limits. That's the
# MAGIC "test before expand" story FH wants, with evidence. <b>This answers Gina and Ty's AI-governance ask (#5).</b>
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[06_inactive_users_report]($./06_inactive_users_report)** for the dormant-account audit.
