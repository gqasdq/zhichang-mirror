"""会话历史回顾 — 读取 data/sessions/{uid}/ 下的持久化记录。"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from core.session_manager import SessionManager
from ui.sidebar import navigate_to_page


MODULE_META = {
    "emotion": {"icon": "💙", "label": "情绪急救", "route": "emotion"},
    "diary": {"icon": "📔", "label": "情绪日记", "route": "emotion"},
    "gold": {"icon": "✨", "label": "金子探测", "route": "gold"},
    "parallel": {"icon": "🌌", "label": "平行宇宙", "route": "parallel"},
    "gene": {"icon": "🧬", "label": "职业基因", "route": "gene"},
    "empathy": {"icon": "🔗", "label": "人才共情链", "route": "empathy"},
}


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _truncate(text: str, limit: int = 120) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_time(raw: str) -> str:
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d %H:%M", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m-%d %H:%M")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw).strftime("%m-%d %H:%M")
    except (TypeError, ValueError):
        return raw


def collect_session_records() -> list[dict[str, Any]]:
    """汇总当前用户所有模块的历史记录。"""
    records: list[dict[str, Any]] = []
    base = SessionManager.get_session_dir()

    emotion_hist = _load_json(base / "emotion" / "history.json")
    if isinstance(emotion_hist, list):
        for idx, item in enumerate(reversed(emotion_hist)):
            if not isinstance(item, dict):
                continue
            records.append({
                "module": "emotion",
                "sort_key": f"emotion-{idx:04d}",
                "title": _truncate(item.get("input", "倾诉记录")),
                "preview": _truncate(item.get("reply", ""), 160),
                "time": item.get("time", ""),
                "detail": item,
            })

    diary = _load_json(base / "emotion" / "diary.json")
    if isinstance(diary, list):
        for idx, item in enumerate(reversed(diary)):
            if not isinstance(item, dict):
                continue
            score = item.get("score", "?")
            note = item.get("note", "")
            records.append({
                "module": "diary",
                "sort_key": f"diary-{item.get('date', idx)}",
                "title": f"情绪签到 · {score} 分",
                "preview": _truncate(note) or "（无备注）",
                "time": item.get("date", ""),
                "detail": item,
            })

    probes = _load_json(base / "gold_probes.json")
    if isinstance(probes, list):
        for idx, probe in enumerate(reversed(probes)):
            if not isinstance(probe, dict):
                continue
            name = probe.get("name") or f"探测 {len(probes) - idx}"
            snippet = _truncate(probe.get("resume_snippet", ""), 80)
            records.append({
                "module": "gold",
                "sort_key": f"gold-{idx:04d}",
                "title": name,
                "preview": snippet or "简历分析记录",
                "time": "",
                "detail": probe,
            })

    for mod_key, subpath in (
        ("parallel", ("parallel", "history.json")),
        ("gene", ("gene", "history.json")),
        ("empathy", ("empathy", "history.json")),
    ):
        hist = _load_json(base.joinpath(*subpath))
        if not isinstance(hist, list):
            continue
        for idx, item in enumerate(reversed(hist)):
            if not isinstance(item, dict):
                continue
            title = (
                item.get("worry")
                or item.get("question")
                or item.get("input")
                or item.get("title")
                or "分析记录"
            )
            preview = (
                item.get("insight")
                or item.get("summary")
                or item.get("reply")
                or item.get("result")
                or ""
            )
            if isinstance(preview, dict):
                preview = json.dumps(preview, ensure_ascii=False)[:120]
            records.append({
                "module": mod_key,
                "sort_key": f"{mod_key}-{idx:04d}",
                "title": _truncate(str(title), 80),
                "preview": _truncate(str(preview), 160),
                "time": item.get("time") or item.get("timestamp") or "",
                "detail": item,
            })

    export_path = base / "workshop" / "exported.json"
    export_data = _load_json(export_path)
    if isinstance(export_data, dict) and export_data.get("exported_at"):
        records.append({
            "module": "gold",
            "sort_key": "export-0000",
            "title": "简历 PDF 导出",
            "preview": f"模板：{export_data.get('template', 'classic')}",
            "time": export_data.get("exported_at", ""),
            "detail": export_data,
        })

    records.sort(key=lambda r: r.get("sort_key", ""), reverse=True)
    return records


def _inject_history_styles() -> None:
    if st.session_state.get("_session_history_styles"):
        return
    st.session_state["_session_history_styles"] = True
    st.markdown(
        """
