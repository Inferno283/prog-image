from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.image_router import router as image_router
from app.connections.db_connection import get_async_db
from app.services.image_service import (
    ImageNotFoundError,
    InvalidImageError,
    InvalidStorageStateError,
)

TEST_IMAGE_UUID = UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(image_router)

    async def override_get_db():
        yield Mock()

    test_app.dependency_overrides[get_async_db] = override_get_db

    return test_app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest.fixture
def image_service():
    return Mock()


@pytest.fixture
def patched_image_service(image_service):
    with patch(
        "app.api.routes.image_router.ImageService",
        return_value=image_service,
    ):
        yield image_service


@pytest.fixture
def store_image_service(image_service):
    image_service.store = AsyncMock(
        return_value=TEST_IMAGE_UUID,
    )
    return image_service


@pytest.fixture
def retrieve_image_service(image_service):
    image_service.retrieve = AsyncMock()
    return image_service


@pytest.mark.asyncio
async def test_store_image_success(
    client: AsyncClient,
    store_image_service,
    patched_image_service,
):
    response = await client.post(
        "/images",
        files={
            "image": (
                "test.png",
                b"test image",
                "image/png",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "image_uuid": str(TEST_IMAGE_UUID),
    }

    store_image_service.store.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_image_invalid_image(
    client: AsyncClient,
    image_service,
    patched_image_service,
):
    image_service.store = AsyncMock(
        side_effect=InvalidImageError("Invalid image"),
    )

    response = await client.post(
        "/images",
        files={
            "image": (
                "test.png",
                b"not an image",
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid image",
    }

    image_service.store.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieve_image_success(
    client: AsyncClient,
    image_service,
    patched_image_service,
):
    image_service.retrieve = AsyncMock(
        return_value=Mock(
            content=b"test image",
            filename="test.png",
            content_type="image/png",
        ),
    )

    response = await client.get(
        f"/images/{TEST_IMAGE_UUID}",
    )

    assert response.status_code == 200
    assert response.content == b"test image"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'attachment; filename="test.png"'

    image_service.retrieve.assert_awaited_once_with(
        TEST_IMAGE_UUID,
    )


@pytest.mark.asyncio
async def test_retrieve_image_not_found(
    client: AsyncClient,
    image_service,
    patched_image_service,
):
    image_service.retrieve = AsyncMock(
        side_effect=ImageNotFoundError(
            f"Image not found {TEST_IMAGE_UUID}",
        ),
    )

    response = await client.get(
        f"/images/{TEST_IMAGE_UUID}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Image not found {TEST_IMAGE_UUID}",
    }

    image_service.retrieve.assert_awaited_once_with(
        TEST_IMAGE_UUID,
    )


@pytest.mark.asyncio
async def test_retrieve_image_blob_missing(
    client: AsyncClient,
    image_service,
    patched_image_service,
):
    image_service.retrieve = AsyncMock(
        side_effect=InvalidStorageStateError(
            f"Image metadata exists but blob is missing: {TEST_IMAGE_UUID}",
        ),
    )

    response = await client.get(
        f"/images/{TEST_IMAGE_UUID}",
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Unable to retrieve image.",
    }

    image_service.retrieve.assert_awaited_once_with(
        TEST_IMAGE_UUID,
    )


@pytest.mark.asyncio
async def test_retrieve_image_invalid_uuid(
    client: AsyncClient,
):
    response = await client.get(
        "/images/not-a-uuid",
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_store_image_missing_file(
    client: AsyncClient,
):
    response = await client.post(
        "/images",
    )

    assert response.status_code == 422
