"""Durable job queue and worker system."""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Delivery, DeliveryStatus, DuplicateBlocked, SessionLocal

logger = logging.getLogger(__name__)


class JobQueue:
    """Durable delivery queue with atomic duplicate protection and lease-based claiming."""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    @staticmethod
    def get_db():
        return SessionLocal()

    @staticmethod
    def build_delivery_id(event_id: str, rule_id: str, user_id: str) -> str:
        """Generate a deterministic delivery ID that fits the schema and remains stable per rule/user/event."""
        return f"dlv_{uuid.uuid5(uuid.NAMESPACE_URL, f'{event_id}:{rule_id}:{user_id}').hex}"

    @staticmethod
    async def enqueue_delivery(
        db: Session,
        rule_id: str,
        user_id: str,
        comment_id: str,
        event_id: str,
        message: str,
    ) -> Optional[str]:
        """Insert a delivery row only if this rule+user pair has not already been used."""
        delivery_id = JobQueue.build_delivery_id(event_id=event_id, rule_id=rule_id, user_id=user_id)

        try:
            delivery = Delivery(
                id=delivery_id,
                rule_id=rule_id,
                user_id=user_id,
                comment_id=comment_id,
                event_id=event_id,
                message=message,
                status=DeliveryStatus.PENDING,
                next_attempt_at=datetime.utcnow(),
            )
            db.add(delivery)
            db.commit()
            logger.info(
                "Delivery enqueued",
                extra={
                    "delivery_id": delivery_id,
                    "rule_id": rule_id,
                    "user_id": user_id,
                    "comment_id": comment_id,
                },
            )
            return delivery_id
        except IntegrityError as exc:
            db.rollback()
            if "uq_rule_user_delivery" in str(exc).lower():
                dup = DuplicateBlocked(
                    event_id=event_id,
                    rule_id=rule_id,
                    user_id=user_id,
                    comment_id=comment_id,
                )
                try:
                    db.add(dup)
                    db.commit()
                except IntegrityError:
                    db.rollback()
                logger.debug(
                    "Duplicate delivery blocked; logical duplicate recorded",
                    extra={"rule_id": rule_id, "user_id": user_id, "event_id": event_id},
                )
                return None
            logger.error("Failed to enqueue delivery", extra={"delivery_id": delivery_id, "error": str(exc)})
            raise
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_pending_deliveries(
        db: Session,
        limit: int = 10,
    ) -> list:
        """Claim queued deliveries without holding the DB open while sending external HTTP."""
        now = datetime.utcnow()
        stmt = (
            select(Delivery)
            .where(
                and_(
                    Delivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.QUEUED]),
                    Delivery.next_attempt_at <= now,
                )
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        deliveries = db.execute(stmt).scalars().all()

        if not deliveries:
            return []

        for delivery in deliveries:
            delivery.status = DeliveryStatus.QUEUED
            delivery.updated_at = now
            delivery.lease_expires_at = now + timedelta(minutes=5)

        db.commit()
        return deliveries

    @staticmethod
    def get_pending_reconciliations(
        db: Session,
        limit: int = 10,
    ) -> list:
        """Get deliveries awaiting reconciliation with the external DM status API."""
        stmt = (
            select(Delivery)
            .where(
                and_(
                    Delivery.status == DeliveryStatus.SENT,
                    Delivery.external_dm_id.isnot(None),
                )
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()

    @staticmethod
    def mark_sent(
        db: Session,
        delivery_id: str,
        external_dm_id: str,
    ) -> bool:
        """Mark delivery as accepted/queued by the external API."""
        stmt = (
            update(Delivery)
            .where(Delivery.id == delivery_id)
            .values(
                status=DeliveryStatus.SENT,
                external_dm_id=external_dm_id,
                updated_at=datetime.utcnow(),
                lease_expires_at=None,
            )
        )
        db.execute(stmt)
        db.commit()
        logger.info("Delivery marked as sent", extra={"delivery_id": delivery_id, "dm_id": external_dm_id})
        return True

    @staticmethod
    def mark_delivered(
        db: Session,
        delivery_id: str,
    ) -> bool:
        stmt = (
            update(Delivery)
            .where(Delivery.id == delivery_id)
            .values(
                status=DeliveryStatus.DELIVERED,
                updated_at=datetime.utcnow(),
                delivered_at=datetime.utcnow(),
                lease_expires_at=None,
            )
        )
        db.execute(stmt)
        db.commit()
        logger.info("Delivery marked as delivered", extra={"delivery_id": delivery_id})
        return True

    @staticmethod
    def mark_failed(
        db: Session,
        delivery_id: str,
        error: Optional[str] = None,
        is_permanent: bool = False,
    ) -> bool:
        """Move a delivery into queued retry or permanent failure state."""
        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
        if delivery is None:
            return False

        if is_permanent:
            status = DeliveryStatus.FAILED
            next_attempt = None
        else:
            status = DeliveryStatus.QUEUED
            attempts = delivery.attempts + 1
            delay = min(
                settings.initial_retry_delay_seconds * (settings.retry_backoff_multiplier ** max(attempts - 1, 0)),
                settings.max_retry_delay_seconds,
            )
            next_attempt = datetime.utcnow() + timedelta(seconds=int(delay))

        stmt = (
            update(Delivery)
            .where(Delivery.id == delivery_id)
            .values(
                status=status,
                attempts=delivery.attempts + 1,
                next_attempt_at=next_attempt,
                last_error=error,
                updated_at=datetime.utcnow(),
                lease_expires_at=None,
            )
        )
        db.execute(stmt)
        db.commit()

        logger.log(
            logging.ERROR if is_permanent else logging.WARNING,
            "Delivery marked as %s",
            extra={"delivery_id": delivery_id, "error": error, "is_permanent": is_permanent},
        )
        return True

    @staticmethod
    def cancel_delivery(
        db: Session,
        delivery_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        stmt = (
            update(Delivery)
            .where(
                and_(
                    Delivery.id == delivery_id,
                    Delivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.QUEUED]),
                )
            )
            .values(
                status=DeliveryStatus.CANCELLED,
                last_error=reason,
                updated_at=datetime.utcnow(),
            )
        )
        result = db.execute(stmt)
        db.commit()

        if result.rowcount > 0:
            logger.info("Delivery cancelled", extra={"delivery_id": delivery_id, "reason": reason})
            return True

        logger.debug("Could not cancel delivery (may already be sent)", extra={"delivery_id": delivery_id})
        return False
