from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import diskcache


class HttpCache:
    """Cache en disco de respuestas JSON, para no repetir llamadas dentro de su TTL.

    Tambien es la base de la ingesta incremental: si se vuelve a ejecutar la
    extraccion antes de que expire el TTL de una pagina, no se vuelve a pedir.
    """

    def __init__(self, cache_dir: str | Path) -> None:
        self._cache = diskcache.Cache(str(cache_dir))

    @staticmethod
    def make_key(path: str, params: dict[str, Any] | None) -> str:
        raw = json.dumps({"path": path, "params": params or {}}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        return self._cache.get(key, default=None)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._cache.set(key, value, expire=ttl_seconds)

    def close(self) -> None:
        self._cache.close()
