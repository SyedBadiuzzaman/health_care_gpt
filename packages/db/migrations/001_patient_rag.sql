\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE IF NOT EXISTS rag.ingestion_runs (
    run_id uuid PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
    embedding_model text NOT NULL,
    embedding_revision text NOT NULL,
    chunk_version integer NOT NULL,
    source_rows integer,
    chunk_count integer,
    reused_embedding_count integer,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_code text
);

CREATE TABLE IF NOT EXISTS rag.patient_chunks (
    chunk_id text PRIMARY KEY,
    patient_id text NOT NULL,
    admission_ids text[] NOT NULL,
    domain text NOT NULL CHECK (domain IN ('encounter', 'medication', 'microbiology', 'drg')),
    facts jsonb NOT NULL,
    content text NOT NULL,
    content_hash char(64) NOT NULL,
    repeat_count integer NOT NULL CHECK (repeat_count > 0),
    embedding vector(384) NOT NULL,
    embedding_model text NOT NULL,
    embedding_revision text NOT NULL,
    chunk_version integer NOT NULL,
    ingestion_run_id uuid NOT NULL REFERENCES rag.ingestion_runs(run_id),
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    indexed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (patient_id, content_hash, embedding_model, embedding_revision, chunk_version)
);

CREATE TABLE IF NOT EXISTS rag.patient_summaries (
    patient_id text PRIMARY KEY,
    admission_ids text[] NOT NULL,
    source_row_count integer NOT NULL,
    domain_fact_counts jsonb NOT NULL,
    ingestion_run_id uuid NOT NULL REFERENCES rag.ingestion_runs(run_id),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS patient_chunks_patient_idx
    ON rag.patient_chunks (patient_id);
CREATE INDEX IF NOT EXISTS patient_chunks_patient_domain_idx
    ON rag.patient_chunks (patient_id, domain);
CREATE INDEX IF NOT EXISTS patient_chunks_admissions_idx
    ON rag.patient_chunks USING gin (admission_ids);
CREATE INDEX IF NOT EXISTS patient_chunks_search_idx
    ON rag.patient_chunks USING gin (search_vector);
CREATE INDEX IF NOT EXISTS patient_chunks_embedding_idx
    ON rag.patient_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

GRANT USAGE ON SCHEMA rag TO :"app_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO :"app_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA rag
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
