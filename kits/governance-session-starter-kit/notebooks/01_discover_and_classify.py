# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 01 · DISCOVER & CLASSIFY · DAY-1 SHARED ANCHOR</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🔎 Find the PHI, then label it</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     You can't govern what you haven't classified. Scan the 6 OMOP tables, decide which columns
# MAGIC     are direct identifiers / quasi-identifiers / clinical PHI, and stamp them with Unity Catalog
# MAGIC     <b>tags</b>, so every downstream policy (and every auditor) can find them.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why classification comes first
# MAGIC
# MAGIC Masks (nb 02) and row filters (nb 03) are only as good as your knowledge of *what to protect*.
# MAGIC In a real OMOP warehouse with dozens of tables, "which columns hold PHI?" is the first question an
# MAGIC auditor asks, and the hardest to answer by eye. Unity Catalog **tags** make the answer queryable:
# MAGIC once a column is tagged `phi=direct_identifier`, you can find every such column across the whole
# MAGIC catalog with one query against `information_schema`, drive ABAC policies off it (nb 03), and prove
# MAGIC coverage to a reviewer.
# MAGIC
# MAGIC This notebook is the **Day-1 shared anchor**: the ML and DE tracks build silver/gold *on top of*
# MAGIC these governed bronze tables, so getting the classification right here protects everything after it.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Scan: what's actually in these tables? (PRE-BUILT)
# MAGIC
# MAGIC Before tagging, look at the columns and a few values. The sensitive ones are not subtle here:
# MAGIC `person_id` (who), `note_text` (a free-text pathology report, the highest-risk unstructured PHI),
# MAGIC `year_of_birth` (a re-identification quasi-identifier), and the clinical `*_source_value` columns
# MAGIC (diagnosis, biomarker, drug, sensitive health facts).

# COMMAND ----------

# DBTITLE 1,Inventory every column across the 6 tables (PRE-BUILT)
from pyspark.sql import functions as F

rows = []
for t in OMOP_TABLES:
    for f in spark.table(fqn(t)).schema.fields:
        rows.append((t, f.name, f.dataType.simpleString()))
inv = spark.createDataFrame(rows, ["table", "column", "type"])
print(f"{inv.count()} columns across {len(OMOP_TABLES)} tables")
display(inv)

# COMMAND ----------

# DBTITLE 1,Peek at the highest-risk column: a raw pathology note (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT person_id, note_source_value, LEFT(note_text, 240) AS note_preview
# MAGIC FROM note
# MAGIC WHERE note_source_value = 'PATHOLOGY_REPORT'
# MAGIC LIMIT 3;

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 2️⃣ The classification you'll apply (PRE-BUILT reference)
# MAGIC
# MAGIC `_config` ships a `PHI_COLUMNS` map: the agreed answer to "what is sensitive and how sensitive."
# MAGIC We classify in two dimensions, mapped to the metastore's **governed tag policies**:
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b><code>phi</code> = HIPAA identifier type</b>, only on columns that <i>identify the patient</i>:
# MAGIC <code>person_id</code> and free-text <code>note_text</code> get <code>phi=other_identifier</code>;
# MAGIC <code>year_of_birth</code> / <code>birth_date</code> get <code>phi=birth_date</code>. These are the
# MAGIC columns you'll <b>mask</b> in nb 02.<br>
# MAGIC <b><code>data_sensitivity</code> = official | official_sensitive</b>, on <i>every</i> sensitive
# MAGIC column, including clinical facts (diagnosis, biomarker, drug) that aren't identifiers but are still
# MAGIC protected health information.
# MAGIC </div>
# MAGIC
# MAGIC <div style="background:#EDE7F6; border-left:6px solid #5E35B1; padding:12px 16px; border-radius:4px">
# MAGIC <b>⚠️ Governed tag policy (a real FH-style control):</b> this metastore <b>constrains the allowed
# MAGIC tag values</b> for <code>phi</code> and <code>data_sensitivity</code>. A typo or an off-list value
# MAGIC (<code>'high'</code>, <code>'direct_identifier'</code>) is <b>rejected</b> at <code>ALTER TABLE</code>.
# MAGIC That's the point. Governance enforces one vocabulary. The allowed values are in <code>_config</code>.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,The PHI map you'll tag from (PRE-BUILT, from _config)
for tbl, cols in PHI_COLUMNS.items():
    print(f"{tbl}:")
    for col, (phi, sens) in cols.items():
        print(f"    {col:<28} phi={phi!s:<18} data_sensitivity={sens}")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🔑 The tagging pattern you need (read before you build)
