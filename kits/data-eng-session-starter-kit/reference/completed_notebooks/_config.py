# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC # ⚙️ Configuration: Data Engineering Session (PRE-BUILT)
# MAGIC
# MAGIC <div style="background:#f4f6f9; border-left:6px solid #C8102E; padding:14px 18px; border-radius:4px; font-size:0.95em">
# MAGIC This is the <b>companion config notebook</b>. It is <b>pre-built; you do not edit it</b>.
# MAGIC Every other notebook starts with <code>%run ./_config</code> so they all share one
# MAGIC catalog / schema / warehouse and the same source-of-truth tables.<br>
# MAGIC Just set the widgets at the top of <code>00_START_HERE</code> (matching your bundle's
# MAGIC <code>client_catalog</code> / <code>client_schema</code> / <code>warehouse_id</code>) and re-run.
# MAGIC </div>
# MAGIC
# MAGIC Everything here is Unity-Catalog-scoped (no hive_metastore) and reads from widgets, with no
# MAGIC hardcoded secrets.

# COMMAND ----------

# DBTITLE 1,Widgets: set these to your bundle vars (catalog / schema you WRITE to / warehouse)
# `schema` is YOUR writable schema (bronze landing, evolved tables, reconciliation outputs,
#   the ingest allow-list config). `source_catalog` / `source_schema` point at the read-only OMOP
#   tables you ingest FROM. Synthetic (workshop): leave source_catalog blank (defaults to your own
#   catalog) and source_schema = clinops_foundation. Real: set source_catalog = curated_omop,
#   source_schema = omop. The 6 OMOP table names are identical either way, no query changes.
# `feed_schema` is where the shared LIVE trials feed lands (the foundation's land_trial_feed
#   Volume). It is a workshop feed, so it stays on the foundation schema even when OMOP repoints
#   to real. Do NOT tie it to source_schema.
dbutils.widgets.text("catalog",        "<your_catalog>",     "1 · Catalog")
dbutils.widgets.text("schema",         "clinops_de",         "2 · Schema (you write here)")
dbutils.widgets.text("warehouse_id",   "<your_wh_id>",       "3 · SQL Warehouse ID")
dbutils.widgets.text("source_schema",  "clinops_foundation", "4 · Source schema (read-only OMOP)")
dbutils.widgets.text("source_catalog", "",                   "5 · Source catalog (blank = same as Catalog)")
dbutils.widgets.text("feed_schema",    "clinops_foundation", "6 · Trials-feed schema (foundation Volume)")

CATALOG        = dbutils.widgets.get("catalog")
SCHEMA         = dbutils.widgets.get("schema")
WAREHOUSE_ID   = dbutils.widgets.get("warehouse_id")
SOURCE_SCHEMA  = dbutils.widgets.get("source_schema")
# Synthetic reads from your own catalog; real OMOP (curated_omop) sits in a different catalog.
SOURCE_CATALOG = dbutils.widgets.get("source_catalog").strip() or CATALOG
# The trials feed lives in the foundation schema, in your own catalog (not the OMOP source).
FEED_SCHEMA    = dbutils.widgets.get("feed_schema")

# COMMAND ----------

# DBTITLE 1,Point Spark at the (Unity Catalog) catalog & YOUR schema
# Create the catalog if you have rights AND it's missing; otherwise just use the existing one.
# (Many workspaces pre-provision the team catalog and don't grant CREATE CATALOG, and that's fine.)
try:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
except Exception as e:
    print(f"ℹ️ Not creating catalog {CATALOG} (likely pre-provisioned / no CREATE CATALOG): {str(e)[:80]}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

print(f"✅ Writing to {CATALOG}.{SCHEMA}")
print(f"   Reading source OMOP from {SOURCE_CATALOG}.{SOURCE_SCHEMA}")
print(f"   Trials feed lands in     {CATALOG}.{FEED_SCHEMA}")
print(f"   SQL Warehouse: {WAREHOUSE_ID}")

# COMMAND ----------

# DBTITLE 1,Tiny helpers used across the notebooks
def fqn(table: str) -> str:
    """Fully-qualified name in YOUR schema: fqn('bronze_person') -> 'catalog.schema.bronze_person'."""
    return f"{CATALOG}.{SCHEMA}.{table}"


def src(table: str) -> str:
    """Fully-qualified name of a READ-ONLY source OMOP table: src('person') -> 'source_catalog.source_schema.person'."""
    return f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table}"


def show_md(markdown: str):
    """Render a Markdown string inline (handy for dynamic value callouts)."""
    displayHTML(f"<div style='font-size:1.0em; line-height:1.5'>{markdown}</div>")


# The 6 OMOP source tables you ingest from (read-only). person_id is the join key everywhere.
OMOP_TABLES = ["person", "condition_occurrence", "measurement", "observation", "drug_exposure", "note"]

print("Helpers ready: fqn(), src(), show_md(), OMOP_TABLES")
