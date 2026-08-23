from uuid import UUID

from sqlalchemy.orm import Session
from app.models.models import ImageMetadata

class ImageMetadataRepository:
    
    def __init__(self, db: Session):
        self.db = db
        
    async def store(self, blob_storage_provider, blob_key):
        metadata = ImageMetadata(
            blob_storage_provider=blob_storage_provider,
            blob_url=blob_key,
        )

        try:
            self.db.add(metadata)
            self.db.commit()
            self.db.refresh(metadata)

            return metadata.id

        except Exception:
            self.db.rollback()
            raise

    def retrieve(self, image_uuid: UUID):
        
        # Retrieve image metadata
        # 
        pass