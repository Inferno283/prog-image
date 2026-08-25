from uuid import UUID

from fastapi import APIRouter, Response, UploadFile

from app.schemas.images import StoreImageResponse
from app.services.image_service import ImageService

router = APIRouter(prefix="/images", tags=["images"])
image_service = ImageService()

@router.post("", response_model=StoreImageResponse)
async def store_image(image: UploadFile) -> StoreImageResponse:
    image_uuid = await image_service.store(image)
    return StoreImageResponse(id=image_uuid)


@router.get("/{image_id}")
async def retrieve_image(image_id: UUID) -> Response:
    image = await image_service.retrieve(image_id)
    return Response(
        content=image.content,
        media_type=image.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{image.filename}"',
        },
    )