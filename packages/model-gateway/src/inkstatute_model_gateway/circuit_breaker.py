"""Circuit breakers for provider failure isolation.

Three states: CLOSED (normal), OPEN (tripped, rejecting), HALF_OPEN (probe).

- Trips after N consecutive failures (``failure_threshold``).
- Stays OPEN for ``cooldown_seconds``, then transitions to HALF_OPEN.
- A successful request in HALF_OPEN closes the breaker.
- A failed request in HALF_OPEN re-opens it.

Per-provider circuit breakers are managed by ``CircuitBreakerRegistry``.

No external dependencies — ``dependencies = []`` invariant preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    failure_threshold: int = 5
    cooldown_seconds: float = 60.0


class CircuitBreaker:
    """Single-provider circuit breaker with CLOSED/OPEN/HALF_OPEN states.

    Uses an injectable clock (``Callable[[], float]``) for deterministic
    testing.  The default clock uses ``time.monotonic``.
    """

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.config = config or CircuitBreakerConfig()
        self._clock = clock or _default_clock
        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def can_execute(self, now: float | None = None) -> bool:
        """Return True if a request can be executed.

        - CLOSED → always True.
        - OPEN → check cooldown; if elapsed, transition to HALF_OPEN and return True.
        - HALF_OPEN → always True (probe request).
        """
        ts = now if now is not None else self._clock()
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if self._opened_at is not None and (ts - self._opened_at) >= self.config.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN
        return True

    def record_success(self) -> None:
        """Record a successful request — resets failures and closes the breaker."""
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self, now: float | None = None) -> None:
        """Record a failed request — may trip the breaker to OPEN."""
        ts = now if now is not None else self._clock()
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.config.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = ts

    def reset(self) -> None:
        """Force the breaker to CLOSED state with zeroed counters."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None


class CircuitBreakerRegistry:
    """Registry of per-provider circuit breakers.

    Each provider gets its own independent ``CircuitBreaker`` instance,
    ensuring failure isolation between providers.
    """

    def __init__(
        self,
        default_config: CircuitBreakerConfig | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._default_config = default_config or CircuitBreakerConfig()
        self._clock = clock or _default_clock
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(self, provider_id: str) -> CircuitBreaker:
        breaker = self._breakers.get(provider_id)
        if breaker is None:
            breaker = CircuitBreaker(self._default_config, clock=self._clock)
            self._breakers[provider_id] = breaker
        return breaker

    def get_state(self, provider_id: str) -> CircuitState:
        return self.get_or_create(provider_id).state

    def can_execute(self, provider_id: str, now: float | None = None) -> bool:
        return self.get_or_create(provider_id).can_execute(now)

    def record_success(self, provider_id: str) -> None:
        self.get_or_create(provider_id).record_success()

    def record_failure(self, provider_id: str, now: float | None = None) -> None:
        self.get_or_create(provider_id).record_failure(now)

    def reset(self) -> None:
        """Reset all breakers (for testing)."""
        for breaker in self._breakers.values():
            breaker.reset()


def _default_clock() -> float:
    import time

    return time.monotonic()


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitState",
]
