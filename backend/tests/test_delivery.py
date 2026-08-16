"""Tests for delivery tracking and statistics."""
import pytest
from datetime import datetime
from app.database import Delivery, DeliveryStatus, Rule, Event, EventType
from app.job_queue import JobQueue
from sqlalchemy.exc import IntegrityError


def test_delivery_creation(db):
    """Test creating a delivery record."""
    rule = Rule(
        id="rule_test",
        keyword="TEST",
        keyword_normalized="test",
        dm_message="Test message",
        active=True,
    )
    db.add(rule)
    db.commit()
    
    delivery = Delivery(
        id="dlv_test_123",
        rule_id="rule_test",
        user_id="user_123",
        comment_id="cmt_123",
        event_id="evt_123",
        message="Test message",
        status=DeliveryStatus.PENDING,
    )
    db.add(delivery)
    db.commit()
    
    assert delivery.id == "dlv_test_123"
    assert delivery.status == DeliveryStatus.PENDING


def test_unique_rule_user_delivery_constraint(db):
    """Test that same user cannot be DMed twice for same rule."""
    rule = Rule(
        id="rule_test",
        keyword="TEST",
        keyword_normalized="test",
        dm_message="Test message",
        active=True,
    )
    db.add(rule)
    db.commit()
    
    # Create first delivery
    delivery1 = Delivery(
        id="dlv_1",
        rule_id="rule_test",
        user_id="user_123",
        comment_id="cmt_1",
        event_id="evt_1",
        message="Test message",
        status=DeliveryStatus.PENDING,
    )
    db.add(delivery1)
    db.commit()
    
    # Try to create second delivery for same rule+user
    delivery2 = Delivery(
        id="dlv_2",
        rule_id="rule_test",
        user_id="user_123",
        comment_id="cmt_2",
        event_id="evt_2",
        message="Test message",
        status=DeliveryStatus.PENDING,
    )
    db.add(delivery2)
    
    # Should raise IntegrityError due to unique constraint
    with pytest.raises(IntegrityError):
        db.commit()


def test_event_id_uniqueness(db):
    """Test that event_ids are unique."""
    # Create first event
    event1 = Event(
        event_id="evt_duplicate",
        event_type=EventType.COMMENT_CREATED,
        comment_id="cmt_1",
        user_id="user_1",
        comment_text="Test",
        processing_status="pending",
    )
    db.add(event1)
    db.commit()
    
    # Try to create second event with same event_id
    event2 = Event(
        event_id="evt_duplicate",
        event_type=EventType.COMMENT_CREATED,
        comment_id="cmt_2",
        user_id="user_2",
        comment_text="Test",
        processing_status="pending",
    )
    db.add(event2)
    
    # Should raise IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()


def test_delivery_status_transitions(db):
    """Test delivery status transitions."""
    rule = Rule(
        id="rule_test",
        keyword="TEST",
        keyword_normalized="test",
        dm_message="Test",
        active=True,
    )
    db.add(rule)
    
    delivery = Delivery(
        id="dlv_test",
        rule_id="rule_test",
        user_id="user_123",
        comment_id="cmt_123",
        event_id="evt_123",
        message="Test",
        status=DeliveryStatus.PENDING,
    )
    db.add(delivery)
    db.commit()
    
    # Transition to SENT
    JobQueue.mark_sent(db, delivery.id, "dm_123")
    db.refresh(delivery)
    assert delivery.status == DeliveryStatus.SENT
    assert delivery.external_dm_id == "dm_123"
    
    # Transition to DELIVERED
    JobQueue.mark_delivered(db, delivery.id)
    db.refresh(delivery)
    assert delivery.status == DeliveryStatus.DELIVERED
    assert delivery.delivered_at is not None


