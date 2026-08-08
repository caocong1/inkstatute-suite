"""Golden fixture tests for citation extraction — ports all 12 Rust test cases.

Replicates every test from ``extract.rs:164-284`` as Python golden fixtures.
The test inputs and expected outputs are byte-identical to the Rust source.

The ``kinds()`` helper maps ``extract_citations(text)`` to
``list[tuple[CitationKind, str, str]]`` for easy assertion, matching the
Rust test helper at ``extract.rs:168-173``.
"""

from __future__ import annotations

import unittest

from inkstatute_agent_core.citations.extract import (
    CitationKind,
    ExtractedCitation,
    extract_citations,
)


def kinds(text: str) -> list[tuple[CitationKind, str, str]]:
    """Map extract_citations to list of (kind, source, reference) tuples.

    Matches the Rust test helper at extract.rs:168-173.
    """
    return [(c.kind, c.source, c.reference) for c in extract_citations(text)]


class TestExtractLawArticles(unittest.TestCase):
    """Tests for law-article extraction (法条)."""

    def test_extracts_law_article_chinese_and_arabic(self) -> None:
        """《中华人民共和国民法典》第五百八十五条 + 《公司法》第20条 → 2 Law citations."""
        got = kinds("依据《中华人民共和国民法典》第五百八十五条，以及《公司法》第20条的规定。")
        self.assertEqual(got, [
            (CitationKind.LAW, "中华人民共和国民法典", "第五百八十五条"),
            (CitationKind.LAW, "公司法", "第20条"),
        ])

    def test_expands_article_enumerations(self) -> None:
        """《民法典》第六百八十六条、第六百八十八条 → 2 citations."""
        got = kinds("《民法典》第六百八十六条、第六百八十八条均有规定。")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0][2], "第六百八十六条")
        self.assertEqual(got[1][2], "第六百八十八条")

    def test_extracts_zhi_yi_suffix(self) -> None:
        """《刑法》第二百八十七条之一 → reference="第二百八十七条之一"."""
        got = kinds("《刑法》第二百八十七条之一规定。")
        self.assertEqual(got[0][2], "第二百八十七条之一")

    def test_handles_inner_book_titles_in_law_name(self) -> None:
        """《...〈民法典〉...解释》 uses fullwidth inner brackets — outer name must match."""
        got = kinds("《最高人民法院关于适用〈中华人民共和国民法典〉有关担保制度的解释》第二十一条")
        self.assertTrue(
            any(
                k == CitationKind.LAW and "担保制度的解释" in s and r == "第二十一条"
                for k, s, r in got
            )
        )


class TestExtractInterpretations(unittest.TestCase):
    """Tests for interpretation extraction (司法解释)."""

    def test_extracts_interpretation_with_adjacent_name(self) -> None:
        """Interpretation with ref="法释〔2020〕28号"."""
        got = kinds(
            "《最高人民法院关于适用〈中华人民共和国民法典〉有关担保制度的解释》"
            "（法释〔2020〕28号）第二十五条"
        )
        self.assertTrue(
            any(
                k == CitationKind.INTERPRETATION and r == "法释〔2020〕28号"
                for k, _, r in got
            )
        )

    def test_normalizes_interpretation_bracket_variants(self) -> None:
        """法释[2016]24号 → normalized to 法释〔2016〕24号."""
        got = kinds("依据法释[2016]24号第一条。")
        self.assertTrue(
            any(
                k == CitationKind.INTERPRETATION and r == "法释〔2016〕24号"
                for k, _, r in got
            )
        )

    def test_extracts_state_council_decree(self) -> None:
        """Interpretation with source and reference="国务院令第683号"."""
        got = kinds("《融资担保公司监督管理条例》（国务院令第683号）规定。")
        self.assertTrue(
            any(
                k == CitationKind.INTERPRETATION
                and s == "融资担保公司监督管理条例"
                and r == "国务院令第683号"
                for k, s, r in got
            )
        )


class TestExtractCaseNumbers(unittest.TestCase):
    """Tests for case-number extraction (案号)."""

    def test_extracts_case_numbers_fullwidth_and_halfwidth(self) -> None:
        """2 Case citations, both normalized to fullwidth brackets."""
        got = kinds("参见（2024）渝01民初1234号判决，另见(2023)京民终567号。")
        self.assertEqual(got, [
            (CitationKind.CASE, "", "（2024）渝01民初1234号"),
            (CitationKind.CASE, "", "（2023）京民终567号"),
        ])

    def test_extracts_specialized_case_types(self) -> None:
        """知民终 and 执异 case types."""
        got = kinds("（2022）最高法知民终82号、（2021）粤03执异77号。")
        self.assertEqual(len(got), 2)

    def test_extracts_db_case_ids(self) -> None:
        """2024-10-2-358-001 → 1 Case citation."""
        got = kinds("入库案例 2024-10-2-358-001 认定担保公司不具备开立独立保函主体资格。")
        self.assertEqual(got, [
            (CitationKind.CASE, "", "2024-10-2-358-001"),
        ])


class TestExtractDedupAndEdgeCases(unittest.TestCase):
    """Tests for deduplication and edge cases."""

    def test_dedupes_repeated_citations(self) -> None:
        """Same citation twice → 1 item."""
        got = kinds("《民法典》第五百八十五条……再依《民法典》第五百八十五条。")
        self.assertEqual(len(got), 1)

    def test_ignores_plain_text_without_citations(self) -> None:
        """No 《》 prefix → empty."""
        self.assertTrue(kinds("本案应当尽快起诉，没有引用任何法条。") == [])
        self.assertTrue(kinds("第十条没有书名号前缀，不算法条引用。") == [])


if __name__ == "__main__":
    unittest.main()
