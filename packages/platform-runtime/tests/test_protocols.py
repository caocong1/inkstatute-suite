from __future__ import annotations

import inspect
import sys
import unittest

from platform_runtime import BackendAdapter, ChannelAdapter, RunRuntime, SolutionLoader
from platform_runtime import protocols


class ProtocolSurfaceTests(unittest.TestCase):
    def test_four_protocol_names_are_importable(self) -> None:
        for protocol in (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime):
            with self.subTest(protocol=protocol.__name__):
                self.assertTrue(getattr(protocol, "_is_protocol", False))

    def test_runtime_surface_is_signature_only(self) -> None:
        expected = {"create_run", "poll", "stream", "cancel", "approve"}
        self.assertTrue(expected.issubset(vars(RunRuntime)))
        for name in expected:
            self.assertTrue(callable(getattr(RunRuntime, name)))

    def test_protocol_module_does_not_import_runtime_implementations(self) -> None:
        forbidden_prefixes = ("services", "channels", "backends", "hermes")
        imported_roots = {
            name.split(".", 1)[0]
            for name in sys.modules
            if name.split(".", 1)[0] in forbidden_prefixes
        }
        self.assertEqual(set(), imported_roots)

    def test_no_concrete_behavior_is_declared(self) -> None:
        protocol_classes = (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime)
        for protocol in protocol_classes:
            with self.subTest(protocol=protocol.__name__):
                self.assertTrue(inspect.isclass(protocol))
                self.assertTrue(getattr(protocol, "_is_protocol", False))

        data_shape_names = {
            "RawInbound",
            "AckResponse",
            "InboundNormalized",
            "DeliveryResult",
            "RunRequest",
            "RunHandle",
            "BootstrapStatus",
            "SolutionBinding",
            "ComponentHealth",
        }
        self.assertTrue(data_shape_names.issubset(vars(protocols)))


if __name__ == "__main__":
    unittest.main()
