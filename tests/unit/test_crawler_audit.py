from pathlib import Path

from needradar.crawlers.factory import available_platforms

FULL_SUPPORT = {"github", "juejin", "stackoverflow"}


def _documented_rows(audit: str) -> dict[str, list[str]]:
    return {
        cells[0].strip("`"): cells
        for line in audit.splitlines()
        if line.startswith("| `")
        for cells in [[cell.strip() for cell in line.strip("|").split("|")]]
    }


def test_audit_lists_every_discovered_keyword_crawler():
    audit = Path("docs/crawler-audit.md").read_text(encoding="utf-8")
    documented = set(_documented_rows(audit))

    assert documented == set(available_platforms())


def test_audit_assigns_evidence_based_support_tiers():
    audit = Path("docs/crawler-audit.md").read_text(encoding="utf-8")
    rows = _documented_rows(audit)

    assert {platform for platform, cells in rows.items() if cells[2] == "Full"} == FULL_SUPPORT
    assert all(cells[2] in {"Full", "Experimental"} for cells in rows.values())
    assert "no planned keyword platforms" in audit.lower()


def test_audit_references_existing_test_files():
    audit = Path("docs/crawler-audit.md").read_text(encoding="utf-8")
    referenced_tests = {
        token.strip("`")
        for token in audit.replace("|", " ").split()
        if token.startswith("`tests/") and token.endswith(".py`")
    }

    assert referenced_tests
    assert all(Path(path).is_file() for path in referenced_tests)
