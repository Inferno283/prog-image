

from uuid import UUID


class S3BlobRepository:
    def __init__(self, client):
        self.client = client
        self.storage_provider_type = "S3"

    def store(self, bucket_name, image_to_store, image_content_type, key: UUID):
        self.client.put_object(
            Bucket=bucket_name,
            Key=str(key),
            Body=image_to_store,
            ContentType=image_content_type
        )
        return key

 
    def retrieve(self, bucket_name, key: UUID) -> bytes:
        response = self.client.get_object(
            Bucket=bucket_name,
            Key=str(key),
        )

        return response["Body"].read()
