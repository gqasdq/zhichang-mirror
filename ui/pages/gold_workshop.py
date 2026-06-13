"""金子工坊 — 简历在线编辑器。"""

from __future__ import annotations

import difflib
import html
import io
import json
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any

import streamlit as st

from core.analytics import track_module_enter
from core.session_manager import SessionManager
from components.optimization_report import render_optimization_report
from components.thinking_chain import get_workshop_steps, run_with_thinking_chain
from engines.basic_info_checker import check_basic_info_format, format_check_summary
from engines.pdf_exporter import PDFExporter, pre_export_check, _find_unconfirmed_estimates
from engines.resume_optimizer import ResumeOptimizer
from engines.resume_parser import ResumeParser, SECTION_KEYS
from ui.design_system import render_page_header
from ui.emotion_theme import apply_emotion_breath
from utils.emotion_adapter import EmotionAdapter, normalize_emotion_state

logger = logging.getLogger(__name__)

SECTION_ORDER = [
    ("basic_info", "基本信息", "📋"),
    ("objective", "求职意向", "🎯"),
    ("education", "教育背景", "🎓"),
    ("work_exp", "工作经历", "💼"),
    ("project_exp", "项目经历", "🔧"),
    ("skills", "专业技能", "⚡"),
    ("self_eval", "自我评价", "💬"),
]

SECTION_OPTIMIZE_TYPES: dict[str, list[str]] = {
    "basic_info": ["格式规范"],
    "objective": ["措辞优化", "JD匹配"],
    "education": ["相关课程补充"],
    "work_exp": ["STAR改写", "量化补充", "关键词嵌入", "去口语化"],
    "project_exp": ["STAR改写", "量化补充", "技术栈突出"],
    "skills": ["分类整理", "JD对比补全"],
    "self_eval": ["去空话套话", "数据支撑"],
}

SECTION_NAME_MAP = {key: name for key, name, _ in SECTION_ORDER}

EMPTY_SECTION_GUIDES: dict[str, dict[str, str]] = {
    "objective": {
        "title": "📭 当前简历中没有求职意向。",
        "body": "求职意向能帮 HR 快速判断你和岗位的匹配度，建议补充。",
        "hint": "格式参考：意向岗位：XXX | 期望城市：XXX | 到岗时间：XXX",
        "btn": "✏️ 添加求职意向",
    },
    "self_eval": {
        "title": "📭 当前简历中没有自我评价。",
        "body": "简短有力的自我评价可以突出你的核心优势（可选板块）。",
        "hint": "格式参考：3 句话概括核心能力 + 与岗位的匹配点",
        "btn": "✏️ 添加自我评价",
    },
}


def _get_query_value(key: str) -> str | None:
    if hasattr(st, "query_params"):
        value = st.query_params.get(key)
    else:
        value = st.experimental_get_query_params().get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _consume_section_query() -> None:
    section = _get_query_value("ws_section")
    valid = {key for key, _, _ in SECTION_ORDER}
    if section in valid:
        st.session_state.workshop_current_section = section
        st.session_state.workshop_manual_editing = None


