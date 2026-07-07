# 🧭 RUNBOOK: Applied AI Feature Extraction & Trial Pre-Screening (build-level facilitation)

**Mentor-facing. Build-level only.** Event-level facilitation (agenda, room dynamics, escalation
ladder, the security-first framing, debrief) lives in the separate `13-mentor-brief.md`. Don't
duplicate it here. This runbook is the per-build-block detail: what's pre-built, what the team
builds, the named **Checkpoints**, common failures, and the notebook safety-net fallback.

**Customer:** Fred Hutch · Applied AI session of the 2-day onsite (this kit is that session only).
**Team:** single team, mixed CORE-maturity. Comfortable with SQL and notebooks, **newer to GenAI and
agents**. So go light on the SQL/pipeline TODOs and heavier on signposting the `ai_query` and MLflow-
eval parts.
**Outcome:** a governed, **data-driven** trial pre-screen on OMOP that recovers the notes-only patients,
joins the DE group's trials catalog (so a new trial is a file drop, not a code change), and measures
the extraction, plus the coordinator/researcher app Sita asked for (inspiration demo). **Security-first:**
synthetic data only, everything UC-scoped, governance visible.

> **Set expectations in the first two minutes.** Say plainly what this session is. It is applied AI
> feature extraction, not model training. Tell the team there is no classifier to fit. A language
> model reads the pathology notes and pulls out biomarkers. Deterministic rules then decide trial
> eligibility, with a plain-English reason per patient. This framing is a feature, not an apology. A
> security-first, IRB-minded room trusts an auditable rule more than a score it cannot explain. If
> anyone wants a trained model, point them to the prioritization-ranker stretch in `STRETCH.md`, which
> sits on top of the rules and never replaces them. The full is/is-not table is in the kit `README.md`.

**Reveal ladder (from the mentor brief):** nudge → hint (point at the `# TODO`) → **point at the matching
prompt in `GENIE_CODE_PROMPTS.md`** → pair → reveal (`reference/ANSWER_KEY.md`, or the full working
notebooks at `onsite_july2026/notebooks/`). Reveal **late** on the learnable core; reveal **early** on
plumbing and anything PHI/security-sensitive.

**Free-form build.** This session is intentionally open. The team designs their own pre-screen off the
6 OMOP tables in the shared foundation. `GENIE_CODE_PROMPTS.md` holds ready-to-use Genie Code build prompts (the proven
dry-run set, numbered to the notebooks, each with a "good looks like" + the `ai_query` gotcha); treat
them as *starters the team can adapt*, not a script.

---

## 🗺️ Build surface map: Genie Code vs. the notebooks you run

**The rule:** Genie Code runs on a SQL warehouse, so anything expressible in SQL is built **live in
Genie Code**. Anything that needs Python on serverless (importing a Hugging Face model, logging an
MLflow experiment) is a **notebook you open and Run All**. Every numbered notebook also exists as a
stall fallback; only `05` and `07` are ones you actually run.

| Notebook | The work | Build surface | Notebook role |
|---|---|---|---|
| `00_START_HERE` | Config / widgets | Read + set widgets | Setup |
| `01_data_foundation_omop` | Profile the 6 OMOP tables | **Genie Code** (SQL) | Backup |
| `02_silver_feature_pipeline` | Structured silver (biomarker pivot, demographics, prior therapy) | **Genie Code** (SQL) | Backup |
| `03_exploratory_data_analysis` | Cohort charts + name the notes-only gap | **Genie Code** (it authors a serverless notebook for the Python charts) | Backup |
| `04_nlp_biomarker_extraction` | `ai_query` recovers notes-only patients | **Genie Code** (SQL) | Backup |
| `05_clinicalbert_mlflow_uc` | Register the HF model to UC, embed notes | **Notebook, Run All** | **The one step Genie Code cannot do (`%pip` + Python on serverless)** |
| `06_gold_unified_prescreen` | Fuse structured and NLP, generic trials-as-data pre-screen, patient timeline | **Genie Code** (materialized views) | Backup |
| `07_mlflow_evaluation_runs` | Extraction eval | **Genie Code** for the live SQL accuracy check; **Notebook, Run All** for the logged MLflow experiment (runs, leaderboard, traces) | **Run the notebook only for the deeper artifact** |
| `08_genie_space_setup` | Coordinator Genie space | **Genie Code** (via the `prompt-to-genie` skill) | Backup |
| `09_app` | Coordinator app | Inspiration demo, pre-built at `app/` | Reference |

