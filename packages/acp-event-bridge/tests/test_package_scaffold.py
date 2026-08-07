"""Placeholder test to verify the package scaffolds correctly."""

import unittest


class TestPackageScaffold(unittest.TestCase):
    """Trivial test — the acp-event-bridge package exists and imports."""

    def test_package_scaffold(self) -> None:
        """The package can be imported."""
        import inkstatute_acp_event_bridge  # noqa: F401
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
