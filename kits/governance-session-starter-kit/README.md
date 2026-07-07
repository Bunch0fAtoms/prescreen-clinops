# 🛡️ Governing PHI on OMOP with Unity Catalog: Governance Session Starter Kit

**Fred Hutch onsite · Governance session · notebooks (UC-scoped)**

This is a **starter build kit**, not a finished solution. The hard plumbing is already wired for you:
the six shared synthetic OMOP foundation tables every group works from, the PHI column map, helper
functions, and a verification harness that *proves* a policy actually changed what a user sees. **You**
build the learnable core: the classification, the masking and row-filter logic, and the tag-based policy
that decides who sees a patient identifier and who sees `***MASKED***`, catalog-wide. You build it with
**Genie Code**; the pre-built notebooks and answer key are the facilitator's backup if a team stalls.

> Scaffold, don't hand-hold. The notebooks tell you *what* to build and *why*; you write the policy
> logic. If a team gets truly stuck, the mentor has an answer key (see `reference/`).

---

## 🎯 The outcome you are shipping

Fred Hutch's data office (OCDO/DASL) lets researchers do science on the shared OMOP clinical data
**without ever exposing PHI they don't need.** You'll build the Unity Catalog controls that make that
true *in the data layer*, so the policy holds no matter who queries (notebook, SQL, Genie, app, BI):

**These are the questions your team submitted.** This session is built around them, in your own words.

| The Fred Hutch ask (verbatim) | Where it lands |
|---|---|
| *"I have a set of patients that need their data masked and only exposed based on an internal user's group. How do I go about masking these patients and setting up a filter to allow specific OCDO users access to their data?"* (Josh) | Column masks and row filters, the core of the session (nb 02 and 03) |
| *"I would like to see a report when users have been inactive for more than 90 days in any DBX environment."* (Gina) | Inactive-user audit over system tables (nb 06) |
| *"I would like to search for whether a patient identifier shows up in catalogs or schemas shared to researchers."* (Gina) | Identifier search, by value and by tag (nb 04) |
| *"I would like to understand what restrictions or limitations are available when enabling AI features such as Genie."* (Gina) | AI-feature governance walkthrough (nb 05) |

> **You already gathered your requirements.** In the Day 1 whole-room Genie session
> (`../../foundation/DISCOVERY.md`), the room asked real questions of the data and you watched which
> columns identify a patient and who should see what. That list is your starting point here. The tags,
> masks, and filters below turn what you saw into enforced policy. The pre-built PHI column map is a
> safety net so nothing slips through, not a replacement for what the room found.

| Control | What it does | Notebook |
|---|---|---|
| **Tags / classification** | Label every PHI column so policy and audit can find it | `01` |
| **Column masks** | A researcher sees `***MASKED***` where the owner sees `person_id` / `note_text` | `02` |
| **Row filters and tag-based ABAC** | Gate rows by entitlement, then one policy that follows the tag catalog-wide | `03` |
| **Identifier search** | Find everywhere a patient identifier appears across catalogs | `04` |
| **AI-feature governance** | Know the limits before turning Genie / AI functions on over PHI | `05` |
| **Inactive-user audit** | Surface accounts dormant > 90 days (least-privilege hygiene) | `06` |

The headline ask anchoring this session is **Josh's, mask patient data and filter access by OCDO user
group** (notebooks 02 and 03). The rest round out a full governance posture: an inactive-user audit,
identifier search, and knowing the AI-feature limits before turning them on.

---

## 🧱 What's pre-built vs. what you build

| Component | Status |
|---|---|
| The 6 shared OMOP foundation tables (the same tables every group uses) | ✅ **Pre-built by the foundation** |
| `_config` shared catalog/schema/warehouse, the PHI column map, and the governed-tag vocabulary | ✅ **Pre-built** |
| The verification harness (owner-view vs. masked/filtered projection) | ✅ **Pre-built** |
| Apply UC **tags** to every PHI column (nb 01) | 🛠️ **You build** (Day-1 shared anchor) |
| **Masking UDFs** and binding (`person_id`, `note_text`) by OCDO group (nb 02) | 🧠 **You build** (see the mechanism) |
| **Row-filter UDF** and binding by OCDO group (nb 03) | 🧠 **You build** (the core) |
| Tag-based **ABAC policy**, one policy that follows the tag catalog-wide (nb 03) | 🧠 **You build** (the scalable core; preview, may be gated) |
| **Identifier-search** by value across tables (nb 04) | 🛠️ **You build** |
| AI-feature limits walkthrough and serving-usage report (nb 05) | ✅ guided, plus 🛠️ light TODO |
| **Inactive-users >90d** report from system tables (nb 06) | 🛠️ **You build** |

---

## 🚀 How to start

This kit is **Unity-Catalog-scoped** and runs on synthetic data only (no PHI). **There is no bundle to
deploy and no data to clone.** The shared **foundation** already stood up the six OMOP tables every
group works from. Your job is to govern those shared tables in place. You drive the whole build with
**Genie Code**; the pre-built notebooks and answer key are the facilitator's backup if a team stalls.

> **Govern the shared tables, that is the point.** Set classification and policy at the **catalog and
> schema level** on the shared foundation. Your masks, row filters, and tag-based policy protect the
> data every group uses, and because they sit high in the hierarchy, they cover every table the other
> groups build next, with no rework. Governance affecting shared data is the goal here, not a hazard to
> engineer around.

