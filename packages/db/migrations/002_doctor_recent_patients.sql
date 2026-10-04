\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS rag.doctor_recent_patients (
    doctor_hash char(64) NOT NULL,
    patient_id text NOT NULL,
    last_selected_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (doctor_hash, patient_id)
);

CREATE INDEX IF NOT EXISTS doctor_recent_patients_order_idx
    ON rag.doctor_recent_patients (doctor_hash, last_selected_at DESC);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON rag.doctor_recent_patients TO :"app_user";
