# database.py
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing import AsyncGenerator

from config import settings

# 1. Create the Async Engine
# echo=False in production to prevent logging every SQL statement.
# pool_size and max_overflow dictate how many concurrent connections your API holds.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10, 
    max_overflow=20,
    # CRITICAL PGBOUNCER CONFIGURATION:
    # Disables the asyncpg statement cache so the Supabase pooler doesn't choke
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0}
)

# 2. Dependency Injection Generator
# This is a Python generator. It yields a session to the incoming HTTP request,
# and the `finally` block ensures the connection is returned to the pool even if the API crashes.
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()