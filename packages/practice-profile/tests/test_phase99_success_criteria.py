"""Phase 99 success criteria verification test.

Asserts all 6 success criteria from the Phase 99 roadmap:

1. 执业配置在平台侧建模并按租户存储：审查立场、升级矩阵、文书风格、管辖识别
2. 执行时执业配置被注入 skill 上下文，覆盖索引中标记了 practice_profile_dependency 的全部 skill
3. 未配置时降级"临时模式"：使用通用默认值，且每个输出被标记 [临时模式]
4. 冷启动访谈可通过 elicitation.requested 完成——多轮 2-4 题采集，答案写回租户执业配置
5. 执业配置的读写经 RBAC 授权，跨租户访问被拒
6. 执业配置不含 secrets，且不进入契约事件日志
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from inkstatute_practice_profile import (
    ColdStartInterviewOrchestrator,
    COMMERCIAL_LEGAL_INTERVIEW_STEPS,
    InMemoryPracticeProfileStore,
    PracticeProfile,
    PracticeProfileInjector,
    SecretDetectedError,
    TEMPORARY_MODE_TAG,
    check_read_access,
    check_tenant_access,
    check_write_access,
    create_temporary_profile,
    validate_no_secrets,
)

from platform_contract.elicitation import validate_question_count
from rbac.roles import Role


class TestPhase99SuccessCriteria(unittest.TestCase):
    """Verify all 6 Phase 99 success criteria."""

    # ------------------------------------------------------------------
    # Criterion 1: 执业配置在平台侧建模并按租户存储
    # ------------------------------------------------------------------

    def test_criterion_1_profile_modeled_and_stored(self) -> None:
        """Verifies PracticeProfile models 审查立场, 升级矩阵, 文书风格, 管辖识别;
        verifies InMemoryPracticeProfileStore stores per-tenant."""
        # Create a profile with all required fields
        profile = PracticeProfile(
            tenant_id="t1",
            plugin="commercial-legal",
            identity={"org_name": "测试律所"},
            user_role={"role": "律师"},
            integrations={},
            escalation_matrix={
                "amount_thresholds": [{"limit": "¥50万", "role": "初级律师"}],
                "approval_levels": [{"level": "合伙人", "threshold": "¥500万"}],
                "auto_escalation_triggers": ["无限责任条款"],
            },
            document_style={"revision_tone": "半正式", "citation_style": "法条引用"},
            shared_guardrails={"jurisdiction_identification": "中国大陆法律"},
            plugin_configs={
                "commercial-legal": {
                    "风险偏好": "平衡型",
                    "甲方立场": {"责任限制": "标准立场", "违约金": "可接受备选"},
                    "乙方立场": {"责任限制": "标准立场"},
                    "交易破坏者": "无限责任条款",
                },
            },
        )

        # Verify all modeled fields are present
        self.assertIn("风险偏好", profile.plugin_configs["commercial-legal"])
        self.assertIn("甲方立场", profile.plugin_configs["commercial-legal"])
        self.assertIn("交易破坏者", profile.plugin_configs["commercial-legal"])
        self.assertIn("amount_thresholds", profile.escalation_matrix)
        self.assertIn("auto_escalation_triggers", profile.escalation_matrix)
        self.assertIn("revision_tone", profile.document_style)
        self.assertIn("jurisdiction_identification", profile.shared_guardrails)

        # Verify per-tenant storage
        store = InMemoryPracticeProfileStore()
        store.upsert("t1", profile)
        retrieved = store.get("t1", "commercial-legal")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.tenant_id, "t1")
        self.assertEqual(retrieved.plugin, "commercial-legal")

        # Verify tenant isolation in store
        self.assertIsNone(store.get("t2", "commercial-legal"))

        # Verify round-trip serialization
        round_tripped = PracticeProfile.from_json(profile.to_json())
        self.assertEqual(round_tripped, profile)

    # ------------------------------------------------------------------
    # Criterion 2: 执行时执业配置被注入 skill 上下文
    # ------------------------------------------------------------------

    def test_criterion_2_context_injection_covers_all_dependent_skills(self) -> None:
        """Verifies PracticeProfileInjector injects context for skills with
        practice_profile_dependency=True."""
        # Create a fixture skill index with known dependency flags
        fixture_index = {
            "skills": [
                {
                    "skill_id": "contract-review",
                    "plugin": "commercial-legal",
                    "practice_profile_dependency": True,
                },
                {
                    "skill_id": "legal-research",
                    "plugin": "commercial-legal",
                    "practice_profile_dependency": True,
                },
                {
                    "skill_id": "non-dependent-skill",
                    "plugin": "commercial-legal",
                    "practice_profile_dependency": False,
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "skill-index.json"
            index_path.write_text(json.dumps(fixture_index), encoding="utf-8")

            store = InMemoryPracticeProfileStore()
            # Store a real profile
            store.upsert("t1", PracticeProfile(
                tenant_id="t1",
                plugin="commercial-legal",
                identity={"org_name": "测试律所"},
                user_role={"role": "律师"},
                shared_guardrails={"jurisdiction_identification": "中国大陆法律"},
                plugin_configs={"commercial-legal": {"风险偏好": "平衡型"}},
            ))

            injector = PracticeProfileInjector(store, index_path)

            # Dependent skills should get injection
            for skill_id in ["contract-review", "legal-research"]:
                with self.subTest(skill=skill_id):
                    result = injector.inject(skill_id, "t1")
                    self.assertTrue(result.profile_injected)
                    self.assertIn("## 执业配置", result.context_section)
                    self.assertFalse(result.temporary_mode)

            # Non-dependent skill should NOT get injection
            result = injector.inject("non-dependent-skill", "t1")
            self.assertFalse(result.profile_injected)
            self.assertEqual(result.context_section, "")

    # ------------------------------------------------------------------
    # Criterion 3: 未配置时降级"临时模式"
    # ------------------------------------------------------------------

    def test_criterion_3_temporary_mode_tagged(self) -> None:
        """Verifies that when no profile exists, create_temporary_profile is used,
        temporary_mode=True, and the [临时模式] tag is present in the injected context."""
        fixture_index = {
            "skills": [
                {
                    "skill_id": "dependent-skill",
                    "plugin": "commercial-legal",
                    "practice_profile_dependency": True,
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "skill-index.json"
            index_path.write_text(json.dumps(fixture_index), encoding="utf-8")

            store = InMemoryPracticeProfileStore()
            # No profile stored — should use temporary mode
            injector = PracticeProfileInjector(store, index_path)

            result = injector.inject("dependent-skill", "t1")
            self.assertTrue(result.profile_injected)
            self.assertTrue(result.temporary_mode)
            # The tag must be present and never omitted
            self.assertIn(TEMPORARY_MODE_TAG, result.context_section)
            # The tag should be at the beginning
            self.assertTrue(
                result.context_section.startswith(TEMPORARY_MODE_TAG),
                f"Context section should start with {TEMPORARY_MODE_TAG}",
            )

        # Also verify create_temporary_profile directly
        temp_profile = create_temporary_profile("t1", "commercial-legal")
        self.assertTrue(temp_profile.temporary_mode)
        self.assertEqual(temp_profile.user_role["role"], "律师")
        self.assertEqual(
            temp_profile.shared_guardrails["jurisdiction_identification"],
            "中国大陆法律",
        )

    # ------------------------------------------------------------------
    # Criterion 4: 冷启动访谈可通过 elicitation.requested 完成
    # ------------------------------------------------------------------

    def test_criterion_4_cold_start_interview_via_elicitation(self) -> None:
        """Verifies ColdStartInterviewOrchestrator emits ElicitationRequestedPayload
        with 2-4 questions per round, 5 rounds, and answers are written back to the store."""
        store = InMemoryPracticeProfileStore()
        orchestrator = ColdStartInterviewOrchestrator(
            store, COMMERCIAL_LEGAL_INTERVIEW_STEPS,
        )

        # Verify 5 steps
        self.assertEqual(orchestrator.total_steps, 5)

        # Start the interview
        state = orchestrator.start("t1", "commercial-legal")
        self.assertEqual(state.current_step_index, 0)
        self.assertEqual(len(state.completed_steps), 0)

        # Verify each step emits a valid elicitation with 2-4 questions
        sample_answers = {
            "identity-team": {
                "identity-team.company_name": "测试律所",
                "identity-team.entity_type": "有限责任公司",
                "identity-team.team_size": "10",
                "identity-team.counterparty_type": "大客户",
            },
            "review-stance": {
                "review-stance.risk_appetite": "平衡型",
                "review-stance.primary_side": "甲方",
            },
            "escalation-rules": {
                "escalation-rules.junior_threshold": "¥50万",
                "escalation-rules.auto_escalation_triggers": "无限责任条款",
            },
            "document-style": {
                "document-style.revision_tone": "半正式",
                "document-style.citation_preference": "含法条引用",
            },
            "jurisdiction-profile": {
                "jurisdiction-profile.governing_law": "中国大陆法律",
                "jurisdiction-profile.special_zones": "无",
            },
        }

        step_ids = []
        for i in range(orchestrator.total_steps):
            with self.subTest(step=i):
                elicitation = orchestrator.get_current_elicitation(state)
                self.assertIsNotNone(elicitation.interrupt_id)
                self.assertIsNotNone(elicitation.intro)
                # 2-4 questions per round
                validate_question_count(elicitation.questions)
                self.assertGreaterEqual(len(elicitation.questions), 2)
                self.assertLessEqual(len(elicitation.questions), 4)

                step_id = elicitation.metadata.get("step_id")
                step_ids.append(step_id)

                # Submit answers
                state = orchestrator.submit_answers(state, sample_answers[step_id])

        # Verify all 5 steps completed
        self.assertTrue(orchestrator.is_complete(state))
        self.assertEqual(len(state.completed_steps), 5)

        # Finalize — should write to store
        profile = orchestrator.finalize(state)
        self.assertFalse(profile.temporary_mode)

        # Verify the profile is stored
        stored = store.get("t1", "commercial-legal")
        self.assertIsNotNone(stored)
        self.assertFalse(stored.temporary_mode)

        # Verify answers were written back
        self.assertEqual(stored.identity["org_name"], "测试律所")
        self.assertEqual(
            stored.plugin_configs["commercial-legal"]["风险偏好"], "平衡型"
        )
        self.assertEqual(
            stored.shared_guardrails["jurisdiction_identification"],
            "中国大陆法律",
        )

    # ------------------------------------------------------------------
    # Criterion 5: 执业配置的读写经 RBAC 授权，跨租户访问被拒
    # ------------------------------------------------------------------

    def test_criterion_5_rbac_authorized(self) -> None:
        """Verifies check_read_access allows all roles, check_write_access
        allows only ADMIN/OPERATOR, check_tenant_access denies cross-tenant."""
        # Read access — all 4 roles
        for role in [Role.ADMIN, Role.OPERATOR, Role.LAWYER, Role.VIEWER]:
            with self.subTest(role=role, operation="read"):
                self.assertTrue(check_read_access(role))

        # Write access — ADMIN and OPERATOR only
        self.assertTrue(check_write_access(Role.ADMIN))
        self.assertTrue(check_write_access(Role.OPERATOR))
        self.assertFalse(check_write_access(Role.LAWYER))
        self.assertFalse(check_write_access(Role.VIEWER))

        # Tenant access — same tenant allowed, cross-tenant denied
        self.assertTrue(check_tenant_access("t1", "t1"))
        self.assertFalse(check_tenant_access("t1", "t2"))
        self.assertFalse(check_tenant_access("t2", "t1"))

    # ------------------------------------------------------------------
    # Criterion 6: 执业配置不含 secrets，且不进入契约事件日志
    # ------------------------------------------------------------------

    def test_criterion_6_no_secrets_no_event_log(self) -> None:
        """Verifies validate_no_secrets rejects secret patterns; verifies the
        injector and orchestrator do NOT create RunEvent objects."""
        # Secret patterns are rejected
        for secret_field in ["api_key", "password", "access_token", "secret_key"]:
            with self.subTest(field=secret_field):
                with self.assertRaises(SecretDetectedError):
                    validate_no_secrets({secret_field: "some-value"})

        # Normal profile data passes
        validate_no_secrets({
            "org_name": "测试律所",
            "risk_appetite": "平衡型",
            "jurisdiction": "中国大陆法律",
        })

        # Verify the error message never contains the secret value
        try:
            validate_no_secrets({"api_key": "super-secret-123"})
        except SecretDetectedError as e:
            self.assertNotIn("super-secret-123", str(e))

        # Verify the injector does NOT create RunEvent objects
        # (it returns a ProfileInjectionResult, not a RunEvent)
        fixture_index = {
            "skills": [
                {
                    "skill_id": "test-skill",
                    "plugin": "commercial-legal",
                    "practice_profile_dependency": True,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "skill-index.json"
            index_path.write_text(json.dumps(fixture_index), encoding="utf-8")

            store = InMemoryPracticeProfileStore()
            injector = PracticeProfileInjector(store, index_path)
            result = injector.inject("test-skill", "t1")
            # The result is a ProfileInjectionResult, not a RunEvent
            self.assertFalse(hasattr(result, "occurred_at"))
            self.assertFalse(hasattr(result, "seq"))
            self.assertFalse(hasattr(result, "event_type"))

        # Verify the orchestrator does NOT create RunEvent objects
        # (it returns ElicitationRequestedPayload, not RunEvent)
        orchestrator = ColdStartInterviewOrchestrator(
            store, COMMERCIAL_LEGAL_INTERVIEW_STEPS,
        )
        state = orchestrator.start("t1", "commercial-legal")
        elicitation = orchestrator.get_current_elicitation(state)
        # The elicitation is an ElicitationRequestedPayload, not a RunEvent
        self.assertFalse(hasattr(elicitation, "occurred_at"))
        self.assertFalse(hasattr(elicitation, "seq"))
        self.assertFalse(hasattr(elicitation, "event_type"))
        self.assertTrue(hasattr(elicitation, "interrupt_id"))
        self.assertTrue(hasattr(elicitation, "questions"))


if __name__ == "__main__":
    unittest.main()