**Two notebooks you run: `05` (required for the model and similarity enrichment) and `07` (optional, the
logged eval). Everything else is Genie Code.** The dividing line is the runtime, not the notebook
number: SQL → Genie Code; Python on serverless → a notebook you run.

---

## Block 0 · Setup (pre-build)

- **Pre-built by the foundation:** the six shared OMOP tables (300 patients, planted cohorts) this
  session reads. This kit adds `_config`, the notebook scaffold, and the one pre-built HF notebook.
  **No bundle to deploy, no data to generate here.**
- **Team does:** confirm the foundation is up, then open `00_START_HERE`, set the widgets (the shared
  foundation `catalog`/`schema` for reads, a `warehouse_id`, and a writable schema for what they build),
  and run `01` to profile the tables. From here the build is Genie Code, with the `05` HF notebook the
  one they run.
- **🚩 Checkpoint 1, Data foundation up.** `01` row-counts show person=300, note=300, all 6 tables
  > 0; the three biomarker groups read ≈ 180 / 60 / 60.
- **Common failures:**
  - *Stuck on auth/grants/catalog creation* → **plumbing, reveal early.** Pull the Governance SSA;
    confirm the catalog/schema names match the bundle. This is not their learnable core.
  - *`hive_metastore` muscle memory* → redirect to the UC catalog/schema from the widgets. No
    hive_metastore anywhere.
  - *Six OMOP tables not found* → the foundation lands them in the shared foundation schema. Point the
    read widgets there (e.g. `clinops_foundation`), not at the team's empty write schema.

## Block 1 · Structured silver (nb 02), the ML group's own build off the 6 OMOP tables

- **What it is:** the structured silver layer (`silver_biomarker_profile`, `silver_demographics`,
  `silver_prior_therapy`) is a biomarker pivot (HER2/ER/PR via `MAX(CASE…)`), demographics, and prior
  therapy, built directly off the 6 OMOP tables. The ML group **builds this layer** as part of their
  own pipeline. See `../../SHARED_FOUNDATION.md`.
- **ML group does:** build `02` off the 6 OMOP tables, then move to Block 2 (the gap). This is a
  straightforward pivot, so a team can move through it quickly and spend most of their time on the
  learnable core (the gap and the `ai_query` recovery).
- **🚩 Checkpoint 2, Structured silver built.** Verify `silver_biomarker_profile` has HER2 populated;
  the other two views present. (If it fails to build, the 6 OMOP tables may be missing, pull the lead
  SA; this is plumbing, not the ML lesson.)
- **Note:** the `MAX(CASE…)` pivot is standard SQL, so reveal the mechanism early if a team is spinning
  on it. The ML value is in the gap analysis and the NLP recovery that follow.

## Block 2 · EDA & the gap (nb 03), light TODO

- **Pre-built:** all the demographic/biomarker EDA cells + the plain-language gap callout.
- **Team builds:** the one biomarker-evidence classification query (both / notes-only / structured-only).
- **🚩 Checkpoint 3, The gap is named.** Team can state the number out loud: "~60 patients are
  invisible to SQL." This is the motivation for everything that follows. Make sure they feel it.

## Block 3 · NLP extraction with `ai_query` (nb 04), 🧠 SIGNPOSTED, the core "aha"

- **Pre-built:** the `responseFormat` + `from_json` cheat-sheet (both response shapes given), the
  recovery-count proof, the accuracy gut-check.
- **Team builds:** the prompt + the `ai_query` call (single note first, then `silver_nlp_biomarkers`
  over all notes with a `'nlp'` source literal).
