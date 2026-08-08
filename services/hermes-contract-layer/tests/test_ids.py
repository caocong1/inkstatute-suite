from __future__ import annotations

import unittest

from hermes_contract_layer.ids import stable_hash_id


class StableHashIdTests(unittest.TestCase):
    def test_deterministic_for_same_inputs(self) -> None:
        a = stable_hash_id("evt", "part1", "part2")
        b = stable_hash_id("evt", "part1", "part2")

        self.assertEqual(a, b)
        self.assertTrue(a.startswith("evt-"))

    def test_different_inputs_produce_different_ids(self) -> None:
        a = stable_hash_id("evt", "alpha")
        b = stable_hash_id("evt", "beta")

        self.assertNotEqual(a, b)

    def test_custom_length_controls_digest_size(self) -> None:
        short = stable_hash_id("x", "data", length=8)

        self.assertTrue(short.startswith("x-"))
        self.assertEqual(len(short), 2 + 8)

    def test_dict_parts_are_sorted_by_key(self) -> None:
        a = stable_hash_id("d", {"z": 1, "a": 2})
        b = stable_hash_id("d", {"a": 2, "z": 1})

        self.assertEqual(a, b)

    def test_nested_dict_keys_are_sorted_recursively(self) -> None:
        a = stable_hash_id("d", {"outer": {"z": 1, "a": 2}})
        b = stable_hash_id("d", {"outer": {"a": 2, "z": 1}})

        self.assertEqual(a, b)

    def test_list_and_tuple_parts_produce_same_id(self) -> None:
        a = stable_hash_id("l", [1, "two", 3])
        b = stable_hash_id("l", (1, "two", 3))

        self.assertEqual(a, b)

    def test_non_json_primitive_falls_back_to_str(self) -> None:
        class Custom:
            def __str__(self) -> str:
                return "custom-repr"

        result = stable_hash_id("c", Custom())

        self.assertTrue(result.startswith("c-"))
        self.assertEqual(len(result), 2 + 16)

    def test_mixed_nested_structures(self) -> None:
        part = {"items": [1, {"nested_key": "val"}], "flag": True}
        result = stable_hash_id("m", part)

        self.assertTrue(result.startswith("m-"))
        self.assertEqual(stable_hash_id("m", part), result)


if __name__ == "__main__":
    unittest.main()
