"""Open bounded PostgreSQL connections with pgvector type registration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from doc_agent_common.config import AppSettings
from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection


class DatabaseConnectionFactory:
    """Create one connection per repository operation."""

    def __init__(self, settings: AppSettings) -> None:
        self._conninfo = settings.database_conninfo()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection[object]]:
        connection = await AsyncConnection.connect(self._conninfo)
        try:
            await register_vector_async(connection)
            yield connection
        finally:
            await connection.close()
