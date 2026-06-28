#!/usr/bin/env python3
"""
Fred Hutch Clinical Trial Pre-Screening — OMOP Synthetic Data Generator

Generates 300 breast-cancer patients across 3 biomarker-source groups plus
planted cohorts for two clinical trials. Run via:

    python generate_omop_data.py [catalog] [schema]

Defaults (local dev only): pass catalog and schema as argv[1]/argv[2].
When run via `databricks bundle run`, catalog/schema come from bundle variables.
"""

import sys
import random
import math
from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np
from faker import Faker
from pyspark.sql.types import (
    StructType, StructField,
    LongType, IntegerType, FloatType, StringType, DateType, TimestampType,
)

# ── CLI args ───────────────────────────────────────────────────────────────────
CATALOG = sys.argv[1] if len(sys.argv) > 1 else "your_catalog_here"  # pass via bundle variables in production
SCHEMA  = sys.argv[2] if len(sys.argv) > 2 else "demo_clinical_trial_pre_screening_omop"

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

# ── Spark session (serverless via Databricks Connect; falls back to local) ─────
try:
    from databricks.connect import DatabricksSession
    spark = DatabricksSession.builder.serverless(True).getOrCreate()
except Exception:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT IDs — synthetic but stable.
# Same integer = same meaning everywhere. Readers should rely on *_source_value
# strings; these exist so cross-table joins/filters are coherent.
# ─────────────────────────────────────────────────────────────────────────────

GENDER_FEMALE         = 8532
GENDER_MALE           = 8507

RACE_WHITE            = 8527   # White
RACE_BLACK            = 8516   # Black or African American
RACE_ASIAN            = 8515   # Asian
RACE_NHPI             = 8657   # Native Hawaiian or Other Pacific Islander
RACE_OTHER            = 8522   # Other / Unknown

ETHNIC_NOT_HISPANIC   = 38003564
ETHNIC_HISPANIC       = 38003563

COND_BREAST_CANCER    = 4112853   # Malignant neoplasm of breast
COND_TYPE_EHR         = 32817     # EHR
COND_STATUS_ACTIVE    = 4230359   # Active

MEAS_ER               = 36031453  # Estrogen receptor [Interpretation] in Tissue
MEAS_PR               = 36031454  # Progesterone receptor [Interpretation] in Tissue
MEAS_HER2             = 36031455  # HER2 [Presence] in Tissue by Immune stain
MEAS_TYPE_LAB         = 44818702  # Lab

VAL_POSITIVE          = 9191
VAL_NEGATIVE          = 9189
VAL_EQUIVOCAL         = 4132135

OBS_MENOPAUSAL        = 4218190   # Menopausal status
OBS_ECOG              = 4170770   # ECOG performance status
OBS_TYPE_EHR          = 38000280  # EHR

VAL_POSTMENOPAUSAL    = 4216458
VAL_PREMENOPAUSAL     = 4099823

DRUG_TRASTUZUMAB      = 1397141   # Herceptin
DRUG_PERTUZUMAB       = 1300132   # Perjeta
DRUG_PACLITAXEL       = 1300109   # Taxol
DRUG_DOXORUBICIN      = 1300200   # Adriamycin
DRUG_CYCLOPHOSPHAMIDE = 1300201   # Cytoxan
DRUG_LETROZOLE        = 1300202   # Femara
DRUG_TAMOXIFEN        = 1300203   # Nolvadex
DRUG_TYPE_EHR         = 38000177

OBS_AJCC_STAGE        = 4222095   # AJCC clinical stage

# AJCC stage value concept IDs (synthetic, stable)
STAGE_CONCEPTS = {
    "Stage I":    1002001,
    "Stage IIA":  1002002,
    "Stage IIB":  1002003,
    "Stage IIIA": 1002004,
    "Stage IIIB": 1002005,
    "Stage IV":   1002006,
}
# Cumulative distribution — clinically plausible for diagnosed breast cancer
# Stage I 15% | IIA 28% | IIB 22% | IIIA 18% | IIIB 10% | IV 7%
STAGE_CDF = [
    (0.15, "Stage I"),
    (0.43, "Stage IIA"),
    (0.65, "Stage IIB"),
    (0.83, "Stage IIIA"),
    (0.93, "Stage IIIB"),
    (1.00, "Stage IV"),
]

NOTE_TYPE_PATH        = 44814641  # Pathology report
NOTE_CLASS_PATH       = 44814643  # Pathology report
NOTE_CLASS_PROGRESS   = 44814637  # Progress note
NOTE_ENCODING_UTF8    = 32678
NOTE_LANG_ENGLISH     = 4180186

# Fixed reference "today" for reproducibility
REF_DATE = date(2025, 6, 15)

# ─────────────────────────────────────────────────────────────────────────────
# ICD-10 breast cancer codes — varied per patient
# ─────────────────────────────────────────────────────────────────────────────
ICD10_BREAST = [
    ("ICD10:C50.011", "Malignant neoplasm of nipple and areola, right female breast"),
    ("ICD10:C50.111", "Malignant neoplasm of central portion of right female breast"),
    ("ICD10:C50.211", "Malignant neoplasm of upper-inner quadrant of right female breast"),
    ("ICD10:C50.311", "Malignant neoplasm of lower-inner quadrant of right female breast"),
    ("ICD10:C50.411", "Malignant neoplasm of upper-outer quadrant of right female breast"),
    ("ICD10:C50.511", "Malignant neoplasm of lower-outer quadrant of right female breast"),
    ("ICD10:C50.611", "Malignant neoplasm of axillary tail of right female breast"),
    ("ICD10:C50.811", "Malignant neoplasm of overlapping sites of right female breast"),
    ("ICD10:C50.911", "Malignant neoplasm of unspecified site of right female breast"),
    ("ICD10:C50.012", "Malignant neoplasm of nipple and areola, left female breast"),
    ("ICD10:C50.412", "Malignant neoplasm of upper-outer quadrant of left female breast"),
    ("ICD10:C50.912", "Malignant neoplasm of unspecified site of left female breast"),
]

HISTOLOGIES = [
    "Invasive ductal carcinoma, NOS",
    "Invasive ductal carcinoma, grade {g}",
    "Infiltrating ductal carcinoma",
    "Invasive lobular carcinoma",
    "Invasive mammary carcinoma, no special type",
    "Invasive carcinoma of breast (IDC)",
]

SPECIMENS = [
    "Right breast, core needle biopsy",
    "Left breast, core needle biopsy",
    "Right breast mass, ultrasound-guided biopsy",
    "Left breast, stereotactic biopsy",
    "Right breast, excisional biopsy",
    "Left breast lumpectomy specimen",
    "Right breast, vacuum-assisted biopsy",
    "Left upper outer quadrant, core biopsy",
]

