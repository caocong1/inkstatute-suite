"""Tests for CircuitBreaker (CLOSED/OPEN/HALF_OPEN with cooldown)."""

from __future__ import annotations

import unittest

from inkstatute_model_gateway.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
)


def _make_clock() -> list[float]:
    """Return a mutable clock that starts at t=0 and advances on demand."""
    state = [0.0]

    def clock() -> float:
        return state[0]

    def advance(dt: float) -> None:
        state[0] += dt

    clock.advance = advance  # type: ignore[attr-defined]
    return clock  # type: ignore[return-value]


class TestCircuitBreakerStates(unittest.TestCase):
    """Circuit breaker state transition tests."""

    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_record_failure_below_threshold_stays_closed(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=5))
        for _ in range(3):
            cb.record_failure(now=0.0)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.consecutive_failures, 3)

    def test_record_failure_at_threshold_opens(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=5))
        for _ in range(5):
            cb.record_failure(now=0.0)
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_open_blocks_execution(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure(now=0.0)
        cb.record_failure(now=0.0)
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.can_execute(now=1.0))

    def test_open_transitions_to_half_open_after_cooldown(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=60.0))
        cb.record_failure(now=0.0)
        cb.record_failure(now=0.0)
        self.assertEqual(cb.state, CircuitState.OPEN)
        # Before cooldown
        self.assertFalse(cb.can_execute(now=30.0))
        # After cooldown
        self.assertTrue(cb.can_execute(now=61.0))
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=60.0))
        cb.record_failure(now=0.0)
        cb.record_failure(now=0.0)
        cb.can_execute(now=61.0)  # transitions to HALF_OPEN
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.consecutive_failures, 0)

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=60.0))
        cb.record_failure(now=0.0)
        cb.record_failure(now=0.0)
        cb.can_execute(now=61.0)  # transitions to HALF_OPEN
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        cb.record_failure(now=61.0)
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_record_success_resets_failures(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=5))
        cb.record_failure(now=0.0)
        cb.record_failure(now=0.0)
        cb.record_failure(now=0.0)
        cb.record_success()
        self.assertEqual(cb.consecutive_failures, 0)
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_reset_forces_closed(self) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure(now=0.0)
        cb.record_failure(now=0.0)
        self.assertEqual(cb.state, CircuitState.OPEN)
        cb.reset()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.consecutive_failures, 0)

    def test_closed_can_execute_always_true(self) -> None:
        cb = CircuitBreaker()
        self.assertTrue(cb.can_execute(now=0.0))
        self.assertTrue(cb.can_execute(now=100.0))


class TestCircuitBreakerRegistry(unittest.TestCase):
    """Registry isolation and lookup tests."""

    def test_get_or_create_returns_same_instance(self) -> None:
        registry = CircuitBreakerRegistry()
        cb1 = registry.get_or_create("provider-a")
        cb2 = registry.get_or_create("provider-a")
        self.assertIs(cb1, cb2)

    def test_different_providers_isolated(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=2))
        cb_a = registry.get_or_create("provider-a")
        cb_b = registry.get_or_create("provider-b")
        self.assertIsNot(cb_a, cb_b)
        # Trip provider-a
        cb_a.record_failure(now=0.0)
        cb_a.record_failure(now=0.0)
        self.assertEqual(cb_a.state, CircuitState.OPEN)
        self.assertEqual(cb_b.state, CircuitState.CLOSED)

    def test_get_state(self) -> None:
        registry = CircuitBreakerRegistry()
        self.assertEqual(registry.get_state("provider-a"), CircuitState.CLOSED)

    def test_can_execute_delegates(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=1))
        registry.record_failure("provider-a", now=0.0)
        self.assertFalse(registry.can_execute("provider-a", now=1.0))
        self.assertTrue(registry.can_execute("provider-b", now=1.0))

    def test_record_success_and_failure_delegates(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=2))
        registry.record_failure("provider-a", now=0.0)
        registry.record_failure("provider-a", now=0.0)
        self.assertEqual(registry.get_state("provider-a"), CircuitState.OPEN)
        registry.get_or_create("provider-a").can_execute(now=61.0)  # half-open
        registry.record_success("provider-a")
        self.assertEqual(registry.get_state("provider-a"), CircuitState.CLOSED)

    def test_reset_all(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=1))
        registry.record_failure("provider-a", now=0.0)
        registry.record_failure("provider-b", now=0.0)
        registry.reset()
        self.assertEqual(registry.get_state("provider-a"), CircuitState.CLOSED)
        self.assertEqual(registry.get_state("provider-b"), CircuitState.CLOSED)


if __name__ == "__main__":
    unittest.main()
