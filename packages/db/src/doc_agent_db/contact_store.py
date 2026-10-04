"""Preserve repeated patient records in a local SQLite index."""

import hashlib
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from doc_agent_db.contact_schema import CLINICAL_COLUMNS, SOURCE_COLUMNS
from doc_agent_db.contact_source import SourceRow

EMAIL_PATTERN = re.compile(
    r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE
)


def build_patient_index(rows: list[SourceRow], path: Path) -> dict[str, int]:
    """Replace the local snapshot atomically while preserving repeated records."""
    if not rows:
        raise ValueError(
            "The source returned no rows; the existing index is unchanged."
        )
    records: list[tuple[str, str, str, str, str]] = []
    contacts: set[tuple[str, str]] = set()
    occurrences: Counter[str] = Counter()

    # Step 1: Validate identifiers before touching an existing local snapshot.
    for row in rows:
        if set(row) != set(SOURCE_COLUMNS):
            raise ValueError("A source record does not match the approved columns.")
        patient_id = row["subject_id"]
        admission_id = row["hadm_id"]
        if not patient_id or not patient_id.strip():
            raise ValueError("A record has no patient ID; the import is stopped.")
        if not admission_id or not admission_id.strip():
            raise ValueError("A record has no admission ID; the import is stopped.")

        # Step 2: Keep contact addresses outside the clinical record and its text.
        email = row["email"]
        if email and email.strip():
            contacts.add((patient_id, email.strip()))
        clinical = {
            column: (
                EMAIL_PATTERN.sub("[email removed]", value)
                if (value := row[column]) is not None
                else None
            )
            for column in CLINICAL_COLUMNS
        }
        content = json.dumps(clinical, ensure_ascii=False, sort_keys=True)
        text = "\n".join(
            f"{column}: {value.strip()}"
            for column, value in clinical.items()
            if value is not None and value.strip()
        )

        # Step 3: An occurrence suffix preserves even identical selected records.
        identity = json.dumps([patient_id, admission_id, clinical], sort_keys=True)
        digest = hashlib.sha256(identity.encode()).hexdigest()
        occurrences[digest] += 1
        record_id = f"{digest}:{occurrences[digest]}"
        records.append((record_id, patient_id, admission_id, content, text))

    # Step 4: Replace both tables in one transaction so failed imports roll back.
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS clinical_records (
                record_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                admission_id TEXT NOT NULL,
                clinical_json TEXT NOT NULL,
                document_text TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS records_by_patient_admission
                ON clinical_records(patient_id, admission_id);
            CREATE TABLE IF NOT EXISTS patient_contacts (
                patient_id TEXT NOT NULL,
                email TEXT NOT NULL,
                PRIMARY KEY(patient_id, email)
            );
        """)
        with connection:
            connection.execute("DELETE FROM clinical_records")
            connection.execute("DELETE FROM patient_contacts")
            connection.executemany(
                "INSERT INTO clinical_records VALUES (?, ?, ?, ?, ?)", records
            )
            connection.executemany(
                "INSERT INTO patient_contacts VALUES (?, ?)", sorted(contacts)
            )

    # Step 5: Report counts only; logs do not expose patient or contact values.
    contact_counts = Counter(patient for patient, _ in contacts)
    return {
        "records": len(records),
        "patients": len({record[1] for record in records}),
        "patient_admission_pairs": len({record[1:3] for record in records}),
        "repeated_selected_records_preserved": sum(n - 1 for n in occurrences.values()),
        "contact_addresses": len(contacts),
        "patients_with_multiple_emails": sum(n > 1 for n in contact_counts.values()),
    }


def get_patient_records(
    path: Path, patient_id: str, admission_id: str | None = None
) -> list[dict[str, str]]:
    """Retrieve one patient's records without exposing the contact table."""
    if not patient_id.strip():
        raise ValueError("A patient ID is required for retrieval.")
    query = "SELECT * FROM clinical_records WHERE patient_id = ?"
    parameters = [patient_id]
    if admission_id is not None:
        query += " AND admission_id = ?"
        parameters.append(admission_id)
    query += " ORDER BY record_id"
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    ) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query, parameters)]
