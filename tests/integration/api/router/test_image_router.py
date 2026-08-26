from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.image_models import StoredImageMetadata


@pytest.fixture
def test_image() -> bytes:
    """
    Generate a real 100x100 PNG image.
    """
    image = Image.new("RGB", (100, 100), color="red")

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


@pytest.mark.asyncio
async def test_store_and_retrieve_image(
    client: AsyncClient,
    test_image: bytes,
):
    store_response = await client.post(
        "/images",
        files={
            "image": (
                "test.png",
                test_image,
                "image/png",
            )
        },
    )

    assert store_response.status_code == 200

    response_data = store_response.json()

    assert "image_uuid" in response_data

    image_uuid = UUID(response_data["image_uuid"])

    retrieve_response = await client.get(
        f"/images/{image_uuid}"
    )

    assert retrieve_response.status_code == 200
    assert retrieve_response.content == test_image
    assert retrieve_response.headers["content-type"] == "image/png"
    assert (
        'filename="test.png"'
        in retrieve_response.headers["content-disposition"]
    )


@pytest.mark.asyncio
async def test_store_image_persists_metadata_and_blob(
    client: AsyncClient,
    db_session: AsyncSession,
    s3_client,
    test_image: bytes,
):
    filename = "test.png"

    response = await client.post(
        "/images",
        files={
            "image": (
                filename,
                test_image,
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    image_uuid = UUID(response.json()["image_uuid"])

    # ------------------------------------------------------------------
    # Verify PostgreSQL state.
    # ------------------------------------------------------------------

    result = await db_session.execute(
        select(StoredImageMetadata).where(
            StoredImageMetadata.id == image_uuid
        )
    )

    metadata = result.scalar_one()

    assert metadata.id == image_uuid
    assert metadata.blob_storage_provider == "s3"
    assert metadata.blob_key == str(image_uuid)
    assert metadata.content_type == "image/png"
    assert metadata.filename == filename
    assert metadata.size_bytes == len(test_image)
    assert metadata.width == 100
    assert metadata.height == 100
    assert metadata.image_format == "PNG"

    # ------------------------------------------------------------------
    # Verify MinIO/S3 state.
    # ------------------------------------------------------------------

    s3_response = await s3_client.get_object(
        Bucket=settings.s3_bucket,
        Key=str(image_uuid),
    )

    async with s3_response["Body"] as body:
        stored_image = await body.read()

    assert stored_image == test_image


@pytest.mark.asyncio
async def test_store_image_invalid_image(
    client: AsyncClient,
):
    response = await client.post(
        "/images",
        files={
            "image": (
                "test.png",
                b"this is not an image",
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid image"


@pytest.mark.asyncio
async def test_store_image_empty_file(
    client: AsyncClient,
):
    response = await client.post(
        "/images",
        files={
            "image": (
                "empty.png",
                b"",
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Image is empty"


@pytest.mark.asyncio
async def test_store_image_exceeds_maximum_size(
    client: AsyncClient,
):
    # The configured limit is in megabytes.
    oversized_image = b"x" * (
        settings.max_image_size_mb * 1024 * 1024 + 1
    )

    response = await client.post(
        "/images",
        files={
            "image": (
                "large.png",
                oversized_image,
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Image exceeds maximum size of "
        f"{settings.max_image_size_mb} MB"
    )


@pytest.mark.asyncio
async def test_retrieve_image_not_found(
    client: AsyncClient,
):
    missing_uuid = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/images/{missing_uuid}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        f"Image not found {missing_uuid}"
    )


@pytest.mark.asyncio
async def test_retrieve_image_invalid_uuid(
    client: AsyncClient,
):
    response = await client.get(
        "/images/not-a-uuid"
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_retrieve_image_blob_missing(
    client: AsyncClient,
    s3_client,
    test_image: bytes,
):
    # Store the image normally.
    store_response = await client.post(
        "/images",
        files={
            "image": (
                "test.png",
                test_image,
                "image/png",
            )
        },
    )

    assert store_response.status_code == 200

    image_uuid = UUID(store_response.json()["image_uuid"])

    # Delete only the blob. PostgreSQL metadata remains.
    await s3_client.delete_object(
        Bucket=settings.s3_bucket,
        Key=str(image_uuid),
    )

    retrieve_response = await client.get(
        f"/images/{image_uuid}"
    )

    assert retrieve_response.status_code == 500
    assert retrieve_response.json()["detail"] == (
        "Unable to retrieve image."
    )


@pytest.mark.asyncio
async def test_store_and_retrieve_different_image_formats(
    client: AsyncClient,
):
    formats = [
        ("PNG", "image/png"),
        ("JPEG", "image/jpeg"),
        ("WEBP", "image/webp"),
        ("GIF", "image/gif"),
        ("BMP", "image/bmp"),
        ("TIFF", "image/tiff"),
    ]

    for image_format, content_type in formats:
        image = Image.new("RGB", (50, 75))

        image_bytes = BytesIO()
        image.save(
            image_bytes,
            format=image_format,
        )

        image_data = image_bytes.getvalue()
        filename = f"test.{image_format.lower()}"

        store_response = await client.post(
            "/images",
            files={
                "image": (
                    filename,
                    image_data,
                    content_type,
                )
            },
        )

        assert store_response.status_code == 200

        image_uuid = UUID(
            store_response.json()["image_uuid"]
        )

        retrieve_response = await client.get(
            f"/images/{image_uuid}"
        )

        assert retrieve_response.status_code == 200
        assert retrieve_response.content == image_data
        assert (
            retrieve_response.headers["content-type"]
            == content_type
        )
        assert (
            f'filename="{filename}"'
            in retrieve_response.headers["content-disposition"]
        )