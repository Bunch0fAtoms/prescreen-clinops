# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 28px; border-radius:8px">
# MAGIC   <div style="font-size:0.9em; letter-spacing:2px; opacity:0.85">NOTEBOOK 04 · SLA WINDOWS · YOU BUILD THE GUARD</div>
# MAGIC   <div style="font-size:2.0em; font-weight:700; margin-top:4px">⏰ Keep jobs out of the source's SLA window</div>
# MAGIC   <div style="font-size:1.1em; margin-top:8px; max-width:880px; opacity:0.95">
# MAGIC     The source system is off-limits from <b>11pm to 8am</b> while it runs its own batch. Build a
# MAGIC     runtime guard that <b>skips (or waits)</b> if a job wakes inside that window, plus the Jobs
# MAGIC     schedule / pause-window pattern that prevents it at the scheduler level.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## Why this matters (FH ask: Jennifer #9)
# MAGIC
# MAGIC The source database has a nightly maintenance / batch window, **23:00 to 08:00**. If an ingest job
# MAGIC pulls from it during that window it can corrupt the source's batch or blow the SLA. There are **two
# MAGIC layers of defense**, and a robust pipeline uses both:
# MAGIC
# MAGIC | Layer | Mechanism | Strength |
# MAGIC |---|---|---|
# MAGIC | **Scheduler** | Jobs cron/quartz schedule + `pause_status` only fires outside the window | prevents the run from starting |
# MAGIC | **Runtime guard** | a cell at the top of the job checks the clock and skips/sleeps if in-window | defends against manual/backfill/misconfigured runs |
# MAGIC
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:12px 16px; border-radius:4px">
# MAGIC <b>The window config, the clock, and the schedule pattern are pre-built; the guard is yours.</b> You
# MAGIC write <code>in_sla_window(now)</code>, the function that decides whether a given time falls inside
# MAGIC the <b>overnight</b> blackout (note: it <i>wraps past midnight</i>, which is the whole trick).
# MAGIC </div>

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ The SLA window config (PRE-BUILT)
# MAGIC
# MAGIC The blackout is configuration, not a magic number buried in code: **start 23:00, end 08:00**, in the
# MAGIC source system's timezone (`America/Los_Angeles` for Fred Hutch). Because it crosses midnight, "inside
# MAGIC the window" means `hour >= 23 OR hour < 8`. That wrap-around is exactly what your guard must get
# MAGIC right.

# COMMAND ----------

# DBTITLE 1,Window config + a timezone-aware "now" helper (PRE-BUILT)
from datetime import datetime, time
from zoneinfo import ZoneInfo

SLA_TZ         = "America/Los_Angeles"
SLA_START_HOUR = 23   # 11pm, window opens (source off-limits)
SLA_END_HOUR   = 8    # 8am,  window closes (source available again)

def source_now() -> datetime:
    """Current time in the SOURCE system's timezone (what the SLA window is defined in)."""
    return datetime.now(ZoneInfo(SLA_TZ))

