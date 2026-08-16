"""Webhook endpoint for receiving comment events."""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Delivery, Event, EventProcessingStatus, EventType, Rule, get_db
from app.job_queue import JobQueue
from app.webhook_signature import verify_webhook_signature

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_webhook_event(db: Session, event_data: dict) -> int:
    """Persist and process a webhook event durably before returning HTTP 200."""
    event_id = event_data.get("event_id")
    event_type = event_data.get("event_type")
    if not event_id:
        raise ValueError("Webhook event missing event_id")

    try:
        event = Event(
            event_id=event_id,
            event_type=EventType(event_type),
            comment_id=event_data.get("data", {}).get("comment_id"),
            post_id=event_data.get("data", {}).get("post_id"),
            user_id=event_data.get("data", {}).get("from", {}).get("user_id"),
            username=event_data.get("data", {}).get("from", {}).get("username"),
            comment_text=event_data.get("data", {}).get("text"),
            sent_at=(
                datetime.fromisoformat(event_data.get("sent_at", "").replace("Z", "+00:00"))
                if event_data.get("sent_at")
                else None
            ),
            processing_status=EventProcessingStatus.PENDING,
        )
        db.add(event)
        db.commit()
        logger.info("Event persisted", extra={"event_id": event_id, "event_type": event_type})
    except IntegrityError:
        db.rollback()
        logger.info("Duplicate event received", extra={"event_id": event_id, "event_type": event_type})
        return 0

    try:
        if event_type == "comment.created":
            return await process_comment_created(db, event)
        if event_type == "comment.deleted":
            return await process_comment_deleted(db, event)
        logger.warning("Unknown event type", extra={"event_id": event_id, "event_type": event_type})
        return 0
    except Exception as exc:
        logger.error("Error processing webhook event", extra={"error": str(exc), "event_id": event_id})
        raise


async def process_comment_created(db: Session, event: Event) -> int:
    """Match a comment-created event to active rules and create durable delivery jobs."""
    if not event.comment_text or not event.user_id:
        logger.warning(
            "Comment event missing required fields",
            extra={"event_id": event.event_id, "has_text": bool(event.comment_text), "has_user_id": bool(event.user_id)},
        )
        event.processing_status = EventProcessingStatus.PROCESSED
        event.processed_at = datetime.utcnow()
        db.commit()
        return 0

    existing_deleted = db.query(Event).filter(
        Event.comment_id == event.comment_id,
        Event.event_type == EventType.COMMENT_DELETED,
    ).first()
    if existing_deleted:
        logger.info("Comment deleted before creation processing; skipping delivery", extra={"comment_id": event.comment_id})
        event.processing_status = EventProcessingStatus.PROCESSED
        event.processed_at = datetime.utcnow()
        db.commit()
        return 0

    comment_text_lower = event.comment_text.lower()
    deliveries_enqueued = 0
    rules = db.query(Rule).filter(Rule.active == True).all()

    for rule in rules:
        if rule.keyword_normalized not in comment_text_lower:
            continue

        logger.debug(
            "Rule matched",
            extra={"rule_id": rule.id, "keyword": rule.keyword, "event_id": event.event_id, "user_id": event.user_id},
        )

        delivery_id = await JobQueue.enqueue_delivery(
            db=db,
            rule_id=rule.id,
            user_id=event.user_id,
            comment_id=event.comment_id,
            event_id=event.event_id,
            message=rule.dm_message,
        )

        if delivery_id is not None:
            deliveries_enqueued += 1
        else:
            logger.debug("Delivery already exists for this rule/user", extra={"rule_id": rule.id, "user_id": event.user_id})

    event.processing_status = EventProcessingStatus.PROCESSED
    event.processed_at = datetime.utcnow()
    db.commit()

    logger.info(
        "Comment event processed",
        extra={"event_id": event.event_id, "user_id": event.user_id, "deliveries_enqueued": deliveries_enqueued},
    )
    return deliveries_enqueued


async def process_comment_deleted(db: Session, event: Event) -> int:
    """Cancel pending or queued deliveries for the deleted comment but do not unsend accepted DMs."""
    comment_id = event.comment_id
    if not comment_id:
        logger.warning("Delete event missing comment_id", extra={"event_id": event.event_id})
        event.processing_status = EventProcessingStatus.PROCESSED
        event.processed_at = datetime.utcnow()
        db.commit()
        return 0

    deliveries = db.query(Delivery).filter(Delivery.comment_id == comment_id).all()
    cancelled_count = 0
    for delivery in deliveries:
        if delivery.status in ["pending", "queued"]:
            JobQueue.cancel_delivery(db=db, delivery_id=delivery.id, reason="Comment was deleted")
            cancelled_count += 1

    event.processing_status = EventProcessingStatus.PROCESSED
    event.processed_at = datetime.utcnow()
    db.commit()

    logger.info("Delete event processed", extra={"event_id": event.event_id, "comment_id": comment_id, "cancelled_count": cancelled_count})
    return cancelled_count


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive webhook events, persist them durably, and return 200 only after the DB commit."""
    try:
        body = await request.body()
        signature_header = request.headers.get("X-PseudoGram-Signature")

        verify_webhook_signature(
            body=body,
            signature_header=signature_header,
            secret=settings.webhook_secret,
            verify_enabled=settings.verify_webhook_signature,
        )

        try:
            event_data = json.loads(body)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse webhook JSON", extra={"error": str(exc)})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

        event_id = event_data.get("event_id")
        logger.info("Webhook received", extra={"event_id": event_id, "event_type": event_data.get("event_type")})

        await process_webhook_event(db, event_data)
        return {"status": "received"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error in webhook handler", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error")
