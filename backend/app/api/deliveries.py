"""Delivery activity endpoint."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import Delivery, Rule, get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/deliveries")
async def list_deliveries(db: Session = Depends(get_db)) -> List[dict]:
    """Return actual database-backed delivery activity for the dashboard."""
    try:
        rows = (
            db.query(Delivery, Rule.keyword)
            .join(Rule, Rule.id == Delivery.rule_id)
            .order_by(Delivery.updated_at.desc())
            .all()
        )
        result = []
        for delivery, keyword in rows:
            result.append(
                {
                    "delivery_id": delivery.id,
                    "rule_id": delivery.rule_id,
                    "keyword": keyword,
                    "user_id": delivery.user_id,
                    "comment_id": delivery.comment_id,
                    "status": delivery.status.value,
                    "attempts": delivery.attempts,
                    "external_dm_id": delivery.external_dm_id,
                    "last_error": delivery.last_error,
                    "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
                    "updated_at": delivery.updated_at.isoformat() if delivery.updated_at else None,
                    "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
                }
            )
        return result
    except Exception as exc:
        logger.error("Failed to list deliveries", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to retrieve delivery activity")
