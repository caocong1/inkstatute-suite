"""Writable Skill Registry with CRUD, immutable versioning, rollback,
two-person rule, and per-tenant namespaces.

This module is separate from the frozen read-only ``registry.py`` module.
``SkillRegistryWritePort`` is a new Protocol — ``SkillRegistryPort`` (3
read methods) remains frozen and unchanged.

Every write path (create, update, deactivate, rollback) goes through a
submit → approve flow enforcing the human-review two-person rule:

1. ``submit_create`` / ``submit_update`` / ``submit_deactivate`` /
   ``submit_rollback`` create a pending ``WriteRequest``.
2. ``approve_write`` commits the write, creating a new immutable
   ``SkillVersion`` with an incrementing version number.  The reviewer
   must differ from the requester (self-approval is rejected).
3. ``reject_write`` marks the request as rejected.

Immutable versioning: every committed write creates a new
``SkillVersion``.  Existing versions are never mutated or deleted.
Rollback creates a new version from a prior version's content — history
is never deleted.

Per-tenant namespaces: skills are keyed by ``"{tenant_id}/{name}"``.
All read/write operations require ``tenant_id`` and cross-tenant access
is rejected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from platform_contract.events import JsonObject


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SkillRegistryWriteError(Exception):
    """Raised when a skill registry write operation fails."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewRecord:
    """Record of human review for the two-person rule.

    The ``reviewer`` must differ from the write requester.  Stored
    immutably on every committed ``SkillVersion``.
    """

    reviewer: str
    reviewed_at: str
    decision: str
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class SkillVersion:
    """Immutable version of a skill descriptor.

    Every committed write (create, update, deactivate, rollback) creates
    a new ``SkillVersion`` with an incrementing ``version`` number.
    Existing versions are never mutated.
    """

    skill_id: str
    tenant_id: str
    name: str
    version: int
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    required_tool_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)
    status: str = "active"
    created_by: str = ""
    created_at: str = ""
    review: HumanReviewRecord | None = None


@dataclass(frozen=True, slots=True)
class WriteRequest:
    """Pending write request awaiting human review.

    Created by ``submit_*`` methods and committed (or rejected) by
    ``approve_write`` / ``reject_write``.
    """

    request_id: str
    skill_id: str
    tenant_id: str
    operation: str
    requested_by: str
    requested_at: str
    payload: JsonObject = field(default_factory=dict)
    target_version: int | None = None
    review: HumanReviewRecord | None = None
    status: str = "pending"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SkillRegistryWritePort(Protocol):
    """Write protocol for the Skill Registry — separate from frozen SkillRegistryPort."""

    def submit_create(
        self,
        tenant_id: str,
        name: str,
        *,
        requested_by: str,
        requested_at: str,
        description: str | None = None,
        input_schema_ref: str | None = None,
        output_schema_ref: str | None = None,
        required_tool_refs: list[str] | None = None,
        metadata: JsonObject | None = None,
    ) -> WriteRequest: ...

    def submit_update(
        self,
        tenant_id: str,
        skill_id: str,
        *,
        requested_by: str,
        requested_at: str,
        description: str | None = None,
        input_schema_ref: str | None = None,
        output_schema_ref: str | None = None,
        required_tool_refs: list[str] | None = None,
        metadata: JsonObject | None = None,
    ) -> WriteRequest: ...

    def submit_deactivate(
        self,
        tenant_id: str,
        skill_id: str,
        *,
        requested_by: str,
        requested_at: str,
    ) -> WriteRequest: ...

    def submit_rollback(
        self,
        tenant_id: str,
        skill_id: str,
        target_version: int,
        *,
        requested_by: str,
        requested_at: str,
    ) -> WriteRequest: ...

    def approve_write(
        self,
        request_id: str,
        *,
        reviewer: str,
        reviewed_at: str,
        comment: str | None = None,
    ) -> SkillVersion: ...

    def reject_write(
        self,
        request_id: str,
        *,
        reviewer: str,
        reviewed_at: str,
        comment: str | None = None,
    ) -> WriteRequest: ...

    def list_versions(self, tenant_id: str, skill_id: str) -> list[SkillVersion]: ...

    def get_version(
        self, tenant_id: str, skill_id: str, version: int
    ) -> SkillVersion | None: ...

    def get_current(self, tenant_id: str, skill_id: str) -> SkillVersion | None: ...

    def list_skills(self, tenant_id: str) -> list[SkillVersion]: ...

    def list_pending_writes(self, tenant_id: str) -> list[WriteRequest]: ...


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


