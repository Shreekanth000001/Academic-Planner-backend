# database.py
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing import AsyncGenerator

from config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=15,

    connect_args = {"statement_cache_size":0,"prepared_statement_cache_size":0}
)

async def get_session() -> AsyncGenerator[AsyncSession,None]:
    session_maker = async_sessionmaker(
        engine,class_=AsyncSession,expire_on_commit=False
    )
    async with session_maker() as session:
            yield session
