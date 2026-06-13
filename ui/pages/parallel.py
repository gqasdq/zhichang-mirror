"""
平行宇宙（镜语者）页面。

交互流程：
1) 极简入口：上传简历/手写现状 + 纠结输入 + 照一照
2) 三条平行人生展示
3) 五张翻牌追问（1-3先问后答，4直接展开A，5挖掘第四种可能）
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List

import logging

import streamlit as st

from core.pdf_export import export_parallel_report_pdf, format_parallel_report_text
from core.analytics import track_module_enter
from core.parallel_engine import (
    HistoryManager,
    UserProfile,
    get_engine,
    parse_resume,
)
from ui.design_system import render_page_header, render_section_title
from components.regret_meter import render_regret_meter
from components.smart_navigation import get_parallel_universe_nav_recommendations, render_smart_nav
from core.module_bridge import bridge_parallel_to_gene, render_bridge_hint
from ui.pages.parallel_universe import (
    get_branch_story_full_text,
    init_branch_story_state,
    render_branch_story,
    reset_branch_story_state,
    start_branch_story,
)

logger = logging.getLogger(__name__)

FLIP_CARDS = [
    {"id": "card1", "image": "assets/cards/card_1_mirror.png", "title": "如果当初选了另一条路", "subtitle": "你最遗憾的选择是什么", "color": "#B8908A", "prompt_type": "regret"},
    {"id": "card2", "image": "assets/cards/card_2_water.png", "title": "最害怕的事会影响哪条路", "subtitle": "你的恐惧来自哪里", "color": "#7B9E87", "prompt_type": "fear"},
    {"id": "card3", "image": "assets/cards/card_3_candle.png", "title": "内心最想做的能走通吗", "subtitle": "你最想做但没敢做的事", "color": "#8B7EB8", "prompt_type": "dream"},
    {"id": "card4", "image": "assets/cards/card_4_steps.png", "title": "展开镜面A的完整5年路径", "subtitle": "深耕当下这条路怎么走", "color": "#B8908A", "prompt_type": "expand"},
    {"id": "card5", "image": "assets/cards/card_5_door.png", "title": "有没有第四种可能", "subtitle": "跳出三选一的框架", "color": "#7B9E87", "prompt_type": "fourth"},
]

_CARD_PLACEHOLDER_ICONS = {
    "card1": "🪞",
    "card2": "💧",
    "card3": "🕯️",
    "card4": "🪜",
    "card5": "🚪",
}

_MUTED_LIGHT = "#8C8279"


def _inject_styles() -> None:
    st.markdown(
        """
