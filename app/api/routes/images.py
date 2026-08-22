from fastapi import APIRouter

from app.schemas.images import RetrieveImageResponse, StoreImageResponse


router = APIRouter(prefix="/images", tags=["images"])


@router.post("", response_model=StoreImageResponse)
def store_image():
    return StoreImageResponse(id="yo")


@router.get("/{image_id}", response_model=RetrieveImageResponse)
def retrieve_image(image_id: str) -> RetrieveImageResponse:
    return RetrieveImageResponse(id="yo")