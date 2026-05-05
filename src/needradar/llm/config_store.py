from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from loguru import logger

_CONFIG_PATH = Path("data/llm_config.json")


def _ensure_dir() -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {"active_model": "", "presets": {}}
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("llm_config_load_failed", error=str(e))
        return {"active_model": "", "presets": {}}


def save_config(config: dict) -> None:
    _ensure_dir()
    data = json.dumps(config, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_CONFIG_PATH.parent), suffix=".tmp", prefix="llm_cfg_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(_CONFIG_PATH))
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    logger.info("llm_config_saved", path=str(_CONFIG_PATH))


def save_preset_config(preset_id: str, *, api_key: str | None = None,
                       temperature: float | None = None,
                       max_tokens: int | None = None) -> None:
    config = load_config()
    presets = config.setdefault("presets", {})
    entry = presets.setdefault(preset_id, {})
    if api_key is not None:
        entry["api_key"] = api_key
    if temperature is not None:
        entry["temperature"] = temperature
    if max_tokens is not None:
        entry["max_tokens"] = max_tokens
    save_config(config)


def save_active_model(preset_id: str) -> None:
    config = load_config()
    config["active_model"] = preset_id
    save_config(config)
