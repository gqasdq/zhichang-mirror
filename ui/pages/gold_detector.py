import io
import html
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)

from agents.gold_detector.analyzer import resume_analyzer
from agents.gold_detector.reporter import report_generator
from components.reframe_compare import extract_reframe_pairs, render_reframe_compare
from components.cognitive_bias_card import render_cognitive_bias_gate, render_severe_under_hint
from components.gold_report_view import (
    render_report_body,
    render_report_header,
    render_section_divider,
    render_strengths,
)
from components.smart_navigation import (
    get_gold_detector_nav_recommendations,
    render_smart_nav,
)
from components.thinking_chain import (
    JD_MATCH_STEPS,
    RESUME_ANALYSIS_STEPS,
    run_with_thinking_chain,
)
from components.job_recommend_card import render_job_recommendations
from components.radar_compare import render_radar_compare
from components.score_ring import render_quality_ring, render_score_ring
from components.tag_badge import render_quality_tags, render_tags
from engines.jd_matcher_v2 import JDMatcherV2
from engines.job_recommender import JobRecommendation, JobRecommendResult, JobRecommender
from engines.resume_quality_scorer import ResumeQualityScorer
from ui.design_system import render_page_header
from ui.emotion_theme import apply_emotion_breath
from utils.emotion_adapter import EmotionAdapter
from core.pdf_export import export_gold_report_pdf
from core.session_manager import SessionManager
from core.analytics import track_module_enter


# ===== 持久化存储 =====

def _probes_file() -> Path:
    return SessionManager.user_file_path("gold_probes.json")


