from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.config import get_settings

Base = declarative_base()

_engine = None
_SessionLocal: Optional[sessionmaker] = None
_current_db_uid: Optional[str] = None


def _resolve_db_path() -> Path:
    """按匿名 user_id 隔离 SQLite；无 Streamlit 上下文时回退全局配置路径。"""
    try:
        from core.session_manager import SessionManager

        return SessionManager.get_user_db_path()
    except Exception:
        settings = get_settings()
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path


def init_db() -> None:
    """初始化数据库连接与表结构。"""
    global _engine, _SessionLocal, _current_db_uid

    db_path = _resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    uid: Optional[str] = None
    try:
        from core.session_manager import SessionManager

        uid = SessionManager.get_user_id()
    except Exception:
        pass

    if _engine is not None and _current_db_uid == uid:
        return

    _current_db_uid = uid
    settings = get_settings()
    db_url = f"sqlite:///{db_path.as_posix()}"

    _engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=settings.app_env == "development",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # 导入模型，确保 metadata 能收集到所有表
    from data.models import Analysis, ChatSession, Conversation, JobPosting, Skill, User

    _ = (User, ChatSession, Conversation, Analysis, Skill, JobPosting)
    Base.metadata.create_all(bind=_engine)
    logger.info(f"Database initialized: {db_path}")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（上下文管理器）。"""
    global _SessionLocal

    if _SessionLocal is None:
        init_db()

    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """获取数据库会话（用于依赖注入场景）。"""
    global _SessionLocal

    if _SessionLocal is None:
        init_db()
    return _SessionLocal()
