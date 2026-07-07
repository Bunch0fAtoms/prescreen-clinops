# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 03 · INGEST GATE · YOU BUILD THE GUARD</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🚦 Block restricted tables, from config, not code</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     A reusable guard that checks a Unity Catalog <b>allow/deny-list</b> before any write, so a
# MAGIC     restricted table is refused <b>before a single row lands</b>, and the list is governed in UC,
# MAGIC     never hardcoded.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why this matters (FH ask: Jenn #16)
# MAGIC
# MAGIC In a security-first shop, "don't ingest the restricted tables" can't live in a code comment or a
# MAGIC reviewer's memory. It must be **enforced** and **changeable without a deploy**. So we drive the gate
# MAGIC from a **Unity Catalog config table** (`ingest_allowlist`): a steward edits a row, the gate's
# MAGIC behavior changes immediately, and every decision is auditable.
# MAGIC
# MAGIC Two equally valid models (we use the allow-list; the deny-list is a one-line flip):
# MAGIC
# MAGIC | Model | Rule |
# MAGIC |---|---|
# MAGIC | **Allow-list** (default here) | a table may be ingested **only if** it's explicitly allowed |
# MAGIC | **Deny-list** | a table may be ingested **unless** it's explicitly denied |
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The config table + the safe-write wrapper are pre-built; the guard is yours.</b> You write
# MAGIC <code>assert_ingest_allowed(table)</code>, the function that reads the UC allow-list and raises
# MAGIC <i>before</i> any data moves. Nothing is hardcoded: change the table, change the behavior.
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ The governance config table (PRE-BUILT)
# MAGIC
# MAGIC `ingest_allowlist` is a tiny UC table a steward owns: one row per source table, with an `allowed`
# MAGIC flag and a `classification`. The 6 OMOP tables are allowed; we plant two **restricted** tables
# MAGIC (`genomic_sequencing`, `provider_pii`) as `allowed = false` to prove the block.

# COMMAND ----------

# DBTITLE 1,Seed the allow-list config table in UC (PRE-BUILT, a steward owns this, not code)
# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS ingest_allowlist (
# MAGIC   table_name     STRING,
# MAGIC   allowed        BOOLEAN,
# MAGIC   classification STRING,
# MAGIC   reason         STRING
# MAGIC ) COMMENT 'Governs which source tables the ingest jobs may write. Edited by a data steward, not in code.';
# MAGIC
# MAGIC -- Idempotent reseed so the notebook is rerunnable.
# MAGIC DELETE FROM ingest_allowlist;
# MAGIC INSERT INTO ingest_allowlist VALUES
# MAGIC   ('person',               true,  'internal',   'OMOP demographics, synthetic'),
# MAGIC   ('condition_occurrence', true,  'internal',   'OMOP diagnoses, synthetic'),
# MAGIC   ('measurement',          true,  'internal',   'OMOP labs/biomarkers, synthetic'),
# MAGIC   ('observation',          true,  'internal',   'OMOP observations, synthetic'),
# MAGIC   ('drug_exposure',        true,  'internal',   'OMOP medications, synthetic'),
# MAGIC   ('note',                 true,  'internal',   'OMOP clinical notes, synthetic'),
# MAGIC   ('genomic_sequencing',   false, 'restricted', 'Genomic data, separate IRB approval required'),
# MAGIC   ('provider_pii',         false, 'restricted', 'Provider PII, out of scope for this pipeline');

# COMMAND ----------

# DBTITLE 1,Look at the governed list (PRE-BUILT)
# MAGIC %sql
# MAGIC SELECT table_name, allowed, classification, reason FROM ingest_allowlist ORDER BY allowed DESC, table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ 🛠️ TODO: the guard function `assert_ingest_allowed(table)`
# MAGIC
# MAGIC Write the reusable guard. It reads `ingest_allowlist` from UC and:
# MAGIC - **raises** `PermissionError` if the table is missing from the list **or** has `allowed = false`,
# MAGIC - **returns** quietly (allowing the write) if `allowed = true`.
# MAGIC
# MAGIC The key property: it must hit the **config table**, never an in-code list, so a steward can change
# MAGIC the rules without a deploy.

