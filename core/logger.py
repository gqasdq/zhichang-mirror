import sys
from pathlib import Path

from loguru import logger

from core.config import get_settings


def setup_logging() -> None:
    """初始化全局日志配置。"""
    settings = get_settings()
    Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    logger.add(
        settings.log_file,
        level=settings.log_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )


__all__ = ["logger", "setup_logging"]
