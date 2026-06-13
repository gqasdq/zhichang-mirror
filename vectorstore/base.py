"""基于 FAISS 的向量存储（BGE-large-zh-v1.5，1024维）。"""

import json
import os
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
from loguru import logger

from core.config import get_settings
from core.privacy_filter import sanitize_for_api

if TYPE_CHECKING:
    import faiss
    from sentence_transformers import SentenceTransformer


class EncoderUnavailableError(RuntimeError):
    """Embedding 模型不可用（网络/缓存缺失）。"""


_ENCODER_LOAD_FAILED = False
_ENCODER_LOCK = threading.Lock()
_ENCODER_MODEL_ID = "BAAI/bge-large-zh-v1.5"


def _embedding_disabled_by_config() -> bool:
    """环境或配置显式关闭 embedding 时，直接走关键词检索。"""
    if os.environ.get("DISABLE_EMBEDDING", "").lower() in ("1", "true", "yes"):
        return True
    try:
        settings = get_settings()
        return bool(getattr(settings, "disable_embedding", False))
    except Exception:
        return False


def _apply_hf_endpoint() -> None:
    settings = get_settings()
    endpoint = (
        getattr(settings, "hf_endpoint", None)
        or getattr(settings, "huggingface_endpoint", None)
        or getattr(settings, "hf_mirror", None)
        or getattr(settings, "huggingface_mirror", None)
        or os.environ.get("HF_ENDPOINT")
    )
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint


def is_embedding_available() -> bool:
    """embedding 是否仍可用（未被标记失败且未被配置关闭）。"""
    return not (_ENCODER_LOAD_FAILED or _embedding_disabled_by_config())


def mark_embedding_unavailable(reason: str = "") -> None:
    """标记 embedding 不可用，后续检索统一走关键词降级。"""
    global _ENCODER_LOAD_FAILED
    _ENCODER_LOAD_FAILED = True
    if reason:
        logger.info("[vectorstore] embedding marked unavailable: {}", reason)


def _sanitize_metadata(metadata: dict) -> dict:
    """脱敏 metadata 中的字符串字段，避免落盘原始 PII。"""
    safe: dict = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            safe[key] = sanitize_for_api(value)
        elif isinstance(value, dict):
            safe[key] = _sanitize_metadata(value)
        else:
            safe[key] = value
    return safe


_RRF_K = 60
_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fa5]{2,}|\w+")


