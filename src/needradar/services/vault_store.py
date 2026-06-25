from __future__ import annotations

import re
from pathlib import Path

import yaml

from needradar.core.config import settings


class VaultStore:
    def __init__(self) -> None:
        self._root = Path(settings.vault_path).resolve()
        self._list_cache: dict[str, tuple[float, list]] = {}
        self._file_cache: dict[str, tuple[float, dict, str]] = {}
        self._cache_ttl = 10  # seconds

    @property
    def root(self) -> Path:
        return self._root

    def _dir(self, stage: str) -> Path:
        mapping = {
            "素材": self._root / "01-原始素材库" / "灵感剪报",
            "需求": self._root / "02-需求池",
            "大纲": self._root / "03-分析车间" / "大纲挑选",
            "初稿": self._root / "03-分析车间" / "初稿打磨",
            "终稿": self._root / "03-分析车间" / "终稿确认",
            "已归档": self._root / "04-报告归档",
            "图谱": self._root / "06-关系图谱",
            "日志": self._root / "05-工作日志",
        }
        return mapping.get(stage, self._root)

    @staticmethod
    def _safe_filename(title: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', '', title)[:80]
        return name.strip() or "untitled"

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        if not text.startswith("---"):
            return {}, text
        end = text.find("---", 3)
        if end == -1:
            return {}, text
        fm_text = text[3:end].strip()
        body = text[end + 3:].strip()
        try:
            meta = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            meta = {}
        return meta, body

    def _read_cached(self, filepath: Path) -> tuple[dict, str]:
        mtime = filepath.stat().st_mtime
        key = str(filepath)
        cached = self._file_cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]
        text = filepath.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(text)
        self._file_cache[key] = (mtime, meta, body)
        return meta, body

    def _render_frontmatter(self, meta: dict) -> str:
        return yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def read(self, path: str | Path) -> tuple[dict, str]:
        full = self._root / path if not Path(path).is_absolute() else Path(path)
        text = full.read_text(encoding="utf-8")
        return self._parse_frontmatter(text)

    def write(self, stage: str, title: str, meta: dict, body: str = "") -> Path:
        directory = self._dir(stage)
        directory.mkdir(parents=True, exist_ok=True)
        filename = self._safe_filename(title) + ".md"
        filepath = directory / filename
        content = f"---\n{self._render_frontmatter(meta)}---\n\n{body}\n"
        filepath.write_text(content, encoding="utf-8")
        self._list_cache.pop(stage, None)
        self._file_cache.pop(str(filepath), None)
        return filepath

    def update_frontmatter(self, path: str | Path, updates: dict) -> None:
        full = self._root / path if not Path(path).is_absolute() else Path(path)
        meta, body = self._parse_frontmatter(full.read_text(encoding="utf-8"))
        meta.update(updates)
        content = f"---\n{self._render_frontmatter(meta)}---\n\n{body}\n"
        full.write_text(content, encoding="utf-8")
        self._list_cache.clear()

    def list_files(self, stage: str) -> list[tuple[Path, dict, str]]:
        import time
        now = time.monotonic()
        cached = self._list_cache.get(stage)
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1]

        directory = self._dir(stage)
        if not directory.exists():
            return []
        results = []
        for f in sorted(directory.glob("*.md")):
            meta, body = self._read_cached(f)
            results.append((f, meta, body))
        self._list_cache[stage] = (now, results)
        return results

    def find_by_title(self, stage: str, title: str) -> Path | None:
        directory = self._dir(stage)
        if not directory.exists():
            return None
        # Exact match first
        safe = self._safe_filename(title) + ".md"
        target = directory / safe
        if target.exists():
            return target
        # Fuzzy match: normalize and compare
        import unicodedata
        def normalize(s: str) -> str:
            s = s.lower().strip()
            s = unicodedata.normalize("NFKC", s)
            s = re.sub(r'[\s\-_]+', ' ', s)
            return s
        norm_title = normalize(title)
        for f in directory.glob("*.md"):
            if normalize(f.stem) == norm_title:
                return f
        # Partial match: check if title is a substring of existing or vice versa
        for f in directory.glob("*.md"):
            stem = normalize(f.stem)
            if norm_title in stem or stem in norm_title:
                return f
        return None

    def search(self, stage: str, keyword: str = "", platform: str = "",
               sentiment: str = "", page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        all_files = self.list_files(stage)
        filtered = []
        for path, meta, body in all_files:
            if keyword:
                kw_lower = keyword.lower()
                in_title = kw_lower in meta.get("标题", "").lower()
                kws = meta.get("关键词", [])
                if isinstance(kws, list):
                    in_kw = any(kw_lower in str(k).lower() for k in kws)
                else:
                    in_kw = kw_lower in str(kws).lower()
                if not in_title and not in_kw:
                    continue
            if platform and meta.get("来源平台", "") != platform:
                continue
            if sentiment and (meta.get("情感倾向") or "moderate") != sentiment:
                continue
            filtered.append({**meta, "_path": str(path.relative_to(self._root)), "_body": body})
        total = len(filtered)
        start = (page - 1) * page_size
        return filtered[start:start + page_size], total

    def archive_raw(self, platform: str, keyword: str, title: str, source_url: str,
                    content: str, tags: list[str] | None = None) -> Path:
        """Archive raw crawled content to vault/01-原始素材库/灵感剪报/."""
        from datetime import date
        meta = {
            "标题": title,
            "阶段": "素材",
            "来源平台": platform,
            "来源URL": source_url,
            "关键词": [keyword],
            "标签": tags or [],
            "抓取时间": str(date.today()),
            "创建时间": str(date.today()),
            "关联参考": [],
            "发布平台": "内部",
        }
        body = f"## 原始内容\n\n{content}"
        return self.write("素材", title, meta, body)

    def top_keywords(self, stage: str, limit: int = 10) -> list[str]:
        all_files = self.list_files(stage)
        kw_counts: dict[str, int] = {}
        for _, meta, _ in all_files:
            kws = meta.get("关键词", [])
            if isinstance(kws, str):
                kws = [kws]
            for kw in kws:
                kw_counts[kw] = kw_counts.get(kw, 0) + 1
        sorted_kw = sorted(kw_counts.items(), key=lambda x: -x[1])
        return [kw for kw, _ in sorted_kw[:limit]]

    # ── Knowledge Layer (07-知识沉淀) ──

    _knowledge_dir_map = {
        "platform_quality": "平台质量",
        "keyword_effectiveness": "关键词效果",
        "noise_pattern": "噪声模式",
        "extraction_rule": "提取规则",
        "prompt_pattern": "Prompt模式",
    }

    def write_knowledge(self, category: str, key: str, value: dict) -> Path:
        """Write a knowledge entry to vault/07-知识沉淀/{category}/{key}.md."""
        subdir = self._knowledge_dir_map.get(category, category)
        directory = self._root / "07-知识沉淀" / subdir
        directory.mkdir(parents=True, exist_ok=True)
        filename = self._safe_filename(key) + ".md"
        filepath = directory / filename

        from datetime import date
        import json as _json
        meta = {
            "标题": key,
            "阶段": "知识",
            "类别": category,
            "创建时间": str(date.today()),
        }
        body = f"## 知识条目\n\n```json\n{_json.dumps(value, ensure_ascii=False, indent=2)}\n```"
        content = f"---\n{self._render_frontmatter(meta)}---\n\n{body}\n"
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def read_knowledge(self, category: str) -> list[tuple[Path, dict, str]]:
        """Read all knowledge entries for a category."""
        subdir = self._knowledge_dir_map.get(category, category)
        directory = self._root / "07-知识沉淀" / subdir
        if not directory.exists():
            return []
        results = []
        for f in sorted(directory.glob("*.md")):
            meta, body = self._read_cached(f)
            results.append((f, meta, body))
        return results


vault = VaultStore()
