"""Contract-count freeze tests (SAFETY-02).

Freezes the method/field counts of the three core contract surfaces at the
v1.5 baseline so that any accidental addition or removal during M2 is caught
by the contract-test-suite gate.

The baseline values are verified by runtime introspection, not by manual
counting from research documents (which contained miscounts).
"""

from __future__ import annotations

import unittest
from dataclasses import fields

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_runtime.protocols import BackendAdapter, ChannelAdapter


class ContractCountFreezeTests(unittest.TestCase):
    """Assert contract surface counts remain frozen at the v1.5 baseline."""

    BACKEND_ADAPTER_METHOD_COUNT = 9
    ADAPTER_CAPABILITY_SET_FIELD_COUNT = 14
    CHANNEL_ADAPTER_METHOD_COUNT = 6

    def test_backend_adapter_method_count_unchanged(self) -> None:
        methods = [m for m in dir(BackendAdapter) if not m.startswith("_")]
        self.assertEqual(
            len(methods),
            self.BACKEND_ADAPTER_METHOD_COUNT,
            f"BackendAdapter Protocol method count changed: "
            f"expected {self.BACKEND_ADAPTER_METHOD_COUNT}, "
            f"got {len(methods)}: {methods}",
        )

    def test_adapter_capability_set_field_count_unchanged(self) -> None:
        field_names = [f.name for f in fields(AdapterCapabilitySet)]
        self.assertEqual(
            len(field_names),
            self.ADAPTER_CAPABILITY_SET_FIELD_COUNT,
            f"AdapterCapabilitySet field count changed: "
            f"expected {self.ADAPTER_CAPABILITY_SET_FIELD_COUNT}, "
            f"got {len(field_names)}: {field_names}",
        )

    def test_channel_adapter_method_count_unchanged(self) -> None:
        methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
        self.assertEqual(
            len(methods),
            self.CHANNEL_ADAPTER_METHOD_COUNT,
            f"ChannelAdapter Protocol method count changed: "
            f"expected {self.CHANNEL_ADAPTER_METHOD_COUNT}, "
            f"got {len(methods)}: {methods}",
        )


if __name__ == "__main__":
    unittest.main()
