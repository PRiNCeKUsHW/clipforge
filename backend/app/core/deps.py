from functools import lru_cache

from app.core.config import get_settings
from app.core.storage import Storage


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    return Storage(
        bucket=s.s3_bucket,
        access_key=s.s3_access_key,
        secret_key=s.s3_secret_key,
        endpoint_url=s.s3_endpoint_url,
        public_endpoint_url=s.s3_public_endpoint_url,
        region=s.s3_region,
    )
