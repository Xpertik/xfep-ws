"""Tests for xfep.ws.soap — SOAP client with mocked HTTP transport."""

from __future__ import annotations

import pytest

from xfep.ws.soap import SunatSoap, SunatSoapError


SAMPLE_XML = b"<Invoice>test</Invoice>"
FILENAME = "20123456789-01-F001-1"


class TestSendBill:
    async def test_returns_bill_response_with_cdr(self, soap_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        )
        resp = await client.send_bill(SAMPLE_XML, FILENAME)

        assert resp.success is True
        assert resp.cdr_bytes is not None
        assert len(resp.cdr_bytes) > 0

    async def test_extracts_cdr_code(self, soap_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        )
        resp = await client.send_bill(SAMPLE_XML, FILENAME)

        assert resp.cdr_code == "0"

    async def test_extracts_cdr_description(self, soap_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        )
        resp = await client.send_bill(SAMPLE_XML, FILENAME)

        assert "aceptada" in resp.cdr_description

    async def test_extracts_hash_value(self, soap_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        )
        resp = await client.send_bill(SAMPLE_XML, FILENAME)

        assert resp.hash_value == "abc123hash"


class TestSendSummary:
    async def test_returns_ticket(self, soap_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        )
        resp = await client.send_summary(SAMPLE_XML, "20123456789-RC-20260101-1")

        assert resp.success is True
        assert resp.ticket == "1234567890"


class TestGetStatus:
    async def test_returns_status_with_cdr(self, soap_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        )
        resp = await client.get_status("1234567890")

        assert resp.success is True
        assert resp.status_code == "0"
        assert resp.cdr_bytes is not None

    async def test_extracts_cdr_code_from_status(self, soap_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        )
        resp = await client.get_status("1234567890")

        assert resp.cdr_code == "0"


class TestSoapFault:
    async def test_raises_sunat_soap_error(self, soap_fault_client):
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_fault_client
        )

        with pytest.raises(SunatSoapError) as exc_info:
            await client.send_bill(SAMPLE_XML, FILENAME)

        assert "soap:Client" in str(exc_info.value)
        assert exc_info.value.fault_code == "soap:Client"
        assert "ya fue informado" in exc_info.value.fault_message


class TestSoapEnvelope:
    async def test_envelope_contains_ws_security(self, soap_client):
        """Verify the SOAP envelope embeds WS-Security credentials."""
        import httpx

        captured_requests: list[httpx.Request] = []

        def capturing_handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            # Import here to access the fixture's response
            from tests.conftest import SEND_BILL_SUCCESS

            return httpx.Response(200, content=SEND_BILL_SUCCESS)

        capture_client = httpx.AsyncClient(
            transport=httpx.MockTransport(capturing_handler)
        )
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=capture_client
        )
        await client.send_bill(SAMPLE_XML, FILENAME)

        body = captured_requests[0].content.decode()
        assert "wsse:Username" in body
        assert "20123456789MODDATOS" in body
        assert "wsse:Password" in body

    async def test_envelope_contains_zip_base64_content(self, soap_client):
        """Verify the payload is zipped and base64-encoded."""
        import httpx

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            from tests.conftest import SEND_BILL_SUCCESS

            return httpx.Response(200, content=SEND_BILL_SUCCESS)

        cap_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        client = SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=cap_client
        )
        await client.send_bill(SAMPLE_XML, FILENAME)

        body = captured[0].content.decode()
        assert "<contentFile>" in body
        assert f"<fileName>{FILENAME}.zip</fileName>" in body


class TestContextManager:
    async def test_async_with_support(self, soap_client):
        async with SunatSoap(
            "20123456789", "MODDATOS", "MODDATOS", http_client=soap_client
        ) as client:
            resp = await client.send_bill(SAMPLE_XML, FILENAME)
            assert resp.success is True
