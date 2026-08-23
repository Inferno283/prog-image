from fastapi import APIRouter, File, UploadFile, Response

from app.schemas.images import RetrieveImageResponse, StoreImageResponse
from app.services.image_service import ImageService
from uuid import UUID

router = APIRouter(prefix="/images", tags=["images"])
image_service = ImageService()


@router.post("", response_model=StoreImageResponse)
async def store_image(image: UploadFile = File(...)) -> StoreImageResponse:
    image_id = await image_service.store(image)

    return StoreImageResponse(id=image_id)


@router.get("/{image_id}")
async def retrieve_image(image_id: UUID) -> Response:
    image = await image_service.retrieve(image_id)

    return Response(
        content=image,
        media_type="image/jpeg",
    )
