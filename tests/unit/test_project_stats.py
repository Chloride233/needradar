from pathlib import Path

from needradar.cli import DEFAULT_PLATFORMS
from needradar.services.project_stats import (
    FULL_SUPPORT,
    collect_project_stats,
    format_project_stats,
)


def test_collect_project_stats_from_fixture(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_module.py").write_text(
        "def test_one(): pass\nclass TestGroup:\n    async def test_two(self): pass\n",
        encoding="utf-8",
    )
    requirement_dir = tmp_path / "vault" / "02-需求池"
    requirement_dir.mkdir(parents=True)
    (requirement_dir / "one.md").write_text("# One\n", encoding="utf-8")
    log_dir = tmp_path / "vault" / "05-工作日志"
    log_dir.mkdir()
    (log_dir / "ignored.md").write_text("# Log\n", encoding="utf-8")

    stats = collect_project_stats(tmp_path)

    assert stats == {
        "keyword_platforms": 9,
        "full_support_platforms": 3,
        "experimental_platforms": 6,
        "planned_platforms": 0,
        "python_source_files": 1,
        "test_functions": 2,
        "vault_markdown_files": 1,
    }


def test_format_project_stats_explains_counting_scope():
    output = format_project_stats({"test_functions": 2})

    assert "test_functions: 2" in output
    assert "not parametrized cases" in output
    assert "excludes work logs" in output


def test_stats_command_is_documented():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "python -m needradar.cli stats" in readme


def test_readme_cli_and_stats_use_the_same_support_counts():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert set(DEFAULT_PLATFORMS) == FULL_SUPPORT
    assert "3 fully supported and 6 experimental keyword platforms" in readme
    assert "3 full + 6 experimental platforms" in readme