CLINICAL_HX = [
    "Palpable {side} breast mass. Rule out malignancy.",
    "Screening mammogram with {side} breast mass, BIRADS 5. Biopsy requested.",
    "Known {side} breast carcinoma; re-biopsy for receptor status.",
    "{side} breast density with suspicious calcifications on mammography.",
    "Palpable axillary node, {side}. Primary breast cancer suspected.",
    "{side} breast mass found on MRI; clinical stage T2N0.",
    "Newly diagnosed {side} breast cancer; receptor studies requested.",
]

GRADE_NOTTINGHAM = {1: "5", 2: "6", 3: "7–8"}  # approximate Nottingham score per grade


# ─────────────────────────────────────────────────────────────────────────────
# NOTE GENERATION — phrase banks + 3 report structures
# ─────────────────────────────────────────────────────────────────────────────

def _r(pid: int, offset: int, lst: list):
    """Deterministically pick one element from lst using person_id as seed."""
    random.seed(pid * 1000 + offset)
    return random.choice(lst)

def _ri(pid: int, offset: int, lo: int, hi: int) -> int:
    random.seed(pid * 1000 + offset)
    return random.randint(lo, hi)

def _rf(pid: int, offset: int, lo: float, hi: float) -> float:
    random.seed(pid * 1000 + offset)
    return round(random.uniform(lo, hi), 1)


def _er_phrase(pid: int, status: str) -> str:
    pct = _ri(pid, 1, 70, 95)
    allred = _ri(pid, 2, 6, 8)
    intensity = _r(pid, 3, ["moderate", "strong", "strong diffuse"])
    if status == "Positive":
        return _r(pid, 10, [
            f"Estrogen receptor (ER): Positive ({pct}% nuclear staining, Allred score {allred}/8)",
            f"ER: Positive — {intensity} nuclear immunoreactivity in {pct}% of tumor cells",
            f"Estrogen receptor status: POSITIVE (Allred {allred}/8; {intensity} staining)",
            f"ER immunostain: positive, {pct}% nuclei reactive ({intensity})",
            f"Estrogen receptor: reactive, {pct}% of nuclei, Allred score {allred}",
        ])
    elif status == "Negative":
        return _r(pid, 10, [
            "Estrogen receptor (ER): Negative (< 1% nuclear staining)",
            "ER: Negative — no significant nuclear reactivity observed",
            "Estrogen receptor status: NEGATIVE (Allred 0/8, <1%)",
            "ER immunostain: negative (<1% nuclei reactive)",
            "Estrogen receptor: non-reactive (<1%)",
        ])
    else:
        return "Estrogen receptor (ER): Borderline (10% nuclear staining, Allred 3/8)"


def _pr_phrase(pid: int, status: str) -> str:
    pct = _ri(pid, 11, 40, 90)
    allred = _ri(pid, 12, 5, 7)
    intensity = _r(pid, 13, ["moderate", "moderate-to-strong", "weak-to-moderate"])
    if status == "Positive":
        return _r(pid, 20, [
            f"Progesterone receptor (PR): Positive ({pct}% nuclear staining, Allred score {allred}/8)",
            f"PR: Positive — {intensity} nuclear staining in {pct}% of cells",
            f"Progesterone receptor status: POSITIVE (Allred {allred}; {intensity})",
            f"PR immunostain: positive, {pct}% reactive nuclei",
            f"Progesterone receptor: reactive ({pct}%, Allred {allred}/8)",
        ])
    elif status == "Negative":
        return _r(pid, 20, [
            "Progesterone receptor (PR): Negative (< 1%)",
            "PR: Negative — no progesterone receptor expression detected",
            "Progesterone receptor status: NEGATIVE (Allred 0/8)",
            "PR immunostain: negative",
            "Progesterone receptor: non-reactive (<1%)",
        ])
    else:
        return "Progesterone receptor (PR): Borderline (5% nuclear staining)"


def _her2_phrase(pid: int, status: str) -> str:
    fish_ratio = _rf(pid, 21, 2.4, 3.8)
    fish_ratio_neg = _rf(pid, 22, 1.2, 1.7)
    if status == "Positive":
        return _r(pid, 30, [
            "HER2: Positive (3+ by IHC)",
            f"HER2/neu: Positive by FISH (HER2/CEP17 ratio {fish_ratio})",
            "HER2 (c-erbB-2): 3+ (strongly positive)",
            f"HER2 amplification: DETECTED (FISH ratio {fish_ratio})",
            "Her-2/neu overexpression confirmed: 3+ (score positive)",
        ])
    elif status == "Negative":
        return _r(pid, 30, [
            "HER2: Negative (1+ by IHC, FISH not performed)",
            "HER2/neu: Negative (score 1+)",
            f"HER2: negative (2+ by IHC; FISH: ratio {fish_ratio_neg}, non-amplified)",
            "Her-2/neu: 0 (negative)",
            f"HER2/neu amplification: NOT detected (FISH ratio {fish_ratio_neg})",
        ])
    else:  # Equivocal
        return "HER2 (c-erbB-2): 2+ (equivocal by IHC; FISH reflex testing recommended)"


