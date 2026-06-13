"""Few-Shot 样例检索与格式化（跨模块共享）。"""

from __future__ import annotations

from typing import Any

from loguru import logger

EMPTY_FEW_SHOT = "（暂无相似优质样例）"


def _filter_few_shot_results(
    results: list[dict[str, Any]],
    *,
    module: str,
    top_k: int,
) -> list[str]:
    quality_hits = [
        r
        for r in results
        if (r.get("metadata") or {}).get("type") == "few_shot"
        or float((r.get("metadata") or {}).get("quality_score", 0)) >= 0.8
    ]

    picked: list[dict[str, Any]] = []
    if module:
        module_hits = [
            r for r in quality_hits
            if (r.get("metadata") or {}).get("module") == module
        ]
        if module_hits:
            picked = module_hits[:top_k]
        elif quality_hits:
            picked = quality_hits[:top_k]
        else:
            picked = [r for r in results if r.get("score", 0) > 0.01][:top_k]
    else:
        picked = quality_hits[:top_k] if quality_hits else results[:top_k]

    texts: list[str] = []
    for item in picked:
        text = str(item.get("text", "")).strip()
        if text:
            texts.append(text)
    return texts[:top_k]


def _search_few_shot_keyword_only(
    query: str,
    *,
    module: str,
    top_k: int,
) -> list[str]:
    """不加载 embedding，仅关键词检索 metadata + pending 队列。"""
    from pathlib import Path
    import json

    from core.config import get_settings
    from vectorstore.base import VectorStore

    settings = get_settings()
    store = VectorStore(dimension=settings.vector_dim)
    index_dir = Path(settings.faiss_index_path)
    metadata_file = index_dir / "metadata.json"
    if metadata_file.exists():
        try:
            data = json.loads(metadata_file.read_text(encoding="utf-8"))
            store._texts = list(data.get("texts", []))
            store._metadata = list(data.get("metadata", []))
        except (json.JSONDecodeError, OSError):
            pass

    results = store._search_keyword(query.strip(), top_k=max(top_k * 2, top_k))

    pending_file = index_dir / "pending.json"
    if pending_file.exists():
        try:
            pending = json.loads(pending_file.read_text(encoding="utf-8"))
            q = query.strip().lower()
            for i, item in enumerate(pending if isinstance(pending, list) else []):
                text = str(item.get("text", ""))
                if q and q in text.lower():
                    results.append(
                        {
                            "text": text,
                            "metadata": item.get("metadata", {}),
                            "score": 0.5,
                        }
                    )
        except (json.JSONDecodeError, OSError):
            pass

    return _filter_few_shot_results(results, module=module, top_k=top_k)


def search_few_shot_examples(
    query: str,
    *,
    module: str = "",
    top_k: int = 3,
) -> list[str]:
    """混合检索向量库，优先返回指定模块的优质 Few-Shot 样例。"""
    if not (query or "").strip():
        return []

    from vectorstore.base import is_embedding_available

    if not is_embedding_available():
        return _search_few_shot_keyword_only(query, module=module, top_k=top_k)

    try:
        from vectorstore.builder import build_vectorstore
        from vectorstore.base import EncoderUnavailableError
        from core.config import get_settings

        settings = get_settings()
        vs = build_vectorstore(
            dimension=settings.vector_dim,
            index_path=settings.faiss_index_path,
        )
        results = vs.search(query.strip(), top_k=max(top_k * 2, top_k), hybrid=True)
    except EncoderUnavailableError:
        logger.info("[few_shot] embedding unavailable, using keyword-only retrieval")
        return _search_few_shot_keyword_only(query, module=module, top_k=top_k)
    except Exception as exc:
        logger.debug("[few_shot] search skipped: %s", exc)
        return _search_few_shot_keyword_only(query, module=module, top_k=top_k)

    return _filter_few_shot_results(results, module=module, top_k=top_k)


def format_few_shot_for_prompt(
    examples: list[str],
    *,
    header: str = "以下是相似场景的过往优质样例，请参考其风格与结构，针对当前输入生成新内容：",
) -> str:
    """将样例列表格式化为 Prompt 注入文本。"""
    if not examples:
        return EMPTY_FEW_SHOT

    lines = [header, ""]
    for i, text in enumerate(examples, 1):
        lines.append(f"### 样例{i}：\n{text.strip()}\n")
    return "\n".join(lines)


def retrieve_few_shot_text(
    query: str,
    *,
    module: str = "",
    top_k: int = 3,
    header: str = "",
) -> str:
    """检索并格式化 Few-Shot 文本，供 Prompt 占位符注入。"""
    examples = search_few_shot_examples(query, module=module, top_k=top_k)
    default_header = (
        "以下是相似场景的过往优质样例，请参考其风格与结构，针对当前输入生成新内容："
        if not header
        else header
    )
    return format_few_shot_for_prompt(examples, header=default_header)
