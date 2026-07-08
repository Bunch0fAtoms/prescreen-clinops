# ─────────────────────────────────────────────────────────────────────────────
# Fred Hutch Clinical Trial Pre-Screening — Coordinator App (Streamlit)
#
# Audience: a research coordinator (stakeholder: Sita). Pick a breast-cancer
# trial, see which patients are eligible and WHY, and see a data-provenance
# badge on every patient. The provenance badge is the whole story: some patients
# are eligible only because natural language processing (NLP) recovered a
# biomarker from a clinical note that structured data alone would have missed.
#
# Reads two Unity Catalog (UC) gold tables built by the notebooks:
#   1. gold_trial_prescreen_wide   — one row per patient, eligibility per trial
#   2. gold_patient_measurements   — a per-patient test timeline (drill-down)
#
# Auth + config: see app.yaml. Runs as the app service principal in Databricks
# Apps, or locally with a personal access token (PAT) in DATABRICKS_TOKEN.
# ─────────────────────────────────────────────────────────────────────────────
import os

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

# ── Configuration from environment variables (documented in app.yaml) ────────
CATALOG = os.environ.get("CLINOPS_CATALOG", "")
SCHEMA = os.environ.get("CLINOPS_SCHEMA", "")
HTTP_PATH = os.environ.get("DATABRICKS_WAREHOUSE_HTTP_PATH", "")

# Fully-qualified table names.
PRESCREEN_TABLE = f"{CATALOG}.{SCHEMA}.gold_trial_prescreen_wide"
MEASUREMENTS_TABLE = f"{CATALOG}.{SCHEMA}.gold_patient_measurements"
# Companion review table: the coordinator's human decision per (patient, trial). Kept SEPARATE
# from the AI-produced gold table (which the notebook pipeline rebuilds), so a decision is never
# overwritten and every override is auditable. The app writes here; data scientists LEFT JOIN it
# back to gold_trial_prescreen for an adjudicated coordinator_decision column.
REVIEW_TABLE = f"{CATALOG}.{SCHEMA}.trial_prescreen_review"

# ── Trial catalog. Keys map to the trial_<x>_eligible / trial_<x>_reason columns.
# Trial A = HER2+ ; Trial B = ER+/HER2-/postmenopausal ; Trial C = triple-negative.
TRIALS = {
    "A": {"label": "Trial A — HER2+", "eligible": "trial_a_eligible", "reason": "trial_a_reason"},
    "B": {"label": "Trial B — ER+/HER2-/postmenopausal", "eligible": "trial_b_eligible", "reason": "trial_b_reason"},
    "C": {"label": "Trial C — triple-negative", "eligible": "trial_c_eligible", "reason": "trial_c_reason"},
}

# ─────────────────────────────────────────────────────────────────────────────
# Connection. In Databricks Apps, Config() picks up the app service principal
# credentials automatically. Locally, it uses your profile or DATABRICKS_TOKEN.
# ─────────────────────────────────────────────────────────────────────────────
def get_connection():
    """Open a SQL warehouse connection using the app service principal (or a
    local token). Returns a live databricks-sql-connector connection."""
    cfg = Config()  # picks up app SP creds in Databricks Apps; profile/PAT locally
    return sql.connect(
        server_hostname=cfg.host,
        http_path=HTTP_PATH,
        credentials_provider=lambda: cfg.authenticate,
    )