def generate_pathology_note(pid: int, er: str, pr: str, her2: str,
                             dx_date: date, patient_name: str) -> str:
    """Return a realistic surgical pathology / IHC report for a breast cancer patient."""
    random.seed(pid * 1000 + 99)

    acc_no = f"FH-PATH-{random.randint(100000, 999999)}"
    mrn = f"FH-MRN-{pid:06d}"
    grade = random.choice([2, 2, 2, 3, 1])  # grade 2 most common
    tumor_size = round(random.uniform(0.8, 4.2), 1)
    ki67 = random.randint(12, 65)
    nottingham = GRADE_NOTTINGHAM.get(grade, "6")
    lvi = random.choice(["Not identified", "Not identified", "Present", "Not identified"])
    specimen = _r(pid, 50, SPECIMENS)
    side = "right" if "right" in specimen.lower() or "Right" in specimen else "left"
    clin_hx = _r(pid, 51, CLINICAL_HX).format(side=side.title())
    histology_tmpl = _r(pid, 52, HISTOLOGIES)
    histology = histology_tmpl.format(g=grade)
    provider_first = fake.first_name()
    provider_last = fake.last_name()
    provider = f"{provider_first} {provider_last}"

    date_recv = dx_date
    date_rep = dx_date + timedelta(days=random.randint(1, 3))

    er_line  = _er_phrase(pid, er)
    pr_line  = _pr_phrase(pid, pr)
    her2_line = _her2_phrase(pid, her2)

    # Staging note based on biomarker combo
    if her2 == "Positive" and er == "Positive":
        subtype = "HR+/HER2+ (luminal B-like, HER2-positive)"
    elif her2 == "Positive" and er == "Negative":
        subtype = "HER2-positive (non-luminal)"
    elif her2 == "Negative" and er == "Positive":
        subtype = "HR+/HER2- (luminal A or B)"
    else:
        subtype = "Triple-negative (ER-/PR-/HER2-)"

    # Rotate across 3 report structures by person_id
    struct = pid % 3

    if struct == 0:
        # ── Structure 0: Formal section-based surgical pathology report ──────
        note = f"""FRED HUTCHINSON CANCER CENTER
DEPARTMENT OF PATHOLOGY — SURGICAL PATHOLOGY REPORT

Accession No.: {acc_no}
Date Received: {date_recv.strftime('%B %d, %Y')}
Date Reported: {date_rep.strftime('%B %d, %Y')}

Patient MRN: {mrn}

SPECIMEN SUBMITTED:
  {specimen}

CLINICAL HISTORY:
  {clin_hx}

GROSS DESCRIPTION:
  Received in formalin, labeled with patient MRN and specimen site.
  Core biopsy material, estimated {random.randint(2, 5)} cores measuring up to
  {round(random.uniform(10, 18), 0):.0f} mm in greatest dimension. Submitted in entirety.

MICROSCOPIC DESCRIPTION:
  Sections show {histology.lower()}. Nottingham histologic grade {grade}/3
  (tubular formation score {random.randint(2,3)}, nuclear pleomorphism score
  {random.randint(1,3)}, mitotic rate score {random.randint(1,2)};
  combined Nottingham score {nottingham}). Invasive tumor size estimated at
  {tumor_size} cm. Lymphovascular invasion: {lvi}.

IMMUNOHISTOCHEMISTRY:
  {er_line}
  {pr_line}
  {her2_line}
  Ki-67 proliferative index: {ki67}%

PATHOLOGIC SUBTYPE: {subtype}

DIAGNOSIS:
  {specimen} — {histology}
  Nuclear grade: {grade}/3
  Tumor size (estimate): {tumor_size} cm
  Lymphovascular invasion: {lvi}
  Receptor profile: {subtype}

Electronically signed by: {provider}, MD
{date_rep.strftime('%m/%d/%Y')}
"""

    elif struct == 1:
        # ── Structure 1: Short core needle biopsy format ──────────────────────
        note = f"""PATHOLOGY REPORT — CORE NEEDLE BIOPSY
{acc_no}  |  {date_rep.strftime('%Y-%m-%d')}

SPECIMEN: {specimen}
INDICATION: {clin_hx}

HISTOLOGIC FINDINGS:
  Diagnosis: {histology}
  Nuclear Grade: {grade}/3
  Estimated Tumor Size: {tumor_size} cm
  Lymphovascular Invasion: {lvi}

RECEPTOR / BIOMARKER STATUS:
  {er_line}
  {pr_line}
  {her2_line}
  Ki-67: {ki67}%

MOLECULAR SUBTYPE: {subtype}

COMMENT:
  Clinical correlation recommended. These findings represent a biopsy
  diagnosis; final staging will require complete excision and axillary
  lymph node evaluation.

Pathologist: {provider}, M.D.  |  Fred Hutchinson Cancer Center
"""

    else:
        # ── Structure 2: Consultation / outside institution report ─────────────
        note = f"""CONSULTATION SURGICAL PATHOLOGY
Fred Hutchinson Cancer Center — Department of Pathology

Accession: {acc_no}
Outside MRN: {mrn}
Date of Consultation: {date_rep.strftime('%m/%d/%Y')}

SUBMITTED MATERIAL: {specimen}

CLINICAL SUMMARY:
  {clin_hx} Outside pathology reviewed; confirmatory studies performed.

HISTOPATHOLOGY:
  {histology}, Nottingham grade {grade}/3, tumor size approximately
  {tumor_size} cm. {lvi} lymphovascular invasion.

IHC / BIOMARKER RESULTS:
  {er_line}
  {pr_line}
  {her2_line}
  Ki-67 labeling index: {ki67}%

INTERPRETATION:
  The above findings are consistent with {subtype} breast carcinoma.
  Recommend multidisciplinary tumor board review for treatment planning.

Attending Pathologist: {provider}, M.D.
"""

    return note.strip()


