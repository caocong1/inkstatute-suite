"""Placeholder test to ensure the gateway gate passes during scaffolding."""

import unittest


class TestGatewayPlaceholder(unittest.TestCase):
    def test_package_imports(self) -> None:
        from gateway.config import GatewayConfig

        config = GatewayConfig()
        self.assertEqual(config.api_id, "gateway")
        self.assertEqual(config.default_tenant_id, "default")


if __name__ == "__main__":
    unittest.main()
