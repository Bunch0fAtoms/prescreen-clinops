# 🧬 Applied AI Feature Extraction & Trial Pre-Screening — Session Starter Kit

**Fred Hutch onsite · Applied AI session · Genie Code + notebooks**

> ### What this session is, and what it is not
> This is not a model-training session. There is no classifier to fit or tune. The work is
> **applied AI feature extraction**. You use a language model to pull biomarker facts out of
> free-text pathology notes, then feed those facts to a transparent, rules-based eligibility screen.
>
> | This session **is** | This session is **not** |
> |---|---|
> | Applied AI feature extraction. `ai_query` and ClinicalBERT read notes to pull HER2, ER, and PR status. | Training a predictive classifier. |
> | Rigorous evaluation. MLflow scores the extraction against a ground-truth set. | Hyperparameter tuning or feature engineering a model. |
> | A governed, auditable pre-screen. Deterministic rules, plus a plain-English reason per patient. | A black-box "probability of eligibility." |
> | The payoff. 31 notes-only patients recovered, 109 to 140. | A model metric like AUC. |
>
> The "model" here is a language model doing extraction, not a classifier doing prediction. The
> eligibility decision stays as auditable rules on purpose. In a clinical setting you want a decision a
> coordinator can defend, not a score they cannot explain. Want a real trained model? That lands as a
> patient-prioritization ranker in `STRETCH.md`, on top of the rules, never inside them.

This is a **starter build kit**, not a finished solution. The hard plumbing is already
wired for you: synthetic OMOP data, the pipeline skeleton, Unity Catalog governance,
all the boilerplate. **You** build the learnable core: the eligibility SQL, the
biomarker pivot, the `ai_query` NLP extraction, and the MLflow evaluation. Look for
`# TODO (you build this)` markers. That is your work.

> Scaffold, don't hand-hold. The notebooks tell you *what* to build and *why*; you
> write the logic. If a team gets truly stuck, the mentor has an answer key (see
> `reference/`) and the full working notebooks to fall back on.

> 🛟 **Backup / reference build (empowerment model).** At the onsite the ML **group builds
> their own** pre-screen on the governed foundation and presents it. This kit's `notebooks/` and
> `reference/ANSWER_KEY.md` are the **safety net**, not the script — reveal them if a group stalls,
> and lead with what the group builds. See this kit's `RUNBOOK.md` for the clean step-by-step guide.

---

## 🎯 The outcome you are shipping

A research coordinator needs to pre-screen breast-cancer patients for a set of trials:

| Trial | Looking for |
|---|---|
| **Trial A** — HER2+ | Breast cancer · HER2 **Positive** · age 18–75 · **no** prior anti-HER2 therapy |
| **Trial B** — ER+/HER2− | Breast cancer · ER **Positive** · HER2 **Negative** · **postmenopausal** · age 18–75 |
| **Trial C** — net-new | Comes from the DE group's trials catalog. **No code change** on the ML side — it screens because the pre-screen is data-driven. |

> 🔗 **Trials are data now, not hardcoded rules.** The eligibility criteria live in the DE group's
> `silver_trial_criteria` table (a Volume-fed trials catalog — see `../../SHARED_FOUNDATION.md`). Your
> pre-screen **joins that table** instead of hardcoding Trial A/B logic. The generic rule: a patient
> qualifies for a trial when **each non-NULL `req_*` matches and age is in range** (a NULL requirement
> means the trial does not constrain that field). Because it's a join, **Trial C screens with no code
> change** — the DE group added it by dropping a file.

**The catch — and the whole point of the session:** biomarker status is not always in
the structured tables. For ~60 of our 300 synthetic patients, HER2/ER/PR status was
only ever written into a **free-text pathology note**. A SQL query over `measurement`
alone **silently misses them**. You will recover them with a Foundation Model
(`ai_query`), prove the win, and *measure* how good the extraction is with MLflow.

