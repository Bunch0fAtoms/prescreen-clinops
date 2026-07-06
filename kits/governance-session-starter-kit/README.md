# 🛡️ Governing PHI on OMOP with Unity Catalog — Governance Session Starter Kit

**Fred Hutch onsite · Governance session · notebooks (UC-scoped)**

This is a **starter build kit**, not a finished solution. The hard plumbing is already wired for you
— six synthetic OMOP tables (deep-cloned into your own schema so you can't break anyone else's data),
the PHI column map, helper functions, and a verification harness that *proves* a policy actually
changed what a user sees. **You** build the learnable core: the masking UDFs, the row-filter logic,
and the group-gating that decides who sees a patient identifier and who sees `***MASKED***`. Look for
`# TODO (you build this)` markers — that is your work.

> Scaffold, don't hand-hold. The notebooks tell you *what* to build and *why*; you write the policy
> logic. If a team gets truly stuck, the mentor has an answer key (see `reference/`).

---

## 🎯 The outcome you are shipping

Fred Hutch's data office (OCDO/DASL) must let researchers do science on an OMOP clinical warehouse
**without ever exposing PHI they don't need.** You'll build the Unity Catalog controls that make that
true *in the data layer* — so the policy holds no matter who queries (notebook, SQL, Genie, app, BI):

| Control | What it does | Notebook |
|---|---|---|
| **Tags / classification** | Label every PHI column so policy & audit can find it | `01` |
| **Column masks** | A researcher sees `***MASKED***` where the owner sees `person_id` / `note_text` | `02` |
| **Row filters + ABAC** | A group only sees the patient *rows* it's entitled to | `03` |
| **Identifier search** | Find everywhere a patient identifier appears across catalogs | `04` |
| **AI-feature governance** | Know the limits before turning Genie / AI functions on over PHI | `05` |
| **Inactive-user audit** | Surface accounts dormant > 90 days (least-privilege hygiene) | `06` |

The headline FH ask anchoring this session is **Josh #14 — mask patient data + filter access by OCDO
user group** (notebooks 02 + 03). Plus **Gina, Ty #3** (inactive users), **#4** (identifier search), and
**#5** (AI-feature limits).

---

## 🧱 What's pre-built vs. what you build

| Component | Status |
|---|---|
| 6 synthetic OMOP tables (deep-cloned into your governed schema) | ✅ **Pre-built** — the setup step lands them |
| `_config` shared catalog/schema/warehouse + the PHI column map + governed-tag vocabulary | ✅ **Pre-built** |
| The verification harness (owner-view vs. masked/filtered projection) | ✅ **Pre-built** |
| Apply UC **tags** to every PHI column (nb 01) | 🛠️ **You build** (Day-1 shared anchor) |
| **Masking UDFs** + binding (`person_id`, `note_text`) by OCDO group (nb 02) | 🧠 **You build** (the core) |
| **Row-filter UDF** + binding by OCDO group (nb 03) | 🧠 **You build** (the core) |
| Tag-based **ABAC policy** (nb 03) | 🚀 **Stretch** — attempt; preview, may be gated |
| **Identifier-search** by value across tables (nb 04) | 🛠️ **You build** |
| AI-feature limits walkthrough + serving-usage report (nb 05) | ✅ guided + 🛠️ light TODO |
| **Inactive-users >90d** report from system tables (nb 06) | 🛠️ **You build** |

---

## 🚀 How to deploy

This kit is **Unity-Catalog-scoped** and runs on synthetic data only (no PHI). The **recommended** way
to stand it up is the shared **`fred-hutch-onsite-adaptation`** Genie Code skill — installed **once at
the workspace level** (not per repo), it adapts whichever onsite kit you're working in by reading that
kit's `ADAPTATION_FACTS.json` (shipped beside this README). The manual paths below (deep-clone or
generate) are the fallback and are what the skill runs for you.

### Recommended — drive it with the workspace-level onsite handoff skill ("run in my workspace")
Genie Code does **not** auto-load skills, so install the shared skill once per workspace, then drive it
from a fresh chat in this kit's folder:

1. **Install the skill once per workspace** (shared across all four onsite kits — skip if already done).
   Run it in a **workspace web terminal** (authenticates as you, nothing to edit); the wildcard finds
   your imported repo copy, so it works from any directory:
   ```bash
   cd /Workspace/Users/*/prescreen-clinops && databricks workspace import-dir \
     .assistant/skills/fred-hutch-onsite-adaptation \
     /Workspace/.assistant/skills/fred-hutch-onsite-adaptation
   ```
2. **Open Genie Code in a fresh chat, in this kit's folder** (hard-refresh first — skills cache per tab) and say:
   > run in my workspace

   The skill reads **this kit's `ADAPTATION_FACTS.json`**, auto-detects your workspace, current user, catalog, and a running warehouse; confirms your
   **governance** schema (default `clinops_gov`) and the `ocdo_group`; and writes **only**
   `databricks.yml`'s target variables — Accept the diff. It then **runs the deep-clone setup job** so
   the 6 OMOP tables land in your own schema (Option A below), emitting the web-terminal commands and
   stopping (it never deploys from inside Genie Code).
   > **Isolation is enforced for you:** the skill clones into your governance schema, never binds
   > policies to a shared source schema.

