# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 03 · ROW FILTERS + ABAC · 🧠 THE FILTER CORE — YOU BUILD THIS</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🚧 Filter the rows by group</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Masks hide <i>columns</i>; row filters hide <i>rows</i>. An OCDO researcher should only see the
# MAGIC     patients their group is entitled to — and never even know the others exist. Same table, fewer
# MAGIC     rows. <b>This is the second half of Josh's ask: filter access by OCDO user group.</b>
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## How UC row filters work
# MAGIC
# MAGIC A **row filter** is a SQL UDF returning a boolean, bound to a table. UC evaluates it for every row;
# MAGIC rows where it returns `FALSE` simply disappear from the caller's result — no error, no hint they
# MAGIC existed. Like masks, it's enforced everywhere (SQL, Genie, apps, BI) and gates on
# MAGIC `is_account_group_member(...)`.
# MAGIC
# MAGIC **Our scenario:** the data office has flagged a subset of patients as **research-consented**. OCDO
# MAGIC researchers may only see consented patients; the data office sees everyone. We model consent
# MAGIC synthetically with a `consent` table you'll build, then a filter that lets the group through only
# MAGIC for consented `person_id`s.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# DBTITLE 1,Build a synthetic research-consent set (PRE-BUILT — ~70% of patients consented)
# In a real warehouse this comes from your consent system; here we synthesize it deterministically.
spark.sql(f"""
  CREATE OR REPLACE TABLE {fqn('research_consent')} AS
  SELECT person_id, (person_id % 10 < 7) AS research_consented
  FROM {fqn('person')}
""")
display(spark.sql(f"""
  SELECT research_consented, COUNT(*) AS n FROM {fqn('research_consent')} GROUP BY research_consented
"""))

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🔑 The row-filter pattern you need (read before you build)
# MAGIC
# MAGIC The filter UDF takes the **columns it needs to decide** and returns a boolean:
# MAGIC
# MAGIC ```sql
# MAGIC CREATE OR REPLACE FUNCTION consent_row_filter(pid BIGINT)
# MAGIC RETURN
# MAGIC   -- data office (not in the OCDO group): see every row
# MAGIC   NOT is_account_group_member('ocdo_data_scientists')
# MAGIC   -- OCDO researcher: only rows whose person_id is research-consented
# MAGIC   OR pid IN (SELECT person_id FROM research_consent WHERE research_consented);
# MAGIC
# MAGIC ALTER TABLE person SET ROW FILTER consent_row_filter ON (person_id);
# MAGIC ```
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The gotcha:</b> the <code>ON (person_id)</code> clause names which column(s) feed the function —
# MAGIC they must exist on the table you bind to. Bind the same filter to every table that has a
# MAGIC <code>person_id</code> and the whole cohort is filtered consistently. The filter must return
# MAGIC <code>TRUE</code> for the data office (else <i>you</i> lose all rows too) — that's the
# MAGIC <code>NOT is_account_group_member(...)</code> branch.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Build the row-filter UDF 🧠 (GA — this is the core)

# COMMAND ----------

# DBTITLE 1,TODO — create the consent row-filter UDF
# TODO (you build this): create `consent_row_filter(pid BIGINT) RETURNS BOOLEAN` that returns TRUE for
#   non-OCDO-group callers (the data office sees all rows), and for OCDO_GROUP members returns TRUE only
#   when pid is a consented person. Use is_account_group_member('<group>') and a subquery against
#   research_consent. Interpolate OCDO_GROUP + fqn('research_consent').
#
# Skeleton:
# spark.sql(f"""
#   CREATE OR REPLACE FUNCTION {fqn('consent_row_filter')}(pid BIGINT)
#   RETURN
#     NOT is_account_group_member('{OCDO_GROUP}')
#     OR pid IN (SELECT person_id FROM {fqn('research_consent')} WHERE research_consented)
# """)

# COMMAND ----------

