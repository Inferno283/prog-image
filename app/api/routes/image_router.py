from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.db_connection import get_db
from app.connections.s3_connection import async_client_factory
from app.repository.blob_repository import AsyncBlobRepository
from app.repository.image_metadata_repository import AsyncImageMetadataRepository
from app.schemas.images import StoreImageResponse
from app.services.image_service import (
    ImageNotFoundError,
    ImageService,
    InvalidImageError,
    InvalidStorageStateError,
)

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", response_model=StoreImageResponse)
async def store_image(
    image: UploadFile, db: Annotated[AsyncSession, Depends(get_db)]
) -> StoreImageResponse:
    image_service = ImageService(
        image_metadata_repo=AsyncImageMetadataRepository(db),
        blob_repo=AsyncBlobRepository(async_client_factory, "s3"),
    )
    try:
        image_uuid = await image_service.store(image)
        return StoreImageResponse(image_uuid=image_uuid)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/{image_id}")
async def retrieve_image(
    image_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> Response:
    image_service = ImageService(
        image_metadata_repo=AsyncImageMetadataRepository(db),
        blob_repo=AsyncBlobRepository(async_client_factory, "s3"),
    )
    try:
        image = await image_service.retrieve(image_id)
    except ImageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidStorageStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image not stored. Please try again.",
        ) from exc

    return Response(
        content=image.content,
        media_type=image.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{image.filename}"',
        },
    )
