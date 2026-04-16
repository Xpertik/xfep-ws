"""SOL credential helpers and OAuth2 token management for SUNAT."""

from __future__ import annotations

import time


def build_sol_username(ruc: str, usuario_sol: str) -> str:
    """Build SUNAT SOL username: RUC + usuario_sol."""
    return f"{ruc}{usuario_sol}"


class OAuth2TokenManager:
    """Manages OAuth2 tokens with TTL caching for GRE REST API.

    Uses the ``client_credentials`` grant type against the SUNAT token
    endpoint.  Tokens are cached and automatically refreshed when they
    expire (with a 30-second safety margin).
    """

    _SAFETY_MARGIN_SECONDS = 30

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    @property
    def _is_expired(self) -> bool:
        return time.monotonic() >= self._expires_at

    async def get_token(self, http_client) -> str:  # noqa: ANN001
        """Return a valid access token, refreshing if necessary.

        Parameters
        ----------
        http_client:
            An ``httpx.AsyncClient`` used to POST to the token endpoint.
        """
        if self._access_token is not None and not self._is_expired:
            return self._access_token

        response = await http_client.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        response.raise_for_status()

        body = response.json()
        self._access_token = body["access_token"]
        expires_in: int = body.get("expires_in", 3600)
        self._expires_at = (
            time.monotonic() + expires_in - self._SAFETY_MARGIN_SECONDS
        )
        return self._access_token  # type: ignore[return-value]
