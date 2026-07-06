# 🧭 RUNBOOK, Admin Session (Genie One: cost, chargeback & budget alerts)

**Mentor- and Amy-facing.** This is the guided click-path for the Admin session: open Genie One →
point it at the billing system tables → ask the chargeback cost questions → stand up the scheduled
report + budget alert. Three named **Checkpoints**, plus the common failure modes and the synthetic
fallback if `system.billing` isn't available.

**Customer:** Fred Hutch · Admin session of the 2-day onsite (this kit is the **Admin session only**).
**Audience:** Amy Paguirigan (Deputy CDO) + admins, natural-language / click-driven, **not** notebook
builders. So the path is: ask in plain English, trust-but-verify against the validated SQL, then schedule.
**Outcome:** a monthly chargeback cost report (DE / DS / research) + an alert when a category is within
10% of its budget, both running hands-off. **Security-first:** read-only system tables, no PHI.

> Reveal ladder: nudge → show the matching prompt in `GENIE_ONE_PROMPTS.md` → paste the trusted
> SQL from `sql/`. Reveal the SQL **early**. It's plumbing, and seeing the exact join builds trust.
> Keep the *question-writing* open (that's Amy's learnable bit).

---

## Block 0 · Confirm system tables (pre-flight)

- **Where the SQL is:** you do not clone anything. Both files were delivered into the workspace by
  the one Day 1 foundation deploy, at
  `/Workspace/fh-onsite/prescreen/client/files/kits/admin-session-starter-kit/sql/` (the shared
  folder the foundation deploys to; the README's "Where the SQL lives" section explains it). Open
  them from there in the SQL
  editor. This session reads `system.billing`, not the foundation's clinical tables, so you can
  start as soon as billing is readable.
- **Pre-built:** both SQL files (`sql/cost_by_category.sql`, `sql/budget_threshold_alert.sql`),
  already validated on FEVM2.
- **Amy/mentor does:** confirm `system.billing` is readable in this workspace.
- Quick check (SQL editor or Genie One): `SELECT count(*) FROM system.billing.usage`, a non-zero
  count means you're good.
- **🚩 Checkpoint 1: Billing tables reachable.** `system.billing.usage` returns a row count > 0 and
  `system.billing.list_prices` is readable. Genie One is pointed at both tables.
- **Common failures:**
  - *`TABLE_OR_VIEW_NOT_FOUND` / permission denied on `system.billing`* → the schema isn't enabled or
    not granted. **This is an account-admin action, reveal early.** An account admin enables the
    `system.billing` schema and grants `SELECT` to the admin/finance group. On FH prod this is
    typically already done. **Fallback:** use the synthetic CTE below to demo the query shape now.
  - *`usage` exists but is empty / very sparse* → billing backfills after enablement; recent days
    populate first. Narrow the window to the last few days, or use the synthetic fallback.

### Synthetic fallback (only if `system.billing` is unavailable)
Demonstrates the exact query *shape* without live billing. Paste into a SQL editor / Genie One:

```sql
WITH usage AS (
  SELECT * FROM VALUES
    (DATE'2026-06-01', map('department','Data Engineering'), 'JOBS',          120.0, 0.55),
    (DATE'2026-06-01', map('department','Data Science'),     'MODEL_SERVING',  90.0, 0.80),
    (DATE'2026-06-01', map(),                                'SQL',           300.0, 0.22),
    (DATE'2026-05-01', map('department','Data Engineering'), 'JOBS',          100.0, 0.55),
    (DATE'2026-05-01', map('department','Research'),         'SQL',           250.0, 0.22)
  AS t(usage_date, custom_tags, billing_origin_product, usage_quantity, unit_price)
)
SELECT date_trunc('MONTH', usage_date) AS usage_month,
       COALESCE(custom_tags['department'], billing_origin_product) AS category,
       ROUND(SUM(usage_quantity * unit_price), 2) AS cost_usd
FROM usage GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC;
```

This mirrors `cost_by_category.sql` (the real one joins `list_prices` for the unit price and maps
categories into DE/DS/research buckets, see the file).

---

## Block 1 · The chargeback cost report (Amy #1), GUIDED

- **Pre-built:** `sql/cost_by_category.sql`, the validated month × category dollar query.
- **Amy does:** in Genie One, run prompts **1 → 2 → 3** from `GENIE_ONE_PROMPTS.md` (total monthly
  cost → break down by `department` tag with product fallback into DE/DS/research → month-over-month).
- **🚩 Checkpoint 2: Chargeback breakdown renders.** Genie One returns a month × category grid of
  dollars that matches (within rounding) `sql/cost_by_category.sql`. Amy can read off "DE vs DS vs
  research" for the latest month.
- **Common failures:**
  - *Genie One's numbers don't match the trusted SQL* → it likely skipped the price-in-effect join or
    didn't filter the date window. Add `cost_by_category.sql` as a **trusted sample query** in the
    Genie One space and re-ask; its answers snap to the right join.
  - *Almost everything lands in "Other (untagged)"* → resources aren't tagged with `department`. That's
    a real finding, not a bug: run prompt 8 (tagging coverage) and flag that FH needs a tagging policy
    for exact chargeback. The product fallback keeps the report useful meanwhile.
  - *Wrong chargeback tag name* → FH may use `cost_center` / `team` / `grant_id` instead of
    `department`. Change the one `CATEGORY_TAG` line in `cost_by_category.sql` (and the prompt).

---

## Block 2 · Budget alert + scheduling (Amy #2), GUIDED, the payoff

- **Pre-built:** `sql/budget_threshold_alert.sql` (MTD spend vs per-category budget, flags ≥90%) and
  `resources/cost_report_job.yml` (monthly schedule + email).
- **Amy does:** run prompt **4** (which categories are within 10% of budget), then prompt **5** to save
  it as a scheduled SQL alert. Set the budgets in the query's `budget_config` CTE (or point it at a UC
  budgets table).
