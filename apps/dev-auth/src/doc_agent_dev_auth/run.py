"""Run the loopback-only development token server."""

import uvicorn


def main() -> None:
    uvicorn.run(
        "doc_agent_dev_auth.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8001,
        access_log=False,
        server_header=False,
    )
