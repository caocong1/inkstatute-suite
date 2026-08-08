"""Golden fixture tests for citation verification — ports all 2 Rust test cases.

Replicates every test from ``verify.rs:220-250`` as Python golden fixtures.
Uses ``asyncio.run()`` for async verify tests.

Additional tests cover the law-library mock path (verified status) and
the ``audit()`` orchestration function.
"""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_agent_core.citations import (
    CitationAudit,
    CitationAuditItem,
    CitationKind,
    ExtractedCitation,
    LawEntry,
    ArticleLookup,
    audit,
    extract_citations,
    verify_items,
)


# ---------------------------------------------------------------------------
# Mock law library for verified-path tests
# ---------------------------------------------------------------------------

class MockLawLibrary:
    """Minimal mock law library implementing the LawLibrary protocol."""

    def __init__(
        self,
        articles: dict[tuple[str, str], ArticleLookup] | None = None,
        doc_numbers: dict[str, LawEntry] | None = None,
    ) -> None:
        self._articles = articles or {}
        self._doc_numbers = doc_numbers or {}

    async def lookup_article(self, law_name: str, article: str) -> ArticleLookup | None:
        return self._articles.get((law_name, article))

    async def find_by_doc_number(self, doc_number: str) -> LawEntry | None:
        return self._doc_numbers.get(doc_number)


# ---------------------------------------------------------------------------
# Rust golden fixture tests (verify.rs:220-250)
# ---------------------------------------------------------------------------

class TestCaseNumbersVerifyAgainstRetrievalsOnly(unittest.TestCase):
    """Port of verify.rs:220-233 — case_numbers_verify_against_retrievals_only."""

    def test_case_numbers_verify_against_retrievals_only(self) -> None:
        """Case in retrieval → 'retrieved' with tier; not in retrieval → 'unverified'."""
        text = "参见（2024）渝01民初1234号判决与（2021）粤03民终99号。"
        retrievals = [(
            "mcp__wenshu__search_cases",
            "找到案例：（2024）渝01民初1234号 …\n来源层级: L2-入库\n链接: https://rmfyalk.court.gov.cn/x",
        )]
        items = asyncio.run(verify_items(extract_citations(text), retrievals))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].status, "retrieved")
        self.assertEqual(items[0].tier, "L2-入库")
        self.assertEqual(items[1].status, "unverified")
        self.assertIn("待律师复核", items[1].note or "")


class TestLawArticlesWithoutLibraryFallBackToRetrievals(unittest.TestCase):
    """Port of verify.rs:235-249 — law_articles_without_library_fall_back_to_retrievals."""

    def test_law_articles_without_library_fall_back_to_retrievals(self) -> None:
        """No library → retrieval path; no retrievals → 'unverified'."""
        text = "依据《测试专用法》第三条。"
        retrievals = [(
            "mcp__law-database__search_laws",
            "《测试专用法》第三条：……\n来源层级: L1-法规",
        )]
        items = asyncio.run(verify_items(extract_citations(text), retrievals))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "retrieved")

        items_none = asyncio.run(verify_items(extract_citations(text), []))
        self.assertEqual(items_none[0].status, "unverified")


# ---------------------------------------------------------------------------
# Library mock tests — verified path
# ---------------------------------------------------------------------------

