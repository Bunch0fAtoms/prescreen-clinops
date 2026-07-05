-- =============================================================================
-- cost_by_category.sql  ·  FH Admin session (Genie One) starter kit
-- FH ask (Amy #1): monthly cost broken down for chargebacks (DE / DS / research),
-- emailable as a CSV.
--
-- WHAT IT DOES
--   Joins system.billing.usage to system.billing.list_prices to turn raw usage
--   quantity into list-price dollars, then rolls cost up by month and by a
--   chargeback "category". The category is the `department` custom tag when the
--   resource was tagged (the chargeback-correct dimension), and falls back to
--   `billing_origin_product` (JOBS / SQL / MODEL_SERVING / ...) when it wasn't.
--
-- HOW TO MAKE IT YOURS  (the learnable bit — leave this open for Amy)
--   - Swap `department` for whatever tag FH standardizes on for chargeback
--     (e.g. `cost_center`, `team`, `grant_id`). One line: see CATEGORY_TAG below.
--   - Map raw tag/product values to the friendly DE / DS / research buckets in
--     the `category_map` CTE.
--
-- READ-ONLY. system.billing is read-only by design; this query writes nothing.
-- =============================================================================

-- The lookback window for the report. 12 months gives month-over-month context;
-- the scheduled job (resources/cost_report_job.yml) can narrow this if desired.
WITH params AS (
  SELECT add_months(date_trunc('MONTH', current_date()), -11) AS window_start
),

-- ----------------------------------------------------------------------------
-- 1. List-price dollars per usage record.
--    list_prices is slowly-changing (price_start_time / price_end_time), so we
--    join on the SKU *and* the price that was in effect at usage time.
-- ----------------------------------------------------------------------------
priced_usage AS (
  SELECT
    date_trunc('MONTH', u.usage_date)            AS usage_month,
    u.custom_tags                                AS custom_tags,
    u.billing_origin_product                     AS product,
    u.usage_quantity                             AS qty,
    -- pricing.default is the list $/unit for the SKU
    u.usage_quantity * lp.pricing.default        AS list_cost_usd
  FROM system.billing.usage u
  JOIN params p
    ON u.usage_date >= p.window_start
  LEFT JOIN system.billing.list_prices lp
    ON  u.sku_name = lp.sku_name
    AND u.usage_end_time >= lp.price_start_time
    AND (lp.price_end_time IS NULL OR u.usage_end_time < lp.price_end_time)
),

-- ----------------------------------------------------------------------------
-- 2. Pick the chargeback dimension: the `department` tag, else the product.
--    >>> CATEGORY_TAG: change 'department' here to FH's chargeback tag. <<<
-- ----------------------------------------------------------------------------
categorized AS (
  SELECT
    usage_month,
    COALESCE(
      custom_tags['department'],   -- chargeback-correct when tagged
      product                      -- fallback for untagged usage
    )                                            AS raw_category,
    list_cost_usd
  FROM priced_usage
),

-- ----------------------------------------------------------------------------
-- 3. Map raw values to friendly DE / DS / research chargeback buckets.
--    Everything unmatched rolls up to 'other (untagged)' so nothing is hidden.
-- ----------------------------------------------------------------------------
category_map AS (
  SELECT
    usage_month,
    CASE
      WHEN lower(raw_category) IN ('de', 'data_engineering', 'jobs', 'dlt', 'lakeflow_connect')
        THEN 'Data Engineering'
      WHEN lower(raw_category) IN ('ds', 'data_science', 'ml', 'model_serving', 'ai_functions', 'vector_search', 'agent_bricks')
        THEN 'Data Science / ML'
      WHEN lower(raw_category) IN ('research', 'sql', 'interactive', 'all_purpose')
        THEN 'Research / Analytics'
      ELSE 'Other (untagged)'
    END                                          AS chargeback_category,
    list_cost_usd
  FROM categorized
)

SELECT
  usage_month,
  chargeback_category,
  ROUND(SUM(list_cost_usd), 2)                   AS monthly_cost_usd
FROM category_map
GROUP BY usage_month, chargeback_category
ORDER BY usage_month DESC, monthly_cost_usd DESC;
