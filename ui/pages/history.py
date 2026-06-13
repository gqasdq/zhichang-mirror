"""历史记录页面。"""

from __future__ import annotations

import streamlit as st

from components.session_history import render_session_history_page
from core.analytics import track_module_enter


def render() -> None:
    track_module_enter("历史记录")
    render_session_history_page()