<style>
/* 平行宇宙 · 页面专属样式 */
.stApp {
  background: radial-gradient(circle at top, rgba(255, 248, 242, 0.75), #F7F3EF 42%);
}

.entry-box, .worry-input-area {
  background: rgba(184, 144, 138, 0.06) !important;
  border-radius: 16px !important;
  padding: 24px !important;
  border: 1px solid rgba(184, 144, 138, 0.15) !important;
  margin-top: 8px;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stTextarea > div > div > textarea {
  background: rgba(255, 255, 255, 0.8) !important;
  border: 1px solid rgba(184, 144, 138, 0.2) !important;
  border-radius: 10px !important;
  color: #2C2420 !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stTextarea > div > div > textarea:focus {
  border-color: #B8908A !important;
  box-shadow: 0 0 0 3px rgba(184, 144, 138, 0.15) !important;
}

.mirror-wrap { display: flex; gap: 14px; margin-top: 14px; }
.mirror-card { flex: 1; border-radius: 14px; overflow: hidden; border: 1px solid rgba(44,36,32,.12); background: rgba(255,255,255,.65); }
.mirror-header { padding: 12px 14px; color: #fff; font-weight: 600; font-size: 14px; }
.mirror-body { padding: 14px; font-size: 13px; line-height: 1.7; color: #2C2420; }

.insight { margin-top: 14px; padding: 12px 14px; border-left: 4px solid #B8908A; background: rgba(184,144,138,.10); border-radius: 0 10px 10px 0; }
.flip-label { margin-top: 28px; font-weight: 600; color: #2C2420; }
.flip-result { margin-top: 10px; border-left: 4px solid #B8908A; background: rgba(255,255,255,.58); padding: 12px 14px; border-radius: 0 10px 10px 0; }
.history-item { font-size: 12px; color: #6E5D54; padding: 8px 0; border-bottom: 1px dashed rgba(44,36,32,.14); }
.flip-card-placeholder { box-shadow: inset 0 0 0 1px rgba(255,255,255,0.35); }

.card-flip-wrapper { perspective: 800px; cursor: pointer; }
.card-flip-inner {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  transition: transform 0.6s ease;
  transform-style: preserve-3d;
}
.card-flip-inner.flipping { animation: flipAnim 0.6s ease forwards; }
@keyframes flipAnim {
  0% { transform: rotateY(0deg); }
  50% { transform: rotateY(90deg); }
  100% { transform: rotateY(0deg); }
}
.card-front img { width: 100%; display: block; border-radius: 12px; }
.card-front .card-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px;
  background: linear-gradient(transparent, rgba(44,36,32,0.6));
  color: white;
  text-align: center;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
  border-radius: 0 0 12px 12px;
}
.card-back {
  background: rgba(255,255,255,0.8);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid rgba(184,144,138,0.3);
}
.card-back-img {
  width: 50px;
  height: 50px;
  border-radius: 8px;
  object-fit: cover;
  float: left;
  margin-right: 12px;
  margin-bottom: 8px;
  opacity: 0.7;
}
.card-label {
  text-align: center;
  font-size: 12px;
  color: #8C8279;
  margin-top: 8px;
  line-height: 1.4;
}
.card-label strong {
  display: block;
  color: #2C2420;
  font-size: 13px;
  margin-bottom: 2px;
}
.card-flip-wrapper.flipped-state .card-flip-inner {
  opacity: 0.5;
  filter: grayscale(40%);
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
.flip-result { animation: fadeInUp 0.4s ease-out; }
@media (max-width: 768px) {
  .mirror-wrap { flex-direction: column; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _image_to_base64(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        return ""
    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode()


def _card_visual_html(card: Dict[str, str], *, flipped: bool = False) -> str:
    """翻牌正面：优先本地插图，缺失时用主题色渐变占位（避免空白破图）。"""
    path = Path(card["image"])
    state_style = "opacity:0.45;filter:grayscale(40%);" if flipped else ""
    shell = (
        'height:200px;overflow:hidden;border-radius:12px;'
        'border:1px solid rgba(61,56,51,0.1);'
        f"{state_style}"
    )
    if path.exists():
        img_b64 = _image_to_base64(card["image"])
        return (
            f'<div style="{shell}">'
            f'<img src="data:image/png;base64,{img_b64}" alt="" '
            'style="width:100%;height:200px;object-fit:cover;display:block;">'
            "</div>"
        )
    icon = _CARD_PLACEHOLDER_ICONS.get(card["id"], "✨")
    color = escape(card.get("color", "#B8908A"))
    return (
        f'<div class="flip-card-placeholder" style="{shell}">'
        f'<div style="height:200px;display:flex;align-items:center;justify-content:center;'
        f"background:linear-gradient(145deg,{color}22,{color}55);"
        f'font-size:56px;line-height:1;">{icon}</div>'
        "</div>"
    )


def _render_card_thumbnail(card_info: Dict[str, str]) -> None:
    path = Path(card_info.get("image", ""))
    if path.exists():
        st.image(str(path), width=80)
    else:
        icon = _CARD_PLACEHOLDER_ICONS.get(card_info.get("id", ""), "✨")
        st.markdown(
            f'<div style="font-size:36px;text-align:center;line-height:1.2;padding:8px 0;">{icon}</div>',
            unsafe_allow_html=True,
        )


def _init_state() -> None:
    history = HistoryManager().load()
    defaults = {
        "parallel_resume_mode": "",
        "parallel_resume_text": "",
        "parallel_worry": "",
        "parallel_parsed": {},
        "parallel_result": None,
        "parallel_flipped_cards": [],
        "parallel_flip_results": [],
        "parallel_pending_question": None,
        "parallel_history": history,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    init_branch_story_state()


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
                return re.sub(r"(.)\1+", r"\1", raw)
        except Exception:
            pass

        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw_bytes))
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
            merged = "\n".join(p for p in pages if p).strip()
            if merged:
                return re.sub(r"(.)\1+", r"\1", merged)
        except Exception:
            st.warning("PDF 解析失败，请直接粘贴简历文本。")
        return ""

    if suffix in {"docx", "doc"}:
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


def _render_entry() -> None:
    render_page_header("平行宇宙", "如果当初选了另一条路，会怎样？镜语者帮你看见「如果」的可能")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("上传简历", use_container_width=True):
            st.session_state.parallel_resume_mode = "upload"
    with col_b:
        if st.button("手写现状", use_container_width=True):
            st.session_state.parallel_resume_mode = "manual"

    st.markdown('<div class="entry-box">', unsafe_allow_html=True)
    if st.session_state.parallel_resume_mode == "upload":
        uploaded = st.file_uploader(
            "可上传 txt/pdf/docx（可选）",
            type=["txt", "pdf", "docx", "doc"],
            label_visibility="visible",
        )
        if uploaded is not None:
            content = _read_uploaded_resume(uploaded)
            if not content.strip():
                content = f"[上传文件] {uploaded.name}"
            st.session_state.parallel_resume_text = content
            st.session_state.parallel_parsed = parse_resume(content)
            if content.startswith("[上传文件]"):
                st.caption("已记录文件名，未能提取正文，建议改用手写现状或 txt。")
            else:
                st.caption("已读取简历内容。")

    if st.session_state.parallel_resume_mode == "manual":
        text = st.text_area(
            "你的现状",
            value=st.session_state.parallel_resume_text,
            placeholder="写下你的经历、技能、现岗位、想法（可选）",
            height=100,
        )
        st.session_state.parallel_resume_text = text
        st.session_state.parallel_parsed = parse_resume(text)

    worry = st.text_area(
        "你现在最纠结的事",
        value=st.session_state.parallel_worry,
        placeholder="比如：要不要转行、该留在杭州还是回成都、该不该考公...",
        height=90,
    )
    st.session_state.parallel_worry = worry
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("照一照", type="primary", use_container_width=True):
        _on_generate()

    st.markdown("---")

    render_section_title("大家都在纠结什么")
    cols = st.columns(3)
    scenarios = [
        ("要不要考公", "稳定但不甘心，纠结要不要赌一把体制外"),
        ("留在一线还是回老家", "大城市机会多但压力大，老家安稳但选择少"),
        ("转行还是坚持", "现在这条路越走越窄，但转行又怕从零开始"),
    ]
    for i, (title, desc) in enumerate(scenarios):
        with cols[i]:
            st.markdown(f"""
        <div style="background-color:#FAF7F4; border-radius:8px; padding:16px; border-left:3px solid #B8908A;">
            <div style="color:#2C2420; font-size:14px; font-weight:600;">{title}</div>
            <div style="color:{_MUTED_LIGHT}; font-size:12px; margin-top:4px;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown(
        f"""
<div style="background-color:#F0EBE3; border-radius:8px; padding:12px 16px;">
    <span style="color:{_MUTED_LIGHT}; font-size:13px;">镜语者会基于你的现状，推演不同选择的可能性——不是替你决定，是帮你看见。</span>
</div>
""",
        unsafe_allow_html=True,
    )


def _on_generate() -> None:
    worry = st.session_state.parallel_worry.strip()
    if not worry:
        st.warning("先告诉镜语者你在纠结什么。")
        return

    parsed = st.session_state.parallel_parsed or {}
    profile = UserProfile(
        worry=worry,
        resume_text=st.session_state.parallel_resume_text,
        education=parsed.get("education", ""),
        major=parsed.get("major", ""),
        skills=parsed.get("skills", []),
    )
    engine = get_engine()
    try:
        with st.status("🧠 镜语者正在推演...", expanded=True) as status:
            st.write("理解你的纠结与现状…")
            st.write("推演路径 A / B / C…")
            result = engine.generate(profile)
            status.update(label="推演完成", state="complete", expanded=False)
        if result is None:
            raise ValueError("推演未返回结果，请稍后重试")
        result_dict = result.to_dict()
    except ValueError as e:
        from ui.error_handler import handle_api_error

        handle_api_error(e, context="parallel")
        err_text = str(e)
        st.caption(err_text)
        if "DEEPSEEK" in err_text or "API" in err_text.upper():
            st.caption("请检查 .env 中的 DEEPSEEK_API_KEY 是否配置正确。")
        return
    except Exception as e:
        from ui.error_handler import handle_api_error

        handle_api_error(e, context="parallel")
        st.caption(f"技术详情：{type(e).__name__}: {e}")
        logger.exception("parallel generate failed")
        return

    st.session_state.parallel_result = result_dict
    st.session_state.parallel_flipped_cards = []
    st.session_state.parallel_flip_results = []
    st.session_state.parallel_pending_question = None
    reset_branch_story_state()

    new_item = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "worry": worry[:120],
        "insight": result_dict.get("insight", "")[:160],
    }
    history = st.session_state.parallel_history + [new_item]
    st.session_state.parallel_history = history[-50:]
    HistoryManager().save(st.session_state.parallel_history)
    st.rerun()


def _story_context_builder() -> Dict[str, str]:
    mirror_a_title, mirror_a_summary = _get_mirror_a_meta()
    return {
        "user_worry": st.session_state.parallel_worry,
        "mirror_a_title": mirror_a_title,
        "mirror_a_summary": mirror_a_summary,
        "user_resume_raw": st.session_state.get("parallel_resume_text", ""),
        "mirror_titles": _get_mirror_titles(),
        "user_revealed_info": _build_user_revealed_info(),
    }


def _sync_branch_story_result(card: Dict[str, str]) -> None:
    if not st.session_state.get("parallel_story_complete"):
        return
    full_text = get_branch_story_full_text()
    for item in st.session_state.parallel_flip_results:
        if item.get("card_id") == card["id"]:
            item["result"] = full_text
            return
    st.session_state.parallel_flip_results.append(
        {
            "card_id": card["id"],
            "title": card["title"],
            "color": card["color"],
            "answer": "",
            "result": full_text,
        }
    )


def _render_mirror_result() -> None:
    result = st.session_state.parallel_result
    if not result:
        return

    insight = escape(result.get("insight", "")).replace("\n", "<br>")
    if insight:
        st.markdown(f'<div class="insight"><strong>镜语者说：</strong>{insight}</div>', unsafe_allow_html=True)

    st.markdown('<div class="mirror-wrap">', unsafe_allow_html=True)
    for key, label, color in [
        ("mirror_a", "镜面A：深耕当下", "#B8908A"),
        ("mirror_b", "镜面B：拐弯之路", "#7B9E87"),
        ("mirror_c", "镜面C：意外可能", "#8B7EB8"),
    ]:
        mirror = result.get(key, {})
        turning_html = ""
        for item in mirror.get("turning_points", [])[:4]:
            year = escape(str(item.get("year", "")))
            event = escape(str(item.get("event", "")))
            turning_html += f"<li>{year}：{event}</li>"
        risks_html = "".join(f"<li>{escape(str(risk))}</li>" for risk in mirror.get("risks", [])[:4])
        body = f"""
<div class="mirror-card">
  <div class="mirror-header" style="background:{color};">{label} · {escape(str(mirror.get("title", "")))}</div>
  <div class="mirror-body">
    <div style="color:#7C6B63;">{escape(str(mirror.get("summary", "")))}</div>
    <p><strong>5年后：</strong>{escape(str(mirror.get("year5", {}).get("position", "信息不足")))} · {escape(str(mirror.get("year5", {}).get("salary", "信息不足")))}</p>
    <p>{escape(str(mirror.get("year5", {}).get("description", "")))}</p>
    <p><strong>10年后：</strong>{escape(str(mirror.get("year10", {}).get("position", "信息不足")))} · {escape(str(mirror.get("year10", {}).get("salary", "信息不足")))}</p>
    <p>{escape(str(mirror.get("year10", {}).get("description", "")))}</p>
    <p><strong>关键转折：</strong></p><ul>{turning_html}</ul>
    <p><strong>风险提示：</strong></p><ul>{risks_html}</ul>
    <p style="font-size:12px;color:#8A7A71;">{escape(str(mirror.get("data_source", "基于行业数据与政策推演")))}</p>
  </div>
</div>
"""
        st.markdown(body, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    render_regret_meter(result)

    hint = render_bridge_hint()
    if hint:
        st.caption(hint)

    col_bridge, _ = st.columns([1, 2])
    with col_bridge:
        if st.button("🧬 用此路径做职业基因测序", key="parallel_to_gene", use_container_width=True):
            bridge_parallel_to_gene(result)
            from ui.sidebar import navigate_to_page
            navigate_to_page("gene")
            st.rerun()

    parallel_report_text = format_parallel_report_text(result)
    st.session_state.parallel_report = parallel_report_text
    if parallel_report_text:
        try:
            pdf_bytes = export_parallel_report_pdf(parallel_report_text)
            st.download_button(
                label="📥 下载推演报告 (PDF)",
                data=pdf_bytes,
                file_name="职场镜子-平行宇宙报告.pdf",
                mime="application/pdf",
                key="parallel_download_pdf",
                use_container_width=True,
            )
        except Exception as e:
            logger.warning("[parallel] PDF export failed: %s", e)

    _render_flip_cards()


def _render_flip_cards() -> None:
    st.markdown('<div class="flip-label">翻牌追问（共5张）</div>', unsafe_allow_html=True)
    cols = st.columns(5)
    for index, card in enumerate(FLIP_CARDS):
        with cols[index]:
            is_flipped = card["id"] in st.session_state.parallel_flipped_cards
            st.markdown(_card_visual_html(card, flipped=is_flipped), unsafe_allow_html=True)
            st.markdown(
                f'''
<div style="text-align:center; margin-top:8px; height:36px; overflow:hidden;">
  <div style="font-size:13px; font-weight:600; color:{'#9E8E83' if is_flipped else '#2C2420'};">
    {escape(card["title"])}
  </div>
</div>
''',
                unsafe_allow_html=True,
            )
            if not is_flipped:
                if st.button("翻开", key=f"flip_{card['id']}", use_container_width=True):
                    _on_flip(card)
            else:
                st.markdown(
                    '<div style="text-align:center;font-size:12px;color:#9E8E83;padding:6px 0;">✓ 已探索</div>',
                    unsafe_allow_html=True,
                )

    if st.session_state.parallel_pending_question:
        pending = st.session_state.parallel_pending_question
        card = pending["card"]
        st.markdown(
            f'<div class="flip-result" style="border-left-color:{card["color"]};"><strong>{escape(card["title"])}</strong><br>{escape(pending["question"])}</div>',
            unsafe_allow_html=True,
        )
        answer = st.text_input("你的回答", key=f"answer_{card['id']}", placeholder="写下你的真实想法...")
        action_l, action_r = st.columns([1, 1])
        with action_l:
            if st.button("跳过这张牌", key=f"skip_{card['id']}", use_container_width=True):
                _save_flip_result(card, "你选择了先跳过这张牌，等你准备好再继续。", "")
                st.session_state.parallel_pending_question = None
        with action_r:
            if st.button("提交回答", key=f"submit_{card['id']}", use_container_width=True):
                if not answer.strip():
                    st.warning("先写一句你的想法。")
                else:
                    _on_flip_answer(card, answer.strip())

    card4 = next((c for c in FLIP_CARDS if c["id"] == "card4"), None)
    if (
        card4
        and card4["id"] in st.session_state.parallel_flipped_cards
        and st.session_state.get("parallel_story_card_id") == card4["id"]
    ):
        render_branch_story(card4["title"], card4["color"], _story_context_builder)
        _sync_branch_story_result(card4)

    for fr in st.session_state.parallel_flip_results:
        if fr.get("card_id") == "card4" and st.session_state.get("parallel_story_card_id") == "card4":
            continue
        card_info = next((c for c in FLIP_CARDS if c["id"] == fr.get("card_id")), {})
        st.markdown(f'<div class="flip-result" style="border-left-color:{fr["color"]};">', unsafe_allow_html=True)
        cols_r = st.columns([1, 6])
        with cols_r[0]:
            if card_info.get("image"):
                _render_card_thumbnail(card_info)
        with cols_r[1]:
            st.markdown(
                f'<strong>{escape(fr["title"])}</strong><br>{escape(fr["result"]).replace(chr(10), "<br>")}',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def _on_flip(card: Dict[str, str]) -> None:
    if card["id"] not in st.session_state.parallel_flipped_cards:
        st.session_state.parallel_flipped_cards.append(card["id"])

    prompt_type = card["prompt_type"]
    if prompt_type == "expand":
        try:
            with st.spinner("镜语者正在讲述你的5年故事..."):
                start_branch_story(card["id"], _story_context_builder)
        except Exception as e:
            from ui.error_handler import handle_api_error

            handle_api_error(e, context="parallel")
        st.rerun()
        return

    if prompt_type in {"regret", "fear", "dream"}:
        try:
            question = get_engine().flip_card(
                prompt_type=prompt_type,
                card_title=card["title"],
                user_worry=st.session_state.parallel_worry,
                user_revealed_info=_build_user_revealed_info(),
                user_answer="",
                user_resume_raw=st.session_state.get("parallel_resume_text", ""),
            )
        except Exception as e:
            from ui.error_handler import get_friendly_message, handle_api_error

            handle_api_error(e, context="parallel")
            question = get_friendly_message(e)
        st.session_state.parallel_pending_question = {"card": card, "question": question}
        st.rerun()
        return

    mirror_a_text = _mirror_a_brief()
    mirror_titles = _get_mirror_titles()
    mirror_a_title, mirror_a_summary = _get_mirror_a_meta()
    try:
        result = get_engine().flip_card(
            prompt_type=prompt_type,
            card_title=card["title"],
            user_worry=st.session_state.parallel_worry,
            user_revealed_info=_build_user_revealed_info(),
            mirror_a_text=mirror_a_text,
            user_resume_raw=st.session_state.get("parallel_resume_text", ""),
            mirror_titles=mirror_titles,
            mirror_a_title=mirror_a_title,
            mirror_a_summary=mirror_a_summary,
        )
    except Exception as e:
        from ui.error_handler import get_friendly_message, handle_api_error

        handle_api_error(e, context="parallel")
        result = get_friendly_message(e)
    _save_flip_result(card, result, "")
    st.rerun()


def _on_flip_answer(card: Dict[str, str], answer: str) -> None:
    mirror_a_text = _mirror_a_brief()
    mirror_titles = _get_mirror_titles()
    mirror_a_title, mirror_a_summary = _get_mirror_a_meta()
    try:
        result = get_engine().flip_card(
            prompt_type=card["prompt_type"],
            card_title=card["title"],
            user_worry=st.session_state.parallel_worry,
            user_revealed_info=_build_user_revealed_info(),
            user_answer=answer,
            mirror_a_text=mirror_a_text,
            user_resume_raw=st.session_state.get("parallel_resume_text", ""),
            mirror_titles=mirror_titles,
            mirror_a_title=mirror_a_title,
            mirror_a_summary=mirror_a_summary,
        )
    except Exception as e:
        from ui.error_handler import get_friendly_message, handle_api_error

        handle_api_error(e, context="parallel")
        result = get_friendly_message(e)
    _save_flip_result(card, result, answer)
    st.session_state.parallel_pending_question = None
    st.rerun()


def _save_flip_result(card: Dict[str, str], result: str, answer: str) -> None:
    safe_result = str(result or "").strip()
    if not safe_result:
        safe_result = "我一时没回上来，能再说一遍吗？"
    st.session_state.parallel_flip_results.append(
        {
            "card_id": card["id"],
            "title": card["title"],
            "color": card["color"],
            "answer": answer,
            "result": safe_result,
        }
    )


def _build_user_revealed_info() -> str:
    chunks: List[str] = []
    worry = st.session_state.parallel_worry
    if worry:
        chunks.append(f"纠结：{worry}")
    for item in st.session_state.parallel_flip_results:
        chunks.append(f"【{item['title']}】")
        if item.get("answer"):
            chunks.append(f"用户回答：{item['answer']}")
        chunks.append(f"洞察：{item['result']}")
    return "\n".join(chunks).strip()


def _get_mirror_titles() -> str:
    titles: List[str] = []
    result = st.session_state.parallel_result or {}
    for key in ["a", "b", "c"]:
        mirror = result.get(f"mirror_{key}", {})
        if isinstance(mirror, dict) and mirror.get("title"):
            titles.append(str(mirror["title"]))
    return "、".join(titles) if titles else "未知"


def _get_mirror_a_meta() -> tuple[str, str]:
    result = st.session_state.parallel_result or {}
    mirror_a = result.get("mirror_a", {})
    if not isinstance(mirror_a, dict):
        return "", ""
    return str(mirror_a.get("title", "")), str(mirror_a.get("summary", ""))


def _mirror_a_brief() -> str:
    result = st.session_state.parallel_result or {}
    mirror_a = result.get("mirror_a", {})
    if not isinstance(mirror_a, dict):
        return ""
    year5 = mirror_a.get("year5", {}) if isinstance(mirror_a.get("year5", {}), dict) else {}
    return "；".join(
        [
            str(mirror_a.get("title", "")),
            str(mirror_a.get("summary", "")),
            str(year5.get("position", "")),
            str(year5.get("salary", "")),
        ]
    ).strip("；")


def _render_history() -> None:
    history = st.session_state.parallel_history
    if not history:
        return
    with st.expander("历史推演记录", expanded=False):
        if st.button("清空记录", use_container_width=False):
            st.session_state.parallel_history = []
            HistoryManager().save([])
        for item in reversed(history[-10:]):
            text = f"{escape(item.get('time', ''))} | {escape(item.get('worry', '')[:80])}"
            st.markdown(f'<div class="history-item">{text}</div>', unsafe_allow_html=True)


def _reset_page_state() -> None:
    st.session_state.parallel_resume_mode = ""
    st.session_state.parallel_resume_text = ""
    st.session_state.parallel_worry = ""
    st.session_state.parallel_parsed = {}
    st.session_state.parallel_result = None
    st.session_state.parallel_flipped_cards = []
    st.session_state.parallel_flip_results = []
    st.session_state.parallel_pending_question = None
    reset_branch_story_state()


def render() -> None:
    track_module_enter("平行宇宙")
    _inject_styles()
    _init_state()

    if st.session_state.parallel_result is None:
        _render_entry()
    else:
        render_page_header("平行宇宙", "你的平行人生镜像")
        _render_mirror_result()
        render_smart_nav(get_parallel_universe_nav_recommendations())
        if st.button("重新开始", use_container_width=False):
            _reset_page_state()

    _render_history()


if __name__ == "__main__":
    st.set_page_config(page_title="平行宇宙", page_icon="🪞", layout="wide")
    render()
