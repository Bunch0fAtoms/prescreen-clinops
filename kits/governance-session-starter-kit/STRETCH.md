# 🚀 STRETCH, make it your own

Finished the core build (notebooks 01 to 06, all the `# TODO (you build this)` markers)? Pick an
extension. These map to the `# EXTENSION (optional)` hooks in the notebooks and to the real FH asks
beyond the headline. None are required. They're for teams who want to push the governance further.

Ground rules still apply: **Unity-Catalog-scoped, synthetic data only, no hardcoded secrets, no
hive_metastore**. Policy sits at the **catalog and schema level** on the shared foundation, so it
inherits to everything built on it.

> **Tag-based ABAC is now the main build, not a stretch.** Writing one tag-based policy that follows the
> `phi` tag catalog-wide (classify once, policy follows the tag, covers any new table) is the scalable
> core in nb 03. See the README and RUNBOOK. If `CREATE POLICY` is preview-gated on your metastore,
> attempt it, then log it as a **preview feature to request for FH** and fall back to per-table binds.
> The extensions below build on top of that.

---

## 1. Govern a researcher's *derived* table

A researcher built `my_cohort` from `person`. Show that PHI controls don't automatically follow a copy:
- Create a derived table that selects `person_id` into a new table (no tags).
- Run nb 04's structural search, watch it surface the untagged identifier (the leak).
- Re-run nb 01's classify and nb 02's masks against the derived table to bring it under governance.
- This is the real lifecycle. **Derived data needs re-governing**, and your tags and search make it findable.

## 2. Differential masking by sensitivity

Right now `mask_person_id` is binary (reveal/redact). Make it tiered:
- A `data_steward` group sees raw; `ocdo_data_scientists` see a **hashed** surrogate (`sha2(...)` so
  joins still work but the real id is hidden); everyone else sees NULL.
- Use nested `is_account_group_member` checks. Show how one UDF encodes a whole access matrix.

## 3. Row filter by cohort, not just consent

Extend nb 03's filter so different groups see different *cohorts*, e.g. a breast-cancer study group
only sees patients with `condition_source_value = 'Malignant neoplasm of breast'`. Join the filter UDF
to `condition_occurrence`. Demonstrates attribute-driven row security beyond a flat consent flag.

## 4. Audit dashboards and alerts on the governance posture

Turn the system-table queries into a standing posture report:
- A **Lakeview dashboard** over `inactive_user_report` (nb 06) and a "PHI columns without a mask" query
  (join `column_tags` where `phi=other_identifier` against `column_masks`).
- A scheduled **alert** when an inactive-over-90d user appears, or when a `phi`-tagged column has no mask.
- Use the `databricks-aibi-dashboards` / `databricks-jobs` skills.

## 5. Lineage-driven impact analysis

Use `system.access.table_lineage` (nb 04 step 3) to answer: "if I mask `note.note_text`, which
downstream tables / dashboards / models are affected?" Walk the lineage graph from a governed column to
every consumer, the data office's "what breaks if we lock this down?" question, answered from system
tables.

## 6. Metric view for governed KPIs

Define a UC **metric view** over the governed tables (e.g. count of consented patients, count of
PHI-tagged columns, count masked vs. unmasked) so the data office shares one definition of "governed."
Point a Genie space at it (and prove, per nb 05, that the Genie space honors the masks). See the
`databricks-metric-views` skill.
