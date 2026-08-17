"""Webhook signature verification and event parsing."""
import hmac
import hashlib
import logging
from typing import Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def verify_webhook_signature(
    body: bytes,
    signature_header: Optional[str],
    secret: Optional[str],
    verify_enabled: bool = True,
) -> bool:
    """
    Verify webhook signature using HMAC-SHA256.

    Args:
        body: Raw request body bytes
        signature_header: X-PseudoGram-Signature header value
        secret: Secret key (API key)
        verify_enabled: Whether verification is enabled

    Returns:
        True if signature is valid or verification is disabled

    Raises:
        HTTPException: If signature is invalid
    """
    if not verify_enabled:
        logger.debug("Webhook signature verification disabled")
        return True

    if not signature_header:
        logger.warning("Missing X-PseudoGram-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    if not secret:
        logger.error("Webhook secret not configured")
        raise HTTPException(status_code=500, detail="Server misconfigured")

    # Parse signature header: "sha256=<hex>"
    try:
        algo, provided_sig = signature_header.split("=", 1)
        if algo != "sha256":
            logger.warning(f"Unsupported signature algorithm: {algo}")
            raise HTTPException(status_code=400, detail="Unsupported algorithm")
    except ValueError:
        logger.warning(f"Invalid signature header format: {signature_header}")
        raise HTTPException(status_code=400, detail="Invalid signature format")

    # Calculate expected signature
    computed_sig = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    if not hmac.compare_digest(computed_sig, provided_sig):
        logger.warning(
            f"Invalid webhook signature: "
            f"provided={provided_sig[:16]}... "
            f"computed={computed_sig[:16]}..."
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    logger.debug("Webhook signature verified")
    return True
