"""Tests for PracticeProfileInjector (injector.py).

Covers PROF-01 (context injection covers all skills with
``practice_profile_dependency``) and PROF-02 (temporary mode
``[临时模式]`` tag in injected context).
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from inkstatute_practice_profile import (
    InMemoryPracticeProfileStore,
    PracticeProfile,
    PracticeProfileInjector,
    ProfileInjectionResult,
    SkillNotFoundError,
    TEMPORARY_MODE_TAG,
)


def _make_index(skills: list[dict]) -> str:
    """Create a temporary skill-index.json and return its path."""
    index_data = {"repos": {}, "skills": skills}
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(index_data, f)
    f.close()
    return f.name


def _make_real_profile() -> PracticeProfile:
    """Create a real (non-temporary) profile for test fixtures."""
    return PracticeProfile(
        tenant_id="t1",
        plugin="commercial-legal",
        identity={
            "org_name": "某律所",
            "entity_type": "有限责任公司",
            "team_size": "5",
        },
        user_role={"role": "律师", "lawyer_contact": "张律师"},
        integrations={"contract_mgmt": "已连接", "e_signature": "未连接"},
        escalation_matrix={
            "junior_threshold": "¥50万",
            "auto_escalation_triggers": ["无限责任条款"],
        },
        document_style={"revision_tone": "温和但有立场", "citation_style": "含法条引用"},
        shared_guardrails={"jurisdiction_identification": "中国大陆法律"},
        plugin_configs={"commercial-legal": {"风险偏好": "平衡型"}},
        temporary_mode=False,
    )


# ---------------------------------------------------------------------------
# ProfileInjectionResult structure tests
# ---------------------------------------------------------------------------


class ProfileInjectionResultStructureTests(unittest.TestCase):
    def test_is_frozen_dataclass_with_slots(self) -> None:
        self.assertTrue(dataclasses.is_dataclass(ProfileInjectionResult))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r = ProfileInjectionResult(
                context_section="", profile_injected=False,
                temporary_mode=False, plugin=None,
            )
            r.profile_injected = True  # type: ignore[misc]

    def test_has_four_fields(self) -> None:
        field_names = {f.name for f in dataclasses.fields(ProfileInjectionResult)}
        self.assertEqual(
            field_names,
            {"context_section", "profile_injected", "temporary_mode", "plugin"},
        )


# ---------------------------------------------------------------------------
# Injector tests — no dependency
# ---------------------------------------------------------------------------


class NoDependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx_path = _make_index([
            {"skill_id": "no-dep", "plugin": "commercial-legal",
             "practice_profile_dependency": False},
        ])
        self.store = InMemoryPracticeProfileStore()
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def tearDown(self) -> None:
        Path(self.idx_path).unlink(missing_ok=True)

    def test_no_dependency_returns_not_injected(self) -> None:
        r = self.injector.inject("no-dep", "t1")
        self.assertFalse(r.profile_injected)
        self.assertEqual(r.context_section, "")
        self.assertFalse(r.temporary_mode)
        self.assertIsNone(r.plugin)

    def test_no_dependency_does_not_access_store(self) -> None:
        """The injector should not call store.get when there's no dependency."""
        # Use a store that raises on get to verify it's not called.
        class FailingStore:
            def get(self, tenant_id, plugin):
                raise AssertionError("store.get should not be called")
            def upsert(self, tenant_id, profile):
                raise AssertionError("store.upsert should not be called")
            def delete(self, tenant_id, plugin):
                raise AssertionError("store.delete should not be called")
            def list_plugins(self, tenant_id):
                raise AssertionError("store.list_plugins should not be called")
        injector = PracticeProfileInjector(FailingStore(), self.idx_path)
        r = injector.inject("no-dep", "t1")
        self.assertFalse(r.profile_injected)


# ---------------------------------------------------------------------------
# Injector tests — dependency + real profile
# ---------------------------------------------------------------------------


class RealProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx_path = _make_index([
            {"skill_id": "dep-skill", "plugin": "commercial-legal",
             "practice_profile_dependency": True},
        ])
        self.store = InMemoryPracticeProfileStore()
        self.store.upsert("t1", _make_real_profile())
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def tearDown(self) -> None:
        Path(self.idx_path).unlink(missing_ok=True)

    def test_dependency_with_real_profile_injects(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertTrue(r.profile_injected)
        self.assertFalse(r.temporary_mode)
        self.assertEqual(r.plugin, "commercial-legal")

    def test_context_starts_with_header(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertTrue(r.context_section.startswith("## 执业配置"))

    def test_context_contains_identity_data(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertIn("某律所", r.context_section)
        self.assertIn("有限责任公司", r.context_section)

    def test_context_contains_subsection_headers(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertIn("### 身份信息", r.context_section)
        self.assertIn("### 升级矩阵", r.context_section)
        self.assertIn("### 文书风格", r.context_section)

    def test_context_contains_plugin_config(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertIn("commercial-legal 配置", r.context_section)
        self.assertIn("风险偏好", r.context_section)

    def test_no_temporary_tag_in_real_profile(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertNotIn(TEMPORARY_MODE_TAG, r.context_section)


# ---------------------------------------------------------------------------
# Injector tests — dependency + no profile (temporary mode)
# ---------------------------------------------------------------------------


class TemporaryModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx_path = _make_index([
            {"skill_id": "dep-skill", "plugin": "commercial-legal",
             "practice_profile_dependency": True},
        ])
        self.store = InMemoryPracticeProfileStore()
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def tearDown(self) -> None:
        Path(self.idx_path).unlink(missing_ok=True)

    def test_temporary_mode_flag(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertTrue(r.profile_injected)
        self.assertTrue(r.temporary_mode)

    def test_temporary_tag_present(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertIn(TEMPORARY_MODE_TAG, r.context_section)

    def test_temporary_tag_starts_context(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertTrue(r.context_section.startswith(TEMPORARY_MODE_TAG))

    def test_temporary_tag_followed_by_header(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        # Tag, then blank line, then ## 执业配置
        self.assertIn(f"{TEMPORARY_MODE_TAG}\n\n## 执业配置", r.context_section)

    def test_temporary_tag_never_omitted(self) -> None:
        """Critical assertion: the [临时模式] tag must never be omitted
        in temporary mode (PROF-02 success criterion 3)."""
        r = self.injector.inject("dep-skill", "t1")
        self.assertTrue(r.temporary_mode)
        self.assertIn(TEMPORARY_MODE_TAG, r.context_section)
        # Also verify the exact tag text
        self.assertIn("[临时模式", r.context_section)
        self.assertIn("配置你的档案以获得定制输出", r.context_section)


# ---------------------------------------------------------------------------
# Injector tests — non-empty subsections only
# ---------------------------------------------------------------------------


class NonEmptySubsectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx_path = _make_index([
            {"skill_id": "dep-skill", "plugin": "commercial-legal",
             "practice_profile_dependency": True},
        ])
        self.store = InMemoryPracticeProfileStore()
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def tearDown(self) -> None:
        Path(self.idx_path).unlink(missing_ok=True)

    def test_only_identity_subsection_included(self) -> None:
        """Profile with only identity data should only show 身份信息."""
        profile = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "某律所"},
        )
        self.store.upsert("t1", profile)
        r = self.injector.inject("dep-skill", "t1")
        self.assertIn("### 身份信息", r.context_section)
        self.assertNotIn("### 可用集成", r.context_section)
        self.assertNotIn("### 升级矩阵", r.context_section)

    def test_empty_profile_shows_only_header(self) -> None:
        """A profile with all empty fields still shows ## 执业配置."""
        profile = PracticeProfile(tenant_id="t1", plugin="commercial-legal")
        self.store.upsert("t1", profile)
        r = self.injector.inject("dep-skill", "t1")
        self.assertTrue(r.context_section.startswith("## 执业配置"))
        # No subsections should be present
        self.assertNotIn("###", r.context_section)

    def test_temporary_profile_shows_default_subsections(self) -> None:
        """Temporary profile has defaults, so subsections appear."""
        r = self.injector.inject("dep-skill", "t1")
        # Temporary profile has user_role, escalation_matrix, document_style,
        # shared_guardrails, and plugin_config — so those subsections appear.
        self.assertIn("### 使用者角色", r.context_section)
        self.assertIn("### 升级矩阵", r.context_section)
        self.assertIn("### 文书风格", r.context_section)
        self.assertIn("### 共享护栏", r.context_section)


# ---------------------------------------------------------------------------
# Injector tests — plugin override
# ---------------------------------------------------------------------------


class PluginOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx_path = _make_index([
            {"skill_id": "dep-skill", "plugin": "commercial-legal",
             "practice_profile_dependency": True},
        ])
        self.store = InMemoryPracticeProfileStore()
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def tearDown(self) -> None:
        Path(self.idx_path).unlink(missing_ok=True)

    def test_plugin_override_uses_override_plugin(self) -> None:
        r = self.injector.inject("dep-skill", "t1", plugin="litigation-legal")
        self.assertEqual(r.plugin, "litigation-legal")
        # No profile for litigation-legal -> temporary mode
        self.assertTrue(r.temporary_mode)

    def test_plugin_override_with_real_profile(self) -> None:
        profile = PracticeProfile(
            tenant_id="t1", plugin="litigation-legal",
            identity={"org_name": "诉讼团队"},
        )
        self.store.upsert("t1", profile)
        r = self.injector.inject("dep-skill", "t1", plugin="litigation-legal")
        self.assertEqual(r.plugin, "litigation-legal")
        self.assertFalse(r.temporary_mode)
        self.assertIn("诉讼团队", r.context_section)

    def test_no_override_uses_index_plugin(self) -> None:
        r = self.injector.inject("dep-skill", "t1")
        self.assertEqual(r.plugin, "commercial-legal")


# ---------------------------------------------------------------------------
# Injector tests — error handling
# ---------------------------------------------------------------------------


class ErrorHandlingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx_path = _make_index([
            {"skill_id": "dep-skill", "plugin": "commercial-legal",
             "practice_profile_dependency": True},
        ])
        self.store = InMemoryPracticeProfileStore()
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def tearDown(self) -> None:
        Path(self.idx_path).unlink(missing_ok=True)

    def test_skill_not_found_raises(self) -> None:
        with self.assertRaises(SkillNotFoundError):
            self.injector.inject("missing-skill", "t1")

    def test_missing_index_file_raises_filenotfound(self) -> None:
        injector = PracticeProfileInjector(
            self.store, "/nonexistent/path/skill-index.json"
        )
        with self.assertRaises(FileNotFoundError):
            injector.inject("dep-skill", "t1")

    def test_no_index_path_raises_filenotfound(self) -> None:
        injector = PracticeProfileInjector(self.store, None)
        with self.assertRaises(FileNotFoundError):
            injector.inject("dep-skill", "t1")


# ---------------------------------------------------------------------------
# Injector tests — no RunEvent created
# ---------------------------------------------------------------------------


class NoRunEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx_path = _make_index([
            {"skill_id": "dep-skill", "plugin": "commercial-legal",
             "practice_profile_dependency": True},
        ])
        self.store = InMemoryPracticeProfileStore()
        self.injector = PracticeProfileInjector(self.store, self.idx_path)

    def tearDown(self) -> None:
        Path(self.idx_path).unlink(missing_ok=True)

    def test_inject_returns_result_not_event(self) -> None:
        """The injector returns a ProfileInjectionResult, not a RunEvent."""
        r = self.injector.inject("dep-skill", "t1")
        self.assertIsInstance(r, ProfileInjectionResult)
        # Verify it's not a RunEvent by checking it doesn't have RunEvent fields
        self.assertFalse(hasattr(r, "event_id"))
        self.assertFalse(hasattr(r, "run_id"))
        self.assertFalse(hasattr(r, "event_type"))

    def test_inject_does_not_import_run_event(self) -> None:
        """The injector module should not import or create RunEvent."""
        import inkstatute_practice_profile.injector as inj_module
        # Check that RunEvent is not in the module's namespace
        self.assertFalse(hasattr(inj_module, "RunEvent"))


if __name__ == "__main__":
    unittest.main()