class VectorStore:
    """基于 FAISS 的向量存储（BGE-large-zh-v1.5，1024维）。"""

    def __init__(self, dimension: int = 1024) -> None:
        self.dimension = dimension
        self._index: Any = None
        self._metadata: list[dict] = []
        self._texts: list[str] = []
        self._encoder: Optional["SentenceTransformer"] = None
        self._add_lock = threading.Lock()

    def _ensure_index(self) -> Any:
        if self._index is None:
            import faiss

            self._index = faiss.IndexFlatIP(self.dimension)
        return self._index

    def _instantiate_encoder(self, *, local_files_only: bool) -> "SentenceTransformer":
        from sentence_transformers import SentenceTransformer

        _apply_hf_endpoint()
        return SentenceTransformer(_ENCODER_MODEL_ID, local_files_only=local_files_only)

    def _load_encoder(self) -> "SentenceTransformer":
        """懒加载编码模型；优先离线缓存，失败则标记不可用并降级关键词检索。"""
        global _ENCODER_LOAD_FAILED

        if self._encoder is not None:
            return self._encoder
        if _ENCODER_LOAD_FAILED or _embedding_disabled_by_config():
            _ENCODER_LOAD_FAILED = True
            raise EncoderUnavailableError("embedding model previously unavailable")

        with _ENCODER_LOCK:
            if self._encoder is not None:
                return self._encoder
            if _ENCODER_LOAD_FAILED or _embedding_disabled_by_config():
                _ENCODER_LOAD_FAILED = True
                raise EncoderUnavailableError("embedding model previously unavailable")

            try:
                self._encoder = self._instantiate_encoder(local_files_only=True)
            except Exception as local_exc:
                allow_download = os.environ.get("ALLOW_EMBEDDING_DOWNLOAD", "").lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if not allow_download:
                    mark_embedding_unavailable("local cache missing and download disabled")
                    raise EncoderUnavailableError(str(local_exc)) from local_exc
                try:
                    self._encoder = self._instantiate_encoder(local_files_only=False)
                except Exception as exc:
                    mark_embedding_unavailable(str(exc))
                    logger.warning("[vectorstore] embedding model load failed: {}", exc)
                    raise EncoderUnavailableError(str(exc)) from exc

        return self._encoder

    def _encode(self, texts: list[str]) -> np.ndarray:
        """内部编码方法。"""
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        try:
            model = self._load_encoder()
        except EncoderUnavailableError:
            raise

        vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        return vectors

    def add_vectors(self, texts: list[str], metadatas: list[dict] | None = None) -> list[int]:
        """编码文本并添加到索引，返回新增向量 ID 列表。"""
        if not texts:
            return []

        if metadatas is not None and len(metadatas) != len(texts):
            raise ValueError("metadatas length must equal texts length")

        if metadatas is None:
            metadatas = [{} for _ in texts]

        sanitized_texts = [sanitize_for_api(t) for t in texts]
        sanitized_metadatas = [_sanitize_metadata(m) for m in metadatas]

        try:
            vectors = self._encode(sanitized_texts)
        except EncoderUnavailableError as exc:
            raise EncoderUnavailableError(
                "cannot add vectors while embedding model is unavailable"
            ) from exc
        index = self._ensure_index()
        with self._add_lock:
            start_id = index.ntotal
            index.add(vectors)

            self._texts.extend(sanitized_texts)
            self._metadata.extend(sanitized_metadatas)

            end_id = index.ntotal
            return list(range(start_id, end_id))

    def search(self, query: str, top_k: int = 5, hybrid: bool = True) -> list[dict]:
        """编码查询文本并返回最相似的结果；embedding 不可用时降级关键词检索。"""
        if not (query or "").strip():
            return []
        if not is_embedding_available():
            return self._search_keyword(query, top_k=top_k)
        if hybrid:
            return self.search_hybrid(query, top_k=top_k)
        try:
            return self._search_vector(query, top_k=top_k)
        except EncoderUnavailableError:
            return self._search_keyword(query, top_k=top_k)

    def _search_vector(self, query: str, top_k: int) -> list[dict]:
        """纯向量检索。"""
        if not query.strip():
            return []
        index = self._ensure_index()
        if index.ntotal == 0:
            return []

        query_vector = self._encode([query])
        k = min(max(top_k, 1), index.ntotal)
        scores, indices = index.search(query_vector, k)

        results: list[dict] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append(
                {
                    "id": int(idx),
                    "text": self._texts[int(idx)] if idx < len(self._texts) else "",
                    "metadata": self._metadata[int(idx)] if idx < len(self._metadata) else {},
                    "score": float(score),
                    "source": "vector",
                }
            )
        return results

    def search_hybrid(self, query: str, top_k: int = 5) -> list[dict]:
        """混合检索：向量 + 关键词；向量不可用时仅关键词。"""
        if not query.strip():
            return []

        if not is_embedding_available():
            return self._search_keyword(query, top_k)[:top_k]

        vector_results: list[dict] = []
        try:
            vector_results = self._search_vector(query, top_k * 2)
        except EncoderUnavailableError:
            vector_results = []

        keyword_results = self._search_keyword(query, top_k * 2)
        if not vector_results:
            return keyword_results[:top_k]

        fused_scores: dict[int, dict[str, Any]] = {}
        for rank, doc in enumerate(vector_results):
            doc_id = int(doc["id"])
            if doc_id not in fused_scores:
                fused_scores[doc_id] = {"doc": doc, "score": 0.0}
            fused_scores[doc_id]["score"] += 1.0 / (rank + _RRF_K)

        for rank, doc in enumerate(keyword_results):
            doc_id = int(doc["id"])
            if doc_id not in fused_scores:
                fused_scores[doc_id] = {"doc": doc, "score": 0.0}
            fused_scores[doc_id]["score"] += 1.0 / (rank + _RRF_K)

        sorted_docs = sorted(fused_scores.values(), key=lambda x: x["score"], reverse=True)
        results: list[dict] = []
        for item in sorted_docs[:top_k]:
            doc = dict(item["doc"])
            doc["score"] = float(item["score"])
            doc["source"] = "hybrid"
            results.append(doc)
        return results

    def _doc_tokens(self, idx: int) -> set[str]:
        """提取文档关键词 token（metadata.keywords 或文本 fallback）。"""
        tokens: set[str] = set()
        metadata = self._metadata[idx] if idx < len(self._metadata) else {}

        keywords = metadata.get("keywords")
        if isinstance(keywords, list):
            tokens.update(str(k).lower() for k in keywords if k)
        elif isinstance(keywords, str) and keywords.strip():
            tokens.update(keywords.lower().split())

        for key in ("emotion", "category", "type", "target_role"):
            val = metadata.get(key, "")
            if isinstance(val, str) and val.strip():
                tokens.add(val.lower())

        text = self._texts[idx] if idx < len(self._texts) else ""
        tokens.update(t.lower() for t in _TOKEN_PATTERN.findall(text))
        return tokens

    def _search_keyword(self, query: str, top_k: int) -> list[dict]:
        """关键词检索（基于 metadata 与文本 token 重叠）。"""
        query_tokens = set(t.lower() for t in _TOKEN_PATTERN.findall(query))
        if not query_tokens:
            query_tokens = set(query.lower().split())

        results: list[dict] = []
        for idx in range(len(self._texts)):
            doc_tokens = self._doc_tokens(idx)
            overlap = len(query_tokens & doc_tokens)
            if overlap <= 0:
                continue
            results.append(
                {
                    "id": idx,
                    "text": self._texts[idx],
                    "metadata": self._metadata[idx] if idx < len(self._metadata) else {},
                    "score": overlap / max(len(query_tokens), 1),
                    "source": "keyword",
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def save(self, path: str) -> None:
        """保存索引和元数据到磁盘。"""
        import faiss

        index = self._ensure_index()
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)

        index_file = target / "index.faiss"
        metadata_file = target / "metadata.json"

        faiss.write_index(index, str(index_file))
        with metadata_file.open("w", encoding="utf-8") as f:
            json.dump({"texts": self._texts, "metadata": self._metadata}, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        """从磁盘加载索引和元数据。"""
        import faiss

        target = Path(path)
        index_file = target / "index.faiss"
        metadata_file = target / "metadata.json"

        if not index_file.exists() or not metadata_file.exists():
            raise FileNotFoundError(f"Vector index or metadata not found in: {path}")

        self._index = faiss.read_index(str(index_file))
        with metadata_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self._texts = list(data.get("texts", []))
        self._metadata = list(data.get("metadata", []))
