import aioboto3

from app.core.config import settings

async_s3_session = aioboto3.Session(
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
)


def async_client_factory():
    return async_s3_session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
    )