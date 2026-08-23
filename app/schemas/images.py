from pydantic import BaseModel


class StoreImageResponse(BaseModel):
    id: str

class RetrieveImageResponse(BaseModel):
    content: bytes
    media_type: str