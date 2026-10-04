"""Apply the privileged RAG migration through the configured Ubuntu SSH host."""

import asyncio
import json
import shlex
import sys

from doc_agent_common.config import AppSettings

REMOTE_MIGRATOR = r"""
import json, subprocess, sys
payload = json.load(sys.stdin)
result = subprocess.run(
    [
        'sudo', '-u', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
        '-v', 'app_user=' + payload['app_user'], '-d', payload['database'],
    ],
    input=payload['sql'], text=True, capture_output=True,
)
if result.returncode:
    sys.exit(result.returncode)
"""


async def apply_migration() -> None:
    """Send SQL over encrypted standard input without exposing database secrets."""
    settings = AppSettings.load()
    migration_paths = sorted(
        (settings.project / "packages/db/migrations").glob("*.sql")
    )
    if not migration_paths:
        raise RuntimeError("No RAG migrations were found.")
    # The files are idempotent and run in lexical order through one psql session.
    sql = "\n".join(path.read_text(encoding="utf-8") for path in migration_paths)
    payload = json.dumps(
        {
            "database": settings.database_name,
            "app_user": settings.database_user,
            "sql": sql,
        }
    ).encode()
    process = await asyncio.create_subprocess_exec(
        "ssh",
        "-i",
        str(settings.ssh_key_path),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={settings.ssh_known_hosts_path}",
        f"{settings.ssh_user}@{settings.database_host}",
        "python3 -c " + shlex.quote(REMOTE_MIGRATOR),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.communicate(payload)
    if process.returncode:
        raise RuntimeError("The privileged RAG migration failed.")


def main() -> None:
    """Apply the migration with a safe one-line outcome."""
    try:
        asyncio.run(apply_migration())
    except Exception as error:  # noqa: BLE001 - this is the admin CLI boundary.
        print(f"Migration failed ({type(error).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None
    print("RAG migration applied successfully.")


if __name__ == "__main__":
    main()
