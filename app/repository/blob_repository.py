from collections.abc import Callable
from uuid import UUID

from app.schemas.images import ImageMetadata


class AsyncBlobRepository:
    def __init__(self, async_client_factory: Callable, storage_provider: str):
        self.async_client_factory = async_client_factory
        self.storage_provider = storage_provider
        

    async def store(self, bucket_name: str, file_to_store: bytes, image_metadata: ImageMetadata, key: UUID):
        async with self.async_client_factory() as client:
            await client.put_object(
                Bucket=bucket_name,
                Key=str(key),
                Body=file_to_store,
                ContentType=image_metadata.content_type,
            )
        
        return key

 
    async def retrieve(self, bucket_name, key: UUID) -> bytes:
        async with self.async_client_factory() as client:
            response = await client.get_object(
                Bucket=bucket_name,
                Key=str(key),
            )
            async with response["Body"] as body:
                return await body.read()

    async def delete(self, bucket_name: str, key: UUID) -> None:
        async with self.async_client_factory() as client:
            await client.delete_object(
                Bucket=bucket_name,
                Key=str(key),
            )