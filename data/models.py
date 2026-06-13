from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from data.database import Base


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True, comment="用户唯一标识")
    username = Column(String(64), nullable=True, comment="用户名")
    email = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, user_id='{self.user_id}')>"


class ChatSession(Base):
    """会话表（类名避免与 SQLAlchemy Session 冲突）。"""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    module_type = Column(
        String(32),
        nullable=False,
        comment="模块类型: emotion/gold_detector/parallel_universe/gene_sequencing",
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="sessions")
    conversations = relationship("Conversation", back_populates="session", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, module_type='{self.module_type}')>"


class Conversation(Base):
    """对话记录表。"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    role = Column(String(16), nullable=False, comment="角色: user/assistant/system")
    content = Column(Text, nullable=False)
    model_type = Column(String(32), nullable=True, comment="使用的模型: deepseek/zhipu")
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_conversation_session_created", "session_id", "created_at"),
    )

    session = relationship("ChatSession", back_populates="conversations")

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, role='{self.role}')>"


class Analysis(Base):
    """分析结果表。"""

    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    analysis_type = Column(String(32), nullable=False, comment="分析类型")
    input_data = Column(JSON, nullable=True, comment="输入数据")
    output_data = Column(JSON, nullable=False, comment="输出数据")
    score = Column(Float, nullable=True, comment="评分/分数")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_analysis_session_type", "session_id", "analysis_type"),
    )

    session = relationship("ChatSession", back_populates="analyses")

    def __repr__(self) -> str:
        return f"<Analysis(id={self.id}, type='{self.analysis_type}')>"


class Skill(Base):
    """技能库表。"""

    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_name = Column(String(128), nullable=False, index=True)
    skill_category = Column(String(64), nullable=True)
    skill_level = Column(String(32), nullable=True, comment="基础/中级/高级/专家")
    description = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    vector_id = Column(Integer, nullable=True, index=True, comment="FAISS向量ID")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.skill_name}')>"


class JobPosting(Base):
    """职位表。"""

    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_title = Column(String(128), nullable=False, index=True)
    company_name = Column(String(128), nullable=True)
    job_description = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=True)
    salary_range = Column(String(64), nullable=True)
    location = Column(String(128), nullable=True)
    job_category = Column(String(64), nullable=True, index=True)
    vector_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<JobPosting(id={self.id}, title='{self.job_title}')>"
