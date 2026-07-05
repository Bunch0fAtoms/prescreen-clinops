-- PRE-BUILT — deep-clone the 6 OMOP tables into the isolated governance schema.
-- Driven by the setup_clone_job parameters (source_* and client_*). DEEP CLONE copies data + schema
-- so the governance schema is fully independent of the source — apply masks/filters here safely.
CREATE SCHEMA IF NOT EXISTS IDENTIFIER(:client_catalog || '.' || :client_schema);

CREATE OR REPLACE TABLE IDENTIFIER(:client_catalog || '.' || :client_schema || '.person')
  DEEP CLONE IDENTIFIER(:source_catalog || '.' || :source_schema || '.person');

CREATE OR REPLACE TABLE IDENTIFIER(:client_catalog || '.' || :client_schema || '.condition_occurrence')
  DEEP CLONE IDENTIFIER(:source_catalog || '.' || :source_schema || '.condition_occurrence');

CREATE OR REPLACE TABLE IDENTIFIER(:client_catalog || '.' || :client_schema || '.measurement')
  DEEP CLONE IDENTIFIER(:source_catalog || '.' || :source_schema || '.measurement');

CREATE OR REPLACE TABLE IDENTIFIER(:client_catalog || '.' || :client_schema || '.observation')
  DEEP CLONE IDENTIFIER(:source_catalog || '.' || :source_schema || '.observation');

CREATE OR REPLACE TABLE IDENTIFIER(:client_catalog || '.' || :client_schema || '.drug_exposure')
  DEEP CLONE IDENTIFIER(:source_catalog || '.' || :source_schema || '.drug_exposure');

CREATE OR REPLACE TABLE IDENTIFIER(:client_catalog || '.' || :client_schema || '.note')
  DEEP CLONE IDENTIFIER(:source_catalog || '.' || :source_schema || '.note');
