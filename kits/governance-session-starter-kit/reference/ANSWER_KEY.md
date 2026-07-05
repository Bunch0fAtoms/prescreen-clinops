# 🔑 Answer Key — SA / MENTOR ONLY

> **For the mentor. Reveal a snippet only if a team is genuinely stuck** (after the nudge → hint →
> pair ladder in `RUNBOOK.md`). Reveal **late** on the learnable core (the group-gating logic), and
> **early** on plumbing or the governed-tag vocabulary. Everything below was validated on the FEVM
> workspace `a reference workspace` against `clinops_gov` — the per-notebook validation
> result is noted with each item.

---

## NB 01 — tag every PHI column (GUIDED TODO) · ✅ validated

```python
for tbl, cols in PHI_COLUMNS.items():
    for col, (phi_type, sensitivity) in cols.items():
        if phi_type:
            tags = f"'{TAG_PHI}' = '{phi_type}', '{TAG_SENSITIVITY}' = '{sensitivity}'"
        else:
            tags = f"'{TAG_SENSITIVITY}' = '{sensitivity}'"
        spark.sql(f"ALTER TABLE {fqn(tbl)} ALTER COLUMN {col} SET TAGS ({tags})")
```

- **Why two keys:** `phi` is the HIPAA identifier *type* (only on identifiers); `data_sensitivity` is on
  every sensitive column including clinical facts that aren't identifiers.
- **⚠ THE governed-tag gotcha (reveal early — vocabulary, not the lesson):** this metastore has
  **governed tag policies**. `phi` only accepts `[name, mrn, ssn, birth_date, death_date, telephone,
  fax, email, url, ipaddr, account_number, license_number, device_identifier, finger_print, photo,
  address_part, other_identifier, true, false]`; `data_sensitivity` only accepts `[official,
  official_sensitive]`. Any other value → `Tag value X is not an allowed value for tag policy key …`.
  The values in `PHI_COLUMNS` are already valid — tell the team to use them, not invent `'high'`.
- **Expected:** coverage check = 0 missing; `information_schema.column_tags` lists ~20 (key, column)
  rows (8 identifier columns carry both `phi` + `data_sensitivity`; clinical/quasi carry the right mix).

## NB 02 — column masks (🧠 THE CORE — Josh #14, half 1) · ✅ validated

```python
spark.sql(f"""CREATE OR REPLACE FUNCTION {fqn('mask_person_id')}(pid BIGINT)
  RETURN CASE WHEN is_account_group_member('{OCDO_GROUP}') THEN NULL ELSE pid END""")

spark.sql(f"""CREATE OR REPLACE FUNCTION {fqn('mask_note_text')}(txt STRING)
  RETURN CASE WHEN is_account_group_member('{OCDO_GROUP}')
              THEN '***REDACTED PATHOLOGY NOTE***' ELSE txt END""")

spark.sql(f"ALTER TABLE {fqn('person')} ALTER COLUMN person_id SET MASK {fqn('mask_person_id')}")
spark.sql(f"ALTER TABLE {fqn('note')}   ALTER COLUMN person_id SET MASK {fqn('mask_person_id')}")
spark.sql(f"ALTER TABLE {fqn('note')}   ALTER COLUMN note_text SET MASK {fqn('mask_note_text')}")
```

- **Return type must match the column type.** `person_id` is BIGINT → return NULL (or a hashed BIGINT);
  `note_text` is STRING → return a redaction literal.
- **⚠ Owner bypasses masks.** By default the table owner / metastore admin sees raw even with a mask
  bound — this is correct UC behavior, not a bug. To *prove* the mask, use the UDF-decision cell
  (`SELECT mask_note_text('REAL NOTE')` — returns the literal for a group member), or have a non-owner
  group member query the table. On FEVM the owner is not in `ocdo_data_scientists`, so the
  `information_schema.column_masks` read-back is the cleanest proof the masks are *bound*.
- **Expected:** `column_masks` shows 3 rows (person.person_id, note.person_id, note.note_text). Validated.

## NB 03 — row filters + ABAC (🧠 THE CORE — Josh #14, half 2) · ✅ GA validated; ABAC gated (preview)

```python
spark.sql(f"""CREATE OR REPLACE TABLE {fqn('research_consent')} AS
  SELECT person_id, (person_id % 10 < 7) AS research_consented FROM {fqn('person')}""")

spark.sql(f"""CREATE OR REPLACE FUNCTION {fqn('consent_row_filter')}(pid BIGINT)
  RETURN NOT is_account_group_member('{OCDO_GROUP}')
    OR pid IN (SELECT person_id FROM {fqn('research_consent')} WHERE research_consented)""")

for t in OMOP_TABLES:
    spark.sql(f"ALTER TABLE {fqn(t)} SET ROW FILTER {fqn('consent_row_filter')} ON (person_id)")
```

