# Handoff Notes — Fred Hutch Clinical Trial Pre-Screening

SA notes for the client package. These are things to be aware of during deployment and adaptation.

## 1. Data Generator is a Standalone Databricks Connect Script

`src/data_generation/generate_omop_data.py` runs via Databricks Connect (serverless Spark). It can be run locally during SA development with:

```bash
DATABRICKS_CONFIG_PROFILE=<your-profile> \
  python src/data_generation/generate_omop_data.py <catalog> <schema>
```

The DAB job (`data_generation_job`) passes `client_catalog` and `client_schema` as argv[1]/argv[2] automatically — no changes needed for client deployment.

## 2. Synth Toggle: Pattern B (Early Return)

The synth/real toggle is implemented in the job parameters, not as a DAB `condition_task`. The job always runs when `bundle run data_generation_job` is called.

**Current behavior:** when `run_with_synthetic_data=no`, the client simply doesn't run `bundle run data_generation_job` — there is no automatic gate. The downstream Genie/Genie Code queries read from `source_catalog.source_schema` directly.

**TODO (Pattern A upgrade):** For a cleaner implementation, consider adding a `condition_task` gate to `resources/data_gen_job.yml`:
```yaml
tasks:
  - task_key: gate_synth
    condition_task:
      op: EQUAL_TO
      left: ${var.run_with_synthetic_data}
      right: "yes"
  - task_key: generate_omop_data
    depends_on:
      - task_key: gate_synth
        outcome: "true"
    python_script_task:
      ...
```
This makes `bundle run data_generation_job` a no-op when the client has flipped to real data.

## 3. python_script_task Bundle Schema Warning

`databricks bundle validate` emits:
```
Warning: unknown field: python_script_task
  at resources.jobs.data_generation_job.tasks[0]
  in resources/data_gen_job.yml:12:11
```

This is a bundle YAML schema validation warning — the `python_script_task` field exists in the Jobs API v2.2 (serverless) but the bundle JSON schema validator doesn't yet list it as a known field. The job deploys and runs correctly. No action required.

## 4. IP-Strip Summary

The following SA-specific values were removed from the client package:

| Item | Original | In client package |
|---|---|---|
| SA workspace profile | `<SA build profile>` (redacted) | Stripped (only in `dev:` target, not included in ZIP) |
| SA warehouse ID | `718f1b203cdea5c4` | Replaced with `<your_warehouse_id>` placeholder |
| SA catalog | `<SA build catalog>` (redacted) | Replaced with `<your_catalog>` placeholder |
| SA schema | `demo_clinical_trial_pre_screening_omop` | Replaced with `<your_schema>` placeholder |

## 5. Variable Rename Applied

As part of the handoff, variables were renamed for client clarity:
- `demo_catalog` → `client_catalog`
- `demo_schema` → `client_schema`

This rename was applied across `databricks.yml` and `resources/data_gen_job.yml`. The Python generator script receives catalog/schema as argv parameters (not via variable names), so no change was needed there.

## 6. OMOP Table Names Are Locked

The 6 OMOP CDM table names are standard (`person`, `condition_occurrence`, etc.) and must not be renamed. The synth→real toggle works because real `curated_omop.omop` tables share these exact names. If the client's real OMOP uses different table names, the toggle's `source_catalog`/`source_schema` variables point at the right schema — no table renames needed.
