import uuid
from io import BytesIO
from uuid import UUID

from fastapi import UploadFile
from PIL import Image

from app.blob.s3_connection import client
from app.core.config import settings
from app.database.connection import SessionLocal
from app.repository.image_metadata_repository import ImageMetadataRepository
from app.repository.blob_repository import BlobRepository
from app.schemas.images import ImageMetadata, RetrievedImage

default_image_repo = ImageMetadataRepository(SessionLocal())
default_blob_repo = BlobRepository(client, "s3")

MAX_IMAGE_SIZE_IN_MB = 10


IMAGE_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}

class ImageService:
    def __init__(
        self,
        image_repo: ImageMetadataRepository = default_image_repo,
        blob_repo: BlobRepository = default_blob_repo,
    ):
        self.image_storage_metadata_repo = image_repo
        self.blob_repo = blob_repo

    async def store(self, image: UploadFile) -> UUID:
        image_data = await image.read()
        image_metadata = self.get_image_metadata(image, image_data)
        image_uuid = uuid.uuid4()

        self.blob_repo.store(
            bucket_name=settings.s3_bucket,
            file_to_store=image_data,
            image_metadata=image_metadata,
            key=image_uuid,
        )

        await self.image_storage_metadata_repo.store(
            blob_storage_provider=self.blob_repo.storage_provider_type,
            blob_key=image_uuid,
            image_metadata=image_metadata,
        )

        return image_uuid

    async def retrieve(self, image_uuid: UUID):
        metadata = self.image_storage_metadata_repo.retrieve(image_uuid)
        image = await self.blob_repo.retrieve(bucket_name=settings.s3_bucket, key=image_uuid)
        return RetrievedImage(content=image, filename=metadata.filename, content_type=metadata.content_type)

    def get_image_metadata(self, image: UploadFile, image_data: bytes) -> ImageMetadata:
        if not image_data:
            raise ValueError("Image is empty")

        if len(image_data) > (settings.max_image_size_mb*(1024**2)):
            raise ValueError(f"Image exceeds maximum size of {settings.max_image_size_mb} MB")

        with Image.open(BytesIO(image_data)) as pil_image:
            pil_image.load()
            
            if pil_image.format not in IMAGE_MIME_TYPES:
                raise ValueError(
                    f"Unsupported image format: {pil_image.format}"
                )
            content_type = IMAGE_MIME_TYPES.get(pil_image.format)
            
            return ImageMetadata(
                filename=image.filename or "",
                content_type=content_type or "",
                size_bytes=len(image_data),
                width=pil_image.width,
                height=pil_image.height,
                format=pil_image.format or "",
            )
