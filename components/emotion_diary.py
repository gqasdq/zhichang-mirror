"""情绪日记 — 每日签到与情绪曲线。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from core.session_manager import SessionManager


def _diary_path() -> Path:
    return SessionManager.user_file_path("emotion/diary.json")


def load_diary() -> list[dict[str, Any]]:
    path = _diary_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_diary(entries: list[dict[str, Any]]) -> None:
    path = _diary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries[-90:], ensure_ascii=False, indent=2), encoding="utf-8")


def record_checkin(score: int, note: str = "") -> None:
    """记录今日情绪签到（每天一条）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    entries = load_diary()
    entries = [e for e in entries if e.get("date") != today]
    entries.append({
        "date": today,
        "score": max(1, min(10, int(score))),
        "note": (note or "").strip()[:120],
        "time": datetime.now().strftime("%H:%M"),
    })
    save_diary(entries)


def _inject_diary_styles() -> None:
    if st.session_state.get("_emotion_diary_styles"):
        return
    st.session_state["_emotion_diary_styles"] = True
    st.markdown(
        """
<style>
.emotion-diary-shell {
  margin: 16px 0 20px;
  padding: 18px 20px;
  background: linear-gradient(135deg, rgba(255,252,249,0.95), rgba(240,235,227,0.85));
  border: 1px solid rgba(184, 144, 138, 0.16);
  border-radius: 14px;
}
.emotion-diary-title {
  font-size: 15px; font-weight: 650; color: #2C2420; margin-bottom: 4px;
}
.emotion-diary-sub {
  font-size: 12px; color: #8C8279; margin-bottom: 14px;
}
.emotion-spark-row {
  display: flex; align-items: flex-end; gap: 6px; height: 64px;
  padding: 8px 4px 0;
}
.emotion-spark-bar {
  flex: 1; min-width: 8px; max-width: 28px;
  background: linear-gradient(to top, #B8908A, #E8D5CF);
  border-radius: 4px 4px 0 0;
  transition: height 0.3s ease;
}
.emotion-spark-label {
  font-size: 9px; color: #9E8E83; text-align: center; margin-top: 4px;
}
.emotion-diary-trend {
  font-size: 13px; color: #5C4F47; margin-top: 12px; padding-top: 10px;
  border-top: 1px dashed rgba(184, 144, 138, 0.2);
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_emotion_diary() -> None:
    """渲染情绪日记签到 + 近7日曲线。"""
    _inject_diary_styles()
    entries = load_diary()
    recent = entries[-7:]

    st.markdown(
        """
<div class="emotion-diary-shell mirror-reveal">
  <div class="emotion-diary-title">📔 情绪日记</div>
  <div class="emotion-diary-sub">每天签个到，看看情绪是在好转还是更需要被接住</div>
</div>
""",
        unsafe_allow_html=True,
    )

    col_s, col_n = st.columns([2, 3])
    with col_s:
        score = st.slider("今天几度？", 1, 10, 5, key="diary_checkin_score")
    with col_n:
        note = st.text_input("一句话（可选）", placeholder="比如：又投了一轮，有点累", key="diary_checkin_note")
    if st.button("签到", key="diary_checkin_btn", use_container_width=True):
        record_checkin(score, note)
        st.success("已记录今日情绪")
        st.rerun()

    if not recent:
        st.caption("还没有记录，签个到开始吧")
        return

    max_score = 10
    bars_html = ""
    labels_html = ""
    for e in recent:
        s = int(e.get("score", 5))
        h = int(s / max_score * 100)
        d = str(e.get("date", ""))[-5:]
        bars_html += f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;"><div class="emotion-spark-bar" style="height:{h}%;"></div><div class="emotion-spark-label">{d}</div></div>'

    avg = sum(int(e.get("score", 5)) for e in recent) / len(recent)
    trend = "在慢慢好转 🌱" if len(recent) >= 2 and recent[-1]["score"] > recent[0]["score"] else "需要多照顾自己 🫂"

    st.markdown(
        f"""
<div class="emotion-diary-shell">
  <div class="emotion-spark-row">{bars_html}</div>
  <div class="emotion-diary-trend">近 {len(recent)} 天平均 {avg:.1f} 分 · {trend}</div>
</div>
""",
        unsafe_allow_html=True,
    )