**Where you start:** you build the **structured silver** layer (`silver_biomarker_profile`,
`silver_demographics`, `silver_prior_therapy`) yourself, off the 6 OMOP tables — that is notebook 02.
From there your build moves to the gap (notebook 03) and the `ai_query` transformation (notebook 04).

By the end you will have built:
- the **gap analysis** surfacing the ~60 notes-only patients structured SQL silently misses,
- ⭐ an **`ai_query`** NLP step that reads biomarkers out of the unstructured pathology notes (the hero),
- a **gold** unified cohort with a `biomarker_source` audit column,
- a **data-driven pre-screen** that joins the DE group's `silver_trial_criteria` — one LONG
  `gold_trial_prescreen` (row per person × trial) plus a backward-compat `gold_trial_prescreen_wide` view,
- an **MLflow evaluation** comparing prompts × models against ground truth,
- a **Genie space** so a non-technical coordinator can self-serve the cohort,
- a **coordinator/researcher app** (Sita's ask) — patient timeline drill-down, an override write-back,
  and an in-app lightweight agent.

---

## 🧱 What's pre-built vs. what you build

| Component | Status |
|---|---|
| Synthetic OMOP data generator (6 tables, 300 patients, planted cohorts) | ✅ **Shared foundation** |
| `_config` shared catalog/schema/warehouse, helpers, FM endpoints | ✅ **Pre-built** |
| **Structured silver** — biomarker pivot (HER2/ER/PR), demographics, prior therapy | 🛠️ **You build** (notebook 02, off the 6 OMOP tables) |
| Gap analysis — classify patients by evidence location (both / structured-only / notes-only) | 🛠️ **You build** (notebook 03) |
| Eligibility-cohort + gold unified prescreen logic (COALESCE + `biomarker_source` audit) | 🛠️ **You build** |
| Data-driven pre-screen: join DE's `silver_trial_criteria`, LONG `gold_trial_prescreen` + `_wide` view | 🛠️ **You build** (generic join, no hardcoded rules) |
| `gold_patient_measurements` — per-patient longitudinal test timeline (feeds the app) | 🛠️ **You build** |
| `ai_query` NLP biomarker extraction from `note_text` | 🧠 **You build** (heavily signposted) |
| MLflow evaluation run (prompt × model) | 🧠 **You build** (heavily signposted) |
| ClinicalBERT → UC registration | ✅ **Pre-built boilerplate** — running it is optional |
| Coordinator/researcher app (timeline + override + in-app agent, Sita's ask) | 🖥️ **Built** — inspiration demo at `app/` (see below) |
| More trials, advanced evals, real-data toggle | 🚀 **Stretch** — see `STRETCH.md` |

---

## 🚀 How to deploy

This kit ships as a **Databricks Asset Bundle (DAB)**, Unity-Catalog-scoped per team. The
**recommended** way to stand it up is the shared **`fred-hutch-onsite-adaptation`** Genie Code skill —
installed **once at the workspace level** (not per repo), it adapts whichever onsite kit you're working
in by reading that kit's `ADAPTATION_FACTS.json` (shipped beside this README). Manual CLI deploy is
the fallback.

### Recommended — drive it with the workspace-level onsite handoff skill ("run in my workspace")
Genie Code does **not** auto-load skills, so install the shared skill once per workspace, then drive it
from a fresh chat in this kit's folder:

1. **Install the skill once per workspace** (shared across all four onsite kits — skip if already done):
   ```bash
   databricks workspace import-dir \
     ../.assistant/skills/fred-hutch-onsite-adaptation \
     /Workspace/Users/<you>/.assistant/skills/fred-hutch-onsite-adaptation --profile <profile>
   ```
2. **Open Genie Code in a fresh chat, in this kit's folder** (hard-refresh the tab first — skills cache
   per tab) and say:
   > run in my workspace

   The skill reads **this kit's `ADAPTATION_FACTS.json`**, auto-detects your workspace, current user, catalog/schema,
   and a running warehouse; asks **synthetic-vs-real** (default synthetic — 300 patients, two trial
   cohorts, runs end-to-end immediately); and writes **only** `databricks.yml`'s `client` target
   variables (`client_catalog`, `client_schema`, `warehouse_id`). Review and **Accept** the diff.
   Nothing is hardcoded into the notebooks/SQL.
3. **Deploy + generate data from a Web Terminal** (Compute → Terminal, or ⌘+Shift+T) — the skill
   *outputs* the exact commands and stops (it never deploys from inside Genie Code, which is
   sandboxed):
   ```bash
   cd ~/<repo-folder>
   databricks bundle validate       --target client
   databricks bundle deploy         --target client
   databricks bundle run data_generation_job --target client   # lands 6 OMOP tables (300 patients)
   ```

### Fallback — manual bundle deploy
Skip the skill and configure by hand: open `databricks.yml`, fill the `client` target's
`client_catalog`, `client_schema`, and `warehouse_id` (all bundle variables), then
`databricks bundle deploy --target client` and `databricks bundle run data_generation_job --target client`.

### Then (either path)
**Open the notebooks** in your workspace (the bundle syncs `notebooks/`). Start at
**`00_START_HERE`**, set the three widgets to match your bundle targets.
   Work through the notebooks in order: **`01` (bronze) then `02` (structured silver, which you build
   off the 6 OMOP tables)**, then `03` (the gap) → `04` (`ai_query`), then `05` → `08`. Each notebook
   `%run ./_config` so they share one catalog/schema/warehouse. (See `../../SHARED_FOUNDATION.md` for
   what the shared foundation provides vs. what you build.)

> **Self-serve data option:** notebook `01` can also `exec()` the generator in-notebook
> if you'd rather not run the job. Either path lands the same tables.

### Optional — build the Genie space with the `prompt-to-genie` skill (notebook 08)
Notebook `08_genie_space_setup` stands up the self-serve Genie space. You can point-and-click it
in the UI, or drive it conversationally with the community **`prompt-to-genie`** Genie Code skill
([sean-zhang-dbx/prompt-to-genie](https://github.com/sean-zhang-dbx/prompt-to-genie)) — it walks you
through requirements → data sources → sample questions → validated `serialized_space` JSON → API
deploy → benchmark. Like the onsite adaptation skill, install it **once at the workspace level**
(it's a multi-file skill repo, so clone then import the whole folder):

```bash
gh repo clone sean-zhang-dbx/prompt-to-genie /tmp/prompt-to-genie
databricks workspace import-dir \
  /tmp/prompt-to-genie \
  /Workspace/Users/<you>/.assistant/skills/prompt-to-genie --profile <profile>
```

Then open a fresh Genie Code chat (hard-refresh — skills cache per tab) and say **"create a Genie
space"**; it reads your gold `gold_trial_prescreen` cohort and builds the space over it. It's a
conversational, checkpoint-driven flow (confirm each step), and prompt-matching is off by default on
API-created spaces — enable it in the UI after creation.

---

## 🔄 The synth → real toggle

The whole kit runs on **synthetic data by default** (no PHI — this is a security-first
customer). When Fred Hutch is ready to point it at real `curated_omop.omop` data, flip
**one** bundle variable — no query changes:

```yaml
# databricks.yml
run_with_synthetic_data: "no"   # was "yes"
source_catalog: "curated_omop"  # your real OMOP catalog
source_schema:  "omop"          # your real OMOP schema
```

The 6 OMOP table names are **identical** in synthetic and real modes, so every silver /
gold / NLP query you write here runs unchanged against the real thing. (Trying the
toggle is a stretch exercise — see `STRETCH.md`.)

---

## 🖥️ The coordinator/researcher app (Sita's ask)

Sita asked for a researcher-facing app on top of the pre-screen. **We built it as this kit's app
deliverable** and demo it onsite. Fred Hutch has not yet approved Databricks Apps, so this is our
**inspiration demo** — a working thing that shows the value, not a required build. It lives at
`onsite_july2026/app/`. Three capabilities:

- **Patient timeline drill-down.** A coordinator picks a patient and sees their tests over time.
  Reads `gold_patient_measurements` (the per-patient longitudinal test timeline).
- **Override / disagree write-back.** A coordinator can disagree and remove a patient from a trial
  with a reason. **The model output stays immutable** — the app never edits `gold_trial_prescreen`.
  Human decisions go to a separate `eligibility_override` table; the app shows **effective
  eligibility** (`COALESCE(human_says, model_says)`). Auditable and reversible. Retraining the model
  is out of scope.
- **In-app lightweight agent.** A small agent runs inside the app and calls the
  `databricks-claude-sonnet-4-6` FM endpoint directly. Authored with the MLflow **`ResponsesAgent`**
  pattern (so graduating to a served endpoint later is a lift, not a rewrite), with three tools:
  **patient timeline**, **check-a-patient-against-all-trials**, and **screen-a-subset**. This is how
  a coordinator personalizes across trials — pull a subset and check them against other criteria.

---

## 🔒 Ground rules (security-first customer)

- **Everything is Unity-Catalog-scoped** — catalog/schema come from bundle variables.
  No `hive_metastore`, ever.
- **Synthetic data only.** No real PHI in this kit. The toggle exists so you never have
  to improvise on real data to land a demo.
- **No hardcoded secrets.** No tokens, keys, or passwords in code — use bundle variables
  (and `dbutils.secrets` for any external call, though this kit needs none).
- **Governance is visible, not hidden.** Models register to UC, lineage is automatic,
  the gold layer carries a `biomarker_source` audit column so every eligibility decision
  is traceable to structured data or an AI reading of a note.

---

## 🗂️ Repo layout

```
ml-session-starter-kit/
  README.md            ← you are here
  databricks.yml       ← DAB: UC-scoped per-team target + synth/real toggle
  RUNBOOK.md           ← MENTOR build-level facilitation (checkpoints, failure modes)
  GENIE_CODE_PROMPTS.md ← ready-to-use Genie Code build prompts (free-form; the proven dry-run set)
  STRETCH.md           ← "make it your own" extension ideas
  notebooks/           ← the team scaffold (00–09): pre-built plumbing + your TODOs
  genie/               ← Genie space definition (instructions, prompts, trusted SQL)
  reference/           ← SA-ONLY answer key (mentor reveals only if a team is stuck)
  src/data_generation/ ← the synthetic OMOP generator (pre-built, do not edit)
  resources/           ← the DAB job that runs the generator
```

## 📒 The notebook arc

| # | Notebook | What it builds | Your job? |
|---|---|---|---|
| — | `_config` | shared catalog/schema/warehouse | ✅ pre-built |
| 00 | `00_START_HERE` | overview, the value story | ✅ read it |
| 01 | `01_data_foundation_omop` | generate + profile 6 OMOP tables | ✅ run, light TODO |
| 02 | `02_silver_feature_pipeline` | silver feature views (SQL pipeline) | 🛠️ build the pivots |
| 03 | `03_exploratory_data_analysis` | quantify the notes-only gap | 🛠️ light TODO |
| 04 | `04_nlp_biomarker_extraction` | `ai_query` over `note_text` | 🧠 the GenAI core |
| 05 | `05_clinicalbert_mlflow_uc` | ClinicalBERT → UC via MLflow | ✅ pre-built, optional |
| 06 | `06_gold_unified_prescreen` | gold unified + data-driven prescreen (joins `silver_trial_criteria`; LONG + `_wide` view) + `gold_patient_measurements` | 🛠️ build the fusion + the generic join |
| 07 | `07_mlflow_evaluation_runs` | MLflow eval: prompt × model | 🧠 build the eval |
| 08 | `08_genie_space_setup` | self-serve Genie space | ✅ guided setup |
| 09 | `09_app` | coordinator/researcher app: timeline drill-down + override write-back + in-app agent (Sita's ask) | 🚀 inspiration demo (we built it; `app/`) |
```
