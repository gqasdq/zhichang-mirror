"""离线安全的混合检索（各业务模块统一入口，避免 HuggingFace 阻塞）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.config import get_settings
from vectorstore.builder import build_vectorstore


def _merge_pending_keyword_hits(
    results: list[dict[str, Any]],
    query: str,
    index_dir: Path,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    pending_file = index_dir / "pending.json"
    if not pending_file.exists():
        return results

    try:
        pending = json.loads(pending_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return results

    q = query.strip().lower()
    if not q:
        return results

    merged = list(results)
    seen_texts = {str(r.get("text", "")) for r in merged}
    for i, item in enumerate(pending if isinstance(pending, list) else []):
        text = str(item.get("text", ""))
        if not text or text in seen_texts:
            continue
        if q in text.lower():
            merged.append(
                {
                    "id": f"pending_{i}",
                    "text": text,
                    "metadata": item.get("metadata", {}),
                    "score": 0.5,
                    "source": "pending",
                }
            )
            seen_texts.add(text)

    merged.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return merged[:top_k]


def hybrid_search(
    query: str,
    *,
    top_k: int = 5,
    include_pending: bool = True,
) -> list[dict[str, Any]]:
    """
    混合检索主索引；embedding 不可用时自动关键词降级。
    不会触发 HuggingFace 长时间下载阻塞。
    """
    q = (query or "").strip()
    if not q:
        return []

    settings = get_settings()
    index_dir = Path(settings.faiss_index_path)
    store = build_vectorstore(
        dimension=settings.vector_dim,
        index_path=str(index_dir),
    )
    results = store.search(q, top_k=top_k, hybrid=True)
    if include_pending:
        results = _merge_pending_keyword_hits(results, q, index_dir, top_k=top_k)
    return results[:top_k]
