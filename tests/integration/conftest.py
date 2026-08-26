from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.db_connection import Base, SessionLocal, engine
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncGenerator[None, None]:
    async with SessionLocal() as session:
        await session.execute(
            text("TRUNCATE TABLE stored_image_metadata")
        )
        await session.commit()

    yield