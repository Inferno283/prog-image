from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app.repository.blob_repository import AsyncBlobRepository
from app.schemas.images import ImageMetadata


@pytest.fixture
def async_blob_client():
    return AsyncMock()


@pytest.fixture
def async_client_factory(async_blob_client):
    client_context = Mock()
    client_context.__aenter__ = AsyncMock(return_value=async_blob_client)
    client_context.__aexit__ = AsyncMock(return_value=None)

    factory = Mock(return_value=client_context)

    return factory


@pytest.fixture
def blob_repository(async_client_factory):
    return AsyncBlobRepository(
        async_client_factory=async_client_factory,
        storage_provider="s3",
    )


@pytest.fixture
def image_metadata():
    return ImageMetadata(
        filename="test.png",
        content_type="image/png",
        size_bytes=123,
        width=100,
        height=100,
        format="PNG",
    )


@pytest.fixture
def image_uuid():
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def image_data():
    return b"test image data"


@pytest.mark.asyncio
async def test_blob_store_success(
    blob_repository,
    async_blob_client,
    image_metadata,
    image_uuid,
    image_data,
):
    result = await blob_repository.store(
        bucket_name="test-bucket",
        file_to_store=image_data,
        image_metadata=image_metadata,
        key=image_uuid,
    )

    assert result == image_uuid

    async_blob_client.put_object.assert_awaited_once_with(
        Bucket="test-bucket",
        Key=str(image_uuid),
        Body=image_data,
        ContentType=image_metadata.content_type,
    )


@pytest.mark.asyncio
async def test_blob_retrieve_success(
    blob_repository,
    async_blob_client,
    image_uuid,
    image_data,
):
    body = Mock()
    body.read = AsyncMock(return_value=image_data)
    body.__aenter__ = AsyncMock(return_value=body)
    body.__aexit__ = AsyncMock(return_value=None)
    
    async_blob_client.get_object.return_value = {
        "Body": body,
    }

    result = await blob_repository.retrieve(
        bucket_name="test-bucket",
        key=image_uuid,
    )

    assert result == image_data

    async_blob_client.get_object.assert_awaited_once_with(
        Bucket="test-bucket",
        Key=str(image_uuid),
    )
    body.read.assert_awaited_once()


@pytest.mark.asyncio
async def test_blob_delete_success(
    blob_repository,
    async_blob_client,
    image_uuid,
):
    result = await blob_repository.delete(
        bucket_name="test-bucket",
        key=image_uuid,
    )

    assert result is None

    async_blob_client.delete_object.assert_awaited_once_with(
        Bucket="test-bucket",
        Key=str(image_uuid),
    )