# COMMAND ----------

# DBTITLE 1,TODO: assert_ingest_allowed: read the UC allow-list, block or pass (YOU BUILD THIS)
from pyspark.sql import functions as F

def assert_ingest_allowed(table: str) -> None:
    """
    TODO (you build this): guard a write against the UC `ingest_allowlist` config table.

      • Look up `table` in fqn("ingest_allowlist").
      • If there is NO matching row, OR the matching row has allowed = false:
            raise PermissionError(...) with a clear message (include the classification/reason if present).
      • Otherwise return None (the caller is cleared to write).

    WHY a function reading a UC table (not an `if table in [...]:`): the rule lives in governed config a
      steward owns, is auditable, and changes with NO code deploy. That is the whole ask.

    PATTERN:
      row = (spark.table(fqn("ingest_allowlist"))
                 .filter(F.col("table_name") == table).limit(1).collect())
      if not row or not row[0]["allowed"]:
          raise PermissionError(f"🚫 Ingest BLOCKED for '{table}' ...")
    """
    # ---- your code below ----
    raise NotImplementedError("Build assert_ingest_allowed. See the TODO above.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ A safe-write wrapper that calls your guard FIRST (PRE-BUILT)
# MAGIC
# MAGIC This is how an ingest task uses your guard: the gate runs **before** any DataFrame is written, so a
# MAGIC restricted table never lands a single row.

# COMMAND ----------

# DBTITLE 1,safe_ingest: guard, then write (PRE-BUILT, calls YOUR function)
def safe_ingest(table: str) -> None:
    """Guard with assert_ingest_allowed(), then copy source -> bronze. Restricted tables raise here."""
    assert_ingest_allowed(table)                         # <- your guard; raises to block
    (spark.table(src(table))
        .write.mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(fqn(f"bronze_{table}")))
    print(f"✅ Ingested '{table}' -> {fqn('bronze_'+table)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Prove it: allowed passes, restricted is blocked (PRE-BUILT, runs your guard)

# COMMAND ----------

# DBTITLE 1,An ALLOWED table ingests cleanly (PRE-BUILT)
safe_ingest("person")   # allowed = true -> should write bronze_person

# COMMAND ----------

# DBTITLE 1,A RESTRICTED table is blocked BEFORE any row lands (PRE-BUILT)
import traceback
try:
    safe_ingest("genomic_sequencing")   # allowed = false -> your guard must raise
    print("⚠ Unexpected: the restricted table was NOT blocked. Check your guard.")
except PermissionError as e:
    print("✅ Correctly BLOCKED a restricted table:")
    print("   " + str(e))
    # confirm nothing landed
    assert not spark.catalog.tableExists(fqn("bronze_genomic_sequencing")), \
        "A bronze table was created for a blocked source: the guard ran too late!"
    print("   ✅ Verified: no bronze_genomic_sequencing table was created.")
except NotImplementedError:
    print("⏳ Build assert_ingest_allowed first (the TODO above), then re-run.")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you built:</b> a config-driven ingest gate. Want to allow a new table tomorrow? A steward
# MAGIC flips <code>allowed</code> in <code>ingest_allowlist</code>, no code change, no deploy, full audit
# MAGIC trail. Flip the seed to a <i>deny-list</i> by inverting the boolean and the default.
# MAGIC </div>
# MAGIC
# MAGIC <!-- EXTENSION (optional): drive the gate from UC TAGS instead of a table, read information_schema
# MAGIC      tag assignments and block any source tagged classification=restricted. See STRETCH.md. -->
# MAGIC
# MAGIC ## ▶️ Next step
# MAGIC ### → Open **[04_sla_job_windows]($./04_sla_job_windows)** to keep jobs out of the source's nightly SLA window.
