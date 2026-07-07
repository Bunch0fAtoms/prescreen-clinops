# 🔎 Data discovery — get to know the 6 OMOP tables before you build

**Goal: understand the data before you build on it.** This is a whole-room session, and everyone
is here: Data Engineering, Applied AI, Governance, and Admin all start on the same six tables.
Spend the first part of the session interrogating the foundation so the build that follows is
grounded in what the data actually says, not in assumptions. It is a genuinely fun first hour,
because the data starts answering your questions right away.

You have two ways to explore, and using both is the point:

1. **Genie Code** — ask questions in plain language and let it write and run the SQL. Fast,
   iterative, good for "what is in here and how does it join."
2. **A Genie space** — a saved, self-serve place where anyone on the team, including a clinical
   researcher who does not write SQL, can ask questions about the data in plain English. See
   `genie/genie_space.md` to stand one up over these six tables.

**This session doubles as Governance's requirements-gathering.** As the room asks real questions of
the data, the Governance group watches what comes up. Which columns hold patient identifiers? Which
questions imply that one group should see more than another? Those answers become the control set
Governance applies right afterward, so the governance work is grounded in how the room actually uses
the data. Admin is here too, getting a feel for the tables that the cost and usage story sits on
top of.

The six tables are the Observational Medical Outcomes Partnership (OMOP) Common Data Model
(CDM), a shared standard for clinical data: `person`, `condition_occurrence`, `measurement`,
`observation`, `drug_exposure`, and `note`. They hold 300 synthetic breast-cancer patients.
They are read-only for both groups. Nothing you do in discovery changes them.

---

## Genie Code — starter discovery prompts

Paste one at a time. Change them, combine them, or ask your own. The aim is a shared mental
model of the foundation, not a checklist.

### 1. Map the foundation
> **"Profile the six OMOP tables in my source schema. For each one give me the row count, the
> columns and types, and two sample rows. Then draw the join path: how does a person link to
> their conditions, measurements, observations, drug exposures, and notes?"**

*What you learn:* the shape of the data and the keys that tie it together (`person_id` is the
spine). Counts you should see: person 300, condition_occurrence 300, measurement 720,
observation 720, drug_exposure 383, note 265.

### 2. Find the clinical signal
> **"In `measurement` and `observation`, what biomarker and staging values are recorded, and how
> are they spelled in the `*_source_value` columns? Show me the distinct values and how many
> patients have each. I care about ER, PR, HER2, ECOG, and AJCC stage."**

*What you learn:* which biomarkers live in structured fields, and the exact strings you will
filter on later. The `*_source_value` columns are human-readable, so you can screen in plain
language without a vocabulary lookup.

### 3. Spot the gap that motivates the build
> **"How many patients have a HER2 result in the structured `measurement` table, and how many do
> not? For the patients with no structured HER2 result, do they have a pathology note in the
> `note` table?"**

*What you learn:* a real gap. About 60 patients carry their biomarker status only in the free
text of a pathology note, not in a structured field. Structured filters alone miss them. That
gap is exactly what the Applied AI group closes with language models, and what the Data
Engineering group makes sure never silently drops rows.

### 4. Sanity-check consistency
> **"Pick five patients who have both a structured HER2 measurement and a pathology note. Show me
> the structured value next to the note text. Do they agree?"**

*What you learn:* whether the structured data and the notes tell the same story. They should.
This builds trust in the foundation before you extend it.

### 5. Spot what needs protecting (Governance lens)
> **"Across the six tables, which columns hold something that identifies a patient, like a name,
> a date of birth, a record number, or free-text notes that could name someone? List them by
> table, and flag the ones a general researcher should not see in the clear."**

*What you learn:* a first draft of the control set. This is the Governance group's starting point.
The identifiers you list here are the columns you will tag, mask, and row-filter next, so the
governance you apply reflects what the room actually saw in the data.

---

## Where each group goes next

- **Data Engineering** moves to `../kits/data-eng-session-starter-kit/` — harden the ingest of
  this data and bring in the net-new trials feed that is landing in the `trial_landing` Volume.
- **Applied AI** moves to `../kits/ml-session-starter-kit/` — build the features, recover the
  notes-only patients with language models, and produce the trial pre-screen and a Genie space
  clinical researchers can question.
- **Governance** moves to `../kits/governance-session-starter-kit/` — turn the requirements it
  just captured into real tags, column masks, and row filters on the shared tables, then re-apply
  them to what Data Engineering and Applied AI build.
- **Admin** moves to `../kits/admin-session-starter-kit/` — answer cost and usage questions and set
  budget alerts in plain language with Genie One, over the workspace billing system tables.

The discovery Genie space you build here is worth keeping. It becomes the front door a
researcher uses to ask about the data, and it is a natural thing to show in your final
presentation.
