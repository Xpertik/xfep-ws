"""REST client for SUNAT GRE (Guias de Remision Electronica).

Uses OAuth2 ``client_credentials`` grant for authentication and sends
dispatch guides via the SUNAT GRE REST API.
"""

from __future__ import annotations

from typing import Any

import httpx

from xfep.ws.auth import OAuth2TokenManager
from xfep.ws.config import Environment, SunatConfig


class SunatRest:
    """REST client for SUNAT GRE (Guias de Remision Electronica).

    Usage::

        async with SunatRest(client_id, client_secret) as client:
            result = await client.send_despatch(xml_bytes, "20123456789-09-T001-1")
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        production: bool = False,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        env = Environment.PRODUCTION if production else Environment.BETA
        self._config = SunatConfig(environment=env)
        self._client_id = client_id

        token_url = self._config.auth_url.format(client_id=client_id)
        self._token_manager = OAuth2TokenManager(
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
        )
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=60.0)

    # -- context manager ----------------------------------------------------

    async def __aenter__(self) -> SunatRest:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client (only if we own it)."""
        if self._owns_client:
            await self._http.aclose()

    # -- public API ---------------------------------------------------------

    async def send_despatch(
        self, xml_bytes: bytes, filename: str
    ) -> dict[str, Any]:
        """Send a GRE document to SUNAT.

        Parameters
        ----------
        xml_bytes:
            Signed XML content of the dispatch guide.
        filename:
            Document identifier, e.g. ``20123456789-09-T001-1``.

        Returns
        -------
        dict
            SUNAT response containing ticket/tracking info.
        """
        token = await self._token_manager.get_token(self._http)
        url = f"{self._config.gre_base_url}/v1/contribuyente/gem/comprobantes/{filename}"
        response = await self._http.post(
            url,
            content=xml_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/xml",
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_status(self, ticket: str) -> dict[str, Any]:
        """Check status of a GRE submission by ticket number.

        Parameters
        ----------
        ticket:
            Ticket number from a previous ``send_despatch`` call.

        Returns
        -------
        dict
            Status response from SUNAT, including optional CDR info.
        """
        token = await self._token_manager.get_token(self._http)
        url = f"{self._config.gre_base_url}/v1/contribuyente/gem/comprobantes/envios/{ticket}"
        response = await self._http.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
        response.raise_for_status()
        return response.json()
