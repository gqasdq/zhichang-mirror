"""閲戝瓙宸ュ潑 鈥?绠€鍘嗗湪绾跨紪杈戝櫒銆?""

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
    ("basic_info", "鍩烘湰淇℃伅", "馃搵"),
    ("objective", "姹傝亴鎰忓悜", "馃幆"),
    ("education", "鏁欒偛鑳屾櫙", "馃帗"),
    ("work_exp", "宸ヤ綔缁忓巻", "馃捈"),
    ("project_exp", "椤圭洰缁忓巻", "馃敡"),
    ("skills", "涓撲笟鎶€鑳?, "鈿?),
    ("self_eval", "鑷垜璇勪环", "馃挰"),
]

SECTION_OPTIMIZE_TYPES: dict[str, list[str]] = {
    "basic_info": ["鏍煎紡瑙勮寖"],
    "objective": ["鎺緸浼樺寲", "JD鍖归厤"],
    "education": ["鐩稿叧璇剧▼琛ュ厖"],
    "work_exp": ["STAR鏀瑰啓", "閲忓寲琛ュ厖", "鍏抽敭璇嶅祵鍏?, "鍘诲彛璇寲"],
    "project_exp": ["STAR鏀瑰啓", "閲忓寲琛ュ厖", "鎶€鏈爤绐佸嚭"],
    "skills": ["鍒嗙被鏁寸悊", "JD瀵规瘮琛ュ叏"],
    "self_eval": ["鍘荤┖璇濆璇?, "鏁版嵁鏀拺"],
}

SECTION_NAME_MAP = {key: name for key, name, _ in SECTION_ORDER}

EMPTY_SECTION_GUIDES: dict[str, dict[str, str]] = {
    "objective": {
        "title": "馃摥 褰撳墠绠€鍘嗕腑娌℃湁姹傝亴鎰忓悜銆?,
        "body": "姹傝亴鎰忓悜鑳藉府 HR 蹇€熷垽鏂綘鍜屽矖浣嶇殑鍖归厤搴︼紝寤鸿琛ュ厖銆?,
        "hint": "鏍煎紡鍙傝€冿細鎰忓悜宀椾綅锛歑XX | 鏈熸湜鍩庡競锛歑XX | 鍒板矖鏃堕棿锛歑XX",
        "btn": "鉁忥笍 娣诲姞姹傝亴鎰忓悜",
    },
    "self_eval": {
        "title": "馃摥 褰撳墠绠€鍘嗕腑娌℃湁鑷垜璇勪环銆?,
        "body": "绠€鐭湁鍔涚殑鑷垜璇勪环鍙互绐佸嚭浣犵殑鏍稿績浼樺娍锛堝彲閫夋澘鍧楋級銆?,
        "hint": "鏍煎紡鍙傝€冿細3 鍙ヨ瘽姒傛嫭鏍稿績鑳藉姏 + 涓庡矖浣嶇殑鍖归厤鐐?,
        "btn": "鉁忥笍 娣诲姞鑷垜璇勪环",
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

/* 鈹€鈹€ 閲戝瓙宸ュ潑瑙嗚绮句慨锛堜粎鏍峰紡锛屼笉鏀归€昏緫锛?鈹€鈹€ */
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
        "workshop_emotion_state": "骞崇ǔ",
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
    """浠庢儏缁€ユ晳绔欏悓姝ユ儏缁姸鎬侊紝璇讳笉鍒板垯淇濇寔骞崇ǔ銆?""
    raw = st.session_state.get("emotion_state")
    if raw:
        st.session_state.workshop_emotion_state = normalize_emotion_state(raw)
        return
    if not st.session_state.get("workshop_emotion_state"):
        st.session_state.workshop_emotion_state = EmotionAdapter.CALM


def _resolve_emotion_state() -> str:
    """瑙ｆ瀽褰撳墠搴斾娇鐢ㄧ殑鍥涚鎯呯华鐘舵€佷箣涓€銆?""
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
    """鎸触/杩疯尗鏃惰皟鏁村鑸『搴忥紝鍏朵綑淇濇寔榛樿銆?""
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
    """浠庨噾瀛愭帰娴嬪櫒浼犲叆鐨?match/quality 鏁版嵁鎻愬彇鍒嗘暟锛岄伩鍏嶉噸澶?AI 璋冪敤銆?""
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
    """璇勫垎锛涢粯璁ゅ甫鎬濊€冮摼锛堜粎棣栨鍔犺浇锛夈€備紭鍖栧悗鍒锋柊搴旇蛋澧為噺浼扮畻銆?""
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
        model_name="DeepSeek V3 路 鍒嗘瀽鎺ㄧ悊",
    )


