from __future__ import annotations

import importlib
from pathlib import Path

from loguru import logger

from needradar.crawlers.base import BaseCrawler

_registry: dict[str, type[BaseCrawler]] = {}


def _auto_discover() -> None:
    """Scan crawlers/ package for modules with BaseCrawler subclasses."""
    if _registry:
        return
    pkg_dir = Path(__file__).parent
    for f in sorted(pkg_dir.glob("*.py")):
        if f.name.startswith("_") or f.name == "base.py" or f.name == "factory.py":
            continue
        mod_name = f"needradar.crawlers.{f.stem}"
        try:
            mod = importlib.import_module(mod_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseCrawler)
                    and attr is not BaseCrawler
                    and hasattr(attr, "PLATFORM")
                ):
                    platform = attr.PLATFORM
                    _registry[platform] = attr
                    logger.debug("crawler_registered", platform=platform, cls=attr.__name__)
        except Exception as e:
            logger.warning("crawler_import_failed", module=mod_name, error=str(e))


def register_crawler(platform: str, crawler_cls: type[BaseCrawler]) -> None:
    """Register a crawler class for a platform. For external plugins."""
    _registry[platform] = crawler_cls


def create_crawler(platform: str) -> BaseCrawler:
    _auto_discover()
    cls = _registry.get(platform)
    if cls is None:
        available = ", ".join(sorted(_registry.keys())) or "none"
        raise ValueError(f"Unknown platform: {platform}. Available: {available}")
    return cls()


def available_platforms() -> list[str]:
    _auto_discover()
    return sorted(_registry.keys())
