"""Run the preparation steps in the order described in the README."""

import argparse
import asyncio
import json
from pathlib import Path

from doc_agent_db.contact_source import load_settings, read_clinical_records
from doc_agent_db.contact_store import build_patient_index


async def prepare(project: Path) -> dict[str, int]:
    """Read approved data and build a patient index inside the project."""
    # Step 1: Read connection settings from the existing private environment file.
    settings = load_settings(project / ".env")

    # Step 2: Fetch only approved fields through the read-only SSH connection.
    rows = await read_clinical_records(settings, project / "Keys" / "health.pem")

    # Step 3: Store clinical records and separate contacts in an indexed snapshot.
    return await asyncio.to_thread(
        build_patient_index, rows, project / "data" / "patient_index.sqlite3"
    )


def main() -> None:
    """Prepare the local patient index and print a non-identifying summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        summary = asyncio.run(prepare(args.project.resolve()))
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        parser.exit(
            1,
            f"Preparation failed ({type(error).__name__}). Check settings and access.\n",
        )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
