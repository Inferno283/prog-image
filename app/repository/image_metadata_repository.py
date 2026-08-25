from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image_models import StoredImageMetadata
from app.schemas.images import ImageMetadata


class AsyncImageMetadataRepository():
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def store(self, blob_storage_provider, blob_key, image_metadata: ImageMetadata):
        metadata = StoredImageMetadata(
            id=blob_key,
            blob_storage_provider=blob_storage_provider,
            blob_key=str(blob_key),
            content_type=image_metadata.content_type,
            filename=image_metadata.filename,
            size_bytes=image_metadata.size_bytes,
            height=image_metadata.height,
            width=image_metadata.width,
            image_format=image_metadata.format,
        )

        try:
            self.db.add(metadata)
            await self.db.commit()

            return metadata.blob_key

        except Exception:
            await self.db.rollback()
            raise

    async def retrieve(self, image_uuid: UUID) -> StoredImageMetadata | None:
        
        result = await self.db.execute(
            select(StoredImageMetadata)
            .where(StoredImageMetadata.id == image_uuid)
        )

        metadata = result.scalar_one_or_none()

        return metadata
        