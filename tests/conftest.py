import importlib
import os
from typing import Iterator

import boto3
import pytest
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

TEST_DATABASE_NAME = "progimage_test"
TEST_BUCKET_NAME = "images-test"


def _create_test_database() -> None:
    admin_engine = create_engine(
        "postgresql+psycopg://progimage:progimage@localhost:5432/postgres",
        isolation_level="AUTOCOMMIT",
    )
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": TEST_DATABASE_NAME},
        ).scalar()
        if exists is None:
            connection.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))


def _create_test_bucket() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ["S3_REGION"],
    )
    try:
        client.head_bucket(Bucket=TEST_BUCKET_NAME)
    except ClientError:
        client.create_bucket(Bucket=TEST_BUCKET_NAME)


@pytest.fixture(scope="session", autouse=True)
def test_environment() -> Iterator[None]:
    os.environ["DATABASE_URL"] = "postgresql+psycopg://progimage:progimage@localhost:5432/progimage_test"
    os.environ["S3_ENDPOINT_URL"] = "http://localhost:9000"
    os.environ["S3_ACCESS_KEY"] = "minio"
    os.environ["S3_SECRET_KEY"] = "minio123"
    os.environ["S3_REGION"] = "us-east-1"
    os.environ["S3_BUCKET"] = TEST_BUCKET_NAME

    _create_test_database()
    _create_test_bucket()

    from app.core import config as config_module
    from app.database import connection as connection_module
    from app.blob import s3_connection as s3_module

    importlib.reload(config_module)
    importlib.reload(connection_module)
    importlib.reload(s3_module)

    connection_module.Base.metadata.create_all(bind=connection_module.engine)
    yield


@pytest.fixture()
def db_session():
    from sqlalchemy import text

    from app.database.connection import Base, SessionLocal

    bind = SessionLocal.kw["bind"]
    session = SessionLocal()
    try:
        with bind.connect() as connection:
            try:
                connection.execute(text("TRUNCATE TABLE stored_image_metadata"))
            except Exception:
                Base.metadata.create_all(bind=bind)
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ["S3_REGION"],
    )
