from uuid import UUID

from pydantic import BaseModel


class StoreImageResponse(BaseModel):
    id: UUID
    
class ImageMetadata(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    format: str
    
class RetrievedImage(BaseModel):
    content: bytes
    filename: str
    content_type: str