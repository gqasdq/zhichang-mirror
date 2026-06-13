import time
from collections import OrderedDict
from typing import Any, Optional

from core.config import get_settings


class CacheManager:
    """简单LRU缓存（带TTL）。"""

    def __init__(self, max_size: int, ttl: int) -> None:
        self.max_size = max_size
        self.ttl = ttl
        self._cache: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()

    def _is_expired(self, created_at: float) -> bool:
        return (time.time() - created_at) > self.ttl

    def get(self, key: str) -> Optional[Any]:
        item = self._cache.get(key)
        if item is None:
            return None

        value, created_at = item
        if self._is_expired(created_at):
            self._cache.pop(key, None)
            return None

        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        now = time.time()
        if key in self._cache:
            self._cache.pop(key, None)
        self._cache[key] = (value, now)
        self._cache.move_to_end(key)

        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


_settings = get_settings()
cache_manager = CacheManager(max_size=_settings.cache_max_size, ttl=_settings.cache_ttl)
