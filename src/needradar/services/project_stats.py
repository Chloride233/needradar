from __future__ import annotations

import ast
from pathlib import Path

from needradar.crawlers.factory import available_platforms

FULL_SUPPORT = {"github", "juejin", "stackoverflow"}
VAULT_CONTENT_DIRS = {
    "01-原始素材库",
    "02-需求池",
    "03-分析车间",
    "04-报告归档",
    "06-关系图谱",
    "07-知识沉淀",
}


def _count_test_functions(tests_dir: Path) -> int:
    count = 0
    for path in tests_dir.rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            for node in ast.walk(tree)
        )
    return count


def collect_project_stats(root: Path) -> dict[str, int]:
    platforms = set(available_platforms())
    full_support = platforms & FULL_SUPPORT
    experimental_support = platforms - full_support
    vault = root / "vault"

    return {
        "keyword_platforms": len(platforms),
        "full_support_platforms": len(full_support),
        "experimental_platforms": len(experimental_support),
        "planned_platforms": 0,
        "python_source_files": sum(1 for _ in (root / "src").rglob("*.py")),
        "test_functions": _count_test_functions(root / "tests"),
        "vault_markdown_files": sum(
            1
            for directory in VAULT_CONTENT_DIRS
            for _ in (vault / directory).rglob("*.md")
        ),
    }


def format_project_stats(stats: dict[str, int]) -> str:
    lines = ["NeedRadar Project Stats", "=" * 24]
    lines.extend(f"{key}: {value}" for key, value in stats.items())
    lines.append("test_functions counts test_* definitions, not parametrized cases")
    lines.append("vault_markdown_files excludes work logs")
    return "\n".join(lines)
