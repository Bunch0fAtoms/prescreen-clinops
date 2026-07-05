# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 02 · COLUMN MASKS · 🧠 THE MASKING CORE — YOU BUILD THIS</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🎭 Mask the identifiers by group</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Same <code>SELECT person_id, note_text FROM …</code> — the data office sees the real value, an
# MAGIC     OCDO researcher sees <code>***MASKED***</code>. The gate is a function you write, applied to the
# MAGIC     column once and enforced everywhere. <b>This is Josh's core ask.</b>
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## How UC column masking works
# MAGIC
# MAGIC A **column mask** is a SQL UDF bound to a column. Whenever *anyone* reads that column — notebook,
# MAGIC SQL, Genie, an app, a BI tool — UC runs the function first and returns whatever it returns. The
# MAGIC function decides, per the **current user's group membership**, whether to reveal or redact.
# MAGIC
# MAGIC Two moving parts:
# MAGIC 1. A **masking UDF** — `mask_value(col)` → returns `col` if the caller is privileged, else a redacted value.
# MAGIC 2. **Binding** it: `ALTER TABLE … ALTER COLUMN … SET MASK <udf>`.
# MAGIC
# MAGIC The privilege test is `is_account_group_member('<group>')`. **Important nuance:** in UC, by default
# MAGIC the data owner / metastore admin **bypasses** masks (sees raw). So the cleanest way to *prove* a mask
# MAGIC works is to build it so the **owner is NOT in the OCDO group** → you-the-owner still see raw (bypass),
# MAGIC and the mask logic redacts for everyone who *is* in the group and *isn't* an owner. We also show an
# MAGIC explicit `current_user()` test so the demo is visible even to an owner.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# DBTITLE 1,Where do we stand before masking? (PRE-BUILT — the "before")
# MAGIC %sql
# MAGIC -- As the owner, raw values are visible. Note the real person_id and the raw note text.
# MAGIC SELECT person_id, LEFT(note_text, 80) AS note_preview
# MAGIC FROM note WHERE note_source_value = 'PATHOLOGY_REPORT' ORDER BY person_id LIMIT 5;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🔑 The masking pattern you need (read before you build)
# MAGIC
# MAGIC A mask UDF takes the column value and returns a value of the **same type**. Gate on group membership:
# MAGIC
# MAGIC ```sql
# MAGIC CREATE OR REPLACE FUNCTION mask_person_id(pid BIGINT)
# MAGIC RETURN CASE
# MAGIC   WHEN is_account_group_member('ocdo_data_scientists') THEN NULL   -- researcher: hide it
# MAGIC   ELSE pid                                                          -- data office: reveal
# MAGIC END;
# MAGIC
# MAGIC ALTER TABLE person ALTER COLUMN person_id SET MASK mask_person_id;
# MAGIC ```
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>Return type must match the column type.</b> For a string column like <code>note_text</code> you can
# MAGIC return a literal like <code>'***REDACTED PATHOLOGY NOTE***'</code>; for a <code>BIGINT</code> like
# MAGIC <code>person_id</code> you return <code>NULL</code> or a hashed surrogate (<code>NULL</code> is simplest).
# MAGIC The group name comes from the <code>ocdo_group</code> widget → <code>OCDO_GROUP</code> in <code>_config</code>.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Build the masking UDFs 🧠
# MAGIC
# MAGIC Two masks: `person_id` (a direct identifier on every table) and `note_text` (free-text PHI). Both
# MAGIC gate on `OCDO_GROUP`. Reveal to the data office; redact for the researcher group.

# COMMAND ----------

# DBTITLE 1,TODO — create the person_id masking UDF
# TODO (you build this): create a SQL UDF `mask_person_id(pid BIGINT) RETURNS BIGINT` that returns NULL
#   when the caller is a member of OCDO_GROUP, else returns pid. Use is_account_group_member('<group>').
#   Interpolate OCDO_GROUP from _config. Run it with spark.sql(f""" ... """).
#
# Skeleton:
# spark.sql(f"""
#   CREATE OR REPLACE FUNCTION {fqn('mask_person_id')}(pid BIGINT)
#   RETURN CASE WHEN is_account_group_member('{OCDO_GROUP}') THEN ___ ELSE ___ END
# """)

