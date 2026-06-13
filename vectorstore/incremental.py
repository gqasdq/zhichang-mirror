"""FAISS 向量库增量更新。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from core.config import get_settings
from vectorstore.base import VectorStore, EncoderUnavailableError, is_embedding_available


class IncrementalVectorStore:
    """
    增量向量库管理器。
    策略：追加写入 user 级 pending 队列，定期 merge 到主索引。
    """

    def __init__(self, base_path: str | None = None) -> None:
        settings = get_settings()
        self.base_path = Path(base_path or settings.faiss_index_path)
        self.pending_path = self.base_path / "pending.json"
        self._store = VectorStore(dimension=settings.vector_dim)

    def _load_pending(self) -> list[dict[str, Any]]:
        if not self.pending_path.exists():
            return []
        try:
            data = json.loads(self.pending_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_pending(self, items: list[dict[str, Any]]) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.pending_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def queue_add(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        """将新文档加入待索引队列（即时可用，异步合并）。"""
        pending = self._load_pending()
        item = {
            "text": text,
            "metadata": metadata or {},
            "queued_at": datetime.now().isoformat(),
        }
        pending.append(item)
        self._save_pending(pending)
        logger.info(f"[vectorstore] queued item #{len(pending)}")
        return len(pending) - 1

    def flush_pending(self) -> int:
        """将 pending 队列合并入主 FAISS 索引并持久化。"""
        pending = self._load_pending()
        if not pending:
            return 0

        if not is_embedding_available():
            logger.info("[vectorstore] flush skipped: embedding unavailable, pending kept")
            return 0

        index_dir = self.base_path
        if (index_dir / "index.faiss").exists():
            self._store.load(str(index_dir))

        texts = [p["text"] for p in pending]
        metas = [p.get("metadata", {}) for p in pending]
        try:
            added = self._store.add_vectors(texts, metas)
        except EncoderUnavailableError:
            logger.info("[vectorstore] flush skipped: embedding unavailable, pending kept")
            return 0
        self._store.save(str(index_dir))
        self._save_pending([])
        logger.info(f"[vectorstore] flushed {len(added)} vectors to index")
        return len(added)

    def search_with_pending(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """搜索主索引 + pending 队列（embedding 不可用时仅关键词）。"""
        from vectorstore.safe_search import hybrid_search

        return hybrid_search(query, top_k=top_k, include_pending=True)
