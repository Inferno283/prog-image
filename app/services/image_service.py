import uuid

from fastapi import UploadFile

from app.blob.s3_connection import client
from app.database.connection import SessionLocal
from app.repository.image_repository import ImageMetadataRepository
from app.repository.s3_blob_repository import S3BlobRepository
from app.validators.image_validation import validate_image
from app.core.config import settings
from uuid import UUID


default_image_repo = ImageMetadataRepository(SessionLocal())
default_blob_repo = S3BlobRepository(client)

class ImageService:

    def __init__(
        self,
        image_repo: ImageMetadataRepository = default_image_repo,
        blob_repo: S3BlobRepository = default_blob_repo
    ):
        self.image_storage_metadata_repo = image_repo
        self.blob_repo = blob_repo
        
    async def store(self, image: UploadFile) -> UUID:
        # Validate image
        # Checks
        validate_image(image)
        image_type = "image/jpeg"
        image_uuid = uuid.uuid4()

        image_data = await image.read() # latency? TODO
        blob_key = self.blob_repo.store(
            bucket_name=settings.s3_bucket,
            image_to_store=image_data,
            image_content_type=image_type,
            key=image_uuid
        )
        
        await self.image_storage_metadata_repo.store(
            blob_storage_provider=self.blob_repo.storage_provider_type,
            blob_key=blob_key
        )

        return blob_key

    async def retrieve(self, image_uuid: UUID):
        # metadata = await self.image_storage_metadata_repo.retrieve(image_uuid)

        return self.blob_repo.retrieve(bucket_name=settings.s3_bucket, key=image_uuid)
