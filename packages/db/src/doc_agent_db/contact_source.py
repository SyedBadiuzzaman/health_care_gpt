"""Read approved columns through SSH without changing PostgreSQL data."""

import asyncio
import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from doc_agent_db.contact_schema import SOURCE_COLUMNS

SourceRow = dict[str, str | None]


@dataclass(frozen=True)
class DatabaseSettings:
    """Hold credentials without exposing them in object representations."""

    host: str
    port: str
    database: str
    user: str
    password: str = field(repr=False)


def load_settings(env_path: Path) -> DatabaseSettings:
    """Load the existing database settings without expanding password values."""
    if not env_path.is_file():
        raise ValueError("The database .env file does not exist.")
    values = dotenv_values(env_path, interpolate=False, encoding="utf-8-sig")
    keys = (
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_NAME",
        "DATABASE_USER",
        "DATABASE_PASSWORD",
    )
    configured: list[str] = []
    for key in keys:
        value = values.get(key)
        if not value:
            raise ValueError(f"Missing setting: {key}")
        configured.append(value)
    if not configured[1].isdigit() or not 1 <= int(configured[1]) <= 65535:
        raise ValueError("DATABASE_PORT must be between 1 and 65535.")
    return DatabaseSettings(*configured)


# Credentials travel over encrypted standard input, not in command arguments.
# PostgreSQL enforces a read-only transaction and a bounded query duration.
REMOTE_READER = """
import json, os, subprocess, sys
payload = json.load(sys.stdin)
environment = os.environ.copy()
environment.update(
    PGHOST='127.0.0.1', PGPORT=payload['port'],
    PGDATABASE=payload['database'], PGUSER=payload['user'],
    PGPASSWORD=payload['password'], PGCONNECT_TIMEOUT='10',
    PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=45000',
)
result = subprocess.run(
    ['psql', '-X', '-q', '-t', '-A', '-v', 'ON_ERROR_STOP=1',
     '-c', payload['query']],
    env=environment, capture_output=True, text=True,
)
if result.returncode:
    sys.exit(1)
sys.stdout.write(result.stdout)
"""


def parse_source_rows(output: bytes) -> list[SourceRow]:
    """Validate the approved schema before storing any imported data."""
    decoded: object = json.loads(output)
    if not isinstance(decoded, list):
        raise TypeError("The database did not return a record list.")
    rows: list[SourceRow] = []
    for item in decoded:
        if not isinstance(item, dict) or set(item) != set(SOURCE_COLUMNS):
            raise ValueError("A source record does not match the approved columns.")
        row: SourceRow = {}
        for column in SOURCE_COLUMNS:
            value: object = item[column]
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Unexpected source type for {column}.")
            row[column] = value
        rows.append(row)
    return rows


async def read_clinical_records(
    settings: DatabaseSettings, key_path: Path, ssh_user: str = "ubuntu"
) -> list[SourceRow]:
    """Fetch a consistent snapshot using the existing trusted SSH host key."""
    if not key_path.is_file():
        raise ValueError("The SSH private key does not exist.")
    known_hosts = key_path.parent / "known_hosts"
    if not known_hosts.is_file():
        raise ValueError("The trusted SSH known_hosts file does not exist.")

    # Select an explicit allowlist so new source columns cannot enter RAG silently.
    columns = ", ".join(f'"{name}"' for name in SOURCE_COLUMNS)
    query = (
        "SELECT COALESCE(json_agg(row_to_json(records)), '[]'::json) "
        f"FROM (SELECT {columns} FROM public.clinical_records) records"
    )
    payload = {
        "port": settings.port,
        "database": settings.database,
        "user": settings.user,
        "password": settings.password,
        "query": query,
    }
    process = await asyncio.create_subprocess_exec(
        "ssh",
        "-i",
        str(key_path.resolve()),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=12",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts.resolve()}",
        f"{ssh_user}@{settings.host}",
        "python3 -c " + shlex.quote(REMOTE_READER),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(json.dumps(payload).encode()), timeout=65
        )
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise RuntimeError("The read-only database import timed out.") from None
    if process.returncode:
        # Remote errors can contain credentials or row values; do not print them.
        raise RuntimeError("The SSH/database read failed; check access and settings.")
    return parse_source_rows(output)
