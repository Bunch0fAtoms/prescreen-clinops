# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC # ⚙️ Configuration — UC Governance on OMOP (PRE-BUILT)
# MAGIC
# MAGIC <div style="background:#f4f6f9; border-left:6px solid #C8102E; padding:14px 18px; border-radius:4px; font-size:0.95em">
# MAGIC This is the <b>companion config notebook</b> — it is <b>pre-built; you do not edit it</b>.
# MAGIC Every other notebook starts with <code>%run ./_config</code> so they all share one
# MAGIC catalog / schema / warehouse and the same governance vocabulary.<br>
# MAGIC Just set the widgets at the top of <code>00_START_HERE</code> (matching your
# MAGIC bundle's <code>client_catalog</code> / <code>client_schema</code> / <code>warehouse_id</code>)
# MAGIC and re-run.
# MAGIC </div>
# MAGIC
# MAGIC Everything here is Unity-Catalog-scoped (no hive_metastore) and reads from widgets — no
# MAGIC hardcoded secrets.

# COMMAND ----------

# DBTITLE 1,Widgets — the four things you set (match your bundle vars)
# catalog / schema / warehouse_id should match your databricks.yml client target.
# ocdo_group is the analyst group masks & row filters gate on — see note below.
dbutils.widgets.text("catalog",      "<your_catalog>",       "1 · Catalog")
dbutils.widgets.text("schema",       "clinops_gov",    "2 · Schema")
dbutils.widgets.text("warehouse_id", "<your_wh_id>",         "3 · SQL Warehouse ID")
dbutils.widgets.text("ocdo_group",   "ocdo_data_scientists", "4 · OCDO researcher group")

CATALOG      = dbutils.widgets.get("catalog")
SCHEMA       = dbutils.widgets.get("schema")
WAREHOUSE_ID = dbutils.widgets.get("warehouse_id")
OCDO_GROUP   = dbutils.widgets.get("ocdo_group")

# COMMAND ----------

# DBTITLE 1,Point Spark at the (Unity Catalog) catalog & schema
# Create the catalog/schema only if absent AND you have the privilege — in most workshop
# workspaces the catalog already exists, so we don't force CREATE CATALOG (which needs a
# metastore-level grant). The schema is created if you can; otherwise we assume it's there.
if not spark.catalog.databaseExists(f"{CATALOG}.{SCHEMA}"):
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
    except Exception as _e:
        print(f"(catalog {CATALOG} not created — assuming it already exists: {str(_e)[:120]})")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

print(f"✅ Using {CATALOG}.{SCHEMA}")
print(f"   SQL Warehouse: {WAREHOUSE_ID}")
print(f"   OCDO researcher group (masks/filters gate on this): {OCDO_GROUP}")

# COMMAND ----------

# DBTITLE 1,Tiny helpers used across the notebooks
def fqn(table: str) -> str:
    """Fully-qualified name: fqn('person') -> 'catalog.schema.person'."""
    return f"{CATALOG}.{SCHEMA}.{table}"


def show_md(markdown: str):
    """Render a Markdown string inline (handy for dynamic value callouts)."""
    displayHTML(f"<div style='font-size:1.0em; line-height:1.5'>{markdown}</div>")


# The 6 governed OMOP tables this session secures (deep-cloned from the shared foundation
# schema so this kit can apply policies without touching anyone else's tables).
OMOP_TABLES = ["person", "condition_occurrence", "measurement",
               "observation", "drug_exposure", "note"]

# COMMAND ----------

# DBTITLE 1,The governance vocabulary (GOVERNED tag policies — values are constrained!)
# ⚠️ FH FINDING: this metastore enforces GOVERNED TAG POLICIES on these two tag keys — you may
# only use values from the allowed list, or ALTER TABLE ... SET TAGS is REJECTED. This is a *good*
# governance feature: it forces a consistent, HIPAA-aligned vocabulary instead of free-text tags.
#   • 'phi'              — HIPAA Safe Harbor identifier types. Allowed values include:
#                          name, mrn, ssn, birth_date, death_date, telephone, fax, email, url,
#                          ipaddr, account_number, license_number, device_identifier, finger_print,
#                          photo, address_part, other_identifier, true, false.
#   • 'data_sensitivity' — allowed values: official | official_sensitive.
# If your workspace does NOT have these policies, any string works; the kit still runs. To inspect
# the policy: SELECT * FROM system.information_schema.tag_policies (if exposed) or just try a value.
TAG_PHI         = "phi"
TAG_SENSITIVITY = "data_sensitivity"

# The PHI map: for each column, (phi_identifier_type, sensitivity). phi=None means "sensitive but
# not a HIPAA identifier" (we tag it with data_sensitivity only — e.g. clinical facts, gender).
# This is the *answer to "what is sensitive"* — nb 01 applies it as UC tags; nb 02/03 mask & filter.
#   classification recap: person_id + note_text = identifiers (mask these); year/birth_date = quasi-
#   identifiers; clinical *_source_value = sensitive health facts.
PHI_COLUMNS = {
    "person":               {"person_id": ("other_identifier", "official_sensitive"),
                             "year_of_birth": ("birth_date", "official_sensitive"),
                             "birth_date": ("birth_date", "official_sensitive"),
                             "gender_source_value": (None, "official")},
    "condition_occurrence": {"person_id": ("other_identifier", "official_sensitive"),
                             "condition_source_value": (None, "official_sensitive")},
    "measurement":          {"person_id": ("other_identifier", "official_sensitive"),
                             "measurement_source_value": (None, "official"),
                             "value_source_value": (None, "official_sensitive")},
    "observation":          {"person_id": ("other_identifier", "official_sensitive"),
                             "observation_source_value": (None, "official_sensitive")},
    "drug_exposure":        {"person_id": ("other_identifier", "official_sensitive"),
                             "drug_source_value": (None, "official_sensitive")},
    "note":                 {"person_id": ("other_identifier", "official_sensitive"),
                             "note_text": ("other_identifier", "official_sensitive"),
                             "note_source_value": (None, "official")},
}

# The columns to MASK (HIPAA direct identifiers) — used by nb 02.
DIRECT_IDENTIFIERS = [(t, c) for t, cols in PHI_COLUMNS.items()
                      for c, (phi, sens) in cols.items() if phi == "other_identifier"]

print("Helpers ready: fqn(), show_md(), OMOP_TABLES, PHI_COLUMNS, DIRECT_IDENTIFIERS, TAG_PHI, TAG_SENSITIVITY")
print(f"PHI map covers {sum(len(v) for v in PHI_COLUMNS.values())} columns across {len(PHI_COLUMNS)} tables.")
