"""Tests for webhook endpoints."""
import pytest
import json
import hmac
import hashlib
from app.database import Event, Delivery, Rule, EventType, DeliveryStatus
from app.config import settings


def sign_payload(payload: bytes, secret: str) -> str:
    """Create HMAC-SHA256 signature for payload."""
    return "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()


def test_webhook_signature_verification(client, db, sample_webhook_event):
    """Test webhook signature verification."""
    payload = json.dumps(sample_webhook_event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 200


def test_webhook_invalid_signature(client, sample_webhook_event):
    """Test webhook rejects invalid signature."""
    payload = json.dumps(sample_webhook_event).encode()
    invalid_signature = "sha256=invalid"
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": invalid_signature,
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 401


def test_webhook_rejects_api_key_signature(client, sample_webhook_event):
    """The API credential must not be accepted in place of the webhook secret."""
    payload = json.dumps(sample_webhook_event).encode()
    api_key_signature = sign_payload(payload, settings.pseudogram_api_key)

    response = client.post(
        "/webhook",
        content=payload,
        headers={"X-PseudoGram-Signature": api_key_signature},
    )

    assert response.status_code == 401


def test_webhook_missing_signature(client, sample_webhook_event):
    """Test webhook rejects missing signature."""
    payload = json.dumps(sample_webhook_event).encode()
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_webhook_comment_created_with_matching_rule(client, db, sample_rule, sample_webhook_event):
    """Test webhook processing for matching comment."""
    payload = json.dumps(sample_webhook_event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 200
    
    # Wait a bit for background processing to complete
    import time
    time.sleep(0.5)


def test_webhook_comment_created_persists_pending_delivery(client, db, sample_rule, sample_webhook_event):
    """A valid comment.created webhook must commit a durable pending delivery for matching rules."""
    payload = json.dumps(sample_webhook_event).encode()
    signature = sign_payload(payload, settings.webhook_secret)

    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200

    delivery = db.query(Delivery).filter(
        Delivery.event_id == sample_webhook_event["event_id"],
        Delivery.rule_id == "rule_test_123",
    ).first()

    assert delivery is not None
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempts == 0


def test_webhook_duplicate_event_id(client, db, sample_rule, sample_webhook_event):
    """Test that duplicate event_ids are blocked."""
    payload = json.dumps(sample_webhook_event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    # Send same event twice
    response1 = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response1.status_code == 200
    
    response2 = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response2.status_code == 200
    
    # Verify only one event was stored
    events = db.query(Event).filter(Event.event_id == "evt_test_123").all()
    assert len(events) == 1


def test_webhook_case_insensitive_matching(client, db, sample_webhook_event):
    """Test that keyword matching is case-insensitive."""
    # Create rule with uppercase keyword
    rule = Rule(
        id="rule_case_test",
        keyword="HELLO",
        keyword_normalized="hello",
        dm_message="Hi there!",
        active=True,
    )
    db.add(rule)
    db.commit()
    
    # Send webhook with lowercase mention
    event = sample_webhook_event.copy()
    event["event_id"] = "evt_case_test"
    event["data"]["text"] = "hello there, how are you?"
    
    payload = json.dumps(event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 200


def test_webhook_keyword_substring_match(client, db, sample_webhook_event):
    """Test that keyword matches as substring."""
    rule = Rule(
        id="rule_substring_test",
        keyword="WORLD",
        keyword_normalized="world",
        dm_message="Hello!",
        active=True,
    )
    db.add(rule)
    db.commit()
    
    event = sample_webhook_event.copy()
    event["event_id"] = "evt_substring_test"
    event["data"]["text"] = "Hello beautiful world!"
    
    payload = json.dumps(event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 200


def test_webhook_non_matching_comment(client, db, sample_rule, sample_webhook_event):
    """Test webhook with non-matching comment."""
    event = sample_webhook_event.copy()
    event["event_id"] = "evt_nomatch"
    event["data"]["text"] = "This has no keywords"
    
    payload = json.dumps(event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 200


def test_webhook_comment_deleted(client, db, sample_webhook_event):
    """Test comment.deleted event processing."""
    event = sample_webhook_event.copy()
    event["event_id"] = "evt_delete_test"
    event["event_type"] = "comment.deleted"
    event["data"]["text"] = None
    
    payload = json.dumps(event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    assert response.status_code == 200


def test_webhook_returns_quickly(client, db, sample_rule, sample_webhook_event):
    """Test that webhook returns quickly (doesn't block on DM delivery)."""
    import time
    payload = json.dumps(sample_webhook_event).encode()
    signature = sign_payload(payload, settings.webhook_secret)
    
    start = time.time()
    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-PseudoGram-Signature": signature,
            "Content-Type": "application/json",
        }
    )
    elapsed = time.time() - start
    
    assert response.status_code == 200
    # Should return in less than 1 second (not waiting for DM sends)
    assert elapsed < 1.0
