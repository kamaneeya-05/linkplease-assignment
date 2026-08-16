"""Pydantic models for API requests and responses."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class RuleCreateRequest(BaseModel):
    """Request to create a rule."""
    keyword: str = Field(..., min_length=1, max_length=255)
    dm_message: str = Field(..., min_length=1, max_length=5000)


class RuleResponse(BaseModel):
    """Response with rule details."""
    rule_id: str
    keyword: str
    dm_message: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class WebhookEventData(BaseModel):
    """Data object in webhook event."""
    comment_id: Optional[str] = None
    post_id: Optional[str] = None
    text: Optional[str] = None
    created_at: Optional[datetime] = None
    from_user: Optional[Dict[str, Any]] = Field(None, alias="from")
    
    class Config:
        populate_by_name = True


class WebhookEventPayload(BaseModel):
    """Webhook event payload from PseudoGram API."""
    event_id: str
    event_type: str
    sent_at: datetime
    data: WebhookEventData
    
    class Config:
        populate_by_name = True


class DeliveryStatusEnum(str, Enum):
    """Delivery status values."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryResponse(BaseModel):
    """Response with delivery details."""
    delivery_id: str
    rule_id: str
    user_id: str
    comment_id: str
    status: DeliveryStatusEnum
    attempts: int
    created_at: datetime
    updated_at: datetime
    delivered_at: Optional[datetime] = None
    last_error: Optional[str] = None
    
    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    """Stats response."""
    sent: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    queued: int = Field(..., ge=0)
    duplicates_blocked: int = Field(..., ge=0)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    version: str


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str
    code: Optional[str] = None