# COMMAND ----------

# DBTITLE 1,TODO — create the note_text masking UDF
# TODO (you build this): create `mask_note_text(txt STRING) RETURNS STRING` that returns a redaction
#   literal (e.g. '***REDACTED PATHOLOGY NOTE***') for OCDO_GROUP members, else the real txt.
#   Same is_account_group_member gate.

# COMMAND ----------

# DBTITLE 1,TODO — bind the masks to the columns
# TODO (you build this): apply the masks with ALTER TABLE ... ALTER COLUMN ... SET MASK.
#   • person.person_id        -> mask_person_id
#   • note.person_id          -> mask_person_id
#   • note.note_text          -> mask_note_text
#   (person_id is a direct identifier on EVERY table — EXTENSION below extends to all 6.)
#
# Skeleton:
# spark.sql(f"ALTER TABLE {fqn('person')} ALTER COLUMN person_id SET MASK {fqn('mask_person_id')}")
# spark.sql(f"ALTER TABLE {fqn('note')}   ALTER COLUMN person_id SET MASK {fqn('mask_person_id')}")
# spark.sql(f"ALTER TABLE {fqn('note')}   ALTER COLUMN note_text SET MASK {fqn('mask_note_text')}")
#
# EXTENSION (optional): bind mask_person_id to person_id on ALL 6 tables (loop over OMOP_TABLES),
#   so a researcher can never recover an identifier from any join.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Prove it — same query, masked vs. unmasked (PRE-BUILT verification)
# MAGIC
# MAGIC As the table owner you (likely) **bypass** the mask, so to make the effect visible regardless we
# MAGIC show two things: (a) the mask UDF's own decision for the **current user**, and (b) the actual
# MAGIC column projection. If you're not in `OCDO_GROUP`, (a) reveals; add yourself to the group (or have a
# MAGIC researcher run it) to watch it flip to redacted.

# COMMAND ----------

# DBTITLE 1,What would the mask do for YOU right now? (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT
# MAGIC   current_user()                                          AS me,
# MAGIC   is_account_group_member('${ocdo_group}')               AS in_ocdo_group,
# MAGIC   CASE WHEN is_account_group_member('${ocdo_group}')
# MAGIC        THEN 'REDACTED'  ELSE 'REVEALED' END               AS person_id_would_be,
# MAGIC   CASE WHEN is_account_group_member('${ocdo_group}')
# MAGIC        THEN 'REDACTED'  ELSE 'REVEALED' END               AS note_text_would_be;

# COMMAND ----------

# DBTITLE 1,The actual masked projection (PRE-BUILT)
# MAGIC %sql
# MAGIC -- This is the query a researcher runs. With the masks bound, person_id is NULL and note_text is the
# MAGIC -- redaction literal FOR THEM; for the data office (owner / non-group) the real values come through.
# MAGIC SELECT person_id, LEFT(note_text, 80) AS note_preview
# MAGIC FROM note WHERE note_source_value = 'PATHOLOGY_REPORT' ORDER BY note_id LIMIT 5;

# COMMAND ----------

# DBTITLE 1,Confirm the masks are registered on the columns (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT table_name, column_name, mask_name
# MAGIC FROM information_schema.column_masks
# MAGIC WHERE table_schema = current_schema()
# MAGIC ORDER BY table_name, column_name;

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just did:</b> bound a policy to the <i>column</i>, not the query — so a researcher can
# MAGIC run any SQL, open Genie, or hit an app, and the identifier is gone every time. That's the difference
# MAGIC between a governed warehouse and a hopeful one. <b>This satisfies Josh's "mask patient data by OCDO
# MAGIC user group."</b>
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[03_row_filters_abac]($./03_row_filters_abac)** to restrict which patient *rows* each group can see.
