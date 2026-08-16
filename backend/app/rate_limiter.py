"""Rate limiting for DM sends."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import RateLimitBucket

logger = logging.getLogger(__name__)


class RateLimiter:
    """PostgreSQL-backed rate limiter using an atomic reservation check."""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    @staticmethod
    def is_rate_limited(
        db: Session,
        bucket_key: str = "dm_sends",
    ) -> bool:
        """Check if the current rolling window is exhausted without reserving capacity."""
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=settings.rate_limit_seconds)
            stmt = select(RateLimitBucket).where(RateLimitBucket.bucket_key == bucket_key).with_for_update()
            bucket = db.execute(stmt).scalar_one_or_none()

            if bucket is None:
                return False

            if bucket.window_start < cutoff:
                bucket.window_start = now
                bucket.request_count = 0
                db.commit()
                return False

            if bucket.request_count >= settings.rate_limit_requests:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "bucket_key": bucket_key,
                        "request_count": bucket.request_count,
                        "limit": settings.rate_limit_requests,
                    },
                )
                return True

            return False
        except Exception as e:
            logger.error("Error checking rate limit", extra={"error": str(e)})
            return False

    @staticmethod
    def reserve_capacity(
        db: Session,
        bucket_key: str = "dm_sends",
    ) -> bool:
        """Atomically reserve one DM send slot for the current rolling window."""
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=settings.rate_limit_seconds)

            stmt = select(RateLimitBucket).where(RateLimitBucket.bucket_key == bucket_key).with_for_update()
            bucket = db.execute(stmt).scalar_one_or_none()

            if bucket is None:
                bucket = RateLimitBucket(
                    bucket_key=bucket_key,
                    request_count=1,
                    window_start=now,
                )
                db.add(bucket)
                db.commit()
                logger.debug(
                    "Rate limit capacity reserved",
                    extra={"bucket_key": bucket_key, "request_count": 1, "limit": settings.rate_limit_requests},
                )
                return True

            if bucket.window_start < cutoff:
                bucket.window_start = now
                bucket.request_count = 0

            if bucket.request_count >= settings.rate_limit_requests:
                db.rollback()
                logger.warning(
                    "Rate limit exhausted; reservation denied",
                    extra={
                        "bucket_key": bucket_key,
                        "request_count": bucket.request_count,
                        "limit": settings.rate_limit_requests,
                    },
                )
                return False

            bucket.request_count += 1
            db.commit()
            logger.debug(
                "Rate limit capacity reserved",
                extra={
                    "bucket_key": bucket_key,
                    "request_count": bucket.request_count,
                    "limit": settings.rate_limit_requests,
                },
            )
            return True
        except Exception as e:
            db.rollback()
            logger.error("Error reserving rate limit capacity", extra={"error": str(e)})
            return False

    @staticmethod
    def increment_counter(
        db: Session,
        bucket_key: str = "dm_sends",
    ) -> bool:
        """Compatibility wrapper for legacy callers; rate limiting is reserved before send."""
        return RateLimiter.reserve_capacity(db, bucket_key=bucket_key)

