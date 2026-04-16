"""SOAP client for SUNAT SEE (Servicio de Envio Electronico).

Handles ``sendBill``, ``sendSummary``, and ``getStatus`` operations by
building raw SOAP envelopes with WS-Security headers and sending them
over ``httpx``.
"""

from __future__ import annotations

import base64
import io
import zipfile
from xml.etree import ElementTree as ET

import httpx

from xfep.ws.auth import build_sol_username
from xfep.ws.config import Environment, SunatConfig
from xfep.ws.models import BillResponse, StatusResponse, SummaryResponse

# ---------------------------------------------------------------------------
# XML namespaces used when parsing SUNAT SOAP responses
# ---------------------------------------------------------------------------
_NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "br": "http://service.sunat.gob.pe",
}

# ---------------------------------------------------------------------------
# SOAP envelope template
# ---------------------------------------------------------------------------
_ENVELOPE_TEMPLATE = """\
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:ser="http://service.sunat.gob.pe"
                   xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
  <soapenv:Header>
    <wsse:Security>
      <wsse:UsernameToken>
        <wsse:Username>{username}</wsse:Username>
        <wsse:Password>{password}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    {body}
  </soapenv:Body>
</soapenv:Envelope>"""


class SunatSoapError(Exception):
    """Raised when SUNAT returns a SOAP fault."""

    def __init__(self, fault_code: str, fault_message: str) -> None:
        self.fault_code = fault_code
        self.fault_message = fault_message
        super().__init__(f"SOAP Fault [{fault_code}]: {fault_message}")


class SunatSoap:
    """SOAP client for SUNAT SEE (Servicio de Envio Electronico).

    Usage::

        async with SunatSoap(ruc, usuario_sol, clave_sol) as client:
            resp = await client.send_bill(xml_bytes, "20123456789-01-F001-1")
    """

    def __init__(
        self,
        ruc: str,
        usuario_sol: str,
        clave_sol: str,
        *,
        production: bool = False,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        env = Environment.PRODUCTION if production else Environment.BETA
        self._config = SunatConfig(environment=env)
        self._username = build_sol_username(ruc, usuario_sol)
        self._password = clave_sol
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=60.0)

    # -- context manager ----------------------------------------------------

    async def __aenter__(self) -> SunatSoap:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client (only if we own it)."""
        if self._owns_client:
            await self._http.aclose()

    # -- public API ---------------------------------------------------------

    async def send_bill(
        self, xml_bytes: bytes, filename: str
    ) -> BillResponse:
        """Send a single document (Invoice, NC, ND). Returns CDR immediately."""
        zip_b64 = _zip_and_b64(xml_bytes, filename)
        body = (
            "<ser:sendBill>\n"
            f"      <fileName>{filename}.zip</fileName>\n"
            f"      <contentFile>{zip_b64}</contentFile>\n"
            "    </ser:sendBill>"
        )
        root = await self._post(body, soap_action="urn:sendBill")
        return _parse_bill_response(root)

    async def send_summary(
        self, xml_bytes: bytes, filename: str
    ) -> SummaryResponse:
        """Send batch (Resumen Diario, Comunicacion de Baja). Returns ticket."""
        zip_b64 = _zip_and_b64(xml_bytes, filename)
        body = (
            "<ser:sendSummary>\n"
            f"      <fileName>{filename}.zip</fileName>\n"
            f"      <contentFile>{zip_b64}</contentFile>\n"
            "    </ser:sendSummary>"
        )
        root = await self._post(body, soap_action="urn:sendSummary")
        return _parse_summary_response(root)

    async def get_status(self, ticket: str) -> StatusResponse:
        """Check status of an async operation by ticket number."""
        body = (
            "<ser:getStatus>\n"
            f"      <ticket>{ticket}</ticket>\n"
            "    </ser:getStatus>"
        )
        root = await self._post(body, soap_action="urn:getStatus")
        return _parse_status_response(root)

    # -- internal -----------------------------------------------------------

    async def _post(self, body_xml: str, *, soap_action: str) -> ET.Element:
        """Build envelope, POST, parse response, check for SOAP faults."""
        envelope = _ENVELOPE_TEMPLATE.format(
            username=self._username,
            password=self._password,
            body=body_xml,
        )
        response = await self._http.post(
            self._config.soap_url,
            content=envelope.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": soap_action,
            },
        )
        root = ET.fromstring(response.text)  # noqa: S314
        _check_fault(root)
        return root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _zip_and_b64(xml_bytes: bytes, filename: str) -> str:
    """ZIP the XML and return base64 encoded content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{filename}.xml", xml_bytes)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _check_fault(root: ET.Element) -> None:
    """Raise ``SunatSoapError`` if the response contains a SOAP fault."""
    fault = root.find(".//soap:Fault", _NS)
    if fault is not None:
        code = _text(fault, "faultcode")
        message = _text(fault, "faultstring")
        raise SunatSoapError(code, message)


