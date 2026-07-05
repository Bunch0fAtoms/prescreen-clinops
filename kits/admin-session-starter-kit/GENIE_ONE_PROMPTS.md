# 💬 Genie One — ready-to-use prompts (Admin / cost & chargeback)

**Fred Hutch onsite · Admin session · Genie One on the `system.billing` tables**

Genie One is natural-language and click-driven — you ask in plain English, it writes
and runs the SQL. These ~8 prompts are sized to the two FH asks (chargeback cost +
budget alerting). Point Genie One at `system.billing.usage` and `system.billing.list_prices`
first (see `RUNBOOK.md` Checkpoint 1), then paste a prompt.

> **The learnable bit (leave this open):** the last two prompts are deliberately
> open-ended. Once Amy sees the pattern, she should write her *own* questions — that's
> the whole point of Genie One. Encourage tweaking the budget number, the time window,
> and the category breakdown.

> **Read-only, no PHI.** Everything here reads `system.billing` (usage + prices). No
> patient data, no writes.

---

### 1. Total monthly cost (the warm-up)
> **"What was our total Databricks list-price cost per month for the last 6 months?"**

*Good looks like:* one row per month, descending, with a dollar total. Confirms Genie
One is joining `usage` to `list_prices` correctly. This is the foundation for everything else.

---

### 2. Cost broken down for chargeback  *(FH ask — Amy #1)*
> **"Break down monthly cost by the `department` custom tag for the last 6 months. For usage with no department tag, group it by its product instead. Label the buckets Data Engineering, Data Science, and Research."**

*Good looks like:* a month × category grid of dollars. This is the chargeback report Amy
wants emailed. If most cost lands in "untagged", that's the signal that FH needs a tagging
policy — call it out (see prompt 8).

---

### 3. Month-over-month change
> **"For each chargeback category, show this month's cost versus last month's, and the percent change."**

*Good looks like:* a category list with two dollar columns and a % delta. Surfaces a
category that's trending up before it blows the budget.

---

### 4. Which categories are near budget  *(FH ask — Amy #2)*
> **"Our monthly budgets are: Data Engineering 8000 dollars, Data Science 12000, Research 5000. Which categories are within 10% of their budget this month?"**

*Good looks like:* a category list with month-to-date spend, the budget, % of budget, and a
flag for any category at or above 90%. This is the alert condition — prompt 5 turns it into
a scheduled alert.

---

### 5. Schedule it as an alert
> **"Save that budget check as a scheduled SQL alert that emails me on the 1st of each month when any category is within 10% of budget."**

*Good looks like:* Genie One offers to create a SQL Alert / scheduled query. Accept it, set
the recipient, and confirm the trigger is "any row over 90%". (The RUNBOOK shows the manual
click-path too, as a fallback.)

---

### 6. Top cost drivers
> **"What are the top 10 SKUs by cost this month, and which workspace did each run in?"**

*Good looks like:* a ranked SKU list with dollars and `workspace_id`. Answers "where is the
money actually going" — usually serverless SQL, model serving, or jobs.

---

### 7. Cost trend for one category
> **"Show me the daily cost for the Data Science category over the last 30 days as a line chart."**

*Good looks like:* a daily time series Genie One renders as a chart. Spikes here are the
early-warning signal a monthly report would miss.

---

### 8. Tagging coverage (the governance nudge)
> **"What percent of our cost this month is on resources with no `department` tag?"**

*Good looks like:* a single percentage. High = chargeback is guessing. This is the prompt
that motivates an FH cluster/warehouse **tagging policy** so future chargeback is exact, not
inferred from product. Tie it back to the governance theme of the onsite.

---

### 🧩 Now write your own (the open part)
Two starters — change the numbers, the window, the dimension and watch Genie One adapt:

- *"Which workspace had the biggest month-over-month cost increase, and in what product?"*
- *"If Research keeps growing at last month's rate, what month does it cross its 5000 budget?"*

If Genie One's answer looks off, check that it filtered to recent `usage_date` and joined
`list_prices` on the price that was in effect (see the trusted SQL in `sql/` for the exact
join). Adding the working query from `sql/cost_by_category.sql` as a **trusted example /
sample query** in the Genie One space makes its answers far more reliable.
