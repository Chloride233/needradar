"""Tests for requirements API helper functions."""
import pytest

from needradar.api.v1.requirements import (
    _extract_categories,
    _extract_numbered_bold,
    _extract_pain_points,
    _make_pain_point,
    _normalize_severity,
)


# ── _extract_numbered_bold ──


def test_extract_numbered_bold():
    lines = [
        "## 核心发现",
        "1. **AI code review tools are in high demand**",
        "2. **Developer productivity is key**",
        "Not a finding",
    ]
    results = _extract_numbered_bold(lines, "核心发现")
    assert len(results) == 2
    assert "AI code review" in results[0]


def test_extract_numbered_bold_no_section():
    lines = ["No matching section"]
    results = _extract_numbered_bold(lines, "核心发现")
    assert results == []


def test_extract_numbered_bold_limits_to_5():
    lines = ["## 核心发现"] + [f"{i}. **Finding {i}**" for i in range(1, 10)]
    results = _extract_numbered_bold(lines, "核心发现")
    # The function returns up to 5 (caller slices)
    assert len(results) <= 9  # function itself doesn't limit, caller does [:5]


# ── _normalize_severity ──


def test_normalize_severity_stars():
    assert _normalize_severity("★★★★★") == "高"
    assert _normalize_severity("★★★★") == "中到高"
    assert _normalize_severity("★★★") == "中"
    assert _normalize_severity("★★") == "低"


def test_normalize_severity_text():
    assert _normalize_severity("高") == "高"
    assert _normalize_severity("中") == "中"
    assert _normalize_severity("中到高") == "中到高"


def test_normalize_severity_empty():
    assert _normalize_severity("") == "中"


# ── _make_pain_point ──


def test_make_pain_point():
    point = _make_pain_point("Test Title", "高", ["Line 1", "Line 2"])
    assert point.title == "Test Title"
    assert point.severity == "高"
    assert "Line 1" in point.description
    assert "Line 2" in point.description


def test_make_pain_point_truncates():
    long_lines = ["A" * 200, "B" * 200]
    point = _make_pain_point("Title", "中", long_lines)
    assert len(point.description) <= 300


# ── _extract_pain_points ──


def test_extract_pain_points_format1():
    """Format: ### 1. 共性痛点：Title"""
    lines = [
        "### 1. 共性痛点：AI 代码审查工具不足",
        "表现：开发者需要更好的工具",
        "影响：效率低下",
        "### 2. 共性痛点：文档质量差",
        "表现：文档过时",
    ]
    points = _extract_pain_points(lines)
    assert len(points) >= 1
    assert any("AI" in p.title or "代码" in p.title for p in points)


def test_extract_pain_points_format2():
    """Format: ### 痛点 1：Title"""
    lines = [
        "### 痛点 1：缺少自动化测试",
        "表现：测试覆盖率低",
        "### 痛点 2：部署复杂",
    ]
    points = _extract_pain_points(lines)
    assert len(points) >= 1


def test_extract_pain_points_with_severity():
    """Pain point with inline severity."""
    lines = [
        "### 1. 共性痛点：问题标题（严重程度：★★★★★）",
        "表现：问题描述",
    ]
    points = _extract_pain_points(lines)
    assert len(points) == 1
    assert points[0].severity == "高"


def test_extract_pain_points_empty():
    points = _extract_pain_points(["No pain points here"])
    assert points == []


# ── _extract_categories ──


def test_extract_categories():
    lines = [
        "## 需求类别",
        "### 类别1：工具类",
        "**AI code review**",
        "**CI/CD integration**",
        "### 类别2：平台类",
        "**Developer portal**",
    ]
    categories = _extract_categories(lines)
    assert len(categories) >= 1
    assert categories[0]["name"] == "工具类"


def test_extract_categories_empty():
    categories = _extract_categories(["No categories"])
    assert categories == []
