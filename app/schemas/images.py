from pydantic import BaseModel


class StoreImageResponse(BaseModel):
    id: str

class RetrieveImageResponse(BaseModel):
    id: str
