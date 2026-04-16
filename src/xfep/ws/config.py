"""Environment configuration and SUNAT endpoint URLs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Environment(StrEnum):
    """SUNAT target environment."""

    BETA = "beta"
    PRODUCTION = "production"


@dataclass(frozen=True)
class SunatConfig:
    """Resolves SUNAT endpoint URLs based on environment."""

    environment: Environment = Environment.BETA

    @property
    def soap_url(self) -> str:
        """SOAP endpoint for SEE (sendBill, sendSummary, getStatus)."""
        if self.environment == Environment.PRODUCTION:
            return "https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService"
        return "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService"

    @property
    def gre_base_url(self) -> str:
        """REST base URL for GRE (Guias de Remision Electronica)."""
        if self.environment == Environment.PRODUCTION:
            return "https://api-cpe.sunat.gob.pe"
        return "https://api-cpe-beta.sunat.gob.pe"

    @property
    def auth_url(self) -> str:
        """OAuth2 token endpoint for GRE. Format with client_id before use."""
        if self.environment == Environment.PRODUCTION:
            return "https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/"
        return "https://gre-beta.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/"
