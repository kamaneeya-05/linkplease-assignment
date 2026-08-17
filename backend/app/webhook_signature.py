"""Webhook signature verification and event parsing."""
import hmac
import hashlib
import json
import logging
from typing import Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_TEMPORARY_TEST_WEBHOOK_SECRET = "test-webhook-secret"


def _log_temporary_invalid_signature_diagnostic(
    *,
    body: bytes,
    algorithm: str,
    provided_signature: str,
    api_key: str,
    webhook_secret: Optional[str],
    content_type: Optional[str],
    user_agent: Optional[str],
    content_length: Optional[str],
) -> None:
    """Log non-secret, temporary diagnostics for an invalid webhook signature."""
    try:
        payload = json.loads(body)
        has_event_id = isinstance(payload, dict) and "event_id" in payload
        has_event_type = isinstance(payload, dict) and "event_type" in payload
        has_sent_at = isinstance(payload, dict) and "sent_at" in payload
        has_data = isinstance(payload, dict) and "data" in payload
    except (json.JSONDecodeError, UnicodeDecodeError):
        has_event_id = has_event_type = has_sent_at = has_data = False

    api_key_match = hmac.compare_digest(
        hmac.new(api_key.encode(), body, hashlib.sha256).hexdigest(),
        provided_signature,
    )
    webhook_secret_match = (
        hmac.compare_digest(
            hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest(),
            provided_signature,
        )
        if webhook_secret
        else None
    )
    test_secret_match = hmac.compare_digest(
        hmac.new(_TEMPORARY_TEST_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest(),
        provided_signature,
    )

    logger.warning(
        "TEMPORARY webhook signature diagnostic: "
        "body_length=%d body_sha256=%s signature_algorithm=%s signature_length=%d "
        "signature_prefix=%s... api_key_match=%s webhook_secret_match=%s "
        "test_secret_match=%s content_type=%s user_agent=%s content_length=%s "
        "has_event_id=%s has_event_type=%s has_sent_at=%s has_data=%s",
        len(body),
        hashlib.sha256(body).hexdigest(),
        algorithm,
        len(provided_signature),
        provided_signature[:16],
        api_key_match,
        webhook_secret_match,
        test_secret_match,
        content_type,
        user_agent,
        content_length,
        has_event_id,
        has_event_type,
        has_sent_at,
        has_data,
    )


def verify_webhook_signature(
    body: bytes,
    signature_header: Optional[str],
    secret: Optional[str],
    verify_enabled: bool = True,
    webhook_secret: Optional[str] = None,
    content_type: Optional[str] = None,
    user_agent: Optional[str] = None,
    content_length: Optional[str] = None,
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
        _log_temporary_invalid_signature_diagnostic(
            body=body,
            algorithm=algo,
            provided_signature=provided_sig,
            api_key=secret,
            webhook_secret=webhook_secret,
            content_type=content_type,
            user_agent=user_agent,
            content_length=content_length,
        )
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    logger.debug("Webhook signature verified")
    return True
