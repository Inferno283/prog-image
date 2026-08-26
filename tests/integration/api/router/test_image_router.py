from io import BytesIO
from uuid import UUID

import pytest
from botocore.exceptions import ClientError
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image_models import StoredImageMetadata
from app.core.config import settings


@pytest.mark.asyncio
async def test_store_and_retrieve_image(
    client: AsyncClient,
    test_image: bytes,
):
    # Store the image through the API.
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

    # Retrieve the image through the API.
    retrieve_response = await client.get(f"/images/{image_uuid}")

    assert retrieve_response.status_code == 200
    assert retrieve_response.content == test_image
    assert retrieve_response.headers["content-type"] == "image/png"
    assert 'filename="test.png"' in retrieve_response.headers[
        "content-disposition"
    ]


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

    # Verify metadata exists in PostgreSQL.
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

    # Verify the actual blob exists in MinIO/S3.
    response = await s3_client.get_object(
        Bucket="images",
        Key=str(image_uuid),
    )

    async with response["Body"] as body:
        stored_image = await body.read()

    assert stored_image == test_image


@pytest.mark.asyncio
async def test_store_image_invalid_image(
    client: AsyncClient,
):
    invalid_image = b"this is not an image"

    response = await client.post(
        "/images",
        files={
            "image": (
                "test.png",
                invalid_image,
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid image"


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
async def test_retrieve_image_blob_missing(
    client: AsyncClient,
    db_session: AsyncSession,
    s3_client,
    test_image: bytes,
):
    # First store an image normally.
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

    # Delete the blob directly from S3/MinIO while leaving
    # the metadata in PostgreSQL.
    await s3_client.delete_object(
        Bucket="images",
        Key=str(image_uuid),
    )

    # The metadata still exists, but the blob doesn't.
    retrieve_response = await client.get(
        f"/images/{image_uuid}"
    )

    assert retrieve_response.status_code == 500
    assert retrieve_response.json()["detail"] == (
        "Image not stored. Please try again."
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
        image.save(image_bytes, format=image_format)
        image_bytes.seek(0)

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
        assert retrieve_response.headers["content-type"] == content_type
        assert f'filename="{filename}"' in retrieve_response.headers[
            "content-disposition"
        ]