class TestVerifyWithLibraryMock(unittest.TestCase):
    """Tests for the verified path when a law library is available."""

    def test_law_article_verified_via_library(self) -> None:
        """Library lookup finds article → status='verified', tier='L1-法规（本地库）'."""
        text = "依据《民法典》第五百八十五条。"
        library = MockLawLibrary(
            articles={
                ("民法典", "第五百八十五条"): ArticleLookup(
                    kind="found",
                    entry=LawEntry(name="民法典", status="现行有效", source_url="https://example.com/minfa"),
                    heading="第五百八十五条",
                    text="当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金…",
                ),
            }
        )
        items = asyncio.run(verify_items(extract_citations(text), [], law_library=library))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "verified")
        self.assertEqual(items[0].tier, "L1-法规（本地库）")
        self.assertEqual(items[0].url, "https://example.com/minfa")
        self.assertIsNotNone(items[0].excerpt)

    def test_law_article_verified_with_non_current_status_note(self) -> None:
        """Library entry with non-现行有效 status → note contains warning."""
        text = "依据《旧法》第一条。"
        library = MockLawLibrary(
            articles={
                ("旧法", "第一条"): ArticleLookup(
                    kind="found",
                    entry=LawEntry(name="旧法", status="已废止", source_url=None),
                    heading="第一条",
                    text="内容…",
                ),
            }
        )
        items = asyncio.run(verify_items(extract_citations(text), [], law_library=library))
        self.assertEqual(items[0].status, "verified")
        self.assertIn("已废止", items[0].note or "")

    def test_law_found_article_missing(self) -> None:
        """Library finds law but not the article → 'unverified' with count note."""
        text = "依据《民法典》第九百九十九条。"
        library = MockLawLibrary(
            articles={
                ("民法典", "第九百九十九条"): ArticleLookup(
                    kind="law_found_article_missing",
                    entry=LawEntry(name="民法典", article_count=1260),
                    article_count=1260,
                ),
            }
        )
        items = asyncio.run(verify_items(extract_citations(text), [], law_library=library))
        self.assertEqual(items[0].status, "unverified")
        self.assertIn("1260", items[0].note or "")
        self.assertIn("未找到", items[0].note or "")

    def test_interpretation_verified_via_doc_number(self) -> None:
        """Interpretation found by doc number → 'verified'."""
        text = "依据法释〔2020〕28号。"
        library = MockLawLibrary(
            doc_numbers={
                "法释〔2020〕28号": LawEntry(name="担保制度解释", status="现行有效", source_url="https://example.com"),
            }
        )
        items = asyncio.run(verify_items(extract_citations(text), [], law_library=library))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "verified")
        self.assertEqual(items[0].tier, "L1-法规（本地库）")

    def test_interpretation_verified_via_name_fallback(self) -> None:
        """Interpretation not found by doc number but found by name → 'verified'."""
        text = "《担保制度解释》法释〔2020〕28号"
        library = MockLawLibrary(
            articles={
                ("担保制度解释", "第一条"): ArticleLookup(
                    kind="found",
                    entry=LawEntry(name="担保制度解释", status="现行有效"),
                    heading="第一条",
                    text="内容…",
                ),
            }
        )
        items = asyncio.run(verify_items(extract_citations(text), [], law_library=library))
        # Should find the interpretation by name
        interp_items = [i for i in items if i.kind == CitationKind.INTERPRETATION]
        self.assertTrue(len(interp_items) >= 1)
        self.assertEqual(interp_items[0].status, "verified")
        self.assertIn("按名称匹配", interp_items[0].note or "")

    def test_interpretation_retrieved_fallback(self) -> None:
        """Interpretation not in library but in retrievals → 'retrieved'."""
        text = "依据法释〔2020〕28号。"
        retrievals = [(
            "mcp__law-database__search_laws",
            "法释〔2020〕28号 担保制度解释\n来源层级: L1-法规",
        )]
        items = asyncio.run(verify_items(extract_citations(text), retrievals))
        self.assertEqual(items[0].status, "retrieved")
        self.assertEqual(items[0].tier, "L1-法规")

    def test_case_retrieved_halfwidth_variant(self) -> None:
        """Case number in retrieval with halfwidth brackets → 'retrieved'."""
        text = "参见（2024）渝01民初1234号。"
        retrievals = [(
            "mcp__wenshu__search_cases",
            "找到案例：(2024)渝01民初1234号 …\n来源层级: L2-入库",
        )]
        items = asyncio.run(verify_items(extract_citations(text), retrievals))
        self.assertEqual(items[0].status, "retrieved")


# ---------------------------------------------------------------------------
# audit() orchestration tests
# ---------------------------------------------------------------------------

class TestAudit(unittest.TestCase):
    """Tests for the audit() orchestration function."""

    def test_audit_returns_citation_audit_with_counts(self) -> None:
        """audit() returns CitationAudit with correct counts."""
        text = "参见（2024）渝01民初1234号判决与（2021）粤03民终99号。"
        retrievals = [(
            "mcp__wenshu__search_cases",
            "找到案例：（2024）渝01民初1234号 …\n来源层级: L2-入库",
        )]
        result = asyncio.run(audit(text, retrievals))
        self.assertIsInstance(result, CitationAudit)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.verified, 0)
        self.assertEqual(result.retrieved, 1)
        self.assertEqual(result.unverified, 1)
        self.assertEqual(len(result.items), 2)

    def test_audit_no_citations(self) -> None:
        """audit() on text with no citations → empty audit."""
        result = asyncio.run(audit("本案应当尽快起诉，没有引用任何法条。", []))
        self.assertEqual(result.total, 0)
        self.assertEqual(result.verified, 0)
        self.assertEqual(result.retrieved, 0)
        self.assertEqual(result.unverified, 0)
        self.assertEqual(result.items, [])

    def test_audit_with_library(self) -> None:
        """audit() with a law library → verified count increases."""
        text = "依据《民法典》第五百八十五条。"
        library = MockLawLibrary(
            articles={
                ("民法典", "第五百八十五条"): ArticleLookup(
                    kind="found",
                    entry=LawEntry(name="民法典", status="现行有效"),
                    heading="第五百八十五条",
                    text="违约金条款…",
                ),
            }
        )
        result = asyncio.run(audit(text, [], law_library=library))
        self.assertEqual(result.total, 1)
        self.assertEqual(result.verified, 1)
        self.assertEqual(result.retrieved, 0)
        self.assertEqual(result.unverified, 0)


if __name__ == "__main__":
    unittest.main()
