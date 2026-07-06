# 🧞 Discovery Genie space — ask the 6 OMOP tables in plain English

**Goal: give the whole team, including non-SQL users, a place to question the data.** A Genie
space is a saved, self-serve interface where someone types a question in plain English and Genie
answers it with a query and a chart. Standing one up over the six OMOP tables early means a
clinical researcher can interrogate the foundation without waiting on an analyst.

The whole room builds this space together during discovery, and it makes a clean thing to show in
the final presentation. It has a second job too: the questions the room asks here are exactly what
the Governance group listens to when it decides what to protect. A question that pulls up patient
identifiers is a signal for a mask; a question one group should not be able to answer is a signal
for a row filter. So the space is both the front door for researchers and the evidence base for
governance.

## What to put in the space

Point the space at the six read-only foundation tables in your schema:

- `person`, `condition_occurrence`, `measurement`, `observation`, `drug_exposure`, `note`

## Two ways to build it

**A. Genie Code (fastest).** Install the `prompt-to-genie` skill once at the workspace level (see
the top-level `README.md`), open Genie Code, and say:

> **"Create a Genie space over the six OMOP tables in my schema (person, condition_occurrence,
> measurement, observation, drug_exposure, note) so a clinical researcher can ask about patient
> counts, biomarker values, and staging in plain English. Add helpful table and column
> descriptions and a few sample questions."**

**B. The Databricks UI.** New → Genie space, add the six tables, and write short table and column
descriptions so Genie answers well.

## Sample questions to seed the space

Good descriptions plus a few example questions make the space answer reliably from the start:

- "How many patients are there, and what is the age and sex breakdown?"
- "How many patients have a positive HER2 measurement?"
- "How many patients have a pathology note but no structured HER2 result?"
- "What AJCC stages are recorded, and how many patients are at each stage?"
- "Show the most common conditions and drug exposures."
- "Which columns here could identify a specific patient?" (a governance-lens question that helps the
  Governance group see what to protect)

## A note on trust

The data here is synthetic and Unity Catalog scoped, so the space is safe to share and demo. When
Fred Hutch points the same pattern at real curated OMOP data, the governance controls the
Governance group applies (column masks, row filters, lineage, audit) carry straight over, so the
space respects who is allowed to see what.