<style>
.history-page-shell { max-width: 880px; }
.history-filter-row { margin-bottom: 12px; }
.history-card {
  padding: 14px 16px; margin-bottom: 10px;
  background: rgba(255,255,255,0.78);
  border: 1px solid rgba(61,56,51,0.08); border-radius: 12px;
}
.history-card-head {
  display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
}
.history-card-module {
  font-size: 11px; font-weight: 650; color: #8C8279;
  background: rgba(184,144,138,0.12); padding: 2px 8px; border-radius: 999px;
}
.history-card-title { font-size: 14px; font-weight: 600; color: #2C2420; flex: 1; }
.history-card-time { font-size: 11px; color: #9E8E83; }
.history-card-preview { font-size: 13px; color: #5C4F47; line-height: 1.5; }
.history-empty {
  padding: 32px 20px; text-align: center; color: #8C8279;
  background: rgba(255,252,249,0.9); border-radius: 14px;
  border: 1px dashed rgba(184,144,138,0.25);
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_session_history_page() -> None:
    """历史记录完整页面。"""
    from ui.design_system import render_page_header

    _inject_history_styles()
    render_page_header("历史记录", "回顾过往分析，随时找回当时的洞察")

    records = collect_session_records()
    modules_present = sorted({r["module"] for r in records})
    filter_options = ["全部"] + [
        MODULE_META[m]["label"] for m in modules_present if m in MODULE_META
    ]

    col_filter, col_count = st.columns([3, 1])
    with col_filter:
        selected = st.selectbox("筛选模块", filter_options, key="history_module_filter")
    with col_count:
        st.metric("记录数", len(records))

    if not records:
        st.markdown(
            """
<div class="history-empty mirror-reveal">
  <div style="font-size:28px;margin-bottom:8px;">📭</div>
  <div style="font-size:15px;font-weight:600;color:#2C2420;margin-bottom:6px;">还没有历史记录</div>
  <div>使用任意模块后，分析结果会自动保存在本地</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("去首页开始", key="history_go_home", use_container_width=True):
            navigate_to_page("home")
            st.rerun()
        return

    label_to_module = {v["label"]: k for k, v in MODULE_META.items()}
    filtered = records
    if selected != "全部":
        mod = label_to_module.get(selected)
        if mod:
            filtered = [r for r in records if r["module"] == mod]

    for idx, rec in enumerate(filtered[:30]):
        meta = MODULE_META.get(rec["module"], {"icon": "📋", "label": rec["module"]})
        time_label = _format_time(str(rec.get("time", "")))
        with st.expander(
            f"{meta['icon']} {rec['title']}" + (f" · {time_label}" if time_label else ""),
            expanded=False,
        ):
            st.markdown(
                f'<div class="history-card-preview">{html.escape(rec.get("preview", ""))}</div>',
                unsafe_allow_html=True,
            )
            detail = rec.get("detail") or {}
            if rec["module"] == "emotion":
                st.markdown("**你说的**")
                st.write(detail.get("input", ""))
                st.markdown("**小镜的回应**")
                st.write(detail.get("reply", ""))
            elif rec["module"] == "diary":
                st.write(f"日期：{detail.get('date', '—')} · 分数：{detail.get('score', '—')}")
                if detail.get("note"):
                    st.write(detail.get("note"))
            elif rec["module"] == "parallel":
                if detail.get("worry"):
                    st.markdown(f"**困扰：** {detail.get('worry')}")
                if detail.get("insight"):
                    st.markdown(f"**洞察：** {detail.get('insight')}")
            else:
                st.json(detail)

            route = meta.get("route")
            if route and st.button(f"再去 {meta['label']}", key=f"history_nav_{idx}_{rec['module']}"):
                if route == "emotion":
                    st.session_state.emotion_scroll_diary = rec["module"] == "diary"
                navigate_to_page(route)
                st.rerun()

    if len(filtered) > 30:
        st.caption(f"仅显示最近 30 条，共 {len(filtered)} 条记录")

    st.caption("🔒 记录仅保存在本机浏览器会话目录，关闭后仍可在同一会话 ID 下查看")
