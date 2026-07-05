# 🚀 STRETCH — make it your own

Finished the core build (notebooks 01–06, all the `# TODO (you build this)` markers)? Pick an
extension. These map to the `# EXTENSION (optional)` hooks in the notebooks and to the real FH asks
beyond the headline. None are required — they're for teams who want to push the governance further.

Ground rules still apply: **Unity-Catalog-scoped, synthetic data only, no hardcoded secrets, no
hive_metastore**, and **only on your own cloned schema** (never the shared source).

---

## 1. Tag-based ABAC — one policy, whole-catalog coverage

The GA path binds a mask/filter to each column/table by hand. **ABAC policies** let you write the
logic *once* and have UC apply it to **every column carrying a tag** (the `phi=other_identifier` tags
from nb 01). Notebook 03 already has the attempt wrapped in try/except — if it errored on your
workspace (it's preview), this is the stretch:
- Confirm whether tag-based ABAC / `CREATE POLICY` is enabled (account console / preview features).
- If enabled, author one policy that masks every `phi=other_identifier` column for the OCDO group, drop
  the per-table masks from nb 02, and prove the *same* redaction now holds catalog-wide — including on
  any new table that gets the tag. This is the governance dream: classify once, policy follows the tag.
- If not enabled, document it as a **preview feature to request for FH** and note the exact DDL you'd run.

## 2. Govern a researcher's *derived* table

A researcher built `my_cohort` from `person`. Show that PHI controls don't automatically follow a copy:
- Create a derived table that selects `person_id` into a new table (no tags).
- Run nb 04's structural search — watch it surface the untagged identifier (the leak).
- Re-run nb 01's classify + nb 02's masks against the derived table to bring it under governance.
- This is the real lifecycle: **derived data needs re-governing**, and your tags + search make it findable.

## 3. Differential masking by sensitivity

Right now `mask_person_id` is binary (reveal/redact). Make it tiered:
- A `data_steward` group sees raw; `ocdo_data_scientists` see a **hashed** surrogate (`sha2(...)` so
  joins still work but the real id is hidden); everyone else sees NULL.
- Use nested `is_account_group_member` checks. Show how one UDF encodes a whole access matrix.

## 4. Row filter by cohort, not just consent

Extend nb 03's filter so different groups see different *cohorts* — e.g. a breast-cancer study group
only sees patients with `condition_source_value = 'Malignant neoplasm of breast'`. Join the filter UDF
to `condition_occurrence`. Demonstrates attribute-driven row security beyond a flat consent flag.

## 5. Audit dashboards + alerts on the governance posture

Turn the system-table queries into a standing posture report:
- A **Lakeview dashboard** over `inactive_user_report` (nb 06) + a "PHI columns without a mask" query
  (join `column_tags` where `phi=other_identifier` against `column_masks`).
- A scheduled **alert** when an inactive-over-90d user appears, or when a `phi`-tagged column has no mask.
- Use the `databricks-aibi-dashboards` / `databricks-jobs` skills.

## 6. Lineage-driven impact analysis

Use `system.access.table_lineage` (nb 04 step 3) to answer: "if I mask `note.note_text`, which
downstream tables / dashboards / models are affected?" Walk the lineage graph from a governed column to
every consumer — the data office's "what breaks if we lock this down?" question, answered from system
tables.

## 7. Metric view for governed KPIs

Define a UC **metric view** over the governed tables (e.g. count of consented patients, count of
PHI-tagged columns, count masked vs. unmasked) so the data office shares one definition of "governed."
Point a Genie space at it (and prove — per nb 05 — that the Genie space honors the masks). See the
`databricks-metric-views` skill.
