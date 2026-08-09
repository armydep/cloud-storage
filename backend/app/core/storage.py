import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from app.core.config import settings


class ObjectNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ObjectStat:
    size_bytes: int
    content_type: str | None = None


def get_object_key(blob_hash: str) -> str:
    return f"sha256/{blob_hash}"


def get_pending_upload_object_key(*, owner_id: Any, upload_id: Any) -> str:
    return f"uploads/{owner_id}/{upload_id}"


def get_s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


def _get_expires_in(expires_in: int | None) -> int:
    return expires_in or settings.S3_PRESIGNED_URL_EXPIRES_SECONDS


def _rewrite_public_url(url: str) -> str:
    internal_url = settings.S3_ENDPOINT_URL.rstrip("/")
    public_url = settings.S3_PUBLIC_ENDPOINT_URL.rstrip("/")

    if internal_url == public_url or not url.startswith(internal_url):
        return url

    return public_url + url[len(internal_url) :]


def create_presigned_upload_url(
    *,
    object_key: str,
    mime_type: str,
    expires_in: int | None = None,
) -> str:
    url = get_s3_client().generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": object_key,
            "ContentType": mime_type,
        },
        ExpiresIn=_get_expires_in(expires_in),
    )
    return _rewrite_public_url(url)


def create_presigned_download_url(
    *,
    object_key: str,
    filename: str,
    expires_in: int | None = None,
) -> str:
    safe_filename = filename.replace("\\", "\\\\").replace('"', '\\"')
    encoded_filename = quote(filename)
    url = get_s3_client().generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": object_key,
            "ResponseContentDisposition": (
                f'attachment; filename="{safe_filename}"; '
                f"filename*=UTF-8''{encoded_filename}"
            ),
        },
        ExpiresIn=_get_expires_in(expires_in),
    )
    return _rewrite_public_url(url)


def stat_object(*, object_key: str) -> ObjectStat:
    try:
        response = get_s3_client().head_object(
            Bucket=settings.S3_BUCKET,
            Key=object_key,
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise ObjectNotFoundError from exc
        raise

    return ObjectStat(
        size_bytes=response["ContentLength"],
        content_type=response.get("ContentType"),
    )


def calculate_object_sha256(*, object_key: str) -> str:
    response = get_s3_client().get_object(
        Bucket=settings.S3_BUCKET,
        Key=object_key,
    )
    digest = hashlib.sha256()
    body = response["Body"]
    try:
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            digest.update(chunk)
    finally:
        close = getattr(body, "close", None)
        if close:
            close()
    return digest.hexdigest()


def copy_object(*, source_object_key: str, destination_object_key: str) -> None:
    get_s3_client().copy_object(
        Bucket=settings.S3_BUCKET,
        CopySource={"Bucket": settings.S3_BUCKET, "Key": source_object_key},
        Key=destination_object_key,
    )


def delete_object(*, object_key: str) -> None:
    get_s3_client().delete_object(
        Bucket=settings.S3_BUCKET,
        Key=object_key,
    )