- **🚩 Checkpoint 4, Notes-only patients recovered.** `silver_nlp_biomarkers` = 240 rows; the
  recovery-count cell shows all ~60 notes-only patients now have a biomarker call.
- **Common failures:**
  - *⚠ The whole column comes back NULL* → **THE classic gotcha. Reveal early, it's plumbing.**
    Without `responseFormat`, the model emits ```` ```json ```` fences and `from_json` returns NULL for
    every row. The fix (the two response shapes) is already on the cheat-sheet; point at it. Do **not**
    hand them the prompt wording, that's their learnable bit.
  - *FM endpoint not reachable* → confirm `databricks-claude-haiku-4-5` access; this is the team's
    GenAI-newer area, so pair early rather than letting them spin.
  - *Slow over all notes* → that's fine for 240 rows; reassure them it's the same call at 10M scale.

## Block 4 · ClinicalBERT → UC (nb 05), PRE-BUILT, optional

- **Pre-built:** the entire pyfunc wrap → log → register → `spark_udf` flow.
- **Team does:** read it for the governance story; run it **only if** HF egress + serving are available.
- **🚩 Checkpoint 5 (optional), Model in UC.** `clinicalbert_note_embedder` registered in UC;
  `silver_clinicalbert_note_embeddings` written (768-dim vectors) and the cosine-similarity demo returns
  sensible top-3 matches.
- **Common failure:** *HF download blocked or serving not approved* → **skip to nb 06**. This notebook is
  off the critical path (BYO-model governance story via embeddings, not extraction); nb 06 only needs
  `silver_nlp_biomarkers` from nb 04's `ai_query`.
  This is expected in a security-first / gated workspace. Don't let it block the track.

## Block 5 · Gold fusion + data-driven pre-screen (nb 06), GUIDED TODO

- **Pre-built:** the `joined` CTE skeleton, the source-split payoff cells, the plain-language win.
- **Team builds:** `gold_unified_biomarker_profile` (FULL OUTER + COALESCE + source audit); the
  **data-driven** pre-screen that **joins the DE group's `silver_trial_criteria`** instead of
  hardcoding Trial A/B; and `gold_patient_measurements` (the per-patient test timeline the app reads).
- **The pre-screen join (the shift this session):** trials are now data, not code. The generic rule
  is **each non-NULL `req_*` must match and age BETWEEN `age_min` AND `age_max`** (a NULL requirement =
  unconstrained). Sex match is case-insensitive (the data stores `FEMALE`). The result is a **LONG**
  `gold_trial_prescreen` (row per person × trial) via a CROSS JOIN to the criteria; a backward-compat
  **`gold_trial_prescreen_wide` VIEW** preserves the old one-row-per-person A/B/C shape.
- **🚩 Checkpoint 6, Audited, data-driven cohort exists.** `gold_trial_prescreen` (LONG) built; the
  source-split cell shows non-zero `'nlp'` eligible counts. The cohort grew because of the NLP step.
  Numbers preserved: **Trial A 140 / Trial B 56 / +31 NLP-recovered**, plus **net-new Trial C (53)**
  that screened **with no code change** because it came in via the join. **This is the end-to-end
  payoff; make the team say what the audit column buys them in a clinical setting, and that adding
  Trial C was a DE file drop, not an ML edit.**
- **Common failures:**
  - *"Both" patients double-counted* → they used UNION instead of FULL OUTER JOIN (ANSWER_KEY nb 06).
  - *Trial A loses everyone* → missing `COALESCE(had_anti_her2_therapy, false)`; NULL kills the boolean.
  - *They hardcode Trial A/B rules again* → **the redirect.** Join `silver_trial_criteria`; a non-NULL
    `req_*` is a constraint, NULL is unconstrained. Then Trial C works for free. (ANSWER_KEY nb 06.)
  - *Trial C shows no one / everyone* → the generic NULL-means-unconstrained logic is off, or the sex
    match isn't case-insensitive (`FEMALE`). (ANSWER_KEY nb 06.)

## Block 6 · MLflow evaluation (nb 07), 🧠 SIGNPOSTED

- **Pre-built:** the goldset table, the accuracy harness, the leaderboard + error-pattern cells.
- **Team builds:** the two prompts (V1 terse / V2 careful), the scoring `ai_query` inside
  `run_config()`, and the `mlflow.log_params/log_metrics` calls.
- **🚩 Checkpoint 7, Four runs in MLflow.** The Experiments UI shows 4 runs (2 prompts × 2 models);
  the leaderboard renders; the error table shows misses clustering on HER2 IHC 2+ (the *safe* miss).
- **Common failures:**
  - *Single quotes break the SQL* → they skipped `safe_prompt = prompt_text.replace("'", "''")`.
  - *No runs appear* → the `mlflow.start_run` / `log_*` TODO wasn't filled. Hint, don't reveal, this
    is a learnable bit for a GenAI-newer team (treating a prompt like a model).
  - *Eval `responseFormat` differs from nb 04* → here it's the flat 3-field form (no `result` wrapper,
    no `from_json`); that's correct, see ANSWER_KEY nb 07.

## Block 7 · Genie space (nb 08), guided setup

- **Pre-built:** the column comments, the UI click-path, all curated content in `genie/genie_space.md`.
- **Team builds:** the two verify-SQL counts, then stands up the space and pastes in the instructions +
  trusted SQL.
- **🚩 Checkpoint 8, Genie answers the headline.** The space answers *"How many Trial A-eligible
  patients were found only through pathology-note NLP?"* and the number matches the verify SQL.
- **Common failure:** *Genie's number is off* → add the trusted example SQL from `genie/genie_space.md`;
  confirm the nb 08 comment cell ran (comments are Genie's main signal).

## Block 8 · Coordinator/researcher app (nb 09), INSPIRATION DEMO (Sita's ask)

- **What it is:** the researcher-facing app Sita asked for. **We built it** as this kit's app
  deliverable; it lives at `onsite_july2026/app/`. FH has not yet approved Databricks Apps, so it is
  an **inspiration demo**, show the value, don't require the room to rebuild it. Three capabilities:
  - **Patient timeline drill-down**, reads `gold_patient_measurements`, shows a patient's tests over time.
  - **Override write-back**, the model output stays **immutable** (`gold_trial_prescreen` is never
    edited); a coordinator's disagree/remove goes to `eligibility_override` with a reason, and the app
    shows **effective eligibility** = `COALESCE(human_says, model_says)`. Auditable, reversible.
  - **In-app lightweight agent**, MLflow `ResponsesAgent` pattern, calls the `databricks-claude-sonnet-4-6`
    FM endpoint directly, three tools: patient timeline, check-against-all-trials, screen-a-subset.
- **Facilitation:** demo it to make the point (model output immutable + human overrides + an agent
  that personalizes across trials). If a team wants to extend it, timebox and restate the one success
  signal (the actionable, audited patient list). See `STRETCH.md` for open-ended extensions.
- **Framing to hold:** this is our inspiration demo, synthetic data only, PREVIEW / do-not-publish.

---

## Quick reference: checkpoint summary

| # | Checkpoint | Signal it's met |
|---|---|---|
| 1 | Data foundation up | 6 tables, groups ≈ 180/60/60 |
| 2 | Silver layer built | `silver_biomarker_profile` ≈ 240, HER2 populated |
| 3 | The gap is named | team states "~60 invisible to SQL" |
| 4 | Notes-only recovered | `silver_nlp_biomarkers` = 240, ~60 recovered |
| 5 | (opt) Model in UC | `clinicalbert_note_embedder` registered, embeddings written |
| 6 | Audited, data-driven cohort | LONG `gold_trial_prescreen` joins `silver_trial_criteria`; A 140 / B 56 / +31 NLP; Trial C 53 with no code change; `_wide` view present |
| 7 | Four runs in MLflow | 2×2 leaderboard + error patterns |
| 8 | Genie headline | NLP-recovery count matches verify SQL |

**Safety net, always:** the complete working notebooks at `onsite_july2026/notebooks/` reproduce every
artifact. Reveal them as a last resort to keep a team in the game, never as a substitute for the
learnable core, and default to synthetic for anything PHI-adjacent.