def test_delivery_retry_scheduling(db):
    """Test that failed deliveries are scheduled for retry."""
    rule = Rule(
        id="rule_test",
        keyword="TEST",
        keyword_normalized="test",
        dm_message="Test",
        active=True,
    )
    db.add(rule)
    
    delivery = Delivery(
        id="dlv_test",
        rule_id="rule_test",
        user_id="user_123",
        comment_id="cmt_123",
        event_id="evt_123",
        message="Test",
        status=DeliveryStatus.PENDING,
        attempts=0,
    )
    db.add(delivery)
    db.commit()
    
    # Mark as temporary failure
    original_attempts = delivery.attempts
    JobQueue.mark_failed(
        db,
        delivery.id,
        error="Temporary error",
        is_permanent=False,
    )
    
    db.refresh(delivery)
    assert delivery.status == DeliveryStatus.QUEUED
    assert delivery.attempts == original_attempts + 1
    assert delivery.next_attempt_at is not None
    assert delivery.last_error == "Temporary error"


def test_delivery_permanent_failure(db):
    """Test permanent failure handling."""
    rule = Rule(
        id="rule_test",
        keyword="TEST",
        keyword_normalized="test",
        dm_message="Test",
        active=True,
    )
    db.add(rule)
    
    delivery = Delivery(
        id="dlv_test",
        rule_id="rule_test",
        user_id="user_123",
        comment_id="cmt_123",
        event_id="evt_123",
        message="Test",
        status=DeliveryStatus.PENDING,
    )
    db.add(delivery)
    db.commit()
    
    # Mark as permanent failure
    JobQueue.mark_failed(
        db,
        delivery.id,
        error="Invalid request",
        is_permanent=True,
    )
    
    db.refresh(delivery)
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.next_attempt_at is None
    assert delivery.last_error == "Invalid request"


def test_delivery_cancellation(db):
    """Test cancelling a delivery."""
    rule = Rule(
        id="rule_test",
        keyword="TEST",
        keyword_normalized="test",
        dm_message="Test",
        active=True,
    )
    db.add(rule)
    
    delivery = Delivery(
        id="dlv_test",
        rule_id="rule_test",
        user_id="user_123",
        comment_id="cmt_123",
        event_id="evt_123",
        message="Test",
        status=DeliveryStatus.PENDING,
    )
    db.add(delivery)
    db.commit()
    
    # Cancel delivery
    result = JobQueue.cancel_delivery(
        db,
        delivery.id,
        reason="Comment was deleted",
    )
    
    assert result is True
    db.refresh(delivery)
    assert delivery.status == DeliveryStatus.CANCELLED
    assert delivery.last_error == "Comment was deleted"


def test_stats_endpoint(client, db):
    """Test /stats endpoint."""
    response = client.get("/stats")
    assert response.status_code == 200
    
    data = response.json()
    assert "sent" in data
    assert "failed" in data
    assert "queued" in data
    assert "duplicates_blocked" in data
    assert all(isinstance(data[k], int) for k in data.keys())


def test_stats_accuracy(client, db):
    """Test that stats are accurate."""
    # Create rule
    rule = Rule(
        id="rule_test",
        keyword="TEST",
        keyword_normalized="test",
        dm_message="Test",
        active=True,
    )
    db.add(rule)
    db.commit()
    
    # Create deliveries with different statuses
    db.add(Delivery(
        id="dlv_sent",
        rule_id="rule_test",
        user_id="user_1",
        comment_id="cmt_1",
        event_id="evt_1",
        message="Test",
        status=DeliveryStatus.DELIVERED,
        delivered_at=datetime.utcnow(),
    ))
    db.add(Delivery(
        id="dlv_failed",
        rule_id="rule_test",
        user_id="user_2",
        comment_id="cmt_2",
        event_id="evt_2",
        message="Test",
        status=DeliveryStatus.FAILED,
    ))
    db.add(Delivery(
        id="dlv_queued",
        rule_id="rule_test",
        user_id="user_3",
        comment_id="cmt_3",
        event_id="evt_3",
        message="Test",
        status=DeliveryStatus.PENDING,
    ))
    db.commit()
    
    response = client.get("/stats")
    data = response.json()
    
    assert data["sent"] == 1
    assert data["failed"] == 1
    assert data["queued"] >= 1
