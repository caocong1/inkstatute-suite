"""E2e test for the full cold-start interview flow via Gateway endpoints.

Simulates the complete 5-step interview:
1. POST /v1/practice-profile/interview to start
2. Receive first elicitation (step 1: identity-team, 2-4 questions)
3. Submit answers via POST /v1/practice-profile/interview/answers
4. Repeat for all 5 steps
5. Verify the finalized profile is stored and retrievable via GET
6. Verify validate_question_count passes for every step
7. Verify interview cannot be finalized before all 5 steps are complete
"""

from __future__ import annotations

import asyncio
import unittest

from gateway.app import GatewayApp
from gateway.auth import GatewayAuth
from gateway.config import GatewayConfig
from gateway.practice_profile import GatewayPracticeProfileHandler
from gateway.sessions import GatewaySessionManager
from gateway.sse import GatewaySseStream
from rbac.session import InMemorySessionStore

from inkstatute_practice_profile import (
    ColdStartInterviewOrchestrator,
    COMMERCIAL_LEGAL_INTERVIEW_STEPS,
    InMemoryPracticeProfileStore,
)

from platform_contract.elicitation import validate_question_count

AUTH_HEADERS = {"Authorization": "Bearer test-token"}

# Expected step IDs in order
EXPECTED_STEPS = [
    "identity-team",
    "review-stance",
    "escalation-rules",
    "document-style",
    "jurisdiction-profile",
]

# Sample answers for each step (question_id -> answer)
SAMPLE_ANSWERS: dict[str, dict[str, str]] = {
    "identity-team": {
        "identity-team.company_name": "示例律师事务所",
        "identity-team.entity_type": "有限责任公司",
        "identity-team.team_size": "15",
        "identity-team.counterparty_type": "大客户",
    },
    "review-stance": {
        "review-stance.risk_appetite": "平衡型",
        "review-stance.primary_side": "甲方",
    },
    "escalation-rules": {
        "escalation-rules.junior_threshold": "¥50万",
        "escalation-rules.auto_escalation_triggers": "无限责任条款|知识产权全部转让",
    },
    "document-style": {
        "document-style.revision_tone": "温和但有立场",
        "document-style.citation_preference": "含法条引用",
    },
    "jurisdiction-profile": {
        "jurisdiction-profile.governing_law": "中国大陆法律",
        "jurisdiction-profile.special_zones": "经济特区",
    },
}


def _make_app() -> GatewayApp:
    """Create a GatewayApp with a practice profile handler."""
    config = GatewayConfig(enabled=True)
    auth = GatewayAuth(rbac_enabled=False, static_token="test-token")
    store = InMemorySessionStore()
    session_mgr = GatewaySessionManager(session_store=store, rbac_secret="test-secret")
    sse = GatewaySseStream()

    profile_store = InMemoryPracticeProfileStore()
    orchestrator = ColdStartInterviewOrchestrator(
        profile_store, COMMERCIAL_LEGAL_INTERVIEW_STEPS,
    )
    handler = GatewayPracticeProfileHandler(profile_store, orchestrator)

    return GatewayApp(
        config,
        runtime=object(),
        auth=auth,
        session_manager=session_mgr,
        sse_stream=sse,
        practice_profile_handler=handler,
    )