def _apply_adopt_score_delta(section_key: str) -> None:
    """閲囩撼 AI 浼樺寲鍚庡嵆鏃舵洿鏂板浘琛ㄥ垎鏁帮紝涓嶈Е鍙戞暣浠界畝鍘嗛噸璇勩€?""
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
    """棣栨鍔犺浇鏃跺瓨鍌ㄤ紭鍖栧墠鍒嗘暟锛屽彧瀛樹竴娆°€?""
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
                {"title": "璇嗗埆鏉垮潡鏍囬", "desc": "瀹氫綅鏁欒偛銆佺粡鍘嗐€佹妧鑳界瓑鍒嗗尯"},
                {"title": "鎷嗗垎鏉垮潡鍐呭", "desc": "灏嗗叏鏂囩粨鏋勫寲鍒板悇鏉垮潡"},
                {"title": "鏍￠獙瀹屾暣鎬?, "desc": "纭繚鍏抽敭鏉垮潡涓嶉仐婕?},
            ],
            _parse,
            model_name="DeepSeek V3 路 鍒嗘瀽鎺ㄧ悊",
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
    """瑙ｆ瀽鍚庡厹搴曪細纭繚鑷冲皯鏈変竴涓澘鍧楁湁鍐呭锛屽苟鑷姩瀹氫綅鍒伴涓潪绌烘澘鍧椼€?""
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
    escaped = escaped.replace("銆怱銆?, '<span class="workshop-star-tag-S">銆怱銆?/span>')
    escaped = escaped.replace("銆怲銆?, '<span class="workshop-star-tag-T">銆怲銆?/span>')
    escaped = escaped.replace("銆怉銆?, '<span class="workshop-star-tag-A">銆怉銆?/span>')
    escaped = escaped.replace("銆怰銆?, '<span class="workshop-star-tag-R">銆怰銆?/span>')
    return escaped.replace("\n", "<br>")


def render_optimized_content(content: str) -> str:
    """娓叉煋浼樺寲鐗堝唴瀹癸紝鈿狅笍鏍囪杞负閱掔洰鏍囩銆?""
    escaped = _format_star_tags(content)
    escaped = re.sub(
        r"(\d+(?:\.\d+)?%?)鈿狅笍",
        r'\1 <span class="ai-estimate-badge">闇€纭</span>',
        escaped,
    )
    return escaped


def compute_diff_lines(original: str, optimized: str) -> list[dict]:
    """鎸夎瀵规瘮锛岃繑鍥炴瘡琛岀殑鐘舵€併€?""
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
    """宸︿晶鍘熸枃锛氬垹闄?鏇挎崲琛岀孩鑹叉贰鍑恒€?""
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

    return "".join(parts) if parts else '<span class="workshop-empty-hint">锛堟殏鏃犲唴瀹癸級</span>'


def _render_optimized_diff_html(original: str, optimized: str) -> str:
    """鍙充晶浼樺寲鐗堬細鏂板/淇敼琛岄粍鑹查珮浜€?""
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

    return "".join(parts) if parts else '<span class="workshop-empty-hint">锛堟殏鏃犱紭鍖栫粨鏋滐級</span>'


def _build_change_summary(changes: list[dict]) -> str:
    """浠?changes 鍒楄〃缁熻鏀瑰姩鎽樿銆?""
    counter: Counter[str] = Counter()
    for change in changes:
        if isinstance(change, dict):
            change_type = str(change.get("type", "")).strip()
            if change_type:
                counter[change_type] += 1
    if not counter:
        return ""
    parts = [f"{count}澶剓change_type}" for change_type, count in counter.items()]
    return " 路 ".join(parts)


