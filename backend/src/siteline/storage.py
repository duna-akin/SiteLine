"""Final agreed documents: the files precedents cite as their source.

Stored in an S3-compatible bucket (Supabase Storage) when the S3_* settings are set,
otherwise in var/documents. Keys look like "site-07/NSO-417_CTA_Site07_final.docx"; the same
key is saved on each precedent (source_key) and served back by GET /api/sources.
"""

from __future__ import annotations

import re

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from siteline.config import RUNTIME_DIR, settings

LOCAL_DIR = RUNTIME_DIR / "documents"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
KEY_PATTERN = re.compile(r"[\w.-]+/[\w.-]+\.docx")

_client = None


class StorageError(Exception):
    pass


def enabled() -> bool:
    return settings.s3_enabled


def valid_key(key: str) -> bool:
    return bool(KEY_PATTERN.fullmatch(key)) and ".." not in key


def client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            # Supabase Storage needs path-style URLs (endpoint/bucket/key)
            config=Config(s3={"addressing_style": "path"}, connect_timeout=10, read_timeout=30, retries={"max_attempts": 2}),
        )
    return _client


def put(key: str, data: bytes, content_type: str = DOCX) -> None:
    if not enabled():
        path = LOCAL_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    try:
        client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError) as e:
        raise StorageError(f"Could not upload {key}: {type(e).__name__}") from e


def get(key: str) -> bytes | None:
    """The document's bytes, or None when there is no such document."""
    if not enabled():
        path = LOCAL_DIR / key
        return path.read_bytes() if path.is_file() else None
    try:
        return client().get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()
    except ClientError as e:
        # AWS sends NoSuchKey; Supabase Storage sends a bare 404 with an empty code
        if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404 or e.response.get("Error", {}).get("Code") == "NoSuchKey":
            return None
        raise StorageError(f"Could not read {key}: {type(e).__name__}") from e
    except BotoCoreError as e:
        raise StorageError(f"Could not read {key}: {type(e).__name__}") from e
