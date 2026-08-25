from uuid import UUID

from sqlalchemy.orm import Session

from app.models.image_models import StoredImageMetadata
from app.repository.repository_protocol import Repository
from app.schemas.images import ImageMetadata


class ImageMetadataRepository(Repository):
    
    def __init__(self, db: Session):
        self.db = db
        
    async def store(self, blob_storage_provider, blob_key, image_metadata: ImageMetadata):
        metadata = StoredImageMetadata(
            id=blob_key,
            blob_storage_provider=blob_storage_provider,
            blob_key=blob_key,
            content_type=image_metadata.content_type,
            filename=image_metadata.filename,
            size_bytes=image_metadata.size_bytes,
            height=image_metadata.height,
            width=image_metadata.width,
            image_format=image_metadata.format,
        )

        try:
            self.db.add(metadata)
            self.db.commit()
            self.db.refresh(metadata)

            return metadata.blob_key

        except Exception:
            self.db.rollback()
            raise

    def retrieve(self, image_uuid: UUID) -> StoredImageMetadata:
        metadata = (
            self.db.query(StoredImageMetadata)
            .filter(StoredImageMetadata.id == image_uuid)
            .first()
        )

        if metadata is None:
            raise ValueError(f"Image metadata not found: {image_uuid}")

        return metadata