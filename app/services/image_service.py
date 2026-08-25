import uuid
from io import BytesIO
from uuid import UUID

from botocore.exceptions import ClientError
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.schemas.images import ImageMetadata, RetrievedImage

MAX_IMAGE_SIZE_IN_MB = 10


IMAGE_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}


class InvalidImageError(Exception):
    pass

class InvalidStorageStateError(Exception):
    pass


class ImageService:
    def __init__(self, image_metadata_repo, blob_repo):
        self.image_metadata_repo = image_metadata_repo
        self.blob_repo = blob_repo

    async def store(self, image: UploadFile) -> UUID:
        image_data = await image.read()
        image_metadata = self.get_image_metadata(image, image_data)
        image_uuid = uuid.uuid4()

        await self.blob_repo.store(
            bucket_name=settings.s3_bucket,
            file_to_store=image_data,
            image_metadata=image_metadata,
            key=image_uuid,
        )
        try:
            # IF THIS FAILS, DELETE BLOB FILE TO ENSURE CONSISTENCY
            await self.image_metadata_repo.store(
                blob_storage_provider=self.blob_repo.storage_provider,
                blob_key=image_uuid,
                image_metadata=image_metadata,
            )
        except Exception:
            try:
                await self.blob_repo.delete(
                    bucket_name=settings.s3_bucket,
                    key=image_uuid,
                )
            except Exception:
                # Log this loudly: orphaned blob requires reconciliation.
                raise
            raise
        return image_uuid

    def get_image_metadata(self, image: UploadFile, image_data: bytes) -> ImageMetadata:
        if not image_data:
            raise InvalidImageError("Image is empty")

        if len(image_data) > (settings.max_image_size_mb * (1024**2)):
            raise InvalidImageError(
                f"Image exceeds maximum size of {settings.max_image_size_mb} MB"
            )

        try:
            with Image.open(BytesIO(image_data)) as pil_image:
                pil_image.load()

                if pil_image.format not in IMAGE_MIME_TYPES:
                    raise InvalidImageError(
                        f"Unsupported image format: {pil_image.format}"
                    )
                content_type = IMAGE_MIME_TYPES.get(
                    pil_image.format
                )  # This is not always clear from the request, e.g. octet-stream

                return ImageMetadata(
                    filename=image.filename or "",
                    content_type=content_type or "",
                    size_bytes=len(image_data),
                    width=pil_image.width,
                    height=pil_image.height,
                    format=pil_image.format or "",
                )
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise InvalidImageError("Invalid image") from exc

    async def retrieve(self, image_uuid: UUID):
        metadata = await self.image_metadata_repo.retrieve(image_uuid)
        try:    
            image = await self.blob_repo.retrieve(
                bucket_name=settings.s3_bucket, key=image_uuid
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):    
                raise InvalidStorageStateError(
                    f"Image metadata exists but blob is missing: {image_uuid}"
                ) from exc
            raise
            
        
        return RetrievedImage(
            content=image,
            filename=metadata.filename,
            content_type=metadata.content_type,
        )
