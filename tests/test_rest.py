"""Tests for xfep.ws.rest — REST client with mocked HTTP transport."""

from __future__ import annotations

import httpx
import pytest

from xfep.ws.auth import OAuth2TokenManager
from xfep.ws.rest import SunatRest


SAMPLE_XML = b"<DespatchAdvice>test</DespatchAdvice>"
FILENAME = "20123456789-09-T001-1"


class TestSendDespatch:
    async def test_returns_ticket(self, rest_client):
        client = SunatRest(
            "client-id", "client-secret", http_client=rest_client
        )
        result = await client.send_despatch(SAMPLE_XML, FILENAME)

        assert result["numTicket"] == "GRE-2026-001"

    async def test_returns_reception_date(self, rest_client):
        client = SunatRest(
            "client-id", "client-secret", http_client=rest_client
        )
        result = await client.send_despatch(SAMPLE_XML, FILENAME)

        assert "fecRecepcion" in result


class TestGetStatus:
    async def test_returns_status(self, rest_client):
        client = SunatRest(
            "client-id", "client-secret", http_client=rest_client
        )
        result = await client.get_status("GRE-2026-001")

        assert result["codRespuesta"] == "0"


class TestOAuth2TokenAcquisition:
    async def test_acquires_token_on_first_call(self, rest_client):
        manager = OAuth2TokenManager(
            client_id="test-id",
            client_secret="test-secret",
            token_url="https://gre-beta.sunat.gob.pe/v1/clientessol/test-id/oauth2/token/",
        )
        token = await manager.get_token(rest_client)

        assert token == "test-token-abc123"


class TestOAuth2TokenReuse:
    async def test_reuses_cached_token(self, rest_client):
        """Token manager should not make a second auth request if cached."""
        call_count = 0

        def counting_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            url = str(request.url)
            if "oauth2/token" in url:
                call_count += 1
                return httpx.Response(
                    200,
                    content=b'{"access_token": "cached-token", "expires_in": 3600}',
                )
            return httpx.Response(200, content=b'{}')

        counting_client = httpx.AsyncClient(
            transport=httpx.MockTransport(counting_handler)
        )
        manager = OAuth2TokenManager(
            client_id="test-id",
            client_secret="test-secret",
            token_url="https://gre-beta.sunat.gob.pe/v1/clientessol/test-id/oauth2/token/",
        )

        token1 = await manager.get_token(counting_client)
        token2 = await manager.get_token(counting_client)

        assert token1 == token2 == "cached-token"
        assert call_count == 1  # Only one auth call


class TestOAuth2TokenRefresh:
    async def test_refreshes_expired_token(self):
        """After TTL expires, a new token should be fetched."""
        import time
        from unittest.mock import patch

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                content=b'{"access_token": "fresh-token", "expires_in": 3600}',
            )

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        manager = OAuth2TokenManager(
            client_id="test-id",
            client_secret="test-secret",
            token_url="https://gre-beta.sunat.gob.pe/v1/clientessol/test-id/oauth2/token/",
        )

        # First call
        await manager.get_token(mock_client)
        assert call_count == 1

        # Simulate expiry by moving _expires_at to the past
        manager._expires_at = time.monotonic() - 1

        # Second call should refresh
        await manager.get_token(mock_client)
        assert call_count == 2


class TestRestContextManager:
    async def test_async_with_support(self, rest_client):
        async with SunatRest(
            "client-id", "client-secret", http_client=rest_client
        ) as client:
            result = await client.send_despatch(SAMPLE_XML, FILENAME)
            assert "numTicket" in result
