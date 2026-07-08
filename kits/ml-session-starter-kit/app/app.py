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
else:
    st.caption("No patients available to drill into.")
