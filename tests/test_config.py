"""Tests for xfep.ws.config — environment switching and URL resolution."""

from xfep.ws.config import Environment, SunatConfig


class TestEnvironmentEnum:
    def test_beta_value(self):
        assert Environment.BETA == "beta"

    def test_production_value(self):
        assert Environment.PRODUCTION == "production"

    def test_is_str_enum(self):
        assert isinstance(Environment.BETA, str)


class TestSunatConfigBeta:
    def setup_method(self):
        self.config = SunatConfig(environment=Environment.BETA)

    def test_soap_url_targets_beta(self):
        assert "e-beta.sunat.gob.pe" in self.config.soap_url
        assert "beta" in self.config.soap_url

    def test_gre_base_url_targets_beta(self):
        assert "api-cpe-beta.sunat.gob.pe" in self.config.gre_base_url

    def test_auth_url_targets_beta(self):
        assert "gre-beta.sunat.gob.pe" in self.config.auth_url
        assert "{client_id}" in self.config.auth_url

    def test_default_is_beta(self):
        default = SunatConfig()
        assert default.environment == Environment.BETA
        assert default.soap_url == self.config.soap_url


class TestSunatConfigProduction:
    def setup_method(self):
        self.config = SunatConfig(environment=Environment.PRODUCTION)

    def test_soap_url_targets_production(self):
        assert "e-factura.sunat.gob.pe" in self.config.soap_url
        assert "beta" not in self.config.soap_url

    def test_gre_base_url_targets_production(self):
        assert "api-cpe.sunat.gob.pe" in self.config.gre_base_url
        assert "beta" not in self.config.gre_base_url

    def test_auth_url_targets_production(self):
        assert "api-seguridad.sunat.gob.pe" in self.config.auth_url
        assert "beta" not in self.config.auth_url

    def test_auth_url_has_client_id_placeholder(self):
        assert "{client_id}" in self.config.auth_url


class TestSunatConfigFrozen:
    def test_config_is_immutable(self):
        config = SunatConfig()
        try:
            config.environment = Environment.PRODUCTION  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass
