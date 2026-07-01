"""
职业基因 - 基因测序师
职场镜子第四核心模块

交互流程：
1. 输入简历或描述当前状况
2. 点击「开始测序」
3. 展示基因图谱、岗位方向、隐藏基因、基因陷阱
4. 点击岗位「查看详情」进行智谱追问
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from html import escape, unescape
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from core.pdf_export import export_gene_report_pdf, format_gene_report_text
from core.analytics import track_module_enter
from components.gene_evolution import render_gene_evolution
from components.smart_navigation import get_career_gene_nav_recommendations, render_smart_nav
from components.thinking_chain import GENE_ANALYSIS_STEPS, run_with_thinking_chain
from core.module_bridge import bridge_gene_to_workshop, render_bridge_hint
from ui.pages.career_gene import render_gene_result_tabs
from ui.design_system import TOKENS, render_insight_card, render_page_header, render_section_title

logger = logging.getLogger(__name__)

try:
    from core.gene_engine import Config, GeneEngine, HistoryManager, repair_gene_result_dict
except Exception as import_error:
    logger.error("GeneEngine import failed: %s", import_error)
    raise


COLORS = {
    "bg": TOKENS["bg"],
    "sidebar": TOKENS["bg_sidebar"],
    "text": TOKENS["ink"],
    "accent": TOKENS["accent"],
    "muted": TOKENS["muted_light"],
    "light": "#E8E2DC",
}


@st.cache_resource
def _get_engine() -> GeneEngine:
    return GeneEngine()


def _get_history_manager() -> HistoryManager:
    return HistoryManager(Config())


def _load_history() -> List[Dict[str, Any]]:
    return _get_history_manager().load()


def _save_history(history: List[Dict[str, Any]]) -> None:
    manager = _get_history_manager()
    manager._history_path.parent.mkdir(parents=True, exist_ok=True)
    manager._history_path.write_text(
        json.dumps(history[-50:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _inject_styles() -> None:
    st.markdown(
        f"""
<style>
/* 职业基因 · 页面专属样式 */
[data-testid="stMainBlockContainer"] {{
    padding-top: 8px !important;
    padding-bottom: 8px !important;
}}

.gene-card {{
    background: rgba(184,144,138,0.08);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
    border: 1px solid rgba(184,144,138,0.15);
}}
.gene-name {{
    font-size: 15px;
    font-weight: 600;
    color: {COLORS["text"]};
    margin-bottom: 6px;
}}
.gene-level-bar {{
    height: 6px;
    background: rgba(184,144,138,0.2);
    border-radius: 3px;
    margin-bottom: 4px;
}}
.gene-level-fill {{
    height: 100%;
    background: {COLORS["accent"]};
    border-radius: 3px;
}}
.gene-desc {{
    font-size: 12px;
    color: {COLORS["muted"]};
    margin-top: 4px;
}}

.combo-card {{
    background: rgba(255,255,255,0.65);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 16px;
    border: 1px solid {COLORS["light"]};
}}
.combo-title {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS["text"]};
    margin-bottom: 8px;
}}
.combo-line {{
    font-size: 13px;
    color: {COLORS["muted"]};
    line-height: 1.6;
    margin-bottom: 4px;
}}

.job-card {{
    background: white;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 16px;
    border: 1px solid {COLORS["light"]};
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}}
.job-title {{
    font-size: 17px;
    font-weight: 600;
    color: {COLORS["text"]};
    margin-bottom: 4px;
}}
.job-type {{
    font-size: 12px;
    color: {COLORS["accent"]};
    margin-bottom: 12px;
}}
.job-section {{ margin-bottom: 10px; }}
.job-label {{
    font-size: 11px;
    color: {COLORS["accent"]};
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}}
.job-content {{
    font-size: 14px;
    color: {COLORS["text"]};
    line-height: 1.7;
}}

.hidden-gene {{
    background: rgba(123,158,135,0.08);
    border-left: 3px solid #7B9E87;
    padding: 14px 18px;
    margin-bottom: 10px;
    border-radius: 0 10px 10px 0;
}}
.hidden-name {{
    font-weight: 600;
    color: #5A7A62;
    margin-bottom: 6px;
}}
.hidden-evidence {{
    font-size: 13px;
    color: {COLORS["muted"]};
    margin-bottom: 6px;
}}
.hidden-question {{
    font-size: 12px;
    color: {COLORS["accent"]};
    font-style: italic;
}}

