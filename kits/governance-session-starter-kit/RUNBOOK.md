# 🧭 RUNBOOK — Governance Session (build-level facilitation)

**Mentor-facing. Build-level only.** Event-level facilitation (agenda, room dynamics, the
security-first framing, debrief) lives in the onsite agenda — don't duplicate it here. This runbook is
the per-build-block detail: what's pre-built, what the team builds, the named **Checkpoints**, common
failures, and the answer-key fallback.

**Customer:** Fred Hutch · Governance section of the 2-day onsite. Governance is the **spine** of this
onsite — this section builds the tag→mask→row-filter pattern on the shared Day-1 bronze foundation,
and Josh rotates into the DE/ML tracks to apply it to their silver/gold/models.
**Team:** OCDO/DASL data office — comfortable with SQL and Unity Catalog concepts; the learnable core
here is *policy authoring* (mask/filter UDFs that gate on group membership), not SQL itself.
**Outcome:** a governed PHI warehouse where researchers do science without touching raw identifiers,
and the data office can prove who sees what. **Security-first:** synthetic data only, all UC-scoped.

**Reveal ladder:** nudge → hint (point at the `# TODO`) → **point at the matching prompt in
`GENIE_CODE_PROMPTS.md`** → pair → reveal (`reference/ANSWER_KEY.md`). Reveal **late** on the learnable
core (the gating logic); reveal **early** on plumbing and anything PHI/security-sensitive (you never want
a team improvising masks on real-looking data).

**Free-form build.** This session is intentionally open — the team designs their own governance solution
on the foundation. `GENIE_CODE_PROMPTS.md` holds ready-to-use Genie Code build prompts (numbered to the
notebooks, each with a "good looks like"); treat them as *starters the team can adapt*, not a script.
The checkpoints below still define "done" no matter which path they take.

---

## Block 0 · Setup & foundation (pre-build)

- **Pre-built:** the DAB, the deep-clone setup job, `_config` (PHI map + governed-tag vocabulary).
- **Team does:** fill `databricks.yml` (source + client catalog/schema, warehouse, `ocdo_group`);
  `databricks bundle deploy` + `databricks bundle run setup_clone_job`; open `00_START_HERE`, set the
  four widgets, run the foundation check.
- **🚩 Checkpoint 1 — Foundation up.** `00` row counts: person≈300, condition_occurrence≈300,
  measurement≈720, observation≈720, drug_exposure≈383, note≈265 — all 6 present in the **governance**
  schema (`clinops_gov`), not the source.
- **Common failures:**
  - *Bound policies to the shared source schema* → **the cardinal sin.** Masks/filters change what
    *everyone* sees; never bind to a schema the ML/DE tracks read. Confirm the `schema` widget is the
    cloned `clinops_gov`, not the source.
  - *`CREATE CATALOG` permission denied* → expected on a shared metastore; the catalog already exists,
    so `_config` skips creation when the schema is present. Plumbing — reveal/fix early.

## Block 1 · Discover & classify (nb 01) — GUIDED TODO (Day-1 shared anchor)

- **Pre-built:** the column inventory, the note preview, the `PHI_COLUMNS` map, the governed-vocabulary
  reference, the coverage check.
- **Team builds:** the tagging loop — apply `phi` (identifier type) + `data_sensitivity` to every PHI
  column, using the **governed allowed values** straight from `PHI_COLUMNS`.
- **🚩 Checkpoint 2 — Everything classified.** The coverage cell shows zero missing; `information_schema
  .column_tags` lists every tagged column. The catalog now *knows* what's sensitive.
