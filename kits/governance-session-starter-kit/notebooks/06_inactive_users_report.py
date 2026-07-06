# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 06 · INACTIVE-USER AUDIT · FH ASK (GINA #3)</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">🧹 Who hasn't logged in for 90 days?</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     Least privilege isn't just <i>granting</i> the right access. It's <i>revoking</i> the access
# MAGIC     nobody's using. Dormant accounts are attack surface. Find every user inactive > 90 days from
# MAGIC     the audit system tables, so the data office can review and deactivate.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why this matters here
# MAGIC
# MAGIC FH had a multi-million-dollar breach and is mid-SOC2. A dormant-but-active account with `SELECT` on
# MAGIC PHI tables is exactly the kind of finding an auditor flags and an attacker exploits. The data office
# MAGIC wants a **standing report**: every workspace user whose **last activity** is older than 90 days.
# MAGIC
# MAGIC The signal lives in **`system.access.audit`**. Every authenticated action writes a row with the
# MAGIC actor and a timestamp. "Last seen" = the max `event_time` per user. Anyone whose max is > 90 days
# MAGIC ago (or who never appears) is a review candidate.

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# DBTITLE 1,Confirm we can read the audit system table (PRE-BUILT)
# system.access must be enabled on the metastore. If this errors, an account admin enables the
# system schema (Account console → Previews/System tables). Note it and move on.
try:
    n = spark.sql(
        "SELECT COUNT(*) AS n FROM system.access.audit WHERE event_date >= current_date() - INTERVAL 120 DAYS"
    ).first()["n"]
    show_md(f"<b>✅ <code>system.access.audit</code> readable.</b> {n:,} events in the last 120 days.")
except Exception as e:
    show_md(
        "<b>ℹ️ <code>system.access.audit</code> not available.</b> Ask an account admin to enable the "
        f"<code>system.access</code> schema, then re-run. <br><code>{str(e)[:280]}</code>"
    )

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🔑 The pattern you need (read before you build)
# MAGIC
# MAGIC ```sql
# MAGIC -- last activity per user, anywhere in the audit log:
# MAGIC SELECT user_identity.email AS user_email, MAX(event_time) AS last_seen
# MAGIC FROM system.access.audit
# MAGIC WHERE user_identity.email IS NOT NULL
# MAGIC GROUP BY user_identity.email;
# MAGIC ```
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>Notes:</b> the actor is <code>user_identity.email</code> (a struct field). Filter out service
# MAGIC accounts / system actors (emails ending in nothing, or <code>System-User</code>) if you only want
# MAGIC humans. "Inactive > 90 days" = <code>last_seen &lt; current_timestamp() - INTERVAL 90 DAYS</code>.
# MAGIC On a fresh workshop workspace everyone is recently active, so also report each user's
# MAGIC <code>days_since_last_seen</code> and sort descending, which makes the report meaningful even when
# MAGIC nobody is technically dormant yet.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Build the inactivity report 🛠️

# COMMAND ----------

# DBTITLE 1,TODO: last-activity-per-user and the >90-day flag
# TODO (you build this): from system.access.audit, compute per user:
#   • user_email, last_seen (MAX event_time), days_since_last_seen
#   • inactive_over_90d boolean (last_seen older than 90 days)
#   Exclude null/system actors. Order by days_since_last_seen DESC. Display it.
#
# Skeleton:
# report = spark.sql("""
#   WITH activity AS (
#     SELECT user_identity.email AS user_email, MAX(event_time) AS last_seen
#     FROM system.access.audit
#     WHERE user_identity.email IS NOT NULL AND user_identity.email LIKE '%@%'
#     GROUP BY user_identity.email
#   )
#   SELECT user_email, last_seen,
#          datediff(current_timestamp(), last_seen)                 AS days_since_last_seen,
#          last_seen < current_timestamp() - INTERVAL 90 DAYS       AS inactive_over_90d
#   FROM activity
#   ORDER BY days_since_last_seen DESC
# """)
# display(report)
#
# EXTENSION (optional): LEFT JOIN against the FULL user list so users who NEVER appear in the audit
#   window (zero activity) show up too. They're the most dormant of all. The account-level user list
#   isn't in system.access.audit; pull it from the SCIM Users API or system.access tables if available.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Make it a standing report (PRE-BUILT, persist for the data office)
# MAGIC
# MAGIC Materialize the result so the office can schedule it and trend it. (Run after your TODO builds
# MAGIC `report`.) A scheduled job over this table + an alert on `inactive_over_90d = true` closes the loop.

# COMMAND ----------

# DBTITLE 1,Persist the audit report (PRE-BUILT, uncomment once `report` exists)
# report.write.mode("overwrite").saveAsTable(fqn("inactive_user_report"))
# print(f"Wrote {fqn('inactive_user_report')}. Schedule a job over it + alert on inactive_over_90d=true.")

# COMMAND ----------

# MAGIC %md
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you just built:</b> a least-privilege hygiene report straight from governed system tables,
# MAGIC no agents, no scraping, just SQL over the audit log. Schedule it and the data office has a standing
# MAGIC answer to "who should we deactivate?" <b>This answers Gina and Ty's inactive-users ask (#3).</b>
# MAGIC </div>
# MAGIC
# MAGIC ## 🏁 You've completed the governance arc
# MAGIC
# MAGIC Classify (01) → mask (02) → filter (03) → search (04) → AI-govern (05) → audit (06). Every control
# MAGIC lives in the data layer, follows the data into every tool, and is provable. That's a governed PHI
# MAGIC warehouse Fred Hutch can defend. See `STRETCH.md` to go further.
