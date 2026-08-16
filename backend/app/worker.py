"""Worker process for sending DMs and handling reconciliation."""
import asyncio
import logging
from datetime import datetime, timedelta

from app.config import settings
from app.database import SessionLocal
from app.job_queue import JobQueue
from app.pseudogram_client import PermanentError, PseudoGramClient, RateLimitError, TemporaryError
from app.rate_limiter import RateLimiter

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DeliveryWorker:
    """Worker for sending DMs."""

    def __init__(self):
        self.client = None
        self.running = True

    async def initialize(self):
        self.client = PseudoGramClient()
        logger.info("Delivery worker initialized")

    async def cleanup(self):
        if self.client:
            await self.client.close()
        logger.info("Delivery worker cleaned up")

    async def send_delivery(self, db, delivery):
        """Send a single delivery after reserving rate-limit capacity."""
        try:
            if not RateLimiter.reserve_capacity(db, bucket_key="dm_sends"):
                logger.warning("Rate limit reached; delaying delivery", extra={"delivery_id": delivery.id})
                delivery.next_attempt_at = datetime.utcnow() + timedelta(seconds=settings.initial_retry_delay_seconds)
                db.commit()
                return False

            idempotency_key = f"{delivery.rule_id}:{delivery.user_id}:{delivery.comment_id}"
            response = await self.client.send_dm(
                recipient_user_id=delivery.user_id,
                message=delivery.message,
                comment_id=delivery.comment_id,
                idempotency_key=idempotency_key,
            )
            JobQueue.mark_sent(db=db, delivery_id=delivery.id, external_dm_id=response.get("dm_id"))
            return True

        except RateLimitError as e:
            logger.warning("Rate limit hit; retry scheduled", extra={"delivery_id": delivery.id, "retry_after": e.retry_after})
            retry_delay = e.retry_after or 60
            delivery.next_attempt_at = datetime.utcnow() + timedelta(seconds=retry_delay)
            db.commit()
            return False

        except PermanentError as e:
            logger.error("Permanent error sending DM", extra={"delivery_id": delivery.id, "error": str(e)})
            JobQueue.mark_failed(db=db, delivery_id=delivery.id, error=str(e), is_permanent=True)
            return False

        except TemporaryError as e:
            logger.warning("Temporary error sending DM", extra={"delivery_id": delivery.id, "error": str(e)})
            JobQueue.mark_failed(db=db, delivery_id=delivery.id, error=str(e), is_permanent=False)
            return False

    async def reconcile_delivery(self, db, delivery):
        """Check external status without holding the row under a DB transaction."""
        try:
            if not delivery.external_dm_id:
                logger.warning("No external dm_id to reconcile", extra={"delivery_id": delivery.id})
                return False

            status_response = await self.client.get_dm_status(delivery.external_dm_id)
            status = status_response.get("status")

            logger.debug("Reconciliation status", extra={"delivery_id": delivery.id, "dm_id": delivery.external_dm_id, "status": status})

            if status == "delivered":
                JobQueue.mark_delivered(db, delivery.id)
                return True

            if status == "failed":
                logger.warning("DM delivery failed by API", extra={"delivery_id": delivery.id, "dm_id": delivery.external_dm_id})
                JobQueue.mark_failed(db=db, delivery_id=delivery.id, error="API reported delivery failed", is_permanent=False)
                return False

            if status == "queued":
                logger.debug("DM still queued", extra={"delivery_id": delivery.id, "dm_id": delivery.external_dm_id})
                return False

            logger.warning("Unknown reconciliation status", extra={"delivery_id": delivery.id, "status": status})
            return False

        except PermanentError as e:
            logger.error("Permanent error during reconciliation", extra={"delivery_id": delivery.id, "error": str(e)})
            return False

        except TemporaryError as e:
            logger.warning("Temporary error during reconciliation", extra={"delivery_id": delivery.id, "error": str(e)})
            return False

    async def process_deliveries(self):
        db = SessionLocal()
        try:
            deliveries = JobQueue.get_pending_deliveries(db, limit=10)
            if deliveries:
                logger.info("Processing deliveries", extra={"count": len(deliveries)})
            for delivery in deliveries:
                await self.send_delivery(db, delivery)
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error("Error processing deliveries", extra={"error": str(e)})
        finally:
            db.close()

    async def reconcile_deliveries(self):
        if not settings.reconciliation_enabled:
            return

        db = SessionLocal()
        try:
            deliveries = JobQueue.get_pending_reconciliations(db, limit=settings.reconciliation_max_batch_size)
            if deliveries:
                logger.info("Reconciling deliveries", extra={"count": len(deliveries)})
            for delivery in deliveries:
                await self.reconcile_delivery(db, delivery)
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error("Error reconciling deliveries", extra={"error": str(e)})
        finally:
            db.close()

    async def run(self):
        await self.initialize()
        try:
            while self.running:
                await self.process_deliveries()
                await self.reconcile_deliveries()
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Worker interrupted")
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            await self.cleanup()


async def main():
    worker = DeliveryWorker()
    await worker.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
