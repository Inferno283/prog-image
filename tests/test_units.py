import asyncio
import importlib
import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile
from PIL import Image


def test_settings_loads_expected_environment_values(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://progimage:progimage@localhost:5432/progimage_test")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "minio")
    monkeypatch.setenv("S3_SECRET_KEY", "minio123")
    monkeypatch.setenv("S3_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET", "images-test")

    from app.core import config as config_module

    importlib.reload(config_module)

    assert config_module.settings.database_url == "postgresql+psycopg://progimage:progimage@localhost:5432/progimage_test"
    assert config_module.settings.s3_bucket == "images-test"


def test_database_session_factory_uses_engine_and_base_models():
    from app.database.connection import SessionLocal

    assert SessionLocal.kw["bind"] is not None
    assert hasattr(SessionLocal, "kw")
    assert hasattr(SessionLocal.kw["bind"], "connect")


def test_s3_client_configuration_uses_minio_endpoint():
    from app.blob.s3_connection import client

    assert client is not None
    assert client.meta.endpoint_url is not None


def test_image_service_rejects_empty_file():
    from app.services.image_service import ImageService

    service = ImageService(image_repo=MagicMock(), blob_repo=MagicMock())
    upload = UploadFile(filename="empty.png", file=io.BytesIO(b""), headers={"content-type": "image/png"})

    with pytest.raises(ValueError, match="Image is empty"):
        service.get_image_metadata(upload, b"")


def test_image_service_rejects_oversized_file():
    from app.services.image_service import ImageService

    service = ImageService(image_repo=MagicMock(), blob_repo=MagicMock())
    payload = b"x" * (10 * 1024 * 1024 + 1)
    upload = UploadFile(filename="large.png", file=io.BytesIO(payload), headers={"content-type": "image/png"})

    with pytest.raises(ValueError, match="maximum size"):
        service.get_image_metadata(upload, payload)


def test_image_service_store_calls_blob_repo_and_metadata_repo():
    from app.services.image_service import ImageService

    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="red").save(buffer, format="PNG")
    buffer.seek(0)

    image_repo = MagicMock()
    image_repo.store = AsyncMock(return_value=None)
    blob_repo = MagicMock()
    blob_repo.storage_provider_type = "S3"
    service = ImageService(image_repo=image_repo, blob_repo=blob_repo)

    image = UploadFile(filename="sample.png", file=buffer, headers={"content-type": "image/png"})
    image_id = asyncio.run(service.store(image))

    assert image_id is not None
    blob_repo.store.assert_called_once()
    image_repo.store.assert_awaited_once()


def test_blob_repository_store_and_retrieve_round_trip():
    from app.repository.s3_blob_repository import BlobRepository
    from app.schemas.images import ImageMetadata

    client = MagicMock()
    client.get_object.return_value = {"Body": io.BytesIO(b"hello world")}
    repo = BlobRepository(client)
    key = "abc123"

    stored_key = repo.store("images-test", b"hello world", ImageMetadata(
        filename="hello.png",
        content_type="image/png",
        size_bytes=11,
        width=4,
        height=4,
        format="PNG",
    ), key)

    assert stored_key == key
    client.put_object.assert_called_once_with(
        Bucket="images-test",
        Key=key,
        Body=b"hello world",
        ContentType="image/png",
    )
    assert repo.retrieve("images-test", key) == b"hello world"


def test_repository_persists_metadata_record(db_session):
    from app.models.image_models import StoredImageMetadata
    from app.repository.image_repository import StoredImageMetadataRepository
    from app.schemas.images import ImageMetadata

    repo = StoredImageMetadataRepository(db_session)
    record_id = "550e8400-e29b-41d4-a716-446655440000"

    asyncio.run(repo.store(
        blob_storage_provider="S3",
        blob_key=record_id,
        image_metadata=ImageMetadata(
            filename="persisted.png",
            content_type="image/png",
            size_bytes=128,
            width=8,
            height=8,
            format="PNG",
        ),
    ))

    saved = db_session.query(StoredImageMetadata).filter(StoredImageMetadata.blob_key == record_id).one_or_none()
    assert saved is not None
    assert saved.content_type == "image/png"
    assert saved.blob_storage_provider == "S3"


def test_image_metadata_model_round_trip():
    from app.schemas.images import ImageMetadata

    metadata = ImageMetadata(
        filename="photo.png",
        content_type="image/png",
        size_bytes=64,
        width=8,
        height=8,
        format="PNG",
    )

    assert metadata.filename == "photo.png"
    assert metadata.size_bytes == 64
    assert metadata.format == "PNG"