class TestInterviewE2E(unittest.TestCase):
    """E2e test for the full 5-step cold-start interview flow."""

    def test_full_interview_flow(self) -> None:
        """Complete the full 5-step interview and verify the profile is stored."""
        app = _make_app()

        # Step 1: Start the interview
        start_result = asyncio.run(app.dispatch(
            "POST", "/v1/practice-profile/interview", AUTH_HEADERS,
            {"plugin": "commercial-legal"},
        ))
        self.assertNotIn("error", start_result, f"Start failed: {start_result}")
        self.assertIn("interrupt_id", start_result)
        self.assertIn("intro", start_result)
        self.assertIn("questions", start_result)

        # Verify first elicitation has 2-4 questions
        questions = start_result["questions"]
        self.assertGreaterEqual(len(questions), 2)
        self.assertLessEqual(len(questions), 4)

        # Verify validate_question_count passes for the first step
        from platform_contract.unified_events import ElicitationQuestion, ElicitationOption
        rebuilt_questions = []
        for q in questions:
            opts = [ElicitationOption(label=o["label"], value=o["value"]) for o in q.get("options", [])]
            rebuilt_questions.append(ElicitationQuestion(
                id=q["id"], question=q["question"],
                allow_multiple=q.get("allow_multiple", False),
                options=opts,
            ))
        validate_question_count(rebuilt_questions)  # Should not raise

        # Verify the interrupt_id contains the step_id
        self.assertIn("identity-team", start_result["interrupt_id"])

        # Steps 2-5: Submit answers for each step
        for i, step_id in enumerate(EXPECTED_STEPS):
            with self.subTest(step=step_id, index=i):
                answers = SAMPLE_ANSWERS[step_id]
                result = asyncio.run(app.dispatch(
                    "POST", "/v1/practice-profile/interview/answers", AUTH_HEADERS,
                    {"plugin": "commercial-legal", "answers": answers},
                ))

                if i < len(EXPECTED_STEPS) - 1:
                    # Not the last step — should return next elicitation
                    self.assertNotIn("error", result, f"Step {step_id} failed: {result}")
                    self.assertIn("interrupt_id", result)
                    self.assertIn("questions", result)
                    next_questions = result["questions"]
                    self.assertGreaterEqual(len(next_questions), 2)
                    self.assertLessEqual(len(next_questions), 4)

                    # Verify validate_question_count passes for this step
                    rebuilt = []
                    for q in next_questions:
                        opts = [ElicitationOption(label=o["label"], value=o["value"]) for o in q.get("options", [])]
                        rebuilt.append(ElicitationQuestion(
                            id=q["id"], question=q["question"],
                            allow_multiple=q.get("allow_multiple", False),
                            options=opts,
                        ))
                    validate_question_count(rebuilt)

                    # Verify the next step's interrupt_id contains the next step_id
                    next_step_id = EXPECTED_STEPS[i + 1]
                    self.assertIn(next_step_id, result["interrupt_id"])
                else:
                    # Last step — should finalize
                    self.assertEqual(result["status"], "finalized")
                    self.assertIn("profile", result)
                    profile = result["profile"]
                    self.assertFalse(profile["temporary_mode"])

                    # Verify the profile contains data from interview answers
                    self.assertEqual(profile["identity"]["org_name"], "示例律师事务所")
                    self.assertEqual(profile["identity"]["entity_type"], "有限责任公司")
                    self.assertEqual(profile["user_role"]["role"], "律师")
                    self.assertEqual(
                        profile["plugin_configs"]["commercial-legal"]["风险偏好"],
                        "平衡型",
                    )
                    self.assertEqual(
                        profile["shared_guardrails"]["jurisdiction_identification"],
                        "中国大陆法律",
                    )

        # Verify the stored profile is retrievable via GET
        get_result = asyncio.run(app.dispatch(
            "GET", "/v1/practice-profile?plugin=commercial-legal", AUTH_HEADERS, None,
        ))
        self.assertNotIn("error", get_result, f"GET failed: {get_result}")
        self.assertFalse(get_result["temporary_mode"])
        self.assertEqual(get_result["identity"]["org_name"], "示例律师事务所")

    def test_interview_validate_question_count_all_steps(self) -> None:
        """Verify validate_question_count passes for every step's elicitation."""
        app = _make_app()
        from platform_contract.unified_events import ElicitationQuestion, ElicitationOption

        # Start interview
        asyncio.run(app.dispatch(
            "POST", "/v1/practice-profile/interview", AUTH_HEADERS,
            {"plugin": "commercial-legal"},
        ))

        for i, step_id in enumerate(EXPECTED_STEPS):
            with self.subTest(step=step_id):
                # Get the current elicitation from the handler's state
                handler = app.practice_profile_handler
                assert handler is not None
                state = handler.get_interview_state("default", "commercial-legal")
                self.assertIsNotNone(state, f"Interview state should exist for step {step_id}")

                elicitation = handler._orchestrator.get_current_elicitation(state)
                # validate_question_count should pass
                validate_question_count(elicitation.questions)

                # Submit answers to advance
                answers = SAMPLE_ANSWERS[step_id]
                asyncio.run(app.dispatch(
                    "POST", "/v1/practice-profile/interview/answers", AUTH_HEADERS,
                    {"plugin": "commercial-legal", "answers": answers},
                ))

    def test_interview_cannot_finalize_before_complete(self) -> None:
        """Verify the interview cannot be finalized before all 5 steps are complete."""
        store = InMemoryPracticeProfileStore()
        orchestrator = ColdStartInterviewOrchestrator(
            store, COMMERCIAL_LEGAL_INTERVIEW_STEPS,
        )

        # Start the interview
        state = orchestrator.start("default", "commercial-legal")

        # Try to finalize immediately — should raise
        with self.assertRaises(ValueError) as cm:
            orchestrator.finalize(state)
        self.assertIn("Cannot finalize", str(cm.exception))

        # Submit only 2 steps
        state = orchestrator.submit_answers(state, SAMPLE_ANSWERS["identity-team"])
        state = orchestrator.submit_answers(state, SAMPLE_ANSWERS["review-stance"])

        # Try to finalize — should still raise
        with self.assertRaises(ValueError):
            orchestrator.finalize(state)

    def test_interview_all_5_steps_completed(self) -> None:
        """Verify all 5 steps are completed in the full flow."""
        store = InMemoryPracticeProfileStore()
        orchestrator = ColdStartInterviewOrchestrator(
            store, COMMERCIAL_LEGAL_INTERVIEW_STEPS,
        )

        state = orchestrator.start("default", "commercial-legal")
        self.assertEqual(orchestrator.total_steps, 5)

        for step_id in EXPECTED_STEPS:
            self.assertFalse(orchestrator.is_complete(state))
            state = orchestrator.submit_answers(state, SAMPLE_ANSWERS[step_id])

        self.assertTrue(orchestrator.is_complete(state))
        self.assertEqual(len(state.completed_steps), 5)
        self.assertEqual(state.completed_steps, EXPECTED_STEPS)

        # Finalize should succeed
        profile = orchestrator.finalize(state)
        self.assertFalse(profile.temporary_mode)
        self.assertEqual(profile.tenant_id, "default")
        self.assertEqual(profile.plugin, "commercial-legal")

        # Verify the profile is in the store
        stored = store.get("default", "commercial-legal")
        self.assertIsNotNone(stored)
        self.assertFalse(stored.temporary_mode)


if __name__ == "__main__":
    unittest.main()