def _inject_styles() -> None:
    st.markdown(
        """
<style>
.block-container {
    max-width: 100% !important;
    padding-left: 12px !important;
    padding-right: 24px !important;
    padding-top: 6px !important;
}
[data-testid="stMainBlockContainer"] {
    padding-top: 6px !important;
}
#ws-root ~ div[data-testid="stHorizontalBlock"] {
    gap: 1rem !important;
    align-items: flex-start !important;
}
#ws-root ~ div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
    min-width: 176px !important;
    max-width: 200px !important;
    flex: 0 0 200px !important;
}
#ws-root ~ div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
    flex: 1 1 0 !important;
    min-width: 0 !important;
}
.ws-nav-shell {
    background: linear-gradient(180deg, rgba(255,255,255,0.72) 0%, rgba(255,255,255,0.52) 100%);
    border: 1px solid rgba(61, 56, 51, 0.07);
    border-radius: 14px;
    padding: 10px 8px 14px;
    box-shadow: 0 1px 3px rgba(44, 36, 32, 0.04);
}
.ws-nav-title {
    font-size: 11px;
    font-weight: 650;
    color: #8C8279;
    padding: 2px 8px 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.ws-nav-item {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 36px;
    padding: 0 10px;
    margin-bottom: 2px;
    border-radius: 8px;
    text-decoration: none !important;
    color: #2C2420 !important;
    font-size: 13px;
    transition: background 0.15s ease;
}
.ws-nav-item:hover {
    background: rgba(184, 144, 138, 0.08);
}
.ws-nav-active {
    background: rgba(184, 144, 138, 0.15) !important;
    font-weight: 600;
}
.ws-nav-icon { flex-shrink: 0; width: 18px; text-align: center; }
.ws-nav-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ws-nav-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.ws-dot-current { background: #4A90D9; }
.ws-dot-done { background: #5DAE8B; }
.ws-dot-pending {
    background: transparent;
    border: 1.5px solid #C4B5A9;
}
.workshop-shell { width: 100%; }
.workshop-section-nav {
    background: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(61, 56, 51, 0.08);
    border-radius: 14px;
    padding: 16px 12px;
}
.workshop-nav-title {
    font-size: 13px;
    font-weight: 650;
    color: #6B5B52;
    margin-bottom: 12px;
    letter-spacing: 0.02em;
}
.workshop-progress-label {
    font-size: 12px;
    color: #8C8279;
    margin: 14px 0 6px;
    text-align: center;
}
.workshop-progress-bar {
    height: 6px;
    background: rgba(184, 144, 138, 0.15);
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 8px;
}
.workshop-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #B8908A, #5DAE8B);
    border-radius: 999px;
    transition: width 0.3s ease;
}
.workshop-progress-text {
    font-size: 12px;
    color: #6B5B52;
    text-align: center;
    margin-bottom: 12px;
}
.workshop-editor-card {
    background: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(61, 56, 51, 0.08);
    border-radius: 14px;
    padding: 20px 24px;
}
.ws-content-box {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 14px;
    line-height: 1.75;
    color: #2C2420;
    padding: 16px 18px;
    background: rgba(247, 243, 239, 0.65);
    border: 1px solid rgba(61, 56, 51, 0.08);
    border-radius: 12px;
    min-height: 220px;
    margin: 10px 0 16px;
}
.st-key-ws_nav_basic_info button,
.st-key-ws_nav_objective button,
.st-key-ws_nav_education button,
.st-key-ws_nav_work_exp button,
.st-key-ws_nav_project_exp button,
.st-key-ws_nav_skills button,
.st-key-ws_nav_self_eval button {
    text-align: left !important;
    justify-content: flex-start !important;
    height: 36px !important;
    min-height: 36px !important;
    padding: 0 10px !important;
    margin-bottom: 2px !important;
    font-size: 13px !important;
    border-radius: 8px !important;
}
.st-key-ws_nav_basic_info button:hover,
.st-key-ws_nav_objective button:hover,
.st-key-ws_nav_education button:hover,
.st-key-ws_nav_work_exp button:hover,
.st-key-ws_nav_project_exp button:hover,
.st-key-ws_nav_skills button:hover,
.st-key-ws_nav_self_eval button:hover {
    background: rgba(184, 144, 138, 0.08) !important;
}
.workshop-editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(61, 56, 51, 0.08);
}
.workshop-editor-title {
    font-size: 18px;
    font-weight: 650;
    color: #2C2420;
}
.workshop-diff-label {
    font-size: 12px;
    font-weight: 600;
    color: #8C8279;
    margin-bottom: 8px;
}
.workshop-diff-original,
.workshop-diff-optimized {
    background: rgba(247, 243, 239, 0.8);
    border: 1px solid rgba(61, 56, 51, 0.08);
    border-radius: 12px;
    padding: 16px 18px;
    font-size: 14px;
    line-height: 1.75;
    color: #2C2420;
    white-space: pre-wrap;
    word-break: break-word;
    min-height: 200px;
}
.workshop-diff-optimized {
    background: rgba(255, 255, 255, 0.85);
    border-color: rgba(184, 144, 138, 0.2);
}
.workshop-diff-highlight {
    background: rgba(255, 235, 59, 0.3);
    padding: 1px 4px;
    border-radius: 3px;
}
.workshop-star-tag-S {
    background: rgba(74, 144, 217, 0.15);
    color: #4A90D9;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
}
.workshop-star-tag-T {
    background: rgba(93, 174, 139, 0.15);
    color: #5DAE8B;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
}
.workshop-star-tag-A {
    background: rgba(212, 149, 106, 0.15);
    color: #D4956A;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
}
.workshop-star-tag-R {
    background: rgba(184, 144, 138, 0.18);
    color: #9E6B64;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
}
.workshop-change-badges {
    margin: 16px 0 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.workshop-change-badge {
    display: inline-block;
    background: rgba(255, 235, 59, 0.25);
    color: #6B5B52;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid rgba(184, 144, 138, 0.2);
}
.workshop-content-view {
    background: rgba(247, 243, 239, 0.6);
    border: 1px solid rgba(61, 56, 51, 0.08);
    border-radius: 12px;
    padding: 18px 20px;
    font-size: 14px;
    line-height: 1.75;
    color: #2C2420;
    white-space: pre-wrap;
    min-height: 180px;
    margin-bottom: 16px;
}
.workshop-empty-hint {
    color: #8C8279;
    font-size: 13px;
    font-style: italic;
}
.workshop-meta-row {
    font-size: 12px;
    color: #8C8279;
    margin-bottom: 8px;
}
.ws-format-result {
    margin-top: 16px;
    padding: 14px 16px;
    background: rgba(247, 243, 239, 0.7);
    border: 1px solid rgba(61, 56, 51, 0.08);
    border-radius: 12px;
}
.ws-format-line {
    font-size: 13px;
    line-height: 1.8;
    color: #2C2420;
}
.ws-empty-guide {
    padding: 28px 24px;
    background: rgba(247, 243, 239, 0.55);
    border: 1px dashed rgba(184, 144, 138, 0.35);
    border-radius: 12px;
    margin: 12px 0 16px;
}
.ws-empty-guide-title {
    font-size: 15px;
    font-weight: 650;
    color: #2C2420;
    margin-bottom: 8px;
}
.ws-empty-guide-body {
    font-size: 14px;
    color: #5C4F47;
    line-height: 1.65;
    margin-bottom: 8px;
}
.ws-empty-guide-hint {
    font-size: 12px;
    color: #8C8279;
    line-height: 1.6;
}
.workshop-entry-box {
    background: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(61, 56, 51, 0.08);
    border-radius: 14px;
    padding: 24px 28px;
    margin-top: 8px;
}
.workshop-entry-hint {
    color: #8C8279;
    font-size: 13px;
    margin-bottom: 16px;
    line-height: 1.6;
}

/* ── 金子工坊视觉精修（仅样式，不改逻辑） ── */
.ws-diff-panel {
    border-radius: 14px;
    border: 1px solid rgba(61, 56, 51, 0.08);
    overflow: hidden;
    background: #fff;
    box-shadow: 0 1px 4px rgba(44, 36, 32, 0.04);
}
.ws-diff-panel--ai {
    border-color: rgba(184, 144, 138, 0.22);
    box-shadow: 0 2px 12px rgba(184, 144, 138, 0.08);
}
.ws-diff-panel-head {
    padding: 10px 14px;
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0.05em;
    border-bottom: 1px solid rgba(61, 56, 51, 0.06);
}
.ws-diff-panel--original .ws-diff-panel-head {
    background: rgba(247, 243, 239, 0.95);
    color: #6B5B52;
}
.ws-diff-panel--ai .ws-diff-panel-head {
    background: linear-gradient(90deg, rgba(184,144,138,0.10), rgba(255,252,249,0.95));
    color: #8B5E58;
}
.ws-diff-panel-body {
    padding: 16px 18px;
    font-size: 14px;
    line-height: 1.78;
    min-height: 260px;
    max-height: 420px;
    overflow-y: auto;
}
.ws-diff-panel--original .ws-diff-panel-body { background: rgba(247,243,239,0.45); }
.ws-diff-panel--ai .ws-diff-panel-body { background: rgba(255,255,255,0.92); }
.ws-diff-panel-body.workshop-diff-original,
.ws-diff-panel-body.workshop-diff-optimized {
    border: none;
    border-radius: 0;
    min-height: 260px;
    padding: 16px 18px;
    background: transparent;
}
.ws-compare-badge {
    display: inline-block;
    margin-left: 8px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #8B5E58;
    background: rgba(184, 144, 138, 0.12);
    border-radius: 999px;
    vertical-align: middle;
}
.workshop-diff-highlight {
    background: rgba(255, 214, 102, 0.38) !important;
    border-radius: 4px;
    box-decoration-break: clone;
    -webkit-box-decoration-break: clone;
}
.ws-diff-line {
    padding: 2px 6px;
    border-radius: 4px;
    margin-bottom: 2px;
    white-space: pre-wrap;
    word-break: break-word;
}
.ws-diff-line--unchanged {
    padding: 2px 6px;
}
.ws-diff-line--removed {
    background: rgba(239, 83, 80, 0.08);
    text-decoration: line-through;
    color: #9E8E83;
    border-left: 3px solid #EF5350;
}
.ws-diff-line--changed,
.ws-diff-line--added {
    background: rgba(255, 235, 59, 0.25);
    border-left: 3px solid #FBC02D;
}
.ws-diff-summary {
    font-size: 13px;
    color: #6B5B52;
    margin: 0 0 12px;
    padding: 8px 12px;
    background: rgba(184, 144, 138, 0.08);
    border-radius: 8px;
}
.ai-estimate-badge {
    display: inline-block;
    font-size: 9px;
    background: #FFF8E1;
    color: #F57F17;
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px dashed #F57F17;
    margin-left: 2px;
    vertical-align: middle;
    cursor: help;
}
.workshop-star-tag-S, .workshop-star-tag-T, .workshop-star-tag-A, .workshop-star-tag-R {
    display: inline-block;
    margin-right: 2px;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: 650;
    line-height: 1.5;
}
.workshop-change-badges {
    margin: 14px 0 16px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}
.workshop-change-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255, 248, 235, 0.9);
    padding: 5px 11px;
    font-weight: 500;
}
.workshop-change-badge::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #E6C04A;
}
.workshop-change-badges-label {
    font-size: 12px;
    font-weight: 650;
    color: #8C8279;
    margin-right: 2px;
    letter-spacing: 0.02em;
}
[class*="st-key-workshop_adopt_"] button {
    background: rgba(93, 174, 139, 0.12) !important;
    border: 1px solid rgba(93, 174, 139, 0.35) !important;
    color: #3D7A5C !important;
    font-weight: 600 !important;
}
[class*="st-key-workshop_reject_"] button {
    background: rgba(255,255,255,0.85) !important;
    border: 1px solid rgba(61,56,51,0.12) !important;
    color: #6B5B52 !important;
}
[class*="st-key-workshop_manual_"] button,
[class*="st-key-workshop_edit_"] button {
    background: rgba(230, 168, 87, 0.10) !important;
    border: 1px solid rgba(230, 168, 87, 0.28) !important;
    color: #8A5A24 !important;
    font-weight: 600 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border-color: rgba(61, 56, 51, 0.08) !important;
    background: rgba(255, 255, 255, 0.38) !important;
    box-shadow: 0 1px 3px rgba(44, 36, 32, 0.03);
}
.ws-format-line--pass { color: #3D7A5C; }
.ws-format-line--warn { color: #8A6A1E; }
.ws-format-line--error { color: #B85450; }
.ws-diff-panel-body::-webkit-scrollbar { width: 6px; }
.ws-diff-panel-body::-webkit-scrollbar-thumb {
    background: rgba(184, 144, 138, 0.35);
    border-radius: 999px;
}
.st-key-ws_nav_basic_info button[kind="primary"],
.st-key-ws_nav_objective button[kind="primary"],
.st-key-ws_nav_education button[kind="primary"],
.st-key-ws_nav_work_exp button[kind="primary"],
.st-key-ws_nav_project_exp button[kind="primary"],
.st-key-ws_nav_skills button[kind="primary"],
.st-key-ws_nav_self_eval button[kind="primary"] {
    background: rgba(184, 144, 138, 0.14) !important;
    border: 1px solid rgba(184, 144, 138, 0.22) !important;
    color: #2C2420 !important;
    font-weight: 600 !important;
}
.ws-content-box {
    line-height: 1.8;
    padding: 18px 20px;
    background: linear-gradient(180deg, rgba(255,252,249,0.95), rgba(247,243,239,0.85));
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
}
.ws-format-result-title {
    font-size: 13px;
    font-weight: 650;
    color: #2C2420;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(61, 56, 51, 0.06);
}
.workshop-editor-title { font-size: 17px; letter-spacing: -0.01em; }
.workshop-progress-bar { height: 4px; margin: 0 6px 4px; }
.workshop-progress-fill { transition: width 0.35s cubic-bezier(0.22, 1, 0.36, 1); }
@media (prefers-reduced-motion: reduce) {
    .workshop-progress-fill { transition: none !important; }
}
.ws-export-check {
    margin-top: 20px;
    padding: 20px 22px;
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid rgba(184, 144, 138, 0.22);
    border-radius: 14px;
    box-shadow: 0 2px 12px rgba(44, 36, 32, 0.05);
}
.ws-export-check-title {
    font-size: 16px;
    font-weight: 650;
    color: #2C2420;
    margin-bottom: 14px;
}
.ws-export-check-line {
    font-size: 13px;
    line-height: 1.85;
    color: #2C2420;
    padding: 4px 0;
}
.ws-export-check-line--warn { color: #8A6A1E; }
.ws-export-check-line--info { color: #5C6B7A; }
.ws-export-footer {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px dashed rgba(61, 56, 51, 0.12);
}
.st-key-nav_export button,
.st-key-workshop_export_pdf button {
    font-weight: 600 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "workshop_resume_text": "",
        "workshop_jd_text": "",
        "workshop_quality_data": None,
        "workshop_match_data": None,
        "workshop_sections": {},
        "workshop_sections_parsed": False,
        "workshop_current_section": "basic_info",
        "workshop_section_status": {},
        "workshop_optimized": {},
        "workshop_adopted": {},
        "workshop_emotion_state": "平稳",
        "workshop_manual_editing": None,
        "workshop_optimize_error": None,
        "workshop_changes": {},
        "workshop_optimize_types": {},
        "workshop_resume_input": "",
        "workshop_jd_input": "",
        "workshop_upload_name": None,
        "workshop_basic_format_checked": False,
        "workshop_basic_format_issues": [],
        "workshop_basic_format_passes": [],
        "workshop_show_export_check": False,
        "workshop_pdf_bytes": None,
        "workshop_pdf_template": "classic",
        "workshop_before_scores": None,
        "workshop_after_scores": None,
        "workshop_after_fp": None,
        "workshop_fast_entry": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    if not st.session_state.get("workshop_resume_input") and st.session_state.get("workshop_resume_text"):
        st.session_state.workshop_resume_input = st.session_state.workshop_resume_text
    if not st.session_state.get("workshop_jd_input") and st.session_state.get("workshop_jd_text"):
        st.session_state.workshop_jd_input = st.session_state.workshop_jd_text

    _sync_emotion_state()


def _sync_emotion_state() -> None:
    """从情绪急救站同步情绪状态，读不到则保持平稳。"""
    raw = st.session_state.get("emotion_state")
    if raw:
        st.session_state.workshop_emotion_state = normalize_emotion_state(raw)
        return
    if not st.session_state.get("workshop_emotion_state"):
        st.session_state.workshop_emotion_state = EmotionAdapter.CALM


def _resolve_emotion_state() -> str:
    """解析当前应使用的四种情绪状态之一。"""
    raw = st.session_state.get("emotion_state") or st.session_state.get("workshop_emotion_state")
    if raw:
        return normalize_emotion_state(raw)

    score = st.session_state.get("emotion_start_score")
    if score is not None:
        try:
            s = int(score)
        except (TypeError, ValueError):
            return EmotionAdapter.CALM
        if s <= 6:
            return EmotionAdapter.ANXIOUS
        return EmotionAdapter.CALM

    return EmotionAdapter.CALM


def _get_emotion_adapter() -> EmotionAdapter:
    return EmotionAdapter(_resolve_emotion_state())


def _get_nav_section_order() -> list[tuple[str, str, str]]:
    """挫败/迷茫时调整导航顺序，其余保持默认。"""
    default_keys = [key for key, _, _ in SECTION_ORDER]
    sections = st.session_state.get("workshop_sections") or {}
    adapter = _get_emotion_adapter()
    ordered_keys = adapter.get_section_order(sections, default_order=default_keys)
    order_map = {key: item for item in SECTION_ORDER for key in [item[0]]}
    ordered = [order_map[key] for key in ordered_keys if key in order_map]
    seen = {key for key, _, _ in ordered}
    for item in SECTION_ORDER:
        if item[0] not in seen:
            ordered.append(item)
    return ordered


def _emotion_from_score() -> str:
    return _resolve_emotion_state()


def _extract_scores_from_session() -> dict[str, float | int] | None:
    """从金子探测器传入的 match/quality 数据提取分数，避免重复 AI 调用。"""
    match = st.session_state.get("workshop_match_data")
    if isinstance(match, dict) and match.get("overall_score") is not None:
        return {
            "overall": float(match.get("overall_score", 0)),
            "star": int(match.get("star_score", 0)),
            "quantify": int(match.get("quant_score", 0)),
            "keyword": int(match.get("keyword_score", 0)),
        }
    quality = st.session_state.get("workshop_quality_data")
    if isinstance(quality, dict) and quality.get("overall_score") is not None:
        return {
            "overall": float(quality.get("overall_score", 0)),
            "star": int(quality.get("star_score", 0)),
            "quantify": int(quality.get("quant_score", 0)),
            "keyword": int(quality.get("expression_score", 0)),
        }
    return None


def _score_resume_with_scorer(resume_text: str, *, show_thinking: bool = True) -> dict[str, float | int]:
    """评分；默认带思考链（仅首次加载）。优化后刷新应走增量估算。"""
    from engines.resume_quality_scorer import ResumeQualityScorer

    def _evaluate_only() -> dict[str, float | int]:
        result = ResumeQualityScorer().evaluate(resume_text)
        d = result.model_dump()
        match = st.session_state.get("workshop_match_data")
        if isinstance(match, dict) and match.get("keyword_score") is not None:
            return {
                "overall": float(match.get("overall_score", d["overall_score"])),
                "star": int(match.get("star_score", d["star_score"])),
                "quantify": int(match.get("quant_score", d["quant_score"])),
                "keyword": int(match.get("keyword_score", 0)),
            }
        return {
            "overall": float(d["overall_score"]),
            "star": int(d["star_score"]),
            "quantify": int(d["quant_score"]),
            "keyword": int(d.get("expression_score", 0)),
        }

    if not show_thinking:
        return _evaluate_only()

    from agents.gold_detector.analyzer import resume_analyzer
    from components.thinking_chain import RESUME_ANALYSIS_STEPS

    def _work():
        analysis = resume_analyzer.analyze(resume_text)
        result = ResumeQualityScorer().evaluate(analysis.raw_content)
        d = result.model_dump()
        match = st.session_state.get("workshop_match_data")
        if isinstance(match, dict) and match.get("keyword_score") is not None:
            return {
                "overall": float(match.get("overall_score", d["overall_score"])),
                "star": int(match.get("star_score", d["star_score"])),
                "quantify": int(match.get("quant_score", d["quant_score"])),
                "keyword": int(match.get("keyword_score", 0)),
            }
        return {
            "overall": float(d["overall_score"]),
            "star": int(d["star_score"]),
            "quantify": int(d["quant_score"]),
            "keyword": int(d.get("expression_score", 0)),
        }

    return run_with_thinking_chain(
        RESUME_ANALYSIS_STEPS,
        _work,
        model_name="DeepSeek V3 · 分析推理",
    )


def _apply_adopt_score_delta(section_key: str) -> None:
    """采纳 AI 优化后即时更新图表分数，不触发整份简历重评。"""
    from components.workshop_score_delta import apply_optimization_delta

    before = st.session_state.get("workshop_before_scores")
    if not before:
        return

    base = dict(st.session_state.get("workshop_after_scores") or before)
    types = (st.session_state.get("workshop_optimize_types") or {}).get(section_key, [])
    changes = (st.session_state.get("workshop_changes") or {}).get(section_key, [])
    updated = apply_optimization_delta(base, optimize_types=types, changes=changes)

    st.session_state.workshop_after_scores = updated
    st.session_state.workshop_after_fp = _merged_resume_fingerprint()


def _ensure_before_scores() -> None:
    """首次加载时存储优化前分数，只存一次。"""
    if st.session_state.get("workshop_before_scores"):
        return
    cached = _extract_scores_from_session()
    if cached:
        st.session_state.workshop_before_scores = cached
        return
    resume = (st.session_state.get("workshop_resume_text") or "").strip()
    if not resume:
        return
    st.session_state.workshop_before_scores = _score_resume_with_scorer(resume)


def _has_adopted_optimization() -> bool:
    adopted = st.session_state.get("workshop_adopted") or {}
    return any(v == "optimized" for v in adopted.values())


def _merged_resume_fingerprint() -> str:
    return str(hash(_build_final_sections().__repr__()))


def _ensure_after_scores() -> dict[str, float | int] | None:
    if not _has_adopted_optimization():
        return None
    fp = _merged_resume_fingerprint()
    cached = st.session_state.get("workshop_after_scores")
    if st.session_state.get("workshop_after_fp") == fp and cached:
        return cached
    before = st.session_state.get("workshop_before_scores")
    if before and cached:
        st.session_state.workshop_after_fp = fp
        return cached
    if before:
        st.session_state.workshop_after_scores = dict(before)
        st.session_state.workshop_after_fp = fp
        return st.session_state.workshop_after_scores
    return None


def _render_optimization_report_if_ready() -> None:
    before = st.session_state.get("workshop_before_scores")
    if not before or not _has_adopted_optimization():
        return
    after = _ensure_after_scores()
    if after:
        render_optimization_report(before, after)


def _ensure_sections_parsed() -> None:
    if st.session_state.get("workshop_sections_parsed"):
        _post_parse_normalize()
        return

    resume_text = (st.session_state.get("workshop_resume_text") or "").strip()
    if not resume_text:
        st.session_state.workshop_sections = {key: "" for key in SECTION_KEYS}
        st.session_state.workshop_sections_parsed = True
        return

    fast_entry = bool(st.session_state.pop("workshop_fast_entry", False))
    if fast_entry or _extract_scores_from_session() is not None:
        from engines.resume_parser import ResumeParser, sections_look_monolithic

        try:
            parsed = ResumeParser().parse_fast(resume_text)
            sections = parsed.sections
            if sections_look_monolithic(sections):
                logger.info("[gold_workshop] fast parse monolithic, falling back to AI parse")
                parsed = ResumeParser().parse(resume_text)
                sections = parsed.sections
            st.session_state.workshop_sections = sections
        except Exception as exc:
            logger.warning("[gold_workshop] fast parse failed: %s", exc)
            st.session_state.workshop_sections = {key: "" for key in SECTION_KEYS}
            st.session_state.workshop_sections["basic_info"] = resume_text
        st.session_state.workshop_sections_parsed = True
        _post_parse_normalize()
        return

    try:
        from engines.resume_parser import ResumeParser, sections_look_monolithic

        def _parse():
            return ResumeParser().parse(resume_text)

        parsed = run_with_thinking_chain(
            [
                {"title": "识别板块标题", "desc": "定位教育、经历、技能等分区"},
                {"title": "拆分板块内容", "desc": "将全文结构化到各板块"},
                {"title": "校验完整性", "desc": "确保关键板块不遗漏"},
            ],
            _parse,
            model_name="DeepSeek V3 · 分析推理",
        )
        sections = parsed.sections
        if sections_look_monolithic(sections):
            from engines.resume_parser import heuristic_split_resume

            logger.info("[gold_workshop] AI parse monolithic, applying heuristic split")
            sections = heuristic_split_resume(resume_text)
        st.session_state.workshop_sections = sections
    except Exception as exc:
        logger.warning("[gold_workshop] parse failed: %s", exc)
        st.session_state.workshop_sections = {key: "" for key in SECTION_KEYS}
        if resume_text:
            st.session_state.workshop_sections["basic_info"] = resume_text

    st.session_state.workshop_sections_parsed = True
    _post_parse_normalize()


def _post_parse_normalize() -> None:
    """解析后兜底：确保至少有一个板块有内容，并自动定位到首个非空板块。"""
    from engines.resume_parser import heuristic_split_resume, sections_look_monolithic

    sections = st.session_state.get("workshop_sections") or {}
    resume_text = (st.session_state.get("workshop_resume_text") or "").strip()

    if resume_text and sections_look_monolithic(sections):
        sections = heuristic_split_resume(resume_text)
        st.session_state.workshop_sections = sections

    if not any(str(v).strip() for v in sections.values()) and resume_text:
        sections = {key: "" for key in SECTION_KEYS}
        sections["basic_info"] = resume_text
        st.session_state.workshop_sections = sections

    current = st.session_state.get("workshop_current_section", "basic_info")
    if not str(sections.get(current, "")).strip():
        for key, _, _ in SECTION_ORDER:
            if str(sections.get(key, "")).strip():
                st.session_state.workshop_current_section = key
                break


def _section_char_count(section_key: str) -> int:
    return len(_get_section_content(section_key).strip())


def _non_empty_section_names() -> list[str]:
    names: list[str] = []
    for key, name, _ in SECTION_ORDER:
        if _section_char_count(key) > 0:
            names.append(name)
    return names


def _get_section_content(section_key: str) -> str:
    sections = st.session_state.get("workshop_sections") or {}
    return str(sections.get(section_key, "") or "")


def _set_section_content(section_key: str, content: str) -> None:
    if "workshop_sections" not in st.session_state:
        st.session_state.workshop_sections = {}
    st.session_state.workshop_sections[section_key] = content


def _is_section_done(section_key: str) -> bool:
    if section_key == "basic_info":
        return bool(st.session_state.get("workshop_basic_format_checked")) and not (
            st.session_state.get("workshop_basic_format_issues") or []
        )
    adopted = st.session_state.get("workshop_adopted") or {}
    status = adopted.get(section_key)
    return status in ("optimized", "manual")


def _nav_dot_class(section_key: str) -> str:
    current = st.session_state.get("workshop_current_section")
    if _is_section_done(section_key):
        return "ws-dot-done"
    if section_key == current:
        return "ws-dot-current"
    return "ws-dot-pending"


def _supports_ai_optimize(section_key: str, content: str) -> bool:
    if section_key == "basic_info":
        return False
    if not content.strip():
        return False
    return True


def _optimized_count() -> int:
    return sum(1 for key, _, _ in SECTION_ORDER if _is_section_done(key))


def _format_star_tags(text: str) -> str:
    escaped = html.escape(text)
    escaped = escaped.replace("【S】", '<span class="workshop-star-tag-S">【S】</span>')
    escaped = escaped.replace("【T】", '<span class="workshop-star-tag-T">【T】</span>')
    escaped = escaped.replace("【A】", '<span class="workshop-star-tag-A">【A】</span>')
    escaped = escaped.replace("【R】", '<span class="workshop-star-tag-R">【R】</span>')
    return escaped.replace("\n", "<br>")


def render_optimized_content(content: str) -> str:
    """渲染优化版内容，⚠️标记转为醒目标签。"""
    escaped = _format_star_tags(content)
    escaped = re.sub(
        r"(\d+(?:\.\d+)?%?)⚠️",
        r'\1 <span class="ai-estimate-badge">需确认</span>',
        escaped,
    )
    return escaped


def compute_diff_lines(original: str, optimized: str) -> list[dict]:
    """按行对比，返回每行的状态。"""
    orig_lines = original.splitlines()
    opt_lines = optimized.splitlines()
    matcher = difflib.SequenceMatcher(None, orig_lines, opt_lines)
    result: list[dict] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                result.append({"status": "unchanged", "content": orig_lines[i]})
        elif tag == "replace":
            for i in range(i1, i2):
                result.append({"status": "removed", "content": orig_lines[i]})
            for j in range(j1, j2):
                result.append({"status": "changed", "content": opt_lines[j]})
        elif tag == "insert":
            for j in range(j1, j2):
                result.append({"status": "added", "content": opt_lines[j]})
        elif tag == "delete":
            for i in range(i1, i2):
                result.append({"status": "removed", "content": orig_lines[i]})

    return result


def _render_original_diff_html(original: str, optimized: str) -> str:
    """左侧原文：删除/替换行红色淡出。"""
    orig_lines = original.splitlines()
    opt_lines = optimized.splitlines()
    matcher = difflib.SequenceMatcher(None, orig_lines, opt_lines)
    parts: list[str] = []

    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                parts.append(
                    f'<div class="ws-diff-line ws-diff-line--unchanged">{_format_star_tags(orig_lines[i])}</div>'
                )
        elif tag in ("replace", "delete"):
            for i in range(i1, i2):
                parts.append(
                    f'<div class="ws-diff-line ws-diff-line--removed">{html.escape(orig_lines[i])}</div>'
                )

    return "".join(parts) if parts else '<span class="workshop-empty-hint">（暂无内容）</span>'


def _render_optimized_diff_html(original: str, optimized: str) -> str:
    """右侧优化版：新增/修改行黄色高亮。"""
    orig_lines = original.splitlines()
    opt_lines = optimized.splitlines()
    matcher = difflib.SequenceMatcher(None, orig_lines, opt_lines)
    parts: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                parts.append(
                    f'<div class="ws-diff-line ws-diff-line--unchanged">{_format_star_tags(orig_lines[i])}</div>'
                )
        elif tag == "replace":
            for j in range(j1, j2):
                parts.append(
                    f'<div class="ws-diff-line ws-diff-line--changed">{render_optimized_content(opt_lines[j])}</div>'
                )
        elif tag == "insert":
            for j in range(j1, j2):
                parts.append(
                    f'<div class="ws-diff-line ws-diff-line--added">{render_optimized_content(opt_lines[j])}</div>'
                )

    return "".join(parts) if parts else '<span class="workshop-empty-hint">（暂无优化结果）</span>'


def _build_change_summary(changes: list[dict]) -> str:
    """从 changes 列表统计改动摘要。"""
    counter: Counter[str] = Counter()
    for change in changes:
        if isinstance(change, dict):
            change_type = str(change.get("type", "")).strip()
            if change_type:
                counter[change_type] += 1
    if not counter:
        return ""
    parts = [f"{count}处{change_type}" for change_type, count in counter.items()]
    return " · ".join(parts)


def _apply_estimate_confirmations(section_key: str, content: str) -> str:
    """将已确认的估算数据替换进正文。"""
    confirmed_map = st.session_state.get(f"{section_key}_estimates") or {}
    if not confirmed_map:
        return content

    result_parts: list[str] = []
    last = 0
    for idx, match in enumerate(re.finditer(r"(\d+(?:\.\d+)?%?)⚠️", content)):
        result_parts.append(content[last:match.start()])
        if idx in confirmed_map and str(confirmed_map[idx]).strip():
            result_parts.append(str(confirmed_map[idx]).strip())
        else:
            result_parts.append(match.group(0))
        last = match.end()
    result_parts.append(content[last:])
    return "".join(result_parts)


def _get_estimate_confirmations() -> dict[str, dict[int, str]]:
    """收集各板块已确认的估算数据。"""
    confirmations: dict[str, dict[int, str]] = {}
    for key, _, _ in SECTION_ORDER:
        estimates = st.session_state.get(f"{key}_estimates")
        if estimates:
            confirmations[key] = dict(estimates)
    return confirmations


def _get_unconfirmed_estimates(sections: dict[str, str]) -> list[str]:
    """获取未确认的估算数值列表。"""
    return _find_unconfirmed_estimates(sections, _get_estimate_confirmations())


def _render_estimate_confirmation(section_key: str, content: str) -> None:
    """渲染⚠️估算数据的确认区。"""
    estimates = re.findall(r"(\d+(?:\.\d+)?%?)⚠️", content)
    if not estimates:
        return

    st.markdown("#### 📋 确认AI估算数据")
    st.markdown(
        '<div style="color:#8C8279; font-size:12px; margin-bottom:8px;">'
        "以下数据由AI基于上下文估算，请确认或修改为实际数值"
        "</div>",
        unsafe_allow_html=True,
    )

    state_key = f"{section_key}_estimates"
    if state_key not in st.session_state:
        st.session_state[state_key] = {}

    for i, estimate in enumerate(estimates):
        col_label, col_input, col_check = st.columns([2, 2, 1])
        with col_label:
            st.markdown(f"📊 `{estimate}`（AI估算）")
        with col_input:
            default_val = st.session_state[state_key].get(i, estimate)
            new_val = st.text_input(
                "实际数值",
                value=str(default_val),
                key=f"est_{section_key}_{i}",
                label_visibility="collapsed",
                placeholder="输入实际数字",
            )
        with col_check:
            confirmed = st.checkbox("✓", key=f"est_confirm_{section_key}_{i}")
            if confirmed and new_val.strip():
                st.session_state[state_key][i] = new_val.strip()

    confirmed_map = st.session_state.get(state_key) or {}
    if len(confirmed_map) == len(estimates) and all(confirmed_map.get(i) for i in range(len(estimates))):
        st.success("✅ 所有估算数据已确认")


def _render_header() -> None:
    render_page_header("金子工坊", "在浏览器里逐段打磨简历，AI 优化结果左右对比，逐条采纳")


def _reset_workshop_content_state() -> None:
    """更换简历时重置解析与优化状态。"""
    st.session_state.workshop_sections = {}
    st.session_state.workshop_sections_parsed = False
    st.session_state.workshop_section_status = {}
    st.session_state.workshop_optimized = {}
    st.session_state.workshop_adopted = {}
    st.session_state.workshop_changes = {}
    st.session_state.workshop_optimize_types = {}
    st.session_state.workshop_manual_editing = None
    st.session_state.workshop_optimize_error = None
    st.session_state.workshop_current_section = "basic_info"
    st.session_state.workshop_basic_format_checked = False
    st.session_state.workshop_basic_format_issues = []
    st.session_state.workshop_basic_format_passes = []
    st.session_state.workshop_show_export_check = False
    st.session_state.workshop_pdf_bytes = None


def _render_resume_input_area() -> None:
    """与金子探测器一致的简历添加区：上传 PDF 自动填入，或手动粘贴。"""
    st.markdown('<div class="workshop-entry-box">', unsafe_allow_html=True)
    st.markdown(
        '<div class="workshop-entry-hint">'
        "上传 PDF 或粘贴简历全文，点击「添加简历并开始解析」后自动拆分为各板块。"
        "也可从金子探测器评分后一键带入。"
        "</div>",
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "上传简历（支持 PDF）",
        type=["pdf"],
        key="workshop_resume_upload",
    )
    if uploaded_file and st.session_state.get("workshop_upload_name") != uploaded_file.name:
        with st.spinner("正在解析 PDF…"):
            try:
                import pdfplumber

                pdf_bytes = io.BytesIO(uploaded_file.read())
                with pdfplumber.open(pdf_bytes) as pdf:
                    resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                st.session_state.workshop_upload_name = uploaded_file.name
                st.session_state.workshop_resume_input = resume_text
                st.session_state.workshop_resume_text = resume_text.strip()
            except ModuleNotFoundError:
                st.error("PDF 解析依赖未安装：请执行 `python -m pip install pdfplumber` 后重试。")
            except Exception as exc:
                st.error(f"PDF 解析失败：{exc}")

    resume = st.text_area(
        "简历内容",
        placeholder="把你的简历粘贴到这里，或上传 PDF 文件…",
        height=250,
        key="workshop_resume_input",
    )
    jd = st.text_area(
        "岗位描述（可选，填写后 AI 优化会嵌入 JD 关键词）",
        placeholder="把目标岗位的 JD 粘贴到这里…",
        height=120,
        key="workshop_jd_input",
    )

    col_add, col_clear = st.columns([1, 1])
    with col_add:
        if st.button("添加简历并开始解析", type="primary", use_container_width=True, key="workshop_start_parse"):
            if not resume.strip():
                st.warning("请先输入或上传简历")
            else:
                st.session_state.workshop_resume_text = resume.strip()
                st.session_state.workshop_jd_text = jd.strip()
                _reset_workshop_content_state()
                st.rerun()
    with col_clear:
        if st.button("清空", use_container_width=True, key="workshop_clear_resume"):
            st.session_state.workshop_resume_text = ""
            st.session_state.workshop_jd_text = ""
            st.session_state.workshop_upload_name = None
            st.session_state.workshop_resume_input = ""
            st.session_state.workshop_jd_input = ""
            _reset_workshop_content_state()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_empty_state() -> None:
    st.info("还没有简历内容。请添加简历，或从金子探测器完成评分后点击「进入金子工坊」。")
    _render_resume_input_area()


def _render_content_display(content: str) -> None:
    """用 HTML 展示板块正文（避免 text_area 的 key 缓存空值问题）。"""
    if not content.strip():
        return
    st.markdown(
        f'<pre class="ws-content-box">{html.escape(content)}</pre>',
        unsafe_allow_html=True,
    )


def _render_section_nav() -> None:
    current = st.session_state.get("workshop_current_section", "basic_info")
    st.markdown('<div class="ws-nav-shell">', unsafe_allow_html=True)
    st.markdown('<div class="ws-nav-title">板块导航</div>', unsafe_allow_html=True)

    for key, name, icon in _get_nav_section_order():
        label = f"{icon}  {name}"
        if st.button(
            label,
            key=f"ws_nav_{key}",
            use_container_width=True,
            type="primary" if key == current else "secondary",
        ):
            st.session_state.workshop_current_section = key
            st.session_state.workshop_manual_editing = None
            st.rerun()

    done = _optimized_count()
    total = len(SECTION_ORDER)
    pct = int(done / total * 100) if total else 0
    st.markdown(
        f"""
<div class="workshop-progress-label">── {done}/{total} ──</div>
<div class="workshop-progress-bar">
  <div class="workshop-progress-fill" style="width:{pct}%;"></div>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button("📄 导出PDF", key="nav_export", use_container_width=True):
        st.session_state.workshop_show_export_check = True
        st.session_state.workshop_pdf_bytes = None
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _check_anxiety_pace(section_key: str) -> None:
    """焦虑时提示先看当前板块，不硬阻断后续优化。"""
    adapter = _get_emotion_adapter()
    if not adapter.should_limit_optimization():
        return
    status_map = st.session_state.get("workshop_section_status") or {}
    optimizing = [k for k, v in status_map.items() if v == "optimizing"]
    if optimizing and section_key not in optimizing:
        st.warning("💙 先看完当前这个板块的优化建议，不急。采纳或保持原文后再优化下一个。")


def _run_optimize(section_key: str) -> None:
    section_name = SECTION_NAME_MAP.get(section_key, section_key)
    original = _get_section_content(section_key)
    jd = st.session_state.get("workshop_jd_text") or ""
    emotion = _emotion_from_score()

    status_map = st.session_state.get("workshop_section_status") or {}
    status_map[section_key] = "optimizing"
    st.session_state.workshop_section_status = status_map
    st.session_state.workshop_optimize_error = None

    steps = get_workshop_steps(section_key)
    result = run_with_thinking_chain(
        steps,
        lambda: ResumeOptimizer().optimize_section(
            section_name=section_name,
            original=original,
            jd=jd,
            emotion_state=emotion,
        ),
        model_name="DeepSeek V3 · 分析推理",
    )

    if not result.success:
        st.session_state.workshop_optimize_error = result.error_message
        status_map[section_key] = "original"
        st.session_state.workshop_section_status = status_map
        return

    st.session_state.workshop_optimized[section_key] = result.optimized_content
    st.session_state.workshop_changes[section_key] = result.changes
    st.session_state.workshop_optimize_types[section_key] = result.optimize_types
    status_map[section_key] = "optimizing"
    st.session_state.workshop_section_status = status_map
    st.session_state.workshop_optimize_error = None


def _render_compare_view(section_key: str, section_name: str, icon: str) -> None:
    original = _get_section_content(section_key)
    optimized = (st.session_state.get("workshop_optimized") or {}).get(section_key, "")
    changes = (st.session_state.get("workshop_changes") or {}).get(section_key, [])
    adapter = _get_emotion_adapter()
    layout = adapter.get_layout_mode()

    if layout == "guided":
        adapter.render_guided_steps(
            [
                "① 先看 AI 优化版的核心改动",
                "② 觉得好的点「采纳」，不喜欢的保持原文",
                "③ 一次只处理一个板块就好",
            ],
            title="跟着这三步走",
        )
    elif layout == "single_column":
        st.markdown(
            '<div class="step-guide" style="font-size:13px; color:#6B5B52; margin-bottom:12px;">'
            "💡 一次看一个板块就好，不急。点左侧板块名逐个查看。</div>",
            unsafe_allow_html=True,
        )

    summary = _build_change_summary(changes)
    if summary and layout != "single_column":
        st.markdown(
            f'<div class="ws-diff-summary">本次优化：{html.escape(summary)}</div>',
            unsafe_allow_html=True,
        )

    if layout == "praise_first" and changes:
        st.markdown("**🌱 先看看做得好的**")
        for change in changes[:3]:
            if not isinstance(change, dict):
                continue
            optimized_snip = str(change.get("optimized", "")).strip()
            if optimized_snip:
                st.markdown(f'<div class="highlight-done" style="padding:8px 12px; margin-bottom:6px;">'
                            f"✅ {html.escape(optimized_snip)}</div>", unsafe_allow_html=True)

    if layout == "single_column":
        body = _render_optimized_diff_html(original, optimized) if optimized else (
            '<span class="workshop-empty-hint">（暂无优化结果）</span>'
        )
        st.markdown(
            f"""
<div class="ws-diff-panel ws-diff-panel--ai breathe-card">
  <div class="ws-diff-panel-head">AI 优化建议</div>
  <div class="ws-diff-panel-body workshop-diff-optimized">{body}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if original.strip():
            with st.expander("查看原文（可选）"):
                _render_content_display(original)
    else:
        col_left, col_right = st.columns(2, gap="medium")
        with col_left:
            body = _render_original_diff_html(original, optimized) if original else (
                '<span class="workshop-empty-hint">（暂无内容）</span>'
            )
            st.markdown(
                f"""
<div class="ws-diff-panel ws-diff-panel--original">
  <div class="ws-diff-panel-head">原文</div>
  <div class="ws-diff-panel-body workshop-diff-original">{body}</div>
</div>
""",
                unsafe_allow_html=True,
            )
        with col_right:
            body = _render_optimized_diff_html(original, optimized) if optimized else (
                '<span class="workshop-empty-hint">（暂无优化结果）</span>'
            )
            panel_class = "ws-diff-panel ws-diff-panel--ai"
            if layout == "praise_first":
                panel_class += " highlight-done"
            st.markdown(
                f"""
<div class="{panel_class}">
  <div class="ws-diff-panel-head">AI 优化版</div>
  <div class="ws-diff-panel-body workshop-diff-optimized">{body}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    if optimized:
        _render_estimate_confirmation(section_key, optimized)

    if changes:
        with st.expander("📋 查看每条改动详情"):
            type_icons = {
                "STAR补全": "🟡",
                "量化改写": "🟠",
                "关键词嵌入": "🔵",
                "去口语化": "🟢",
                "逻辑重组": "🟣",
            }
            for change in changes:
                if not isinstance(change, dict):
                    continue
                col_type, col_detail = st.columns([1, 3])
                change_type = str(change.get("type", ""))
                icon_mark = type_icons.get(change_type, "⚪")
                with col_type:
                    st.markdown(f"{icon_mark} **{change_type}**")
                with col_detail:
                    original_snip = str(change.get("original", ""))
                    optimized_snip = str(change.get("optimized", ""))
                    st.markdown(f"~~{original_snip}~~")
                    st.markdown(f"→ **{optimized_snip}**")
                    reason = str(change.get("reason", "")).strip()
                    if reason:
                        st.caption(reason)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("✅ 采纳 AI 优化", key=f"workshop_adopt_{section_key}", use_container_width=True):
            _set_section_content(section_key, optimized)
            adopted = st.session_state.get("workshop_adopted") or {}
            already_optimized = adopted.get(section_key) == "optimized"
            adopted[section_key] = "optimized"
            st.session_state.workshop_adopted = adopted
            status = st.session_state.get("workshop_section_status") or {}
            status[section_key] = "optimized"
            st.session_state.workshop_section_status = status
            st.session_state.workshop_manual_editing = None
            if not already_optimized:
                _apply_adopt_score_delta(section_key)
            st.success(f"{section_name} 已采纳 AI 优化")
            st.rerun()
    with col_b:
        if st.button("✏️ 手动编辑", key=f"workshop_manual_{section_key}", use_container_width=True):
            st.session_state.workshop_manual_editing = section_key
            st.rerun()
    with col_c:
        if st.button("❌ 保持原文", key=f"workshop_reject_{section_key}", use_container_width=True):
            adopted = st.session_state.get("workshop_adopted") or {}
            adopted[section_key] = "original"
            st.session_state.workshop_adopted = adopted
            status = st.session_state.get("workshop_section_status") or {}
            status[section_key] = "original"
            st.session_state.workshop_section_status = status
            st.session_state.workshop_manual_editing = None
            st.rerun()


def _render_manual_edit(section_key: str, section_name: str, icon: str) -> None:
    current = _get_section_content(section_key)
    optimized = (st.session_state.get("workshop_optimized") or {}).get(section_key, "")
    default = optimized or current

    st.markdown(
        f'<div class="workshop-editor-title">{icon} {html.escape(section_name)} · 手动编辑</div>',
        unsafe_allow_html=True,
    )
    edited = st.text_area(
        "编辑内容",
        value=default,
        height=280,
        key=f"workshop_manual_area_{section_key}",
        label_visibility="collapsed",
    )
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("保存修改", type="primary", key=f"workshop_save_manual_{section_key}", use_container_width=True):
            _set_section_content(section_key, edited.strip())
            adopted = st.session_state.get("workshop_adopted") or {}
            adopted[section_key] = "manual"
            st.session_state.workshop_adopted = adopted
            status = st.session_state.get("workshop_section_status") or {}
            status[section_key] = "original"
            st.session_state.workshop_section_status = status
            st.session_state.workshop_manual_editing = None
            if section_key == "basic_info":
                st.session_state.workshop_basic_format_checked = False
            st.success("已保存手动修改")
            st.rerun()
    with col_cancel:
        if st.button("取消", key=f"workshop_cancel_manual_{section_key}", use_container_width=True):
            st.session_state.workshop_manual_editing = None
            st.rerun()


def _render_empty_section_guide(section_key: str) -> None:
    guide = EMPTY_SECTION_GUIDES.get(section_key)
    if not guide:
        return
    st.markdown(
        f"""
<div class="ws-empty-guide">
  <div class="ws-empty-guide-title">{html.escape(guide["title"])}</div>
  <div class="ws-empty-guide-body">{html.escape(guide["body"])}</div>
  <div class="ws-empty-guide-hint">{html.escape(guide["hint"])}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button(guide["btn"], key=f"workshop_add_{section_key}", type="primary"):
        st.session_state.workshop_manual_editing = section_key
        st.rerun()


def _render_basic_info_format_results() -> None:
    issues = st.session_state.get("workshop_basic_format_issues") or []
    passes = st.session_state.get("workshop_basic_format_passes") or []
    st.markdown('<div class="ws-format-result">', unsafe_allow_html=True)
    st.markdown('<div class="ws-format-result-title">格式检查结果</div>', unsafe_allow_html=True)
    for item in passes:
        st.markdown(
            f'<div class="ws-format-line ws-format-line--pass">✅ {html.escape(item.get("message", ""))}</div>',
            unsafe_allow_html=True,
        )
    for item in issues:
        status = item.get("status", "warning")
        icon_mark = "❌" if status == "error" else "⚠️"
        line_class = "ws-format-line--error" if status == "error" else "ws-format-line--warn"
        st.markdown(
            f'<div class="ws-format-line {line_class}">{icon_mark} {html.escape(item.get("message", ""))}</div>',
            unsafe_allow_html=True,
        )
    if not issues:
        st.markdown(
            '<div class="ws-format-line ws-format-line--pass">✅ 基本信息无问题，不需要优化</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    st.info(f"💡 {format_check_summary(issues, passes)}")


def _render_original_view(section_key: str, section_name: str, icon: str, content: str) -> None:
    if not content.strip() and section_key in EMPTY_SECTION_GUIDES:
        _render_empty_section_guide(section_key)
        return

    if content.strip():
        _render_content_display(content)
    else:
        others = [n for k, n, _ in SECTION_ORDER if k != section_key and _section_char_count(k) > 0]
        if others:
            st.info(f"「{section_name}」暂无识别内容，请点左侧查看：{'、'.join(others)}。")
        else:
            st.warning("未能识别该板块内容，可点击「手动编辑」自行补充。")

    if section_key != "basic_info" and content.strip():
        if st.button("✏️ 手动编辑", key=f"workshop_edit_plain_{section_key}", use_container_width=False):
            st.session_state.workshop_manual_editing = section_key
            st.rerun()


def _render_adopted_view(section_key: str, section_name: str, icon: str, content: str) -> None:
    title_col, _ = st.columns([5, 1])
    with title_col:
        st.markdown(
            f'<div class="workshop-editor-title">{icon} {html.escape(section_name)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="workshop-meta-row">{len(content.strip())} 字</div>',
            unsafe_allow_html=True,
        )
    st.success("✅ 已优化")
    _render_content_display(content)
    if st.button("✏️ 手动编辑", key=f"workshop_edit_done_{section_key}"):
        st.session_state.workshop_manual_editing = section_key
        st.rerun()


def _render_editor() -> None:
    adapter = _get_emotion_adapter()
    layout = adapter.get_layout_mode()

    if layout == "guided" and st.session_state.get("workshop_section_status", {}).get(
        st.session_state.get("workshop_current_section"), "original"
    ) == "original":
        adapter.render_guided_steps(
            [
                "① 先看看你的简历整体评分（金子探测器）",
                "② 点开每个板块看看 AI 的建议",
                "③ 觉得好的点「采纳」，不喜欢的跳过就好",
            ],
        )

    pace_hint = adapter.get_pace_hint()
    if pace_hint:
        st.info(f"💙 {pace_hint}")

    jd_prompt = adapter.get_jd_prompt()
    if jd_prompt and not (st.session_state.get("workshop_jd_text") or "").strip():
        st.warning(jd_prompt)

    section_key = st.session_state.get("workshop_current_section", "basic_info")
    section_name = SECTION_NAME_MAP.get(section_key, section_key)
    icon = next((ic for k, _, ic in SECTION_ORDER if k == section_key), "📄")
    content = _get_section_content(section_key)

    error_msg = st.session_state.get("workshop_optimize_error")
    if error_msg:
        st.warning(error_msg)
        st.session_state.workshop_optimize_error = None

    jd = (st.session_state.get("workshop_jd_text") or "").strip()
    if jd:
        st.caption(f"📎 已关联 JD · {len(jd)} 字 · 情绪：{_emotion_from_score()}")

    status_map = st.session_state.get("workshop_section_status") or {}
    section_status = status_map.get(section_key, "original")
    manual_key = st.session_state.get("workshop_manual_editing")

    with st.container(border=True):
        if manual_key == section_key:
            _render_manual_edit(section_key, section_name, icon)
            return

        if section_status == "optimizing":
            st.markdown(
                f'<div class="workshop-editor-title">{icon} {html.escape(section_name)}'
                f'<span class="ws-compare-badge">AI 对比</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="workshop-meta-row">左侧为原文，右侧高亮为 AI 改动 · 确认后请选择采纳或保持原文</div>',
                unsafe_allow_html=True,
            )
            _render_compare_view(section_key, section_name, icon)
            return

        if section_status == "optimized" and _is_section_done(section_key) and section_key != "basic_info":
            _render_adopted_view(section_key, section_name, icon, content)
            return

        # 默认：原文 + 操作按钮
        if section_key == "basic_info":
            title_col, action_col = st.columns([5, 1])
            with title_col:
                st.markdown(
                    f'<div class="workshop-editor-title">{icon} {html.escape(section_name)}</div>',
                    unsafe_allow_html=True,
                )
                char_count = len(content.strip())
                st.markdown(
                    f'<div class="workshop-meta-row">{char_count} 字</div>' if char_count else '<div class="workshop-meta-row">暂无内容</div>',
                    unsafe_allow_html=True,
                )
            with action_col:
                if content.strip() and st.button(
                    "格式检查 🔍",
                    key="workshop_format_check",
                    use_container_width=True,
                    type="primary",
                ):
                    issues, passes = check_basic_info_format(content)
                    st.session_state.workshop_basic_format_issues = issues
                    st.session_state.workshop_basic_format_passes = passes
                    st.session_state.workshop_basic_format_checked = True
                    st.rerun()
            if content.strip():
                _render_content_display(content)
                if st.session_state.get("workshop_basic_format_checked"):
                    _render_basic_info_format_results()
                if st.button("✏️ 手动编辑", key="workshop_edit_basic_inline"):
                    st.session_state.workshop_manual_editing = section_key
                    st.rerun()
            else:
                st.warning("基本信息为空，请点击手动编辑补充。")
                if st.button("✏️ 手动编辑", key="workshop_edit_basic_empty"):
                    st.session_state.workshop_manual_editing = section_key
                    st.rerun()
        else:
            header_col, btn_col = st.columns([5, 1])
            with header_col:
                st.markdown(
                    f'<div class="workshop-editor-title">{icon} {html.escape(section_name)}</div>',
                    unsafe_allow_html=True,
                )
                char_count = len(content.strip())
                st.markdown(
                    f'<div class="workshop-meta-row">{char_count} 字</div>' if char_count else '<div class="workshop-meta-row">暂无内容</div>',
                    unsafe_allow_html=True,
                )
            with btn_col:
                if _supports_ai_optimize(section_key, content):
                    if st.button("AI 优化 ✨", key=f"workshop_optimize_{section_key}", use_container_width=True, type="primary"):
                        _check_anxiety_pace(section_key)
                        _run_optimize(section_key)
                        st.rerun()
            _render_original_view(section_key, section_name, icon, content)


def _build_raw_final_sections() -> dict[str, str]:
    """合并各板块最终内容（未应用估算确认）。"""
    sections = st.session_state.get("workshop_sections") or {}
    adopted_map = st.session_state.get("workshop_adopted") or {}
    optimized_map = st.session_state.get("workshop_optimized") or {}
    final: dict[str, str] = {}
    for key, _, _ in SECTION_ORDER:
        adopted = adopted_map.get(key, "original")
        if adopted == "optimized":
            final[key] = str(optimized_map.get(key, "") or sections.get(key, ""))
        else:
            final[key] = str(sections.get(key, "") or "")
    return final


def _build_final_sections() -> dict[str, str]:
    """合并各板块最终内容，并应用已确认的估算数据。"""
    final = _build_raw_final_sections()
    for key in final:
        final[key] = _apply_estimate_confirmations(key, final[key])
    return final


def _render_template_selector() -> str:
    """渲染 PDF 模板选择卡片，返回当前选中模板。"""
    selected = st.session_state.get("workshop_pdf_template", "classic")
    st.markdown("#### 📄 选择简历模板")

    templates = [
        ("classic", "📄", "经典商务", "国企 · 银行 · 体制内"),
        ("modern", "📋", "现代简约", "互联网 · 科技"),
        ("ats", "📝", "ATS友好", "系统筛选 · 纯文本"),
    ]
    cols = st.columns(3)
    for col, (tpl_id, emoji, title, desc) in zip(cols, templates):
        border = "2px solid #B8908A" if selected == tpl_id else "1px solid rgba(61,56,51,0.1)"
        with col:
            st.markdown(
                f"""
<div style="text-align:center; padding:12px; border-radius:10px;
            border:{border}; background:rgba(255,255,255,0.55);">
    <div style="font-size:24px;">{emoji}</div>
    <div style="font-weight:600; font-size:13px; margin-top:4px;">{title}</div>
    <div style="color:#8C8279; font-size:11px;">{desc}</div>
</div>
""",
                unsafe_allow_html=True,
            )
            if st.button("选择", key=f"tpl_{tpl_id}", use_container_width=True):
                st.session_state.workshop_pdf_template = tpl_id
                st.rerun()

    return st.session_state.get("workshop_pdf_template", "classic")


def _mark_resume_exported(template: str) -> None:
    """持久化导出标记，供求职进度看板检测。"""
    path = SessionManager.user_file_path("workshop", "exported.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "template": template,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _render_export_check() -> None:
    raw_sections = _build_raw_final_sections()
    sections = _build_final_sections()
    status_map = st.session_state.get("workshop_section_status") or {}
    confirmations = _get_estimate_confirmations()
    checks = pre_export_check(raw_sections, status_map, estimate_confirmations=confirmations)
    unconfirmed = _get_unconfirmed_estimates(raw_sections)

    st.markdown('<div class="ws-export-check">', unsafe_allow_html=True)
    st.markdown('<div class="ws-export-check-title">📋 导出前检查</div>', unsafe_allow_html=True)

    icon_map = {"pass": "✅", "warn": "⚠️", "info": "ℹ️"}
    for check in checks:
        icon = icon_map.get(str(check.get("status", "pass")), "✅")
        detail = check.get("detail") or ""
        detail_text = f" — {detail}" if detail else ""
        line_class = ""
        status = check.get("status")
        if status == "warn":
            line_class = " ws-export-check-line--warn"
        elif status == "info":
            line_class = " ws-export-check-line--info"
        st.markdown(
            f'<div class="ws-export-check-line{line_class}">'
            f'{icon} {html.escape(str(check.get("item", "")))}{html.escape(detail_text)}'
            f"</div>",
            unsafe_allow_html=True,
        )

    if unconfirmed:
        preview = ", ".join(unconfirmed[:3])
        suffix = "..." if len(unconfirmed) > 3 else ""
        st.warning(
            f"⚠️ AI估算数据确认 — 有{len(unconfirmed)}处AI估算数据未确认：{preview}{suffix}\n\n"
            "建议确认后再导出，未确认的数据在PDF中会显示虚线下划线标记。"
        )

    selected_template = _render_template_selector()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("仍然导出", type="primary", use_container_width=True, key="workshop_export_confirm"):
            with st.spinner("正在生成PDF..."):
                try:
                    pdf_bytes = PDFExporter().export(sections, template=selected_template)
                    st.session_state.workshop_pdf_bytes = pdf_bytes
                    st.session_state.workshop_show_export_check = False
                    _mark_resume_exported(selected_template)
                    st.success("PDF 已生成，请点击下方下载。")
                except Exception as exc:
                    logger.exception("[gold_workshop] PDF export failed: %s", exc)
                    st.error(f"PDF 生成失败：{exc}")
            st.rerun()
    with col2:
        if st.button("返回继续优化", use_container_width=True, key="workshop_export_cancel"):
            st.session_state.workshop_show_export_check = False
            st.session_state.workshop_pdf_bytes = None
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_export_footer() -> None:
    _render_optimization_report_if_ready()
    st.markdown('<div class="ws-export-footer">', unsafe_allow_html=True)
    col_spacer, col_export = st.columns([3, 1])
    with col_export:
        if st.button("📄 导出PDF", type="primary", use_container_width=True, key="workshop_export_pdf"):
            st.session_state.workshop_show_export_check = True
            st.session_state.workshop_pdf_bytes = None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    pdf_bytes = st.session_state.get("workshop_pdf_bytes")
    if pdf_bytes:
        file_name = f"简历_{datetime.now().strftime('%Y%m%d')}.pdf"
        st.download_button(
            label="⬇️ 下载PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            use_container_width=True,
            key="workshop_download_pdf",
        )


def render() -> None:
    track_module_enter("金子工坊")
    _inject_styles()
    _init_state()
    _consume_section_query()
    _render_header()
    apply_emotion_breath()

    resume_text = (st.session_state.get("workshop_resume_text") or "").strip()
    if not resume_text:
        _render_empty_state()
        return

    if st.session_state.get("workshop_fast_entry"):
        st.caption("已从金子探测器带入简历与评分，正在快速加载…")

    _ensure_sections_parsed()
    _ensure_before_scores()

    st.markdown('<div id="ws-root"></div>', unsafe_allow_html=True)
    col_nav, col_editor = st.columns([1, 4], gap="medium")
    with col_nav:
        _render_section_nav()
    with col_editor:
        _render_editor()
        _render_export_footer()

    if st.session_state.get("workshop_show_export_check"):
        _render_export_check()


if __name__ == "__main__":
    st.set_page_config(page_title="金子工坊", page_icon="🔨", layout="wide")
    render()
