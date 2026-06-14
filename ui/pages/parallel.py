"""
骞宠瀹囧畽锛堥暅璇€咃級椤甸潰銆?
浜や簰娴佺▼锛?1) 鏋佺畝鍏ュ彛锛氫笂浼犵畝鍘?鎵嬪啓鐜扮姸 + 绾犵粨杈撳叆 + 鐓т竴鐓?2) 涓夋潯骞宠浜虹敓灞曠ず
3) 浜斿紶缈荤墝杩介棶锛?-3鍏堥棶鍚庣瓟锛?鐩存帴灞曞紑A锛?鎸栨帢绗洓绉嶅彲鑳斤級
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
    {"id": "card1", "image": "assets/cards/card_1_mirror.png", "title": "濡傛灉褰撳垵閫変簡鍙︿竴鏉¤矾", "subtitle": "浣犳渶閬楁喚鐨勯€夋嫨鏄粈涔?, "color": "#B8908A", "prompt_type": "regret"},
    {"id": "card2", "image": "assets/cards/card_2_water.png", "title": "鏈€瀹虫€曠殑浜嬩細褰卞搷鍝潯璺?, "subtitle": "浣犵殑鎭愭儳鏉ヨ嚜鍝噷", "color": "#7B9E87", "prompt_type": "fear"},
    {"id": "card3", "image": "assets/cards/card_3_candle.png", "title": "鍐呭績鏈€鎯冲仛鐨勮兘璧伴€氬悧", "subtitle": "浣犳渶鎯冲仛浣嗘病鏁㈠仛鐨勪簨", "color": "#8B7EB8", "prompt_type": "dream"},
    {"id": "card4", "image": "assets/cards/card_4_steps.png", "title": "灞曞紑闀滈潰A鐨勫畬鏁?骞磋矾寰?, "subtitle": "娣辫€曞綋涓嬭繖鏉¤矾鎬庝箞璧?, "color": "#B8908A", "prompt_type": "expand"},
    {"id": "card5", "image": "assets/cards/card_5_door.png", "title": "鏈夋病鏈夌鍥涚鍙兘", "subtitle": "璺冲嚭涓夐€変竴鐨勬鏋?, "color": "#7B9E87", "prompt_type": "fourth"},
]

_CARD_PLACEHOLDER_ICONS = {
    "card1": "馃獮",
    "card2": "馃挧",
    "card3": "馃暞锔?,
    "card4": "馃獪",
    "card5": "馃毆",
}

_MUTED_LIGHT = "#8C8279"


def _inject_styles() -> None:
    st.markdown(
        """
