"""Durable platform-native SQLite memory store for InkStatute production memory."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_contract.events import JsonObject, MemoryCandidate, MemoryRecord, MemoryUse

from .memory import (
    MemoryPrivacyError,
    MemoryQuery,
    MemorySearchResult,
    MemoryStorePolicy,
    _clock_now,
    _copy_candidate,
    _copy_record,
    _copy_use,
    _parse_timestamp,
    _query_now,
    _record_visible,
    _safe_metadata,
    _search_records,
    _timestamp,
    _validate_candidate,
    _validate_record,
    _validate_use,
)
from .memory_adapters import MemoryStoreCapabilityManifest


_CREATE_RECORDS = """
CREATE TABLE IF NOT EXISTS memory_records (
    memory_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_refs TEXT NOT NULL,
    summary TEXT,
    subject TEXT,
    related_user_id TEXT,
    session_id TEXT,
    raw_payload_ref TEXT,
    confidence REAL,
    ttl_expires_at TEXT,
    deleted_at TEXT,
    deletion_reason TEXT,
    industry_context TEXT NOT NULL,
    metadata TEXT NOT NULL
)
"""

_CREATE_CANDIDATES = """
CREATE TABLE IF NOT EXISTS memory_candidates (
    candidate_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    status TEXT NOT NULL,
    source_refs TEXT NOT NULL,
    created_at TEXT NOT NULL,
    proposed_scope TEXT,
    proposed_sensitivity TEXT,
    proposed_action TEXT,
    memory_id TEXT,
    proposed_record_ref TEXT,
    reason TEXT,
    confidence REAL,
    requires_human_review INTEGER NOT NULL DEFAULT 1,
    raw_payload_ref TEXT,
    industry_context TEXT NOT NULL,
    metadata TEXT NOT NULL
)
"""

_CREATE_USES = """
CREATE TABLE IF NOT EXISTS memory_uses (
    use_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    context_bundle_id TEXT NOT NULL,
    used_at TEXT NOT NULL,
    purpose TEXT NOT NULL,
    run_id TEXT,
    turn_id TEXT,
    relevance_score REAL,
    policy_result TEXT,
    source_refs TEXT NOT NULL,
    metadata TEXT NOT NULL
)
"""


class SQLiteMemoryStore:
    """Durable, stdlib-only SQLite-backed memory store for platform-native legal memory.

    .. deprecated:: v1.4
        SQLiteMemoryStore is no longer the default long-term memory backend. Starting
        with v1.4 the productized memory layer is the ``Memory`` interface implemented
        by ``HindsightMemory``. SQLiteMemoryStore remains available for derived read-
        model caches, legacy tests, and migration tooling, but new runtime code should
        target the ``Memory`` interface instead.

    Uses Python stdlib sqlite3 only — no external dependencies.
    Stores refs, hashes, lengths, statuses, scopes, TTL, sensitivity, confidence, and
    safe summaries only. Raw payloads, full text, and secrets are rejected before storage.

    Thread safety: single-threaded use assumed (one store per process/test). For multi-
    threaded use, wrap with external locking or use separate in-process stores per tenant.
    """

    def __init__(
        self,
        *,
        db_path: str | None = None,
        clock: Callable[[], datetime | str] | Any | None = None,
    ) -> None:
        self._db_path = db_path
        self._clock = clock
        path = db_path if db_path is not None else ":memory:"
        if db_path is not None:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        """Create tables if they do not yet exist (idempotent)."""
        cur = self._conn.cursor()
        cur.execute(_CREATE_RECORDS)
        cur.execute(_CREATE_CANDIDATES)
        cur.execute(_CREATE_USES)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def capability_manifest(self) -> MemoryStoreCapabilityManifest:
        return MemoryStoreCapabilityManifest(
            adapter_id="platform-native-sqlite",
            provider="platform_native",
            adapter_version="0.1.0",
            deployment_model="in_process_sqlite",
            source_refs=("docs/architecture/memory/production-memory-system-strategy.md",),
            supports_memory_records=True,
            supports_memory_candidates=True,
            supports_memory_uses=True,
            supports_ttl=True,
            supports_delete=True,
            supports_export=True,
            supports_tenant_isolation=True,
            supports_metadata_filters=True,
            supports_raw_payload_blocking=True,
            supports_human_review_gate=True,
            stores_raw_payloads_by_default=False,
            network_required=False,
            requires_secrets=False,
            sanitized_fixture_only=False,
            default_for_legal_memory=False,
            approved_for_live_legal_memory=True,
            data_residency="process_local",
            deletion_model="ttl_and_tombstone",
            export_model="memory_record_sqlite_export",
            metadata={"privacy": "refs_hashes_lengths_statuses_only"},
        )

    # ── Record write ──────────────────────────────────────────────────────────

    def upsert(self, record: MemoryRecord) -> None:
        """Validate and persist a MemoryRecord (INSERT OR REPLACE)."""
        _validate_record(record)
        row = _record_to_row(record)
        self._conn.execute(
            """
            INSERT OR REPLACE INTO memory_records
            (memory_id, tenant_id, workspace_id, scope, status, sensitivity,
             created_at, updated_at, source_refs, summary, subject,
             related_user_id, session_id, raw_payload_ref, confidence,
             ttl_expires_at, deleted_at, deletion_reason, industry_context, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            row,
        )
        self._conn.commit()

    # ── Record read ───────────────────────────────────────────────────────────

    def get(self, memory_id: str) -> MemoryRecord | None:
        """Return a copy-safe MemoryRecord by id, or None if not found."""
        cur = self._conn.execute(
            "SELECT * FROM memory_records WHERE memory_id = ?", (memory_id,)
        )
        row = cur.fetchone()
        return _copy_record(_row_to_record(row)) if row is not None else None

    def list_for_query(
        self,
        query: MemoryQuery,
        *,
        policy: MemoryStorePolicy | None = None,
    ) -> tuple[MemoryRecord, ...]:
        """Return records visible for the query using coarse SQL filters plus Python visibility check."""
        cfg = policy or MemoryStorePolicy()
        now = _query_now(query, self._clock)

        sql = "SELECT * FROM memory_records WHERE tenant_id = ? AND workspace_id = ?"
        params: list[Any] = [query.tenant_id, query.workspace_id]

        if not query.include_deleted:
            sql += " AND deleted_at IS NULL"

        if not query.include_expired:
            now_str = _timestamp(now)
            sql += " AND (ttl_expires_at IS NULL OR ttl_expires_at > ?)"
            params.append(now_str)

        if query.sensitivities:
            placeholders = ",".join("?" * len(query.sensitivities))
            sql += f" AND sensitivity IN ({placeholders})"
            params.extend(query.sensitivities)

        if query.statuses:
            placeholders = ",".join("?" * len(query.statuses))
            sql += f" AND status IN ({placeholders})"
            params.extend(query.statuses)

        if query.minimum_confidence is not None:
            sql += " AND (confidence IS NOT NULL AND confidence >= ?)"
            params.append(float(query.minimum_confidence))

        if query.ttl_expires_before is not None:
            sql += " AND (ttl_expires_at IS NOT NULL AND ttl_expires_at < ?)"
            params.append(query.ttl_expires_before)

        if query.ttl_expires_after is not None:
            sql += " AND (ttl_expires_at IS NOT NULL AND ttl_expires_at > ?)"
            params.append(query.ttl_expires_after)

        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()
        results = []
        for row in rows:
            record = _row_to_record(row)
            if _record_visible(record, query, cfg, now):
                results.append(_copy_record(record))
        return tuple(results)

    def search(
        self,
        query: MemoryQuery,
        *,
        policy: MemoryStorePolicy | None = None,
    ) -> tuple[MemorySearchResult, ...]:
        """Search and rank memory records using deterministic relevance scoring."""
        cfg = policy or MemoryStorePolicy()
        return _search_records(self.list_for_query(query, policy=cfg), query, cfg)

    # ── Record lifecycle ──────────────────────────────────────────────────────

    def mark_deleted(
        self,
        memory_id: str,
        *,
        deleted_at: str | datetime | None = None,
        reason: str = "",
    ) -> MemoryRecord:
        """Tombstone a record: set status=deleted, deleted_at, deletion_reason."""
        cur = self._conn.execute(
            "SELECT * FROM memory_records WHERE memory_id = ?", (memory_id,)
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"memory record not found: {memory_id!r}")
        record = _row_to_record(row)
        ts = _timestamp(deleted_at or _clock_now(self._clock))
        from dataclasses import replace as _replace
        deleted = _replace(
            record,
            status="deleted",
            deleted_at=ts,
            deletion_reason=reason or "deleted_by_policy",
            updated_at=ts,
        )
        self.upsert(deleted)
        return _copy_record(deleted)

    def export_records(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        """Export all records (including deleted/expired) for the given tenant/workspace scope."""
        export_query = MemoryQuery(
            tenant_id=query.tenant_id,
            workspace_id=query.workspace_id,
            now=query.now,
            max_results=query.max_results,
            include_deleted=True,
            include_expired=True,
        )
        # Bypass _record_visible for export — return all rows for the scope
        cur = self._conn.execute(
            "SELECT * FROM memory_records WHERE tenant_id = ? AND workspace_id = ?",
            (query.tenant_id, query.workspace_id),
        )
        return tuple(_copy_record(_row_to_record(row)) for row in cur.fetchall())

    def expire_records(self, *, now: str | None = None) -> int:
        """Mark all active records whose TTL has passed as status=expired. Returns count."""
        now_str = now if now is not None else _timestamp(_clock_now(self._clock))
        cur = self._conn.execute(
            """
            UPDATE memory_records
            SET status = 'expired', updated_at = ?
            WHERE status = 'active'
              AND ttl_expires_at IS NOT NULL
              AND ttl_expires_at <= ?
            """,
            (now_str, now_str),
        )
        self._conn.commit()
        return cur.rowcount

    # ── Candidate write/read ──────────────────────────────────────────────────

    def upsert_candidate(self, candidate: MemoryCandidate) -> None:
        """Validate and persist a MemoryCandidate (INSERT OR REPLACE)."""
        _validate_candidate(candidate)
        row = _candidate_to_row(candidate)
        self._conn.execute(
            """
            INSERT OR REPLACE INTO memory_candidates
            (candidate_id, tenant_id, workspace_id, status, source_refs, created_at,
             proposed_scope, proposed_sensitivity, proposed_action, memory_id,
             proposed_record_ref, reason, confidence, requires_human_review,
             raw_payload_ref, industry_context, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            row,
        )
        self._conn.commit()

    def get_candidate(self, candidate_id: str) -> MemoryCandidate | None:
        """Return a copy-safe MemoryCandidate by id, or None if not found."""
        cur = self._conn.execute(
            "SELECT * FROM memory_candidates WHERE candidate_id = ?", (candidate_id,)
        )
        row = cur.fetchone()
        return _copy_candidate(_row_to_candidate(row)) if row is not None else None

    def list_candidates(self, query: MemoryQuery) -> tuple[MemoryCandidate, ...]:
        """Return all candidates for the query's tenant/workspace scope."""
        cur = self._conn.execute(
            "SELECT * FROM memory_candidates WHERE tenant_id = ? AND workspace_id = ?",
            (query.tenant_id, query.workspace_id),
        )
        return tuple(_copy_candidate(_row_to_candidate(row)) for row in cur.fetchall())

    # ── Use write/read ────────────────────────────────────────────────────────

    def record_memory_use(self, use: MemoryUse) -> None:
        """Validate and persist a MemoryUse (INSERT OR REPLACE)."""
        _validate_use(use)
        row = _use_to_row(use)
        self._conn.execute(
            """
            INSERT OR REPLACE INTO memory_uses
            (use_id, memory_id, context_bundle_id, used_at, purpose,
             run_id, turn_id, relevance_score, policy_result, source_refs, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            row,
        )
        self._conn.commit()

    def list_memory_uses(self, query: MemoryQuery) -> tuple[MemoryUse, ...]:
        """Return all MemoryUse rows whose memory_id belongs to the query's workspace."""
        cur = self._conn.execute(
            """
            SELECT u.* FROM memory_uses u
            JOIN memory_records r ON u.memory_id = r.memory_id
            WHERE r.tenant_id = ? AND r.workspace_id = ?
            """,
            (query.tenant_id, query.workspace_id),
        )
        return tuple(_copy_use(_row_to_use(row)) for row in cur.fetchall())


# ── Row serialization helpers ──────────────────────────────────────────────────


def _record_to_row(record: MemoryRecord) -> tuple[Any, ...]:
    return (
        record.memory_id,
        record.tenant_id,
        record.workspace_id,
        str(record.scope),
        str(record.status),
        str(record.sensitivity),
        record.created_at,
        record.updated_at,
        json.dumps(list(record.source_refs), ensure_ascii=False),
        record.summary,
        record.subject,
        record.related_user_id,
        record.session_id,
        record.raw_payload_ref,
        float(record.confidence) if record.confidence is not None else None,
        record.ttl_expires_at,
        record.deleted_at,
        record.deletion_reason,
        json.dumps(dict(record.industry_context), ensure_ascii=False),
        json.dumps(dict(record.metadata), ensure_ascii=False),
    )


def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
    d = dict(row)
    return MemoryRecord(
        memory_id=d["memory_id"],
        tenant_id=d["tenant_id"],
        workspace_id=d["workspace_id"],
        scope=d["scope"],
        status=d["status"],
        sensitivity=d["sensitivity"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        source_refs=json.loads(d["source_refs"]),
        summary=d["summary"],
        subject=d["subject"],
        related_user_id=d["related_user_id"],
        session_id=d["session_id"],
        raw_payload_ref=d["raw_payload_ref"],
        confidence=d["confidence"],
        ttl_expires_at=d["ttl_expires_at"],
        deleted_at=d["deleted_at"],
        deletion_reason=d["deletion_reason"],
        industry_context=json.loads(d["industry_context"]),
        metadata=json.loads(d["metadata"]),
    )


def _candidate_to_row(candidate: MemoryCandidate) -> tuple[Any, ...]:
    return (
        candidate.candidate_id,
        candidate.tenant_id,
        candidate.workspace_id,
        str(candidate.status),
        json.dumps(list(candidate.source_refs), ensure_ascii=False),
        candidate.created_at,
        str(candidate.proposed_scope) if candidate.proposed_scope is not None else None,
        str(candidate.proposed_sensitivity) if candidate.proposed_sensitivity is not None else None,
        candidate.proposed_action,
        candidate.memory_id,
        candidate.proposed_record_ref,
        candidate.reason,
        float(candidate.confidence) if candidate.confidence is not None else None,
        1 if candidate.requires_human_review else 0,
        candidate.raw_payload_ref,
        json.dumps(dict(candidate.industry_context), ensure_ascii=False),
        json.dumps(dict(candidate.metadata), ensure_ascii=False),
    )


def _row_to_candidate(row: sqlite3.Row) -> MemoryCandidate:
    d = dict(row)
    return MemoryCandidate(
        candidate_id=d["candidate_id"],
        tenant_id=d["tenant_id"],
        workspace_id=d["workspace_id"],
        status=d["status"],
        source_refs=json.loads(d["source_refs"]),
        created_at=d["created_at"],
        proposed_scope=d["proposed_scope"],
        proposed_sensitivity=d["proposed_sensitivity"],
        proposed_action=d["proposed_action"],
        memory_id=d["memory_id"],
        proposed_record_ref=d["proposed_record_ref"],
        reason=d["reason"],
        confidence=d["confidence"],
        requires_human_review=bool(d["requires_human_review"]),
        raw_payload_ref=d["raw_payload_ref"],
        industry_context=json.loads(d["industry_context"]),
        metadata=json.loads(d["metadata"]),
    )


def _use_to_row(use: MemoryUse) -> tuple[Any, ...]:
    return (
        use.use_id,
        use.memory_id,
        use.context_bundle_id,
        use.used_at,
        use.purpose,
        use.run_id,
        use.turn_id,
        float(use.relevance_score) if use.relevance_score is not None else None,
        use.policy_result,
        json.dumps(list(use.source_refs), ensure_ascii=False),
        json.dumps(dict(use.metadata), ensure_ascii=False),
    )


def _row_to_use(row: sqlite3.Row) -> MemoryUse:
    d = dict(row)
    return MemoryUse(
        use_id=d["use_id"],
        memory_id=d["memory_id"],
        context_bundle_id=d["context_bundle_id"],
        used_at=d["used_at"],
        purpose=d["purpose"],
        run_id=d["run_id"],
        turn_id=d["turn_id"],
        relevance_score=d["relevance_score"],
        policy_result=d["policy_result"],
        source_refs=json.loads(d["source_refs"]),
        metadata=json.loads(d["metadata"]),
    )


__all__ = ["SQLiteMemoryStore"]