def _text(parent: ET.Element, tag: str) -> str:
    """Get text of a direct child element, or empty string."""
    el = parent.find(tag)
    return el.text if el is not None and el.text else ""


def _find_text(root: ET.Element, xpath: str) -> str | None:
    """Find text via xpath with SUNAT namespaces."""
    el = root.find(xpath, _NS)
    return el.text if el is not None and el.text else None


def _parse_bill_response(root: ET.Element) -> BillResponse:
    """Parse sendBill SOAP response into a BillResponse."""
    app_response = _find_text(
        root, ".//br:sendBillResponse/applicationResponse"
    )
    cdr_bytes: bytes | None = None
    cdr_code: str | None = None
    cdr_description: str | None = None
    hash_value: str | None = None

    if app_response:
        cdr_bytes = base64.b64decode(app_response)
        # Try to extract CDR info from the ZIP
        try:
            cdr_code, cdr_description, hash_value = _extract_cdr_info(
                cdr_bytes
            )
        except Exception:  # noqa: BLE001
            pass

    return BillResponse(
        success=app_response is not None,
        cdr_bytes=cdr_bytes,
        cdr_code=cdr_code,
        cdr_description=cdr_description,
        hash_value=hash_value,
    )


def _parse_summary_response(root: ET.Element) -> SummaryResponse:
    """Parse sendSummary SOAP response into a SummaryResponse."""
    ticket = _find_text(root, ".//br:sendSummaryResponse/ticket")
    return SummaryResponse(
        success=ticket is not None,
        ticket=ticket,
    )


def _parse_status_response(root: ET.Element) -> StatusResponse:
    """Parse getStatus SOAP response into a StatusResponse."""
    # getStatus returns a statusResponse with content and statusCode
    status_code = _find_text(root, ".//br:getStatusResponse/statusCode")
    app_response = _find_text(root, ".//br:getStatusResponse/content")

    cdr_bytes: bytes | None = None
    cdr_code: str | None = None
    cdr_description: str | None = None

    if app_response:
        cdr_bytes = base64.b64decode(app_response)
        try:
            cdr_code, cdr_description, _ = _extract_cdr_info(cdr_bytes)
        except Exception:  # noqa: BLE001
            pass

    return StatusResponse(
        success=status_code is not None,
        status_code=status_code,
        cdr_bytes=cdr_bytes,
        cdr_code=cdr_code,
        cdr_description=cdr_description,
    )


def _extract_cdr_info(
    cdr_zip_bytes: bytes,
) -> tuple[str | None, str | None, str | None]:
    """Extract response code, description and hash from a CDR ZIP.

    The CDR is a ZIP containing an XML with the SUNAT response. We parse
    the ``ResponseCode``, ``Description``, and ``DigestValue``.
    """
    with zipfile.ZipFile(io.BytesIO(cdr_zip_bytes)) as zf:
        names = zf.namelist()
        if not names:
            return None, None, None
        xml_bytes = zf.read(names[0])

    cdr_root = ET.fromstring(xml_bytes)  # noqa: S314
    # SUNAT CDR uses UBL namespaces
    cdr_ns = {
        "ar": "urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }
    code_el = cdr_root.find(
        ".//cbc:ResponseCode", cdr_ns
    )
    desc_el = cdr_root.find(
        ".//cbc:Description", cdr_ns
    )
    hash_el = cdr_root.find(".//ds:DigestValue", cdr_ns)

    code = code_el.text if code_el is not None and code_el.text else None
    desc = desc_el.text if desc_el is not None and desc_el.text else None
    hv = hash_el.text if hash_el is not None and hash_el.text else None
    return code, desc, hv
