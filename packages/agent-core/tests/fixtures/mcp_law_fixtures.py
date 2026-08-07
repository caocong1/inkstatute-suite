"""Canned law-database responses for fixture-mode regulation search tests.

These responses match the law-database connector's own fixture mode
(``LAW_DB_FIXTURES=1``).  They enable testing the regulation search
tool without a real MCP subprocess or network access.
"""

from __future__ import annotations

# Canned responses keyed by search keyword.
# These mimic the format of the law-database connector's search_laws output.
LAW_FIXTURE_RESPONSES: dict[str, str] = {
    "合同法": (
        "## 搜索结果: 合同法\n\n"
        "### 1. 中华人民共和国民法典\n"
        "- **类型**: 法律\n"
        "- **状态**: 现行有效\n"
        "- **发布机构**: 全国人大\n"
        "- **来源**: flk.npc.gov.cn\n\n"
        "注：《合同法》已废止，相关内容已纳入《民法典》合同编。\n"
    ),
    "民法典": (
        "## 搜索结果: 民法典\n\n"
        "### 1. 中华人民共和国民法典\n"
        "- **类型**: 法律\n"
        "- **状态**: 现行有效\n"
        "- **发布机构**: 全国人大\n"
        "- **发布日期**: 2020-05-28\n"
        "- **施行日期**: 2021-01-01\n"
        "- **来源**: flk.npc.gov.cn\n\n"
        "### 2. 最高人民法院关于适用《中华人民共和国民法典》有关担保制度的解释\n"
        "- **类型**: 司法解释\n"
        "- **状态**: 现行有效\n"
        "- **发布机构**: 最高人民法院\n"
        "- **来源**: court.gov.cn\n"
    ),
    "公司法": (
        "## 搜索结果: 公司法\n\n"
        "### 1. 中华人民共和国公司法\n"
        "- **类型**: 法律\n"
        "- **状态**: 现行有效\n"
        "- **发布机构**: 全国人大常委会\n"
        "- **修订日期**: 2023-12-29\n"
        "- **施行日期**: 2024-07-01\n"
        "- **来源**: flk.npc.gov.cn\n"
    ),
    "劳动法": (
        "## 搜索结果: 劳动法\n\n"
        "### 1. 中华人民共和国劳动法\n"
        "- **类型**: 法律\n"
        "- **状态**: 现行有效\n"
        "- **发布机构**: 全国人大常委会\n"
        "- **发布日期**: 1994-07-05\n"
        "- **施行日期**: 1995-01-01\n"
        "- **来源**: flk.npc.gov.cn\n\n"
        "### 2. 中华人民共和国劳动合同法\n"
        "- **类型**: 法律\n"
        "- **状态**: 现行有效\n"
        "- **发布机构**: 全国人大常委会\n"
        "- **发布日期**: 2007-06-29\n"
        "- **来源**: flk.npc.gov.cn\n"
    ),
}
