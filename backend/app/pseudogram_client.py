"""PseudoGram API client for sending DMs and checking delivery status."""
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


class PseudoGramAPIError(Exception):
    """Base exception for PseudoGram API errors."""
    pass


class RateLimitError(PseudoGramAPIError):
    """Rate limit error."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after} seconds")


class PermanentError(PseudoGramAPIError):
    """Permanent error that should not be retried."""
    pass


class TemporaryError(PseudoGramAPIError):
    """Temporary error that should be retried."""
    pass


class PseudoGramClient:
    """Client for PseudoGram API."""
    
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
    ):
        self.api_key = api_key or settings.pseudogram_api_key
        self.base_url = (base_url or settings.pseudogram_base_url).rstrip("/")
        self.client = httpx.AsyncClient(
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    
    async def send_dm(
        self,
        recipient_user_id: str,
        message: str,
        comment_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a DM via PseudoGram API.

        Supported success responses are 200 and 202. A usable dm_id is required for either status.
        """
        url = f"{self.base_url}/v1/dm/send"
        payload = {
            "recipient_user_id": recipient_user_id,
            "message": message,
            "comment_id": comment_id,
        }
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            logger.debug(
                "Sending DM",
                extra={
                    "recipient_user_id": recipient_user_id,
                    "comment_id": comment_id,
                    "idempotency_key": idempotency_key,
                }
            )

            response = await self.client.post(
                url,
                json=payload,
                headers=headers,
            )

            if response.status_code in (200, 202):
                try:
                    data = response.json()
                except ValueError as exc:
                    raise TemporaryError(f"Invalid JSON success response: {exc}") from exc

                dm_id = data.get("dm_id")
                if not dm_id:
                    raise TemporaryError("Successful DM send response missing dm_id")

                logger.info(
                    "DM accepted",
                    extra={
                        "dm_id": dm_id,
                        "recipient_user_id": recipient_user_id,
                        "status": data.get("status"),
                    }
                )
                return data

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_after = int(retry_after) if retry_after else None
                error_data = response.json()
                logger.warning(
                    "Rate limited",
                    extra={
                        "retry_after": retry_after,
                        "recipient_user_id": recipient_user_id,
                    }
                )
                raise RateLimitError(retry_after=retry_after)

            if response.status_code == 500:
                error_data = response.json()
                logger.warning(
                    "API server error",
                    extra={
                        "error": error_data.get("error"),
                        "recipient_user_id": recipient_user_id,
                    }
                )
                raise TemporaryError(f"API error: {error_data.get('error')}")

            if response.status_code == 400:
                error_data = response.json()
                logger.error(
                    "Invalid request",
                    extra={
                        "error": error_data.get("error"),
                        "detail": error_data.get("detail"),
                        "recipient_user_id": recipient_user_id,
                    }
                )
                raise PermanentError(
                    f"Invalid request: {error_data.get('detail', error_data.get('error'))}"
                )

            logger.error(
                "Unexpected status code",
                extra={
                    "status_code": response.status_code,
                    "recipient_user_id": recipient_user_id,
                }
            )
            raise TemporaryError(f"Unexpected status code: {response.status_code}")

        except httpx.TimeoutException:
            logger.warning(
                "Timeout sending DM",
                extra={"recipient_user_id": recipient_user_id}
            )
            raise TemporaryError("Request timeout")
        except httpx.RequestError as e:
            logger.warning(
                "Network error sending DM",
                extra={
                    "recipient_user_id": recipient_user_id,
                    "error": str(e),
                }
            )
            raise TemporaryError(f"Network error: {str(e)}")
    
    async def get_dm_status(self, dm_id: str) -> Dict[str, Any]:
        """
        Get DM status.
        
        Returns:
            {"dm_id": "...", "status": "queued|delivered|failed", "recipient_user_id": "...", "updated_at": "..."}
        
        Raises:
            TemporaryError: Temporary failure
            PermanentError: Permanent failure
        """
        url = f"{self.base_url}/v1/dm/{dm_id}"
        
        try:
            logger.debug(f"Checking DM status", extra={"dm_id": dm_id})
            
            response = await self.client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(
                    f"DM status checked",
                    extra={
                        "dm_id": dm_id,
                        "status": data.get("status"),
                    }
                )
                return data
            
            elif response.status_code == 500:
                logger.warning(
                    f"API server error checking status",
                    extra={"dm_id": dm_id}
                )
                raise TemporaryError("API server error")
            
            elif response.status_code == 404:
                logger.error(
                    f"DM not found",
                    extra={"dm_id": dm_id}
                )
                raise PermanentError(f"DM not found: {dm_id}")
            
            else:
                logger.error(
                    f"Unexpected status code checking DM",
                    extra={
                        "dm_id": dm_id,
                        "status_code": response.status_code,
                    }
                )
                raise TemporaryError(f"Unexpected status code: {response.status_code}")
        
        except httpx.TimeoutException:
            logger.warning(f"Timeout checking DM status", extra={"dm_id": dm_id})
            raise TemporaryError("Request timeout")
        except httpx.RequestError as e:
            logger.warning(
                f"Network error checking DM status",
                extra={
                    "dm_id": dm_id,
                    "error": str(e),
                }
            )
            raise TemporaryError(f"Network error: {str(e)}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
