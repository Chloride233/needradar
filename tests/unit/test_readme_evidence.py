from pathlib import Path


def test_readme_has_no_unreproducible_runtime_snapshot_counts():
    readme = Path("README.md").read_text(encoding="utf-8")

    for unsupported_claim in ("721 reqs", "1134 rag", "936 md"):
        assert unsupported_claim not in readme