def _make_skill_id(tenant_id: str, name: str) -> str:
    """Construct a tenant-namespaced skill_id."""
    return f"{tenant_id}/{name}"


class WritableSkillRegistry:
    """In-memory WritableSkillRegistry implementing SkillRegistryWritePort.

    Stores versions per skill keyed by ``"{tenant_id}/{name}"`` and
    pending write requests keyed by ``request_id``.  Every committed
    write creates a new immutable ``SkillVersion``.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[SkillVersion]] = {}
        self._pending: dict[str, WriteRequest] = {}
        self._counter: int = 0

    # ------------------------------------------------------------------
    # Submit (create pending write requests)
    # ------------------------------------------------------------------

    def submit_create(
        self,
        tenant_id: str,
        name: str,
        *,
        requested_by: str,
        requested_at: str,
        description: str | None = None,
        input_schema_ref: str | None = None,
        output_schema_ref: str | None = None,
        required_tool_refs: list[str] | None = None,
        metadata: JsonObject | None = None,
    ) -> WriteRequest:
        """Submit a create request for a new skill in *tenant_id*.

        Raises ``SkillRegistryWriteError`` if an active skill with the
        same name already exists in the tenant.
        """
        skill_id = _make_skill_id(tenant_id, name)
        current = self._get_current_unchecked(skill_id)
        if current is not None and current.status == "active":
            raise SkillRegistryWriteError(
                f"skill already exists and is active: {skill_id}"
            )
        request_id = self._new_request_id()
        req = WriteRequest(
            request_id=request_id,
            skill_id=skill_id,
            tenant_id=tenant_id,
            operation="create",
            requested_by=requested_by,
            requested_at=requested_at,
            payload={
                "name": name,
                "description": description,
                "input_schema_ref": input_schema_ref,
                "output_schema_ref": output_schema_ref,
                "required_tool_refs": list(required_tool_refs or []),
                "metadata": dict(metadata or {}),
            },
        )
        self._pending[request_id] = req
        return req

    def submit_update(
        self,
        tenant_id: str,
        skill_id: str,
        *,
        requested_by: str,
        requested_at: str,
        description: str | None = None,
        input_schema_ref: str | None = None,
        output_schema_ref: str | None = None,
        required_tool_refs: list[str] | None = None,
        metadata: JsonObject | None = None,
    ) -> WriteRequest:
        """Submit an update request for an existing active skill.

        Raises ``SkillRegistryWriteError`` if the skill is not found,
        belongs to a different tenant, or is deactivated.
        """
        current = self._get_current_or_raise(tenant_id, skill_id)
        if current.status != "active":
            raise SkillRegistryWriteError(
                f"cannot update deactivated skill: {skill_id}"
            )
        request_id = self._new_request_id()
        req = WriteRequest(
            request_id=request_id,
            skill_id=skill_id,
            tenant_id=tenant_id,
            operation="update",
            requested_by=requested_by,
            requested_at=requested_at,
            payload={
                "name": current.name,
                "description": description,
                "input_schema_ref": input_schema_ref,
                "output_schema_ref": output_schema_ref,
                "required_tool_refs": list(required_tool_refs or []),
                "metadata": dict(metadata or {}),
            },
        )
        self._pending[request_id] = req
        return req

    def submit_deactivate(
        self,
        tenant_id: str,
        skill_id: str,
        *,
        requested_by: str,
        requested_at: str,
    ) -> WriteRequest:
        """Submit a deactivate request for an existing active skill.

        Raises ``SkillRegistryWriteError`` if the skill is not found,
        belongs to a different tenant, or is already deactivated.
        """
        current = self._get_current_or_raise(tenant_id, skill_id)
        if current.status != "active":
            raise SkillRegistryWriteError(
                f"skill already deactivated: {skill_id}"
            )
        request_id = self._new_request_id()
        req = WriteRequest(
            request_id=request_id,
            skill_id=skill_id,
            tenant_id=tenant_id,
            operation="deactivate",
            requested_by=requested_by,
            requested_at=requested_at,
            payload={"name": current.name},
        )
        self._pending[request_id] = req
        return req

    def submit_rollback(
        self,
        tenant_id: str,
        skill_id: str,
        target_version: int,
        *,
        requested_by: str,
        requested_at: str,
    ) -> WriteRequest:
        """Submit a rollback request to restore a prior version's content.

        Raises ``SkillRegistryWriteError`` if the skill or target
        version is not found, or the skill belongs to a different
        tenant.
        """
        self._check_tenant(tenant_id, skill_id)
        target = self.get_version(tenant_id, skill_id, target_version)
        if target is None:
            raise SkillRegistryWriteError(
                f"target version not found: {skill_id} v{target_version}"
            )
        request_id = self._new_request_id()
        req = WriteRequest(
            request_id=request_id,
            skill_id=skill_id,
            tenant_id=tenant_id,
            operation="rollback",
            requested_by=requested_by,
            requested_at=requested_at,
            payload={},
            target_version=target_version,
        )
        self._pending[request_id] = req
        return req

    # ------------------------------------------------------------------
    # Approve / Reject (two-person rule)
    # ------------------------------------------------------------------

    def approve_write(
        self,
        request_id: str,
        *,
        reviewer: str,
        reviewed_at: str,
        comment: str | None = None,
    ) -> SkillVersion:
        """Approve a pending write request and commit it.

        Enforces the two-person rule: ``reviewer`` must differ from the
        request's ``requested_by``.  Creates a new immutable
        ``SkillVersion`` with an incrementing version number.

        Raises ``SkillRegistryWriteError`` if the request is not found,
        not pending, or the reviewer equals the requester (self-
        approval).
        """
        req = self._pending.get(request_id)
        if req is None:
            raise SkillRegistryWriteError(
                f"write request not found: {request_id}"
            )
        if req.status != "pending":
            raise SkillRegistryWriteError(
                f"write request is not pending: {request_id} (status={req.status})"
            )
        if reviewer == req.requested_by:
            raise SkillRegistryWriteError(
                "two-person rule violation: reviewer must differ from requester"
            )

        review = HumanReviewRecord(
            reviewer=reviewer,
            reviewed_at=reviewed_at,
            decision="approved",
            comment=comment,
        )

        version = self._commit_write(req, review)

        # Update the pending request to approved+committed
        approved_req = WriteRequest(
            request_id=req.request_id,
            skill_id=req.skill_id,
            tenant_id=req.tenant_id,
            operation=req.operation,
            requested_by=req.requested_by,
            requested_at=req.requested_at,
            payload=req.payload,
            target_version=req.target_version,
            review=review,
            status="approved",
        )
        self._pending[request_id] = approved_req
        return version

    def reject_write(
        self,
        request_id: str,
        *,
        reviewer: str,
        reviewed_at: str,
        comment: str | None = None,
    ) -> WriteRequest:
        """Reject a pending write request.

        No new version is created.  The request is marked as rejected
        with a ``HumanReviewRecord``.
        """
        req = self._pending.get(request_id)
        if req is None:
            raise SkillRegistryWriteError(
                f"write request not found: {request_id}"
            )
        if req.status != "pending":
            raise SkillRegistryWriteError(
                f"write request is not pending: {request_id} (status={req.status})"
            )
        review = HumanReviewRecord(
            reviewer=reviewer,
            reviewed_at=reviewed_at,
            decision="rejected",
            comment=comment,
        )
        rejected_req = WriteRequest(
            request_id=req.request_id,
            skill_id=req.skill_id,
            tenant_id=req.tenant_id,
            operation=req.operation,
            requested_by=req.requested_by,
            requested_at=req.requested_at,
            payload=req.payload,
            target_version=req.target_version,
            review=review,
            status="rejected",
        )
        self._pending[request_id] = rejected_req
        return rejected_req

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list_versions(self, tenant_id: str, skill_id: str) -> list[SkillVersion]:
        """Return all versions for a skill, ordered by version number.

        Raises ``SkillRegistryWriteError`` on cross-tenant access.
        """
        self._check_tenant(tenant_id, skill_id)
        return list(self._versions.get(skill_id, []))

    def get_version(
        self, tenant_id: str, skill_id: str, version: int
    ) -> SkillVersion | None:
        """Return a specific version of a skill, or ``None`` if not found.

        Raises ``SkillRegistryWriteError`` on cross-tenant access.
        """
        self._check_tenant(tenant_id, skill_id)
        for v in self._versions.get(skill_id, []):
            if v.version == version:
                return v
        return None

    def get_current(self, tenant_id: str, skill_id: str) -> SkillVersion | None:
        """Return the latest version of a skill, or ``None`` if not found.

        Returns ``None`` for cross-tenant access (treated as not found).
        """
        current = self._get_current_unchecked(skill_id)
        if current is None:
            return None
        if current.tenant_id != tenant_id:
            return None
        return current

    def list_skills(self, tenant_id: str) -> list[SkillVersion]:
        """Return all current active skills for *tenant_id* only.

        Deactivated skills are excluded.  Skills from other tenants are
        never returned.
        """
        result: list[SkillVersion] = []
        for skill_id, versions in self._versions.items():
            if not versions:
                continue
            current = versions[-1]
            if current.tenant_id == tenant_id and current.status == "active":
                result.append(current)
        return result

    def list_pending_writes(self, tenant_id: str) -> list[WriteRequest]:
        """Return all pending write requests for *tenant_id*."""
        return [
            req
            for req in self._pending.values()
            if req.tenant_id == tenant_id and req.status == "pending"
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new_request_id(self) -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())

    def _check_tenant(self, tenant_id: str, skill_id: str) -> None:
        """Validate that *skill_id* belongs to *tenant_id*.

        Raises ``SkillRegistryWriteError`` on cross-tenant access.
        """
        # skill_id format: "{tenant_id}/{name}"
        if "/" not in skill_id:
            raise SkillRegistryWriteError(
                f"invalid skill_id format (expected tenant/name): {skill_id}"
            )
        skill_tenant = skill_id.split("/", 1)[0]
        if skill_tenant != tenant_id:
            raise SkillRegistryWriteError(
                f"cross-tenant access denied: skill {skill_id} does not belong to tenant {tenant_id}"
            )

    def _get_current_unchecked(self, skill_id: str) -> SkillVersion | None:
        """Return the latest version without tenant check."""
        versions = self._versions.get(skill_id)
        if not versions:
            return None
        return versions[-1]

    def _get_current_or_raise(
        self, tenant_id: str, skill_id: str
    ) -> SkillVersion:
        """Return the current version or raise if not found / cross-tenant."""
        self._check_tenant(tenant_id, skill_id)
        current = self._get_current_unchecked(skill_id)
        if current is None:
            raise SkillRegistryWriteError(f"skill not found: {skill_id}")
        return current

    def _commit_write(
        self, req: WriteRequest, review: HumanReviewRecord
    ) -> SkillVersion:
        """Commit a write request by creating a new immutable SkillVersion."""
        skill_id = req.skill_id
        versions = self._versions.setdefault(skill_id, [])
        next_version = len(versions) + 1

        if req.operation == "create":
            payload = req.payload
            version = SkillVersion(
                skill_id=skill_id,
                tenant_id=req.tenant_id,
                name=payload["name"],
                version=next_version,
                description=payload.get("description"),
                input_schema_ref=payload.get("input_schema_ref"),
                output_schema_ref=payload.get("output_schema_ref"),
                required_tool_refs=list(payload.get("required_tool_refs", [])),
                metadata=dict(payload.get("metadata", {})),
                status="active",
                created_by=req.requested_by,
                created_at=req.requested_at,
                review=review,
            )
        elif req.operation == "update":
            payload = req.payload
            version = SkillVersion(
                skill_id=skill_id,
                tenant_id=req.tenant_id,
                name=payload["name"],
                version=next_version,
                description=payload.get("description"),
                input_schema_ref=payload.get("input_schema_ref"),
                output_schema_ref=payload.get("output_schema_ref"),
                required_tool_refs=list(payload.get("required_tool_refs", [])),
                metadata=dict(payload.get("metadata", {})),
                status="active",
                created_by=req.requested_by,
                created_at=req.requested_at,
                review=review,
            )
        elif req.operation == "deactivate":
            current = versions[-1]
            version = SkillVersion(
                skill_id=skill_id,
                tenant_id=req.tenant_id,
                name=current.name,
                version=next_version,
                description=current.description,
                input_schema_ref=current.input_schema_ref,
                output_schema_ref=current.output_schema_ref,
                required_tool_refs=list(current.required_tool_refs),
                metadata=dict(current.metadata),
                status="deactivated",
                created_by=req.requested_by,
                created_at=req.requested_at,
                review=review,
            )
        elif req.operation == "rollback":
            target = None
            for v in versions:
                if v.version == req.target_version:
                    target = v
                    break
            if target is None:
                raise SkillRegistryWriteError(
                    f"target version not found: {skill_id} v{req.target_version}"
                )
            version = SkillVersion(
                skill_id=skill_id,
                tenant_id=req.tenant_id,
                name=target.name,
                version=next_version,
                description=target.description,
                input_schema_ref=target.input_schema_ref,
                output_schema_ref=target.output_schema_ref,
                required_tool_refs=list(target.required_tool_refs),
                metadata=dict(target.metadata),
                status="active",
                created_by=req.requested_by,
                created_at=req.requested_at,
                review=review,
            )
        else:
            raise SkillRegistryWriteError(
                f"unknown operation: {req.operation}"
            )

        versions.append(version)
        return version


__all__ = [
    "HumanReviewRecord",
    "SkillRegistryWriteError",
    "SkillRegistryWritePort",
    "SkillVersion",
    "WritableSkillRegistry",
    "WriteRequest",
]
