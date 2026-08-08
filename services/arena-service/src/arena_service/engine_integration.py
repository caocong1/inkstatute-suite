"""Engine integration — wires ArenaEngine to ArenaServiceApp (Plan 05).

Provides:

- :class:`ArenaEventEmitter` — implements the ``EventEmitter`` protocol
  from ``arena_engine.mode1``, forwarding events to the
  :class:`ArenaEventBuffer` (for reconnection replay) and an
  :class:`asyncio.Queue` (for live SSE streaming).
- :class:`ArenaServiceEngine` — the integration wiring layer that
  composes :class:`ArenaEngine` + :class:`ArenaEventBuffer` +
  :class:`ArenaSseStream` + :class:`ArenaOutputBoundary` +
  :class:`SubprocessController` + :class:`StaggeredStartupSemaphore`.

SVC-01..08: this module wires all arena-service components together so
that ``ArenaServiceApp`` handlers delegate to real ``ArenaEngine`` calls.
The orchestrator never produces content — it only coordinates.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable

from arena_engine.engine import ArenaEngine
from platform_contract.arena_contract import (
    ArenaUserAction,
    ArenaWorkflowConfig,
)
from platform_runtime.protocols import BackendAdapter

from .event_buffer import ArenaEventBuffer
from .output_boundary import ArenaOutputBoundary
from .sse import ArenaSseStream
from .staggered_startup import StaggeredStartupSemaphore
from .subprocess_control import SubprocessController

if TYPE_CHECKING:
    from .config import ArenaServiceConfig

#: Type for the adapter factory callable.
AdapterFactory = Callable[[str, dict[str, Any]], BackendAdapter]


# ---------------------------------------------------------------------------
# ArenaEventEmitter — EventEmitter protocol implementation
# ---------------------------------------------------------------------------


class ArenaEventEmitter:
    """EventEmitter protocol implementation forwarding to buffer + SSE queue.

    Implements the ``EventEmitter`` Protocol from
    ``arena_engine.mode1``.  Each call to :meth:`emit`:

    1. Increments the per-arena sequence counter (``self._seq``).
    2. Builds an event dict with ``event_id``, ``event_type``, ``seq``,
       ``payload``, and ``metadata`` (preserving ``agent_slot``).
    3. Appends the event to the :class:`ArenaEventBuffer` for
       reconnection replay.
    4. Puts the event into an :class:`asyncio.Queue` for live SSE
       streaming.

    The seq numbers are monotonically increasing per arena — first event
    gets ``seq=1``, second gets ``seq=2``, etc.  This guarantees no
    duplication and no loss on reconnection (SVC-07).
    """

    def __init__(
        self,
        arena_id: str,
        event_buffer: ArenaEventBuffer,
        event_queue: asyncio.Queue,
    ) -> None:
        self._arena_id = arena_id
        self._event_buffer = event_buffer
        self._event_queue = event_queue
        self._seq = 0

    @property
    def arena_id(self) -> str:
        return self._arena_id

    @property
    def seq(self) -> int:
        """Return the current sequence number (last assigned)."""
        return self._seq

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        """Forward an event to the buffer and SSE queue with a seq number.

        Parameters
        ----------
        event_type
            The unified event type string (e.g. ``"message.delta"``).
        payload
            The event payload dict.
        metadata
            The event metadata dict (must contain ``agent_slot``).
        """
        self._seq += 1
        event = {
            "event_id": uuid.uuid4().hex,
            "event_type": event_type,
            "seq": self._seq,
            "payload": dict(payload),
            "metadata": dict(metadata),
        }
        self._event_buffer.append(self._arena_id, event)
        await self._event_queue.put(event)


# ---------------------------------------------------------------------------
# _StaggeredAdapter — wraps a BackendAdapter with staggered startup
# ---------------------------------------------------------------------------


class _StaggeredAdapter:
    """Wraps a :class:`BackendAdapter` with staggered startup on ``submit_run``.

    Delegates all methods to the wrapped adapter except ``submit_run``,
    which is wrapped with :class:`StaggeredStartupSemaphore` to limit
    concurrent initializations (SVC-08).

    Uses ``__getattr__`` for transparent delegation of all other
    protocol methods (``backend_id``, ``stream_events``, ``cancel_run``,
    ``shutdown``, ``_sessions``, etc.).
    """

    def __init__(
        self,
        adapter: BackendAdapter,
        staggered: StaggeredStartupSemaphore,
    ) -> None:
        self._adapter = adapter
        self._wrapped_submit_run = staggered.wrap_initialize(adapter.submit_run)

    async def submit_run(self, req: Any) -> Any:
        """Submit a run through the staggered startup semaphore."""
        return await self._wrapped_submit_run(req)

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the wrapped adapter."""
        return getattr(self._adapter, name)


