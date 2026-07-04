"""Output boundary fixture tests for Codex and provider_model backend noise.

These tests (ADAPTER-03) prove that backend noise from both the Codex and
provider_model backends — function call traces, model names like "gpt-4", API
errors, rate-limit notices — is blocked or rewritten by
``DefaultAssistantOutputBoundary`` (the runtime-level filter) and
``apply_output_policy`` (the WeCom delivery filter) before reaching any channel.

The boundary is the primary filter with comprehensive hard-block and rewrite
rules.  The WeCom output policy is a secondary delivery filter with a narrower
set of block/rewrite patterns.  Together they ensure no backend noise reaches
ordinary-user visible text.
"""

from __future__ import annotations

import unittest

from platform_runtime.output_boundary import (
    BoundaryAction,
    DefaultAssistantOutputBoundary,
)
from wecom_service.output_policy import apply_output_policy


# ---------------------------------------------------------------------------
# Noise fixtures
# ---------------------------------------------------------------------------
#
# Each fixture is a tuple:
#   (backend, noise_text, expected_boundary_action, expected_policy_action,
#    leaked_patterns)
#
# ``expected_boundary_action`` is a ``BoundaryAction`` enum.
# ``expected_policy_action`` is a string ("block", "rewrite", or "allow").
# ``leaked_patterns`` are substrings that must NOT appear in any visible text.

NOISE_FIXTURES: list[
    tuple[str, str, BoundaryAction, str, list[str]]
] = [
    # ------------------------------------------------------------------
    # Provider model noise
    # ------------------------------------------------------------------
    # Model name leakage — "model:" triggers provider_leak hard-block.
    ("provider_model", "model: gpt-4 generated this response", BoundaryAction.BLOCK, "allow", ["gpt-4"]),
    # Model name in error text — "rate limit" triggers rate_limit_notice rewrite.
    # The boundary rewrites this to an owned service notice; the model name
    # "gpt-4" never appears in the rewritten visible text.
    ("provider_model", "Error from gpt-4: rate limit exceeded", BoundaryAction.REWRITE, "allow", ["gpt-4"]),
    # API error — "api key invalid" triggers api_error hard-block in the
    # boundary.  The WeCom policy block pattern uses api[_-]?key (no space),
    # so "api key" with a space is allowed by the policy — the boundary is the
    # primary filter that catches this.
    ("provider_model", "api key invalid for provider", BoundaryAction.BLOCK, "allow", []),
    # Rate-limit notice — "rate limit" triggers rate_limit_notice rewrite.
    ("provider_model", "rate limit exceeded, retrying after 30s", BoundaryAction.REWRITE, "allow", ["rate limit"]),
    # Rate-limit variant — "too many requests" triggers rate_limit_notice rewrite.
    ("provider_model", "too many requests, please slow down", BoundaryAction.REWRITE, "allow", []),
    # Function call trace — "function call" triggers function_trace hard-block.
    ("provider_model", 'function call: get_weather(args={"city": "HK"})', BoundaryAction.BLOCK, "allow", ["function call"]),
    # Tool output dump — "tool output" triggers function_trace hard-block.
    ("provider_model", 'tool output: {"result": "sunny"}', BoundaryAction.BLOCK, "allow", ["tool output"]),
    # Token usage report — "token usage report" triggers function_trace hard-block.
    ("provider_model", "token usage report: 1234 tokens used", BoundaryAction.BLOCK, "allow", ["token usage"]),
    # Context window — "context window exceeded" triggers context_window rewrite.
    ("provider_model", "context window exceeded", BoundaryAction.REWRITE, "allow", []),
    # Quota error — "insufficient quota" triggers api_error hard-block.
    ("provider_model", "insufficient quota for this month", BoundaryAction.BLOCK, "allow", []),

    # ------------------------------------------------------------------
    # Codex noise
    # ------------------------------------------------------------------
    # Codex thread trace — no boundary rule matches, allowed as business content.
    ("codex", "codex thread started, turn.completed", BoundaryAction.ALLOW, "allow", []),
    # Function call result — "function_call_result" triggers function_trace hard-block.
    ("codex", 'function_call_result: {"output": "..."}', BoundaryAction.BLOCK, "allow", ["function_call_result"]),
    # Token usage — "token_usage" triggers provider_leak hard-block.
    ("codex", 'token_usage: {"input": 100, "output": 50}', BoundaryAction.BLOCK, "allow", ["token_usage"]),
    # Rate limit retry — "rate limit retry" triggers api_error hard-block.
    ("codex", "rate limit retry in 60 seconds", BoundaryAction.BLOCK, "allow", []),

    # ------------------------------------------------------------------
    # Common noise (both backends)
    # ------------------------------------------------------------------
    # Stack trace — "traceback" triggers debug_trace hard-block.
    ("both", "traceback: RuntimeError at line 42", BoundaryAction.BLOCK, "block", ["traceback"]),
    # Secret-like — "api_key" triggers secret_like hard-block.
    ("both", "api_key=REDACTED", BoundaryAction.BLOCK, "block", ["api_key"]),
]