.trap-card {{
    background: rgba(200,180,160,0.08);
    border-left: 3px solid #C8B4A0;
    padding: 14px 18px;
    margin-bottom: 10px;
    border-radius: 0 10px 10px 0;
}}
.trap-name {{
    font-weight: 600;
    color: #8C6D5A;
    margin-bottom: 6px;
}}
.trap-desc {{
    font-size: 13px;
    color: {COLORS["text"]};
    margin-bottom: 6px;
}}
.trap-tip {{
    font-size: 12px;
    color: {COLORS["accent"]};
    padding-top: 6px;
    border-top: 1px dashed rgba(184,144,138,0.2);
}}

.history-item {{
    padding: 10px 14px;
    border-left: 2px solid rgba(184,144,138,0.3);
    margin-bottom: 8px;
    color: {COLORS["muted"]};
    font-size: 13px;
}}
.history-time {{
    color: #9E8E83;
    font-size: 11px;
}}

.stButton > button {{
    background-color: {COLORS["accent"]} !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s;
}}
.stButton > button:hover {{
    background-color: #A07A74 !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    if "gene_result" not in st.session_state:
        st.session_state.gene_result = None
    if "gene_user_input" not in st.session_state:
        st.session_state.gene_user_input = ""
    if "gene_detail_cache" not in st.session_state:
        st.session_state.gene_detail_cache = {}
    if "gene_history" not in st.session_state:
        st.session_state.gene_history = _load_history()
    if "gene_error" not in st.session_state:
        st.session_state.gene_error = None
    if "gene_sequencing" not in st.session_state:
        st.session_state.gene_sequencing = False
    if "gene_sequencing_text" not in st.session_state:
        st.session_state.gene_sequencing_text = ""
    if "gene_detail_loading" not in st.session_state:
        st.session_state.gene_detail_loading = None
    if "gene_current_job_index" not in st.session_state:  # 新增：记录当前查看的岗位索引
        st.session_state.gene_current_job_index = None


def _read_uploaded_resume(uploaded_file: Any) -> str:
    if uploaded_file is None:
        return ""

    suffix = uploaded_file.name.lower().rsplit(".", 1)[-1] if "." in uploaded_file.name else ""
    raw_bytes = uploaded_file.getvalue()
    if not raw_bytes:
        return ""

    if suffix == "txt":
        for encoding in ("utf-8", "gbk", "gb2312"):
            try:
                return raw_bytes.decode(encoding).strip()
            except Exception:
                continue
        return raw_bytes.decode("utf-8", errors="ignore").strip()

    if suffix == "pdf":
        try:
            import pdfplumber

            text_parts: List[str] = []
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page in pdf.pages:
                    text = (page.extract_text(layout=False) or "").strip()
                    if text:
                        text_parts.append(text)
            if text_parts:
                raw = "\n".join(text_parts).strip()
                # 清理PDF提取的重复字符问题
                import re as _re
                raw = _re.sub(r'(.)\1+', r'\1', raw)
                return raw
        except Exception:
            pass

        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw_bytes))
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
            merged = "\n".join([p for p in pages if p]).strip()
            if merged:
                import re as _re
                merged = _re.sub(r'(.)\1+', r'\1', merged)
                return merged
        except Exception:
            st.warning("PDF 解析失败，请直接粘贴简历文本。")
        return ""

    if suffix == "docx":
        try:
            from docx import Document

            document = Document(uploaded_file)
            lines = [para.text.strip() for para in document.paragraphs if para.text.strip()]
            return "\n".join(lines).strip()
        except Exception:
            st.warning("DOCX 解析失败，请直接粘贴简历文本。")
            return ""

    st.warning("暂不支持该文件格式，请上传 txt / pdf / docx。")
    return ""


