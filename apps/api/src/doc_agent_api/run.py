"""Run the FastAPI service without access logs that expose patient URL paths."""

import os
import sys

import uvicorn
from doc_agent_common.runtime import configure_asyncio_for_psycopg


def main() -> None:
    """Start one worker; deploy multiple workers behind a shared gateway limiter."""
    configure_asyncio_for_psycopg()
    config = uvicorn.Config(
        "doc_agent_api.main:create_app",
        factory=True,
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
        access_log=False,
        server_header=False,
        loop="none" if sys.platform == "win32" else "auto",
    )
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        import asyncio

        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        server.run()