def _apply_estimate_confirmations(section_key: str, content: str) -> str:
    """灏嗗凡纭鐨勪及绠楁暟鎹浛鎹㈣繘姝ｆ枃銆?""
    confirmed_map = st.session_state.get(f"{section_key}_estimates") or {}
    if not confirmed_map:
        return content

    result_parts: list[str] = []
    last = 0
    for idx, match in enumerate(re.finditer(r"(\d+(?:\.\d+)?%?)鈿狅笍", content)):
        result_parts.append(content[last:match.start()])
        if idx in confirmed_map and str(confirmed_map[idx]).strip():
            result_parts.append(str(confirmed_map[idx]).strip())
        else:
            result_parts.append(match.group(0))
        last = match.end()
    result_parts.append(content[last:])
    return "".join(result_parts)


def _get_estimate_confirmations() -> dict[str, dict[int, str]]:
    """鏀堕泦鍚勬澘鍧楀凡纭鐨勪及绠楁暟鎹€?""
    confirmations: dict[str, dict[int, str]] = {}
    for key, _, _ in SECTION_ORDER:
        estimates = st.session_state.get(f"{key}_estimates")
        if estimates:
            confirmations[key] = dict(estimates)
    return confirmations


def _get_unconfirmed_estimates(sections: dict[str, str]) -> list[str]:
    """鑾峰彇鏈‘璁ょ殑浼扮畻鏁板€煎垪琛ㄣ€?""
    return _find_unconfirmed_estimates(sections, _get_estimate_confirmations())


def _render_estimate_confirmation(section_key: str, content: str) -> None:
    """娓叉煋鈿狅笍浼扮畻鏁版嵁鐨勭‘璁ゅ尯銆?""
    estimates = re.findall(r"(\d+(?:\.\d+)?%?)鈿狅笍", content)
    if not estimates:
        return

    st.markdown("#### 馃搵 纭AI浼扮畻鏁版嵁")
    st.markdown(
        '<div style="color:#8C8279; font-size:12px; margin-bottom:8px;">'
        "浠ヤ笅鏁版嵁鐢盇I鍩轰簬涓婁笅鏂囦及绠楋紝璇风‘璁ゆ垨淇敼涓哄疄闄呮暟鍊?
        "</div>",
        unsafe_allow_html=True,
    )

    state_key = f"{section_key}_estimates"
    if state_key not in st.session_state:
        st.session_state[state_key] = {}

    for i, estimate in enumerate(estimates):
        col_label, col_input, col_check = st.columns([2, 2, 1])
        with col_label:
            st.markdown(f"馃搳 `{estimate}`锛圓I浼扮畻锛?)
        with col_input:
            default_val = st.session_state[state_key].get(i, estimate)
            new_val = st.text_input(
                "瀹為檯鏁板€?,
                value=str(default_val),
                key=f"est_{section_key}_{i}",
                label_visibility="collapsed",
                placeholder="杈撳叆瀹為檯鏁板瓧",
            )
        with col_check:
            confirmed = st.checkbox("鉁?, key=f"est_confirm_{section_key}_{i}")
            if confirmed and new_val.strip():
                st.session_state[state_key][i] = new_val.strip()

    confirmed_map = st.session_state.get(state_key) or {}
    if len(confirmed_map) == len(estimates) and all(confirmed_map.get(i) for i in range(len(estimates))):
        st.success("鉁?鎵€鏈変及绠楁暟鎹凡纭")


def _render_header() -> None:
    render_page_header("閲戝瓙宸ュ潑", "鍦ㄦ祻瑙堝櫒閲岄€愭鎵撶（绠€鍘嗭紝AI 浼樺寲缁撴灉宸﹀彸瀵规瘮锛岄€愭潯閲囩撼")


def _reset_workshop_content_state() -> None:
    """鏇存崲绠€鍘嗘椂閲嶇疆瑙ｆ瀽涓庝紭鍖栫姸鎬併€?""
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
    """涓庨噾瀛愭帰娴嬪櫒涓€鑷寸殑绠€鍘嗘坊鍔犲尯锛氫笂浼?PDF 鑷姩濉叆锛屾垨鎵嬪姩绮樿创銆?""
    st.markdown('<div class="workshop-entry-box">', unsafe_allow_html=True)
    st.markdown(
        '<div class="workshop-entry-hint">'
        "涓婁紶 PDF 鎴栫矘璐寸畝鍘嗗叏鏂囷紝鐐瑰嚮銆屾坊鍔犵畝鍘嗗苟寮€濮嬭В鏋愩€嶅悗鑷姩鎷嗗垎涓哄悇鏉垮潡銆?
        "涔熷彲浠庨噾瀛愭帰娴嬪櫒璇勫垎鍚庝竴閿甫鍏ャ€?
        "</div>",
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "涓婁紶绠€鍘嗭紙鏀寔 PDF锛?,
        type=["pdf"],
        key="workshop_resume_upload",
    )
    if uploaded_file and st.session_state.get("workshop_upload_name") != uploaded_file.name:
        with st.spinner("姝ｅ湪瑙ｆ瀽 PDF鈥?):
            try:
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
                import pdfplumber

                pdf_bytes = io.BytesIO(uploaded_file.read())
                with pdfplumber.open(pdf_bytes) as pdf:
                    resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                st.session_state.workshop_upload_name = uploaded_file.name
                st.session_state.workshop_resume_input = resume_text
                st.session_state.workshop_resume_text = resume_text.strip()
            except ModuleNotFoundError:
                st.error("PDF 瑙ｆ瀽渚濊禆鏈畨瑁咃細璇锋墽琛?`python -m pip install pdfplumber` 鍚庨噸璇曘€?)
            except Exception as exc:
                st.error(f"PDF 瑙ｆ瀽澶辫触锛歿exc}")

    resume = st.text_area(
        "绠€鍘嗗唴瀹?,
        placeholder="鎶婁綘鐨勭畝鍘嗙矘璐村埌杩欓噷锛屾垨涓婁紶 PDF 鏂囦欢鈥?,
        height=250,
        key="workshop_resume_input",
    )
    jd = st.text_area(
        "宀椾綅鎻忚堪锛堝彲閫夛紝濉啓鍚?AI 浼樺寲浼氬祵鍏?JD 鍏抽敭璇嶏級",
        placeholder="鎶婄洰鏍囧矖浣嶇殑 JD 绮樿创鍒拌繖閲屸€?,
        height=120,
        key="workshop_jd_input",
    )

    col_add, col_clear = st.columns([1, 1])
    with col_add:
        if st.button("娣诲姞绠€鍘嗗苟寮€濮嬭В鏋?, type="primary", use_container_width=True, key="workshop_start_parse"):
            if not resume.strip():
                st.warning("璇峰厛杈撳叆鎴栦笂浼犵畝鍘?)
            else:
                st.session_state.workshop_resume_text = resume.strip()
                st.session_state.workshop_jd_text = jd.strip()
                _reset_workshop_content_state()
                st.rerun()
    with col_clear:
        if st.button("娓呯┖", use_container_width=True, key="workshop_clear_resume"):
            st.session_state.workshop_resume_text = ""
            st.session_state.workshop_jd_text = ""
            st.session_state.workshop_upload_name = None
            st.session_state.workshop_resume_input = ""
            st.session_state.workshop_jd_input = ""
            _reset_workshop_content_state()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_empty_state() -> None:
    st.info("杩樻病鏈夌畝鍘嗗唴瀹广€傝娣诲姞绠€鍘嗭紝鎴栦粠閲戝瓙鎺㈡祴鍣ㄥ畬鎴愯瘎鍒嗗悗鐐瑰嚮銆岃繘鍏ラ噾瀛愬伐鍧娿€嶃€?)
    _render_resume_input_area()


def _render_content_display(content: str) -> None:
    """鐢?HTML 灞曠ず鏉垮潡姝ｆ枃锛堥伩鍏?text_area 鐨?key 缂撳瓨绌哄€奸棶棰橈級銆?""
    if not content.strip():
        return
    st.markdown(
        f'<pre class="ws-content-box">{html.escape(content)}</pre>',
        unsafe_allow_html=True,
    )


def _render_section_nav() -> None:
    current = st.session_state.get("workshop_current_section", "basic_info")
    st.markdown('<div class="ws-nav-shell">', unsafe_allow_html=True)
    st.markdown('<div class="ws-nav-title">鏉垮潡瀵艰埅</div>', unsafe_allow_html=True)

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
<div class="workshop-progress-label">鈹€鈹€ {done}/{total} 鈹€鈹€</div>
<div class="workshop-progress-bar">
  <div class="workshop-progress-fill" style="width:{pct}%;"></div>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button("馃搫 瀵煎嚭PDF", key="nav_export", use_container_width=True):
        st.session_state.workshop_show_export_check = True
        st.session_state.workshop_pdf_bytes = None
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _check_anxiety_pace(section_key: str) -> None:
    """鐒﹁檻鏃舵彁绀哄厛鐪嬪綋鍓嶆澘鍧楋紝涓嶇‖闃绘柇鍚庣画浼樺寲銆?""
    adapter = _get_emotion_adapter()
    if not adapter.should_limit_optimization():
        return
    status_map = st.session_state.get("workshop_section_status") or {}
    optimizing = [k for k, v in status_map.items() if v == "optimizing"]
    if optimizing and section_key not in optimizing:
        st.warning("馃挋 鍏堢湅瀹屽綋鍓嶈繖涓澘鍧楃殑浼樺寲寤鸿锛屼笉鎬ャ€傞噰绾虫垨淇濇寔鍘熸枃鍚庡啀浼樺寲涓嬩竴涓€?)


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
        model_name="DeepSeek V3 路 鍒嗘瀽鎺ㄧ悊",
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
                "鈶?鍏堢湅 AI 浼樺寲鐗堢殑鏍稿績鏀瑰姩",
                "鈶?瑙夊緱濂界殑鐐广€岄噰绾炽€嶏紝涓嶅枩娆㈢殑淇濇寔鍘熸枃",
                "鈶?涓€娆″彧澶勭悊涓€涓澘鍧楀氨濂?,
            ],
            title="璺熺潃杩欎笁姝ヨ蛋",
        )
    elif layout == "single_column":
        st.markdown(
            '<div class="step-guide" style="font-size:13px; color:#6B5B52; margin-bottom:12px;">'
            "馃挕 涓€娆＄湅涓€涓澘鍧楀氨濂斤紝涓嶆€ャ€傜偣宸︿晶鏉垮潡鍚嶉€愪釜鏌ョ湅銆?/div>",
            unsafe_allow_html=True,
        )

    summary = _build_change_summary(changes)
    if summary and layout != "single_column":
        st.markdown(
            f'<div class="ws-diff-summary">鏈浼樺寲锛歿html.escape(summary)}</div>',
            unsafe_allow_html=True,
        )

    if layout == "praise_first" and changes:
        st.markdown("**馃尡 鍏堢湅鐪嬪仛寰楀ソ鐨?*")
        for change in changes[:3]:
            if not isinstance(change, dict):
                continue
            optimized_snip = str(change.get("optimized", "")).strip()
            if optimized_snip:
                st.markdown(f'<div class="highlight-done" style="padding:8px 12px; margin-bottom:6px;">'
                            f"鉁?{html.escape(optimized_snip)}</div>", unsafe_allow_html=True)

    if layout == "single_column":
        body = _render_optimized_diff_html(original, optimized) if optimized else (
            '<span class="workshop-empty-hint">锛堟殏鏃犱紭鍖栫粨鏋滐級</span>'
        )
        st.markdown(
            f"""
<div class="ws-diff-panel ws-diff-panel--ai breathe-card">
  <div class="ws-diff-panel-head">AI 浼樺寲寤鸿</div>
  <div class="ws-diff-panel-body workshop-diff-optimized">{body}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if original.strip():
            with st.expander("鏌ョ湅鍘熸枃锛堝彲閫夛級"):
                _render_content_display(original)
    else:
        col_left, col_right = st.columns(2, gap="medium")
        with col_left:
            body = _render_original_diff_html(original, optimized) if original else (
                '<span class="workshop-empty-hint">锛堟殏鏃犲唴瀹癸級</span>'
            )
            st.markdown(
                f"""
<div class="ws-diff-panel ws-diff-panel--original">
  <div class="ws-diff-panel-head">鍘熸枃</div>
  <div class="ws-diff-panel-body workshop-diff-original">{body}</div>
</div>
""",
                unsafe_allow_html=True,
            )
        with col_right:
            body = _render_optimized_diff_html(original, optimized) if optimized else (
                '<span class="workshop-empty-hint">锛堟殏鏃犱紭鍖栫粨鏋滐級</span>'
            )
            panel_class = "ws-diff-panel ws-diff-panel--ai"
            if layout == "praise_first":
                panel_class += " highlight-done"
            st.markdown(
                f"""
<div class="{panel_class}">
  <div class="ws-diff-panel-head">AI 浼樺寲鐗?/div>
  <div class="ws-diff-panel-body workshop-diff-optimized">{body}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    if optimized:
        _render_estimate_confirmation(section_key, optimized)

    if changes:
        with st.expander("馃搵 鏌ョ湅姣忔潯鏀瑰姩璇︽儏"):
            type_icons = {
                "STAR琛ュ叏": "馃煛",
                "閲忓寲鏀瑰啓": "馃煚",
                "鍏抽敭璇嶅祵鍏?: "馃數",
                "鍘诲彛璇寲": "馃煝",
                "閫昏緫閲嶇粍": "馃煟",
            }
            for change in changes:
                if not isinstance(change, dict):
                    continue
                col_type, col_detail = st.columns([1, 3])
                change_type = str(change.get("type", ""))
                icon_mark = type_icons.get(change_type, "鈿?)
                with col_type:
                    st.markdown(f"{icon_mark} **{change_type}**")
                with col_detail:
                    original_snip = str(change.get("original", ""))
                    optimized_snip = str(change.get("optimized", ""))
                    st.markdown(f"~~{original_snip}~~")
                    st.markdown(f"鈫?**{optimized_snip}**")
                    reason = str(change.get("reason", "")).strip()
                    if reason:
                        st.caption(reason)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("鉁?閲囩撼 AI 浼樺寲", key=f"workshop_adopt_{section_key}", use_container_width=True):
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
            st.success(f"{section_name} 宸查噰绾?AI 浼樺寲")
            st.rerun()
    with col_b:
        if st.button("鉁忥笍 鎵嬪姩缂栬緫", key=f"workshop_manual_{section_key}", use_container_width=True):
            st.session_state.workshop_manual_editing = section_key
            st.rerun()
    with col_c:
        if st.button("鉂?淇濇寔鍘熸枃", key=f"workshop_reject_{section_key}", use_container_width=True):
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
        f'<div class="workshop-editor-title">{icon} {html.escape(section_name)} 路 鎵嬪姩缂栬緫</div>',
        unsafe_allow_html=True,
    )
    edited = st.text_area(
        "缂栬緫鍐呭",
        value=default,
        height=280,
        key=f"workshop_manual_area_{section_key}",
        label_visibility="collapsed",
    )
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("淇濆瓨淇敼", type="primary", key=f"workshop_save_manual_{section_key}", use_container_width=True):
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
            st.success("宸蹭繚瀛樻墜鍔ㄤ慨鏀?)
            st.rerun()
    with col_cancel:
        if st.button("鍙栨秷", key=f"workshop_cancel_manual_{section_key}", use_container_width=True):
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
    st.markdown('<div class="ws-format-result-title">鏍煎紡妫€鏌ョ粨鏋?/div>', unsafe_allow_html=True)
    for item in passes:
        st.markdown(
            f'<div class="ws-format-line ws-format-line--pass">鉁?{html.escape(item.get("message", ""))}</div>',
            unsafe_allow_html=True,
        )
    for item in issues:
        status = item.get("status", "warning")
        icon_mark = "鉂? if status == "error" else "鈿狅笍"
        line_class = "ws-format-line--error" if status == "error" else "ws-format-line--warn"
        st.markdown(
            f'<div class="ws-format-line {line_class}">{icon_mark} {html.escape(item.get("message", ""))}</div>',
            unsafe_allow_html=True,
        )
    if not issues:
        st.markdown(
            '<div class="ws-format-line ws-format-line--pass">鉁?鍩烘湰淇℃伅鏃犻棶棰橈紝涓嶉渶瑕佷紭鍖?/div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    st.info(f"馃挕 {format_check_summary(issues, passes)}")


def _render_original_view(section_key: str, section_name: str, icon: str, content: str) -> None:
    if not content.strip() and section_key in EMPTY_SECTION_GUIDES:
        _render_empty_section_guide(section_key)
        return

    if content.strip():
        _render_content_display(content)
    else:
        others = [n for k, n, _ in SECTION_ORDER if k != section_key and _section_char_count(k) > 0]
        if others:
            st.info(f"銆寋section_name}銆嶆殏鏃犺瘑鍒唴瀹癸紝璇风偣宸︿晶鏌ョ湅锛歿'銆?.join(others)}銆?)
        else:
            st.warning("鏈兘璇嗗埆璇ユ澘鍧楀唴瀹癸紝鍙偣鍑汇€屾墜鍔ㄧ紪杈戙€嶈嚜琛岃ˉ鍏呫€?)

    if section_key != "basic_info" and content.strip():
        if st.button("鉁忥笍 鎵嬪姩缂栬緫", key=f"workshop_edit_plain_{section_key}", use_container_width=False):
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
            f'<div class="workshop-meta-row">{len(content.strip())} 瀛?/div>',
            unsafe_allow_html=True,
        )
    st.success("鉁?宸蹭紭鍖?)
    _render_content_display(content)
    if st.button("鉁忥笍 鎵嬪姩缂栬緫", key=f"workshop_edit_done_{section_key}"):
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
                "鈶?鍏堢湅鐪嬩綘鐨勭畝鍘嗘暣浣撹瘎鍒嗭紙閲戝瓙鎺㈡祴鍣級",
                "鈶?鐐瑰紑姣忎釜鏉垮潡鐪嬬湅 AI 鐨勫缓璁?,
                "鈶?瑙夊緱濂界殑鐐广€岄噰绾炽€嶏紝涓嶅枩娆㈢殑璺宠繃灏卞ソ",
            ],
        )

    pace_hint = adapter.get_pace_hint()
    if pace_hint:
        st.info(f"馃挋 {pace_hint}")

    jd_prompt = adapter.get_jd_prompt()
    if jd_prompt and not (st.session_state.get("workshop_jd_text") or "").strip():
        st.warning(jd_prompt)

    section_key = st.session_state.get("workshop_current_section", "basic_info")
    section_name = SECTION_NAME_MAP.get(section_key, section_key)
    icon = next((ic for k, _, ic in SECTION_ORDER if k == section_key), "馃搫")
    content = _get_section_content(section_key)

    error_msg = st.session_state.get("workshop_optimize_error")
    if error_msg:
        st.warning(error_msg)
        st.session_state.workshop_optimize_error = None

    jd = (st.session_state.get("workshop_jd_text") or "").strip()
    if jd:
        st.caption(f"馃搸 宸插叧鑱?JD 路 {len(jd)} 瀛?路 鎯呯华锛歿_emotion_from_score()}")

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
                f'<span class="ws-compare-badge">AI 瀵规瘮</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="workshop-meta-row">宸︿晶涓哄師鏂囷紝鍙充晶楂樹寒涓?AI 鏀瑰姩 路 纭鍚庤閫夋嫨閲囩撼鎴栦繚鎸佸師鏂?/div>',
                unsafe_allow_html=True,
            )
            _render_compare_view(section_key, section_name, icon)
            return

        if section_status == "optimized" and _is_section_done(section_key) and section_key != "basic_info":
            _render_adopted_view(section_key, section_name, icon, content)
            return

        # 榛樿锛氬師鏂?+ 鎿嶄綔鎸夐挳
        if section_key == "basic_info":
            title_col, action_col = st.columns([5, 1])
            with title_col:
                st.markdown(
                    f'<div class="workshop-editor-title">{icon} {html.escape(section_name)}</div>',
                    unsafe_allow_html=True,
                )
                char_count = len(content.strip())
                st.markdown(
                    f'<div class="workshop-meta-row">{char_count} 瀛?/div>' if char_count else '<div class="workshop-meta-row">鏆傛棤鍐呭</div>',
                    unsafe_allow_html=True,
                )
            with action_col:
                if content.strip() and st.button(
                    "鏍煎紡妫€鏌?馃攳",
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
                if st.button("鉁忥笍 鎵嬪姩缂栬緫", key="workshop_edit_basic_inline"):
                    st.session_state.workshop_manual_editing = section_key
                    st.rerun()
            else:
                st.warning("鍩烘湰淇℃伅涓虹┖锛岃鐐瑰嚮鎵嬪姩缂栬緫琛ュ厖銆?)
                if st.button("鉁忥笍 鎵嬪姩缂栬緫", key="workshop_edit_basic_empty"):
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
                    f'<div class="workshop-meta-row">{char_count} 瀛?/div>' if char_count else '<div class="workshop-meta-row">鏆傛棤鍐呭</div>',
                    unsafe_allow_html=True,
                )
            with btn_col:
                if _supports_ai_optimize(section_key, content):
                    if st.button("AI 浼樺寲 鉁?, key=f"workshop_optimize_{section_key}", use_container_width=True, type="primary"):
                        _check_anxiety_pace(section_key)
                        _run_optimize(section_key)
                        st.rerun()
            _render_original_view(section_key, section_name, icon, content)


def _build_raw_final_sections() -> dict[str, str]:
    """鍚堝苟鍚勬澘鍧楁渶缁堝唴瀹癸紙鏈簲鐢ㄤ及绠楃‘璁わ級銆?""
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
    """鍚堝苟鍚勬澘鍧楁渶缁堝唴瀹癸紝骞跺簲鐢ㄥ凡纭鐨勪及绠楁暟鎹€?""
    final = _build_raw_final_sections()
    for key in final:
        final[key] = _apply_estimate_confirmations(key, final[key])
    return final


def _render_template_selector() -> str:
    """娓叉煋 PDF 妯℃澘閫夋嫨鍗＄墖锛岃繑鍥炲綋鍓嶉€変腑妯℃澘銆?""
    selected = st.session_state.get("workshop_pdf_template", "classic")
    st.markdown("#### 馃搫 閫夋嫨绠€鍘嗘ā鏉?)

    templates = [
        ("classic", "馃搫", "缁忓吀鍟嗗姟", "鍥戒紒 路 閾惰 路 浣撳埗鍐?),
        ("modern", "馃搵", "鐜颁唬绠€绾?, "浜掕仈缃?路 绉戞妧"),
        ("ats", "馃摑", "ATS鍙嬪ソ", "绯荤粺绛涢€?路 绾枃鏈?),
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
            if st.button("閫夋嫨", key=f"tpl_{tpl_id}", use_container_width=True):
                st.session_state.workshop_pdf_template = tpl_id
                st.rerun()

    return st.session_state.get("workshop_pdf_template", "classic")


def _mark_resume_exported(template: str) -> None:
    """鎸佷箙鍖栧鍑烘爣璁帮紝渚涙眰鑱岃繘搴︾湅鏉挎娴嬨€?""
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
    st.markdown('<div class="ws-export-check-title">馃搵 瀵煎嚭鍓嶆鏌?/div>', unsafe_allow_html=True)

    icon_map = {"pass": "鉁?, "warn": "鈿狅笍", "info": "鈩癸笍"}
    for check in checks:
        icon = icon_map.get(str(check.get("status", "pass")), "鉁?)
        detail = check.get("detail") or ""
        detail_text = f" 鈥?{detail}" if detail else ""
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
            f"鈿狅笍 AI浼扮畻鏁版嵁纭 鈥?鏈墈len(unconfirmed)}澶凙I浼扮畻鏁版嵁鏈‘璁わ細{preview}{suffix}\n\n"
            "寤鸿纭鍚庡啀瀵煎嚭锛屾湭纭鐨勬暟鎹湪PDF涓細鏄剧ず铏氱嚎涓嬪垝绾挎爣璁般€?
        )

    selected_template = _render_template_selector()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("浠嶇劧瀵煎嚭", type="primary", use_container_width=True, key="workshop_export_confirm"):
            with st.spinner("姝ｅ湪鐢熸垚PDF..."):
                try:
                    pdf_bytes = PDFExporter().export(sections, template=selected_template)
                    st.session_state.workshop_pdf_bytes = pdf_bytes
                    st.session_state.workshop_show_export_check = False
                    _mark_resume_exported(selected_template)
                    st.success("PDF 宸茬敓鎴愶紝璇风偣鍑讳笅鏂逛笅杞姐€?)
                except Exception as exc:
                    logger.exception("[gold_workshop] PDF export failed: %s", exc)
                    st.error(f"PDF 鐢熸垚澶辫触锛歿exc}")
            st.rerun()
    with col2:
        if st.button("杩斿洖缁х画浼樺寲", use_container_width=True, key="workshop_export_cancel"):
            st.session_state.workshop_show_export_check = False
            st.session_state.workshop_pdf_bytes = None
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_export_footer() -> None:
    _render_optimization_report_if_ready()
    st.markdown('<div class="ws-export-footer">', unsafe_allow_html=True)
    col_spacer, col_export = st.columns([3, 1])
    with col_export:
        if st.button("馃搫 瀵煎嚭PDF", type="primary", use_container_width=True, key="workshop_export_pdf"):
            st.session_state.workshop_show_export_check = True
            st.session_state.workshop_pdf_bytes = None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    pdf_bytes = st.session_state.get("workshop_pdf_bytes")
    if pdf_bytes:
        file_name = f"绠€鍘哶{datetime.now().strftime('%Y%m%d')}.pdf"
        st.download_button(
            label="猬囷笍 涓嬭浇PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            use_container_width=True,
            key="workshop_download_pdf",
        )


def render() -> None:
    track_module_enter("閲戝瓙宸ュ潑")
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
        st.caption("宸蹭粠閲戝瓙鎺㈡祴鍣ㄥ甫鍏ョ畝鍘嗕笌璇勫垎锛屾鍦ㄥ揩閫熷姞杞解€?)

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
    st.set_page_config(page_title="閲戝瓙宸ュ潑", page_icon="馃敤", layout="wide")
    render()


