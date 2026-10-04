"""Expose focused console entry points for each worker pipeline."""

from doc_agent_worker.pipelines.contact_sync import main as contact_sync_main
from doc_agent_worker.pipelines.patient_index import main as patient_index_main


def run_index() -> None:
    patient_index_main()


def run_contact_sync() -> None:
    contact_sync_main()
