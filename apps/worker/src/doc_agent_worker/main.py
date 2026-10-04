"""Provide one CLI surface for ingestion and isolated contact synchronization."""

import argparse

from doc_agent_worker.pipelines.contact_sync import main as contact_sync_main
from doc_agent_worker.pipelines.patient_index import main as patient_index_main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline", choices=("index", "contacts"))
    args = parser.parse_args()
    if args.pipeline == "index":
        patient_index_main()
    else:
        contact_sync_main()
