"""Fixture SKILL.md bodies for body injector tests.

Provides SKILL.md samples of varying token lengths (~2K, ~5K, ~10K, ~20K)
with realistic section structure including frontmatter, description, gate
sections, core instructions, examples, and appendices.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Frontmatter template
# ---------------------------------------------------------------------------

_FRONTMATTER = """\
---
name: test-skill
description: >
  A test skill for body injector testing. This skill demonstrates the
  section-priority deterministic trim algorithm.
argument-hint: "[test input]"
---
"""


# ---------------------------------------------------------------------------
# Section templates
# ---------------------------------------------------------------------------

_DESC_SECTION = """\
# Test Skill

> This is the first section (protected). It contains the skill description
> and overview that must never be trimmed.
"""


_GATE_SECTION = """\
## research-gate

Before providing any legal conclusion, you MUST search for relevant statutes
and case law. Do not rely on model knowledge alone for specific legal citations.
This gate ensures that all conclusions are grounded in verified legal sources.

1. Identify the legal question
2. Search for applicable statutes
3. Search for relevant case law
4. Verify the currency of all citations
5. Only then proceed to analysis
"""


_ASK_USER_SECTION = """\
## ask-user-enforcement

When key facts are missing, you MUST ask the user before proceeding with
drafting. Do not assume facts. Use the elicitation protocol to collect
missing information through structured questions.

- If the contract type is unclear, ask
- If the parties are unknown, ask
- If the jurisdiction is ambiguous, ask
- If the risk position is unspecified, ask
"""


_CORE_SECTION = """\
## Core Instructions

This section contains the main processing logic for the skill. It is
classified as medium priority for trimming purposes.

### Step 1: Input Analysis

Analyze the input document or question. Identify the key legal issues
and categorize them by type (contract, litigation, compliance, etc.).

### Step 2: Issue Research

For each identified issue, research the applicable legal framework.
Use the research-gate to ensure all citations are verified.

### Step 3: Analysis

Apply the legal framework to the specific facts. Consider:
- Statutory requirements
- Judicial interpretations
- Regulatory guidance
- Practical implications

### Step 4: Output Generation

Generate the output in the appropriate format. Include:
- Legal analysis
- Risk assessment
- Recommendations
- Citations with source labels
"""


_ORCH_SECTION = """\
## Orchestration Table

| Order | Sub-skill | Responsibility | Trigger |
|-------|-----------|---------------|---------|
| 1 | risk-identification | Identify clause-level risks | /test:risk-identification |
| 2 | legal-basis | Find applicable law | /test:legal-basis |
| 3 | clause-revision | Generate revision language | /test:clause-revision |
| 4 | output-formatting | Format final output | /test:output-formatting |
"""


_EXAMPLE_SECTION = """\
## Examples

### Example 1: Simple Contract Review

Input: A standard service agreement with a liability cap clause.

Output: The skill identifies the liability cap as a key risk, researches
applicable law on liability limitations, and generates revised language
that aligns with the team's review position.

### Example 2: Complex Litigation Summary

Input: A set of court documents including complaint, answer, and motions.

Output: The skill analyzes the procedural posture, identifies key legal
issues, researches relevant case law, and produces a summary suitable
for partner review.

### Example 3: Compliance Check

Input: A company privacy policy for GDPR/PIPL compliance review.

Output: The skill identifies gaps between the policy and regulatory
requirements, generates specific revision recommendations, and produces
a compliance gap analysis report.
"""


_APPENDIX_SECTION = """\
## Appendix A: Reference Tables

| Statute | Article | Topic |
|---------|---------|-------|
| Civil Code | Art. 506 | Contract formation |
| Civil Code | Art. 577 | Breach of contract |
| Contract Law Interpretation | Art. 12 | Contract interpretation |

## Appendix B: Glossary

- **Force Majeure**: Unforeseeable circumstances that prevent fulfillment
  of contractual obligations.
- **Indemnity**: A contractual obligation to compensate for loss or damage.
- **Severability**: The ability to remove an unenforceable clause without
  invalidating the entire contract.
"""


_REFERENCE_SECTION = """\
## References

- [1] Civil Code of the People's Republic of China (2021)
- [2] Supreme People's Court Contract Law Interpretations
- [3] Guiding Cases on Commercial Disputes
- [4] Regulatory Guidance on Data Protection
- [5] Industry Standards for Contract Review
"""


# ---------------------------------------------------------------------------
# Padding generator for reaching target token counts
# ---------------------------------------------------------------------------

_PADDING_SECTION_TEMPLATE = """\
## Additional Context {n}

