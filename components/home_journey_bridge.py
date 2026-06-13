"""首页旅程衔接区 — 连接「全流程陪伴」与「探索全部能力」。"""

from __future__ import annotations

import html

import streamlit as st

from components.progress_dashboard import get_journey_snapshot
from components.session_history import collect_session_records
from ui.sidebar import navigate_to_page


def _inject_bridge_styles() -> None:
    if st.session_state.get("_home_bridge_styles"):
        return
    st.session_state["_home_bridge_styles"] = True
    st.markdown(
        """
<style>
.home-bridge {
  margin: 18px 0 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.home-bridge-hero {
  position: relative;
  padding: 20px 22px;
  border-radius: 16px;
  background: linear-gradient(128deg, rgba(255,252,249,0.96) 0%, rgba(234,243,236,0.78) 52%, rgba(240,230,225,0.72) 100%);
  border: 1px solid rgba(184, 144, 138, 0.16);
  overflow: hidden;
}
.home-bridge-hero::after {
  content: '';
  position: absolute;
  right: -40px;
  top: -40px;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(184,144,138,0.14) 0%, transparent 70%);
  pointer-events: none;
}
.home-bridge-hero-title {
  font-size: 15px;
  font-weight: 650;
  color: #2C2420;
  letter-spacing: -0.01em;
  margin-bottom: 4px;
  position: relative;
  z-index: 1;
}
.home-bridge-hero-sub {
  font-size: 12px;
  color: #8C8279;
  margin-bottom: 14px;
  position: relative;
  z-index: 1;
}
.home-bridge-next {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 12px;
  background: rgba(255,255,255,0.82);
  border: 1px solid rgba(255,255,255,0.95);
  position: relative;
  z-index: 1;
}
a.home-bridge-next {
  text-decoration: none !important;
  color: inherit !important;
  cursor: pointer;
  border: 1px solid rgba(184,144,138,0.12);
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}
@media (prefers-reduced-motion: no-preference) {
  a.home-bridge-next:hover {
    border-color: rgba(184,144,138,0.32);
    background: rgba(255,255,255,0.95);
    transform: translateY(-1px);
  }
  a.home-bridge-next:hover .home-bridge-next-icon {
    background: linear-gradient(145deg, rgba(184,144,138,0.24), rgba(184,144,138,0.1));
  }
  a.home-bridge-next:hover .home-bridge-next-arrow {
    color: #B8908A;
    transform: translateX(3px);
  }
}
.home-bridge-next-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  background: linear-gradient(145deg, rgba(184,144,138,0.16), rgba(184,144,138,0.06));
  flex-shrink: 0;
  transition: background 0.2s ease;
}
.home-bridge-next-arrow {
  font-size: 20px;
  color: #C4AFA5;
  flex-shrink: 0;
  margin-left: auto;
  transition: color 0.2s ease, transform 0.2s ease;
}
.home-bridge-next-body { flex: 1; min-width: 0; }
.home-bridge-next-kicker {
  font-size: 11px;
  font-weight: 600;
  color: #B8908A;
  margin-bottom: 3px;
}
.home-bridge-next-title {
  font-size: 15px;
  font-weight: 650;
  color: #2C2420;
  margin-bottom: 3px;
}
.home-bridge-next-desc {
  font-size: 12px;
  color: #6B5B52;
  line-height: 1.45;
  text-wrap: pretty;
}

.home-bridge-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 12px;
}
.home-bridge-panel {
  padding: 16px 18px;
  border-radius: 14px;
  background: rgba(255,255,255,0.68);
  border: 1px solid rgba(61,56,51,0.07);
}
.home-bridge-panel-title {
  font-size: 13px;
  font-weight: 650;
  color: #2C2420;
  margin-bottom: 10px;
}
.home-bridge-history-item {
  padding: 10px 0;
  border-bottom: 1px solid rgba(61,56,51,0.06);
}
.home-bridge-history-item:last-child { border-bottom: none; padding-bottom: 0; }
.home-bridge-history-meta {
  font-size: 10px;
  color: #9E8E83;
  margin-bottom: 3px;
}
.home-bridge-history-text {
  font-size: 12px;
  color: #5C4F47;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.home-bridge-history-empty {
  font-size: 12px;
  color: #9E8E83;
  line-height: 1.55;
  padding: 8px 0 4px;
}

.home-bridge-tools {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.home-bridge-tool {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255,252,249,0.85);
  border: 1px solid rgba(61,56,51,0.05);
  transition: border-color 0.2s ease, background 0.2s ease;
}
@media (prefers-reduced-motion: no-preference) {
  .home-bridge-tool:hover {
    border-color: rgba(184,144,138,0.22);
    background: rgba(255,255,255,0.95);
  }
}
.home-bridge-tool-icon { font-size: 18px; flex-shrink: 0; }
.home-bridge-tool-text { flex: 1; min-width: 0; }
.home-bridge-tool-name {
  font-size: 12px;
  font-weight: 650;
  color: #2C2420;
}
.home-bridge-tool-desc {
  font-size: 10px;
  color: #8C8279;
  margin-top: 1px;
}

.home-bridge-aux {
  padding: 14px 18px;
  border-radius: 14px;
  background: linear-gradient(90deg, rgba(255,255,255,0.55), rgba(240,235,227,0.65));
  border: 1px solid rgba(61,56,51,0.06);
}
.home-bridge-aux-label {
  font-size: 11px;
  font-weight: 600;
  color: #8C8279;
  margin-bottom: 10px;
}
.home-bridge-aux-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.home-bridge-aux-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #5C4F47 !important;
  text-decoration: none !important;
  background: rgba(255,255,255,0.82);
  border: 1px solid rgba(184,144,138,0.14);
  transition: border-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}
@media (prefers-reduced-motion: no-preference) {
  .home-bridge-aux-link:hover {
    border-color: rgba(184,144,138,0.35);
    color: #2C2420 !important;
    transform: translateY(-1px);
  }
}

.home-section-connector {
  margin: 28px auto 20px;
  max-width: 960px;
  padding: 0 4px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.home-section-connector-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(184,144,138,0.28), transparent);
}
.home-section-connector-label {
  font-size: 12px;
  font-weight: 600;
  color: #9E8E83;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .home-bridge-grid { grid-template-columns: 1fr; }
  .home-bridge-next { flex-direction: column; align-items: flex-start; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_history_panel() -> str:
    records = collect_session_records()[:3]
    if not records:
        return """
<div class="home-bridge-panel mirror-reveal mirror-stagger-2">
  <div class="home-bridge-panel-title">📜 历史记录</div>
  <div class="home-bridge-history-empty">
    还没有记录。聊一次、分析一次，洞察会自动保存在这里。
  </div>
</div>"""

    items = []
    module_icons = {
        "emotion": "💙",
        "diary": "📔",
        "gold": "✨",
        "parallel": "🌌",
        "gene": "🧬",
        "empathy": "🔗",
    }
    for rec in records:
        icon = module_icons.get(rec.get("module", ""), "📋")
        time_str = html.escape(str(rec.get("time", "") or ""))
        meta = f"{icon} {time_str}" if time_str else icon
        items.append(
            f'<div class="home-bridge-history-item">'
            f'<div class="home-bridge-history-meta">{meta}</div>'
            f'<div class="home-bridge-history-text">{html.escape(rec.get("title", ""))}</div>'
            f"</div>"
        )

    return f"""
<div class="home-bridge-panel mirror-reveal mirror-stagger-2">
  <div class="home-bridge-panel-title">📜 最近记录</div>
  {"".join(items)}
</div>"""


def render_home_journey_bridge() -> None:
    """主栏行动引导区（进度追踪见右侧栏，此处不重复）。"""
    _inject_bridge_styles()
    snap = get_journey_snapshot()
    nxt = snap["next"]
    route = html.escape(nxt["route"])
    history_html = _render_history_panel()

    st.markdown(
        f"""
<div class="home-bridge">
  <div class="home-bridge-hero mirror-reveal mirror-stagger-1">
    <div class="home-bridge-hero-title">今天从这里开始</div>
    <div class="home-bridge-hero-sub">右侧可查看完整求职进度，点击卡片直接进入</div>
    <a class="home-bridge-next" href="?nav={route}" target="_self" title="前往{html.escape(nxt["label"])}">
      <div class="home-bridge-next-icon">{nxt["emoji"]}</div>
      <div class="home-bridge-next-body">
        <div class="home-bridge-next-kicker">推荐行动</div>
        <div class="home-bridge-next-title">{html.escape(nxt["label"])}</div>
        <div class="home-bridge-next-desc">{html.escape(nxt["hint"])}</div>
      </div>
      <span class="home-bridge-next-arrow" aria-hidden="true">→</span>
    </a>
  </div>

  <div class="home-bridge-grid">
    {history_html}
    <div class="home-bridge-panel mirror-reveal mirror-stagger-3">
      <div class="home-bridge-panel-title">✨ 贴心能力</div>
      <div class="home-bridge-tools">
        <div class="home-bridge-tool">
          <div class="home-bridge-tool-icon">📔</div>
          <div class="home-bridge-tool-text">
            <div class="home-bridge-tool-name">情绪日记</div>
            <div class="home-bridge-tool-desc">每天签个到，看见心情曲线</div>
          </div>
        </div>
        <div class="home-bridge-tool">
          <div class="home-bridge-tool-icon">💬</div>
          <div class="home-bridge-tool-text">
            <div class="home-bridge-tool-name">连续对话</div>
            <div class="home-bridge-tool-desc">情绪急救站可慢慢把话说完</div>
          </div>
        </div>
        <div class="home-bridge-tool">
          <div class="home-bridge-tool-icon">📜</div>
          <div class="home-bridge-tool-text">
            <div class="home-bridge-tool-name">历史回顾</div>
            <div class="home-bridge-tool-desc">随时找回过往分析结果</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="home-bridge-aux mirror-reveal mirror-stagger-4">
    <div class="home-bridge-aux-label">也可单独探索这些模块</div>
    <div class="home-bridge-aux-row">
      <a class="home-bridge-aux-link" href="?nav=parallel" target="_self">🌌 平行宇宙</a>
      <a class="home-bridge-aux-link" href="?nav=gene" target="_self">🧬 职业基因</a>
      <a class="home-bridge-aux-link" href="?nav=empathy" target="_self">🔗 人才共情链</a>
      <a class="home-bridge-aux-link" href="?nav=emotion&mode=continuous" target="_self">💙 连续对话模式</a>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("打开情绪日记", key="bridge_open_diary", use_container_width=True):
            st.session_state.emotion_show_diary = True
            st.session_state.emotion_chat_mode = "single"
            navigate_to_page("emotion")
            st.rerun()
    with col2:
        if st.button("查看历史", key="bridge_open_history", use_container_width=True):
            navigate_to_page("history")
            st.rerun()


def render_section_connector() -> None:
    """「探索全部能力」前的视觉衔接。"""
    _inject_bridge_styles()
    st.markdown(
        """
<div class="home-section-connector mirror-fade-in">
  <div class="home-section-connector-line"></div>
  <div class="home-section-connector-label">探索全部能力</div>
  <div class="home-section-connector-line"></div>
</div>
""",
        unsafe_allow_html=True,
    )