- **Gotcha:** the filter MUST return TRUE for the data office (`NOT is_account_group_member(...)`),
  else *you* lose all rows too. The OCDO branch returns TRUE only for consented `person_id`s.
- **Gotcha:** `ON (person_id)` names the column fed to the UDF — it must exist on the bound table.
- **Expected:** `row_filters` shows the filter on all 6 tables; owner sees 300, an OCDO member would
  see the consented subset (~210 with the `% 10 < 7` rule). Validated.
- **ABAC (the EXTENSION cell):** the `CREATE POLICY … MATCH COLUMNS hasTagValue('phi','other_identifier')`
  form is **preview and may be gated.** **CONFIRMED gated on FEVM2** (`SHOW POLICIES ON CATALOG` returns
  empty; the try/except caught it and the notebook stayed green). The GA per-table masks/filters already
  deliver Josh's ask — this is the documented fallback. Retry the `CREATE POLICY` DDL once the
  tag-based-ABAC preview is enabled for FH; the kit needs no change.
- **Validated on FEVM2:** consent = 300 total / **210 consented** (owner sees 300, an OCDO member sees
  210 — the filter demonstrably changes output). Mask proven both branches: owner → `1042` / raw note;
  group member → `NULL` / `***REDACTED PATHOLOGY NOTE***`.

## NB 04 — PHI identifier search (GUIDED TODO — Gina, Ty #4) · ✅ validated

```python
TARGET_PERSON_ID = spark.sql(f"SELECT MIN(person_id) AS pid FROM {fqn('person')}").first()["pid"]
hits = []
for t in OMOP_TABLES:
    n = spark.sql(f"SELECT COUNT(*) AS n FROM {fqn(t)} WHERE person_id = {TARGET_PERSON_ID}").first()["n"]
    hits.append((t, n))
display(spark.createDataFrame(hits, ["table", "rows_with_identifier"]))
```

- The structural searches are pre-built. **`information_schema` column-name gotcha:** `column_tags` uses
  `schema_name`; `column_masks` / `row_filters` use `table_schema`. The pre-built cells use the right
  names — if a team writes their own audit query, this is the usual error.
- **Expected:** the target `person_id` appears across the tables it has rows in (person=1,
  condition_occurrence ≥1, measurement/observation/drug_exposure/note as applicable). Validated.

## NB 05 — AI-feature governance (guided + light TODO — Gina, Ty #5) · ✅ validated (FM + serving available on FEVM2)

- The teaching point is conceptual and pre-built: **AI features run as the user and inherit UC masks /
  row filters / grants — not a bypass.** The `ai_query` demo proves the model receives the masked value
  for a researcher. If `databricks-claude-haiku-4-5` is gated, skip the demo and use the limits table +
  checklist.
- TODO (serving usage):
```python
display(spark.sql("""
  SELECT requester AS user, served_entity_name AS endpoint, COUNT(*) AS calls
  FROM system.serving.endpoint_usage
  WHERE usage_start_time >= current_date() - INTERVAL 30 DAYS
  GROUP BY requester, served_entity_name ORDER BY calls DESC"""))
```
  `system.serving.endpoint_usage` shape/availability varies by workspace — fall back to
  `system.access.audit` filtered to serving actions if absent. **On FEVM2 both `ai_query`
  (`databricks-claude-haiku-4-5`) and `system.serving.endpoint_usage` are available and validated.**

## NB 06 — inactive-users report (GUIDED TODO — Gina, Ty #3) · ✅ validated (`system.access.audit` available on FEVM2)

```python
report = spark.sql("""
  WITH activity AS (
    SELECT user_identity.email AS user_email, MAX(event_time) AS last_seen
    FROM system.access.audit
    WHERE user_identity.email IS NOT NULL AND user_identity.email LIKE '%@%'
    GROUP BY user_identity.email)
  SELECT user_email, last_seen,
         datediff(current_timestamp(), last_seen) AS days_since_last_seen,
         last_seen < current_timestamp() - INTERVAL 90 DAYS AS inactive_over_90d
  FROM activity ORDER BY days_since_last_seen DESC""")
display(report)
```

- **Gotcha:** the actor is the struct field `user_identity.email`; filter out null/system actors.
- **"Nobody is dormant"** on a fresh workspace is expected — the value is the standing query +
  `days_since_last_seen` ranking. Requires the `system.access` schema enabled. **On FEVM2
  `system.access.audit` is readable (~2.5B events) and the report logic ran green.**