def generate_generic_note(pid: int, dx_date: date) -> str:
    """Return a clinical progress note with NO biomarker mention (structured-only patients)."""
    random.seed(pid * 1000 + 77)
    note_date = dx_date + timedelta(days=random.randint(30, 120))
    mrn = f"FH-MRN-{pid:06d}"
    provider = f"{fake.first_name()} {fake.last_name()}"
    cycles = random.randint(2, 6)
    chemo = random.choice(["AC-T (doxorubicin/cyclophosphamide followed by paclitaxel)",
                            "ddAC-T (dose-dense AC followed by weekly paclitaxel)",
                            "TC (docetaxel/cyclophosphamide)"])
    side = random.choice(["right", "left"])
    return f"""ONCOLOGY PROGRESS NOTE
MRN: {mrn}  |  {note_date.strftime('%m/%d/%Y')}

CHIEF COMPLAINT: Routine follow-up, breast cancer treatment.

INTERVAL HISTORY:
  Patient returns for cycle {cycles} of {chemo} chemotherapy for
  {side} breast cancer diagnosed {dx_date.strftime('%B %Y')}. Tolerating
  treatment reasonably well. Reports fatigue and mild nausea, managed
  with antiemetics. No fever, no signs of infection.

PHYSICAL EXAMINATION:
  General: Alert and oriented, in no acute distress.
  Breast: {side.title()} breast post-biopsy scar well-healed. No new palpable masses.
  Axilla: No palpable lymphadenopathy.

ASSESSMENT / PLAN:
  1. Breast cancer, {side} — continue current regimen per protocol.
  2. Fatigue / nausea — ondansetron PRN, adequate hydration encouraged.
  3. CBC and CMP reviewed; within acceptable parameters for treatment.
  4. Return in 3 weeks for next cycle.

{provider}, MD — Breast Oncology
Fred Hutchinson Cancer Center
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# PATIENT PROFILE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def make_patient_profiles() -> pd.DataFrame:
    """Build the master profile for all 300 patients (includes hidden _columns)."""
    rows = []

    for pid in range(1, 301):
        random.seed(SEED + pid)
        np.random.seed(SEED + pid)

        # ── Segment assignment ─────────────────────────────────────────────
        if 1 <= pid <= 20:
            segment = "trial_a_eligible"
            biomarker_group = "both-agree"
            her2 = "Positive"
            er   = random.choice(["Positive", "Negative"])
            pr   = random.choice(["Positive", "Negative"])
            age  = random.randint(28, 65)
            is_post = age >= 50
            has_anti_her2 = False

        elif 21 <= pid <= 30:
            segment = "trial_a_ineligible"
            biomarker_group = "both-agree"
            her2 = "Positive"
            er   = random.choice(["Positive", "Negative"])
            pr   = random.choice(["Positive", "Negative"])
            age  = random.randint(35, 70)
            is_post = age >= 50
            has_anti_her2 = True

        elif 31 <= pid <= 50:
            segment = "trial_b_eligible"
            biomarker_group = "both-agree"
            her2 = "Negative"
            er   = "Positive"
            pr   = random.choice(["Positive", "Negative"])
            age  = random.randint(50, 72)
            is_post = True
            has_anti_her2 = False

        elif 51 <= pid <= 55:
            segment = "trial_b_ineligible"
            biomarker_group = "both-agree"
            her2 = "Negative"
            er   = "Positive"           # ER+ but pre-menopausal → ineligible for B
            pr   = random.choice(["Positive", "Negative"])
            age  = random.randint(28, 45)
            is_post = False
            has_anti_her2 = False

        elif 56 <= pid <= 60:
            segment = "trial_b_ineligible"
            biomarker_group = "both-agree"
            her2 = "Negative"
            er   = "Negative"           # ER- → ineligible for B
            pr   = "Negative"
            age  = random.randint(40, 70)
            is_post = age >= 50
            has_anti_her2 = False

        elif 61 <= pid <= 180:
            segment = "general_both_agree"
            biomarker_group = "both-agree"
            roll = random.random()
            if roll < 0.30:
                her2, er = "Positive", "Positive"
            elif roll < 0.50:
                her2, er = "Positive", "Negative"
            elif roll < 0.80:
                her2, er = "Negative", "Positive"
            else:
                her2, er = "Negative", "Negative"
            pr = "Positive" if (er == "Positive" and random.random() < 0.75) else "Negative"
            age = int(np.clip(np.random.normal(55, 12), 28, 75))
            is_post = age >= 50
            has_anti_her2 = False

        elif 181 <= pid <= 240:
            segment = "notes_only"
            biomarker_group = "notes-only"
            roll = random.random()
            if roll < 0.30:
                her2, er = "Positive", "Positive"
            elif roll < 0.50:
                her2, er = "Positive", "Negative"
            elif roll < 0.80:
                her2, er = "Negative", "Positive"
            else:
                her2, er = "Negative", "Negative"
            pr = "Positive" if (er == "Positive" and random.random() < 0.75) else "Negative"
            age = int(np.clip(np.random.normal(55, 12), 28, 75))
            is_post = age >= 50
            has_anti_her2 = False

        else:  # 241–300
            segment = "structured_only"
            biomarker_group = "structured-only"
            roll = random.random()
            if roll < 0.30:
                her2, er = "Positive", "Positive"
            elif roll < 0.50:
                her2, er = "Positive", "Negative"
            elif roll < 0.80:
                her2, er = "Negative", "Positive"
            else:
                her2, er = "Negative", "Negative"
            pr = "Positive" if (er == "Positive" and random.random() < 0.75) else "Negative"
            age = int(np.clip(np.random.normal(55, 12), 28, 75))
            is_post = age >= 50
            has_anti_her2 = False

        # ── Demographics ────────────────────────────────────────────────────
        r = random.random()
        if r < 0.65:
            race_id, race_sv = RACE_WHITE, "White"
        elif r < 0.80:
            race_id, race_sv = RACE_ASIAN, "Asian"
        elif r < 0.90:
            race_id, race_sv = RACE_BLACK, "Black or African American"
        elif r < 0.95:
            race_id, race_sv = RACE_NHPI, "Native Hawaiian or Other Pacific Islander"
        else:
            race_id, race_sv = RACE_OTHER, "Other"

        if random.random() < 0.85:
            eth_id, eth_sv = ETHNIC_NOT_HISPANIC, "Not Hispanic or Latino"
        else:
            eth_id, eth_sv = ETHNIC_HISPANIC, "Hispanic or Latino"

        # ── Dates ───────────────────────────────────────────────────────────
        dx_offset = random.randint(180, 1000)
        dx_date = REF_DATE - timedelta(days=dx_offset)

        birth_year  = REF_DATE.year - age - random.randint(0, 1)
        birth_month = random.randint(1, 12)
        birth_day   = random.randint(1, 28)
        bd = date(birth_year, birth_month, birth_day)

        name = fake.name_female()

        rows.append({
            # ── OMOP person columns ──────────────────────────────────────
            "person_id":                  pid,
            "gender_concept_id":          GENDER_FEMALE,
            "year_of_birth":              birth_year,
            "month_of_birth":             birth_month,
            "day_of_birth":               birth_day,
            "birth_datetime":             datetime(birth_year, birth_month, birth_day, 0, 0, 0),
            "race_concept_id":            race_id,
            "ethnicity_concept_id":       eth_id,
            "location_id":                None,
            "provider_id":                None,
            "care_site_id":               None,
            "person_source_value":        f"FH-{pid:06d}",
            "gender_source_value":        "FEMALE",
            "gender_source_concept_id":   GENDER_FEMALE,
            "race_source_value":          race_sv,
            "race_source_concept_id":     race_id,
            "ethnicity_source_value":     eth_sv,
            "ethnicity_source_concept_id": eth_id,
            "birth_date":                 bd,
            # ── Hidden profile (not written to person table) ─────────────
            "_name":             name,
            "_segment":          segment,
            "_biomarker_group":  biomarker_group,
            "_her2":             her2,
            "_er":               er,
            "_pr":               pr,
            "_age_at_dx":        age,
            "_is_postmenopausal": is_post,
            "_has_anti_her2":    has_anti_her2,
            "_dx_date":          dx_date,
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

PERSON_COLS = [
    "person_id", "gender_concept_id", "year_of_birth", "month_of_birth",
    "day_of_birth", "birth_datetime", "race_concept_id", "ethnicity_concept_id",
    "location_id", "provider_id", "care_site_id", "person_source_value",
    "gender_source_value", "gender_source_concept_id", "race_source_value",
    "race_source_concept_id", "ethnicity_source_value", "ethnicity_source_concept_id",
    "birth_date",
]


def build_condition_occurrence(profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in profiles.iterrows():
        random.seed(SEED + int(p.person_id) + 2000)
        icd_code, icd_desc = random.choice(ICD10_BREAST)
        dx_date: date = p._dx_date
        rows.append({
            "condition_occurrence_id":      int(p.person_id),
            "person_id":                    int(p.person_id),
            "condition_concept_id":         COND_BREAST_CANCER,
            "condition_start_date":         dx_date,
            "condition_start_datetime":     datetime.combine(dx_date, datetime.min.time()).replace(hour=9),
            "condition_end_date":           None,
            "condition_end_datetime":       None,
            "condition_type_concept_id":    COND_TYPE_EHR,
            "condition_status_concept_id":  COND_STATUS_ACTIVE,
            "stop_reason":                  None,
            "provider_id":                  None,
            "visit_occurrence_id":          None,
            "visit_detail_id":              None,
            "condition_source_value":       "Malignant neoplasm of breast",
            "condition_source_concept_id":  COND_BREAST_CANCER,
            "condition_status_source_value": "Active",
            "condition_source_name":        f"{icd_code} {icd_desc}",
        })
    return pd.DataFrame(rows)


def build_measurement(profiles: pd.DataFrame) -> pd.DataFrame:
    """ER, PR, HER2 measurements for both-agree + structured-only patients only."""
    rows = []
    mid = 1
    biomarker_defs = [
        (MEAS_ER,   "Estrogen receptor",   "_er"),
        (MEAS_PR,   "Progesterone receptor", "_pr"),
        (MEAS_HER2, "HER2/neu",            "_her2"),
    ]
    val_map = {
        "Positive":  (VAL_POSITIVE, "Positive"),
        "Negative":  (VAL_NEGATIVE, "Negative"),
        "Equivocal": (VAL_EQUIVOCAL, "Equivocal"),
    }

    for _, p in profiles.iterrows():
        if p._biomarker_group == "notes-only":
            continue  # No measurements for this group

        random.seed(SEED + int(p.person_id) + 3000)
        dx_date: date = p._dx_date
        meas_offset = random.randint(1, 14)
        meas_date = dx_date + timedelta(days=meas_offset)
        meas_hour = random.randint(8, 17)

        for concept_id, source_val, profile_col in biomarker_defs:
            status = str(p[profile_col])
            val_concept, val_source = val_map.get(status, (VAL_EQUIVOCAL, status))
            rows.append({
                "measurement_id":              mid,
                "person_id":                   int(p.person_id),
                "measurement_concept_id":      concept_id,
                "measurement_date":            meas_date,
                "measurement_datetime":        datetime.combine(meas_date, datetime.min.time()).replace(hour=meas_hour),
                "measurement_time":            f"{meas_hour:02d}:00",
                "measurement_type_concept_id": MEAS_TYPE_LAB,
                "operator_concept_id":         None,
                "value_as_number":             None,
                "value_as_concept_id":         val_concept,
                "unit_concept_id":             None,
                "range_low":                   None,
                "range_high":                  None,
                "provider_id":                 None,
                "visit_occurrence_id":         None,
                "visit_detail_id":             None,
                "measurement_source_value":    source_val,
                "measurement_source_concept_id": concept_id,
                "unit_source_value":           None,
                "unit_source_concept_id":      None,
                "value_source_value":          val_source,
                "measurement_event_id":        None,
                "meas_event_field_concept_id": None,
            })
            mid += 1
    return pd.DataFrame(rows)


def build_observation(profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    oid = 1
    for _, p in profiles.iterrows():
        random.seed(SEED + int(p.person_id) + 4000)
        dx_date: date = p._dx_date
        obs_date = dx_date + timedelta(days=random.randint(0, 7))
        age = int(p._age_at_dx)
        is_post: bool = bool(p._is_postmenopausal)

        # Menopausal status for patients age >= 45
        if age >= 45:
            # Determine actual status
            if is_post:
                val_concept = VAL_POSTMENOPAUSAL
                val_str = "Postmenopausal"
            else:
                val_concept = VAL_PREMENOPAUSAL
                val_str = "Premenopausal"

            rows.append({
                "observation_id":              oid,
                "person_id":                   int(p.person_id),
                "observation_concept_id":      OBS_MENOPAUSAL,
                "observation_date":            obs_date,
                "observation_datetime":        datetime.combine(obs_date, datetime.min.time()).replace(hour=9),
                "observation_type_concept_id": OBS_TYPE_EHR,
                "value_as_number":             None,
                "value_as_string":             val_str,
                "value_as_concept_id":         val_concept,
                "qualifier_concept_id":        None,
                "unit_concept_id":             None,
                "provider_id":                 None,
                "visit_occurrence_id":         None,
                "visit_detail_id":             None,
                "observation_source_value":    "Menopausal status",
                "observation_source_concept_id": OBS_MENOPAUSAL,
                "unit_source_value":           None,
                "qualifier_source_value":      None,
                "value_source_value":          val_str,
                "observation_event_id":        None,
                "obs_event_field_concept_id":  None,
            })
            oid += 1

        # ECOG for ~60% of patients
        if random.random() < 0.60:
            ecog_val = 0.0 if random.random() < 0.80 else 1.0
            ecog_str = "ECOG 0 — Fully active" if ecog_val == 0.0 else "ECOG 1 — Restricted in strenuous activity"
            rows.append({
                "observation_id":              oid,
                "person_id":                   int(p.person_id),
                "observation_concept_id":      OBS_ECOG,
                "observation_date":            obs_date,
                "observation_datetime":        datetime.combine(obs_date, datetime.min.time()).replace(hour=10),
                "observation_type_concept_id": OBS_TYPE_EHR,
                "value_as_number":             ecog_val,
                "value_as_string":             ecog_str,
                "value_as_concept_id":         None,
                "qualifier_concept_id":        None,
                "unit_concept_id":             None,
                "provider_id":                 None,
                "visit_occurrence_id":         None,
                "visit_detail_id":             None,
                "observation_source_value":    "ECOG performance status",
                "observation_source_concept_id": OBS_ECOG,
                "unit_source_value":           None,
                "qualifier_source_value":      None,
                "value_source_value":          ecog_str,
                "observation_event_id":        None,
                "obs_event_field_concept_id":  None,
            })
            oid += 1

        # AJCC stage — every patient gets one row.
        # Uses a completely separate seed (+ 9000) so existing menopausal /
        # ECOG draws (seeded at + 4000) are not touched at all.
        random.seed(SEED + int(p.person_id) + 9000)
        roll = random.random()
        stage_str = next(s for threshold, s in STAGE_CDF if roll < threshold)
        stage_concept = STAGE_CONCEPTS[stage_str]
        rows.append({
            "observation_id":              oid,
            "person_id":                   int(p.person_id),
            "observation_concept_id":      OBS_AJCC_STAGE,
            "observation_date":            obs_date,
            "observation_datetime":        datetime.combine(obs_date, datetime.min.time()).replace(hour=11),
            "observation_type_concept_id": OBS_TYPE_EHR,
            "value_as_number":             None,
            "value_as_string":             stage_str,
            "value_as_concept_id":         stage_concept,
            "qualifier_concept_id":        None,
            "unit_concept_id":             None,
            "provider_id":                 None,
            "visit_occurrence_id":         None,
            "visit_detail_id":             None,
            "observation_source_value":    "AJCC stage",
            "observation_source_concept_id": OBS_AJCC_STAGE,
            "unit_source_value":           None,
            "qualifier_source_value":      None,
            "value_source_value":          stage_str,
            "observation_event_id":        None,
            "obs_event_field_concept_id":  None,
        })
        oid += 1

    return pd.DataFrame(rows)


def build_drug_exposure(profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    did = 1

    def _drug_row(did_val, pid, concept_id, source_val, start_date,
                  days_supply, route="Intravenous", dose_unit="mg"):
        end_date = start_date + timedelta(days=days_supply)
        return {
            "drug_exposure_id":             did_val,
            "person_id":                    pid,
            "drug_concept_id":              concept_id,
            "drug_exposure_start_date":     start_date,
            "drug_exposure_start_datetime": datetime.combine(start_date, datetime.min.time()).replace(hour=9),
            "drug_exposure_end_date":       end_date,
            "drug_exposure_end_datetime":   datetime.combine(end_date, datetime.min.time()).replace(hour=9),
            "verbatim_end_date":            end_date,
            "drug_type_concept_id":         DRUG_TYPE_EHR,
            "stop_reason":                  None,
            "refills":                      None,
            "quantity":                     None,
            "days_supply":                  days_supply,
            "sig":                          None,
            "route_concept_id":             None,
            "lot_number":                   None,
            "provider_id":                  None,
            "visit_occurrence_id":          None,
            "visit_detail_id":              None,
            "drug_source_value":            source_val,
            "drug_source_concept_id":       concept_id,
            "route_source_value":           route,
            "dose_unit_source_value":       dose_unit,
        }

    for _, p in profiles.iterrows():
        random.seed(SEED + int(p.person_id) + 5000)
        pid = int(p.person_id)
        dx_date: date = p._dx_date

        # ── Trial A ineligible (21–30): mandatory anti-HER2 ───────────────
        if p._has_anti_her2:
            anti_her2_start = dx_date + timedelta(days=random.randint(14, 45))
            # Trastuzumab always; pertuzumab 60% of the time
            rows.append(_drug_row(did, pid, DRUG_TRASTUZUMAB, "Trastuzumab",
                                  anti_her2_start, 21, "Intravenous", "mg"))
            did += 1
            if random.random() < 0.60:
                rows.append(_drug_row(did, pid, DRUG_PERTUZUMAB, "Pertuzumab",
                                      anti_her2_start, 21, "Intravenous", "mg"))
                did += 1

        # ── ER+ patients: 40% receive endocrine therapy ────────────────────
        if str(p._er) == "Positive" and random.random() < 0.40:
            endo_start = dx_date + timedelta(days=random.randint(30, 90))
            drug_id, drug_name, route = (
                (DRUG_LETROZOLE, "Letrozole", "Oral")
                if bool(p._is_postmenopausal)
                else (DRUG_TAMOXIFEN, "Tamoxifen", "Oral")
            )
            rows.append(_drug_row(did, pid, drug_id, drug_name,
                                  endo_start, 30, route, "mg"))
            did += 1

        # ── General chemo: 35% of all patients (excluding already-treated) ─
        if random.random() < 0.35:
            chemo_start = dx_date + timedelta(days=random.randint(30, 60))
            # AC (doxorubicin + cyclophosphamide) same date
            rows.append(_drug_row(did, pid, DRUG_DOXORUBICIN, "Doxorubicin",
                                  chemo_start, 21, "Intravenous", "mg"))
            did += 1
            rows.append(_drug_row(did, pid, DRUG_CYCLOPHOSPHAMIDE, "Cyclophosphamide",
                                  chemo_start, 21, "Intravenous", "mg"))
            did += 1
            # Paclitaxel starts after AC
            taxol_start = chemo_start + timedelta(days=21)
            rows.append(_drug_row(did, pid, DRUG_PACLITAXEL, "Paclitaxel",
                                  taxol_start, 21, "Intravenous", "mg"))
            did += 1

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def build_note(profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    nid = 1
    for _, p in profiles.iterrows():
        random.seed(SEED + int(p.person_id) + 6000)
        pid = int(p.person_id)
        bg = str(p._biomarker_group)
        dx_date: date = p._dx_date

        if bg in ("both-agree", "notes-only"):
            # Full pathology note WITH biomarker mention
            meas_offset = random.randint(1, 14)
            note_date = dx_date + timedelta(days=meas_offset + random.randint(-1, 3))
            if note_date <= dx_date:
                note_date = dx_date + timedelta(days=1)

            note_text = generate_pathology_note(
                pid=pid,
                er=str(p._er),
                pr=str(p._pr),
                her2=str(p._her2),
                dx_date=note_date,
                patient_name=str(p._name),
            )
            title = random.choice([
                "Surgical Pathology Report",
                "Core Needle Biopsy — Pathology Report",
                "Pathology Consultation Report",
            ])
            note_type = NOTE_TYPE_PATH
            note_class = NOTE_CLASS_PATH
            source_val = "PATHOLOGY_REPORT"

        elif bg == "structured-only":
            # 50% no note at all; 50% generic progress note without biomarkers
            if random.random() < 0.50:
                continue  # No note for this patient
            note_date = dx_date + timedelta(days=random.randint(30, 120))
            note_text = generate_generic_note(pid, dx_date)
            title = "Oncology Progress Note"
            note_type = NOTE_TYPE_PATH
            note_class = NOTE_CLASS_PROGRESS
            source_val = "PROGRESS_NOTE"

        else:
            continue

        rows.append({
            "note_id":                    nid,
            "person_id":                  pid,
            "note_date":                  note_date,
            "note_datetime":              datetime.combine(note_date, datetime.min.time()).replace(hour=14),
            "note_type_concept_id":       note_type,
            "note_class_concept_id":      note_class,
            "note_title":                 title,
            "note_text":                  note_text,
            "encoding_concept_id":        NOTE_ENCODING_UTF8,
            "language_concept_id":        NOTE_LANG_ENGLISH,
            "provider_id":                None,
            "visit_occurrence_id":        None,
            "visit_detail_id":            None,
            "note_source_value":          source_val,
            "note_event_id":              None,
            "note_event_field_concept_id": None,
        })
        nid += 1

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# FULL FH SCHEMAS — every column, exact types, exact nullability.
# Parquet files written by write_table() match these schemas 1-for-1, which
# is required both to avoid the "Cannot find column index" Delta read error
# and to satisfy the synth→real toggle (real curated_omop.omop tables have
# this exact shape).
# ─────────────────────────────────────────────────────────────────────────────

TABLE_SCHEMAS: dict[str, StructType] = {

    "person": StructType([
        StructField("person_id",                   LongType(),      False),
        StructField("gender_concept_id",            IntegerType(),   False),
        StructField("year_of_birth",                IntegerType(),   False),
        StructField("month_of_birth",               IntegerType(),   True),
        StructField("day_of_birth",                 IntegerType(),   True),
        StructField("birth_datetime",               TimestampType(), True),
        StructField("race_concept_id",              IntegerType(),   False),
        StructField("ethnicity_concept_id",         IntegerType(),   False),
        StructField("location_id",                  LongType(),      True),
        StructField("provider_id",                  LongType(),      True),
        StructField("care_site_id",                 LongType(),      True),
        StructField("person_source_value",          StringType(),    True),
        StructField("gender_source_value",          StringType(),    True),
        StructField("gender_source_concept_id",     IntegerType(),   True),
        StructField("race_source_value",            StringType(),    True),
        StructField("race_source_concept_id",       IntegerType(),   True),
        StructField("ethnicity_source_value",       StringType(),    True),
        StructField("ethnicity_source_concept_id",  IntegerType(),   True),
        StructField("birth_date",                   DateType(),      True),
    ]),

    "condition_occurrence": StructType([
        StructField("condition_occurrence_id",       LongType(),      False),
        StructField("person_id",                     LongType(),      False),
        StructField("condition_concept_id",          IntegerType(),   False),
        StructField("condition_start_date",          DateType(),      False),
        StructField("condition_start_datetime",      TimestampType(), True),
        StructField("condition_end_date",            DateType(),      True),
        StructField("condition_end_datetime",        TimestampType(), True),
        StructField("condition_type_concept_id",     IntegerType(),   False),
        StructField("condition_status_concept_id",   IntegerType(),   True),
        StructField("stop_reason",                   StringType(),    True),
        StructField("provider_id",                   LongType(),      True),
        StructField("visit_occurrence_id",           LongType(),      True),
        StructField("visit_detail_id",               LongType(),      True),
        StructField("condition_source_value",        StringType(),    True),
        StructField("condition_source_concept_id",   IntegerType(),   True),
        StructField("condition_status_source_value", StringType(),    True),
        StructField("condition_source_name",         StringType(),    True),
    ]),

    "measurement": StructType([
        StructField("measurement_id",                LongType(),      False),
        StructField("person_id",                     LongType(),      True),
        StructField("measurement_concept_id",        IntegerType(),   True),
        StructField("measurement_date",              DateType(),      True),
        StructField("measurement_datetime",          TimestampType(), True),
        StructField("measurement_time",              StringType(),    True),
        StructField("measurement_type_concept_id",   IntegerType(),   True),
        StructField("operator_concept_id",           IntegerType(),   True),
        StructField("value_as_number",               FloatType(),     True),
        StructField("value_as_concept_id",           IntegerType(),   True),
        StructField("unit_concept_id",               IntegerType(),   True),
        StructField("range_low",                     FloatType(),     True),
        StructField("range_high",                    FloatType(),     True),
        StructField("provider_id",                   LongType(),      True),
        StructField("visit_occurrence_id",           LongType(),      True),
        StructField("visit_detail_id",               LongType(),      True),
        StructField("measurement_source_value",      StringType(),    True),
        StructField("measurement_source_concept_id", IntegerType(),   True),
        StructField("unit_source_value",             StringType(),    True),
        StructField("unit_source_concept_id",        IntegerType(),   True),
        StructField("value_source_value",            StringType(),    True),
        StructField("measurement_event_id",          IntegerType(),   True),
        StructField("meas_event_field_concept_id",   IntegerType(),   True),
    ]),

    "observation": StructType([
        StructField("observation_id",                LongType(),      False),
        StructField("person_id",                     LongType(),      True),
        StructField("observation_concept_id",        IntegerType(),   True),
        StructField("observation_date",              DateType(),      True),
        StructField("observation_datetime",          TimestampType(), True),
        StructField("observation_type_concept_id",   IntegerType(),   True),
        StructField("value_as_number",               FloatType(),     True),
        StructField("value_as_string",               StringType(),    True),
        StructField("value_as_concept_id",           IntegerType(),   True),
        StructField("qualifier_concept_id",          IntegerType(),   True),
        StructField("unit_concept_id",               IntegerType(),   True),
        StructField("provider_id",                   LongType(),      True),
        StructField("visit_occurrence_id",           LongType(),      True),
        StructField("visit_detail_id",               LongType(),      True),
        StructField("observation_source_value",      StringType(),    True),
        StructField("observation_source_concept_id", IntegerType(),   True),
        StructField("unit_source_value",             StringType(),    True),
        StructField("qualifier_source_value",        StringType(),    True),
        StructField("value_source_value",            StringType(),    True),
        StructField("observation_event_id",          IntegerType(),   True),
        StructField("obs_event_field_concept_id",    IntegerType(),   True),
    ]),

    "drug_exposure": StructType([
        StructField("drug_exposure_id",             LongType(),      False),
        StructField("person_id",                    LongType(),      True),
        StructField("drug_concept_id",              IntegerType(),   True),
        StructField("drug_exposure_start_date",     DateType(),      True),
        StructField("drug_exposure_start_datetime", TimestampType(), True),
        StructField("drug_exposure_end_date",       DateType(),      True),
        StructField("drug_exposure_end_datetime",   TimestampType(), True),
        StructField("verbatim_end_date",            DateType(),      True),
        StructField("drug_type_concept_id",         IntegerType(),   True),
        StructField("stop_reason",                  StringType(),    True),
        StructField("refills",                      IntegerType(),   True),
        StructField("quantity",                     FloatType(),     True),
        StructField("days_supply",                  IntegerType(),   True),
        StructField("sig",                          StringType(),    True),
        StructField("route_concept_id",             IntegerType(),   True),
        StructField("lot_number",                   StringType(),    True),
        StructField("provider_id",                  LongType(),      True),
        StructField("visit_occurrence_id",          LongType(),      True),
        StructField("visit_detail_id",              LongType(),      True),
        StructField("drug_source_value",            StringType(),    True),
        StructField("drug_source_concept_id",       IntegerType(),   True),
        StructField("route_source_value",           StringType(),    True),
        StructField("dose_unit_source_value",       StringType(),    True),
    ]),

    "note": StructType([
        StructField("note_id",                      LongType(),      False),
        StructField("person_id",                    LongType(),      True),
        StructField("note_date",                    DateType(),      True),
        StructField("note_datetime",                TimestampType(), True),
        StructField("note_type_concept_id",         IntegerType(),   True),
        StructField("note_class_concept_id",        IntegerType(),   True),
        StructField("note_title",                   StringType(),    True),
        StructField("note_text",                    StringType(),    True),
        StructField("encoding_concept_id",          IntegerType(),   True),
        StructField("language_concept_id",          IntegerType(),   True),
        StructField("provider_id",                  LongType(),      True),
        StructField("visit_occurrence_id",          LongType(),      True),
        StructField("visit_detail_id",              LongType(),      True),
        StructField("note_source_value",            StringType(),    True),
        StructField("note_event_id",                LongType(),      True),
        StructField("note_event_field_concept_id",  IntegerType(),   True),
    ]),
}


# ─────────────────────────────────────────────────────────────────────────────
# WRITE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def write_table(df: pd.DataFrame, table_name: str) -> None:
    """Drop the target table, then write with the exact full FH schema.

    Using an explicit StructType + overwriteSchema=true guarantees that the
    parquet column set exactly equals the declared Delta schema, fixing the
    "Cannot find column index for attribute" read error caused by previous
    mergeSchema runs that left stale column declarations.
    """
    if df.empty:
        print(f"  ⚠  {table_name}: empty, skipping")
        return

    schema = TABLE_SCHEMAS[table_name]
    full   = f"{CATALOG}.{SCHEMA}.{table_name}"

    # Ensure every schema column is present in the DataFrame (fill gaps with None)
    for field in schema.fields:
        if field.name not in df.columns:
            df[field.name] = None

    # Reorder columns to match schema exactly
    df = df[[f.name for f in schema.fields]]

    # Drop first so overwriteSchema never hits a "schema mismatch" guard
    spark.sql(f"DROP TABLE IF EXISTS {full}")

    sdf = spark.createDataFrame(df, schema=schema)
    sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(full)
    print(f"  ✓  {full}: {len(df):,} rows")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n🏥  Fred Hutch OMOP Synthetic Data Generator")
    print(f"    Target: {CATALOG}.{SCHEMA}\n")

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

    print("Building patient profiles...")
    profiles = make_patient_profiles()
    print(f"  → {len(profiles)} patients across {profiles._segment.nunique()} segments\n")

    print("Writing tables:")
    write_table(profiles[PERSON_COLS],          "person")
    write_table(build_condition_occurrence(profiles), "condition_occurrence")
    write_table(build_measurement(profiles),    "measurement")
    write_table(build_observation(profiles),    "observation")
    write_table(build_drug_exposure(profiles),  "drug_exposure")
    write_table(build_note(profiles),           "note")

    print("\n─────────────────────────────────────────────")
    print("Quick validation:")
    for tbl in ["person", "condition_occurrence", "measurement",
                "observation", "drug_exposure", "note"]:
        cnt = spark.sql(f"SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.{tbl}").collect()[0].n
        print(f"  {tbl:30s}  {cnt:>6,} rows")

    # Planted cohort spot-checks
    print("\nPlanted cohort checks:")
    a_elig = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.measurement
        WHERE person_id BETWEEN 1 AND 20
          AND measurement_source_value = 'HER2/neu'
          AND value_source_value = 'Positive'
    """).collect()[0].n
    print(f"  Trial A eligible — HER2+ measurements (expect 20):     {a_elig}")

    a_drug = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.drug_exposure
        WHERE person_id BETWEEN 1 AND 20
          AND drug_source_value IN ('Trastuzumab','Pertuzumab')
    """).collect()[0].n
    print(f"  Trial A eligible — anti-HER2 drug rows (expect 0):     {a_drug}")

    b_er = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.measurement
        WHERE person_id BETWEEN 31 AND 50
          AND measurement_source_value = 'Estrogen receptor'
          AND value_source_value = 'Positive'
    """).collect()[0].n
    print(f"  Trial B eligible — ER+ measurements (expect 20):       {b_er}")

    b_her2 = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.measurement
        WHERE person_id BETWEEN 31 AND 50
          AND measurement_source_value = 'HER2/neu'
          AND value_source_value = 'Negative'
    """).collect()[0].n
    print(f"  Trial B eligible — HER2- measurements (expect 20):     {b_her2}")

    b_post = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.observation
        WHERE person_id BETWEEN 31 AND 50
          AND observation_source_value = 'Menopausal status'
          AND value_source_value = 'Postmenopausal'
    """).collect()[0].n
    print(f"  Trial B eligible — postmenopausal obs (expect 20):     {b_post}")

    no_meas = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {CATALOG}.{SCHEMA}.measurement
        WHERE person_id BETWEEN 181 AND 240
    """).collect()[0].n
    print(f"  Notes-only — measurement rows (expect 0):              {no_meas}")

    print("\nAJCC stage distribution:")
    stage_dist = spark.sql(f"""
        SELECT value_source_value AS stage, COUNT(*) AS n
        FROM {CATALOG}.{SCHEMA}.observation
        WHERE observation_source_value = 'AJCC stage'
        GROUP BY value_source_value
        ORDER BY value_source_value
    """).collect()
    total_staged = sum(r.n for r in stage_dist)
    for r in stage_dist:
        pct = 100 * r.n / total_staged if total_staged else 0
        print(f"  {r.stage:<12s}  {r.n:>3}  ({pct:.0f}%)")

    print("\nSELECT * LIMIT 1 smoke-test (schema read check):")
    for tbl in ["person", "condition_occurrence", "measurement",
                "observation", "drug_exposure", "note"]:
        try:
            spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.{tbl} LIMIT 1").collect()
            print(f"  ✓  {tbl}")
        except Exception as exc:
            print(f"  ✗  {tbl}: {exc}")

    print("\n✅  Generation complete.\n")


if __name__ == "__main__":
    main()
