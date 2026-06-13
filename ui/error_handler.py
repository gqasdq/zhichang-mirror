"""统一错误处理"""

import logging

import streamlit as st

logger = logging.getLogger(__name__)

FRIENDLY_MESSAGES = {
    "timeout": "思考的时间有点久，可能是网络不太好，再试一次看看？",
    "api_error": "服务暂时开小差了，稍等一下再试试。",
    "parse_error": "生成结果时出了点问题，再试一次吧。",
    "general": "出了点小状况，再试一次看看？如果一直不行，可以换个方式描述一下。",
    "empty_result": "这次没有分析出结果，换个描述试试？",
}


def _message_key_for(error: Exception) -> str:
    error_str = str(error).lower()

    if "timeout" in error_str or "timed out" in error_str or "超时" in error_str:
        return "timeout"
    if (
        "api" in error_str
        or "connection" in error_str
        or "500" in error_str
        or "502" in error_str
        or "503" in error_str
        or "网络" in error_str
        or "服务" in error_str
    ):
        return "api_error"
    if "json" in error_str or "parse" in error_str or "解析" in error_str:
        return "parse_error"
    return "general"


def get_friendly_message(error: Exception) -> str:
    """根据异常类型返回友好提示文案。"""
    return FRIENDLY_MESSAGES[_message_key_for(error)]


def handle_api_error(error: Exception, context: str = "") -> None:
    """捕获API异常，显示友好提示，记录日志。"""
    if context:
        logger.warning("[%s] %s: %s", context, type(error).__name__, error)

    st.error(get_friendly_message(error))