# ---------------------------------------------------------------------------
# ArenaServiceEngine — integration wiring layer
# ---------------------------------------------------------------------------


class ArenaServiceEngine:
    """Integration layer wiring all arena-service components together.

    Composes:

    - :class:`ArenaEngine` — arena orchestration (Mode 1/2/3/4)
    - :class:`ArenaEventBuffer` — per-arena event buffer for replay
    - :class:`ArenaSseStream` — SSE encoding with output boundary filter
    - :class:`ArenaOutputBoundary` — two-layer output enforcement (SVC-04)
    - :class:`SubprocessController` — per-run timeout + cleanup (SVC-06)
    - :class:`StaggeredStartupSemaphore` — concurrent init limiting (SVC-08)

    Parameters
    ----------
    config
        The :class:`ArenaServiceConfig` with timeout and concurrency
        settings.
    adapter_factory
        Optional callable ``(slot_id, body) -> BackendAdapter`` used to
        create adapters for each agent slot.  When provided,
        :meth:`create_arena` automatically starts a background run.
    """

    def __init__(
        self,
        config: "ArenaServiceConfig",
        *,
        adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self._config = config
        self._engine = ArenaEngine(storage_dir=getattr(config, "storage_dir", None))
        self._event_buffer = ArenaEventBuffer()
        self._sse_stream = ArenaSseStream(output_filter=ArenaOutputBoundary())
        self._subprocess_controller = SubprocessController(
            timeout_seconds=config.per_run_timeout_seconds,
        )
        self._staggered_startup = StaggeredStartupSemaphore(
            max_concurrent=config.max_concurrent_initializations,
        )
        self._adapter_factory = adapter_factory
        self._event_queues: dict[str, asyncio.Queue] = {}
        self._adapters: dict[str, dict[str, BackendAdapter]] = {}

    # ------------------------------------------------------------------
    # Properties (for testing)
    # ------------------------------------------------------------------

    @property
    def event_buffer(self) -> ArenaEventBuffer:
        return self._event_buffer

    @property
    def sse_stream(self) -> ArenaSseStream:
        return self._sse_stream

    @property
    def subprocess_controller(self) -> SubprocessController:
        return self._subprocess_controller

    @property
    def staggered_startup(self) -> StaggeredStartupSemaphore:
        return self._staggered_startup

    @property
    def arena_engine(self) -> ArenaEngine:
        return self._engine

    # ------------------------------------------------------------------
    # Arena lifecycle
    # ------------------------------------------------------------------

    async def create_arena(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a new arena and optionally start a background run.

        Parses :class:`ArenaWorkflowConfig` from *body*, calls
        ``engine.start(config)``, and (when an adapter factory is
        configured) starts the background arena run via
        :meth:`run_arena_background`.

        Returns
        -------
        dict
            ``{"arena_id": "...", "status": "created"}``
        """
        arena_id = str(body.get("arena_id") or f"arena-{uuid.uuid4().hex[:12]}")
        arena_config = ArenaWorkflowConfig(
            arena_id=arena_id,
            mode=str(body.get("mode", "")),
            agent_slots=[str(s) for s in body.get("agent_slots", [])],
            task_instruction=str(body.get("task", "")),
            metadata=dict(body.get("metadata", {})),
        )
        handle = await self._engine.start(arena_config)

        # Create adapters and start background run when a factory is set.
        if self._adapter_factory is not None:
            adapters: dict[str, BackendAdapter] = {}
            for slot_id in arena_config.agent_slots:
                adapters[slot_id] = self._adapter_factory(slot_id, body)
            self._adapters[arena_id] = adapters
            asyncio.create_task(self.run_arena_background(arena_id, adapters))

        return {"arena_id": handle.arena_id, "status": "created"}

    async def run_arena_background(
        self,
        arena_id: str,
        adapters: dict[str, BackendAdapter],
    ) -> None:
        """Start a background arena run with event forwarding.

        Creates an :class:`ArenaEventEmitter` for the arena, wraps each
        adapter's ``submit_run`` with :class:`StaggeredStartupSemaphore`,
        wires the :class:`SubprocessController` cleanup callback to
        ``engine.cancel()``, and runs the arena with a per-run timeout.

        On timeout, the cleanup callback cancels the arena and the
        stream is terminated gracefully (sentinel ``None`` put into the
        event queue).

        .. note::

            This method calls ``engine._run_arena()`` directly instead
            of ``engine.run()`` because the latter catches
            ``CancelledError``, which prevents
            :meth:`SubprocessController.run_with_timeout` from enforcing
            the per-run timeout via :func:`asyncio.wait_for`.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._event_queues[arena_id] = queue
        emitter = ArenaEventEmitter(arena_id, self._event_buffer, queue)

        # Wrap adapters with staggered startup (SVC-08).
        wrapped: dict[str, BackendAdapter] = {}
        for slot_id, adapter in adapters.items():
            wrapped[slot_id] = _StaggeredAdapter(adapter, self._staggered_startup)

        # Wire cleanup callback for this arena — timeout triggers cancel.
        async def _cleanup() -> None:
            await self._engine.cancel(arena_id)

        self._subprocess_controller.set_cleanup_callback(_cleanup)

        # Register adapters and create the background task directly (not
        # via engine.run() which catches CancelledError and prevents the
        # per-run timeout from being enforced by asyncio.wait_for).
        self._engine.register_adapters(arena_id, wrapped)
        task = asyncio.create_task(
            self._engine._run_arena(arena_id, wrapped, emitter),
        )
        self._engine._bg_tasks[arena_id] = task

        # Run with per-run timeout (SVC-06).
        try:
            await self._subprocess_controller.run_with_timeout(task)
        except asyncio.TimeoutError:
            pass  # cleanup already invoked by run_with_timeout
        finally:
            await queue.put(None)  # signal stream end

    async def cancel_arena(self, arena_id: str) -> dict[str, Any]:
        """Cancel an arena — delegates to ``engine.cancel()``.

        Returns
        -------
        dict
            ``{"arena_id": "...", "status": "cancelled"}``
        """
        handle = await self._engine.cancel(arena_id)
        return {"arena_id": handle.arena_id, "status": handle.status}

    async def user_action(
        self,
        arena_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a user action — delegates to ``engine.submit_user_action()``.

        Parses :class:`ArenaUserAction` from *body* and forwards it to
        the engine.  Supported actions: ``select``, ``stop``, ``pause``,
        ``resume``.

        Returns
        -------
        dict
            ``{"arena_id": "...", "status": "..."}`` with the updated
            arena status.
        """
        action = ArenaUserAction(
            arena_id=arena_id,
            action=str(body.get("action", "")),
            selected_slot=body.get("selection"),
            metadata=dict(body.get("metadata", {})),
        )
        handle = await self._engine.submit_user_action(arena_id, action)
        return {"arena_id": handle.arena_id, "status": handle.status}

    async def status_arena(self, arena_id: str) -> dict[str, Any]:
        """Query arena status — delegates to ``engine.query_status()``.

        Returns
        -------
        dict
            The arena status dict with ``arena_id``, ``status``,
            ``mode``, ``agent_slots``, and ``metadata``.
        """
        status = await self._engine.query_status(arena_id)
        return {
            "arena_id": status.arena_id,
            "status": status.status,
            "mode": status.mode,
            "agent_slots": list(status.agent_slots),
            "metadata": dict(status.metadata),
        }

    # ------------------------------------------------------------------
    # SSE streaming
    # ------------------------------------------------------------------

    async def stream_arena(
        self,
        arena_id: str,
        last_seq: int | None,
    ) -> AsyncIterator[str]:
        """Stream arena events as SSE frames.

        When *last_seq* is not ``None``, replays buffered events with
        ``seq > last_seq`` first (through the output boundary), then
        continues with live events from the event queue.

        Each event is encoded through :class:`ArenaSseStream` which
        applies the :class:`ArenaOutputBoundary` — blocked events
        (meta/gateway/system noise) are dropped from the SSE stream
        (SVC-04).

        The stream terminates gracefully when the arena run completes
        (sentinel ``None`` in the event queue).

        Reconnection guarantee (SVC-07): events from the queue with
        ``seq <= max_replayed_seq`` are skipped to prevent duplication
        when the client reconnects after the run has already buffered
        events.
        """
        max_replayed_seq = last_seq or 0

        # Replay buffered events with seq > last_seq (SVC-07).
        if last_seq is not None:
            for event in self._event_buffer.replay(arena_id, last_seq):
                frame = self._sse_stream.encode_event(event)
                if frame is not None:
                    yield frame
                max_replayed_seq = max(
                    max_replayed_seq, event.get("seq", 0),
                )

        # Consume live events from the per-arena queue.
        queue = self._event_queues.get(arena_id)
        if queue is None:
            return  # no active run — nothing to stream

        while True:
            event = await queue.get()
            if event is None:  # sentinel for stream end
                break
            # Skip events already replayed from the buffer — prevents
            # duplication when reconnecting after the run has buffered.
            if event.get("seq", 0) <= max_replayed_seq:
                continue
            frame = self._sse_stream.encode_event(event)
            if frame is not None:
                yield frame


__all__ = [
    "ArenaEventEmitter",
    "ArenaServiceEngine",
]
