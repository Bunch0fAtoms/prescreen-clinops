# Data Engineering Session - Completed Reference Notebooks

These are the **completed reference notebooks** for the Data Engineering session, showing the full solutions for tomorrow's presentation.

## Primary Build: Notebook 05 (Trials Catalog Ingest)

The main DE build focuses on **notebook 05**, which demonstrates:

### Core Capabilities Built
1. **Incremental Ingestion with Auto Loader**
   - Uses `cloudFiles` format with checkpoint tracking
   - Picks up only new files on each run
   - Handles continuous file arrival from live feed

2. **Schema-Stable VARIANT Bronze**
   - Single `VARIANT` column absorbs any JSON structure
   - Schema evolution handled automatically (e.g., `min_ecog` field addition)
   - No pipeline breaks on new fields

3. **Bad Data Quarantine**
   - Routes malformed/invalid records to `quarantine_trial_criteria`
   - Tags each bad row with clear reason:
     - `unparseable`: Malformed JSON
     - `missing_trial_id`: No primary key
     - `bad_type_age`: Wrong data type
   - Pipeline never fails, ops gets clear visibility

4. **Latest-Wins Deduplication**
   - Uses `ROW_NUMBER()` window function
   - Keeps newest version per `trial_id` based on `load_ts`
   - Clean `silver_trial_criteria` table for downstream joins

### Key Success Metrics
- ✅ Bronze ingests incrementally (checkpoint-based)
- ✅ Silver has clean, deduplicated trials
- ✅ Quarantine captures all bad records with reasons
- ✅ Schema evolution requires no code changes
- ✅ Re-running picks up only new files

## Workshop Flow

### Live Demo Sequence (Notebook 05)
1. **Start with clean stage running** (`--stage clean`)
   - Show files landing in Volume
   - Run cells 1-3 to build bronze and silver
   - Point out incremental behavior

2. **Re-run to show incremental pickup**
   - More files have landed
   - Bronze count increases
   - New trials appear in silver

3. **Show schema evolution**
   - Trial A now has `min_ecog` field
   - No code changes needed, VARIANT handles it

4. **Release dirty stage** (`--stage dirty`)
   - Bad records land
   - Run cell 4 (quarantine logic)
   - Show separation of good/bad data

## Contract with Applied AI Team

The `silver_trial_criteria` table is the **key interface** between Data Engineering and Applied AI:

- **DE provides**: Clean, current trial eligibility criteria
- **ML consumes**: Joins against this for patient pre-screening
- **Adding trials**: Just drop a file, no code changes
- **Schema flexible**: New criteria flow through automatically

## Presentation Notes

### Key Messages
1. **Incremental is essential** - Re-processing everything doesn't scale
2. **VARIANT prevents breaks** - Schema changes are inevitable
3. **Quarantine over failure** - Bad data shouldn't stop the pipeline
4. **Config over code** - Adding trials is a data operation, not development

### Common Questions & Answers

**Q: Why VARIANT instead of inferring schema?**
A: VARIANT is stable. Inferred schemas break when new fields appear or types conflict.

**Q: How do you monitor quarantined records?**
A: Query `quarantine_trial_criteria` grouped by reason. Set alerts on row counts.

**Q: What if the feed stops?**
A: Auto Loader waits. When files resume landing, it picks up where it left off.

**Q: Can you replay from the beginning?**
A: Yes, delete the checkpoint and re-run. Bronze will rebuild from all files.

## File Structure

```
completed_notebooks/
├── _config.py                   # Shared configuration
├── 00_START_HERE.py             # Setup and overview
├── 05_trials_catalog_ingest.py  # MAIN BUILD (focus here)
└── README.md                     # This file
```

## Running the Notebooks

1. Open `00_START_HERE.py` first
2. Set your catalog/schema in the widgets
3. Run the foundation check
4. Open `05_trials_catalog_ingest.py`
5. Run cells in order, observing incremental behavior

## Technical Implementation Details

### Auto Loader Configuration
```python
spark.readStream.format("cloudFiles")
  .option("cloudFiles.format", "text")
  .option("cloudFiles.schemaLocation", SCHEMA_LOC)
  .load(LANDING_PATH)
```

### VARIANT Parsing
```python
.withColumn("trial_raw", F.expr("try_parse_json(value)"))
```

### Quarantine Logic
```sql
CASE
  WHEN trial_raw IS NULL THEN 'unparseable'
  WHEN trial_raw:trial_id::string IS NULL THEN 'missing_trial_id'
  WHEN trial_raw:eligibility.min_age_years IS NOT NULL
       AND trial_raw:eligibility.min_age_years::int IS NULL THEN 'bad_type_age'
END AS quarantine_reason
```

### Latest-Wins Window
```sql
ROW_NUMBER() OVER (
  PARTITION BY trial_raw:trial_id::string
  ORDER BY trial_raw:load_ts::timestamp DESC
) AS rn
```

This is production-ready code that handles real-world data challenges.