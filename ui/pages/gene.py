"""
鑱屼笟鍩哄洜 - 鍩哄洜娴嬪簭甯?鑱屽満闀滃瓙绗洓鏍稿績妯″潡

浜や簰娴佺▼锛?1. 杈撳叆绠€鍘嗘垨鎻忚堪褰撳墠鐘跺喌
2. 鐐瑰嚮銆屽紑濮嬫祴搴忋€?3. 灞曠ず鍩哄洜鍥捐氨銆佸矖浣嶆柟鍚戙€侀殣钘忓熀鍥犮€佸熀鍥犻櫡闃?4. 鐐瑰嚮宀椾綅銆屾煡鐪嬭鎯呫€嶈繘琛屾櫤璋辫拷闂?"""

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
/* 鑱屼笟鍩哄洜 路 椤甸潰涓撳睘鏍峰紡 */
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
    if "gene_current_job_index" not in st.session_state:  # 鏂板锛氳褰曞綋鍓嶆煡鐪嬬殑宀椾綅绱㈠紩
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
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
            logging.getLogger("pdfminer.pdffont").setLevel(logging.ERROR)`nimport pdfplumber

            text_parts: List[str] = []
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page in pdf.pages:
                    text = (page.extract_text(layout=False) or "").strip()
                    if text:
                        text_parts.append(text)
            if text_parts:
                raw = "\n".join(text_parts).strip()
                # 娓呯悊PDF鎻愬彇鐨勯噸澶嶅瓧绗﹂棶棰?                import re as _re
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
            st.warning("PDF 瑙ｆ瀽澶辫触锛岃鐩存帴绮樿创绠€鍘嗘枃鏈€?)
        return ""

    if suffix == "docx":
        try:
            from docx import Document

            document = Document(uploaded_file)
            lines = [para.text.strip() for para in document.paragraphs if para.text.strip()]
            return "\n".join(lines).strip()
        except Exception:
            st.warning("DOCX 瑙ｆ瀽澶辫触锛岃鐩存帴绮樿创绠€鍘嗘枃鏈€?)
            return ""

    st.warning("鏆備笉鏀寔璇ユ枃浠舵牸寮忥紝璇蜂笂浼?txt / pdf / docx銆?)
    return ""


def _clean_for_html(text: str) -> str:
    """娓呯悊API杩斿洖鏂囨湰锛氬幓鎺変唬鐮佸洿鏍?HTML鏍囩锛屽啀杩涜HTML杞箟銆?""
    raw = str(text or "").strip()
    if not raw:
        return ""

    # 鍘绘帀 markdown 浠ｇ爜鍥存爮锛岄伩鍏嶅墠绔嚭鐜版暣娈典唬鐮佸潡
    raw = re.sub(r"```[\w-]*\s*", "", raw)
    raw = raw.replace("```", " ")

    # 鍏堝弽杞箟鍐嶅垽鏂槸鍚︽槸 HTML 鐗囨锛屽吋瀹?&lt;div&gt; 杩欑被杈撳叆
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
    reason = str(gene.get("绛夌骇鍒ゅ畾鐞嗙敱", "")).strip()
    if reason:
        return reason
    evidence_chain = gene.get("璇佹嵁閾?, [])
    if isinstance(evidence_chain, list) and evidence_chain:
        first = evidence_chain[0]
        if isinstance(first, dict):
            return str(first.get("璇佹嵁鍐呭", "")).strip()
    return ""


def _format_user_genes(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    for gene in result.get("鏄炬€у熀鍥?, []):
        if not isinstance(gene, dict):
            continue
        lines.append(
            f"- {gene.get('鍩哄洜鍚嶇О', '')}锛坽gene.get('鍩哄洜缂栫爜', '')}锛塋v.{gene.get('绛夌骇', '')}"
        )
    combo = result.get("鍩哄洜缁勫悎鍒嗘瀽", {})
    if isinstance(combo, dict) and combo:
        lines.append(
            f"鍩哄洜缁勫悎锛歿combo.get('缁勫悎鍚嶇О', '')} / {combo.get('鏍稿績鍩哄洜鍨?, '')}"
        )
        if combo.get("缁勫悎浼樺娍"):
            lines.append(f"缁勫悎浼樺娍锛歿combo.get('缁勫悎浼樺娍', '')}")
        if combo.get("缁勫悎鐭澘"):
            lines.append(f"缁勫悎鐭澘锛歿combo.get('缁勫悎鐭澘', '')}")
    return "\n".join(lines)


def _job_market_text(job: Dict[str, Any]) -> str:
    market = job.get("甯傚満闇€姹?, {})
    if isinstance(market, dict):
        data = str(market.get("鏁版嵁", "")).strip()
        source = str(market.get("鏉ユ簮", "")).strip()
        if data and source:
            return f"{data}锛坽source}锛?
        return data or source
    return str(market or "")


def _render_gene_chart(result: Dict[str, Any]) -> None:
    render_section_title("鍩哄洜鍥捐氨")
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:13px; margin-bottom:16px;">'
        "浣犵殑鏍稿績鑱屼笟鍩哄洜</div>",
        unsafe_allow_html=True,
    )

    genes = result.get("鏄炬€у熀鍥?, [])
    if not isinstance(genes, list) or not genes:
        st.markdown(
            f'<div style="color:{COLORS["muted"]}; font-size:13px;">鏆傛棤鏄炬€у熀鍥犳暟鎹?/div>',
            unsafe_allow_html=True,
        )
        return

    for gene in genes:
        if not isinstance(gene, dict):
            continue
        level = int(gene.get("绛夌骇", 3) or 3)
        level = max(1, min(5, level))
        fill_width = level * 20
        name = _clean_for_html(gene.get("鍩哄洜鍚嶇О", ""))
        code = _clean_for_html(gene.get("鍩哄洜缂栫爜", ""))
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

    combo = result.get("鍩哄洜缁勫悎鍒嗘瀽", {})
    if isinstance(combo, dict) and any(combo.values()):
        st.markdown(
            f"""
<div class="combo-card">
    <div class="combo-title">鍩哄洜缁勫悎鍒嗘瀽锛歿_clean_for_html(combo.get("缁勫悎鍚嶇О", ""))}</div>
    <div class="combo-line">鏍稿績鍩哄洜鍨嬶細{_clean_for_html(combo.get("鏍稿績鍩哄洜鍨?, ""))}</div>
    <div class="combo-line">缁勫悎浼樺娍锛歿_clean_for_html(combo.get("缁勫悎浼樺娍", ""))}</div>
    <div class="combo-line">缁勫悎鐭澘锛歿_clean_for_html(combo.get("缁勫悎鐭澘", ""))}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _render_job_card(job: Dict[str, Any], index: int, user_resume: str, result: Dict[str, Any]) -> None:
    if not isinstance(job, dict):
        return

    job_name = str(job.get("宀椾綅鍚嶇О", "")).strip()
    salary = job.get("钖祫鑼冨洿", {}) if isinstance(job.get("钖祫鑼冨洿", {}), dict) else {}

    html = f"""<div class="job-card"><div class="job-title">{escape(job_name)}</div><div class="job-type">{escape(str(job.get("鏂瑰悜绫诲瀷", "")))}</div><div class="job-section"><div class="job-label">涓轰粈涔堥€傚悎浣?/div><div class="job-content">{escape(str(job.get("涓轰粈涔堥€傚悎浣?, "")))}</div></div><div class="job-section"><div class="job-label">甯傚満闇€姹?/div><div class="job-content">{escape(_job_market_text(job))}</div></div><div class="job-section"><div class="job-label">钖祫鑼冨洿</div><div class="job-content"><span style="color:{COLORS["muted"]};">搴斿眾</span> {escape(str(salary.get("搴斿眾鐢?, "-")))} &nbsp;|&nbsp; <span style="color:{COLORS["muted"]};">3骞?/span> {escape(str(salary.get("涓夊勾缁忛獙", "-")))} &nbsp;|&nbsp; <span style="color:{COLORS["muted"]};">5骞?/span> {escape(str(salary.get("浜斿勾缁忛獙", "-")))}</div></div><div class="job-section"><div class="job-label">鍏ラ棬绗竴姝?/div><div class="job-content">{escape(str(job.get("鍏ラ棬绗竴姝?, "")))}</div></div><div class="job-section" style="margin-bottom:0;"><div class="job-label">3骞村悗浣犲彲鑳界殑鐘舵€?/div><div class="job-content" style="font-style:italic;">{escape(str(job.get("涓夊勾鍚庣敾闈?, "")))}</div></div><div class="job-section" style="margin-top:10px;"><div class="job-label">椋庨櫓鎻愮ず</div><div class="job-content">{escape(str(job.get("椋庨櫓鎻愮ず", "")))}</div></div></div>"""
    st.markdown(html, unsafe_allow_html=True)

    cached = st.session_state.gene_detail_cache.get(index)
    if cached:
        st.markdown("---")
        st.markdown(cached)
        if st.button("鏀惰捣璇︽儏", key=f"gene_collapse_btn_{index}"):
            del st.session_state.gene_detail_cache[index]
            st.rerun()
    else:
        if st.button("鏌ョ湅璇︽儏", key=f"gene_detail_btn_{index}"):
            st.session_state.gene_detail_loading = index
            st.rerun()


def _render_hidden_genes(result: Dict[str, Any]) -> None:
    render_section_title("闅愯棌鍩哄洜")
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:13px; margin-bottom:16px;">'
        "绠€鍘嗛噷娌＄洿鎺ヤ綋鐜帮紝浣嗕綘鍙兘鏈夌殑鍩哄洜</div>",
        unsafe_allow_html=True,
    )

    hidden_genes = result.get("闅愯棌鍩哄洜", [])
    if not isinstance(hidden_genes, list) or not hidden_genes:
        st.markdown(
            f'<div style="color:{COLORS["muted"]}; font-size:13px;">鏆傛棤闅愯棌鍩哄洜鎺ㄦ柇</div>',
            unsafe_allow_html=True,
        )
        return

    for item in hidden_genes:
        if not isinstance(item, dict):
            continue
        st.markdown(
            f"""
<div class="hidden-gene">
    <div class="hidden-name">{_clean_for_html(item.get("鍩哄洜鍚嶇О", ""))}
        <span style="font-size:12px;color:{COLORS["accent"]};">鎺ㄦ柇 Lv.{_clean_for_html(item.get("鎺ㄦ柇绛夌骇", ""))}</span>
    </div>
    <div class="hidden-evidence">鎺ㄦ柇閫昏緫锛歿_clean_for_html(item.get("鎺ㄦ柇閫昏緫", ""))}</div>
    <div class="hidden-evidence">璇佹嵁鏉ユ簮锛歿_clean_for_html(item.get("璇佹嵁鏉ユ簮", ""))}</div>
    <div class="hidden-question">楠岃瘉鏂瑰紡锛歿_clean_for_html(item.get("楠岃瘉鏂瑰紡", ""))}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _render_gene_traps(result: Dict[str, Any]) -> None:
    render_section_title("鍩哄洜闄烽槺棰勮")
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:13px; margin-bottom:16px;">'
        "浣犵殑鍩哄洜缁勫悎鍙兘瀵艰嚧鐨勯€夋嫨璇尯</div>",
        unsafe_allow_html=True,
    )

    traps = result.get("鍩哄洜闄烽槺棰勮", [])
    if not isinstance(traps, list) or not traps:
        st.markdown(
            f'<div style="color:{COLORS["muted"]}; font-size:13px;">鏆傛棤闄烽槺棰勮</div>',
            unsafe_allow_html=True,
        )
        return

    for trap in traps:
        if not isinstance(trap, dict):
            continue
        signals = trap.get("璇嗗埆淇″彿", [])
        cures = trap.get("瑙ｈ嵂", [])
        signal_text = "锛?.join(str(x) for x in signals) if isinstance(signals, list) else str(signals or "")
        cure_text = "锛?.join(str(x) for x in cures) if isinstance(cures, list) else str(cures or "")
        desc_parts = [
            str(trap.get("瑙﹀彂鍦烘櫙", "")).strip(),
            str(trap.get("鎴愬洜鍒嗘瀽", "")).strip(),
        ]
        if signal_text:
            desc_parts.append(f"璇嗗埆淇″彿锛歿signal_text}")
        description = " ".join(part for part in desc_parts if part)

        st.markdown(
            f"""
<div class="trap-card">
    <div class="trap-name">{_clean_for_html(trap.get("闄烽槺鍚嶇О", ""))}</div>
    <div class="trap-desc">{_clean_for_html(description)}</div>
    <div class="trap-tip">瑙ｈ嵂锛歿_clean_for_html(cure_text)}</div>
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

    # === 璇︽儏鍔犺浇锛氬繀椤诲湪浠讳綍UI娓叉煋涔嬪墠鎵ц ===
    detail_loading = st.session_state.get("gene_detail_loading")
    if detail_loading is not None:
        st.session_state.gene_detail_loading = None
        jobs = result.get("鎺ㄨ崘宀椾綅鏂瑰悜", [])
        if isinstance(jobs, list) and 0 <= detail_loading < len(jobs):
            job = jobs[detail_loading]
            if isinstance(job, dict):
                job_name = str(job.get("宀椾綅鍚嶇О", "")).strip()
                salary = job.get("钖祫鑼冨洿", {}) if isinstance(job.get("钖祫鑼冨洿", {}), dict) else {}
                existing_info = (
                    f"宀椾綅鍚嶇О锛歿job_name}\n"
                    f"鏂瑰悜绫诲瀷锛歿job.get('鏂瑰悜绫诲瀷', '')}\n"
                    f"涓轰粈涔堥€傚悎浣狅細{job.get('涓轰粈涔堥€傚悎浣?, '')}\n"
                    f"甯傚満闇€姹傦細{_job_market_text(job)}\n"
                    f"钖祫鑼冨洿锛氬簲灞妠salary.get('搴斿眾鐢?, '-')} / 3骞磠salary.get('涓夊勾缁忛獙', '-')} / 5骞磠salary.get('浜斿勾缁忛獙', '-')}\n"
                    f"鍏ラ棬绗竴姝ワ細{job.get('鍏ラ棬绗竴姝?, '')}\n"
                    f"涓夊勾鍚庣敾闈細{job.get('涓夊勾鍚庣敾闈?, '')}\n"
                    f"椋庨櫓鎻愮ず锛歿job.get('椋庨櫓鎻愮ず', '')}"
                )
                with st.spinner("姝ｅ湪鐢熸垚宀椾綅娣卞害瑙ｆ瀽..."):
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

    # === 姝ｅ父UI娓叉煋 ===
    if result.get("parse_error"):
        st.warning(str(result.get("parse_error")))

    render_gene_result_tabs(result, job_market_text=_job_market_text)

    render_gene_evolution(result)

    hint = render_bridge_hint()
    if hint:
        st.info(hint)

    col_w, _ = st.columns([1, 2])
    with col_w:
        if st.button("馃敤 甯︾潃鍩哄洜鍥捐氨鍘讳紭鍖栫畝鍘?, key="gene_to_workshop", use_container_width=True):
            bridge_gene_to_workshop(result)
            from ui.sidebar import navigate_to_page
            navigate_to_page("workshop")
            st.rerun()

    st.caption("馃敀 绠€鍘嗗師鏂囧凡浠庡唴瀛樹腑娓呴櫎锛屼粎淇濈暀鍒嗘瀽鎶ュ憡")

    gene_report_text = format_gene_report_text(result)
    st.session_state.gene_report = gene_report_text
    if gene_report_text:
        try:
            pdf_bytes = export_gene_report_pdf(gene_report_text)
            st.download_button(
                label="馃摜 涓嬭浇鍩哄洜鎶ュ憡 (PDF)",
                data=pdf_bytes,
                file_name="鑱屽満闀滃瓙-鑱屼笟鍩哄洜鎶ュ憡.pdf",
                mime="application/pdf",
                key="gene_download_pdf",
                use_container_width=True,
            )
        except Exception as e:
            logger.warning("[gene] PDF export failed: %s", e)

    if st.button("閲嶆柊娴嬪簭", key="gene_restart", use_container_width=True):
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
                model_name="DeepSeek V3 路 鍒嗘瀽鎺ㄧ悊",
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
        "涓婁紶绠€鍘嗘枃浠?,
        type=["txt", "pdf", "docx"],
        accept_multiple_files=False,
        key="gene_resume_uploader",
    )
    st.markdown(
        f'<div style="color:{COLORS["muted"]}; font-size:12px; margin-top:-6px; margin-bottom:8px;">'
        "鎴栫洿鎺ョ矘璐?/div>",
        unsafe_allow_html=True,
    )
    if uploaded is not None:
        uploaded_text = _read_uploaded_resume(uploaded)
        if uploaded_text:
            st.session_state["gene_text_input"] = uploaded_text

    user_input = st.text_area(
        "绮樿创绠€鍘嗘垨鎻忚堪浣犵殑鐜扮姸",
        placeholder="姣斿锛氭垜鏄痻x涓撲笟搴斿眾鐢燂紝鍋氳繃xx鐩稿叧瀹炰範锛屾搮闀挎矡閫氬拰鏁版嵁鍒嗘瀽...",
        key="gene_text_input",
        height=160,
    )

    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

    if st.button("寮€濮嬫祴搴?, key="gene_start", use_container_width=True, type="primary"):
        text = (user_input or "").strip()
        if not text:
            st.warning("璇疯緭鍏ョ畝鍘嗘垨鎻忚堪浣犵殑鐜扮姸")
        else:
            st.session_state.gene_sequencing = True
            st.session_state.gene_sequencing_text = text
            st.rerun()

    st.markdown(
        '<div style="color:#9E8E83; font-size:12px; margin-top:16px; text-align:center;">'
        "宸叉湁绠€鍘嗕細鑷姩濉厖锛屼篃鍙互鐩存帴鎻忚堪浣犵殑鎯呭喌</div>",
        unsafe_allow_html=True,
    )


def _render_history() -> None:
    history = st.session_state.gene_history
    if not history:
        return

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    with st.expander("鍘嗗彶娴嬪簭璁板綍", expanded=False):
        if st.button("娓呯┖璁板綍", key="gene_clear_history"):
            st.session_state.gene_history = []
            _save_history([])

        for item in reversed(history[-10:]):
            if not isinstance(item, dict):
                continue
            payload = item.get("result", {})
            if not isinstance(payload, dict):
                payload = {}
            genes = payload.get("鏄炬€у熀鍥?, [])
            gene_names: List[str] = []
            if isinstance(genes, list):
                gene_names = [
                    str(g.get("鍩哄洜鍚嶇О", ""))
                    for g in genes[:3]
                    if isinstance(g, dict) and g.get("鍩哄洜鍚嶇О")
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

    render_section_title("娴嬪簭鑳藉彂鐜颁粈涔?)
    cols = st.columns(3)
    findings = [
        ("鏄炬€у熀鍥?, "浣犳槑纭煡閬撶殑浼樺娍锛屼絾鍙兘浣庝及浜嗗畠鐨勪环鍊?),
        ("闅愯棌鍩哄洜", "浣犳病娉ㄦ剰鍒扮殑娼滃姏锛屽埆浜哄嵈鐪嬪緱瑙?),
        ("鍩哄洜闄烽槺", "浼樺娍鐢ㄨ繃澶村氨鏄櫡闃憋紝姣斿鍏辨儏鑳藉姏寮哄鏄撹濂?),
    ]
    for i, (title, desc) in enumerate(findings):
        with cols[i]:
            render_insight_card(title, desc)


def render() -> None:
    track_module_enter("鑱屼笟鍩哄洜")
    _inject_styles()
    _init_state()

    resume_text = str(
        st.session_state.get("gene_text_input")
        or st.session_state.get("resume_text", "")
        or ""
    )

    render_page_header("鑱屼笟鍩哄洜", "娴嬪嚭浣犺兘骞蹭粈涔堛€侀€傚悎骞蹭粈涔?)

    if st.session_state.gene_result:
        _render_result_state()
    else:
        _render_input_state(resume_text)

    _render_history()
    _render_gene_supplement()


if __name__ == "__main__":
    st.set_page_config(page_title="鑱屼笟鍩哄洜", page_icon="馃К", layout="wide")
    render()