# DBTITLE 1,TODO — bind the row filter to the patient tables
# TODO (you build this): apply the filter with ALTER TABLE ... SET ROW FILTER ... ON (person_id).
#   Bind it to person, condition_occurrence, measurement, observation, drug_exposure, note — every
#   table keyed by person_id — so a researcher's cohort is consistent across joins.
#
# Skeleton (loop OMOP_TABLES):
# for t in OMOP_TABLES:
#     spark.sql(f"ALTER TABLE {fqn(t)} SET ROW FILTER {fqn('consent_row_filter')} ON (person_id)")
#     print(f"row filter bound on {t}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Prove it — row counts by who's asking (PRE-BUILT verification)

# COMMAND ----------

# DBTITLE 1,How many rows would YOU see vs. an OCDO researcher? (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT
# MAGIC   current_user()                                 AS me,
# MAGIC   is_account_group_member('${ocdo_group}')      AS in_ocdo_group,
# MAGIC   (SELECT COUNT(*) FROM person)                  AS person_rows_you_see,
# MAGIC   (SELECT COUNT(*) FROM research_consent WHERE research_consented) AS consented_total;
# MAGIC -- If you're NOT in the OCDO group you see all 300; a researcher sees only the consented subset.

# COMMAND ----------

# DBTITLE 1,Confirm the row filters are registered (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT table_name, filter_name
# MAGIC FROM information_schema.row_filters
# MAGIC WHERE table_schema = current_schema()
# MAGIC ORDER BY table_name;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 3️⃣ STRETCH / EXTENSION — Tag-based ABAC (attribute-based access control)
# MAGIC
# MAGIC <div style="background:#EDE7F6; border-left:6px solid #5E35B1; padding:12px 16px; border-radius:4px">
# MAGIC Everything above is the <b>GA</b> per-table row-filter/mask path — it always works. UC also offers
# MAGIC <b>tag-based ABAC policies</b>: write the mask/filter logic <b>once</b> and have UC apply it to
# MAGIC <i>every column or table carrying a given tag</i> (the <code>phi=other_identifier</code> tags from
# MAGIC nb 01). One policy, whole-catalog coverage — the governance dream.
# MAGIC <br><br>
# MAGIC <b>This is a newer / preview feature and may not be enabled on your workspace.</b> Attempt the cell
# MAGIC below; if it errors with "feature not enabled" / unknown syntax, that's expected — fall back to the
# MAGIC GA path above (which already covers Josh's ask) and note it as a preview to request. See ANSWER_KEY.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,EXTENSION (optional) — one ABAC policy over all PHI-tagged columns
# EXTENSION (optional): tag-based ABAC. The exact DDL is evolving; the *intent* is:
#   "for any column tagged phi=other_identifier, apply mask_person_id-style redaction to OCDO_GROUP."
# Attempt it and CATCH the error so the notebook still runs green if the feature is gated.
try:
    spark.sql(f"""
      CREATE POLICY redact_direct_identifiers
      ON CATALOG {CATALOG}
      COMMENT 'Mask any column tagged phi=other_identifier for OCDO researchers'
      COLUMN MASK {fqn('mask_person_id')}
      TO `{OCDO_GROUP}`
      FOR TABLES
      MATCH COLUMNS hasTagValue('phi', 'other_identifier') AS pid
      ON COLUMN pid
    """)
    show_md("<b>✅ ABAC policy created</b> — tag-driven masking is enabled on this workspace.")
except Exception as e:
    show_md(
        "<b>ℹ️ Tag-based ABAC not available here</b> (expected on many workspaces — it's preview). "
        f"Falling back to the GA per-table path above, which fully covers the ask.<br>"
        f"<code>{str(e)[:300]}</code><br>Document this as a preview feature to request for FH. "
        "See <code>reference/ANSWER_KEY.md</code> → nb 03 for the current syntax to retry."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just did:</b> a researcher now sees only the patients they're entitled to, masked where
# MAGIC it counts — and the policy follows the data into every tool. Combined with nb 02, that's Josh's full
# MAGIC ask: <b>mask patient data AND filter access by OCDO user group.</b>
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[04_phi_identifier_search]($./04_phi_identifier_search)** to find everywhere a patient identifier appears.
