from __future__ import annotations

import csv
import io
import json
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from scripts.run_rerank_review import PACKAGE_FIELDS, PROTOCOL_VERSION, build_review_package, create_server


def _write_template(path: Path, rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[*PACKAGE_FIELDS, "relevance_grade", "notes"])
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _row(index: int = 1) -> dict[str, str]:
    return {
        "query_id": "query-1",
        "query": "How do I export data?",
        "split": "dev",
        "blind_document_id": f"blind-{index}",
        "platform": "github",
        "title": f"Export issue {index}",
        "text_excerpt": f"CSV export discussion {index}",
        "relevance_grade": "",
        "notes": "",
    }


def test_build_review_package_exposes_only_blinded_fields(tmp_path):
    template = tmp_path / "annotation.csv"
    _write_template(template, [_row(1), _row(2)])

    package = build_review_package(template)

    assert package["protocol_version"] == PROTOCOL_VERSION
    assert package["query_count"] == 1
    assert package["candidate_count"] == 2
    assert len(package["source_template_sha256"]) == 64
    assert set(package["rows"][0]) == set(PACKAGE_FIELDS)
    serialized = json.dumps(package)
    for forbidden in ("original_rank", "original_score", "reranked_rank", "relevance_score", "model_id"):
        assert forbidden not in serialized


@pytest.mark.parametrize("field", ["relevance_grade", "notes"])
def test_build_review_package_rejects_prefilled_template(tmp_path, field):
    template = tmp_path / "annotation.csv"
    row = _row()
    row[field] = "not blank"
    _write_template(template, [row])

    with pytest.raises(ValueError, match="must be blank"):
        build_review_package(template)


def test_build_review_package_rejects_duplicate_blind_ids(tmp_path):
    template = tmp_path / "annotation.csv"
    _write_template(template, [_row(), _row()])

    with pytest.raises(ValueError, match="must be unique"):
        build_review_package(template)


def test_local_server_serves_package_and_rejects_other_paths(tmp_path):
    template = tmp_path / "annotation.csv"
    _write_template(template, [_row()])
    server = create_server(template, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with urlopen(f"http://{host}:{port}/api/package") as response:  # noqa: S310
            package = json.load(response)
            assert response.headers["Cache-Control"] == "no-store"
            assert package["candidate_count"] == 1
        with pytest.raises(Exception):
            urlopen(f"http://{host}:{port}/../manifest.json")  # noqa: S310
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_real_frozen_template_has_expected_blinded_membership():
    root = Path(__file__).resolve().parents[2]
    package = build_review_package(root / "evaluation" / "rerank" / "annotation-template.csv")

    assert package["query_count"] == 100
    assert package["candidate_count"] == 2000
    assert len({row["blind_document_id"] for row in package["rows"]}) == 2000
