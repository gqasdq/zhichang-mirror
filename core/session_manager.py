import streamlit as st
import time
from pathlib import Path
import uuid
import shutil

class SessionManager:
    SESSION_DATA_DIR = "data/sessions"
    FAISS_DATA_DIR = "data/faiss"

    @staticmethod
    def get_user_id() -> str:
        uid = st.session_state.get("user_id")
        if not uid:
            uid = str(uuid.uuid4())[:8]
            st.session_state.user_id = uid
        return uid

    @staticmethod
    def get_session_dir() -> Path:
        uid = SessionManager.get_user_id()
        path = Path(SessionManager.SESSION_DATA_DIR) / uid
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_faiss_dir() -> Path:
        """用户个人 FAISS 索引目录（公共知识库仍用 data/knowledge_base 或 ./vectorstore）。"""
        uid = SessionManager.get_user_id()
        path = Path(SessionManager.FAISS_DATA_DIR) / uid
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_user_db_path() -> Path:
        path = SessionManager.get_session_dir() / "user.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def user_file_path(*relative_parts: str) -> Path:
        """用户会话目录下的文件路径，例如 ('gene', 'history.json')。"""
        path = SessionManager.get_session_dir().joinpath(*relative_parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def clear_session():
        uid = SessionManager.get_user_id()
        session_dir = Path(SessionManager.SESSION_DATA_DIR) / uid
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
        faiss_dir = Path(SessionManager.FAISS_DATA_DIR) / uid
        if faiss_dir.exists():
            shutil.rmtree(faiss_dir, ignore_errors=True)
        sensitive_keys = ["resume_text", "chat_history", "gene_report",
                          "gold_report", "parallel_result", "empathy_data",
                          "raw_resume", "user_input"]
        for key in sensitive_keys:
            st.session_state.pop(key, None)

    @staticmethod
    def auto_cleanup_on_start():
        """清理过期会话目录；每个 Streamlit 会话只执行一次。"""
        try:
            import streamlit as st

            if st.session_state.get("_session_cleanup_done"):
                return
            st.session_state["_session_cleanup_done"] = True
        except Exception:
            pass

        if not Path(SessionManager.SESSION_DATA_DIR).exists():
            Path(SessionManager.SESSION_DATA_DIR).mkdir(parents=True, exist_ok=True)
        else:
            now = time.time()
            for d in Path(SessionManager.SESSION_DATA_DIR).iterdir():
                if d.is_dir() and (now - d.stat().st_mtime) > 86400:
                    shutil.rmtree(d, ignore_errors=True)

        faiss_root = Path(SessionManager.FAISS_DATA_DIR)
        if faiss_root.exists():
            now = time.time()
            for d in faiss_root.iterdir():
                if d.is_dir() and (now - d.stat().st_mtime) > 86400:
                    shutil.rmtree(d, ignore_errors=True)
