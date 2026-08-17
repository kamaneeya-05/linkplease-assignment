"""Tests for delivery-worker error handling."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import Delivery, DeliveryStatus, Rule
from app.job_queue import JobQueue
from app.pseudogram_client import PermanentError
from app.worker import DeliveryWorker


@pytest.mark.asyncio
async def test_permanent_reconciliation_error_marks_delivery_failed(db):
    """A terminal status lookup error must not leave a delivery in SENT."""
    rule = Rule(id="rule_reconcile", keyword="TEST", keyword_normalized="test", dm_message="Test")
    delivery = Delivery(
        id="dlv_reconcile",
        rule_id=rule.id,
        user_id="user_reconcile",
        comment_id="cmt_reconcile",
        event_id="evt_reconcile",
        message="Test",
        status=DeliveryStatus.SENT,
        external_dm_id="dm_missing",
    )
    db.add_all([rule, delivery])
    db.commit()

    worker = DeliveryWorker()
    worker.client = MagicMock()
    worker.client.get_dm_status = AsyncMock(side_effect=PermanentError("DM not found: dm_missing"))

    assert await worker.reconcile_delivery(db, delivery) is False

    db.refresh(delivery)
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.last_error == "DM not found: dm_missing"
    assert JobQueue.get_pending_reconciliations(db) == []
