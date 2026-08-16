"""Database setup and ORM models."""
from datetime import datetime
import enum

from sqlalchemy import Column, DateTime, Boolean, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class EventType(str, enum.Enum):
    """Event types from webhook."""
    COMMENT_CREATED = "comment.created"
    COMMENT_DELETED = "comment.deleted"


class EventProcessingStatus(str, enum.Enum):
    """Processing status of an event."""
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class DeliveryStatus(str, enum.Enum):
    """Status of a delivery attempt."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Rule(Base):
    """Rule for matching comments and sending DMs."""
    __tablename__ = "rules"

    id = Column(String(36), primary_key=True)
    keyword = Column(String(255), nullable=False, index=True)
    keyword_normalized = Column(String(255), nullable=False, index=True)
    dm_message = Column(Text, nullable=False)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deliveries = relationship("Delivery", back_populates="rule", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Rule {self.id}: {self.keyword}>"


class Event(Base):
    """Webhook event from PseudoGram API."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(255), nullable=False, unique=True, index=True)
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    comment_id = Column(String(255), nullable=True, index=True)
    post_id = Column(String(255), nullable=True)
    user_id = Column(String(255), nullable=True, index=True)
    username = Column(String(255), nullable=True)
    comment_text = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processing_status = Column(SQLEnum(EventProcessingStatus), default=EventProcessingStatus.PENDING, index=True)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_event_id_processing", "event_id", "processing_status"),
        Index("idx_comment_user_type", "comment_id", "user_id", "event_type"),
    )

    def __repr__(self):
        return f"<Event {self.event_id}: {self.event_type}>"


class Delivery(Base):
    """Delivery record for a matched rule."""
    __tablename__ = "deliveries"

    id = Column(String(36), primary_key=True)
    rule_id = Column(String(36), ForeignKey("rules.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    comment_id = Column(String(255), nullable=False, index=True)
    event_id = Column(String(255), nullable=False, index=True)
    message = Column(Text, nullable=False)

    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING, index=True)
    external_dm_id = Column(String(255), nullable=True, index=True)
    attempts = Column(Integer, default=0)
    next_attempt_at = Column(DateTime, nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    delivered_at = Column(DateTime, nullable=True)

    rule = relationship("Rule", back_populates="deliveries")

    __table_args__ = (
        UniqueConstraint("rule_id", "user_id", name="uq_rule_user_delivery"),
        Index("idx_status_next_attempt", "status", "next_attempt_at"),
        Index("idx_rule_user_status", "rule_id", "user_id", "status"),
    )

    def __repr__(self):
        return f"<Delivery {self.id}: {self.status}>"


class DuplicateBlocked(Base):
    """Tracks logical duplicate DM blocks for statistics."""
    __tablename__ = "duplicate_blocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(255), nullable=False, index=True)
    rule_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    comment_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "rule_id", "user_id", name="uq_duplicate_block_event_rule_user"),
        Index("idx_duplicate_block_rule_user", "rule_id", "user_id"),
    )


class RateLimitBucket(Base):
    """Rate limiting state for DM sends."""
    __tablename__ = "rate_limit_buckets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bucket_key = Column(String(255), nullable=False, unique=True, index=True)
    request_count = Column(Integer, default=0)
    window_start = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<RateLimitBucket {self.bucket_key}: {self.request_count}>"
