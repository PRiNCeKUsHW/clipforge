"""S3-compatible object storage (SeaweedFS locally, Cloudflare R2 in production).

Shared by the API and the worker, so it must not import FastAPI or app settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


class Storage:
    def __init__(
        self,
        *,
        bucket: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str | None = None,
        public_endpoint_url: str | None = None,
        region: str = "us-east-1",
    ) -> None:
        self.bucket = bucket
        cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 5})
        common: dict[str, Any] = dict(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=cfg,
        )
        # Client used for real I/O (inside docker: http://s3:8333).
        self.client = boto3.client("s3", endpoint_url=endpoint_url or None, **common)
        # Presigned URLs embed the host in the signature, so they must be signed for the
        # address the *browser* uses (http://localhost:9000). Signing makes no network call.
        self._signer = boto3.client("s3", endpoint_url=(public_endpoint_url or endpoint_url) or None, **common)

    # ---------- presigned URLs ----------
    def presign_put(self, key: str, content_type: str, expires: int = 3600) -> str:
        return self._signer.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )

    def presign_get(self, key: str, expires: int = 3600, download_name: str | None = None) -> str:
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
        return self._signer.generate_presigned_url("get_object", Params=params, ExpiresIn=expires)

    # ---------- object I/O ----------
    def head(self, key: str) -> dict[str, Any] | None:
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def exists(self, key: str) -> bool:
        return self.head(key) is not None

    def upload_file(self, path: str | Path, key: str, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else None
        self.client.upload_file(str(path), self.bucket, key, ExtraArgs=extra)

    def download_file(self, key: str, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(path))

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objects:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
                deleted += len(objects)
        return deleted

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)


# Key layout, in one place so the API and worker agree.
def upload_key(user_id: str, upload_id: str, filename: str) -> str:
    return f"uploads/{user_id}/{upload_id}/{filename}"


def source_key(project_id: str, ext: str = "mp4") -> str:
    return f"sources/{project_id}/source.{ext}"


def clip_key(project_id: str, clip_id: str) -> str:
    return f"clips/{project_id}/{clip_id}.mp4"


def thumbnail_key(project_id: str, clip_id: str) -> str:
    return f"clips/{project_id}/{clip_id}.jpg"
