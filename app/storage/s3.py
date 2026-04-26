from io import BytesIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists() -> None:
    client = get_s3_client()

    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.minio_bucket)


def upload_file(
    object_key: str,
    content: bytes,
    content_type: str | None,
) -> None:
    ensure_bucket_exists()

    client = get_s3_client()
    client.upload_fileobj(
        BytesIO(content),
        settings.minio_bucket,
        object_key,
        ExtraArgs={"ContentType": content_type or "application/octet-stream"},
    )


def download_file(object_key: str):
    client = get_s3_client()
    return client.get_object(
        Bucket=settings.minio_bucket,
        Key=object_key,
    )