### The adaptation skill helps Genie Code build well
The workspace-level **`fred-hutch-onsite-adaptation`** skill is not a value-filler. It gives Genie Code
the context it needs to build clean governance on the first pass, the PHI map, the governed-tag
vocabulary, and the shared-foundation table names, and when your team is ready to point at real
`curated_omop` data, it tells Genie Code exactly how to adapt. A workspace admin installs it once, for
everyone (this is separate from anything you run):

```bash
cd /Workspace/Users/*/prescreen-clinops && databricks workspace import-dir \
  .assistant/skills/fred-hutch-onsite-adaptation \
  /Workspace/.assistant/skills/fred-hutch-onsite-adaptation
```

Then open Genie Code in a fresh chat in this kit's folder (hard-refresh first, skills cache per tab)
and start building. `GENIE_CODE_PROMPTS.md` has ready starter prompts; they are a menu, not a script.

### Also install the Genie-space skill (any team may want one)
The build is free-form. Your team may decide a **self-serve Genie space** over the governed tables is
part of the solution. Install the community `prompt-to-genie` skill once at the workspace level as a
Git folder at the skill path, so it stays updatable from source:
```bash
databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
  --path /Workspace/.assistant/skills/prompt-to-genie
```
Then in a fresh Genie Code chat say **"create a Genie space"** over your **masked/filtered** views. A
Genie space that inherits your governance is a strong governance demo. See `GENIE_CODE_PROMPTS.md` for
build starter prompts.

### Prerequisite: create the OCDO group and federate it to the workspace
Your masks and row filters gate on `is_account_group_member('<ocdo_group>')`, so that group has to exist
at the **account** level and be visible **in this workspace**. Do this once, before you build:

1. **Create the group in the Account Console.** Go to the [Account Console](https://accounts.cloud.databricks.com)
   (you need account-admin rights), open **User management → Groups → Add group**, and name it, e.g.
   `ocdo_researchers` (a matching `ocdo_data_office` group is handy for the "who sees raw" side). Add the
   members who play each role for the demo.
2. **Federate the group to this workspace.** In the Account Console, open **Workspaces →
   `<your workspace>` → Permissions**, and assign the group to the workspace (with identity federation
   on, account groups become assignable to workspaces). Only then does `is_account_group_member(...)`
   resolve to TRUE inside the workspace for that group's members.
3. **Point the widget at it.** Set the `ocdo_group` widget to the exact group name. A quick check:
   `SELECT is_account_group_member('<ocdo_group>')` should return a real boolean, not an error.

> If a group isn't federated yet, `is_account_group_member` simply returns FALSE, the build still runs,
> but you can't demo the owner-vs-researcher flip until a real member of the group queries.

### Then
1. Confirm the foundation is up: the six shared OMOP tables exist. For a reference scaffold, open
   `00_START_HERE` in your workspace.
2. Set the widgets: `catalog`, `schema` (the **shared foundation** schema, e.g. `clinops_foundation`),
   `warehouse_id`, and `ocdo_group` (the researcher group masks and filters gate on).
3. Build with Genie Code in this order: **classify** (tags), then **mask and row-filter** to see the
   mechanism, then **set the tag-based policy** so one rule follows the tag catalog-wide. Prove each
   control with the verification harness.

---

## 🔒 Ground rules (security-first customer)

- **Everything is Unity-Catalog-scoped.** Catalog/schema/group come from widgets/bundle variables.
  No `hive_metastore`, ever.
- **Synthetic data only.** No real PHI in this kit.
- **No hardcoded secrets.** No tokens, keys, or passwords in code.
- **Governance is the product here.** Masks, filters, tags, and audits are the deliverable, every one
  of them is *provable* (the kit shows the before/after), which is what handling real patient data
  demands.
- **Governed tag vocabulary.** This metastore enforces *governed tag policies*: `phi` and
  `data_sensitivity` only accept values from an allowed list (HIPAA Safe Harbor identifier types;
  `official` / `official_sensitive`). The kit uses the allowed values; a typo is rejected by UC, which
  is the point.

---

## 🗂️ Repo layout

```
governance-session-starter-kit/
  README.md             ← you are here
  databricks.yml        ← DAB: UC-scoped per-team target (catalog/schema/warehouse/group)
  RUNBOOK.md            ← MENTOR build-level facilitation (Checkpoints 1 to 6, failure modes)
  GENIE_CODE_PROMPTS.md ← ready-to-use Genie Code build prompts (free-form; starters, not a script)
  STRETCH.md            ← "make it your own" extension ideas
  notebooks/            ← facilitator backup scaffold (00 to 06): pre-built plumbing and your TODOs
  reference/            ← SA-ONLY answer key (mentor reveals only if a team is stuck)
  resources/            ← optional setup job (used on FEVM); the onsite governs the shared foundation directly
```

## 📒 The notebook arc

| # | Notebook | What it builds | Your job? |
|---|---|---|---|
| - | `_config` | shared catalog/schema/warehouse/group and the PHI map | ✅ pre-built |
| 00 | `00_START_HERE` | overview, foundation check, the governance arc | ✅ read it |
| 01 | `01_discover_and_classify` | scan 6 tables, tag every PHI column | 🛠️ classify (Day-1 anchor) |
| 02 | `02_column_masks` | column masks on `person_id` / `note_text` by group | 🧠 the masking mechanism |
| 03 | `03_row_filters_abac` | row filters, then the tag-based ABAC policy catalog-wide | 🧠 the scalable core |
| 04 | `04_phi_identifier_search` | where does an identifier appear across catalogs | 🛠️ build the search |
| 05 | `05_ai_feature_governance` | Genie/AI-function limits over PHI | ✅ guided, plus light TODO |
| 06 | `06_inactive_users_report` | users inactive > 90 days via system tables | 🛠️ build the audit |