def _load_probes() -> list[dict]:
    """从文件加载历史探测记录"""
    probes_file = _probes_file()
    if probes_file.exists():
        try:
            data = json.loads(probes_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_probes(probes: list[dict]) -> None:
    """保存历史探测记录到文件"""
    probes_file = _probes_file()
    probes_file.parent.mkdir(parents=True, exist_ok=True)
    probes_file.write_text(
        json.dumps(probes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ===== 样式 =====

def _inject_styles() -> None:
    st.markdown(
        """
<style>
/* 金子探测器 · 页面专属样式（全局样式见 ui/styles.py） */
[data-testid="stHorizontalBlock"] { gap: 0.75rem !important; align-items: flex-start !important; }
[data-testid="column"]:first-child { padding-left: 0 !important; }
[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child {
    flex: 1 1 0 !important;
    min-width: 0 !important;
}
[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child > div {
    width: 100% !important;
}
.block-container {
    max-width: 100% !important;
    width: 100% !important;
    padding-left: 12px !important;
    padding-right: 32px !important;
    padding-top: 6px !important;
}
[data-testid="stMainBlockContainer"] {
    padding-top: 6px !important;
}
.gold-report-shell,
.gold-report-shell ~ div,
div:has(> .gold-report-shell) {
    width: 100% !important;
    max-width: 100% !important;
}
h3 { margin-top: 0 !important; padding-top: 0 !important; }

/* 报告整体容器：撑满主内容列，不再锁 820px */
.gold-report-shell {
    width: 100%;
    max-width: none;
    margin: 0 0 24px;
    padding: 28px 36px 32px;
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid rgba(61, 56, 51, 0.07);
    border-radius: 16px;
    box-sizing: border-box;
}

/* 报告头部 */
.gold-report-header {
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(61, 56, 51, 0.08);
}
.gold-report-eyebrow {
    display: inline-block;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: #B8908A;
    margin-bottom: 6px;
}
.gold-report-title {
    font-size: 22px;
    font-weight: 650;
    color: #2C2420;
    line-height: 1.35;
    text-wrap: balance;
}
.gold-report-subtitle {
    margin-top: 6px;
    font-size: 14px;
    color: #6B5B52;
    line-height: 1.5;
}

/* 报告正文排版：撑满容器，行宽由 padding 控制而非 72ch 锁死 */
.gold-report-prose {
    width: 100%;
    max-width: none;
    color: #2C2420;
    font-size: 15px;
    line-height: 1.78;
    text-wrap: pretty;
}
.gold-prose-h2 {
    font-size: 17px;
    font-weight: 650;
    color: #2C2420;
    margin: 28px 0 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(184, 144, 138, 0.22);
    text-wrap: balance;
}
.gold-prose-h3 {
    font-size: 15px;
    font-weight: 600;
    color: #3D3530;
    margin: 20px 0 10px;
}
.gold-prose-p {
    margin: 0 0 14px;
    color: #2C2420;
}
.gold-prose-p:last-child { margin-bottom: 0; }
.gold-prose-divider {
    border: none;
    border-top: 1px solid rgba(61, 56, 51, 0.08);
    margin: 24px 0;
}
.gold-prose-ol, .gold-prose-ul {
    margin: 8px 0 16px;
    padding-left: 1.35em;
}
.gold-prose-li {
    margin-bottom: 8px;
    padding-left: 4px;
    color: #2C2420;
}
.gold-report-prose strong {
    color: #2C2420;
    font-weight: 650;
}
.gold-prose-empty {
    color: #6B5B52;
    font-style: italic;
}

/* 区块分隔 */
.gold-section-divider {
    margin: 28px 0 20px;
    border-top: 1px solid rgba(61, 56, 51, 0.08);
    padding-top: 4px;
}
.gold-section-divider-label {
    display: inline-block;
    margin-top: -13px;
    padding: 0 10px 0 0;
    background: rgba(255, 255, 255, 0.78);
    font-size: 12px;
    font-weight: 600;
    color: #8C8279;
    letter-spacing: 0.02em;
}
.gold-section-label {
    font-size: 15px;
    font-weight: 650;
    color: #2C2420;
    margin-bottom: 14px;
}

/* 核心优势 */
.gold-strengths-block {
    margin-top: 4px;
}
.gold-strength-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 12px;
}
.gold-strength-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 14px 16px;
    background: rgba(184, 144, 138, 0.06);
    border: 1px solid rgba(184, 144, 138, 0.14);
    border-radius: 10px;
}
.gold-strength-name {
    font-size: 14px;
    font-weight: 650;
    color: #2C2420;
}
.gold-strength-desc {
    font-size: 13px;
    line-height: 1.65;
    color: #5C4F47;
}

/* 评分报告区块 */
.jd-match-report {
    margin: 0;
    padding: 22px 0 0;
}
.jd-match-title {
    color: #2C2420;
    font-size: 16px;
    font-weight: 650;
    margin-bottom: 12px;
}
.jd-match-layout {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: flex-start;
}
.jd-match-ring {
    flex: 0 0 260px;
    max-width: 280px;
}
.jd-match-dims {
    flex: 1 1 280px;
    min-width: 240px;
}
.jd-dim-row {
    margin-bottom: 14px;
}
.jd-dim-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 6px;
    font-size: 13px;
    color: #2C2420;
}
.jd-dim-label { font-weight: 600; }
.jd-dim-meta { color: #8C8279; font-size: 12px; }
.jd-progress-track {
    height: 8px;
    background: rgba(61, 56, 51, 0.08);
    border-radius: 4px;
    overflow: hidden;
}
.jd-progress-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
}
.jd-fill-blue { background: #4A90D9; }
.jd-fill-green { background: #5DAE8B; }
.jd-fill-orange { background: #D4956A; }
.jd-smart-suggestion {
    margin-top: 16px;
    padding: 14px 16px;
    background: rgba(184, 144, 138, 0.08);
    border-radius: 10px;
    border: 1px solid rgba(184, 144, 138, 0.18);
    color: #2C2420;
    font-size: 14px;
    line-height: 1.65;
}
.jd-smart-suggestion strong { color: #9E6B64; }

/* 导出与操作区 */
.gold-export-block {
    margin-top: 28px;
    padding-top: 22px;
    border-top: 1px solid rgba(61, 56, 51, 0.08);
}
.gold-export-label {
    font-size: 13px;
    font-weight: 600;
    color: #6B5B52;
    margin-bottom: 12px;
}
.gold-privacy-note {
    margin-top: 12px;
    font-size: 12px;
    color: #8C8279;
}

/* 详细数据折叠面板 */
.gold-report-shell [data-testid="stExpander"] {
    margin-top: 20px;
    border: 1px solid rgba(61, 56, 51, 0.08) !important;
    border-radius: 10px !important;
    background: rgba(247, 243, 239, 0.5) !important;
}
.gold-report-shell [data-testid="stExpander"] summary {
    font-size: 13px !important;
    color: #6B5B52 !important;
}

.gold-score {
    color: #B8908A;
    font-size: 34px;
    line-height: 1.2;
    font-weight: 600;
    margin: 8px 0 14px;
}

/* 历史面板 - 左列 */
.gold-history-panel {
    min-height: 0;
    background: rgba(240, 235, 227, 0.5);
    border-radius: 10px;
    padding: 8px;
}
.gold-history-divider {
    border-top: 1px solid rgba(61,56,51,0.06);
    margin: 8px 0;
}

/* 历史面板按钮样式 - 让st.button看起来像对话列表项 */
section[data-testid="stSidebar"] button[kind="secondary"] { display: none !important; }

/* 左列历史面板里的按钮 */
.gold-history-panel button {
    text-align: left !important;
    justify-content: flex-start !important;
    font-size: 13px !important;
    padding: 6px 10px !important;
    border-radius: 8px !important;
    border: 1px solid rgba(61,56,51,0.06) !important;
    background: transparent !important;
    color: #6B5B52 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    margin-bottom: 4px !important;
    height: auto !important;
    min-height: 36px !important;
    line-height: 1.4 !important;
}
.gold-history-panel button:hover {
    background: rgba(184, 144, 138, 0.08) !important;
    border-color: rgba(184, 144, 138, 0.2) !important;
}

/* 追问分析师 */
.gold-followup-wrap {
    margin-top: 28px;
    padding: 22px 24px;
    background: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(61, 56, 51, 0.07);
    border-radius: 14px;
}
.gold-followup-title {
    color: #2C2420;
    font-size: 15px;
    font-weight: 650;
    margin-bottom: 14px;
}
[class^="st-key-gold_fq_"] button {
    background: rgba(184, 144, 138, 0.06) !important;
    color: #6B5B52 !important;
    border: 1px solid rgba(184, 144, 138, 0.35) !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    min-height: 38px !important;
}
[class^="st-key-gold_fq_"] button:hover {
    background: rgba(184, 144, 138, 0.14) !important;
    border-color: #B8908A !important;
}
.st-key-gold_followup_send button[kind="primary"] {
    background-color: #B8908A !important;
    border-color: #B8908A !important;
    color: #FFF !important;
}
.st-key-gold_followup_send button[kind="primary"]:hover {
    background-color: #A07A74 !important;
    border-color: #A07A74 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


# ===== 状态初始化 =====

def _init_state() -> None:
    if "gold_resume_text" not in st.session_state:
        st.session_state.gold_resume_text = ""
    if "gold_jd_text" not in st.session_state:
        st.session_state.gold_jd_text = ""
    if "gold_conversations" not in st.session_state:
        # 从持久化文件加载历史记录
        st.session_state.gold_conversations = _load_probes()
    if "gold_current_id" not in st.session_state:
        st.session_state.gold_current_id = None
    if "gold_current_conv_id" not in st.session_state:
        st.session_state.gold_current_conv_id = None
    if "gold_current_result" not in st.session_state:
        st.session_state.gold_current_result = None
    if "gold_show_input" not in st.session_state:
        st.session_state.gold_show_input = True
    if "gold_pending_probe" not in st.session_state:
        st.session_state.gold_pending_probe = None
    if "gold_probe_running" not in st.session_state:
        st.session_state.gold_probe_running = False
    if "gold_flash_message" not in st.session_state:
        st.session_state.gold_flash_message = None
    if "gold_flash_type" not in st.session_state:
        st.session_state.gold_flash_type = "info"
    if "gold_upload_name" not in st.session_state:
        st.session_state.gold_upload_name = None
    if "gold_resume_input" not in st.session_state:
        st.session_state.gold_resume_input = st.session_state.gold_resume_text
    if "gold_jd_input" not in st.session_state:
        st.session_state.gold_jd_input = st.session_state.gold_jd_text
    if "gold_jd_list" not in st.session_state:
        existing_jd = st.session_state.get("gold_jd_text") or st.session_state.get("gold_jd_input", "")
        st.session_state.gold_jd_list = [{"name": "岗位1", "content": existing_jd}]
    if "gold_followup_history" not in st.session_state:
        st.session_state.gold_followup_history = {}
    if "gold_followup_pending" not in st.session_state:
        st.session_state.gold_followup_pending = None


# ===== 报告解析 =====

def _parse_report_text(result: dict) -> str:
    raw_content = result.get("report", {}).get("raw_content", "")
    return parse_report(raw_content)


def parse_report(raw_content: str) -> str:
    """从reporter的raw_content中提取自然语言报告"""
    text = (raw_content or "").strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(text)
        if "natural_language_report" in parsed:
            return parsed["natural_language_report"]

        parts = []
        if "opening" in parsed:
            parts.append(parsed["opening"])
        if "your_golds" in parsed:
            for gold in parsed["your_golds"]:
                title = gold.get("title", "")
                desc = gold.get("description", "")
                why = gold.get("why_valuable", "")
                parts.append(f" **{title}** \n{desc}\n{why}")
        if "hidden_sparkles" in parsed:
            for sp in parsed["hidden_sparkles"]:
                title = sp.get("title", "")
                value = sp.get("real_value", "")
                parts.append(f" **{title}** \n{value}")
        if "gap_reframes" in parsed:
            for gap in parsed["gap_reframes"]:
                parts.append(f"差距：{gap.get('gap', '')}\n翻案：{gap.get('reframe', '')}")
        if "next_actions" in parsed:
            parts.append("**下一步行动**")
            for action in parsed["next_actions"]:
                parts.append(f"- {action.get('action', '')}：{action.get('how', '')}")
        if "closing" in parsed:
            parts.append(parsed["closing"])
        if parts:
            return "\n\n".join(parts)
    except json.JSONDecodeError:
        pass

    nl_match = re.search(r'"natural_language_report"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_content)
    if nl_match:
        return nl_match.group(1).replace("\\n", "\n").replace('\\"', '"')

    # 兜底：如果返回内容还是JSON开头就再剥一层
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if "natural_language_report" in parsed:
                return parsed["natural_language_report"]
        except json.JSONDecodeError:
            pass
    return raw_content


def _parse_match_score(result: dict):
    match_data = _parse_match_data(result)
    if match_data and match_data.get("overall_score") is not None:
        return int(round(float(match_data["overall_score"])))
    match_raw = result.get("match", {}).get("raw_content", "") if result.get("match") else ""
    score_match = re.search(r'"match_score"\s*:\s*(\d+)', match_raw)
    if score_match:
        return int(score_match.group(1))
    score_match = re.search(r'"overall_score"\s*:\s*([\d.]+)', match_raw)
    return int(round(float(score_match.group(1)))) if score_match else None


def _get_match_results(result: dict) -> list[dict]:
    """从结果中解析多 JD 匹配列表，兼容旧单 JD 格式。"""
    match_results = result.get("match_results")
    if not match_results and result.get("match"):
        return [{"name": "目标岗位", "result": result["match"]}]
    return match_results or []


def _parse_match_data(result: dict) -> Optional[dict]:
    """从结果中解析 JD 三维匹配数据。"""
    match = result.get("match")
    if not match:
        return None

    # 旧版误存入 match 的无 JD 数据，忽略
    if match.get("has_jd") is False:
        return None

    if match.get("keyword_score") is not None or match.get("overall_score") is not None:
        return match

    raw = match.get("raw_content", "")
    if not raw:
        return None

    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and (
            "keyword_score" in parsed or "overall_score" in parsed or "match_score" in parsed
        ):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


def _parse_quality_data(result: dict) -> Optional[dict]:
    """从结果中解析简历质量评估数据。"""
    quality = result.get("quality")
    if not quality:
        return None

    if quality.get("star_score") is not None or quality.get("overall_score") is not None:
        return quality

    raw = quality.get("raw_content", "")
    if not raw:
        return None

    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and (
            "star_score" in parsed or "expression_score" in parsed or "overall_score" in parsed
        ):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


def _render_dimension_bar(label: str, score: int, meta: str, color_class: str) -> str:
    safe_label = html.escape(label, quote=True)
    safe_meta = html.escape(meta, quote=True)
    pct = max(0, min(100, int(score)))
    return f"""
<div class="jd-dim-row">
  <div class="jd-dim-header">
    <span class="jd-dim-label">{safe_label} {pct}%</span>
    <span class="jd-dim-meta">{safe_meta}</span>
  </div>
  <div class="jd-progress-track">
    <div class="jd-progress-fill {color_class}" style="width:{pct}%"></div>
  </div>
</div>
"""


def _ensure_quality_data(
    result: dict,
    conv_id: Optional[str] = None,
    jd: str = "",
) -> Optional[dict]:
    """为旧记录补全简历质量数据（无 JD 且无 quality 字段时）。"""
    quality_data = _parse_quality_data(result)
    if quality_data:
        return quality_data

    if _parse_match_data(result):
        return None

    if (jd or "").strip():
        return None

    analysis_raw = (result.get("analysis") or {}).get("raw_content", "")
    if not analysis_raw:
        return None

    cache_key = f"gold_backfill_quality_{conv_id or 'current'}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    try:
        def _eval_quality():
            return ResumeQualityScorer().evaluate(analysis_raw)

        quality_result = run_with_thinking_chain(
            RESUME_ANALYSIS_STEPS,
            _eval_quality,
            model_name="DeepSeek V3 · 分析推理",
        )
        quality_data = quality_result.model_dump()
        st.session_state[cache_key] = quality_data

        if conv_id:
            for conv in st.session_state.get("gold_conversations", []):
                if conv.get("id") == conv_id:
                    conv.setdefault("result", {})["quality"] = quality_data
                    if conv["result"].get("match", {}).get("has_jd") is False:
                        conv["result"]["match"] = None
                    _save_probes(st.session_state.gold_conversations)
                    break

        return quality_data
    except Exception as e:
        logger.warning("[gold_detector] backfill quality failed: %s", e)
        return None


def _render_match_report(
    match_data: dict,
    report_key: str = "default",
    result: Optional[dict] = None,
) -> None:
    """渲染岗位匹配报告（有 JD 模式）。"""
    adapter = EmotionAdapter.from_session()
    layout = adapter.get_layout_mode()
    theme = adapter.get_theme()
    progress_style = adapter.get_progress_style()

    keyword_score = int(match_data.get("keyword_score", 0))
    star_score = int(match_data.get("star_score", 0))
    quant_score = int(match_data.get("quant_score", 0))
    overall_score = float(match_data.get("overall_score", 0))

    matched = match_data.get("keyword_matched") or []
    missing = match_data.get("keyword_missing") or []
    star_details = match_data.get("star_details") or []
    quant_details = match_data.get("quant_details") or []
    smart_suggestion = (match_data.get("smart_suggestion") or "").strip()

    star_pending = [
        item for item in star_details
        if isinstance(item, dict) and str(item.get("status", "")).lower() not in {"complete", "ok", "done"}
    ]
    quant_ok = sum(
        1 for item in quant_details
        if isinstance(item, dict) and str(item.get("status", "")).lower() == "quantified"
    )
    quant_pending = sum(
        1 for item in quant_details
        if isinstance(item, dict) and str(item.get("status", "")).lower() != "quantified"
    )

    dimensions = [
        ("关键词匹配", keyword_score, f"已匹配 {len(matched)} / 待补充 {len(missing)}", "jd-fill-blue"),
        ("STAR 结构", star_score, f"{len(star_pending)} 段待改写" if star_pending else "结构完整", "jd-fill-green"),
        ("量化表达", quant_score, f"{quant_ok} 处已量化 / {quant_pending} 处待量化", "jd-fill-orange"),
    ]

    if not render_cognitive_bias_gate(int(round(overall_score)), report_key=report_key):
        return

    from engines.cognitive_bias_detector import detect_cognitive_bias, should_show_bias_detection

    emotion_raw = (
        st.session_state.get("workshop_emotion_state")
        or st.session_state.get("emotion_state")
        or "平稳"
    )
    if should_show_bias_detection(str(emotion_raw)):
        self_key = f"gold_self_match_{report_key}"
        if st.session_state.get(f"gold_bias_revealed_{report_key}"):
            self_score = int(st.session_state.get(self_key, 30))
            bias = detect_cognitive_bias(self_score, int(round(overall_score)), str(emotion_raw))
            if bias.severity == "严重低估":
                render_severe_under_hint()
        st.markdown(
            '<div style="border-top:1px solid rgba(61,56,51,0.08);margin:20px 0;"></div>',
            unsafe_allow_html=True,
        )

    if layout == "guided":
        adapter.render_guided_steps(
            ["① 先看总分", "② 再看每个维度的详情", "③ 最后看 AI 建议"],
            title="别急，跟着看",
        )
    elif layout == "praise_first":
        dimensions.sort(key=lambda x: x[1], reverse=True)

    st.markdown(f'<div class="{adapter.get_shell_class("jd-match-report")}">', unsafe_allow_html=True)
    title_prefix = theme.get("emoji_prefix", "🎯")
    if layout == "praise_first":
        st.markdown(f'<div class="jd-match-title">{title_prefix} 先看看你做得好的</div>', unsafe_allow_html=True)
    elif layout == "single_column":
        st.markdown(f'<div class="jd-match-title">{title_prefix} 你的简历匹配度</div>', unsafe_allow_html=True)
        st.caption("💡 综合分已为你保留，细项细节收在下方，需要时再展开。")
    else:
        st.markdown('<div class="jd-match-title">🎯 岗位匹配报告</div>', unsafe_allow_html=True)

    ring_col, dims_col = st.columns([1, 2])
    with ring_col:
        render_score_ring(overall_score, keyword_score, star_score, quant_score)

    show_dims_inline = layout != "single_column"
    with dims_col:
        if show_dims_inline:
            bars_html = ""
            for idx, (label, score, meta, color_class) in enumerate(dimensions):
                if layout == "praise_first" and idx == 0:
                    bars_html += f'<div class="highlight-done" style="padding:4px 0; margin-bottom:4px;">'
                else:
                    bars_html += ""
                dim_meta = meta if progress_style != "minimal" else ""
                bars_html += _render_dimension_bar(label, score, dim_meta, color_class)
                if layout == "praise_first" and idx == 0:
                    bars_html += "</div>"
            st.markdown(f'<div class="jd-match-dims">{bars_html}</div>', unsafe_allow_html=True)
        else:
            st.caption("综合匹配度已为你简化展示，细节可以稍后再看。")

    if layout == "single_column":
        with st.expander("查看各维度详情"):
            bars_html = "".join(
                _render_dimension_bar(label, score, meta, color_class)
                for label, score, meta, color_class in dimensions
            )
            st.markdown(f'<div class="jd-match-dims">{bars_html}</div>', unsafe_allow_html=True)
            render_tags(matched, missing, star_pending)
    else:
        render_tags(matched, missing, star_pending)

    if smart_suggestion:
        safe_suggestion = html.escape(smart_suggestion, quote=True)
        st.markdown(
            f'<div class="jd-smart-suggestion"><strong>💡 智能建议：</strong>{safe_suggestion}</div>',
            unsafe_allow_html=True,
        )

    if st.button(
        "进入金子工坊，开始优化 →",
        type="primary",
        use_container_width=True,
        key=f"gold_workshop_{report_key}",
    ):
        _navigate_to_workshop(_get_workshop_result(match_data=match_data, quality_data=None) if result is None else result)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_quality_report(
    quality_data: dict,
    report_key: str = "default",
    result: Optional[dict] = None,
) -> None:
    """渲染简历质量报告（无 JD 模式）。"""
    adapter = EmotionAdapter.from_session()
    layout = adapter.get_layout_mode()
    theme = adapter.get_theme()
    progress_style = adapter.get_progress_style()

    star_score = int(quality_data.get("star_score", 0))
    quant_score = int(quality_data.get("quant_score", 0))
    expression_score = int(quality_data.get("expression_score", 0))
    overall_score = float(quality_data.get("overall_score", 0))

    star_details = quality_data.get("star_details") or []
    quant_details = quality_data.get("quant_details") or []
    expression_details = quality_data.get("expression_details") or []
    quality_suggestion = (quality_data.get("quality_suggestion") or "").strip()

    star_pending = [
        item for item in star_details
        if isinstance(item, dict) and str(item.get("status", "")).lower() not in {"complete", "ok", "done"}
    ]
    quant_pending = [
        item for item in quant_details
        if isinstance(item, dict) and str(item.get("status", "")).lower() != "quantified"
    ]
    expression_pending = [
        item for item in expression_details
        if isinstance(item, dict) and str(item.get("status", "")).lower() not in {"complete", "ok", "done"}
    ]

    colloquial_count = sum(
        1 for item in expression_pending
        if str(item.get("status", "")).lower() == "colloquial"
    )
    hollow_count = sum(
        1 for item in expression_pending
        if str(item.get("status", "")).lower() in {"hollow_claim", "hollow", "empty_claim"}
    )
    expression_meta_parts = []
    if colloquial_count:
        expression_meta_parts.append(f"{colloquial_count} 处口语化")
    if hollow_count:
        expression_meta_parts.append(f"{hollow_count} 处空话套话")
    if not expression_meta_parts:
        expression_meta_parts.append("表达规范" if not expression_pending else f"{len(expression_pending)} 处待优化")
    expression_meta = " / ".join(expression_meta_parts)

    if star_pending:
        total = max(len(star_details), len(star_pending))
        star_meta = f"{total} 段经历中 {len(star_pending)} 段待改写"
    else:
        star_meta = "结构完整"

    dimensions = [
        ("STAR 结构", star_score, star_meta, "jd-fill-green"),
        (
            "量化表达",
            quant_score,
            f"{len(quant_details) - len(quant_pending)} 处已量化 / {len(quant_pending)} 处待量化",
            "jd-fill-orange",
        ),
        ("表达规范", expression_score, expression_meta, "jd-fill-blue"),
    ]

    if layout == "guided":
        adapter.render_guided_steps(
            ["① 先看总分", "② 再看每个维度的详情", "③ 最后看 AI 建议"],
            title="别急，跟着看",
        )
    elif layout == "praise_first":
        dimensions.sort(key=lambda x: x[1], reverse=True)

    st.markdown(f'<div class="{adapter.get_shell_class("jd-match-report")}">', unsafe_allow_html=True)
    title_prefix = theme.get("emoji_prefix", "📋")
    if layout == "praise_first":
        st.markdown(f'<div class="jd-match-title">{title_prefix} 先看看你做得好的</div>', unsafe_allow_html=True)
    elif layout == "single_column":
        st.markdown(f'<div class="jd-match-title">{title_prefix} 你的简历质量</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="jd-match-title">📋 简历质量报告</div>', unsafe_allow_html=True)
    st.caption("未填写岗位 JD，以下为简历自身质量评估。粘贴目标岗位 JD 后可解锁关键词匹配分析。")

    ring_col, dims_col = st.columns([1, 2])
    with ring_col:
        render_quality_ring(overall_score, star_score, quant_score, expression_score)

    show_dims_inline = layout != "single_column"
    with dims_col:
        if show_dims_inline:
            bars_html = ""
            for idx, (label, score, meta, color_class) in enumerate(dimensions):
                if layout == "praise_first" and idx == 0:
                    bars_html += '<div class="highlight-done" style="padding:4px 0; margin-bottom:4px;">'
                dim_meta = meta if progress_style != "minimal" else ""
                bars_html += _render_dimension_bar(label, score, dim_meta, color_class)
                if layout == "praise_first" and idx == 0:
                    bars_html += "</div>"
            st.markdown(f'<div class="jd-match-dims">{bars_html}</div>', unsafe_allow_html=True)
        else:
            st.caption("综合质量已为你简化展示，细节可以稍后再看。")

    if layout == "single_column":
        with st.expander("查看各维度详情"):
            bars_html = "".join(
                _render_dimension_bar(label, score, meta, color_class)
                for label, score, meta, color_class in dimensions
            )
            st.markdown(f'<div class="jd-match-dims">{bars_html}</div>', unsafe_allow_html=True)
            render_quality_tags(star_pending, quant_pending, expression_pending)
    else:
        render_quality_tags(star_pending, quant_pending, expression_pending)

    if quality_suggestion:
        safe_suggestion = html.escape(quality_suggestion, quote=True)
        st.markdown(
            f'<div class="jd-smart-suggestion"><strong>💡 质量建议：</strong>{safe_suggestion}</div>',
            unsafe_allow_html=True,
        )

    star_evidence = quality_data.get("star_evidence") or []
    quant_evidence = quality_data.get("quant_evidence") or []
    expression_evidence = quality_data.get("expression_evidence") or []
    has_xai = any([star_evidence, quant_evidence, expression_evidence])

    if has_xai or star_pending or quant_pending or expression_pending:
        with st.expander("🔍 查看评分依据（可解释 AI / XAI）", expanded=has_xai):
            from components.xai_evidence import render_xai_evidence_section

            render_xai_evidence_section(
                "STAR 结构",
                star_evidence or [
                    {
                        "original_text": item.get("original_text", item.get("content", "")),
                        "issue": item.get("status", ""),
                        "suggestion": item.get("suggestion", ""),
                    }
                    for item in star_pending
                    if isinstance(item, dict)
                ],
            )
            render_xai_evidence_section(
                "量化表达",
                quant_evidence or [
                    {
                        "original_text": item.get("original_text", item.get("content", "")),
                        "issue": item.get("status", ""),
                        "suggestion": item.get("suggestion", ""),
                    }
                    for item in quant_pending
                    if isinstance(item, dict)
                ],
            )
            render_xai_evidence_section(
                "表达规范",
                expression_evidence or [
                    {
                        "original_text": item.get("original_text", item.get("content", "")),
                        "issue": item.get("status", ""),
                        "suggestion": item.get("suggestion", ""),
                    }
                    for item in expression_pending
                    if isinstance(item, dict)
                ],
            )

    if st.button("粘贴 JD，解锁关键词匹配 →", key=f"gold_unlock_jd_{report_key}"):
        st.session_state.gold_show_input = True
        st.rerun()

    if st.button(
        "进入金子工坊，开始优化 →",
        type="primary",
        use_container_width=True,
        key=f"gold_workshop_quality_{report_key}",
    ):
        _navigate_to_workshop(_get_workshop_result(match_data=None, quality_data=quality_data) if result is None else result)

    st.markdown("</div>", unsafe_allow_html=True)


def _extract_strengths(result: dict, report_text: str) -> list[str]:
    """从analyzer的分析结果中精准提取核心优势，不依赖reporter的自然语言报告"""
    strengths: list[str] = []

    # 第一步：从analysis的raw_content中提取core_advantages
    analysis_raw = result.get("analysis", {}).get("raw_content", "")
    analysis_cleaned = analysis_raw.strip()
    if "```json" in analysis_cleaned:
        analysis_cleaned = analysis_cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in analysis_cleaned:
        analysis_cleaned = analysis_cleaned.split("```")[1].split("```")[0].strip()

    try:
        parsed_analysis = json.loads(analysis_cleaned)
        for gold in parsed_analysis.get("core_advantages", []):
            if not isinstance(gold, dict):
                continue
            name = (gold.get("name") or gold.get("title") or gold.get("advantage") or "").strip()
            diff = (gold.get("differentiation") or gold.get("description") or gold.get("detail") or "").strip()
            market = (gold.get("market_value") or "").strip()
            # 组合：名称 + 差异化描述
            if name and diff:
                strengths.append(f"{name}：{diff}")
            elif name:
                strengths.append(name)
    except json.JSONDecodeError:
        pass

    # 第二步：如果analysis里没有，尝试从report的raw_content里找
    if not strengths:
        raw = result.get("report", {}).get("raw_content", "")
        cleaned = raw.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        try:
            parsed = json.loads(cleaned)
            # reporter可能把analysis结果带进来了
            for gold in parsed.get("core_advantages", []):
                if not isinstance(gold, dict):
                    continue
                name = (gold.get("name") or gold.get("title") or "").strip()
                diff = (gold.get("differentiation") or gold.get("description") or "").strip()
                if name and diff:
                    strengths.append(f"{name}：{diff}")
                elif name:
                    strengths.append(name)
        except json.JSONDecodeError:
            pass

    # 第三步：正则兜底，从analysis_raw中匹配name字段
    if not strengths:
        arr_match = re.search(r'"core_advantages"\s*:\s*\[(.*?)\]', analysis_raw, re.DOTALL)
        if arr_match:
            name_matches = re.findall(r'"name"\s*:\s*"((?:[^"\\]|\\.)*?)"', arr_match.group(1))
            for n in name_matches:
                n = n.replace("\\n", "\n").replace('\\"', '"').strip()
                if n and n not in strengths:
                    strengths.append(n)

    # 清理和去重
    cleaned: list[str] = []
    for item in strengths:
        text = item.strip()
        if not text or text in {"-", "•", "*", "：", "**"}:
            continue
        # 过滤掉方法论特征的内容
        method_keywords = ["记账式", "STAR法则", "动词+任务+结果", "错误示范", "正确示范", "第一步", "第二步", "第三步", "怎么改", "改法"]
        if any(kw in text for kw in method_keywords):
            continue
        if text not in cleaned:
            cleaned.append(text)

    return cleaned[:5]


_FOLLOWUP_SYSTEM_PROMPT = (
    '你是一位简历分析师"金子"，用户对你的报告有疑问，请基于简历原文和报告内容回答。'
    '如果涉及"怎么表达"，给出原文vs改写对比（STAR法则+量化成果）。'
    "如果涉及短板，给出具体补救路线。"
)

_FOLLOWUP_QUICK_QUESTIONS = [
    "你说的优势具体哪里体现？",
    "这些能力求职时怎么表达？",
    "我最大的短板是什么？怎么补？",
]


def _get_current_conv() -> Optional[dict]:
    conv_id = st.session_state.get("gold_current_conv_id")
    if not conv_id:
        return None
    return next((c for c in st.session_state.gold_conversations if c["id"] == conv_id), None)


def _get_followup_conv_key() -> str:
    return st.session_state.get("gold_current_conv_id") or "current"


def _get_followup_history() -> list[dict]:
    key = _get_followup_conv_key()
    history_map = st.session_state.gold_followup_history
    if key not in history_map:
        history_map[key] = []
    return history_map[key]


def _get_resume_for_followup() -> str:
    resume = (st.session_state.get("gold_resume_text") or "").strip()
    if resume:
        return resume
    conv = _get_current_conv()
    if conv:
        return (conv.get("resume") or "").strip()
    return ""


def _emotion_state_for_workshop() -> str:
    from utils.emotion_adapter import sync_emotion_to_session

    return sync_emotion_to_session()


def _get_workshop_result(
    match_data: Optional[dict] = None,
    quality_data: Optional[dict] = None,
) -> dict:
    """获取当前报告完整 result，供跳转金子工坊使用。"""
    current = st.session_state.get("gold_current_result")
    if isinstance(current, dict):
        return current
    conv = _get_current_conv()
    if conv and isinstance(conv.get("result"), dict):
        return conv["result"]
    return {
        "match": match_data,
        "quality": quality_data,
    }


def _extract_bridge_scores(
    result: dict,
    match_data: Optional[dict] = None,
) -> Optional[dict]:
    """从探测器结果提取分数，供工坊跳过重复 AI 评分。"""
    match = match_data if match_data is not None else result.get("match")
    if isinstance(match, dict) and match.get("overall_score") is not None:
        return {
            "overall": float(match.get("overall_score", 0)),
            "star": int(match.get("star_score", 0)),
            "quantify": int(match.get("quant_score", 0)),
            "keyword": int(match.get("keyword_score", 0)),
        }
    quality = result.get("quality")
    if isinstance(quality, dict) and quality.get("overall_score") is not None:
        return {
            "overall": float(quality.get("overall_score", 0)),
            "star": int(quality.get("star_score", 0)),
            "quantify": int(quality.get("quant_score", 0)),
            "keyword": int(quality.get("expression_score", 0)),
        }
    return None


def _bridge_sections_usable(sections: dict) -> bool:
    from engines.resume_parser import sections_look_monolithic

    normalized = {k: str(v or "").strip() for k, v in sections.items()}
    return bool(any(normalized.values())) and not sections_look_monolithic(normalized)


def _navigate_to_workshop(
    result: dict,
    jd_text: str = "",
    match_data: Optional[dict] = None,
) -> None:
    """从金子探测器携带数据进入金子工坊。"""
    conv = _get_current_conv()
    resume = _get_resume_for_followup()
    jd = (jd_text or "").strip()
    if not jd and conv:
        jd = (conv.get("jd") or "").strip()
    if not jd:
        jd = (st.session_state.get("gold_jd_text") or "").strip()

    st.session_state.workshop_resume_text = resume
    st.session_state.workshop_resume_input = resume
    st.session_state.workshop_jd_text = jd
    st.session_state.workshop_jd_input = jd
    st.session_state.workshop_quality_data = result.get("quality")
    st.session_state.workshop_match_data = match_data if match_data is not None else result.get("match")
    st.session_state.workshop_emotion_state = _emotion_state_for_workshop()
    st.session_state.workshop_before_scores = _extract_bridge_scores(
        result, match_data if match_data is not None else result.get("match")
    )

    parsed = result.get("parsed_sections")
    if isinstance(parsed, dict) and _bridge_sections_usable(parsed):
        from engines.resume_parser import SECTION_KEYS

        st.session_state.workshop_sections = {
            key: str(parsed.get(key, "") or "").strip() for key in SECTION_KEYS
        }
        st.session_state.workshop_sections_parsed = True
        st.session_state.workshop_fast_entry = False
    else:
        st.session_state.workshop_sections = {}
        st.session_state.workshop_sections_parsed = False
        st.session_state.workshop_fast_entry = True
    st.session_state.workshop_section_status = {}
    st.session_state.workshop_optimized = {}
    st.session_state.workshop_adopted = {}
    st.session_state.workshop_changes = {}
    st.session_state.workshop_optimize_types = {}
    st.session_state.workshop_manual_editing = None
    st.session_state.workshop_optimize_error = None
    st.session_state.workshop_current_section = "basic_info"

    from ui.sidebar import navigate_to_page

    navigate_to_page("workshop")
    st.rerun()


def _build_followup_prompt(
    resume_text: str,
    result: dict,
    report_text: str,
    question: str,
    history: list[dict],
) -> str:
    analysis_raw = (result.get("analysis") or {}).get("raw_content", "")
    report_raw = (result.get("report") or {}).get("raw_content", "")

    history_lines = []
    for msg in history[-6:]:
        role = "用户" if msg.get("role") == "user" else "金子"
        history_lines.append(f"{role}：{msg.get('content', '')}")

    parts = [
        "【原始简历】",
        resume_text or "（简历原文已从内存清除，请主要依据下方分析结果和报告回答）",
        "",
        "【分析结果摘要】",
        analysis_raw[:4000] or "无",
        "",
        "【报告摘要】",
        (report_text or report_raw)[:4000] or "无",
    ]
    if history_lines:
        parts.extend(["", "【对话历史】", *history_lines])
    parts.extend(["", "【当前问题】", question])
    return "\n".join(parts)


def _call_followup_analyst(prompt: str) -> str:
    from core.model_router import model_router

    return model_router.call(
        prompt=prompt,
        task_type="resume_followup",
        system_prompt=_FOLLOWUP_SYSTEM_PROMPT,
        max_tokens=800,
    )


def _send_followup_question(question: str, result: dict, report_text: str) -> None:
    question = (question or "").strip()
    if not question:
        return

    history = _get_followup_history()
    resume_text = _get_resume_for_followup()
    prompt = _build_followup_prompt(resume_text, result, report_text, question, history)

    try:
        from ui.error_handler import handle_api_error

        answer = run_with_thinking_chain(
            [
                {"title": "理解你的追问", "desc": "结合报告上下文定位问题"},
                {"title": "检索简历证据", "desc": "从分析结果中寻找支撑"},
                {"title": "生成针对性回答", "desc": "给出可执行的表达建议"},
            ],
            lambda: _call_followup_analyst(prompt),
            model_name="DeepSeek V3 · 分析推理",
        )
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer.strip()})
    except Exception as e:
        handle_api_error(e, context="gold_followup")


def _render_followup_section(result: dict, report_text: str) -> None:
    """报告下方的追问分析师区域。"""
    pending = st.session_state.get("gold_followup_pending")
    if pending:
        st.session_state.gold_followup_pending = None
        _send_followup_question(pending, result, report_text)

    with st.container():
        st.markdown('<div class="gold-followup-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="gold-followup-title">💬 追问分析师</div>', unsafe_allow_html=True)

        history = _get_followup_history()
        for msg in history:
            role = msg.get("role", "assistant")
            with st.chat_message("user" if role == "user" else "assistant"):
                st.markdown(msg.get("content", ""))

        q_cols = st.columns(3)
        for i, quick_q in enumerate(_FOLLOWUP_QUICK_QUESTIONS):
            with q_cols[i]:
                if st.button(quick_q, key=f"gold_fq_{i}", use_container_width=True):
                    st.session_state.gold_followup_pending = quick_q
                    st.rerun()

        col_input, col_send = st.columns([5, 1])
        with col_input:
            followup_input = st.text_input(
                "追问输入",
                placeholder="对报告有疑问？继续问...",
                label_visibility="collapsed",
                key="gold_followup_input",
            )
        with col_send:
            send_clicked = st.button("发送", key="gold_followup_send", type="primary", use_container_width=True)

        if send_clicked and followup_input and followup_input.strip():
            _send_followup_question(followup_input.strip(), result, report_text)
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ===== 核心业务 =====

def _run_detection(resume: str, jd_list: list[dict]) -> dict:
    from ui.error_handler import handle_api_error

    try:
        analysis = run_with_thinking_chain(
            RESUME_ANALYSIS_STEPS,
            lambda: resume_analyzer.analyze(resume),
            model_name="DeepSeek V3 · 分析推理",
        )

        match_results: list[dict] = []
        for jd_item in jd_list:
            content = (jd_item.get("content") or "").strip()
            if not content:
                continue
            name = jd_item.get("name") or "目标岗位"
            analysis_raw = analysis.raw_content

            def _match_jd(jd_content: str = content, raw: str = analysis_raw):
                return JDMatcherV2().match(raw, jd_content)

            match_result = run_with_thinking_chain(
                JD_MATCH_STEPS,
                _match_jd,
                model_name="DeepSeek V3 · 分析推理",
            )
            match_results.append({
                "name": name,
                "result": match_result.model_dump(),
            })

        quality_result = None
        if not match_results:
            quality_result = run_with_thinking_chain(
                RESUME_ANALYSIS_STEPS,
                lambda: ResumeQualityScorer().evaluate(analysis.raw_content),
                model_name="DeepSeek V3 · 分析推理",
            )

        first_raw = ""
        if match_results:
            first_raw = match_results[0]["result"].get("raw_content", "")

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        from engines.resume_parser import ResumeParser, heuristic_split_resume, sections_look_monolithic

        def _parse_for_workshop() -> dict[str, str]:
            try:
                sections = ResumeParser().parse(resume).sections
            except Exception as exc:
                logger.warning("[gold_detector] resume parse for workshop failed: %s", exc)
                sections = ResumeParser().parse_fast(resume).sections
            if sections_look_monolithic(sections):
                sections = heuristic_split_resume(resume)
            return sections

        parse_pool = ThreadPoolExecutor(max_workers=1)
        parse_future = parse_pool.submit(_parse_for_workshop)

        report = run_with_thinking_chain(
            [
                {"title": "整合分析结果", "desc": "汇总优势、差距与翻案角度"},
                {"title": "撰写翻案报告", "desc": "用温暖语气呈现你的核心竞争力"},
                {"title": "生成行动建议", "desc": "给出可执行的下一步"},
            ],
            lambda: report_generator.generate(
                analysis.raw_content,
                first_raw or "无岗位信息，请仅基于简历分析",
            ),
            model_name="DeepSeek V3 · 分析推理",
        )

        parsed_sections: dict[str, str] = {}
        try:
            parsed_sections = parse_future.result(timeout=90)
        except FuturesTimeout:
            logger.warning("[gold_detector] resume parse timeout, using fast fallback")
            parsed_sections = ResumeParser().parse_fast(resume).sections
        except Exception as exc:
            logger.warning("[gold_detector] resume parse error: %s", exc)
            parsed_sections = ResumeParser().parse_fast(resume).sections
        finally:
            parse_pool.shutdown(wait=False, cancel_futures=True)

        recommend_data = None
        try:
            match_data_for_rec = None
            if match_results:
                first_match = match_results[0]["result"]
                if isinstance(first_match, dict):
                    match_data_for_rec = {
                        "keyword_matched": first_match.get("keyword_matched", []),
                        "keyword_missing": first_match.get("keyword_missing", []),
                    }
            recommend_result = JobRecommender().recommend(resume, match_data=match_data_for_rec)
            if recommend_result.recommendations:
                recommend_data = {
                    "recommendations": [
                        {
                            "title": r.title,
                            "match_reason": r.match_reason,
                            "ability_match": r.ability_match,
                            "ability_gap": r.ability_gap,
                            "salary_range": r.salary_range,
                            "search_keyword": r.search_keyword,
                        }
                        for r in recommend_result.recommendations
                    ],
                    "summary": recommend_result.summary,
                }
        except Exception as e:
            logger.warning("[gold_detector] job recommend failed: %s", e)
            recommend_data = {"recommendations": [], "summary": "", "error": True}

        return {
            "analysis": analysis.model_dump(),
            "match_results": match_results,
            "match": match_results[0]["result"] if match_results else None,
            "quality": quality_result.model_dump() if quality_result else None,
            "recommend": recommend_data,
            "report": report.model_dump(),
            "parsed_sections": parsed_sections,
        }
    except Exception as e:
        handle_api_error(e, context="gold_detector")
        raise


def _resolve_jd_content(jd_name: str) -> str:
    """按岗位名称查找 JD 原文。"""
    conv = _get_current_conv()
    if conv and conv.get("jd_list"):
        for item in conv["jd_list"]:
            if item.get("name") == jd_name:
                return (item.get("content") or "").strip()
    for item in st.session_state.get("gold_jd_list") or []:
        if item.get("name") == jd_name:
            return (item.get("content") or "").strip()
    return ""


def _save_conversation(
    result: dict,
    resume: str,
    jd: str = "",
    jd_list: Optional[list[dict]] = None,
) -> None:
    new_index = len(st.session_state.gold_conversations) + 1
    conv_id = f"gold_{int(datetime.now().timestamp() * 1000)}"
    conv = {
        "id": conv_id,
        "name": f"探测 {new_index}",
        "resume_snippet": (resume.strip()[:20] + "...") if len(resume.strip()) > 20 else resume.strip(),
        "result": result,
        "resume": resume,
        "jd": jd,
        "jd_list": jd_list or [],
        "created_at": datetime.now().strftime("%m-%d %H:%M"),
    }
    st.session_state.gold_conversations.append(conv)
    # 持久化到文件
    _save_probes(st.session_state.gold_conversations)
    st.session_state.gold_current_conv_id = conv_id
    st.session_state.gold_current_result = result
    st.session_state.gold_show_input = False
    st.session_state.pop("resume_text", None)
    st.session_state.gold_resume_text = ""
    if "gold_resume_input" in st.session_state:
        st.session_state.gold_resume_input = ""


# ===== 新探测 =====

def _handle_new_probe() -> None:
    """点击新探测：当前结果已自动保存，直接重置输入区"""
    st.session_state.gold_show_input = True
    st.session_state.gold_current_conv_id = None
    st.session_state.gold_current_result = None
    st.session_state.gold_pending_probe = None
    st.session_state.gold_probe_running = False
    st.session_state.gold_resume_text = ""
    st.session_state.gold_jd_text = ""
    st.session_state.gold_jd_list = [{"name": "岗位1", "content": ""}]
    st.session_state.gold_upload_name = None  # 重置上传文件标记
    st.session_state.gold_flash_message = None
    # 清空 uploader widget 状态，避免旧文件状态触发反复重跑
    if "resume_upload" in st.session_state:
        st.session_state.resume_upload = None
    if "gold_resume_input" in st.session_state:
        st.session_state.gold_resume_input = ""
    if "gold_jd_input" in st.session_state:
        st.session_state.gold_jd_input = ""


# ===== 渲染：左列历史面板 =====

def _render_history_sidebar() -> None:
    """渲染左列历史面板，始终显示"""
    gold_convs = st.session_state.get("gold_conversations", [])
    current_conv_id = st.session_state.get("gold_current_conv_id")

    if st.button("＋ 新探测", key="gold_history_new", use_container_width=True):
        _handle_new_probe()

    st.markdown('<div class="gold-history-divider"></div>', unsafe_allow_html=True)

    if gold_convs:
        for conv in reversed(gold_convs):
            is_active = conv["id"] == current_conv_id
            name = conv.get("name", "未命名")
            time_str = conv.get("created_at", "")

            # 当前选中的加前缀标记
            label = f"▶ {name} · {time_str}" if is_active else f"   {name} · {time_str}"

            if st.button(
                label,
                key=f"hist_{conv['id']}",
                use_container_width=True,
            ):
                st.session_state.gold_current_conv_id = conv["id"]
                st.session_state.gold_current_result = conv["result"]
                st.session_state.gold_show_input = False
                st.rerun()
    else:
        st.markdown(
            '<div style="color:#B8AFA5; font-size:12px; padding:8px 4px; line-height:1.6;">还没有探测记录<br/>提交简历后会出现在这里</div>',
            unsafe_allow_html=True,
        )


# ===== 渲染：岗位推荐 =====

def _render_job_recommendations_section(result: dict) -> None:
    """渲染岗位方向推荐（旧记录无 recommend 字段时跳过）。"""
    recommend_data = result.get("recommend")
    if not recommend_data:
        return

    if recommend_data.get("error") and not recommend_data.get("recommendations"):
        render_section_divider("岗位推荐")
        st.info("岗位推荐暂时不可用，请稍后重试。")
        return

    if not recommend_data.get("recommendations"):
        return

    recs = [
        JobRecommendation(
            title=r.get("title", ""),
            match_reason=r.get("match_reason", ""),
            ability_match=r.get("ability_match", []),
            ability_gap=r.get("ability_gap", []),
            salary_range=r.get("salary_range", ""),
            search_keyword=r.get("search_keyword", ""),
        )
        for r in recommend_data["recommendations"]
    ]
    rec_result = JobRecommendResult(
        recommendations=recs,
        summary=recommend_data.get("summary", ""),
    )
    render_section_divider("岗位推荐")
    render_job_recommendations(rec_result)


# ===== 渲染：报告区域 =====

def _render_result_block(result: dict) -> None:
    report_text = _parse_report_text(result)
    # 兜底：如果解析结果还是JSON开头，再剥一层
    if report_text and report_text.strip().startswith("{"):
        try:
            parsed = json.loads(report_text)
            if "natural_language_report" in parsed:
                report_text = parsed["natural_language_report"]
        except json.JSONDecodeError:
            pass
    if report_text and report_text.strip().startswith("```"):
        parts = report_text.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            report_text = inner.strip()

    match_score = _parse_match_score(result)
    conv_id = st.session_state.get("gold_current_conv_id")
    conv = _get_current_conv()
    conv_jd = (conv.get("jd") or "") if conv else ""

    match_data = _parse_match_data(result)
    quality_data = _parse_quality_data(result)
    match_results = _get_match_results(result)
    if not quality_data and not match_data and not match_results:
        quality_data = _ensure_quality_data(result, conv_id, conv_jd)

    strengths = _extract_strengths(result, report_text)

    _shell_adapter = EmotionAdapter.from_session()
    st.markdown(f'<div class="{_shell_adapter.get_shell_class()}">', unsafe_allow_html=True)
    render_report_header()
    render_report_body(report_text)

    report_key = str(conv_id or "current")
    if match_results and len(match_results) > 1:
        render_section_divider("投递方向")
        selected_jd = render_radar_compare(match_results)
        if selected_jd and st.button(
            "🔨 进入金子工坊优化",
            type="primary",
            key=f"radar_workshop_{report_key}",
            use_container_width=True,
        ):
            selected_item = next(m for m in match_results if m["name"] == selected_jd)
            selected_result = selected_item.get("result") or {}
            if hasattr(selected_result, "model_dump"):
                selected_result = selected_result.model_dump()
            jd_content = _resolve_jd_content(selected_jd)
            _navigate_to_workshop(result, jd_text=jd_content, match_data=selected_result)
    elif quality_data and not match_data:
        render_section_divider("质量评估")
        _render_quality_report(quality_data, report_key=report_key, result=result)
    elif match_data:
        render_section_divider("岗位匹配")
        _render_match_report(match_data, report_key=report_key, result=result)
    elif match_score is not None:
        render_section_divider("匹配度")
        st.markdown(f'<div class="gold-score">{match_score}</div>', unsafe_allow_html=True)

    if strengths:
        render_section_divider("亮点提炼")
        render_strengths(strengths)

    reframe_pairs = extract_reframe_pairs(result)
    if reframe_pairs:
        render_section_divider("翻案对比")
        render_reframe_compare(reframe_pairs)

    with st.expander("查看详细分析数据"):
        st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")

    st.markdown('<div class="gold-export-block">', unsafe_allow_html=True)
    st.markdown('<div class="gold-export-label">导出报告</div>', unsafe_allow_html=True)
    col_exp1, col_exp2, col_exp3 = st.columns(3)

    with col_exp1:
        md_content = _generate_md_report(result, report_text, match_score, strengths, match_data)
        st.download_button(
            label="📄 导出 Markdown",
            data=md_content,
            file_name=f"金子探测器报告_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            key="download_md",
            use_container_width=True,
        )

    with col_exp2:
        docx_bytes = _generate_docx_report(result, report_text, match_score, strengths, match_data)
        st.download_button(
            label="📝 导出 Word",
            data=docx_bytes,
            file_name=f"金子探测器报告_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="download_docx",
            use_container_width=True,
        )

    with col_exp3:
        pdf_bytes = _generate_pdf_report(result, report_text, match_score, strengths, match_data)
        st.download_button(
            label="📋 导出 PDF",
            data=pdf_bytes,
            file_name=f"金子探测器报告_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key="download_pdf",
            use_container_width=True,
        )

    st.session_state.gold_report = report_text
    try:
        pdf_bytes = export_gold_report_pdf(report_text)
        st.download_button(
            label="📥 下载完整 PDF 报告",
            data=pdf_bytes,
            file_name="职场镜子-金子探测器报告.pdf",
            mime="application/pdf",
            key="download_pdf_core",
            use_container_width=True,
        )
    except Exception as e:
        logger.warning("[gold_detector] PDF export failed: %s", e)

    _render_job_recommendations_section(result)

    st.markdown(
        '<p class="gold-privacy-note">🔒 简历原文已从内存中清除，仅保留分析报告</p>',
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    _render_followup_section(result, report_text)

    has_jd = bool(match_data or match_results)
    nav_match = match_data or (match_results[0]["result"] if match_results else None)
    resume_for_bridge = (st.session_state.get("gold_resume_text") or "").strip()
    render_smart_nav(
        get_gold_detector_nav_recommendations(nav_match, has_jd),
        context={
            "strengths": strengths,
            "result": result,
            "resume_snippet": resume_for_bridge,
        },
    )


def _generate_md_report(
    result: dict,
    report_text: str,
    match_score,
    strengths: list,
    match_data: Optional[dict] = None,
) -> str:
    """生成Markdown格式报告"""
    lines = ["# 金子探测器 - 简历分析报告\n"]
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n")
    lines.append(f"## 报告正文\n\n{report_text}\n\n")
    if match_data:
        lines.append("## 岗位匹配报告\n\n")
        lines.append(f"- **综合匹配**：{match_data.get('overall_score', match_score)} 分\n")
        lines.append(f"- **关键词匹配**：{match_data.get('keyword_score', '-')} 分\n")
        lines.append(f"- **STAR 结构**：{match_data.get('star_score', '-')} 分\n")
        lines.append(f"- **量化表达**：{match_data.get('quant_score', '-')} 分\n\n")
        if match_data.get("smart_suggestion"):
            lines.append(f"**智能建议**：{match_data['smart_suggestion']}\n\n")
    elif match_score is not None:
        lines.append(f"## 匹配度\n\n **{match_score}分**\n\n")
    if strengths:
        lines.append("## 核心优势\n\n")
        for s in strengths:
            lines.append(f"- {s}\n")
        lines.append("\n")
    lines.append("---\n*职场镜子 · 陪你走过最难熬的求职路*\n")
    return "".join(lines)


def _generate_docx_report(
    result: dict,
    report_text: str,
    match_score,
    strengths: list,
    match_data: Optional[dict] = None,
) -> bytes:
    """生成Word格式报告"""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from io import BytesIO

    doc = Document()

    title = doc.add_heading("金子探测器 - 简历分析报告", level=1)
    title.runs[0].font.color.rgb = RGBColor(0x2C, 0x24, 0x20)

    doc.add_paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph("")

    doc.add_heading("报告正文", level=2)
    for para in report_text.split("\n\n"):
        if para.strip():
            p = doc.add_paragraph(para.strip())
            p.paragraph_format.space_after = Pt(6)

    if match_data:
        doc.add_heading("岗位匹配报告", level=2)
        doc.add_paragraph(f"综合匹配：{match_data.get('overall_score', match_score)} 分")
        doc.add_paragraph(f"关键词匹配：{match_data.get('keyword_score', '-')} 分")
        doc.add_paragraph(f"STAR 结构：{match_data.get('star_score', '-')} 分")
        doc.add_paragraph(f"量化表达：{match_data.get('quant_score', '-')} 分")
        if match_data.get("smart_suggestion"):
            doc.add_paragraph(f"智能建议：{match_data['smart_suggestion']}")
    elif match_score is not None:
        doc.add_heading("匹配度", level=2)
        score_para = doc.add_paragraph(f"{match_score}分")
        score_para.runs[0].font.size = Pt(20)
        score_para.runs[0].font.color.rgb = RGBColor(0xB8, 0x90, 0x8A)

    if strengths:
        doc.add_heading("核心优势", level=2)
        for s in strengths:
            doc.add_paragraph(s, style="List Bullet")

    doc.add_paragraph("")
    doc.add_paragraph("职场镜子 · 陪你走过最难熬的求职路").runs[0].font.color.rgb = RGBColor(
        0x9E, 0x8E, 0x83
    )

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _generate_pdf_report(
    result: dict,
    report_text: str,
    match_score,
    strengths: list,
    match_data: Optional[dict] = None,
) -> bytes:
    """生成PDF格式报告（使用weasyprint HTML转PDF，解决中文乱码）"""
    from io import BytesIO

    # 构建HTML内容
    html_parts = [
        '<html><head><meta charset="utf-8">',
        '<style>body{font-family: "Microsoft YaHei", "SimHei", sans-serif; padding: 40px; color: #2C2420; line-height: 1.8;}',
        'h1{color: #2C2420; border-bottom: 2px solid #B8908A; padding-bottom: 10px;}',
        'h2{color: #2C2420; margin-top: 24px;}',
        '.score{color: #B8908A; font-size: 28px; font-weight: bold;}',
        '.footer{color: #9E8E83; font-size: 12px; margin-top: 40px; border-top: 1px solid #ddd; padding-top: 10px;}',
        'ul{padding-left: 20px;} li{margin-bottom: 6px;}</style></head><body>',
        '<h1>金子探测器 - 简历分析报告</h1>',
        f'<p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
        '<h2>报告正文</h2>',
    ]

    for para in report_text.split("\n\n"):
        if para.strip():
            html_parts.append(f'<p>{para.strip().replace(chr(10), "<br/>")}</p>')

    if match_data:
        html_parts.append("<h2>岗位匹配报告</h2>")
        html_parts.append(f"<p>综合匹配：{match_data.get('overall_score', match_score)} 分</p>")
        html_parts.append(f"<p>关键词匹配：{match_data.get('keyword_score', '-')} 分</p>")
        html_parts.append(f"<p>STAR 结构：{match_data.get('star_score', '-')} 分</p>")
        html_parts.append(f"<p>量化表达：{match_data.get('quant_score', '-')} 分</p>")
        if match_data.get("smart_suggestion"):
            html_parts.append(f"<p>智能建议：{match_data['smart_suggestion']}</p>")
    elif match_score is not None:
        html_parts.append(f'<h2>匹配度</h2><p class="score">{match_score}分</p>')

    if strengths:
        html_parts.append('<h2>核心优势</h2><ul>')
        for s in strengths:
            html_parts.append(f'<li>{s}</li>')
        html_parts.append('</ul>')

    html_parts.append('<p class="footer">职场镜子 · 陪你走过最难熬的求职路</p>')
    html_parts.append('</body></html>')

    html_content = "".join(html_parts)

    try:
        from weasyprint import HTML as WeasyHTML
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
        return pdf_bytes
    except Exception:
        # weasyprint在Windows可能因系统库缺失抛OSError，这里统一降级
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.colors import HexColor
            from io import BytesIO

            buf = BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4)
            styles = getSampleStyleSheet()

            # 尝试注册中文字体
            font_name = "ChineseFont"
            font_registered = False
            for font_path in [
                "C:/Windows/Fonts/msyh.ttc",   # 微软雅黑
                "C:/Windows/Fonts/simhei.ttf",  # 黑体
                "C:/Windows/Fonts/simsun.ttc",  # 宋体
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux
                "/System/Library/Fonts/PingFang.ttc",  # macOS
            ]:
                if Path(font_path).exists():
                    try:
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        font_registered = True
                        break
                    except Exception:
                        continue

            body_font = font_name if font_registered else "Helvetica"
            title_font = font_name if font_registered else "Helvetica"

            title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontName=title_font, textColor=HexColor("#2C2420"), fontSize=18, spaceAfter=12)
            heading_style = ParagraphStyle("CustomHeading", parent=styles["Heading2"], fontName=title_font, textColor=HexColor("#2C2420"), fontSize=14, spaceAfter=8)
            body_style = ParagraphStyle("CustomBody", parent=styles["Normal"], fontName=body_font, textColor=HexColor("#2C2420"), fontSize=10, leading=16, spaceAfter=6)

            elements = []
            elements.append(Paragraph("Gold Detector - Resume Report", title_style))
            elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
            elements.append(Spacer(1, 12))

            elements.append(Paragraph("Report", heading_style))
            for para in report_text.split("\n\n"):
                if para.strip():
                    safe_text = para.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
                    elements.append(Paragraph(safe_text, body_style))

            if match_score is not None:
                elements.append(Paragraph("Match Score", heading_style))
                score_style = ParagraphStyle("Score", parent=body_style, fontSize=20, textColor=HexColor("#B8908A"))
                elements.append(Paragraph(f"{match_score}", score_style))

            if strengths:
                elements.append(Paragraph("Core Strengths", heading_style))
                for s in strengths:
                    safe_s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    elements.append(Paragraph(f"• {safe_s}", body_style))

            elements.append(Spacer(1, 20))
            footer_style = ParagraphStyle("Footer", parent=body_style, textColor=HexColor("#9E8E83"), fontSize=8)
            elements.append(Paragraph("Workplace Mirror", footer_style))

            doc.build(elements)
            return buf.getvalue()
        except Exception as e:
            # 最终降级：返回HTML文件但改名为PDF
            return html_content.encode("utf-8")


# ===== 渲染：输入区 =====

def _render_input_area() -> None:
    adapter = EmotionAdapter.from_session()
    if adapter.get_layout_mode() == "single_column":
        st.info("💡 一次看一个板块就好，不急。探测完成后报告会为你简化展示。")

    uploaded_file = st.file_uploader(
        "上传简历（支持PDF）",
        type=["pdf"],
        key="resume_upload",
    )
    if uploaded_file and st.session_state.gold_upload_name != uploaded_file.name:
        with st.spinner("正在解析PDF..."):
            try:
                import pdfplumber

                pdf_bytes = io.BytesIO(uploaded_file.read())
                with pdfplumber.open(pdf_bytes) as pdf:
                    resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                st.session_state.gold_resume_text = resume_text
                st.session_state.gold_upload_name = uploaded_file.name
                if "gold_resume_input" in st.session_state:
                    st.session_state.gold_resume_input = resume_text
            except ModuleNotFoundError:
                st.error("PDF解析依赖未安装：请执行 `python -m pip install pdfplumber` 后重试。")
            except Exception as exc:
                st.error(f"PDF解析失败：{exc}")

    resume = st.text_area(
        "简历内容",
        placeholder="把你的简历粘贴到这里，或上传PDF文件...",
        height=250,
        key="gold_resume_input",
    )

    st.markdown("### 📋 岗位描述（可添加多个对比）")

    for i, jd_item in enumerate(st.session_state.gold_jd_list):
        col_name, col_content, col_remove = st.columns([1, 6, 1])
        with col_name:
            jd_item["name"] = st.text_input(
                "岗位名称",
                value=jd_item.get("name", f"岗位{i + 1}"),
                key=f"jd_name_{i}",
                label_visibility="collapsed",
                placeholder=f"岗位{i + 1}名称",
            )
        with col_content:
            jd_item["content"] = st.text_area(
                "JD内容",
                value=jd_item.get("content", ""),
                height=120,
                key=f"jd_content_{i}",
                label_visibility="collapsed",
                placeholder=f"粘贴岗位{i + 1}的JD...",
            )
        with col_remove:
            if len(st.session_state.gold_jd_list) > 1:
                if st.button("✕", key=f"jd_remove_{i}"):
                    st.session_state.gold_jd_list.pop(i)
                    st.rerun()

    if len(st.session_state.gold_jd_list) < 3:
        if st.button("＋ 添加岗位对比", key="add_jd"):
            idx = len(st.session_state.gold_jd_list) + 1
            st.session_state.gold_jd_list.append({"name": f"岗位{idx}", "content": ""})
            st.rerun()

    st.session_state.gold_resume_text = st.session_state.get("gold_resume_input", "")
    jd_text = st.session_state.gold_jd_list[0]["content"] if st.session_state.gold_jd_list else ""
    st.session_state.gold_jd_text = jd_text

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("开始探测", type="primary"):
            if not resume.strip():
                st.warning("请先输入或上传简历")
            else:
                st.session_state.gold_pending_probe = {
                    "resume": resume,
                    "jd_list": list(st.session_state.gold_jd_list),
                }
                st.session_state.gold_probe_running = True
                st.rerun()
    with col2:
        if st.button("清空"):
            st.session_state.gold_resume_text = ""
            st.session_state.gold_jd_text = ""
            st.session_state.gold_jd_list = [{"name": "岗位1", "content": ""}]
            st.session_state.gold_upload_name = None
            if "gold_resume_input" in st.session_state:
                st.session_state.gold_resume_input = ""
            st.rerun()


# ===== 渲染：右列主内容 =====

def _render_main_content() -> None:
    """渲染右列主内容区"""
    # ===== 如果有待执行的探测，在这里跑（进度在右列可见） =====
    if st.session_state.get("gold_pending_probe"):
        probe_data = st.session_state.gold_pending_probe
        st.session_state.gold_probe_running = True

        st.markdown("### 🔍 正在分析你的简历...")
        st.markdown(
            '<div style="color:#8C8279; font-size:13px;">预计需要1-2分钟，请耐心等待</div>',
            unsafe_allow_html=True,
        )
        st.info("探测任务已启动，正在执行中，请勿重复点击或刷新页面。")

        try:
            jd_list = probe_data.get("jd_list")
            if jd_list is None:
                legacy_jd = probe_data.get("jd", "")
                jd_list = [{"name": "岗位1", "content": legacy_jd}] if legacy_jd else [{"name": "岗位1", "content": ""}]

            result = _run_detection(probe_data["resume"], jd_list)
            primary_jd = (jd_list[0].get("content") or "") if jd_list else ""
            _save_conversation(result, probe_data["resume"], primary_jd, jd_list=jd_list)
            st.session_state.gold_pending_probe = None
            st.session_state.gold_flash_message = "探测完成！"
            st.session_state.gold_flash_type = "success"
            st.rerun()
            return
        except Exception as e:
            from ui.error_handler import get_friendly_message

            logger.warning("[gold_detector] %s: %s", type(e).__name__, e)
            st.session_state.gold_pending_probe = None
            st.session_state.gold_flash_message = get_friendly_message(e)
            st.session_state.gold_flash_type = "error"
            st.session_state.gold_show_input = True
            st.rerun()
            return
        finally:
            st.session_state.gold_probe_running = False

    # ===== Flash 消息 =====
    flash_msg = st.session_state.get("gold_flash_message")
    if flash_msg:
        flash_type = st.session_state.get("gold_flash_type", "info")
        if flash_type == "success":
            st.success(flash_msg)
        elif flash_type == "error":
            st.error(flash_msg)
        else:
            st.info(flash_msg)
        st.session_state.gold_flash_message = None

    # ===== 正常内容 =====
    if st.session_state.get("gold_show_input"):
        _render_input_area()
        return

    conv_id = st.session_state.get("gold_current_conv_id")
    conv = next((c for c in st.session_state.gold_conversations if c["id"] == conv_id), None)
    if conv:
        st.session_state.gold_current_result = conv["result"]
        _render_result_block(conv["result"])
    else:
        current_result = st.session_state.get("gold_current_result")
        if current_result:
            _render_result_block(current_result)
        else:
            st.session_state.gold_show_input = True
            _render_input_area()


# ===== 主入口 =====

def render():
    track_module_enter("金子探测器")
    _inject_styles()
    _init_state()

    render_page_header("金子探测器", "把经历放上来，看看你的核心竞争力")
    apply_emotion_breath()

    # 主体：左列历史（窄） + 右列内容（宽）
    col_history, col_content = st.columns([1, 7], gap="small")

    with col_history:
        _render_history_sidebar()

    with col_content:
        _render_main_content()
