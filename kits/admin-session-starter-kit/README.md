# 💵 Cost, Chargeback & Budget Alerts, Admin Session Starter Kit

**Fred Hutch onsite · Admin session · Genie One + system tables · (Amy Paguirigan)**

> **🔒 PREVIEW: do NOT publish.** This kit is in preview pending validation. Synthetic /
> UC-scoped, read-only, no PHI. Keep it local until the team signs off.

This is a **lighter** starter kit than the ML session's. Genie One is natural-language and
click-driven, so the deliverable is a **guided runbook + ready prompts + working SQL** Amy can
run today and schedule tomorrow, *not* a heavy notebook bundle. The hard parts (the correct
`usage` ↔ `list_prices` join, the chargeback category logic, the 10%-of-budget math) are
**pre-built and validated**. The learnable bit, writing her own Genie One questions and tuning
the budget thresholds, is left open on purpose.

> Scaffold, don't hand-hold, admin edition. Give Amy a clean path to the answer, then get out
> of the way so she owns the next question.

---

## 🎯 The two FH asks this answers

| # | Amy's ask | What's in the kit |
|---|---|---|
| **1** | *Monthly cost, broken down for chargebacks (DE / DS / research), emailed as a CSV* | `sql/cost_by_category.sql` + Genie One prompts 1 to 3 + the scheduled job |
| **2** | *Alert me when a category is within 10% of its budget* | `sql/budget_threshold_alert.sql` + prompts 4 to 5 + the alert task in the job |

Both queries run against Databricks **system tables**, the account's own billing telemetry,
so there's nothing to ingest or model. Just point Genie One at them and ask.

---

## 🧱 What's pre-built vs. what Amy does

| Component | Status |
|---|---|
| The `system.billing.usage` ↔ `list_prices` join (price-in-effect at usage time) | ✅ **Pre-built & validated** |
| Chargeback category logic (`department` tag, product fallback, DE/DS/research buckets) | ✅ **Pre-built**, tune the mapping |
| 10%-of-budget threshold math + OVER / WITHIN_10PCT / OK status | ✅ **Pre-built**, set the budgets |
| Pointing Genie One at the billing tables + asking the cost questions | 🛠️ **Amy does** (guided, RUNBOOK) |
| Writing her *own* Genie One questions / tuning budgets & thresholds | 🧠 **Amy does** (the open part) |
| Scheduling the monthly report + budget alert | 🛠️ **Amy does** (job YAML + RUNBOOK click-path) |

---

## 🗂️ Kit layout

```
admin-session-starter-kit/
  README.md                       ← you are here
  RUNBOOK.md                      ← mentor/Amy guided click-path + checkpoints + failure modes
  GENIE_ONE_PROMPTS.md            ← ~8 ready natural-language prompts (each: question + "what good looks like")
  sql/
    cost_by_category.sql          ← monthly chargeback cost (Amy #1), VALIDATED on FEVM2
    budget_threshold_alert.sql    ← within-10%-of-budget flag (Amy #2), VALIDATED on FEVM2
  resources/
    cost_report_job.yml           ← OPTIONAL scheduled Job (monthly report + alert); documented, not required
```

---

## 📂 Where the SQL lives (no clone, no separate bundle)

You do not clone a repo or run a bundle for this session. The two trusted SQL files ride along
with the one **foundation** deploy the room already runs on Day 1. After that deploy they are in
your workspace at:

```
/Workspace/fh-onsite/prescreen/client/files/kits/admin-session-starter-kit/sql/
    cost_by_category.sql
    budget_threshold_alert.sql
```

The foundation `client` target deploys to that shared `/Workspace/fh-onsite/` folder (not the
deployer's personal home), and whoever runs the Day 1 setup grants all groups read on it, so the
whole room can reach these files. Open either one in the SQL editor to run it, or copy it into your
Genie One space as a trusted sample query. (If your team changed the foundation's `root_path`, the
prefix changes to match. `databricks bundle validate` in the `foundation/` folder prints the exact
files root.)

Note: this session reads `system.billing`, not the foundation's clinical tables. It rides the
foundation deploy only to deliver these SQL files, so you can start as soon as `system.billing` is
readable (see the requirement below), without waiting on the clinical data job.

---

## 🚦 How to use it

1. **Read `RUNBOOK.md`.** It's the guided path: open Genie One → point it at the billing
   system tables → ask the cost questions (from `GENIE_ONE_PROMPTS.md`) → stand up the
   scheduled report/alert. Three named **Checkpoints**.
2. **Try the prompts** in `GENIE_ONE_PROMPTS.md` in order. Each has a one-line "what good looks
   like" so Amy knows the answer is right.
3. **Run the SQL directly** if you want to see/trust the exact query Genie One is approximating.
   `sql/cost_by_category.sql` and `sql/budget_threshold_alert.sql` are the trusted, validated
   versions. Paste either into a SQL editor, or add `cost_by_category.sql` as a **trusted sample
   query** in the Genie One space to sharpen its answers.
4. **Schedule it** (optional) with `resources/cost_report_job.yml`. See the RUNBOOK for the
   email-the-CSV click-path (a SQL Alert / dashboard subscription, since Job emails carry run
   status, not query results).
5. **Optional: a self-serve cost Genie space.** The build is free-form; Amy may want finance/leads
   to self-serve cost questions in natural language. Install the workspace-level `prompt-to-genie`
   skill (shared across all four onsite sections) and say **"create a Genie space"** over the billing
   tables / the `cost_by_category` output. Install it as a Git folder at the skill path, so it stays
   updatable from source:
   ```bash
   databricks repos create https://github.com/sean-zhang-dbx/prompt-to-genie.git gitHub \
     --path /Workspace/.assistant/skills/prompt-to-genie
   ```

---

## 🔒 Ground rules

- **Read-only.** Everything reads `system.billing.*` (account billing telemetry). The queries
  write nothing. If you ever need a scratch table (e.g. a real budgets table), use
  `<your_catalog>.clinops_admin` on FEVM2. Never write to `system`.
- **No PHI.** Billing system tables contain usage, SKUs, tags, and dollars, no patient data.
  This kit never touches `curated_omop` or any clinical schema.
- **Unity-Catalog-scoped.** `system.billing` is governed by UC; access is granted by an account
  admin (see the requirement below).

---

## ⚙️ Requirement: the `system.billing` schema must be enabled

The `system.billing` schema is **enabled per-account by an account admin** and is granted to a
metastore. Once enabled, `usage` backfills and `list_prices` populates automatically.

- **On FH prod:** an account admin enables `system.billing` (and grants `SELECT` to the admin /
  finance group). FH almost certainly already has this for cost visibility.
- **If it's not enabled or is empty:** the queries are still correct and runnable. Point them at
  the tiny **synthetic fallback** documented in `RUNBOOK.md` (a `VALUES` CTE with a few sample
  rows) so you can demo the query *shape* and Genie One's behavior without live billing data.

> ✅ **Validated:** both SQL files were run on FEVM2 (`a reference workspace`,
> warehouse `<your_warehouse_id>`) against the live `system.billing` tables and returned correct
> month-over-month chargeback breakdowns and budget-status flags. See `RUNBOOK.md` for the exact
> results and the one caveat (shared-workspace usage dwarfs sample budgets, so set realistic FH
> budgets in production).