print(f"SLA blackout window: {SLA_START_HOUR:02d}:00 → {SLA_END_HOUR:02d}:00 ({SLA_TZ})")
print(f"Source-local now:    {source_now():%Y-%m-%d %H:%M:%S %Z}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ 🛠️ TODO: `in_sla_window(now)` (the midnight-wrap is the lesson)
# MAGIC
# MAGIC Return `True` if the given datetime falls **inside** the overnight blackout. The window wraps past
# MAGIC midnight, so a naive `start <= hour < end` is wrong. Think about it as "after 23:00 **OR** before 08:00."

# COMMAND ----------

# DBTITLE 1,TODO in_sla_window: the overnight (wrapping) window check (YOU BUILD THIS)
def in_sla_window(now: datetime,
                  start_hour: int = SLA_START_HOUR,
                  end_hour: int = SLA_END_HOUR) -> bool:
    """
    TODO (you build this): return True if `now` is inside the overnight SLA blackout.

    THE TRICK: the window WRAPS past midnight (start_hour=23 > end_hour=8). So it is NOT
      `start_hour <= hour < end_hour` (that's empty when start > end). It's:
          hour >= start_hour  OR  hour < end_hour
      i.e. 23:00 to 23:59 OR 00:00 to 07:59 are inside; 08:00 to 22:59 are outside.

    HINT: pull `now.hour` and return the boolean expression. (Bonus: handle the general case where
      start_hour < end_hour too, a same-day window, with a single conditional.)
    """
    # ---- your code below ----
    raise NotImplementedError("Build in_sla_window: see the TODO above.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Self-test your guard across the clock (PRE-BUILT, runs your function)
# MAGIC
# MAGIC We check representative hours so you can see the wrap-around behavior without waiting for 2am.

# COMMAND ----------

# DBTITLE 1,Truth table: confirm the wrap-around is right (PRE-BUILT)
from datetime import date
EXPECTED = {0: True, 5: True, 7: True, 8: False, 12: False, 22: False, 23: True}
try:
    rows = []
    ok = True
    for h, exp in sorted(EXPECTED.items()):
        got = in_sla_window(datetime(2026, 7, 7, h, 30, tzinfo=ZoneInfo(SLA_TZ)))
        ok &= (got == exp)
        rows.append((f"{h:02d}:30", got, exp, "✅" if got == exp else "❌"))
    display(spark.createDataFrame(rows, "hour string, in_window boolean, expected boolean, ok string"))
    print("✅ Guard is correct across the clock." if ok else "❌ Some hours are wrong. Fix the wrap-around.")
except NotImplementedError:
    print("⏳ Build in_sla_window first (the TODO above), then re-run.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Use the guard at the top of an ingest job (PRE-BUILT pattern)
# MAGIC
# MAGIC Two stances. **Skip** = exit cleanly so the scheduler retries later (best for idempotent ingests).
# MAGIC **Wait** = sleep until the window closes, then proceed (best for a run that must happen tonight).
# MAGIC We demo **skip** here and gate it on a `force_run` widget so this notebook itself never hangs.

# COMMAND ----------

# DBTITLE 1,Guard cell: skip the pull if we're inside the SLA window (PRE-BUILT)
now = source_now()
try:
    blocked = in_sla_window(now)
except NotImplementedError:
    blocked = False
    print("⏳ (guard not built yet, treating as outside the window for this demo run)")

if blocked:
    msg = (f"⏸️  {now:%H:%M %Z} is inside the SLA window "
           f"({SLA_START_HOUR:02d}:00 to {SLA_END_HOUR:02d}:00), skipping the source pull. "
           "The scheduler will retry after 08:00.")
    print(msg)
    # In a real job, exit cleanly so the run is marked complete (not failed) and retried on next schedule:
    #   dbutils.notebook.exit("skipped: in SLA window")
else:
    print(f"▶️  {now:%H:%M %Z} is OUTSIDE the SLA window, clear to pull from the source.")
    # ... your ingest would run here (e.g. safe_ingest(...) from nb 03) ...

# COMMAND ----------

# DBTITLE 1,The "WAIT until the window closes" variant (PRE-BUILT, reference, not run)
# Reference only, do NOT run interactively (it would sleep up to 9 hours):
#
# import time as _time
# while in_sla_window(source_now()):
#     secs = _seconds_until_window_close(source_now())   # compute time to SLA_END_HOUR
#     print(f"Waiting {secs//60} min for the SLA window to close...")
#     _time.sleep(min(secs, 600))   # re-check at least every 10 min
# print("Window closed, proceeding with the pull.")

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC ## 🗓️ The scheduler-level pattern (Jobs schedule + pause window)
# MAGIC
# MAGIC The runtime guard defends manual/backfill runs; the **scheduler** prevents scheduled runs from
# MAGIC firing in-window at all. In a Databricks Job you express this with a **quartz cron** that only fires
# MAGIC outside 23:00 to 08:00, plus `pause_status` to pause the whole schedule on demand.
# MAGIC
# MAGIC ```yaml
# MAGIC # resources/sla_ingest_job.yml, shipped in this bundle
# MAGIC trigger: ~                       # (none, schedule below drives it)
# MAGIC schedule:
# MAGIC   # Run hourly ONLY from 08:00 to 22:00 PT, never inside the 23:00 to 08:00 blackout.
# MAGIC   quartz_cron_expression: "0 0 8-22 * * ?"
# MAGIC   timezone_id: "America/Los_Angeles"
# MAGIC   pause_status: "UNPAUSED"        # flip to "PAUSED" to stop all scheduled runs (e.g. a source outage)
# MAGIC ```
# MAGIC
# MAGIC <div style="background:#E3F2FD; border-left:6px solid #1565C0; padding:12px 16px; border-radius:4px">
# MAGIC <b>Defense in depth:</b> the cron means a scheduled run <i>never</i> starts in the window; the
# MAGIC runtime guard (your function) catches the manual 2am backfill someone kicks off anyway. The bundle
# MAGIC ships this job. See <code>resources/sla_ingest_job.yml</code> and the README.
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#E8F5E9; border-left:6px solid #2E7D32; padding:12px 16px; border-radius:4px">
# MAGIC <b>What you built:</b> a wrap-around-correct SLA guard you can drop at the top of any ingest job,
# MAGIC paired with a cron schedule that keeps scheduled runs out of the window entirely. The source's batch
# MAGIC window is now protected at both layers.
# MAGIC </div>
# MAGIC
# MAGIC <!-- EXTENSION (optional): make the window config-driven from a UC table (like nb 03's allow-list)
# MAGIC      so a steward can change the blackout hours without a deploy; or add a per-source-system window. -->
# MAGIC
# MAGIC ## ▶️ Done!
# MAGIC ### You've built all four DE guards. See `STRETCH.md` to push further, and `RUNBOOK.md` (mentor) for the checkpoints.
