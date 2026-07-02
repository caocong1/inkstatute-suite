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


class InvokeWriterBranchTests(unittest.TestCase):
    def test_writer_with_append_many_method(self) -> None:
        class AppendManyWriter:
            def __init__(self) -> None:
                self.called = False

            def append_many(self, events: object) -> int:
                self.called = True
                return 3

        writer = AppendManyWriter()

        result = hook.record_contract_result(
            "agent:end",
            sample_context(),
            writer=writer,
            log_path="fixture://log.jsonl",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(result.status, "recorded")
        self.assertEqual(result.event_count, 3)
        self.assertTrue(writer.called)

    def test_writer_with_write_events_method(self) -> None:
        class WriteEventsWriter:
            def __init__(self) -> None:
                self.called = False

            def write_events(self, events: object, *, log_path: object, clock: object) -> int:
                self.called = True
                return 2

        writer = WriteEventsWriter()

        result = hook.record_contract_result(
            "agent:end",
            sample_context(),
            writer=writer,
            log_path="fixture://log.jsonl",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(result.status, "recorded")
        self.assertEqual(result.event_count, 2)
        self.assertTrue(writer.called)

    def test_writer_that_is_not_callable_and_lacks_methods_raises(self) -> None:
        writer = object()

        with self.assertRaises(TypeError):
            hook.record_contract_result(
                "agent:end",
                sample_context(),
                writer=writer,
                log_path="fixture://log.jsonl",
                clock=lambda: FIXED_NOW,
            )

    def test_callable_writer_returning_hook_result(self) -> None:
        expected = hook.HookRecordingResult(status="recorded", event_count=7)

        def writer(events, *, log_path, clock):
            return expected

        result = hook.record_contract_result(
            "agent:end",
            sample_context(),
            writer=writer,
            log_path="fixture://log.jsonl",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(result.event_count, 7)

    def test_callable_writer_returning_none(self) -> None:
        def writer(events, *, log_path, clock):
            return None

        result = hook.record_contract_result(
            "agent:end",
            sample_context(),
            writer=writer,
            log_path="fixture://log.jsonl",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(result.event_count, 0)

    def test_callable_writer_returning_non_len_non_int(self) -> None:
        def writer(events, *, log_path, clock):
            return True

        result = hook.record_contract_result(
            "agent:end",
            sample_context(),
            writer=writer,
            log_path="fixture://log.jsonl",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(result.event_count, 1)


class OutboundContextRestoreTests(unittest.TestCase):
    def test_restore_removes_keys_that_did_not_originally_exist(self) -> None:
        context = {"internal_state": {"data": True}}

        def mutating_recorder(event_type, ctx):
            for key in hook.OUTBOUND_CONTEXT_KEYS:
                ctx[key] = f"injected-{key}"
            return hook.HookRecordingResult(status="recorded", event_count=1)

        with patch.object(hook, "record_contract_result", side_effect=mutating_recorder):
            hook.handle("agent:end", context)

        for key in hook.OUTBOUND_CONTEXT_KEYS:
            self.assertNotIn(key, context)


if __name__ == "__main__":
    unittest.main()