### Also install the Genie-space skill (any team may want one)
The build is free-form — your team may decide a **self-serve Genie space** over the governed tables is
part of the solution. Install the community `prompt-to-genie` skill once at the workspace level as a
Git folder at the skill path, so it stays updatable from source:
```bash
databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
  --path /Workspace/.assistant/skills/prompt-to-genie
```
Then in a fresh Genie Code chat say **"create a Genie space"** over your **masked/filtered** views — a
Genie space that inherits your governance is a strong governance demo. See `GENIE_CODE_PROMPTS.md` for
build starter prompts.

### Fallback — configure by hand
Two ways to land the data:

### Option A — deep-clone from an existing OMOP schema (what FEVM uses)
If the 6 OMOP tables already exist in a source schema (e.g. the shared foundation schema `clinops_foundation`),
clone them into your own **governance** schema so you can apply policies in isolation:

```sql
CREATE SCHEMA IF NOT EXISTS <catalog>.clinops_gov;
-- repeat for all 6: person, condition_occurrence, measurement, observation, drug_exposure, note
CREATE TABLE <catalog>.clinops_gov.person
  DEEP CLONE <catalog>.<source_schema>.person;
```

(There's a ready-made setup job in `resources/setup_clone_job.yml` that does all 6 — see below.)

### Option B — generate fresh synthetic data
Use the **ML-session kit's** generator (`ml-session-starter-kit/src/data_generation/`) to land the 6
tables, then point this kit's `schema` widget at them. The schemas are identical.

### Then
1. Open the notebooks in your workspace, start at **`00_START_HERE`**.
2. Set the widgets: `catalog`, `schema` (default `clinops_gov`), `warehouse_id`, and
   `ocdo_group` (the researcher group masks/filters gate on).
3. Work through `01` → `06` in order. Each notebook `%run ./_config` so they share one
   catalog/schema/warehouse/group.

> **Isolation matters.** Apply governance to your **own** cloned schema, not a shared source schema
> — masks and row filters change what *everyone* sees, so never bind them to data another track depends on.

---

## 🔒 Ground rules (security-first customer)

- **Everything is Unity-Catalog-scoped** — catalog/schema/group come from widgets/bundle variables.
  No `hive_metastore`, ever.
- **Synthetic data only.** No real PHI in this kit.
- **No hardcoded secrets.** No tokens, keys, or passwords in code.
- **Governance is the product here.** Masks, filters, tags, and audits are the deliverable — every one
  of them is *provable* (the kit shows the before/after), which is exactly what a SOC2 reviewer wants.
- **Governed tag vocabulary.** This metastore enforces *governed tag policies* — `phi` and
  `data_sensitivity` only accept values from an allowed list (HIPAA Safe Harbor identifier types;
  `official` / `official_sensitive`). The kit uses the allowed values; a typo is rejected by UC, which
  is the point.

---

## 🗂️ Repo layout

```
governance-session-starter-kit/
  README.md             ← you are here
  databricks.yml        ← DAB: UC-scoped per-team target (catalog/schema/warehouse/group)
  RUNBOOK.md            ← MENTOR build-level facilitation (Checkpoints 1–6, failure modes)
  GENIE_CODE_PROMPTS.md ← ready-to-use Genie Code build prompts (free-form; starters, not a script)
  STRETCH.md            ← "make it your own" extension ideas
  notebooks/            ← the team scaffold (00–06): pre-built plumbing + your TODOs
  reference/            ← SA-ONLY answer key (mentor reveals only if a team is stuck)
  resources/            ← the DAB setup job that deep-clones the 6 OMOP tables
```

## 📒 The notebook arc

| # | Notebook | What it builds | Your job? |
|---|---|---|---|
| — | `_config` | shared catalog/schema/warehouse/group + PHI map | ✅ pre-built |
| 00 | `00_START_HERE` | overview, foundation check, the governance arc | ✅ read it |
| 01 | `01_discover_and_classify` | scan 6 tables, tag every PHI column | 🛠️ classify (Day-1 anchor) |
| 02 | `02_column_masks` | column masks on `person_id` / `note_text` by group | 🧠 the masking core |
| 03 | `03_row_filters_abac` | row filters + tag-based ABAC by group | 🧠 the filter core |
| 04 | `04_phi_identifier_search` | where does an identifier appear across catalogs | 🛠️ build the search |
| 05 | `05_ai_feature_governance` | Genie/AI-function limits over PHI | ✅ guided + light TODO |
| 06 | `06_inactive_users_report` | users inactive > 90 days via system tables | 🛠️ build the audit |
