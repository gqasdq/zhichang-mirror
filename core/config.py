from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置类。"""

    # LLM配置
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4-flash"

    # Coze配置（MVP阶段保留，不强依赖）
    coze_api_key: str = ""
    coze_bot_id_emotion: str = ""
    coze_bot_id_gold: str = ""
    coze_bot_id_gene: str = ""

    # 应用配置
    app_name: str = "职场镜子"
    app_version: str = "1.0.0"
    app_env: str = "development"

    # 数据库配置（脚本/无 Streamlit 时回退；应用内由 SessionManager 按 user_id 隔离）
    database_path: str = "./data/zhijing.db"

    # FAISS 公共种子索引（803 条故事 + 情绪知识库，全员共享，勿按 user_id 隔离）
    faiss_index_path: str = "./vectorstore"
    vector_dim: int = 1024
    disable_embedding: bool = False
    hf_endpoint: str = ""

    # 日志配置
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    # 体验数据持久化（JSONL，跨 session 累计）
    analytics_path: str = "./data/analytics/events.jsonl"

    # 缓存配置
    cache_ttl: int = 3600
    cache_max_size: int = 100

    # 限流配置
    rate_limit_enabled: bool = True
    rate_limit_deepseek: int = 60
    rate_limit_zhipu: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def ensure_dirs(self) -> None:
        """确保运行所需目录存在。"""
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.faiss_index_path).mkdir(parents=True, exist_ok=True)
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        Path(self.analytics_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取配置单例。"""
    settings = Settings()
    settings.ensure_dirs()
    return settings
