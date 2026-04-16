"""Shared fixtures for xfep-ws tests.

Provides canned SUNAT SOAP and REST responses plus ``httpx.MockTransport``
factories so tests never hit the network.
"""

from __future__ import annotations

import base64
import io
import zipfile

import httpx
import pytest


# ---------------------------------------------------------------------------
# Canned CDR XML (inside the ZIP that SUNAT returns as applicationResponse)
# ---------------------------------------------------------------------------
CDR_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
                     xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                     xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <cbc:ResponseCode>0</cbc:ResponseCode>
  <cbc:Description>La Factura numero F001-1, ha sido aceptada</cbc:Description>
  <ds:Signature>
    <ds:SignedInfo>
      <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
    </ds:SignedInfo>
    <ds:SignatureValue/>
    <ds:KeyInfo/>
    <ds:Object>
      <ds:DigestValue>abc123hash</ds:DigestValue>
    </ds:Object>
  </ds:Signature>
</ApplicationResponse>"""


def _make_cdr_zip() -> bytes:
    """Create a ZIP containing the CDR XML."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("R-20123456789-01-F001-1.xml", CDR_XML)
    return buf.getvalue()


CDR_ZIP_BYTES = _make_cdr_zip()
CDR_ZIP_B64 = base64.b64encode(CDR_ZIP_BYTES).decode("ascii")


# ---------------------------------------------------------------------------
# Canned SOAP responses
# ---------------------------------------------------------------------------
SEND_BILL_SUCCESS = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <br:sendBillResponse xmlns:br="http://service.sunat.gob.pe">
      <applicationResponse>{CDR_ZIP_B64}</applicationResponse>
    </br:sendBillResponse>
  </soap:Body>
</soap:Envelope>""".encode()

SEND_SUMMARY_SUCCESS = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <br:sendSummaryResponse xmlns:br="http://service.sunat.gob.pe">
      <ticket>1234567890</ticket>
    </br:sendSummaryResponse>
  </soap:Body>
</soap:Envelope>"""

GET_STATUS_SUCCESS = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <br:getStatusResponse xmlns:br="http://service.sunat.gob.pe">
      <statusCode>0</statusCode>
      <content>{CDR_ZIP_B64}</content>
    </br:getStatusResponse>
  </soap:Body>
</soap:Envelope>""".encode()

SOAP_FAULT = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Client</faultcode>
      <faultstring>El documento ya fue informado anteriormente</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""


# ---------------------------------------------------------------------------
# SOAP mock transport
# ---------------------------------------------------------------------------
def _soap_handler(request: httpx.Request) -> httpx.Response:
    """Route SOAP requests to canned responses based on body content."""
    body = request.content
    if b"sendBill" in body:
        return httpx.Response(200, content=SEND_BILL_SUCCESS)
    if b"sendSummary" in body:
        return httpx.Response(200, content=SEND_SUMMARY_SUCCESS)
    if b"getStatus" in body:
        return httpx.Response(200, content=GET_STATUS_SUCCESS)
    return httpx.Response(500, content=b"<error>Unknown</error>")


def _soap_fault_handler(request: httpx.Request) -> httpx.Response:
    """Always return a SOAP fault."""
    return httpx.Response(200, content=SOAP_FAULT)


@pytest.fixture()
def soap_client():
    """Return an ``httpx.AsyncClient`` backed by the SOAP mock transport."""
    return httpx.AsyncClient(transport=httpx.MockTransport(_soap_handler))


@pytest.fixture()
def soap_fault_client():
    """Return an ``httpx.AsyncClient`` that always returns SOAP faults."""
    return httpx.AsyncClient(
        transport=httpx.MockTransport(_soap_fault_handler)
    )


# ---------------------------------------------------------------------------
# REST / OAuth2 mock transport
# ---------------------------------------------------------------------------
OAUTH2_TOKEN_RESPONSE = b'{"access_token": "test-token-abc123", "expires_in": 3600, "token_type": "Bearer"}'
GRE_SEND_RESPONSE = b'{"numTicket": "GRE-2026-001", "fecRecepcion": "2026-01-15T10:30:00"}'
GRE_STATUS_RESPONSE = b'{"codRespuesta": "0", "arcCdr": "", "indCdrGenerado": true}'


def _rest_handler(request: httpx.Request) -> httpx.Response:
    """Route REST requests to canned responses."""
    url = str(request.url)
    if "oauth2/token" in url:
        return httpx.Response(200, content=OAUTH2_TOKEN_RESPONSE)
    if "/envios/" in url:
        return httpx.Response(200, content=GRE_STATUS_RESPONSE)
    if "/comprobantes/" in url and request.method == "POST":
        return httpx.Response(200, content=GRE_SEND_RESPONSE)
    return httpx.Response(404, content=b'{"error": "Not Found"}')


@pytest.fixture()
def rest_client():
    """Return an ``httpx.AsyncClient`` backed by the REST mock transport."""
    return httpx.AsyncClient(transport=httpx.MockTransport(_rest_handler))
