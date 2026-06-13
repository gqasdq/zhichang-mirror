"""职业基因 - 结果展示区（Tab 分层布局）。"""

from __future__ import annotations

import re
from html import escape, unescape
from typing import Any, Callable, Dict, List

import streamlit as st

from core.analytics import track_module_enter
from core.gene_engine import (
    GENE_DIMENSIONS,
    build_gene_summary,
    build_job_match_analysis,
    build_surprise_insight,
    extract_gene_scores_from_result,
    map_gene_to_jobs,
)
from ui.emotion_theme import apply_emotion_breath
from utils.emotion_adapter import EmotionAdapter

ACCENT = "#B8908A"
TEXT = "#2C2420"
MUTED = "#8C8279"
LIGHT = "#E8E2DC"

_PRIORITY_GENE_NAMES = ("空间思维", "数据敏感", "组织号召", "逻辑推演", "自律执行")


def _inject_tab_styles() -> None:
    st.markdown(
        f"""
<style>
.gene-result-summary {{
    text-align: center;
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
    line-height: 1.65;
    margin: 8px 0 14px;
    padding: 0 8px;
}}
.gene-tab-caption {{
    color: {MUTED};
    font-size: 12px;
    margin: -4px 0 10px;
}}
.gene-compact-card {{
    background: rgba(184,144,138,0.08);
    border-radius: 10px;
    padding: 10px 12px;
    border: 1px solid rgba(184,144,138,0.15);
    min-height: 78px;
    margin-bottom: 6px;
}}
.gene-compact-name {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT};
    line-height: 1.35;
}}
.gene-compact-level {{
    font-size: 12px;
    color: {ACCENT};
    font-weight: 600;
    margin: 2px 0 4px;
}}
.gene-compact-verdict {{
    font-size: 11px;
    color: {MUTED};
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}}
.gene-match-col .gene-match-job {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
    margin-bottom: 2px;
}}
.gene-match-col .gene-match-pct {{
    font-size: 22px;
    font-weight: 700;
    color: {ACCENT};
    line-height: 1.1;
    margin-bottom: 4px;
}}
.gene-match-col .gene-match-pct small {{
    font-size: 12px;
}}
.gene-match-col .gene-match-label {{
    font-size: 11px;
    color: {ACCENT};
    font-weight: 600;
    margin: 6px 0 2px;
}}
.gene-match-col .gene-match-text {{
    font-size: 11px;
    color: {MUTED};
    line-height: 1.45;
}}
.gene-match-col .gene-match-fix {{
    font-size: 11px;
    color: {TEXT};
    line-height: 1.45;
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px dashed rgba(184,144,138,0.2);
}}
.gene-match-col {{
    background: #FFFFFF;
    border-radius: 12px;
    border: 1px solid rgba(184,144,138,0.12);
    border-left: 3px solid {ACCENT};
    padding: 12px 12px 10px;
    margin-bottom: 4px;
}}
.gene-match-col div[data-testid="stProgressBar"] {{
    margin-top: 2px !important;
    margin-bottom: 6px !important;
}}
.gene-match-col div[data-testid="stProgressBar"] > div {{
    height: 5px !important;
}}
.gene-match-col div[data-testid="stProgressBar"] > div > div {{
    background-color: {ACCENT} !important;
}}
.combo-block {{
    background: rgba(255,255,255,0.65);
    border-radius: 10px;
    padding: 10px 14px;
    border: 1px solid {LIGHT};
    margin-bottom: 8px;
}}
.combo-block-title {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT};
    margin-bottom: 4px;
}}
.combo-block-line {{
    font-size: 12px;
    color: {MUTED};
    line-height: 1.5;
    margin-bottom: 2px;
}}
.job-list-item {{
    padding: 12px 0 10px;
}}
.job-list-head {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 6px;
}}
.job-list-name {{
    font-size: 15px;
    font-weight: 600;
    color: {TEXT};
}}
.job-dir-tag {{
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    line-height: 1;
    padding: 4px 8px;
    border-radius: 999px;
    white-space: nowrap;
}}
.job-dir-tag-primary {{
    background: {ACCENT};
    color: #FFFFFF;
    border: 1px solid {ACCENT};
}}
.job-dir-tag-secondary, .job-dir-tag-cross {{
    background: transparent;
    color: {ACCENT};
    border: 1px solid {ACCENT};
}}
.job-dir-tag-safe {{
    background: transparent;
    color: #9E8E83;
    border: 1px solid #C4BAB0;
}}
.job-list-reason {{
    font-size: 13px;
    color: {MUTED};
    line-height: 1.65;
    margin-bottom: 8px;
}}
.job-list-divider {{
    border-top: 1px solid rgba(184,144,138,0.14);
    margin: 0;
}}
.job-detail-block {{
    background: rgba(255,255,255,0.72);
    border-radius: 10px;
    border: 1px solid {LIGHT};
    padding: 12px 14px;
    margin: 8px 0 6px;
}}
.job-detail-label {{
    font-size: 11px;
    color: {ACCENT};
    font-weight: 600;
    margin: 8px 0 3px;
}}
.job-detail-label:first-child {{
    margin-top: 0;
}}
.job-detail-text {{
    font-size: 13px;
    color: {TEXT};
    line-height: 1.65;
}}
.job-deep-block {{
    background: rgba(184,144,138,0.06);
    border-radius: 10px;
    border: 1px solid rgba(184,144,138,0.14);
    padding: 12px 14px;
    margin: 10px 0 8px;
}}
.job-deep-title {{
    font-size: 13px;
    font-weight: 600;
    color: {ACCENT};
    margin: 10px 0 6px;
}}
.job-deep-title:first-child {{
    margin-top: 0;
}}
.job-deep-text {{
    font-size: 13px;
    color: {TEXT};
    line-height: 1.65;
}}
.hidden-mini, .trap-mini {{
    background: rgba(255,255,255,0.7);
    border-radius: 10px;
    padding: 8px 10px;
    border: 1px solid {LIGHT};
    margin-bottom: 6px;
    font-size: 12px;
    color: {TEXT};
}}
.gene-section-divider {{
    border-top: 1px solid rgba(184,144,138,0.18);
    margin: 16px 0 14px;
}}
div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    gap: 6px;
}}
div[data-testid="stTabs"] [data-baseweb="tab"] {{
    padding-top: 8px;
    padding-bottom: 8px;
}}
.st-key-gene_match_detail button {{
    background-color: {ACCENT} !important;
    border-color: {ACCENT} !important;
    color: #FFFFFF !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _clean_for_html(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"```[\w-]*\s*", "", raw)
    raw = raw.replace("```", " ")
    normalized = unescape(raw)
    if re.search(r"</?[a-zA-Z][^>]*>", normalized):
        normalized = re.sub(r"(?i)<br\s*/?>", "\n", normalized)
        normalized = re.sub(r"(?i)</(div|p|ul|ol|li|h[1-6]|tr|td|th)>", "\n", normalized)
        normalized = re.sub(r"(?i)<li[^>]*>", "- ", normalized)
        normalized = re.sub(r"<[^>]+>", " ", normalized)
    else:
        normalized = raw
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    return escape(" ".join(lines))


def _gene_description(gene: Dict[str, Any]) -> str:
    reason = str(gene.get("等级判定理由", "")).strip()
    if reason:
        return reason
    evidence_chain = gene.get("证据链", [])
    if isinstance(evidence_chain, list) and evidence_chain:
        first = evidence_chain[0]
        if isinstance(first, dict):
            return str(first.get("证据内容", "")).strip()
    return ""


def _short_verdict(text: str, limit: int = 36) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _reason_preview(text: str, max_sentences: int = 2) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return ""
    parts = [part.strip() for part in re.split(r"(?<=[。！？!?])\s*", cleaned) if part.strip()]
    if not parts:
        return cleaned
    preview = "".join(parts[:max_sentences])
    return preview or cleaned


def _direction_tag_meta(job_type: str) -> tuple[str, str]:
    raw = str(job_type or "").strip()
    if "首选" in raw:
        return "首选", "primary"
    if "次选" in raw:
        return "次选", "secondary"
    if "跨界" in raw:
        return "跨界", "cross"
    if "保守" in raw:
        return "保守", "safe"
    label = raw.replace("方向", "").strip() or "方向"
    return label, "secondary"


def _direction_tag_html(job_type: str) -> str:
    label, style = _direction_tag_meta(job_type)
    return f'<span class="job-dir-tag job-dir-tag-{style}">{escape(label)}</span>'


def _format_dim_list(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "暂无"
    return " · ".join(f"{item['dim']}{item['score']}" for item in items)


def _pick_display_genes(result: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    genes = result.get("显性基因", [])
    if not isinstance(genes, list):
        return []
    valid = [g for g in genes if isinstance(g, dict)]
    if not valid:
        return []

    picked: List[Dict[str, Any]] = []
    used_names = set()
    for name in _PRIORITY_GENE_NAMES:
        for gene in valid:
            gene_name = str(gene.get("基因名称", "")).strip()
            if gene_name == name and gene_name not in used_names:
                picked.append(gene)
                used_names.add(gene_name)
                break
        if len(picked) >= limit:
            break

    if len(picked) < limit:
        for gene in valid:
            gene_name = str(gene.get("基因名称", "")).strip()
            if gene_name in used_names:
                continue
            picked.append(gene)
            used_names.add(gene_name)
            if len(picked) >= limit:
                break
    return picked[:limit]


def _render_radar_chart(gene_scores: Dict[str, int]) -> None:
    try:
        from streamlit_echarts import st_echarts
    except ImportError:
        st.caption(" · ".join(f"{dim} {gene_scores.get(dim, 50)}" for dim in GENE_DIMENSIONS))
        return

    indicators = [{"name": dim, "max": 100} for dim in GENE_DIMENSIONS]
    values = [gene_scores.get(dim, 50) for dim in GENE_DIMENSIONS]
    option = {
        "color": [ACCENT],
        "radar": {
            "indicator": indicators,
            "radius": "62%",
            "splitNumber": 4,
            "axisName": {"color": MUTED, "fontSize": 11},
            "splitLine": {"lineStyle": {"color": "rgba(184,144,138,0.25)"}},
            "splitArea": {"show": False},
            "axisLine": {"lineStyle": {"color": "rgba(184,144,138,0.35)"}},
        },
        "series": [
            {
                "type": "radar",
                "data": [{"value": values, "name": "基因得分", "areaStyle": {"opacity": 0.18}}],
                "lineStyle": {"width": 2},
                "symbolSize": 4,
            }
        ],
    }
    st_echarts(options=option, height="260px")


def _render_compact_gene_card(gene: Dict[str, Any], index: int, highlight: bool = False) -> None:
    level = max(1, min(5, int(gene.get("等级", 3) or 3)))
    name = _clean_for_html(gene.get("基因名称", ""))
    verdict = _short_verdict(_gene_description(gene))
    detail = _clean_for_html(_gene_description(gene))
    code = _clean_for_html(gene.get("基因编码", ""))
    card_class = "gene-compact-card highlight-done" if highlight else "gene-compact-card"

    st.markdown(
        f"""
<div class="{card_class}" style="border-color: var(--emotion-accent, {ACCENT});">
    <div class="gene-compact-name">{name}</div>
    <div class="gene-compact-level">Lv.{level}</div>
    <div class="gene-compact-verdict">{escape(verdict) or "点击查看详细判定"}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.expander("详细说明", expanded=False):
        if code:
            st.caption(f"基因编码：{code}")
        st.markdown(detail or "暂无详细说明")


def _render_gene_map_tab(result: Dict[str, Any], gene_scores: Dict[str, int]) -> None:
    adapter = EmotionAdapter.from_session()
    if adapter.get_layout_mode() == "guided":
        adapter.render_guided_steps(
            ["① 先看雷达图整体轮廓", "② 再看每个基因的详情", "③ 最后看成长路径建议"],
            title="跟着这三步看基因",
        )

    st.markdown(
        f'<div class="gene-tab-caption">8 维度基因雷达 + 核心显性基因一览</div>',
        unsafe_allow_html=True,
    )
    _render_radar_chart(gene_scores)

    genes = _pick_display_genes(result, limit=5)
    if adapter.emotion == EmotionAdapter.FRUSTRATED:
        genes = sorted(
            genes,
            key=lambda g: int(g.get("等级", 0) or 0),
            reverse=True,
        )
    if not genes:
        st.caption("暂无显性基因数据")
        return

    row1 = genes[:3]
    row2 = genes[3:5]
    cols1 = st.columns(3)
    for idx, gene in enumerate(row1):
        with cols1[idx]:
            _render_compact_gene_card(gene, idx, highlight=(adapter.emotion == EmotionAdapter.FRUSTRATED and idx == 0))

    if row2:
        cols2 = st.columns(3)
        for idx, gene in enumerate(row2):
            with cols2[idx]:
                _render_compact_gene_card(gene, idx + 3)


def _render_match_column(job_match: Dict[str, Any]) -> None:
    job_name = str(job_match.get("job", ""))
    match_pct = int(job_match.get("match", 0))
    strengths = _format_dim_list(job_match.get("strengths", []))
    gaps = _format_dim_list(job_match.get("gaps", []))
    fix_text = str(job_match.get("fix", ""))

    st.markdown(
        f"""
<div class="gene-match-col">
    <div class="gene-match-job">{escape(job_name)}</div>
    <div class="gene-match-pct">{match_pct}<small>%</small></div>
    <div class="gene-match-label">优势</div>
    <div class="gene-match-text">{escape(strengths)}</div>
    <div class="gene-match-label">短板</div>
    <div class="gene-match-text">{escape(gaps)}</div>
    <div class="gene-match-label">补救</div>
    <div class="gene-match-fix">{escape(fix_text)}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.progress(match_pct / 100)


def _render_career_path_tab(result: Dict[str, Any]) -> None:
    """成长路径标签页：基于基因数据推演发展路径。"""
    from components.career_path_card import render_career_path
    from engines.career_path_engine import CareerPathEngine

    st.markdown("#### 📈 成长路径图")
    st.markdown(
        f'<div class="gene-tab-caption">基于你的职业基因，推演2-3条发展路径</div>',
        unsafe_allow_html=True,
    )

    resume_text = st.session_state.get("gene_user_input", "")
    cache_key = f"{result.get('analysis_timestamp', '')}_{len(resume_text)}"

    if st.session_state.get("career_path_cache_key") != cache_key:
        with st.spinner("正在生成成长路径..."):
            engine = CareerPathEngine()
            path_result = engine.generate(resume_text, gene_data=result)
            st.session_state.career_path_result = path_result
            st.session_state.career_path_cache_key = cache_key

    path_result = st.session_state.get("career_path_result")
    if not path_result or getattr(path_result, "error", False) or not path_result.paths:
        st.info("成长路径暂时不可用，请稍后重试。")
        return

    render_career_path(path_result)


def _render_job_match_tab(
    job_matches: List[Dict[str, Any]],
    gene_scores: Dict[str, int],
) -> None:
    st.markdown("#### 🧬 你的基因最适合什么？")
    st.markdown(
        f'<div class="gene-tab-caption">基于 8 维度得分匹配最契合方向</div>',
        unsafe_allow_html=True,
    )

    if not job_matches:
        st.info("暂未匹配到岗位方向，可以先完成一次完整测序。")
        return

    cols = st.columns(3)
    for idx, job_match in enumerate(job_matches[:3]):
        with cols[idx]:
            _render_match_column(job_match)

    if "gene_match_detail_open" not in st.session_state:
        st.session_state.gene_match_detail_open = False

    if st.button("详细匹配分析", key="gene_match_detail", use_container_width=True):
        st.session_state.gene_match_detail_open = not st.session_state.gene_match_detail_open
        st.rerun()

    if st.session_state.gene_match_detail_open:
        st.markdown(
            f'<div class="gene-tab-caption">各岗位核心维度与你的得分对比</div>',
            unsafe_allow_html=True,
        )
        for job_match in job_matches:
            st.markdown(build_job_match_analysis(job_match, gene_scores))


def _parse_job_deep_sections(content: str) -> Dict[str, str]:
    """从 AI 深度解析中提取三个核心章节。"""
    raw = str(content or "").strip()
    if not raw:
        return {}

    sections: Dict[str, str] = {}
    title_map = {
        "gene_match": "基因-岗位深度匹配",
        "companies": "真实公司推荐",
        "path": "3个月入门路径",
    }
    chunks = re.split(r"\n(?=##\s)", raw)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        header = chunk.split("\n", 1)[0]
        body = chunk.split("\n", 1)[1].strip() if "\n" in chunk else ""
        for key, keyword in title_map.items():
            if keyword in header:
                sections[key] = body
                break
    return sections


def _render_job_deep_block(cached: str) -> None:
    sections = _parse_job_deep_sections(cached)
    labels = {
        "gene_match": "基因-岗位深度匹配",
        "companies": "真实公司推荐",
        "path": "3个月入门路径",
    }
    rendered = False
    for key, title in labels.items():
        body = sections.get(key, "").strip()
        if not body:
            continue
        rendered = True
        st.markdown(
            f'<div class="job-deep-block"><div class="job-deep-title">{escape(title)}</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(body)

    if not rendered and cached.strip():
        st.markdown(f'<div class="job-deep-block">', unsafe_allow_html=True)
        st.markdown(cached.strip())


def _render_job_detail_block(
    job: Dict[str, Any],
    job_market_text: Callable[[Dict[str, Any]], str],
) -> None:
    salary = job.get("薪资范围", {}) if isinstance(job.get("薪资范围", {}), dict) else {}
    salary_line = (
        f"应届 {escape(str(salary.get('应届生', '-')))} · "
        f"3年 {escape(str(salary.get('三年经验', '-')))} · "
        f"5年 {escape(str(salary.get('五年经验', '-')))}"
    )
    st.markdown(
        f"""
<div class="job-detail-block">
    <div class="job-detail-label">为什么适合你</div>
    <div class="job-detail-text">{_clean_for_html(job.get("为什么适合你", "")) or "暂无"}</div>
    <div class="job-detail-label">市场需求</div>
    <div class="job-detail-text">{escape(job_market_text(job)) or "暂无"}</div>
    <div class="job-detail-label">薪资范围</div>
    <div class="job-detail-text">{salary_line}</div>
    <div class="job-detail-label">入门第一步</div>
    <div class="job-detail-text">{_clean_for_html(job.get("入门第一步", "")) or "暂无"}</div>
    <div class="job-detail-label">3年后你可能的状态</div>
    <div class="job-detail-text">{_clean_for_html(job.get("三年后画面", "")) or "暂无"}</div>
    <div class="job-detail-label">风险提示</div>
    <div class="job-detail-text">{_clean_for_html(job.get("风险提示", "")) or "暂无"}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_recommended_job_row(
    job: Dict[str, Any],
    index: int,
    job_market_text: Callable[[Dict[str, Any]], str],
) -> None:
    if not isinstance(job, dict):
        return

    if "gene_job_detail_open" not in st.session_state:
        st.session_state.gene_job_detail_open = {}

    job_name = str(job.get("岗位名称", "")).strip()
    job_type = str(job.get("方向类型", "")).strip()
    is_open = bool(st.session_state.gene_job_detail_open.get(index))

    st.markdown(
        f"""
<div class="job-list-item">
    <div class="job-list-head">
        <span class="job-list-name">{escape(job_name)}</span>
        {_direction_tag_html(job_type)}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    _render_job_detail_block(job, job_market_text)

    if is_open:
        cached = st.session_state.gene_detail_cache.get(index)
        if cached:
            _render_job_deep_block(cached)
        if st.button("收起", key=f"gene_collapse_btn_{index}"):
            st.session_state.gene_job_detail_open.pop(index, None)
            if index in st.session_state.gene_detail_cache:
                del st.session_state.gene_detail_cache[index]
            st.rerun()
    elif st.button("查看详情", key=f"gene_detail_btn_{index}"):
        st.session_state.gene_job_detail_open[index] = True
        st.session_state.gene_detail_loading = index
        st.rerun()


def _render_hidden_genes_compact(result: Dict[str, Any]) -> None:
    hidden_genes = result.get("隐藏基因", [])
    if not isinstance(hidden_genes, list) or not hidden_genes:
        st.caption("暂无隐藏基因推断")
        return

    cols = st.columns(2)
    for idx, item in enumerate(hidden_genes):
        if not isinstance(item, dict):
            continue
        with cols[idx % 2]:
            name = str(item.get("基因名称", "")).strip()
            with st.expander(f"🔍 {name} · 推断 Lv.{item.get('推断等级', '')}", expanded=False):
                st.markdown(f"**推断逻辑**  \n{item.get('推断逻辑', '')}")
                st.markdown(f"**证据来源**  \n{item.get('证据来源', '')}")
                st.markdown(f"**验证方式**  \n{item.get('验证方式', '')}")


def _render_traps_compact(result: Dict[str, Any]) -> None:
    traps = result.get("基因陷阱预警", [])
    if not isinstance(traps, list) or not traps:
        st.caption("暂无陷阱预警")
        return

    for idx, trap in enumerate(traps):
        if not isinstance(trap, dict):
            continue
        name = str(trap.get("陷阱名称", "")).strip()
        with st.expander(f"⚠️ {name}", expanded=False):
            signals = trap.get("识别信号", [])
            cures = trap.get("解药", [])
            signal_text = "；".join(str(x) for x in signals) if isinstance(signals, list) else str(signals or "")
            cure_text = "；".join(str(x) for x in cures) if isinstance(cures, list) else str(cures or "")
            st.markdown(f"**触发场景**  \n{trap.get('触发场景', '')}")
            st.markdown(f"**成因分析**  \n{trap.get('成因分析', '')}")
            if signal_text:
                st.markdown(f"**识别信号**  \n{signal_text}")
            st.markdown(f"**解药**  \n{cure_text}")


def _render_recommended_jobs_section(
    result: Dict[str, Any],
    job_market_text: Callable[[Dict[str, Any]], str],
) -> None:
    st.markdown("#### 岗位方向推荐")
    st.markdown(
        f'<div class="gene-tab-caption">基于基因组合匹配的 AI 推荐方向</div>',
        unsafe_allow_html=True,
    )

    jobs = result.get("推荐岗位方向", [])
    if not isinstance(jobs, list) or not jobs:
        st.caption("暂无推荐岗位方向")
        return

    for index, job in enumerate(jobs):
        _render_recommended_job_row(job, index, job_market_text)
        if index < len(jobs) - 1:
            st.markdown('<div class="job-list-divider"></div>', unsafe_allow_html=True)


def _render_surprise_section(surprise: str) -> None:
    st.markdown("#### 意外发现")
    st.info(surprise)


def _render_combo_tab(result: Dict[str, Any]) -> None:
    combo = result.get("基因组合分析", {})
    if not isinstance(combo, dict):
        combo = {}

    st.markdown("#### 基因组合分析")
    if any(combo.values()):
        st.markdown(
            f"""
<div class="combo-block">
    <div class="combo-block-title">{_clean_for_html(combo.get("组合名称", ""))}</div>
    <div class="combo-block-line">核心基因型：{_clean_for_html(combo.get("核心基因型", ""))}</div>
    <div class="combo-block-line">组合优势：{_clean_for_html(combo.get("组合优势", ""))}</div>
    <div class="combo-block-line">组合短板：{_clean_for_html(combo.get("组合短板", ""))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    else:
        st.caption("暂无基因组合分析")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            f'<div class="combo-block"><div class="combo-block-title">基因型总结</div>'
            f'<div class="combo-block-line">{_clean_for_html(combo.get("核心基因型", "") or "待测序后生成")}</div></div>',
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            f'<div class="combo-block"><div class="combo-block-title">定位总结</div>'
            f'<div class="combo-block-line">{_clean_for_html(combo.get("组合优势", "") or "待测序后生成")}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("#### 隐藏基因")
    _render_hidden_genes_compact(result)

    st.markdown("#### 基因陷阱预警")
    _render_traps_compact(result)


def render_gene_result_tabs(
    result: Dict[str, Any],
    job_market_text: Callable[[Dict[str, Any]], str],
) -> None:
    """Tab 分层展示测序结果，一句话总结始终置顶。"""
    if not isinstance(result, dict):
        return

    _inject_tab_styles()
    apply_emotion_breath()
    gene_scores = extract_gene_scores_from_result(result)
    summary = build_gene_summary(gene_scores)
    job_matches = map_gene_to_jobs(gene_scores, top_n=3)
    surprise = build_surprise_insight(gene_scores, job_matches)

    st.markdown(
        f'<div class="gene-result-summary">{escape(summary)}</div>',
        unsafe_allow_html=True,
    )

    tab_map, tab_path, tab_combo = st.tabs(["基因图谱", "成长路径", "基因组合"])

    with tab_map:
        _render_gene_map_tab(result, gene_scores)

    with tab_path:
        _render_career_path_tab(result)

    with tab_combo:
        _render_combo_tab(result)

    st.markdown('<div class="gene-section-divider"></div>', unsafe_allow_html=True)
    _render_surprise_section(surprise)


def render_gene_job_match(result: Dict[str, Any]) -> None:
    """兼容旧调用：完整 Tab 结果区。"""
    render_gene_result_tabs(result, job_market_text=lambda job: "")


def render():
    track_module_enter("职业基因")
    st.title("职业基因")
    st.write("请从侧边栏进入完整测序流程。")