# MAGIC
# MAGIC UC column tags are set with `ALTER TABLE ... ALTER COLUMN ... SET TAGS`. A tag is a `key = 'value'`
# MAGIC pair. We use **two keys** (both pre-declared in `_config`):
# MAGIC
# MAGIC ```sql
# MAGIC -- an identifier column gets BOTH tags (phi type + sensitivity):
# MAGIC ALTER TABLE person ALTER COLUMN person_id
# MAGIC   SET TAGS ('phi' = 'other_identifier', 'data_sensitivity' = 'official_sensitive');
# MAGIC
# MAGIC -- a clinical-fact column is sensitive but NOT a HIPAA identifier -> data_sensitivity only:
# MAGIC ALTER TABLE drug_exposure ALTER COLUMN drug_source_value
# MAGIC   SET TAGS ('data_sensitivity' = 'official_sensitive');
# MAGIC ```
# MAGIC
# MAGIC <div style="background:#E3F2FD; border-left:6px solid #1565C0; padding:12px 16px; border-radius:4px">
# MAGIC Each entry in <code>PHI_COLUMNS</code> is <code>(phi_type, sensitivity)</code>. When
# MAGIC <code>phi_type is None</code> the column is sensitive but not an identifier. Set
# MAGIC <code>data_sensitivity</code> only (no <code>phi</code> tag). These tags are what nb 03's ABAC
# MAGIC policy and nb 04's identifier audit read back, so use the exact allowed values from <code>_config</code>.
# MAGIC </div>

# COMMAND ----------

# DBTITLE 1,TODO: tag every PHI column across all 6 tables
# TODO (you build this): loop over PHI_COLUMNS and apply UC tags to each column.
#   Each entry is (phi_type, sensitivity). For each (table, column, phi_type, sensitivity):
#     • if phi_type is not None  -> set BOTH 'phi' and 'data_sensitivity'
#     • if phi_type is None      -> set ONLY 'data_sensitivity' (it's sensitive, not an identifier)
#   Use the governed allowed values straight from PHI_COLUMNS (don't invent values, they'll be rejected).
#   Build the SQL and run spark.sql(...) inside the loop.
#
# Skeleton (fill the body):
#
# for tbl, cols in PHI_COLUMNS.items():
#     for col, (phi_type, sensitivity) in cols.items():
#         if phi_type:
#             tags = f"'{TAG_PHI}' = '{phi_type}', '{TAG_SENSITIVITY}' = '{sensitivity}'"
#         else:
#             tags = f"'{TAG_SENSITIVITY}' = '{sensitivity}'"
#         spark.sql(f"ALTER TABLE {fqn(tbl)} ALTER COLUMN {col} SET TAGS ({tags})")
#         print(f"tagged {tbl}.{col}: phi={phi_type}, data_sensitivity={sensitivity}")
#
# EXTENSION (optional): inspect the metastore's governed tag policy (the allowed-value list) and
#   discuss why constraining tag values matters for a HIPAA audit.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Prove the classification stuck (PRE-BUILT verification)
# MAGIC
# MAGIC Tags live in `information_schema.column_tags`. This is the auditor's view, and the same query
# MAGIC nb 03 / nb 04 build on. After your TODO runs, this should list every column you tagged.

# COMMAND ----------

# DBTITLE 1,Read the tags back from information_schema (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT table_name, column_name, tag_name, tag_value
# MAGIC FROM information_schema.column_tags
# MAGIC WHERE schema_name = current_schema()
# MAGIC   AND tag_name IN ('phi', 'data_sensitivity')
# MAGIC ORDER BY table_name, column_name, tag_name;

# COMMAND ----------

# DBTITLE 1,Coverage check: every PHI column tagged? (PRE-BUILT)
# Every sensitive column must carry at least a data_sensitivity tag; identifiers must also carry phi.
expected = {(t, c) for t, cols in PHI_COLUMNS.items() for c in cols}
expected_phi = {(t, c) for t, cols in PHI_COLUMNS.items()
                for c, (phi, sens) in cols.items() if phi is not None}
tagged = {(r.table_name, r.column_name) for r in spark.sql(
    "SELECT DISTINCT table_name, column_name FROM information_schema.column_tags "
    "WHERE schema_name = current_schema() AND tag_name = 'data_sensitivity'").collect()}
tagged_phi = {(r.table_name, r.column_name) for r in spark.sql(
    "SELECT table_name, column_name FROM information_schema.column_tags "
    "WHERE schema_name = current_schema() AND tag_name = 'phi'").collect()}
missing = (expected - tagged) | (expected_phi - tagged_phi)
if missing:
    show_md(f"<b>⚠️ Not done yet.</b> {len(missing)} PHI columns still untagged: <code>{sorted(missing)}</code>")
else:
    show_md(f"<b>✅ Checkpoint 1 met.</b> All {len(expected)} sensitive columns tagged "
            f"(<code>{len(expected_phi)}</code> identifier columns also carry a <code>phi</code> tag). "
            "The catalog now <i>knows</i> what's sensitive. Masks & filters can target it.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just did:</b> turned "we think these columns are sensitive" into a <i>queryable,
# MAGIC catalog-wide fact</i>. Classification is the foundation every other control stands on.
# MAGIC </div>
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[02_column_masks]($./02_column_masks)** to hide the identifiers from researchers while keeping them for the data office.
