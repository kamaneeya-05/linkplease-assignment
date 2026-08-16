"""Test configuration and fixtures."""
import os
from datetime import datetime

os.environ.setdefault("PSEUDOGRAM_API_KEY", "test-api-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("VERIFY_WEBHOOK_SIGNATURE", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.main import app
from app.database import Base, get_db

settings.pseudogram_api_key = "test-api-key"
settings.webhook_secret = "test-webhook-secret"
settings.verify_webhook_signature = True

TEST_DATABASE_URL = "sqlite://"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client."""
    def override_get_db():
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_rule(db):
    """Create a sample rule for testing."""
    from app.database import Rule

    rule = Rule(
        id="rule_test_123",
        keyword="PRICE",
        keyword_normalized="price",
        dm_message="Here's the price list: $99.99",
        active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@pytest.fixture
def sample_webhook_event():
    """Create a sample webhook event."""
    return {
        "event_id": "evt_test_123",
        "event_type": "comment.created",
        "sent_at": "2024-01-01T00:00:00Z",
        "data": {
            "comment_id": "cmt_123",
            "post_id": "post_123",
            "text": "What's the PRICE?",
            "created_at": "2024-01-01T00:00:00Z",
            "from": {
                "user_id": "user_456",
                "username": "testuser",
            },
        },
    }
