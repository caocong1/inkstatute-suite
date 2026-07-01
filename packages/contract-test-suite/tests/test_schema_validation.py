from __future__ import annotations

import copy
import unittest

from contract_test_suite.schema_validation import (
    ContractValidationError,
    load_contract_fixtures,
    load_schemas,
    validate_event,
    validate_event_bundle,
)


EVENT_KEYS = (
    "agent_turn",
    "route_decision",
    "execution_trace",
    "agent_result",
    "feedback_event",
)


class SchemaValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = load_schemas()
        cls.fixtures = load_contract_fixtures()

    def test_valid_platform_contract_fixtures_pass_for_all_events(self) -> None:
        self.assertEqual(
            {fixture["fixture_id"] for fixture in self.fixtures},
            {
                "legal-wecom-contract-review-001",
                "non-legal-engineering-task-001",
                "non-legal-finance-tax-task-001",
                "non-legal-education-task-001",
                "phase3-route-error-contract-001",
                "phase3-long-task-failure-contract-001",
                "phase3-repeated-feedback-clicks-contract-001",
                "phase3-non-legal-wild-task-contract-001",
                "phase5-wecom-feedback-loop-001",
                "phase55-wecom-service-agent-loop-001",
                "phase6-read-feedback-apis-001",
                "platform-foundation-non-legal-run-001",
                "phase10-runruntime-fake-backend-001",
                "phase15-session-interrupt-runtime-001",
                "phase16-short-term-context-assembler-001",
            },
        )

        for fixture in self.fixtures:
            with self.subTest(fixture=fixture["fixture_id"]):
                validate_event_bundle(fixture, self.schemas)

    def test_required_field_errors_name_fixture_event_and_field(self) -> None:
        fixture = copy.deepcopy(self.fixtures[0])

        for event_key in EVENT_KEYS:
            required_field = self.schemas[self._schema_name(event_key)]["required"][0]
            mutated = copy.deepcopy(fixture)
            del mutated["events"][event_key][required_field]

            with self.subTest(event=event_key, field=required_field):
                with self.assertRaisesRegex(
                    ContractValidationError,
                    rf"{fixture['fixture_id']}.*{event_key}.*{required_field}",
                ):
                    validate_event_bundle(mutated, self.schemas)

    def test_enum_errors_cover_platform_event_domains(self) -> None:
        cases = (
            ("agent_turn", ("channel",), "email"),
            ("route_decision", ("mode",), "manual"),
            ("agent_result", ("status",), "done"),
            ("agent_result", ("reply_type",), "html"),
            ("feedback_event", ("source",), "sms"),
            ("feedback_event", ("event_type",), "praise"),
            ("feedback_event", ("action",), "maybe"),
            ("feedback_event", ("status",), "closed"),
        )

        for event_key, path, bad_value in cases:
            event = copy.deepcopy(self.fixtures[0]["events"][event_key])
            self._set_path(event, path, bad_value)

            with self.subTest(event=event_key, path=".".join(path)):
                with self.assertRaisesRegex(
                    ContractValidationError,
                    rf"{event_key}.*{'.'.join(path)}.*enum",
                ):
                    validate_event(
                        event_key,
                        event,
                        self.schemas,
                        fixture_id=self.fixtures[0]["fixture_id"],
                    )

    def test_type_and_range_errors_include_precise_paths(self) -> None:
        cases = (
            ("execution_trace", ("seq",), -1, "minimum"),
            ("execution_trace", ("matched_registered_skill",), "yes", "boolean"),
        )

        for event_key, path, bad_value, expected in cases:
            event = copy.deepcopy(self.fixtures[0]["events"][event_key])
            self._set_path(event, path, bad_value)

            with self.subTest(path=".".join(path)):
                with self.assertRaisesRegex(
                    ContractValidationError,
                    rf"{event_key}.*{'.'.join(path)}.*{expected}",
                ):
                    validate_event(
                        event_key,
                        event,
                        self.schemas,
                        fixture_id=self.fixtures[0]["fixture_id"],
                    )

    def test_invalid_date_time_format_errors_cover_contract_timestamps(self) -> None:
        cases = (
            ("agent_turn", ("received_at",)),
            ("route_decision", ("created_at",)),
            ("execution_trace", ("occurred_at",)),
            ("feedback_event", ("created_at",)),
        )
        invalid_values = (
            "not-a-date",
            "2026-06-27",
            "2026-06-27T13:00:00",
            "2026-06-27 13:00:00Z",
        )

        for event_key, path in cases:
            for invalid_value in invalid_values:
                event = copy.deepcopy(self.fixtures[0]["events"][event_key])
                self._set_path(event, path, invalid_value)

                with self.subTest(event=event_key, path=".".join(path), value=invalid_value):
                    with self.assertRaisesRegex(
                        ContractValidationError,
                        rf"{event_key}.*{'.'.join(path)}.*date-time",
                    ):
                        validate_event(
                            event_key,
                            event,
                            self.schemas,
                            fixture_id=self.fixtures[0]["fixture_id"],
                        )

    def test_unknown_top_level_event_fields_fail(self) -> None:
        event = copy.deepcopy(self.fixtures[0]["events"]["agent_turn"])
        event["unexpected_top_level"] = "not allowed"

        with self.assertRaisesRegex(
            ContractValidationError,
            r"agent_turn.*unexpected_top_level.*additionalProperties",
        ):
            validate_event(
                "agent_turn",
                event,
                self.schemas,
                fixture_id=self.fixtures[0]["fixture_id"],
            )

    def test_unknown_event_keys_under_bundle_events_fail(self) -> None:
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["events"]["raw_legal_payload"] = {
            "raw_payload": "Synthetic confidential legal text must stay out of contract events."
        }

        with self.assertRaisesRegex(
            ContractValidationError,
            r"raw_legal_payload.*unknown event key",
        ):
            validate_event_bundle(fixture, self.schemas)

    def test_forbidden_top_level_fields_fail_even_if_schema_allows_them(self) -> None:
        schemas = copy.deepcopy(self.schemas)
        schemas["agent_turn"]["properties"]["client_name"] = {"type": "string"}
        event = copy.deepcopy(self.fixtures[0]["events"]["agent_turn"])
        event["client_name"] = "Synthetic Client"

        with self.assertRaisesRegex(
            ContractValidationError,
            r"agent_turn.*client_name.*forbidden top-level",
        ):
            validate_event(
                "agent_turn",
                event,
                schemas,
                fixture_id=self.fixtures[0]["fixture_id"],
            )

    def test_extension_containers_accept_legal_and_profile_specific_data(self) -> None:
        event = copy.deepcopy(self.fixtures[0]["events"]["agent_turn"])
        event["industry_context"]["legal_profile"] = {
            "case_type": "contract_review",
            "jurisdiction": "synthetic-cn",
        }
        event["metadata"]["lawfirm_profile"] = {
            "client_name_ref": "fixture://refs/client-001",
            "raw_payload_ref": "fixture://raw/lawfirm-turn-001",
        }

        validate_event(
            "agent_turn",
            event,
            self.schemas,
            fixture_id=self.fixtures[0]["fixture_id"],
        )

    @staticmethod
    def _schema_name(event_key: str) -> str:
        return event_key

    @staticmethod
    def _set_path(value: dict, path: tuple[str, ...], replacement: object) -> None:
        target = value
        for segment in path[:-1]:
            target = target[segment]
        target[path[-1]] = replacement


if __name__ == "__main__":
    unittest.main()
