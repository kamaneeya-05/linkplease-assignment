"""Tests for PseudoGram API client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.pseudogram_client import (
    PseudoGramClient,
    RateLimitError,
    TemporaryError,
    PermanentError,
)


@pytest.mark.asyncio
async def test_send_dm_success_http_200():
    """HTTP 200 is a valid success response when the API returns a usable dm_id."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")

    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dm_id": "dm_123", "status": "queued"}
        mock_post.return_value = mock_response

        result = await client.send_dm(
            recipient_user_id="user_123",
            message="Test message",
            comment_id="cmt_123",
        )

        assert result["dm_id"] == "dm_123"
        assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_send_dm_success_http_202():
    """HTTP 202 remains a supported success response."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")

    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"dm_id": "dm_456", "status": "queued"}
        mock_post.return_value = mock_response

        result = await client.send_dm(
            recipient_user_id="user_123",
            message="Test message",
            comment_id="cmt_123",
        )

        assert result["dm_id"] == "dm_456"
        assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_send_dm_http_200_without_dm_id_raises_temporary_error():
    """A 200/202 response without a usable dm_id is an integration failure, not success."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")

    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "queued"}
        mock_post.return_value = mock_response

        with pytest.raises(TemporaryError, match="dm_id"):
            await client.send_dm(
                recipient_user_id="user_123",
                message="Test message",
                comment_id="cmt_123",
            )


@pytest.mark.asyncio
async def test_send_dm_rate_limited():
    """Test DM send with rate limiting."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")
    
    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"error": "rate_limited"}
        mock_post.return_value = mock_response
        
        with pytest.raises(RateLimitError) as exc_info:
            await client.send_dm(
                recipient_user_id="user_123",
                message="Test",
                comment_id="cmt_123",
            )
        
        assert exc_info.value.retry_after == 60


@pytest.mark.asyncio
async def test_send_dm_server_error():
    """Test DM send with server error (should retry)."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")

    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "internal_error"}
        mock_post.return_value = mock_response

        with pytest.raises(TemporaryError):
            await client.send_dm(
                recipient_user_id="user_123",
                message="Test",
                comment_id="cmt_123",
            )


@pytest.mark.asyncio
async def test_send_dm_bad_request():
    """Test DM send with bad request (should not retry)."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")

    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_request",
            "detail": "Invalid user ID",
        }
        mock_post.return_value = mock_response

        with pytest.raises(PermanentError):
            await client.send_dm(
                recipient_user_id="user_123",
                message="Test",
                comment_id="cmt_123",
            )


@pytest.mark.asyncio
async def test_send_dm_http_429_raises_rate_limit_error():
    """HTTP 429 must still be treated as rate limiting."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")

    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {"error": "rate_limited"}
        mock_post.return_value = mock_response

        with pytest.raises(RateLimitError):
            await client.send_dm(
                recipient_user_id="user_123",
                message="Test",
                comment_id="cmt_123",
            )


@pytest.mark.asyncio
async def test_send_dm_http_500_raises_temporary_error():
    """HTTP 500 remains a retryable temporary API failure."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")

    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "internal_error"}
        mock_post.return_value = mock_response

        with pytest.raises(TemporaryError):
            await client.send_dm(
                recipient_user_id="user_123",
                message="Test",
                comment_id="cmt_123",
            )


@pytest.mark.asyncio
async def test_get_dm_status_delivered():
    """Test getting status for delivered DM."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")
    
    with patch.object(client.client, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "dm_id": "dm_123",
            "status": "delivered",
            "recipient_user_id": "user_123",
        }
        mock_get.return_value = mock_response
        
        result = await client.get_dm_status("dm_123")
        assert result["status"] == "delivered"


@pytest.mark.asyncio
async def test_get_dm_status_queued():
    """Test getting status for queued DM."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")
    
    with patch.object(client.client, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "dm_id": "dm_123",
            "status": "queued",
        }
        mock_get.return_value = mock_response
        
        result = await client.get_dm_status("dm_123")
        assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_idempotency_key_usage():
    """Test that idempotency key is sent."""
    client = PseudoGramClient(api_key="test-key", base_url="http://test")
    
    with patch.object(client.client, 'post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"dm_id": "dm_123", "status": "queued"}
        mock_post.return_value = mock_response
        
        await client.send_dm(
            recipient_user_id="user_123",
            message="Test",
            comment_id="cmt_123",
            idempotency_key="key_123",
        )
        
        # Verify idempotency key was in headers
        call_kwargs = mock_post.call_args[1]
        assert "Idempotency-Key" in call_kwargs.get("headers", {})
        assert call_kwargs["headers"]["Idempotency-Key"] == "key_123"
