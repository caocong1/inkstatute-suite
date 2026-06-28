from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hermes_contract_layer import hook


BASE = Path(__file__).resolve().parents[1]
HOOK_DIR = BASE / "hooks" / "response_filter_contract_result_recorder"
FIXED_NOW = "2026-06-28T02:10:00Z"


def sample_context() -> dict[str, object]:
    return {
        "response": "filtered answer preview",
        "message_id": "msg-123",
        "platform": "wecom",
        "user_id": "user-1",
        "chat_id": "chat-1",
        "session_id": "session-1",
        "message": "contract review request",
        "internal_state": {"can_change": True},
    }


class HookArtifactTests(unittest.TestCase):
    def test_hook_directory_sorts_after_response_filter(self) -> None:
        self.assertTrue(HOOK_DIR.exists())
        self.assertGreater(HOOK_DIR.name, "response_filter")
        self.assertFalse((BASE / "hooks" / "contract_result_recorder").exists())

    def test_manifest_registers_agent_end_with_contract_recorder_name(self) -> None:
        manifest = (HOOK_DIR / "HOOK.yaml").read_text()
        self.assertIn("name: contract_result_recorder", manifest)
        self.assertIn("agent:end", manifest)

    def test_handler_artifact_delegates_to_package_entrypoint(self) -> None:
        spec = importlib.util.spec_from_file_location("phase4_handler", HOOK_DIR / "handler.py")
        self.assertIsNotNone(spec)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        fake_handle = Mock(return_value=hook.HookRecordingResult(status="recorded", event_count=1))
        with patch.object(module, "_handle", fake_handle):
            context = sample_context()
            result = module.handle("agent:end", context)

        fake_handle.assert_called_once_with("agent:end", context)
        self.assertEqual(result.status, "recorded")


class HookBoundaryTests(unittest.TestCase):
    def test_non_agent_end_events_are_ignored(self) -> None:
        context = sample_context()
        before = copy.deepcopy(context)

        result = hook.handle("agent:start", context)

        self.assertEqual(result.status, "ignored")
        self.assertEqual(context, before)

    def test_agent_end_delegates_to_recording_entrypoint(self) -> None:
        context = sample_context()
        expected = hook.HookRecordingResult(status="recorded", event_count=1)

        with patch.object(hook, "record_contract_result", return_value=expected) as recorder:
            result = hook.handle("agent:end", context)

        recorder.assert_called_once_with("agent:end", context)
        self.assertEqual(result, expected)

    def test_outbound_context_keys_are_restored_after_recorder_runs(self) -> None:
        context = sample_context()
        outbound_before = {key: context[key] for key in hook.OUTBOUND_CONTEXT_KEYS}

        def mutating_recorder(event_type, context):
            for key in hook.OUTBOUND_CONTEXT_KEYS:
                context[key] = f"mutated-{key}"
            context["internal_state"] = {"can_change": "recorder-private"}
            return hook.HookRecordingResult(status="recorded", event_count=1)

        with patch.object(hook, "record_contract_result", side_effect=mutating_recorder):
            result = hook.handle("agent:end", context)

        self.assertEqual(result.status, "recorded")
        self.assertEqual({key: context[key] for key in hook.OUTBOUND_CONTEXT_KEYS}, outbound_before)
        self.assertEqual(context["internal_state"], {"can_change": "recorder-private"})

    def test_recorder_exceptions_do_not_propagate_to_hermes(self) -> None:
        context = sample_context()
        before = {key: context[key] for key in hook.OUTBOUND_CONTEXT_KEYS}

        with patch.object(hook, "record_contract_result", side_effect=RuntimeError("boom")):
            result = hook.handle("agent:end", context)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error, "recorder_failed")
        self.assertEqual({key: context[key] for key in hook.OUTBOUND_CONTEXT_KEYS}, before)

    def test_missing_log_path_configuration_skips_without_context_mutation(self) -> None:
        context = sample_context()
        before = copy.deepcopy(context)

        with patch.dict(os.environ, {hook.CONTRACT_LOG_PATH_ENV: ""}, clear=False):
            os.environ.pop(hook.CONTRACT_LOG_PATH_ENV, None)
            result = hook.handle("agent:end", context)

        self.assertEqual(result.status, "skipped")
        self.assertEqual(context, before)

    def test_explicit_writer_can_record_without_mutating_source_context(self) -> None:
        context = sample_context()
        calls = []

        def writer(events, *, log_path, clock):
            calls.append((events, log_path, clock))
            events["agent_result"]["content"] = "writer-local mutation"
            return list(events)

        result = hook.record_contract_result(
            "agent:end",
            context,
            writer=writer,
            log_path="fixture://contract-log.jsonl",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(result.status, "recorded")
        self.assertEqual(result.event_count, 4)
        self.assertEqual(tuple(calls[0][0]), ("agent_turn", "route_decision", "execution_trace", "agent_result"))
        self.assertEqual(calls[0][1], "fixture://contract-log.jsonl")
        self.assertEqual(context["response"], "filtered answer preview")

    def test_configured_hook_writes_four_jsonl_records_without_outbound_mutation(self) -> None:
        context = sample_context()
        before = {key: context[key] for key in hook.OUTBOUND_CONTEXT_KEYS}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract-log.jsonl"
            result = hook.record_contract_result(
                "agent:end",
                context,
                log_path=path,
                clock=lambda: FIXED_NOW,
            )

            lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.status, "recorded")
        self.assertEqual(result.event_count, 4)
        self.assertEqual([line["event_key"] for line in lines], ["agent_turn", "route_decision", "execution_trace", "agent_result"])
        self.assertEqual({key: context[key] for key in hook.OUTBOUND_CONTEXT_KEYS}, before)


if __name__ == "__main__":
    unittest.main()