def _clean_for_html(text: str) -> str:
    """清理API返回文本：去掉代码围栏/HTML标签，再进行HTML转义。"""
    raw = str(text or "").strip()
    if not raw:
        return ""

    # 去掉 markdown 代码围栏，避免前端出现整段代码块
    raw = re.sub(r"```[\w-]*\s*", "", raw)
    raw = raw.replace("```", " ")

    # 先反转义再判断是否是 HTML 片段，兼容 &lt;div&gt; 这类输入
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


def _format_user_genes(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    for gene in result.get("显性基因", []):
        if not isinstance(gene, dict):
            continue
        lines.append(
            f"- {gene.get('基因名称', '')}（{gene.get('基因编码', '')}）Lv.{gene.get('等级', '')}"
        )
    combo = result.get("基因组合分析", {})
    if isinstance(combo, dict) and combo:
        lines.append(
            f"基因组合：{combo.get('组合名称', '')} / {combo.get('核心基因型', '')}"
        )
        if combo.get("组合优势"):
            lines.append(f"组合优势：{combo.get('组合优势', '')}")
        if combo.get("组合短板"):
            lines.append(f"组合短板：{combo.get('组合短板', '')}")
    return "\n".join(lines)


def _job_market_text(job: Dict[str, Any]) -> str:
    market = job.get("市场需求", {})
    if isinstance(market, dict):
        data = str(market.get("数据", "")).strip()
        source = str(market.get("来源", "")).strip()
        if data and source:
            return f"{data}（{source}）"
        return data or source
    return str(market or "")


def _render_gene_chart(result: Dict[str, Any]) -> None:
    render_section_title("基因图谱")
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:13px; margin-bottom:16px;">'
        "你的核心职业基因</div>",
        unsafe_allow_html=True,
    )

    genes = result.get("显性基因", [])
    if not isinstance(genes, list) or not genes:
        st.markdown(
            f'<div style="color:{COLORS["muted"]}; font-size:13px;">暂无显性基因数据</div>',
            unsafe_allow_html=True,
        )
        return

    for gene in genes:
        if not isinstance(gene, dict):
            continue
        level = int(gene.get("等级", 3) or 3)
        level = max(1, min(5, level))
        fill_width = level * 20
        name = _clean_for_html(gene.get("基因名称", ""))
        code = _clean_for_html(gene.get("基因编码", ""))
        desc = _clean_for_html(_gene_description(gene))
        code_tag = f' <span style="font-size:11px;color:{COLORS["muted"]};">({code})</span>' if code else ""

        st.markdown(
            f"""
<div class="gene-card">
    <div class="gene-name">{name}{code_tag}
        <span style="font-size:12px; color:{COLORS["accent"]};">Lv.{level}</span>
    </div>
    <div class="gene-level-bar">
        <div class="gene-level-fill" style="width:{fill_width}%;"></div>
    </div>
    <div class="gene-desc">{desc}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    combo = result.get("基因组合分析", {})
    if isinstance(combo, dict) and any(combo.values()):
        st.markdown(
            f"""
<div class="combo-card">
    <div class="combo-title">基因组合分析：{_clean_for_html(combo.get("组合名称", ""))}</div>
    <div class="combo-line">核心基因型：{_clean_for_html(combo.get("核心基因型", ""))}</div>
    <div class="combo-line">组合优势：{_clean_for_html(combo.get("组合优势", ""))}</div>
    <div class="combo-line">组合短板：{_clean_for_html(combo.get("组合短板", ""))}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _render_job_card(job: Dict[str, Any], index: int, user_resume: str, result: Dict[str, Any]) -> None:
    if not isinstance(job, dict):
        return

    job_name = str(job.get("岗位名称", "")).strip()
    salary = job.get("薪资范围", {}) if isinstance(job.get("薪资范围", {}), dict) else {}

    html = f"""<div class="job-card"><div class="job-title">{escape(job_name)}</div><div class="job-type">{escape(str(job.get("方向类型", "")))}</div><div class="job-section"><div class="job-label">为什么适合你</div><div class="job-content">{escape(str(job.get("为什么适合你", "")))}</div></div><div class="job-section"><div class="job-label">市场需求</div><div class="job-content">{escape(_job_market_text(job))}</div></div><div class="job-section"><div class="job-label">薪资范围</div><div class="job-content"><span style="color:{COLORS["muted"]};">应届</span> {escape(str(salary.get("应届生", "-")))} &nbsp;|&nbsp; <span style="color:{COLORS["muted"]};">3年</span> {escape(str(salary.get("三年经验", "-")))} &nbsp;|&nbsp; <span style="color:{COLORS["muted"]};">5年</span> {escape(str(salary.get("五年经验", "-")))}</div></div><div class="job-section"><div class="job-label">入门第一步</div><div class="job-content">{escape(str(job.get("入门第一步", "")))}</div></div><div class="job-section" style="margin-bottom:0;"><div class="job-label">3年后你可能的状态</div><div class="job-content" style="font-style:italic;">{escape(str(job.get("三年后画面", "")))}</div></div><div class="job-section" style="margin-top:10px;"><div class="job-label">风险提示</div><div class="job-content">{escape(str(job.get("风险提示", "")))}</div></div></div>"""
    st.markdown(html, unsafe_allow_html=True)

    cached = st.session_state.gene_detail_cache.get(index)
    if cached:
        st.markdown("---")
        st.markdown(cached)
        if st.button("收起详情", key=f"gene_collapse_btn_{index}"):
            del st.session_state.gene_detail_cache[index]
            st.rerun()
    else:
        if st.button("查看详情", key=f"gene_detail_btn_{index}"):
            st.session_state.gene_detail_loading = index
            st.rerun()


def _render_hidden_genes(result: Dict[str, Any]) -> None:
    render_section_title("隐藏基因")
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:13px; margin-bottom:16px;">'
        "简历里没直接体现，但你可能有的基因</div>",
        unsafe_allow_html=True,
    )

    hidden_genes = result.get("隐藏基因", [])
    if not isinstance(hidden_genes, list) or not hidden_genes:
        st.markdown(
            f'<div style="color:{COLORS["muted"]}; font-size:13px;">暂无隐藏基因推断</div>',
            unsafe_allow_html=True,
        )
        return

    for item in hidden_genes:
        if not isinstance(item, dict):
            continue
        st.markdown(
            f"""
<div class="hidden-gene">
    <div class="hidden-name">{_clean_for_html(item.get("基因名称", ""))}
        <span style="font-size:12px;color:{COLORS["accent"]};">推断 Lv.{_clean_for_html(item.get("推断等级", ""))}</span>
    </div>
    <div class="hidden-evidence">推断逻辑：{_clean_for_html(item.get("推断逻辑", ""))}</div>
    <div class="hidden-evidence">证据来源：{_clean_for_html(item.get("证据来源", ""))}</div>
    <div class="hidden-question">验证方式：{_clean_for_html(item.get("验证方式", ""))}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _render_gene_traps(result: Dict[str, Any]) -> None:
    render_section_title("基因陷阱预警")
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:13px; margin-bottom:16px;">'
        "你的基因组合可能导致的选择误区</div>",
        unsafe_allow_html=True,
    )

    traps = result.get("基因陷阱预警", [])
    if not isinstance(traps, list) or not traps:
        st.markdown(
            f'<div style="color:{COLORS["muted"]}; font-size:13px;">暂无陷阱预警</div>',
            unsafe_allow_html=True,
        )
        return

    for trap in traps:
        if not isinstance(trap, dict):
            continue
        signals = trap.get("识别信号", [])
        cures = trap.get("解药", [])
        signal_text = "；".join(str(x) for x in signals) if isinstance(signals, list) else str(signals or "")
        cure_text = "；".join(str(x) for x in cures) if isinstance(cures, list) else str(cures or "")
        desc_parts = [
            str(trap.get("触发场景", "")).strip(),
            str(trap.get("成因分析", "")).strip(),
        ]
        if signal_text:
            desc_parts.append(f"识别信号：{signal_text}")
        description = " ".join(part for part in desc_parts if part)

        st.markdown(
            f"""
<div class="trap-card">
    <div class="trap-name">{_clean_for_html(trap.get("陷阱名称", ""))}</div>
    <div class="trap-desc">{_clean_for_html(description)}</div>
    <div class="trap-tip">解药：{_clean_for_html(cure_text)}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _render_result_state() -> None:
    result = st.session_state.gene_result
    if not isinstance(result, dict):
        st.session_state.gene_result = None
        return

    if result.get("parse_error"):
        repaired = repair_gene_result_dict(result)
        if not repaired.get("parse_error"):
            st.session_state.gene_result = repaired
            result = repaired

    # === 详情加载：必须在任何UI渲染之前执行 ===
    detail_loading = st.session_state.get("gene_detail_loading")
    if detail_loading is not None:
        st.session_state.gene_detail_loading = None
        jobs = result.get("推荐岗位方向", [])
        if isinstance(jobs, list) and 0 <= detail_loading < len(jobs):
            job = jobs[detail_loading]
            if isinstance(job, dict):
                job_name = str(job.get("岗位名称", "")).strip()
                salary = job.get("薪资范围", {}) if isinstance(job.get("薪资范围", {}), dict) else {}
                existing_info = (
                    f"岗位名称：{job_name}\n"
                    f"方向类型：{job.get('方向类型', '')}\n"
                    f"为什么适合你：{job.get('为什么适合你', '')}\n"
                    f"市场需求：{_job_market_text(job)}\n"
                    f"薪资范围：应届{salary.get('应届生', '-')} / 3年{salary.get('三年经验', '-')} / 5年{salary.get('五年经验', '-')}\n"
                    f"入门第一步：{job.get('入门第一步', '')}\n"
                    f"三年后画面：{job.get('三年后画面', '')}\n"
                    f"风险提示：{job.get('风险提示', '')}"
                )
                with st.spinner("正在生成岗位深度解析..."):
                    try:
                        detail = _get_engine().get_job_detail(
                            job_name=job_name,
                            user_resume=st.session_state.gene_user_input,
                            user_genes=_format_user_genes(result),
                            job_market_data=_job_market_text(job),
                            existing_job_info=existing_info,
                        )
                        st.session_state.gene_detail_cache[detail_loading] = detail
                    except Exception as e:
                        from ui.error_handler import handle_api_error

                        handle_api_error(e, context="gene")
                        st.session_state.gene_detail_loading = None
        st.rerun()
        return

    # === 正常UI渲染 ===
    if result.get("parse_error"):
        st.warning(str(result.get("parse_error")))

    render_gene_result_tabs(result, job_market_text=_job_market_text)

    render_gene_evolution(result)

    hint = render_bridge_hint()
    if hint:
        st.info(hint)

    col_w, _ = st.columns([1, 2])
    with col_w:
        if st.button("🔨 带着基因图谱去优化简历", key="gene_to_workshop", use_container_width=True):
            bridge_gene_to_workshop(result)
            from ui.sidebar import navigate_to_page
            navigate_to_page("workshop")
            st.rerun()

    st.caption("🔒 简历原文已从内存中清除，仅保留分析报告")

    gene_report_text = format_gene_report_text(result)
    st.session_state.gene_report = gene_report_text
    if gene_report_text:
        try:
            pdf_bytes = export_gene_report_pdf(gene_report_text)
            st.download_button(
                label="📥 下载基因报告 (PDF)",
                data=pdf_bytes,
                file_name="职场镜子-职业基因报告.pdf",
                mime="application/pdf",
                key="gene_download_pdf",
                use_container_width=True,
            )
        except Exception as e:
            logger.warning("[gene] PDF export failed: %s", e)

    if st.button("重新测序", key="gene_restart", use_container_width=True):
        st.session_state.gene_result = None
        st.session_state.gene_user_input = ""
        st.session_state.gene_detail_cache = {}
        st.session_state.gene_match_detail_open = False
        st.session_state.gene_job_detail_open = {}
        st.session_state.pop("career_path_result", None)
        st.session_state.pop("career_path_cache_key", None)
        st.rerun()

    render_smart_nav(get_career_gene_nav_recommendations(result))


def _render_input_state(resume_text: str) -> None:
    if st.session_state.get("gene_sequencing"):
        text = st.session_state.get("gene_sequencing_text", "")
        try:
            gene_result = run_with_thinking_chain(
                GENE_ANALYSIS_STEPS,
                lambda: _get_engine().sequence(text),
                model_name="DeepSeek V3 · 分析推理",
            )
            st.session_state.gene_result = gene_result.to_dict()
            st.session_state.gene_user_input = text
            st.session_state.pop("career_path_result", None)
            st.session_state.pop("career_path_cache_key", None)
            st.session_state.pop("resume_text", None)
            st.session_state.gene_detail_cache = {}
            st.session_state.gene_history = _load_history()
        except Exception as e:
            from ui.error_handler import handle_api_error

            handle_api_error(e, context="gene")
        finally:
            st.session_state.gene_sequencing = False
            st.session_state.gene_detail_loading = None
        st.rerun()
        return

    if "gene_text_input" not in st.session_state and resume_text.strip():
        st.session_state["gene_text_input"] = resume_text.strip()

    uploaded = st.file_uploader(
        "上传简历文件",
        type=["txt", "pdf", "docx"],
        accept_multiple_files=False,
        key="gene_resume_uploader",
    )
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:12px; margin-top:-6px; margin-bottom:8px;">'
        "或直接粘贴</div>",
        unsafe_allow_html=True,
    )
    if uploaded is not None:
        uploaded_text = _read_uploaded_resume(uploaded)
        if uploaded_text:
            st.session_state["gene_text_input"] = uploaded_text

    user_input = st.text_area(
        "粘贴简历或描述你的现状",
        placeholder="比如：我是xx专业应届生，做过xx相关实习，擅长沟通和数据分析...",
        key="gene_text_input",
        height=160,
    )

    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

    if st.button("开始测序", key="gene_start", use_container_width=True, type="primary"):
        text = (user_input or "").strip()
        if not text:
            st.warning("请输入简历或描述你的现状")
        else:
            st.session_state.gene_sequencing = True
            st.session_state.gene_sequencing_text = text
            st.rerun()

    st.markdown(
        '<div style="color:#9E8E83; font-size:12px; margin-top:16px; text-align:center;">'
        "已有简历会自动填充，也可以直接描述你的情况</div>",
        unsafe_allow_html=True,
    )


