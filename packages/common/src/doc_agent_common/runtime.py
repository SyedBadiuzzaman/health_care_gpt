"""Configure platform details shared by command-line entry points."""

import asyncio
import sys


def configure_asyncio_for_psycopg() -> None:
    """Use Windows selector I/O because psycopg rejects the proactor loop."""
    if sys.platform != "win32":
        return
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
