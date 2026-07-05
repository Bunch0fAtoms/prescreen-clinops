# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC # ⚙️ Configuration — Clinical Trial Pre-Screening (PRE-BUILT)
# MAGIC
# MAGIC <div style="background:#f4f6f9; border-left:6px solid #C8102E; padding:14px 18px; border-radius:4px; font-size:0.95em">
# MAGIC This is the <b>companion config notebook</b> — it is <b>pre-built; you do not edit it</b>.
# MAGIC Every other notebook starts with <code>%run ./_config</code> so they all share one
# MAGIC catalog / schema / warehouse and the same read-only OMOP source.<br>
# MAGIC Just set the widgets at the top of <code>00_START_HERE</code> (matching your
# MAGIC bundle's <code>client_catalog</code> / <code>client_schema</code> / <code>warehouse_id</code>
# MAGIC / <code>source_schema</code>) and re-run.
# MAGIC </div>
# MAGIC
# MAGIC Everything here is Unity-Catalog-scoped (no hive_metastore) and reads from widgets — no
# MAGIC hardcoded secrets.

# COMMAND ----------

# DBTITLE 1,Widgets — set these to your bundle vars (schema you WRITE to + the read-only OMOP source)
# `schema` is YOUR writable schema (silver features, NLP output, gold pre-screen, the model,
#   the Genie space). `source_catalog` / `source_schema` point at the 6 read-only OMOP tables.
#   Synthetic (workshop): leave source_catalog blank (defaults to your own catalog) and
#   source_schema = clinops_foundation. Real: set source_catalog = curated_omop,
#   source_schema = omop. The 6 table names are identical either way — no query changes.
dbutils.widgets.text("catalog",        "<your_catalog>",     "1 · Catalog")
dbutils.widgets.text("schema",         "clinops_ml",         "2 · Schema (you write here)")
dbutils.widgets.text("warehouse_id",   "<your_wh_id>",       "3 · SQL Warehouse ID")
dbutils.widgets.text("source_schema",  "clinops_foundation", "4 · Source schema (read-only OMOP)")
dbutils.widgets.text("source_catalog", "",                   "5 · Source catalog (blank = same as Catalog)")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA         = dbutils.widgets.get("schema")
WAREHOUSE_ID   = dbutils.widgets.get("warehouse_id")
SOURCE_SCHEMA  = dbutils.widgets.get("source_schema")
# Synthetic reads from your own catalog; real OMOP (curated_omop) sits in a different catalog.
SOURCE_CATALOG = dbutils.widgets.get("source_catalog").strip() or CATALOG

# COMMAND ----------

# DBTITLE 1,Point Spark at the (Unity Catalog) catalog & schema
# Many workspaces pre-provision the team catalog and don't grant CREATE CATALOG (it needs the
# metastore-level privilege workshop users / the client typically lack) — that's fine, we only
# need to USE it and create our schema inside it.
try:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
except Exception as e:
    print(f"ℹ️ Not creating catalog {CATALOG} (likely pre-provisioned / no CREATE CATALOG): {str(e)[:80]}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

print(f"✅ Writing to {CATALOG}.{SCHEMA}")
print(f"   Reading read-only OMOP source from {SOURCE_CATALOG}.{SOURCE_SCHEMA}")
print(f"   SQL Warehouse: {WAREHOUSE_ID}")

# COMMAND ----------

# DBTITLE 1,Tiny helpers used across the notebooks
def fqn(table: str) -> str:
    """Fully-qualified name in YOUR writable schema: fqn('silver_biomarker_profile')."""
    return f"{CATALOG}.{SCHEMA}.{table}"


def src(table: str) -> str:
    """Fully-qualified name of a READ-ONLY source OMOP table: src('person') -> 'source_catalog.source_schema.person'."""
    return f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table}"


def show_md(markdown: str):
    """Render a Markdown string inline (handy for dynamic value callouts)."""
    displayHTML(f"<div style='font-size:1.0em; line-height:1.5'>{markdown}</div>")


# Foundation Model endpoints available in the workspace (used by the ai_query steps).
# databricks-claude-haiku-4-5  -> fast, cheap, the default extractor
# databricks-claude-sonnet-4-6 -> higher quality, used in the eval comparison
LLM_FAST   = "databricks-claude-haiku-4-5"
LLM_STRONG = "databricks-claude-sonnet-4-6"

print("Helpers ready: fqn(), src(), show_md(), LLM_FAST, LLM_STRONG")