@st.cache_data(ttl=300, show_spinner="Querying the SQL warehouse…")
def run_query(query: str) -> pd.DataFrame:
    """Run a query and return a DataFrame. Cached for 300 seconds so the
    warehouse is not hammered when the coordinator clicks around."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall_arrow().to_pandas()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_prescreen() -> pd.DataFrame:
    """Load the one-row-per-patient pre-screen table."""
    return run_query(f"SELECT * FROM {PRESCREEN_TABLE}")


@st.cache_data(ttl=300)
def load_measurements(person_id: int) -> pd.DataFrame:
    """Load a single patient's test timeline, ordered by date."""
    return run_query(
        f"SELECT person_id, measurement_date, test_name, value, unit "
        f"FROM {MEASUREMENTS_TABLE} "
        f"WHERE person_id = {int(person_id)} "
        f"ORDER BY measurement_date"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Review write-back. The coordinator's Approve/Reject + reasoning per (patient,
# trial) is written to REVIEW_TABLE, kept separate from the rebuilt gold table.
# ─────────────────────────────────────────────────────────────────────────────
def execute_dml(statement: str) -> None:
    """Run a data-changing statement (CREATE / MERGE) with no result set."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(statement)
    finally:
        conn.close()


def ensure_review_table() -> None:
    """Create the companion review table if it does not exist. Idempotent."""
    execute_dml(
        f"CREATE TABLE IF NOT EXISTS {REVIEW_TABLE} ("
        "  person_id BIGINT, trial_id STRING, decision STRING, reasoning STRING,"
        "  reviewer STRING, reviewed_at TIMESTAMP"
        ") COMMENT 'Coordinator human review of AI pre-screen, one latest row per (person_id, trial_id).'"
    )


@st.cache_data(ttl=30)
def load_reviews() -> pd.DataFrame:
    """Latest review per (person_id, trial_id). Short TTL so a submit shows up fast."""
    return run_query(
        "SELECT person_id, trial_id, decision, reasoning, reviewer, reviewed_at FROM ("
        "  SELECT *, ROW_NUMBER() OVER (PARTITION BY person_id, trial_id ORDER BY reviewed_at DESC) rn"
        f"  FROM {REVIEW_TABLE}"
        ") WHERE rn = 1"
    )


def submit_review(person_id: int, trial_id: str, decision: str, reasoning: str, reviewer: str) -> None:
    """MERGE the reviewer's decision so they can revise it (latest wins per patient+trial)."""
    r = (reasoning or "").replace("'", "''")
    rev = (reviewer or "unknown").replace("'", "''")
    execute_dml(
        f"MERGE INTO {REVIEW_TABLE} t "
        f"USING (SELECT {int(person_id)} AS person_id, '{trial_id}' AS trial_id) s "
        "ON t.person_id = s.person_id AND t.trial_id = s.trial_id "
        f"WHEN MATCHED THEN UPDATE SET decision='{decision}', reasoning='{r}', "
        f"  reviewer='{rev}', reviewed_at=current_timestamp() "
        "WHEN NOT MATCHED THEN INSERT (person_id, trial_id, decision, reasoning, reviewer, reviewed_at) "
        f"  VALUES ({int(person_id)}, '{trial_id}', '{decision}', '{r}', '{rev}', current_timestamp())"
    )


def current_reviewer() -> str:
    """Best-effort identity of the app viewer (Databricks Apps injects user headers);
    falls back to the service principal when unavailable."""
    try:
        h = st.context.headers
        return (
            h.get("X-Forwarded-Email")
            or h.get("X-Forwarded-Preferred-Username")
            or "app-service-principal"
        )
    except Exception:  # noqa: BLE001
        return "app-service-principal"


# ─────────────────────────────────────────────────────────────────────────────
# Provenance badge. Green pill for structured data, amber pill for a biomarker
# recovered from a clinical note via NLP.
# ─────────────────────────────────────────────────────────────────────────────
def provenance_badge_html(source: str) -> str:
    """Return an HTML colored pill for a biomarker_source value."""
    if source == "nlp":
        return (
            '<span style="background:#FBF1DC;color:#8A5A0B;border:1px solid #E8CF94;'
            'border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;'
            'white-space:nowrap;">NLP-recovered</span>'
        )
    return (
        '<span style="background:#DCEFE6;color:#1F6B45;border:1px solid #A9D8C2;'
        'border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;'
        'white-space:nowrap;">Structured</span>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Page setup + Fred Hutch-ish header (red/navy, no external assets or CDNs).
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Trial Pre-Screening — Coordinator", page_icon="🔬", layout="wide")

st.markdown(
    """
    <div style="background:linear-gradient(90deg,#003b5c 0%,#00263a 100%);
                border-left:8px solid #c8102e;border-radius:8px;
                padding:16px 22px;margin-bottom:8px;">
      <div style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:0.2px;">
        Clinical Trial Pre-Screening
      </div>
      <div style="color:#b9c7d1;font-size:13px;margin-top:2px;">
        Coordinator view — eligible patients, the reason why, and where each
        biomarker came from.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Guard: config must be set before we can query anything. ──────────────────
missing = [
    name
    for name, val in [
        ("CLINOPS_CATALOG", CATALOG),
        ("CLINOPS_SCHEMA", SCHEMA),
        ("DATABRICKS_WAREHOUSE_HTTP_PATH", HTTP_PATH),
    ]
    if not val
]
if missing:
    st.error(
        "Missing configuration. Set these environment variables (see app.yaml): "
        + ", ".join(missing)
    )
    st.stop()

# ── Sidebar: trial selector. ─────────────────────────────────────────────────
with st.sidebar:
    st.header("Select a trial")
    trial_key = st.selectbox(
        "Trial",
        options=list(TRIALS.keys()),
        format_func=lambda k: TRIALS[k]["label"],
    )
    st.caption(
        "Provenance: **Structured** biomarkers came from coded lab and pathology "
        "data. **NLP-recovered** biomarkers were read from a clinical note that "
        "structured data alone would have missed."
    )

trial = TRIALS[trial_key]
elig_col = trial["eligible"]
reason_col = trial["reason"]

# ── Load data. Fail gracefully with a readable message. ──────────────────────
try:
    df = load_prescreen()
except Exception as exc:  # noqa: BLE001 — surface any connection/query error to the user
    st.error(f"Could not read {PRESCREEN_TABLE}.\n\n{exc}")
    st.stop()

# Ensure the companion review table exists, then load the latest decision per (patient, trial).
review_map: dict = {}  # (person_id, trial_id) -> {"decision", "reasoning", "reviewer"}
reviews_available = True
try:
    ensure_review_table()
    for _rr in load_reviews().itertuples():
        review_map[(int(_rr.person_id), _rr.trial_id)] = {
            "decision": _rr.decision, "reasoning": _rr.reasoning, "reviewer": _rr.reviewer,
        }
except Exception as exc:  # noqa: BLE001
    reviews_available = False
    st.warning(f"Review write-back unavailable this session (decisions not recorded): {exc}")


def decision_badge_html(person_id) -> str:
    """A thumbs badge for the current decision on (person_id, selected trial)."""
    r = review_map.get((int(person_id), trial_key))
    if not r or not r.get("decision"):
        return '<span style="color:#6B7780;">— not reviewed</span>'
    if r["decision"] == "approved":
        return ('<span style="background:#DCEFE6;color:#1F6B45;border:1px solid #A9D8C2;'
                'border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;">👍 Approved</span>')
    return ('<span style="background:#F7DCDC;color:#9B2226;border:1px solid #E3A9A9;'
            'border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;">👎 Rejected</span>')

# Patients eligible for the selected trial.
eligible = df[df[elig_col] == True].copy()  # noqa: E712 — explicit boolean match

# ─────────────────────────────────────────────────────────────────────────────
# Header KPIs: total eligible, NLP-recovered count, and the structured baseline
# framed as an uplift.
# ─────────────────────────────────────────────────────────────────────────────
total_eligible = len(eligible)
nlp_recovered = int((eligible["biomarker_source"] == "nlp").sum())
structured_baseline = total_eligible - nlp_recovered

st.subheader(TRIALS[trial_key]["label"])

k1, k2, k3 = st.columns(3)
k1.metric("Total eligible", f"{total_eligible}")
k2.metric("Recovered via NLP", f"{nlp_recovered}")
k3.metric("Structured-only baseline", f"{structured_baseline}")

if nlp_recovered > 0:
    st.info(
        f"Structured SQL alone would have found **{structured_baseline}** eligible "
        f"patients. NLP recovered **{nlp_recovered}** more, for a total of "
        f"**{total_eligible}**."
    )
else:
    st.info(
        f"Structured SQL found all **{structured_baseline}** eligible patients for "
        f"this trial. No additional patients were recovered via NLP."
    )

# ─────────────────────────────────────────────────────────────────────────────
# Main panel: sortable table of eligible patients with a provenance badge.
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#### Eligible patients")

if total_eligible == 0:
    st.warning("No patients are eligible for this trial.")
else:
    table = eligible[
        [
            "person_id",
            "age_at_dx_years",
            "her2_status",
            "er_status",
            "pr_status",
            "menopausal_status",
            reason_col,
            "biomarker_source",
        ]
    ].rename(
        columns={
            "person_id": "Person ID",
            "age_at_dx_years": "Age",
            "her2_status": "HER2",
            "er_status": "ER",
            "pr_status": "PR",
            "menopausal_status": "Menopausal status",
            reason_col: "Reason",
        }
    )
    # Turn the raw source string into a colored provenance pill.
    table["Provenance"] = table["biomarker_source"].map(provenance_badge_html)
    table = table.drop(columns=["biomarker_source"])
    # Reflect the coordinator's current decision for this trial (read-only here; set it in the drill-down).
    table["Decision"] = table["Person ID"].map(decision_badge_html)

    # st.markdown with unsafe_allow_html renders the colored pills. We sort by
    # Person ID by default; the coordinator can re-sort by clicking headers is
    # not available in a static HTML table, so we expose a sort control instead.
    sort_col = st.selectbox(
        "Sort by",
        options=["Person ID", "Age", "HER2", "ER", "PR", "Menopausal status", "Reason"],
        index=0,
    )
    table = table.sort_values(by=sort_col, kind="stable")

    # Build an HTML table so the provenance pills render as colored badges.
    header_cells = "".join(
        f'<th style="text-align:left;padding:8px 12px;border-bottom:2px solid #e2dcd2;'
        f'font-size:12px;color:#38434b;">{col}</th>'
        for col in table.columns
    )
    body_rows = []
    for _, row in table.iterrows():
        cells = "".join(
            f'<td style="padding:7px 12px;border-bottom:1px solid #eee;font-size:13px;">{val}</td>'
            for val in row
        )
        body_rows.append(f"<tr>{cells}</tr>")
    html_table = (
        '<div style="overflow-x:auto;">'
        '<table style="border-collapse:collapse;width:100%;">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        "</table></div>"
    )
    st.markdown(html_table, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Patient drill-down: pick a person_id and show that patient's test timeline.
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#### Patient drill-down")

# Offer the eligible patients first; fall back to all patients if none.
drill_options = (
    sorted(eligible["person_id"].tolist())
    if total_eligible > 0
    else sorted(df["person_id"].tolist())
)

if drill_options:
    person_id = st.selectbox("Person ID", options=drill_options)
    try:
        timeline = load_measurements(person_id)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read {MEASUREMENTS_TABLE}.\n\n{exc}")
        timeline = pd.DataFrame()

    if timeline.empty:
        st.caption("No measurements on file for this patient.")
    else:
        st.caption(f"Test timeline for person {person_id}, ordered by date.")
        st.dataframe(
            timeline.rename(
                columns={
                    "person_id": "Person ID",
                    "measurement_date": "Date",
                    "test_name": "Test",
                    "value": "Value",
                    "unit": "Unit",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    # ── Reviewer decision for this (patient, trial). Writes to the review table. ──
    st.markdown(f"##### Reviewer decision — {TRIALS[trial_key]['label']}")
    _existing = review_map.get((int(person_id), trial_key), {})
    _cur = _existing.get("decision")
    if _cur:
        st.caption(
            f"Current: {'👍 Approved' if _cur == 'approved' else '👎 Rejected'} "
            f"by {_existing.get('reviewer', 'unknown')}."
        )
    with st.form(f"review_{person_id}_{trial_key}"):
        choice = st.radio(
            "Decision", options=["approved", "rejected"], horizontal=True,
            index=1 if _cur == "rejected" else 0,
            format_func=lambda x: "👍 Approve" if x == "approved" else "👎 Reject",
        )
        reasoning = st.text_area(
            "Reasoning (why this patient does or does not fit the trial)",
            value=_existing.get("reasoning") or "",
        )
        submitted = st.form_submit_button("Save decision", disabled=not reviews_available)
    if submitted:
        try:
            submit_review(person_id, trial_key, choice, reasoning, current_reviewer())
            st.cache_data.clear()
            st.success("Decision saved to the review table.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not save the decision: {exc}")
else:
    st.caption("No patients available to drill into.")