- **🚩 Checkpoint 3: Alert is scheduled.** A SQL Alert (or the job's `budget_alert` task) is saved,
  emails Amy, and triggers when any category row has status `WITHIN_10PCT` or `OVER_BUDGET`. Bonus:
  the `cost_by_category` report is scheduled monthly.
- **Emailing the CSV (the one gotcha):** Databricks **Job** `email_notifications` send *run status*,
  not query results. To email the **CSV itself**, use one of:
  1. a **SQL Alert** on `budget_threshold_alert.sql` (best for the "tell me when" ask, only fires on
     a real breach), and/or
  2. a **scheduled Dashboard / query subscription** on `cost_by_category.sql` (best for the recurring
     report, subscribers get the results table on a schedule).
  Both are click-path setups in DBSQL; the job YAML runs the queries on schedule and is the deploy
  scaffold. This is documented in `resources/cost_report_job.yml`.
- **Common failures:**
  - *Alert never fires* → on FH's real workspace with realistic budgets it fires correctly; if testing
    on a shared/large workspace, MTD spend dwarfs sample budgets so everything reads `OVER_BUDGET`
    (see validation note below). Set budgets to realistic FH numbers.
  - *Budgets hardcoded in SQL feel brittle* → graduate the `budget_config` CTE to a 2-column UC table
    (`category`, `monthly_budget_usd`) so finance edits budgets without touching SQL. The file shows
    the exact swap; if you need a scratch table on FEVM2 use schema
    `<your_catalog>.clinops_admin`.

---

## Quick reference: checkpoint summary

| # | Checkpoint | Signal it's met |
|---|---|---|
| 1 | Billing tables reachable | `system.billing.usage` count > 0; Genie One pointed at usage + list_prices |
| 2 | Chargeback breakdown renders | month × category dollar grid matches `cost_by_category.sql` |
| 3 | Alert scheduled | SQL Alert / job fires on `WITHIN_10PCT`/`OVER_BUDGET`; monthly report subscribed |

---

## ✅ FEVM2 validation (what was actually run)

Both SQL files were executed on **FEVM2** (`a reference workspace`, warehouse
`<your_warehouse_id>`) against the **live** `system.billing` tables:

- `cost_by_category.sql` → **SUCCEEDED, 47 rows.** Correct month-over-month grid across Data
  Engineering / Data Science / Research / Other(untagged). The `department` custom tag exists on this
  workspace, so the chargeback dimension is real, with product as the fallback.
- `budget_threshold_alert.sql` → **SUCCEEDED, 3 rows** (one per budget category) with correct
  `pct_of_budget` and `status`.

**One caveat:** FEVM2 is a large shared workspace, so MTD spend is enormous relative to the sample
budgets in the CTE. All three categories read `OVER_BUDGET` there. The *logic, math, and status
flags are correct*; on FH's own workspace with realistic per-category budgets, the OK / WITHIN_10PCT /
OVER_BUDGET states will be meaningful. Set FH's real budgets before relying on the alert.

**Safety net, always:** if `system.billing` isn't enabled in the room, the synthetic fallback CTE in
Block 0 demonstrates the identical query shape so the session never stalls on an account-admin
dependency. Default to read-only; never write to `system`.
