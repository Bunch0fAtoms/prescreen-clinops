# Trial Feed Stage Control

The `land_trial_feed` task supports staged execution to facilitate the workshop progression. **Each stage runs independently.** Running `--stage dirty` will NOT re-run the clean data first.

## Available Stages

### Stage 1: `clean` (Build & Validate)
```bash
databricks bundle run foundation_setup_job --refresh --python-params="--stage clean --speed 6"
```
- Lands ONLY clean, valid trial records
- Includes Trials A & B baseline, then C, D, E, F
- Demonstrates schema evolution (min_ecog field added)
- Shows latest-wins conflict resolution
- Continues with heartbeat (re-lands with incremented versions)
- **Use this first** to build and validate the pipeline

### Stage 2: `dirty` (Error Handling)
```bash
databricks bundle run foundation_setup_job --refresh --python-params="--stage dirty --speed 6"
```
- Lands ONLY bad records for quarantine testing
- Does NOT re-run clean data
- Includes: missing trial_id, malformed JSON, wrong-type fields
- NO heartbeat (bad data shouldn't repeat)
- **Run this after teams have working pipeline** to test error handling

### Stage 3: `clean_with_c` (Stretch Goal)
```bash
databricks bundle run foundation_setup_job --refresh --python-params="--stage clean_with_c --speed 6"
```
- Lands ONLY Trial C
- For testing "add a trial = drop a file" independently
- Does NOT re-run Trials A & B
- Continues with heartbeat
- **Optional stretch goal** for advanced teams

### Stage 4: `all` (Full Sequence)
```bash
databricks bundle run foundation_setup_job --refresh --python-params="--stage all --speed 6"
```
- Runs all stages in sequence: clean → dirty → clean_with_c
- Full end-to-end test
- Not typically used in workshop (stages run independently instead)

## Workshop Flow

**Recommended sequence:**

1. **Start:** Run `--stage clean` to build working pipeline
   - Teams build Auto Loader → VARIANT bronze → flatten → silver
   - Validate everything works with clean data
   - Let it run with heartbeat while teams build

2. **Cancel** when teams have Build 1 working
   - Stop the heartbeat to prepare for dirty data

3. **Test:** Run `--stage dirty` to release bad records
   - Teams re-run their pipeline
   - Verify quarantine routing works
   - Silver tables stay clean

4. **Stretch:** Run `--stage clean_with_c` for Trial C only
   - Advanced teams test incremental "add a trial"
   - No need to re-process A & B

## Parameters

All stages support these additional parameters:

- `--speed N`: Time acceleration factor (default 1, use 6 for ~5min runs)
- `--heartbeat-seconds N`: Heartbeat interval (default 300)
- `--max-runtime-min N`: Auto-stop after N minutes (default 0 = no limit)
- `--reset`: Clear the Volume before landing (fresh start)

Example with multiple parameters:
```bash
databricks bundle run foundation_setup_job --refresh \
  --python-params="--stage dirty --speed 10 --reset"
```

## Important Notes

- **Stages are mutually exclusive:** Running `--stage dirty` lands ONLY bad records, not clean+dirty
- **The OMOP tables are NOT affected:** Only the `land_trial_feed` task accepts stage parameters
- **Auto Loader sees everything:** Teams' incremental readers pick up whatever has been landed so far
- **Heartbeat behavior:** Runs for `clean` and `clean_with_c`, but NOT for `dirty` (bad data shouldn't repeat)