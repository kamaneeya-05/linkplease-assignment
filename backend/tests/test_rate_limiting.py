"""Tests for rate limiting."""
import pytest
from datetime import datetime, timedelta
from app.rate_limiter import RateLimiter
from app.database import RateLimitBucket
from app.config import settings


def test_rate_limit_check_no_limit(db):
    """Test rate limit when under limit."""
    is_limited = RateLimiter.is_rate_limited(db, "test_bucket")
    assert is_limited is False


def test_rate_limit_increment(db):
    """Test incrementing rate limit counter."""
    bucket_key = "test_increment"
    
    # Increment counter
    RateLimiter.increment_counter(db, bucket_key)
    
    # Verify counter was incremented
    bucket = db.query(RateLimitBucket).filter(
        RateLimitBucket.bucket_key == bucket_key
    ).first()
    
    assert bucket is not None
    assert bucket.request_count == 1


def test_rate_limit_exceeded(db):
    """Test rate limit when exceeded."""
    bucket_key = "test_exceeded"
    
    # Increment counter to limit
    for i in range(settings.rate_limit_requests):
        RateLimiter.increment_counter(db, bucket_key)
    
    # Check should show limit exceeded
    is_limited = RateLimiter.is_rate_limited(db, bucket_key)
    assert is_limited is True


def test_rate_limit_window_expiry(db):
    """Test that rate limit resets after window expires."""
    bucket_key = "test_window"
    
    # Create bucket with old timestamp
    old_bucket = RateLimitBucket(
        bucket_key=bucket_key,
        request_count=settings.rate_limit_requests,
        window_start=datetime.utcnow() - timedelta(seconds=settings.rate_limit_seconds + 1),
    )
    db.add(old_bucket)
    db.commit()
    
    # Check should show not limited (old window should be cleaned up)
    is_limited = RateLimiter.is_rate_limited(db, bucket_key)
    # Should be False because old bucket was deleted and new one created
    assert is_limited is False


def test_multiple_buckets(db):
    """Test that different buckets don't interfere."""
    # Fill bucket 1
    for i in range(settings.rate_limit_requests):
        RateLimiter.increment_counter(db, "bucket1")
    
    # Check bucket 1 is limited
    assert RateLimiter.is_rate_limited(db, "bucket1") is True
    
    # Check bucket 2 is not limited
    assert RateLimiter.is_rate_limited(db, "bucket2") is False
