import logging
import uuid
from io import BytesIO
from uuid import UUID

from botocore.exceptions import ClientError
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.repository.blob_repository import AsyncBlobRepository
from app.repository.image_metadata_repository import AsyncImageMetadataRepository
from app.schemas.images import ImageMetadata, RetrievedImage

logger = logging.getLogger("prog-image")

IMAGE_MEDIA_TYPES = {
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


class ImageNotFoundError(Exception):
    pass


class ImageService:
    def __init__(self, image_metadata_repo: AsyncImageMetadataRepository, blob_repo: AsyncBlobRepository):
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
            await self.image_metadata_repo.store(
                blob_storage_provider=self.blob_repo.storage_provider,
                blob_key=image_uuid,
                image_metadata=image_metadata,
            )
            return image_uuid
        except Exception:
            try:
                await self.blob_repo.delete(
                    bucket_name=settings.s3_bucket,
                    key=image_uuid,
                )
            except Exception:
                logger.exception(
                    "Failed to clean up orphaned blob %s",
                    image_uuid,
                )
                # Orphaned image requires manual deletion to avoid being orphaned.
            raise

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

                if pil_image.format not in IMAGE_MEDIA_TYPES:
                    raise InvalidImageError(
                        f"Unsupported image format: {pil_image.format}"
                    )
                content_type = IMAGE_MEDIA_TYPES.get(
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

    async def retrieve(self, image_uuid: UUID) -> RetrievedImage:
        metadata = await self.image_metadata_repo.retrieve(image_uuid)
        if metadata is None:
            raise ImageNotFoundError(f"Image not found {image_uuid}")
        try:
            image = await self.blob_repo.retrieve(
                bucket_name=settings.s3_bucket, key=image_uuid
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                raise InvalidStorageStateError(
                    f"Image metadata exists but blob is missing: {image_uuid}"
                ) from exc
            
            logger.exception(
                "Failed to retrieve image %s from blob storage",
                image_uuid,
            )
            raise

        return RetrievedImage(
            content=image,
            filename=metadata.filename,
            content_type=metadata.content_type,
        )
