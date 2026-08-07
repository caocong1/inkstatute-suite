"""Tests for AgentCoreConfig."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from inkstatute_agent_core.config import AgentCoreConfig


class TestAgentCoreConfigDefaults(unittest.TestCase):
    """Default construction matches Rust constants."""

    def test_default_max_turns_is_10(self):
        cfg = AgentCoreConfig()
        self.assertEqual(cfg.max_turns, 10)

    def test_default_silence_threshold_is_5(self):
        cfg = AgentCoreConfig()
        self.assertEqual(cfg.silence_threshold_seconds, 5.0)

    def test_default_response_max_tokens_is_8192(self):
        cfg = AgentCoreConfig()
        self.assertEqual(cfg.response_max_tokens, 8192)

    def test_default_temperature_is_0_3(self):
        cfg = AgentCoreConfig()
        self.assertEqual(cfg.temperature, 0.3)

    def test_default_context_budget_is_32768(self):
        cfg = AgentCoreConfig()
        self.assertEqual(cfg.context_budget_tokens, 32768)

    def test_default_chars_per_token_is_4(self):
        cfg = AgentCoreConfig()
        self.assertEqual(cfg.chars_per_token, 4)

    def test_default_heartbeat_metadata_key(self):
        cfg = AgentCoreConfig()
        self.assertEqual(cfg.heartbeat_metadata_key, "heartbeat")


class TestAgentCoreConfigCustomValues(unittest.TestCase):
    """Custom values are accepted."""

    def test_custom_max_turns(self):
        cfg = AgentCoreConfig(max_turns=20)
        self.assertEqual(cfg.max_turns, 20)

    def test_custom_silence_threshold(self):
        cfg = AgentCoreConfig(silence_threshold_seconds=10.0)
        self.assertEqual(cfg.silence_threshold_seconds, 10.0)

    def test_custom_temperature(self):
        cfg = AgentCoreConfig(temperature=0.7)
        self.assertEqual(cfg.temperature, 0.7)

    def test_custom_all_fields(self):
        cfg = AgentCoreConfig(
            max_turns=5,
            silence_threshold_seconds=3.0,
            response_max_tokens=4096,
            temperature=0.5,
            context_budget_tokens=16384,
            chars_per_token=3,
            heartbeat_metadata_key="hb",
        )
        self.assertEqual(cfg.max_turns, 5)
        self.assertEqual(cfg.silence_threshold_seconds, 3.0)
        self.assertEqual(cfg.response_max_tokens, 4096)
        self.assertEqual(cfg.temperature, 0.5)
        self.assertEqual(cfg.context_budget_tokens, 16384)
        self.assertEqual(cfg.chars_per_token, 3)
        self.assertEqual(cfg.heartbeat_metadata_key, "hb")


class TestAgentCoreConfigValidation(unittest.TestCase):
    """__post_init__ validates field constraints."""

    def test_max_turns_zero_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            AgentCoreConfig(max_turns=0)
        self.assertIn("max_turns", str(ctx.exception))

    def test_max_turns_negative_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            AgentCoreConfig(max_turns=-1)
        self.assertIn("max_turns", str(ctx.exception))

    def test_max_turns_one_is_valid(self):
        cfg = AgentCoreConfig(max_turns=1)
        self.assertEqual(cfg.max_turns, 1)

    def test_silence_threshold_zero_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            AgentCoreConfig(silence_threshold_seconds=0)
        self.assertIn("silence_threshold_seconds", str(ctx.exception))

    def test_silence_threshold_negative_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            AgentCoreConfig(silence_threshold_seconds=-1.0)
        self.assertIn("silence_threshold_seconds", str(ctx.exception))

    def test_silence_threshold_small_positive_is_valid(self):
        cfg = AgentCoreConfig(silence_threshold_seconds=0.1)
        self.assertEqual(cfg.silence_threshold_seconds, 0.1)


class TestAgentCoreConfigFrozen(unittest.TestCase):
    """AgentCoreConfig is a frozen dataclass."""

    def test_frozen_cannot_mutate(self):
        cfg = AgentCoreConfig()
        with self.assertRaises(FrozenInstanceError):
            cfg.max_turns = 20  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