<style>
/* 骞宠瀹囧畽 路 椤甸潰涓撳睘鏍峰紡 */
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
    """缈荤墝姝ｉ潰锛氫紭鍏堟湰鍦版彃鍥撅紝缂哄け鏃剁敤涓婚鑹叉笎鍙樺崰浣嶏紙閬垮厤绌虹櫧鐮村浘锛夈€?""
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
    icon = _CARD_PLACEHOLDER_ICONS.get(card["id"], "鉁?)
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
        icon = _CARD_PLACEHOLDER_ICONS.get(card_info.get("id", ""), "鉁?)
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
            st.warning("PDF 瑙ｆ瀽澶辫触锛岃鐩存帴绮樿创绠€鍘嗘枃鏈€?)
        return ""

    if suffix in {"docx", "doc"}:
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


def _render_entry() -> None:
    render_page_header("骞宠瀹囧畽", "濡傛灉褰撳垵閫変簡鍙︿竴鏉¤矾锛屼細鎬庢牱锛熼暅璇€呭府浣犵湅瑙併€屽鏋溿€嶇殑鍙兘")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("涓婁紶绠€鍘?, use_container_width=True):
            st.session_state.parallel_resume_mode = "upload"
    with col_b:
        if st.button("鎵嬪啓鐜扮姸", use_container_width=True):
            st.session_state.parallel_resume_mode = "manual"

    st.markdown('<div class="entry-box">', unsafe_allow_html=True)
    if st.session_state.parallel_resume_mode == "upload":
        uploaded = st.file_uploader(
            "鍙笂浼?txt/pdf/docx锛堝彲閫夛級",
            type=["txt", "pdf", "docx", "doc"],
            label_visibility="visible",
        )
        if uploaded is not None:
            content = _read_uploaded_resume(uploaded)
            if not content.strip():
                content = f"[涓婁紶鏂囦欢] {uploaded.name}"
            st.session_state.parallel_resume_text = content
            st.session_state.parallel_parsed = parse_resume(content)
            if content.startswith("[涓婁紶鏂囦欢]"):
                st.caption("宸茶褰曟枃浠跺悕锛屾湭鑳芥彁鍙栨鏂囷紝寤鸿鏀圭敤鎵嬪啓鐜扮姸鎴?txt銆?)
            else:
                st.caption("宸茶鍙栫畝鍘嗗唴瀹广€?)

    if st.session_state.parallel_resume_mode == "manual":
        text = st.text_area(
            "浣犵殑鐜扮姸",
            value=st.session_state.parallel_resume_text,
            placeholder="鍐欎笅浣犵殑缁忓巻銆佹妧鑳姐€佺幇宀椾綅銆佹兂娉曪紙鍙€夛級",
            height=100,
        )
        st.session_state.parallel_resume_text = text
        st.session_state.parallel_parsed = parse_resume(text)

    worry = st.text_area(
        "浣犵幇鍦ㄦ渶绾犵粨鐨勪簨",
        value=st.session_state.parallel_worry,
        placeholder="姣斿锛氳涓嶈杞銆佽鐣欏湪鏉窞杩樻槸鍥炴垚閮姐€佽涓嶈鑰冨叕...",
        height=90,
    )
    st.session_state.parallel_worry = worry
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("鐓т竴鐓?, type="primary", use_container_width=True):
        _on_generate()

    st.markdown("---")

    render_section_title("澶у閮藉湪绾犵粨浠€涔?)
    cols = st.columns(3)
    scenarios = [
        ("瑕佷笉瑕佽€冨叕", "绋冲畾浣嗕笉鐢樺績锛岀籂缁撹涓嶈璧屼竴鎶婁綋鍒跺"),
        ("鐣欏湪涓€绾胯繕鏄洖鑰佸", "澶у煄甯傛満浼氬浣嗗帇鍔涘ぇ锛岃€佸瀹夌ǔ浣嗛€夋嫨灏?),
        ("杞杩樻槸鍧氭寔", "鐜板湪杩欐潯璺秺璧拌秺绐勶紝浣嗚浆琛屽張鎬曚粠闆跺紑濮?),
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
    <span style="color:{_MUTED_LIGHT}; font-size:13px;">闀滆鑰呬細鍩轰簬浣犵殑鐜扮姸锛屾帹婕斾笉鍚岄€夋嫨鐨勫彲鑳芥€р€斺€斾笉鏄浛浣犲喅瀹氾紝鏄府浣犵湅瑙併€?/span>
</div>
""",
        unsafe_allow_html=True,
    )


