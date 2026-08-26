from collections.abc import AsyncGenerator

import pytest_asyncio
from botocore.exceptions import ClientError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.connections.db_connection import Base, get_async_db
from app.connections.s3_connection import async_s3_session
from app.core.config import settings
from app.main import app as fast_api_app

# ENV VARIABLES COME FROM PYPROJECT.TOML UNDER [tool.pytest_env]

# ===========================================================================
# TEST DATABASE
# ===========================================================================

test_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # TODO Explain this in more detail
)


async def override_get_db() -> AsyncGenerator[AsyncSession]:
    """
    Database dependency used only by integration tests.

    A fresh AsyncSession and asyncpg connection are created for every
    request. NullPool ensures connections aren't reused across event loops.
    """
    async with TestSessionLocal() as session:
        yield session


# Override get_db to use integration-test-friendly sessions
fast_api_app.dependency_overrides[get_async_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None]:
    """
    Create the test database schema once for the integration test session.
    """
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


# ===========================================================================
# S3 / MINIO
# ===========================================================================


@pytest_asyncio.fixture
async def s3_client():
    """
    Create a fresh async S3 client for each test.

    Keeping this function-scoped avoids retaining an async client across
    pytest event loops.
    """
    async with async_s3_session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
    ) as client: # type: ignore[reportGeneralTypeIssues]
        yield client


async def clean_s3_bucket(s3_client) -> None:
    response = await s3_client.list_objects_v2(
        Bucket=settings.s3_bucket,
    )

    objects = response.get("Contents", [])

    if not objects:
        return

    await s3_client.delete_objects(
        Bucket=settings.s3_bucket,
        Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_s3_bucket() -> AsyncGenerator[None]:
    """
    Create the test bucket once for the integration test session.
    """
    async with async_s3_session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
    ) as client: # type: ignore[reportGeneralTypeIssues]
        try:
            await client.head_bucket(
                Bucket=settings.s3_bucket,
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")

            if error_code in ("404", "NoSuchBucket"):
                await client.create_bucket(
                    Bucket=settings.s3_bucket,
                )
            else:
                raise

        yield

        await clean_s3_bucket(client)

        await client.delete_bucket(
            Bucket=settings.s3_bucket,
        )


# ===========================================================================
# HTTP CLIENT
# ===========================================================================


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """
    Async HTTP client connected directly to FastAPI.
    """
    transport = ASGITransport(app=fast_api_app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as async_client:
        yield async_client


# ===========================================================================
# DATABASE SESSION FOR ASSERTIONS
# ===========================================================================


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """
    Independent database session for test assertions.

    This is NOT the session used by the API request.
    """
    async with TestSessionLocal() as session:
        yield session


# ===========================================================================
# PER-TEST CLEANUP
# ===========================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_database(
    s3_client,
) -> AsyncGenerator[None]:
    """
    Ensure every integration test starts and ends with an empty database
    and empty S3 bucket.
    """

    # -----------------------------------------------------------------------
    # Before test
    # -----------------------------------------------------------------------

    async with TestSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE stored_image_metadata"))
        await session.commit()

    await clean_s3_bucket(s3_client)

    yield

    # -----------------------------------------------------------------------
    # After test
    # -----------------------------------------------------------------------

    async with TestSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE stored_image_metadata"))
        await session.commit()

    await clean_s3_bucket(s3_client)
