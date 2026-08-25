from uuid import UUID

from app.repository.repository_protocol import Repository
from app.schemas.images import ImageMetadata


class BlobRepository(Repository):
    def __init__(self, client, storage_provider):
        self.client = client
        self.storage_provider_type = storage_provider

    def store(self, bucket_name: str, file_to_store: bytes, image_metadata: ImageMetadata, key: UUID):
        self.client.put_object(
            Bucket=bucket_name,
            Key=str(key),
            Body=file_to_store,
            ContentType=image_metadata.content_type # TODO Remove this, make this repo reusable
        )
        return key

 
    async def retrieve(self, bucket_name, key: UUID) -> bytes:
        response = self.client.get_object(
            Bucket=bucket_name,
            Key=str(key),
        )

        return response["Body"].read()
