import io
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image


def _blank_png(width: int = 32, height: int = 32) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color="green").save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_and_retrieve_happy_path(s3_client):
    from app.api.routes import image_router
    from app.blob.s3_connection import client as s3_connection_client
    from app.database.connection import SessionLocal
    from app.main import app
    from app.models.image_models import StoredImageMetadata
    from app.repository.image_repository import StoredImageMetadataRepository
    from app.repository.s3_blob_repository import BlobRepository
    from app.services.image_service import ImageService

    session = SessionLocal()
    image_router.image_service = ImageService(
        image_repo=StoredImageMetadataRepository(session),
        blob_repo=BlobRepository(s3_connection_client),
    )

    client = TestClient(app)
    payload = _blank_png()

    response = client.post("/images", files={"image": ("photo.png", payload, "image/png")})

    assert response.status_code == 200, response.text
    image_id = response.json()["id"]
    assert isinstance(UUID(image_id), UUID)

    with SessionLocal() as session_check:
        metadata = session_check.query(StoredImageMetadata).filter(StoredImageMetadata.id == UUID(image_id)).one_or_none()
        assert metadata is not None
        assert metadata.content_type == "image/png"

    s3_object = s3_client.get_object(Bucket="images-test", Key=image_id)
    assert s3_object["Body"].read() == payload

    retrieve = client.get(f"/images/{image_id}")
    assert retrieve.status_code == 200, retrieve.text
    assert retrieve.content == payload


@pytest.mark.xfail(reason="The app does not catch ValueError from an empty upload and currently bubbles a 500.")
def test_empty_upload_is_rejected_cleanly():
    from app.main import app

    client = TestClient(app)

    response = client.post("/images", files={"image": ("empty.png", b"", "image/png")})

    assert response.status_code == 400
    assert "empty" in response.text.lower()


@pytest.mark.xfail(reason="The app does not guard invalid image payloads and currently raises an uncaught parsing error.")
def test_invalid_image_payload_is_rejected_cleanly():
    from app.main import app

    client = TestClient(app)

    response = client.post("/images", files={"image": ("broken.txt", b"not an image", "text/plain")})

    assert response.status_code == 400
    assert "image" in response.text.lower()


@pytest.mark.xfail(reason="The route does not translate a missing S3 object into a 404 response.")
def test_missing_image_returns_404():
    from app.main import app

    client = TestClient(app)

    response = client.get("/images/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
