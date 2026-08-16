"""Rules management endpoints."""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db, Rule
from app.models import RuleCreateRequest, RuleResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: RuleCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new rule.
    
    Request:
        keyword: The keyword to match (case-insensitive)
        dm_message: The message to DM when keyword is matched
    
    Response:
        rule_id: Unique rule identifier
        keyword: The keyword
        dm_message: The message
        created_at: Creation timestamp
    """
    rule_id = f"rule_{uuid.uuid4().hex[:12]}"
    keyword_normalized = request.keyword.lower()
    
    try:
        rule = Rule(
            id=rule_id,
            keyword=request.keyword,
            keyword_normalized=keyword_normalized,
            dm_message=request.dm_message,
            active=True,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        
        logger.info(
            f"Rule created",
            extra={
                "rule_id": rule_id,
                "keyword": request.keyword,
            }
        )
        
        return RuleResponse(
            rule_id=rule.id,
            keyword=rule.keyword,
            dm_message=rule.dm_message,
            created_at=rule.created_at,
        )
    
    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to create rule",
            extra={
                "keyword": request.keyword,
                "error": str(e),
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rule",
        )


@router.get("/rules")
async def list_rules(db: Session = Depends(get_db)):
    """List all active rules."""
    rules = db.query(Rule).filter(Rule.active == True).all()
    return [
        RuleResponse(
            rule_id=r.id,
            keyword=r.keyword,
            dm_message=r.dm_message,
            created_at=r.created_at,
        )
        for r in rules
    ]