- **Common failures:**
  - *⚠ `Tag value X is not an allowed value for tag policy key phi`* → **THE governed-tag gotcha.** This
    metastore constrains `phi` to HIPAA types and `data_sensitivity` to `official`/`official_sensitive`.
    The fix is to use the values already in `PHI_COLUMNS` (don't invent `'high'`/`'direct_identifier'`).
    Reveal early — it's the vocabulary, not the lesson.
  - *Tagged the `phi` key on a clinical column* → clinical facts aren't HIPAA identifiers; tag them with
    `data_sensitivity` only (the `phi_type is None` branch).

## Block 2 · Column masks (nb 02) — 🧠 THE CORE (Josh #14, half 1)

- **Pre-built:** the "before" projection, the masking pattern cheat-sheet, the verification cells
  (UDF-decision-for-current-user, masked projection, `information_schema.column_masks` read-back).
- **Team builds:** two masking UDFs (`mask_person_id` BIGINT→NULL, `mask_note_text` STRING→redaction)
  gating on `is_account_group_member(OCDO_GROUP)`, then `ALTER TABLE … SET MASK` to bind them.
- **🚩 Checkpoint 3 — Masks bound & provable.** `column_masks` shows masks on `person.person_id`,
  `note.person_id`, `note.note_text`; the team can articulate "owner sees raw, OCDO researcher sees
  NULL/redaction." **Make them say why a column-level policy beats a per-query rule.**
- **Common failures:**
  - *Return type mismatch* → a mask UDF must return the column's type. `person_id` is BIGINT → return
    NULL (or a hashed BIGINT), not a string. ANSWER_KEY nb 02.
  - *"It doesn't redact for me!"* → the **owner bypasses masks** by default. That's correct UC behavior.
    Prove it via the UDF-decision cell, or have a non-owner / group member run it. Don't let this read
    as a bug.
  - *Group doesn't exist* → `is_account_group_member` returns FALSE for a non-existent group, which is
    fine for the build; point the `ocdo_group` widget at a real group to demo the flip.

## Block 3 · Row filters + ABAC (nb 03) — 🧠 THE CORE (Josh #14, half 2)

- **Pre-built:** the synthetic `research_consent` set, the row-filter pattern cheat-sheet, the
  row-count verification, the `information_schema.row_filters` read-back, AND the ABAC attempt wrapped
  in try/except.
- **Team builds:** `consent_row_filter(pid)` returning TRUE for the data office (`NOT
  is_account_group_member`) and only consented rows for the OCDO group, then `ALTER TABLE … SET ROW
  FILTER … ON (person_id)` across the patient tables.
- **🚩 Checkpoint 4 — Filter bound & provable.** `row_filters` shows the filter on all 6 tables; the
  count cell shows owner=300 vs. the consented subset an OCDO member would see. Combined with nb 02,
  **this is Josh's full ask delivered.**
- **Common failures:**
  - *Owner loses all rows too* → they forgot the `NOT is_account_group_member(...)` branch; the filter
    must return TRUE for the data office. ANSWER_KEY nb 03.
  - *`ON (person_id)` column missing* → bind only to tables that have `person_id` (all 6 do here).
  - *ABAC cell errors* → **expected — it's preview.** The try/except keeps the notebook green and prints
    the fallback message. Treat it as a documented preview to request, not a failure. The GA row-filter
    path already satisfies the ask.

## Block 4 · PHI identifier search (nb 04) — GUIDED TODO (Gina, Ty #4)

- **Pre-built:** the tag-based structural search, the name/type heuristic search, the lineage query.
- **Team builds:** the by-value scan — loop the patient tables counting rows for a target `person_id`.
- **🚩 Checkpoint 5 — Identifier located.** The by-value scan reports which tables contain the target
  identifier; the structural search lists every `phi=other_identifier` column.
- **Common failure:** *`information_schema` column-name confusion* → `column_tags` uses `schema_name`;
  `column_masks`/`row_filters` use `table_schema`. The pre-built cells use the right names; if a team
  writes their own, point at the working ones.

## Block 5 · AI-feature governance (nb 05) — guided + light TODO (Gina, Ty #5)

- **Pre-built:** the limits table, the "AI reads through the mask" `ai_query` demo, the test-before-
  expand checklist.
- **Team builds:** the serving-usage report from system tables (who called which endpoint).
- **🚩 Checkpoint 6 — The story lands.** The team can state: "AI features run *as the user* and inherit
  our masks/row filters; they are not a governance bypass." The `ai_query` cell shows the model
  receiving the masked value for a researcher.
- **Common failures:**
  - *FM endpoint gated* → the `ai_query` demo is wrapped/optional; if `databricks-claude-haiku-4-5`
    isn't reachable, skip it and lean on the conceptual table + checklist.
  - *`system.serving.endpoint_usage` absent* → table shape varies by workspace; fall back to
    `system.access.audit` filtered to serving actions, or note it as not-enabled and move on.

## Block 6 · Inactive-users report (nb 06) — GUIDED TODO (Gina, Ty #3)

- **Pre-built:** the audit-table readability check, the last-seen pattern cheat-sheet, the persist cell.
- **Team builds:** the per-user `last_seen` / `days_since_last_seen` / `inactive_over_90d` query over
  `system.access.audit`.
- **🚩 Checkpoint 7 — The audit runs.** A ranked report by `days_since_last_seen` renders.
- **Common failures:**
  - *`system.access.audit` not enabled* → an account admin enables the `system.access` schema; the
    readability cell prints a clear message. Note it and move on if it can't be enabled in the room.
  - *"Nobody is inactive"* → on a fresh workshop workspace everyone is recently active. That's fine —
    the report's value is the *standing query* + the `days_since_last_seen` ranking, not a hit today.

---

## Quick reference — checkpoint summary

| # | Checkpoint | Signal it's met |
|---|---|---|
| 1 | Foundation up | 6 tables in the **governance** schema, counts ≈ 300/300/720/720/383/265 |
| 2 | Everything classified | `column_tags` covers all PHI columns; coverage check = 0 missing |
| 3 | Masks bound & provable | `column_masks` lists the 3 masks; owner-vs-group story articulated |
| 4 | Filter bound & provable | `row_filters` on all 6 tables; owner 300 vs. consented subset |
| 5 | Identifier located | by-value scan + structural search return the target |
| 6 | AI story lands | "AI inherits the masks; not a bypass" + `ai_query` demo |
| 7 | Audit runs | ranked inactive-user report from `system.access.audit` |

**Safety net, always:** `reference/ANSWER_KEY.md` carries the worked solution for every TODO plus the
gotchas. Reveal it as a last resort to keep a team moving — never as a substitute for the learnable
core (the group-gating logic), and reveal **early** on plumbing and the governed-tag vocabulary.