def _on_generate() -> None:
    worry = st.session_state.parallel_worry.strip()
    if not worry:
        st.warning("鍏堝憡璇夐暅璇€呬綘鍦ㄧ籂缁撲粈涔堛€?)
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
        with st.status("馃 闀滆鑰呮鍦ㄦ帹婕?..", expanded=True) as status:
            st.write("鐞嗚В浣犵殑绾犵粨涓庣幇鐘垛€?)
            st.write("鎺ㄦ紨璺緞 A / B / C鈥?)
            result = engine.generate(profile)
            status.update(label="鎺ㄦ紨瀹屾垚", state="complete", expanded=False)
        if result is None:
            raise ValueError("鎺ㄦ紨鏈繑鍥炵粨鏋滐紝璇风◢鍚庨噸璇?)
        result_dict = result.to_dict()
    except ValueError as e:
        from ui.error_handler import handle_api_error

        handle_api_error(e, context="parallel")
        err_text = str(e)
        st.caption(err_text)
        if "DEEPSEEK" in err_text or "API" in err_text.upper():
            st.caption("璇锋鏌?.env 涓殑 DEEPSEEK_API_KEY 鏄惁閰嶇疆姝ｇ‘銆?)
        return
    except Exception as e:
        from ui.error_handler import handle_api_error

        handle_api_error(e, context="parallel")
        st.caption(f"鎶€鏈鎯咃細{type(e).__name__}: {e}")
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
        st.markdown(f'<div class="insight"><strong>闀滆鑰呰锛?/strong>{insight}</div>', unsafe_allow_html=True)

    st.markdown('<div class="mirror-wrap">', unsafe_allow_html=True)
    for key, label, color in [
        ("mirror_a", "闀滈潰A锛氭繁鑰曞綋涓?, "#B8908A"),
        ("mirror_b", "闀滈潰B锛氭嫄寮箣璺?, "#7B9E87"),
        ("mirror_c", "闀滈潰C锛氭剰澶栧彲鑳?, "#8B7EB8"),
    ]:
        mirror = result.get(key, {})
        turning_html = ""
        for item in mirror.get("turning_points", [])[:4]:
            year = escape(str(item.get("year", "")))
            event = escape(str(item.get("event", "")))
            turning_html += f"<li>{year}锛歿event}</li>"
        risks_html = "".join(f"<li>{escape(str(risk))}</li>" for risk in mirror.get("risks", [])[:4])
        body = f"""
<div class="mirror-card">
  <div class="mirror-header" style="background:{color};">{label} 路 {escape(str(mirror.get("title", "")))}</div>
  <div class="mirror-body">
    <div style="color:#7C6B63;">{escape(str(mirror.get("summary", "")))}</div>
    <p><strong>5骞村悗锛?/strong>{escape(str(mirror.get("year5", {}).get("position", "淇℃伅涓嶈冻")))} 路 {escape(str(mirror.get("year5", {}).get("salary", "淇℃伅涓嶈冻")))}</p>
    <p>{escape(str(mirror.get("year5", {}).get("description", "")))}</p>
    <p><strong>10骞村悗锛?/strong>{escape(str(mirror.get("year10", {}).get("position", "淇℃伅涓嶈冻")))} 路 {escape(str(mirror.get("year10", {}).get("salary", "淇℃伅涓嶈冻")))}</p>
    <p>{escape(str(mirror.get("year10", {}).get("description", "")))}</p>
    <p><strong>鍏抽敭杞姌锛?/strong></p><ul>{turning_html}</ul>
    <p><strong>椋庨櫓鎻愮ず锛?/strong></p><ul>{risks_html}</ul>
    <p style="font-size:12px;color:#8A7A71;">{escape(str(mirror.get("data_source", "鍩轰簬琛屼笟鏁版嵁涓庢斂绛栨帹婕?)))}</p>
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
        if st.button("馃К 鐢ㄦ璺緞鍋氳亴涓氬熀鍥犳祴搴?, key="parallel_to_gene", use_container_width=True):
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
                label="馃摜 涓嬭浇鎺ㄦ紨鎶ュ憡 (PDF)",
                data=pdf_bytes,
                file_name="鑱屽満闀滃瓙-骞宠瀹囧畽鎶ュ憡.pdf",
                mime="application/pdf",
                key="parallel_download_pdf",
                use_container_width=True,
            )
        except Exception as e:
            logger.warning("[parallel] PDF export failed: %s", e)

    _render_flip_cards()


def _render_flip_cards() -> None:
    st.markdown('<div class="flip-label">缈荤墝杩介棶锛堝叡5寮狅級</div>', unsafe_allow_html=True)
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
                if st.button("缈诲紑", key=f"flip_{card['id']}", use_container_width=True):
                    _on_flip(card)
            else:
                st.markdown(
                    '<div style="text-align:center;font-size:12px;color:#9E8E83;padding:6px 0;">鉁?宸叉帰绱?/div>',
                    unsafe_allow_html=True,
                )

    if st.session_state.parallel_pending_question:
        pending = st.session_state.parallel_pending_question
        card = pending["card"]
        st.markdown(
            f'<div class="flip-result" style="border-left-color:{card["color"]};"><strong>{escape(card["title"])}</strong><br>{escape(pending["question"])}</div>',
            unsafe_allow_html=True,
        )
        answer = st.text_input("浣犵殑鍥炵瓟", key=f"answer_{card['id']}", placeholder="鍐欎笅浣犵殑鐪熷疄鎯虫硶...")
        action_l, action_r = st.columns([1, 1])
        with action_l:
            if st.button("璺宠繃杩欏紶鐗?, key=f"skip_{card['id']}", use_container_width=True):
                _save_flip_result(card, "浣犻€夋嫨浜嗗厛璺宠繃杩欏紶鐗岋紝绛変綘鍑嗗濂藉啀缁х画銆?, "")
                st.session_state.parallel_pending_question = None
        with action_r:
            if st.button("鎻愪氦鍥炵瓟", key=f"submit_{card['id']}", use_container_width=True):
                if not answer.strip():
                    st.warning("鍏堝啓涓€鍙ヤ綘鐨勬兂娉曘€?)
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
            with st.spinner("闀滆鑰呮鍦ㄨ杩颁綘鐨?骞存晠浜?.."):
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
        safe_result = "鎴戜竴鏃舵病鍥炰笂鏉ワ紝鑳藉啀璇翠竴閬嶅悧锛?
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
        chunks.append(f"绾犵粨锛歿worry}")
    for item in st.session_state.parallel_flip_results:
        chunks.append(f"銆恵item['title']}銆?)
        if item.get("answer"):
            chunks.append(f"鐢ㄦ埛鍥炵瓟锛歿item['answer']}")
        chunks.append(f"娲炲療锛歿item['result']}")
    return "\n".join(chunks).strip()


def _get_mirror_titles() -> str:
    titles: List[str] = []
    result = st.session_state.parallel_result or {}
    for key in ["a", "b", "c"]:
        mirror = result.get(f"mirror_{key}", {})
        if isinstance(mirror, dict) and mirror.get("title"):
            titles.append(str(mirror["title"]))
    return "銆?.join(titles) if titles else "鏈煡"


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
    return "锛?.join(
        [
            str(mirror_a.get("title", "")),
            str(mirror_a.get("summary", "")),
            str(year5.get("position", "")),
            str(year5.get("salary", "")),
        ]
    ).strip("锛?)


def _render_history() -> None:
    history = st.session_state.parallel_history
    if not history:
        return
    with st.expander("鍘嗗彶鎺ㄦ紨璁板綍", expanded=False):
        if st.button("娓呯┖璁板綍", use_container_width=False):
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
    track_module_enter("骞宠瀹囧畽")
    _inject_styles()
    _init_state()

    if st.session_state.parallel_result is None:
        _render_entry()
    else:
        render_page_header("骞宠瀹囧畽", "浣犵殑骞宠浜虹敓闀滃儚")
        _render_mirror_result()
        render_smart_nav(get_parallel_universe_nav_recommendations())
        if st.button("閲嶆柊寮€濮?, use_container_width=False):
            _reset_page_state()

    _render_history()


if __name__ == "__main__":
    st.set_page_config(page_title="骞宠瀹囧畽", page_icon="馃獮", layout="wide")
    render()