This is additional context section number {n}. It provides supplementary
information that supports the core analysis. This section is classified as
low priority for trimming because it contains supporting detail rather than
primary instructions. The content here elaborates on edge cases and special
considerations that may arise during skill execution. The detailed
explanations help ensure that the skill can handle a wide range of inputs
without missing important nuances.

When the primary analysis is complete, this section provides additional
guidance on handling unusual situations. It covers scenarios that are
less common but still important for comprehensive coverage. The detailed
explanations help ensure that the skill can handle a wide range of inputs
without missing important nuances. Additional paragraphs are included here
to increase the token count to realistic skill body sizes (2K-20K tokens).

The following considerations apply to this section:
- Edge case handling for unusual input patterns
- Fallback strategies when primary analysis is inconclusive
- Cross-reference to related skills and shared resources
- Quality assurance checks specific to this context
- Integration notes for downstream consumers of the output

These additional details ensure that the skill body reaches a realistic
token count that exercises the budget trimming algorithm effectively.
The content is intentionally verbose to simulate real-world SKILL.md
files which often contain extensive documentation, examples, and references
that can be trimmed when the context budget is tight.

Further elaboration on the topic includes discussion of regulatory
frameworks, judicial interpretations, and practical implications for
legal practitioners. The analysis considers both substantive and
procedural aspects of the relevant legal domain. Special attention is
given to jurisdiction-specific variations and recent developments in
the law that may affect the analysis.

Additional paragraphs continue with more detailed discussion of the
relevant legal standards and their application to common scenarios
encountered in practice. The goal is to provide comprehensive coverage
of the topic while remaining accessible to practitioners who may not
be specialists in this particular area of law.
"""


def _generate_padding_sections(count: int) -> str:
    """Generate *count* padding sections for reaching target token counts."""
    return "\n".join(_PADDING_SECTION_TEMPLATE.format(n=i) for i in range(1, count + 1))


# ---------------------------------------------------------------------------
# Public fixture builders
# ---------------------------------------------------------------------------


def build_small_skill() -> str:
    """Build a ~2K token SKILL.md body.

    Contains: frontmatter, description, gate section, core instructions,
    one example, one appendix.
    """
    parts = [
        _FRONTMATTER,
        _DESC_SECTION,
        _GATE_SECTION,
        _CORE_SECTION,
        _EXAMPLE_SECTION,
        _APPENDIX_SECTION,
    ]
    return "\n".join(parts)


def build_medium_skill() -> str:
    """Build a ~5K token SKILL.md body.

    Contains: frontmatter, description, gate sections, core instructions,
    orchestration table, examples, appendices, and padding sections.
    """
    parts = [
        _FRONTMATTER,
        _DESC_SECTION,
        _GATE_SECTION,
        _ASK_USER_SECTION,
        _CORE_SECTION,
        _ORCH_SECTION,
        _EXAMPLE_SECTION,
        _APPENDIX_SECTION,
        _REFERENCE_SECTION,
        _generate_padding_sections(8),
    ]
    return "\n".join(parts)


def build_large_skill() -> str:
    """Build a ~10K token SKILL.md body.

    Contains all sections plus more padding.
    """
    parts = [
        _FRONTMATTER,
        _DESC_SECTION,
        _GATE_SECTION,
        _ASK_USER_SECTION,
        _CORE_SECTION,
        _ORCH_SECTION,
        _EXAMPLE_SECTION,
        _APPENDIX_SECTION,
        _REFERENCE_SECTION,
        _generate_padding_sections(18),
    ]
    return "\n".join(parts)


def build_xlarge_skill() -> str:
    """Build a ~20K token SKILL.md body.

    Contains all sections plus extensive padding.
    """
    parts = [
        _FRONTMATTER,
        _DESC_SECTION,
        _GATE_SECTION,
        _ASK_USER_SECTION,
        _CORE_SECTION,
        _ORCH_SECTION,
        _EXAMPLE_SECTION,
        _APPENDIX_SECTION,
        _REFERENCE_SECTION,
        _generate_padding_sections(38),
    ]
    return "\n".join(parts)


def build_skill_with_large_protected() -> str:
    """Build a SKILL.md where protected sections alone exceed a small budget.

    The frontmatter + description + first section are very large.
    Used to test SkillBodyBudgetError when budget is too small.
    """
    large_frontmatter = """\
---
name: test-skill-large-protected
description: >
  A test skill with a very large protected section that exceeds small budgets.
  This description is intentionally long to create a large protected token count.
argument-hint: "[test input]"
---
"""
    large_desc = "# Test Skill\n\n" + "This is protected content. " * 200
    return "\n".join([large_frontmatter, large_desc, _GATE_SECTION])
