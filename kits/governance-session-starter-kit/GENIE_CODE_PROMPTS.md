# 💬 Genie Code: starter prompts (Governance / PHI on OMOP)

**Fred Hutch onsite · Governance session · Genie Code over the shared OMOP foundation tables**

The build is **free-form**. The foundation is already up, the 6 shared OMOP tables are the ones every
group works from, and `_config` holds the PHI map and the governed-tag vocabulary. From here **you
design the governance solution your data office actually needs.** These are **starter prompts** to get
Genie Code moving. Change them, combine them, reorder them, or ignore them and ask your own. The goal is
a governed dataset *your team* designed, not a filled-in worksheet.

> **How to drive Genie Code well:** paste one prompt at a time; **review the diff before you Accept**
> (never "Accept all" on policy code); let it **persist work as real notebooks/SQL**, not scratch. This
> chat runs on a SQL warehouse, masks, filters, and tags are all SQL, so it fits inline. Point it at
> the specific notebook page when you want an edit to land there.

> **🔒 The point, say it to Genie Code:** set classification and policy at the **catalog and schema
> level** on the shared foundation. A policy changes what *everyone* sees, and that is the goal: the
> data office protects the data every group uses. Because the policy is group-gated, the data office
> sees raw and researchers see masked, and because it sits high in the hierarchy it inherits to every
> new table the DE and ML tracks build.

> **Synthetic data only, everything UC-scoped.** No real PHI, no `hive_metastore`.

---

### 1. Profile and find the PHI (the warm-up)
> **"Profile the 6 OMOP tables in the shared foundation schema: row counts and columns. Then tell me which columns are patient identifiers vs. clinical facts, and propose how to classify each using only the governed tag values in `_config`'s `PHI_COLUMNS` map. Don't apply anything yet, show me the plan."**

*Good looks like:* a column inventory and a proposed `phi` / `data_sensitivity` tag per column, using the
**allowed** values only (no invented `'high'` / `'direct_identifier'`). This is your classification plan
for prompt 2.

---

### 2. Tag and classify every PHI column  *(nb 01 · Josh #14 / Gina, Ty)*
> **"Apply the classification: tag each identifier column with `phi` and `data_sensitivity`, and each clinical column with `data_sensitivity` only, using the exact governed values from `PHI_COLUMNS`. Then run a coverage check that lists any PHI column still missing a tag."**

*Good looks like:* `information_schema.column_tags` covers every PHI column, coverage check = **0
missing**. If Genie Code hits *"Tag value X is not an allowed value for tag policy key phi"*, that's the
governed vocabulary doing its job; feed it the allowed values from `PHI_COLUMNS`.

---

### 3. Mask the identifiers by group  *(nb 02 · Josh #14, the core)*
> **"Author two masking UDFs (`mask_person_id` (BIGINT → NULL) and `mask_note_text` (STRING → a redaction string)) that return the raw value when the caller is in the data-office group and the masked value otherwise, gating on `is_account_group_member(<my ocdo_group>)`. Then bind them to `person.person_id`, `note.person_id`, and `note.note_text` on the shared foundation tables."**

*Good looks like:* `information_schema.column_masks` lists the 3 masks. A mask UDF must **return the
column's type** (person_id → NULL/BIGINT, not a string). Remember the **owner bypasses masks**. Prove
the redaction with the UDF-decision cell or a non-owner, not by expecting your own query to redact.

---

### 4. Filter the rows by consent/entitlement  *(nb 03 · Josh #14, the core)*
> **"Create a `consent_row_filter(person_id)` that returns TRUE for the data office (`NOT is_account_group_member(...)`) and only consented rows for the OCDO group, then `SET ROW FILTER ... ON (person_id)` across the patient tables on the shared foundation."**

*Good looks like:* `information_schema.row_filters` shows the filter on all 6 tables; the count cell
shows **owner = 300 vs. the consented subset** an OCDO member sees. If the owner loses all rows too,
they dropped the `NOT is_account_group_member(...)` branch.

---

### 4b. Scale it: one tag-based policy, catalog-wide  *(nb 03 · the scalable core)*
> **"Now make it scale. Instead of binding a mask to each column by hand, write one tag-based ABAC policy (`CREATE POLICY`) that masks every column carrying the `phi` tag for anyone outside the data-office group, and apply it at the catalog level. Prove that a newly tagged column is masked with no new code, and confirm it would cover a table the DE or ML group builds later."**

*Good looks like:* one policy that follows the tag everywhere, classify once and the policy travels with
the tag. This is the scalable target: you set it high, and it inherits to every new table. If
`CREATE POLICY` is preview-gated on this metastore, that is expected, log it as a **preview feature to
request for FH** and keep the per-column binds from prompt 3 as today's fallback.

---

### 5. Prove the policy actually changed what a user sees
> **"Show me `SELECT person_id, note_text FROM person`/`note` as the owner, then explain exactly what a member of my `ocdo_group` would get back instead, masked identifiers and only consented rows. Give me one query I can run to demonstrate the before/after in the room."**

*Good looks like:* a crisp owner-vs-researcher contrast. This is the moment that matters when you hold
real patient data: the policy holds *in the data layer* no matter who queries (notebook, SQL, Genie, BI).

---

### 6. Find where an identifier hides  *(nb 04 · Gina, Ty #4)*
> **"For a target `person_id`, scan every patient table in my schema and report which tables it appears in and how many rows. Also do a structural search: list every column tagged `phi = other_identifier` across the catalog."**

*Good looks like:* a by-value hit list and a tag-based structural inventory, "here is everywhere this
patient identifier lives," which is exactly the question a data-subject request or an audit asks.

---

### 7. Know the AI-feature limits  *(nb 05 · Gina, Ty #5)*
> **"Run an `ai_query` over a masked column as a researcher and show me the model receives the MASKED value, prove AI features run as the user and inherit our masks. Then build a serving-usage report from the system tables: who called which endpoint."**

*Good looks like:* the `ai_query` cell shows the mask flowing through (AI is **not** a governance
bypass) + a usage report. If the FM endpoint or `system.serving` table isn't reachable, lean on the
conceptual limits table and move on, it's gated plumbing, not the lesson.

---

### 8. Audit dormant accounts  *(nb 06 · Gina, Ty #3)*
> **"From `system.access.audit`, build a per-user report with `last_seen`, `days_since_last_seen`, and an `inactive_over_90d` flag, ranked by longest dormant. Persist it as a table I can re-run monthly."**

*Good looks like:* a ranked standing report. On a fresh workshop workspace nobody is inactive yet,
that's fine; the value is the **re-runnable query**, not a hit today.

---

### 🧩 Now design your own (the open part)
You have a governed dataset, extend it however your data office would:

- *"Build a clean researcher-facing view over the masked/filtered tables and grant only the OCDO group SELECT on it."*
- *"Stand up an audit dashboard: tag coverage %, columns with masks, row-filter bindings, and dormant accounts on one page."*

**Optional: expose it via a self-serve Genie space.** Any team can install the workspace-level
`prompt-to-genie` skill (see the README) and say **"create a Genie space"** over your **masked/filtered
views**, researchers self-serve in natural language and *still* never see raw PHI. A Genie space that
inherits your governance is a strong thing to demo.

If a policy behaves unexpectedly, the worked solution for every step is in `reference/ANSWER_KEY.md`,
but reveal it late on the gating logic (that's the learnable core) and early on the governed-tag
vocabulary (that's just plumbing).
