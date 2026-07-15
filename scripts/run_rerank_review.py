"""Serve the local-only rerank relevance review tool."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "evaluation" / "rerank" / "annotation-template.csv"
STATIC_DIR = ROOT / "evaluation" / "rerank" / "review-tool"
PROTOCOL_VERSION = "single-expert-blind-test-retest-v1"
PACKAGE_FIELDS = (
    "query_id",
    "query",
    "split",
    "blind_document_id",
    "platform",
    "title",
    "text_excerpt",
)
REQUIRED_TEMPLATE_FIELDS = (*PACKAGE_FIELDS, "relevance_grade", "notes")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/review.js": ("review.js", "text/javascript; charset=utf-8"),
    "/review.css": ("review.css", "text/css; charset=utf-8"),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_review_package(template_path: Path) -> dict[str, object]:
    raw = template_path.read_bytes()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None or set(reader.fieldnames) != set(REQUIRED_TEMPLATE_FIELDS):
        raise ValueError(f"annotation template must contain exactly: {', '.join(REQUIRED_TEMPLATE_FIELDS)}")

    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    queries: dict[str, tuple[str, str]] = {}
    for line_number, source in enumerate(reader, start=2):
        blind_id = source["blind_document_id"].strip()
        query_id = source["query_id"].strip()
        if not blind_id or blind_id in seen_ids:
            raise ValueError(f"line {line_number}: blind_document_id must be unique and non-empty")
        if not query_id or not source["query"].strip():
            raise ValueError(f"line {line_number}: query_id and query must be non-empty")
        if source["relevance_grade"].strip() or source["notes"].strip():
            raise ValueError(f"line {line_number}: frozen annotation template must be blank")
        query_value = (source["query"], source["split"])
        if query_id in queries and queries[query_id] != query_value:
            raise ValueError(f"line {line_number}: query metadata changed within query_id {query_id}")
        queries[query_id] = query_value
        seen_ids.add(blind_id)
        rows.append({field: source[field] for field in PACKAGE_FIELDS})

    if not rows:
        raise ValueError("annotation template is empty")
    return {
        "schema_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "source_template_sha256": _sha256(raw),
        "query_count": len(queries),
        "candidate_count": len(rows),
        "rows": rows,
    }


class ReviewServer(ThreadingHTTPServer):
    package: dict[str, object]


class ReviewHandler(BaseHTTPRequestHandler):
    server: ReviewServer

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/package":
            body = json.dumps(self.server.package, ensure_ascii=False, separators=(",", ":")).encode()
            self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)
            return
        if path == "/favicon.ico":
            self._send(HTTPStatus.NO_CONTENT, "image/x-icon", b"")
            return
        static = STATIC_FILES.get(path)
        if static is None:
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not found\n")
            return
        filename, content_type = static
        self._send(HTTPStatus.OK, content_type, (STATIC_DIR / filename).read_bytes())

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(template_path: Path, port: int) -> ReviewServer:
    package = build_review_package(template_path)
    server = ReviewServer(("127.0.0.1", port), ReviewHandler)
    server.package = package
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        raise SystemExit("--port must be between 0 and 65535")
    server = create_server(args.template.resolve(), args.port)
    host, port = server.server_address
    print(
        f"NeedRadar review tool: http://{host}:{port} "
        f"({server.package['query_count']} queries, {server.package['candidate_count']} candidates)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
