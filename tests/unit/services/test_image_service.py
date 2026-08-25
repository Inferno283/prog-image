from io import BytesIO
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import logging
from botocore.exceptions import ClientError
from fastapi import UploadFile
from PIL import Image

from app.services.image_service import (
    ImageNotFoundError,
    ImageService,
    InvalidImageError,
    InvalidStorageStateError,
)


@pytest.fixture
def image_metadata_repo():
    image_metadata_repo = Mock()
    image_metadata_repo.store = AsyncMock()
    image_metadata_repo.retrieve = AsyncMock()
    return image_metadata_repo


@pytest.fixture
def blob_repo():
    blob_repo = Mock()
    blob_repo.store = AsyncMock()
    blob_repo.retrieve = AsyncMock()
    blob_repo.delete = AsyncMock()
    blob_repo.storage_provider = "s3"
    return blob_repo


@pytest.fixture
def image_service(image_metadata_repo, blob_repo):
    return ImageService(
        image_metadata_repo=image_metadata_repo,
        blob_repo=blob_repo,
    )


@pytest.fixture
def test_image():
    image = Image.new("RGB", (100, 100), color="red")

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


@pytest.fixture
def upload_file(test_image):
    return UploadFile(
        filename="test.png",
        file=BytesIO(test_image),
    )


@pytest.mark.asyncio
async def test_image_store_success(
    image_service,
    image_metadata_repo,
    blob_repo,
    upload_file,
    test_image,
):
    image_uuid = await image_service.store(upload_file)

    assert image_uuid is not None

    blob_repo.store.assert_awaited_once()
    image_metadata_repo.store.assert_awaited_once()
    blob_repo.delete.assert_not_awaited()

    blob_args = blob_repo.store.await_args.kwargs

    assert blob_args["key"] == image_uuid
    assert blob_args["file_to_store"] == test_image

    metadata_args = image_metadata_repo.store.await_args.kwargs

    assert metadata_args["blob_key"] == image_uuid
    assert metadata_args["blob_storage_provider"] == "s3"


@pytest.mark.asyncio
async def test_image_store_invalid_image(
    image_service,
    image_metadata_repo,
    blob_repo,
):
    image = UploadFile(
        filename="test_not_a_png.png",
        file=BytesIO(b"not an image"),
    )

    with pytest.raises(InvalidImageError):
        await image_service.store(image)

    blob_repo.store.assert_not_awaited()
    image_metadata_repo.store.assert_not_awaited()
    blob_repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_image_store_metadata_storage_failure(
    image_service,
    image_metadata_repo,
    blob_repo,
    upload_file,
):
    image_metadata_repo.store.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await image_service.store(upload_file)

    blob_repo.store.assert_awaited_once()
    image_metadata_repo.store.assert_awaited_once()
    blob_repo.delete.assert_awaited_once()

    stored_key = blob_repo.store.await_args.kwargs["key"]
    deleted_key = blob_repo.delete.await_args.kwargs["key"]

    assert deleted_key == stored_key


@pytest.mark.asyncio
async def test_image_store_cleanup_failure(
    image_service, image_metadata_repo, blob_repo, upload_file, caplog
):
    image_metadata_repo.store.side_effect = RuntimeError("database unavailable")
    blob_repo.delete.side_effect = RuntimeError("S3 unavailable")

    with (
        pytest.raises(RuntimeError, match="database unavailable"),
        caplog.at_level(logging.ERROR, logger="prog-image"),
    ):
        await image_service.store(upload_file)

    blob_repo.store.assert_awaited_once()
    image_metadata_repo.store.assert_awaited_once()
    blob_repo.delete.assert_awaited_once()

    assert "Failed to clean up orphaned blob" in caplog.text


@pytest.mark.asyncio
async def test_image_retrieve_success(
    image_service,
    image_metadata_repo,
    blob_repo,
    test_image,
):
    image_uuid = uuid4()

    metadata = Mock()
    metadata.filename = "test.png"
    metadata.content_type = "image/png"

    image_metadata_repo.retrieve.return_value = metadata
    blob_repo.retrieve.return_value = test_image

    result = await image_service.retrieve(image_uuid)

    assert result.content == test_image
    assert result.filename == "test.png"
    assert result.content_type == "image/png"

    image_metadata_repo.retrieve.assert_awaited_once_with(image_uuid)
    blob_repo.retrieve.assert_awaited_once()

    assert blob_repo.retrieve.await_args.kwargs["key"] == image_uuid


@pytest.mark.asyncio
async def test_image_retrieve_metadata_does_not_exist(
    image_service,
    image_metadata_repo,
    blob_repo,
):
    image_uuid = uuid4()

    image_metadata_repo.retrieve.return_value = None

    with pytest.raises(ImageNotFoundError):
        await image_service.retrieve(image_uuid)

    image_metadata_repo.retrieve.assert_awaited_once_with(image_uuid)
    blob_repo.retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_image_retrieve_metadata_exists_blob_does_not_exist(
    image_service,
    image_metadata_repo,
    blob_repo,
):
    image_uuid = uuid4()

    metadata = Mock()
    metadata.filename = "test.png"
    metadata.content_type = "image/png"

    image_metadata_repo.retrieve.return_value = metadata

    blob_repo.retrieve.side_effect = ClientError(
        {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist.",
            }
        },
        "GetObject",
    )

    with pytest.raises(
        InvalidStorageStateError,
        match=f"Image metadata exists but blob is missing: {image_uuid}",
    ):
        await image_service.retrieve(image_uuid)

    image_metadata_repo.retrieve.assert_awaited_once_with(image_uuid)
    blob_repo.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_image_retrieve_blob_network_failure(
    image_service,
    image_metadata_repo,
    blob_repo,
):
    image_uuid = uuid4()

    metadata = Mock()
    metadata.filename = "test.png"
    metadata.content_type = "image/png"

    image_metadata_repo.retrieve.return_value = metadata

    blob_repo.retrieve.side_effect = ClientError(
        {
            "Error": {
                "Code": "InternalError",
                "Message": "Storage unavailable",
            }
        },
        "GetObject",
    )

    with pytest.raises(ClientError):
        await image_service.retrieve(image_uuid)

    image_metadata_repo.retrieve.assert_awaited_once_with(image_uuid)
    blob_repo.retrieve.assert_awaited_once()