def _render_history() -> None:
    history = st.session_state.gene_history
    if not history:
        return

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    with st.expander("历史测序记录", expanded=False):
        if st.button("清空记录", key="gene_clear_history"):
            st.session_state.gene_history = []
            _save_history([])

        for item in reversed(history[-10:]):
            if not isinstance(item, dict):
                continue
            payload = item.get("result", {})
            if not isinstance(payload, dict):
                payload = {}
            genes = payload.get("显性基因", [])
            gene_names: List[str] = []
            if isinstance(genes, list):
                gene_names = [
                    str(g.get("基因名称", ""))
                    for g in genes[:3]
                    if isinstance(g, dict) and g.get("基因名称")
                ]
            genes_str = ", ".join(gene_names)
            created = item.get("created_at") or item.get("time") or ""
            input_preview = escape(str(item.get("input", ""))[:50])
            st.markdown(
                f"""
<div class="history-item">
    {input_preview}...
    <span style="color:{COLORS["accent"]};">[{escape(genes_str)}]</span>
    <span class="history-time"> {escape(str(created))}</span>
</div>
""",
                unsafe_allow_html=True,
            )


def _render_gene_supplement() -> None:
    st.markdown("---")

    render_section_title("测序能发现什么")
    cols = st.columns(3)
    findings = [
        ("显性基因", "你明确知道的优势，但可能低估了它的价值"),
        ("隐藏基因", "你没注意到的潜力，别人却看得见"),
        ("基因陷阱", "优势用过头就是陷阱，比如共情能力强容易讨好"),
    ]
    for i, (title, desc) in enumerate(findings):
        with cols[i]:
            render_insight_card(title, desc)


def render() -> None:
    track_module_enter("职业基因")
    _inject_styles()
    _init_state()

    resume_text = str(
        st.session_state.get("gene_text_input")
        or st.session_state.get("resume_text", "")
        or ""
    )

    render_page_header("职业基因", "测出你能干什么、适合干什么")

    if st.session_state.gene_result:
        _render_result_state()
    else:
        _render_input_state(resume_text)

    _render_history()
    _render_gene_supplement()


if __name__ == "__main__":
    st.set_page_config(page_title="职业基因", page_icon="🧬", layout="wide")
    render()