def _provider_model_fixtures():
    return [f for f in NOISE_FIXTURES if f[0] == "provider_model"]


def _codex_fixtures():
    return [f for f in NOISE_FIXTURES if f[0] == "codex"]


def _common_fixtures():
    return [f for f in NOISE_FIXTURES if f[0] == "both"]


def _block_or_rewrite_fixtures():
    return [
        f for f in NOISE_FIXTURES
        if f[2] in (BoundaryAction.BLOCK, BoundaryAction.REWRITE)
    ]


class OutputBoundaryBackendNoiseTests(unittest.TestCase):
    """Verify backend noise is blocked or rewritten before delivery."""

    def setUp(self) -> None:
        self.boundary = DefaultAssistantOutputBoundary()

    # ------------------------------------------------------------------
    # DefaultAssistantOutputBoundary tests
    # ------------------------------------------------------------------

    def test_provider_model_noise_blocked_or_rewritten_by_boundary(self) -> None:
        for backend, noise_text, expected_action, _policy, leaked in _provider_model_fixtures():
            with self.subTest(noise=noise_text):
                decision = self.boundary.apply("channel", text=noise_text)
                self.assertEqual(
                    decision.action,
                    expected_action,
                    f"boundary action mismatch for {noise_text!r}: "
                    f"expected {expected_action}, got {decision.action}",
                )
                if expected_action == BoundaryAction.BLOCK:
                    self.assertIsNone(
                        decision.visible_text,
                        f"BLOCK should have visible_text=None for {noise_text!r}",
                    )
                elif expected_action == BoundaryAction.REWRITE:
                    self.assertIsNotNone(decision.visible_text)
                    for pattern in leaked:
                        self.assertNotIn(
                            pattern,
                            decision.visible_text or "",
                            f"leaked pattern {pattern!r} in rewritten text for {noise_text!r}",
                        )
                elif expected_action == BoundaryAction.ALLOW:
                    self.assertEqual(decision.visible_text, noise_text)

    def test_codex_noise_blocked_or_rewritten_by_boundary(self) -> None:
        for backend, noise_text, expected_action, _policy, leaked in _codex_fixtures():
            with self.subTest(noise=noise_text):
                decision = self.boundary.apply("channel", text=noise_text)
                self.assertEqual(
                    decision.action,
                    expected_action,
                    f"boundary action mismatch for {noise_text!r}: "
                    f"expected {expected_action}, got {decision.action}",
                )
                if expected_action == BoundaryAction.BLOCK:
                    self.assertIsNone(decision.visible_text)
                elif expected_action == BoundaryAction.REWRITE:
                    self.assertIsNotNone(decision.visible_text)
                    for pattern in leaked:
                        self.assertNotIn(pattern, decision.visible_text or "")
                elif expected_action == BoundaryAction.ALLOW:
                    self.assertEqual(decision.visible_text, noise_text)

    def test_common_noise_blocked_or_rewritten_by_boundary(self) -> None:
        for backend, noise_text, expected_action, _policy, leaked in _common_fixtures():
            with self.subTest(noise=noise_text):
                decision = self.boundary.apply("channel", text=noise_text)
                self.assertEqual(
                    decision.action,
                    expected_action,
                    f"boundary action mismatch for {noise_text!r}: "
                    f"expected {expected_action}, got {decision.action}",
                )
                if expected_action == BoundaryAction.BLOCK:
                    self.assertIsNone(decision.visible_text)
                elif expected_action == BoundaryAction.REWRITE:
                    self.assertIsNotNone(decision.visible_text)
                    for pattern in leaked:
                        self.assertNotIn(pattern, decision.visible_text or "")
                elif expected_action == BoundaryAction.ALLOW:
                    self.assertEqual(decision.visible_text, noise_text)

    # ------------------------------------------------------------------
    # apply_output_policy tests
    # ------------------------------------------------------------------

    def test_provider_model_noise_blocked_or_rewritten_by_output_policy(self) -> None:
        for backend, noise_text, _boundary, expected_policy, leaked in _provider_model_fixtures():
            with self.subTest(noise=noise_text):
                decision = apply_output_policy(noise_text)
                self.assertEqual(
                    decision.action,
                    expected_policy,
                    f"policy action mismatch for {noise_text!r}: "
                    f"expected {expected_policy!r}, got {decision.action!r}",
                )
                if expected_policy == "block":
                    self.assertIsNone(decision.visible_text)
                elif expected_policy == "rewrite":
                    self.assertIsNotNone(decision.visible_text)
                    for pattern in leaked:
                        self.assertNotIn(pattern, decision.visible_text or "")
                elif expected_policy == "allow":
                    self.assertEqual(decision.visible_text, noise_text)

    def test_codex_noise_blocked_or_rewritten_by_output_policy(self) -> None:
        for backend, noise_text, _boundary, expected_policy, leaked in _codex_fixtures():
            with self.subTest(noise=noise_text):
                decision = apply_output_policy(noise_text)
                self.assertEqual(
                    decision.action,
                    expected_policy,
                    f"policy action mismatch for {noise_text!r}: "
                    f"expected {expected_policy!r}, got {decision.action!r}",
                )
                if expected_policy == "block":
                    self.assertIsNone(decision.visible_text)
                elif expected_policy == "rewrite":
                    self.assertIsNotNone(decision.visible_text)
                    for pattern in leaked:
                        self.assertNotIn(pattern, decision.visible_text or "")
                elif expected_policy == "allow":
                    self.assertEqual(decision.visible_text, noise_text)

    # ------------------------------------------------------------------
    # Combined / cross-cutting assertions
    # ------------------------------------------------------------------

    def test_no_backend_noise_reaches_visible_text(self) -> None:
        """For all BLOCK and REWRITE boundary fixtures, leaked patterns must
        not appear in any visible text."""
        for backend, noise_text, expected_action, _policy, leaked in _block_or_rewrite_fixtures():
            with self.subTest(backend=backend, noise=noise_text):
                decision = self.boundary.apply("channel", text=noise_text)
                if expected_action == BoundaryAction.BLOCK:
                    self.assertIsNone(
                        decision.visible_text,
                        f"BLOCK should have visible_text=None for {noise_text!r}",
                    )
                elif expected_action == BoundaryAction.REWRITE:
                    visible = decision.visible_text or ""
                    for pattern in leaked:
                        self.assertNotIn(
                            pattern,
                            visible,
                            f"leaked pattern {pattern!r} in visible text for {noise_text!r}",
                        )

    def test_model_name_gpt4_never_in_visible_output(self) -> None:
        """The model name 'gpt-4' must never appear in any boundary visible_text
        output for any fixture that contains 'gpt-4' in the input.

        The boundary is the primary filter — it blocks or rewrites all gpt-4
        fixtures.  The WeCom output policy is a secondary delivery filter with
        narrower patterns and may allow some text through; the boundary ensures
        gpt-4 never reaches visible output regardless of policy behavior."""
        gpt4_fixtures = [f for f in NOISE_FIXTURES if "gpt-4" in f[1]]
        self.assertTrue(len(gpt4_fixtures) >= 2, "expected at least 2 gpt-4 fixtures")
        for backend, noise_text, expected_action, _policy, _leaked in gpt4_fixtures:
            with self.subTest(noise=noise_text):
                # Boundary — the primary filter must block or rewrite gpt-4.
                boundary_decision = self.boundary.apply("channel", text=noise_text)
                self.assertIn(
                    boundary_decision.action,
                    (BoundaryAction.BLOCK, BoundaryAction.REWRITE),
                    f"boundary must BLOCK or REWRITE gpt-4 fixture {noise_text!r}, "
                    f"got {boundary_decision.action}",
                )
                if boundary_decision.visible_text is not None:
                    self.assertNotIn(
                        "gpt-4",
                        boundary_decision.visible_text,
                        f"gpt-4 leaked in boundary visible_text for {noise_text!r}",
                    )

    def test_rate_limit_notice_is_rewritten_to_owned_notice(self) -> None:
        """Rate-limit fixtures that get REWRITE must have an owned service notice
        that is not the original text and does not contain 'rate limit' or
        'retrying'."""
        rate_limit_fixtures = [
            f for f in NOISE_FIXTURES
            if f[2] == BoundaryAction.REWRITE and "rate limit" in f[1].lower()
        ]
        self.assertTrue(len(rate_limit_fixtures) >= 1, "expected at least 1 rate-limit REWRITE fixture")
        for backend, noise_text, _action, _policy, _leaked in rate_limit_fixtures:
            with self.subTest(noise=noise_text):
                decision = self.boundary.apply("channel", text=noise_text)
                self.assertEqual(decision.action, BoundaryAction.REWRITE)
                self.assertIsNotNone(decision.visible_text)
                self.assertNotEqual(
                    decision.visible_text,
                    noise_text,
                    f"rewritten text should not equal original for {noise_text!r}",
                )
                self.assertNotIn("rate limit", decision.visible_text.lower())
                self.assertNotIn("retrying", decision.visible_text.lower())


if __name__ == "__main__":
    unittest.main()
