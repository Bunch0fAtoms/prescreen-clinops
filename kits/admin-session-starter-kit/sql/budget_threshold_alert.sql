-- =============================================================================
-- budget_threshold_alert.sql  ·  FH Admin session (Genie One) starter kit
-- FH ask (Amy #2): alert when a chargeback category is within 10% of its budget.
--
-- WHAT IT DOES
--   Computes month-to-date (MTD) list-price spend per chargeback category, then
--   flags any category whose MTD spend has reached >= 90% of its monthly budget.
--   Returns one row per category with a status: OVER_BUDGET / WITHIN_10PCT / OK.
--   The scheduled job (resources/cost_report_job.yml) emails on any non-OK row.
--
-- HOW TO MAKE IT YOURS  (the learnable bit — leave this open for Amy)
--   - Budgets live in the `budget_config` CTE below as a tiny inline table.
--     For production, replace that CTE with a real UC table so finance can edit
--     budgets without touching SQL, e.g.:
--         SELECT category, monthly_budget_usd
--         FROM <your_catalog>.clinops_admin.category_budgets
--     (a 2-column table: category STRING, monthly_budget_usd DOUBLE).
--   - Tune the 0.90 threshold (= "within 10%") to FH's preferred trip point.
--   - Keep the category CASE logic IN SYNC with cost_by_category.sql.
--
-- READ-ONLY against system.billing. Writes nothing.
-- =============================================================================

-- >>> Per-category monthly budgets (USD). Edit these, or swap for a UC table. <<<
WITH budget_config AS (
  SELECT 'Data Engineering'      AS category, 8000.0  AS monthly_budget_usd UNION ALL
  SELECT 'Data Science / ML'     AS category, 12000.0 AS monthly_budget_usd UNION ALL
  SELECT 'Research / Analytics'  AS category, 5000.0  AS monthly_budget_usd
),

-- The "within 10%" trip point. 0.90 => alert at 90% of budget.
threshold AS (SELECT 0.90 AS alert_at_fraction),

-- ----------------------------------------------------------------------------
-- Month-to-date list-price dollars per chargeback category (current month).
-- (Same priced/categorized pattern as cost_by_category.sql, scoped to MTD.)
-- ----------------------------------------------------------------------------
priced_usage AS (
  SELECT
    COALESCE(u.custom_tags['department'], u.billing_origin_product) AS raw_category,
    u.usage_quantity * lp.pricing.default                          AS list_cost_usd
  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices lp
    ON  u.sku_name = lp.sku_name
    AND u.usage_end_time >= lp.price_start_time
    AND (lp.price_end_time IS NULL OR u.usage_end_time < lp.price_end_time)
  WHERE u.usage_date >= date_trunc('MONTH', current_date())
),

mtd_by_category AS (
  SELECT
    CASE
      WHEN lower(raw_category) IN ('de', 'data_engineering', 'jobs', 'dlt', 'lakeflow_connect')
        THEN 'Data Engineering'
      WHEN lower(raw_category) IN ('ds', 'data_science', 'ml', 'model_serving', 'ai_functions', 'vector_search', 'agent_bricks')
        THEN 'Data Science / ML'
      WHEN lower(raw_category) IN ('research', 'sql', 'interactive', 'all_purpose')
        THEN 'Research / Analytics'
      ELSE 'Other (untagged)'
    END                                AS chargeback_category,
    SUM(list_cost_usd)                 AS mtd_cost_usd
  FROM priced_usage
  GROUP BY 1
)

SELECT
  b.category                                          AS chargeback_category,
  ROUND(COALESCE(m.mtd_cost_usd, 0), 2)               AS mtd_cost_usd,
  b.monthly_budget_usd,
  ROUND(100.0 * COALESCE(m.mtd_cost_usd, 0) / b.monthly_budget_usd, 1) AS pct_of_budget,
  CASE
    WHEN COALESCE(m.mtd_cost_usd, 0) >= b.monthly_budget_usd                 THEN 'OVER_BUDGET'
    WHEN COALESCE(m.mtd_cost_usd, 0) >= t.alert_at_fraction * b.monthly_budget_usd THEN 'WITHIN_10PCT'
    ELSE 'OK'
  END                                                 AS status
FROM budget_config b
CROSS JOIN threshold t
LEFT JOIN mtd_by_category m
  ON b.category = m.chargeback_category
ORDER BY pct_of_budget DESC;
