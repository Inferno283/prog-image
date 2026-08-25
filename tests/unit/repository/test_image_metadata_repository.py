from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app.models.image_models import StoredImageMetadata
from app.repository.image_metadata_repository import AsyncImageMetadataRepository
from app.schemas.images import ImageMetadata

TEST_IMAGE_UUID = UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def db():
    db = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def image_metadata_repo(db):
    return AsyncImageMetadataRepository(db)


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
def stored_image_metadata(image_metadata):
    return StoredImageMetadata(
        id=TEST_IMAGE_UUID,
        blob_storage_provider="s3",
        blob_key=str(TEST_IMAGE_UUID),
        content_type=image_metadata.content_type,
        filename=image_metadata.filename,
        size_bytes=image_metadata.size_bytes,
        height=image_metadata.height,
        width=image_metadata.width,
        image_format=image_metadata.format,
    )


@pytest.mark.asyncio
async def test_image_metadata_repo_store_success(
    image_metadata_repo,
    db,
    image_metadata,
):
    result = await image_metadata_repo.store(
        blob_storage_provider="s3",
        blob_key=TEST_IMAGE_UUID,
        image_metadata=image_metadata,
    )

    assert result == str(TEST_IMAGE_UUID)

    db.add.assert_called_once()

    db.commit.assert_awaited_once()

    stored_metadata = db.add.call_args.args[0]

    assert isinstance(stored_metadata, StoredImageMetadata)
    assert stored_metadata.id == TEST_IMAGE_UUID
    assert stored_metadata.blob_storage_provider == "s3"
    assert stored_metadata.blob_key == str(TEST_IMAGE_UUID)
    assert stored_metadata.content_type == "image/png"
    assert stored_metadata.filename == "test.png"
    assert stored_metadata.size_bytes == 123
    assert stored_metadata.width == 100
    assert stored_metadata.height == 100
    assert stored_metadata.image_format == "PNG"


@pytest.mark.asyncio
async def test_image_metadata_repo_store_failure(
    image_metadata_repo,
    db,
    image_metadata,
):
    error = RuntimeError("database unavailable")
    db.commit.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        await image_metadata_repo.store(
            blob_storage_provider="s3",
            blob_key=TEST_IMAGE_UUID,
            image_metadata=image_metadata,
        )

    assert exc_info.value is error

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_image_metadata_repo_retrieve_success(
    image_metadata_repo,
    db,
    stored_image_metadata,
):
    result = Mock()
    result.scalar_one_or_none.return_value = stored_image_metadata

    db.execute.return_value = result

    retrieved = await image_metadata_repo.retrieve(
        TEST_IMAGE_UUID,
    )

    assert retrieved is stored_image_metadata

    db.execute.assert_awaited_once()

    result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_image_metadata_repo_retrieve_not_found(
    image_metadata_repo,
    db,
):
    result = Mock()
    result.scalar_one_or_none.return_value = None

    db.execute.return_value = result

    retrieved = await image_metadata_repo.retrieve(
        TEST_IMAGE_UUID,
    )

    assert retrieved is None

    db.execute.assert_awaited_once()
    result.scalar_one_or_none.assert_called_once()

@pytest.mark.asyncio
async def test_image_metadata_repo_retrieve_failure(
    image_metadata_repo,
    db,
):
    error = RuntimeError("database unavailable")
    db.execute.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        await image_metadata_repo.retrieve(
            TEST_IMAGE_UUID,
        )

    assert exc_info.value is error

    db.execute.assert_awaited_once()
