"""Statistics endpoint."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import Delivery, DeliveryStatus, DuplicateBlocked, get_db
from app.models import StatsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Return the assignment-defined statistics.

    - sent: confirmed delivered by the external API
    - failed: permanent failures after retries
    - queued: pending, queued, or waiting on external reconciliation
    - duplicates_blocked: logical duplicates prevented by the rule+user uniqueness guard
    """
    try:
        sent_count = db.query(func.count(Delivery.id)).filter(
            Delivery.status == DeliveryStatus.DELIVERED
        ).scalar() or 0

        failed_count = db.query(func.count(Delivery.id)).filter(
            Delivery.status == DeliveryStatus.FAILED
        ).scalar() or 0

        queued_count = db.query(func.count(Delivery.id)).filter(
            Delivery.status.in_([
                DeliveryStatus.PENDING,
                DeliveryStatus.QUEUED,
                DeliveryStatus.SENT,
            ])
        ).scalar() or 0

        duplicates_blocked = db.query(func.count(DuplicateBlocked.id)).scalar() or 0

        logger.info(
            "Stats retrieved",
            extra={
                "sent": sent_count,
                "failed": failed_count,
                "queued": queued_count,
                "duplicates_blocked": duplicates_blocked,
            },
        )

        return StatsResponse(
            sent=sent_count,
            failed=failed_count,
            queued=queued_count,
            duplicates_blocked=duplicates_blocked,
        )
    except Exception as exc:
        logger.error("Failed to retrieve stats", extra={"error": str(exc)})
        return StatsResponse(
            sent=0,
            failed=0,
            queued=0,
            duplicates_blocked=0,
        )
