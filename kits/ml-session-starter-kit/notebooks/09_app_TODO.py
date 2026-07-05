# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:28px 32px; border-radius:8px">
# MAGIC   <div style="font-size:0.95em; letter-spacing:2px; opacity:0.85">NOTEBOOK 09 · STRETCH</div>
# MAGIC   <div style="font-size:2.3em; font-weight:700; margin-top:6px">🚀 A Coordinator Pre-Screening App</div>
# MAGIC   <div style="font-size:1.15em; margin-top:10px; max-width:880px; opacity:0.95">
# MAGIC     The natural last mile: a point-and-click Databricks App that lets a trial coordinator
# MAGIC     screen patients without writing SQL. This is a <b>stretch goal</b> — the session's value is
# MAGIC     already proven by notebooks 01–08.
# MAGIC   </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:#FFF8E1; border-left:6px solid #F2A900; padding:18px 22px; border-radius:4px">
# MAGIC <div style="font-size:1.3em; font-weight:700; color:#7A4F00">🚀 EXTENSION (optional) — build this only if your team finishes early</div>
# MAGIC <div style="margin-top:8px; font-size:1.05em">
# MAGIC The hard, differentiating work — recovering the notes-only patients and <i>measuring</i> the
# MAGIC extraction — is done in 01–08. The app is straightforward last-mile packaging over the
# MAGIC <code>gold_trial_prescreen</code> table. Treat it as a creative stretch, not a requirement.
# MAGIC </div>
# MAGIC </div>

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💡 The vision — what to build
# MAGIC
# MAGIC A **Databricks App** giving coordinators a point-and-click pre-screening UI on top of
# MAGIC `gold_trial_prescreen` — no SQL. A coordinator would:
# MAGIC
# MAGIC - **Pick a trial** (Trial A — HER2+, or Trial B — ER+/HER2−) from a dropdown.
# MAGIC - **See the eligible patients** as a sortable list.
# MAGIC - **See *why*** each is eligible — the `trial_a_reason` / `trial_b_reason` string.
# MAGIC - **See a provenance badge** driven by `biomarker_source`: green *"Structured"* vs amber
# MAGIC   *"NLP-recovered"*. That badge is the whole story of this solution, made visible.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧱 What it would use
# MAGIC
# MAGIC - **Databricks Apps** — a small Python/Streamlit app (or CDN-served React, no build step).
# MAGIC - **The SQL warehouse** — the app reads the curated `gold_trial_prescreen`; heavy analytics are done.
# MAGIC - **The Genie space (nb 08)** — optionally embedded for free-text follow-ups inside the app.
# MAGIC - **Unity Catalog governance** — the app runs with controlled, auditable access; governance is
# MAGIC   inherited, not re-implemented. No PHI leaves UC.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Build hooks (see STRETCH.md for the full list)
# MAGIC
# MAGIC - `# EXTENSION (optional):` scaffold a Streamlit app that queries `gold_trial_prescreen` over the
# MAGIC   warehouse and renders the provenance badge from `biomarker_source`.
# MAGIC - `# EXTENSION (optional):` wire a trial-selector dropdown to the `trial_a_eligible` /
# MAGIC   `trial_b_eligible` flags.
# MAGIC - `# EXTENSION (optional):` deploy it as a Databricks App (upload source to the workspace, deploy
# MAGIC   from there) scoped to your UC catalog.
# MAGIC
# MAGIC The `databricks-apps` / `databricks-apps-python` skills have the scaffolding patterns.

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC <div style="background:linear-gradient(90deg,#C8102E 0%,#7A0019 100%); color:white; padding:22px 26px; border-radius:8px">
# MAGIC   <div style="font-size:1.4em; font-weight:700">🎉 That's the build — nice work.</div>
# MAGIC   <div style="margin-top:8px; max-width:820px; opacity:0.95">
# MAGIC     From synthetic OMOP data to a governed, NLP-recovered, measured trial pre-screen — you built the
# MAGIC     whole arc. The app above is the obvious next step, and an easy one, because the hard part is
# MAGIC     already behind you.
# MAGIC   </div>
# MAGIC </div>
# MAGIC
# MAGIC ### ← Back to **[00_START_HERE]($./00_START_HERE)**
