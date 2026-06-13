from pathlib import Path

from vectorstore.base import VectorStore


def build_vectorstore(dimension: int = 1024, index_path: str | None = None) -> VectorStore:
    """构建或加载 VectorStore。"""
    store = VectorStore(dimension=dimension)

    if index_path:
        path = Path(index_path)
        if path.exists():
            try:
                store.load(str(path))
            except FileNotFoundError:
                # 目录存在但索引文件不存在时，返回空 store
                pass

    return store
