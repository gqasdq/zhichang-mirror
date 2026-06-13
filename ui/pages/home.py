import streamlit as st
from datetime import datetime

from components.progress_dashboard import render_progress_dashboard
from components.home_journey_bridge import render_home_journey_bridge, render_section_connector
from ui.sidebar import navigate_to_page

ROUTE_TO_PAGE = {
    "emotion": "💙 情绪急救站",
    "gold": "✨ 金子探测器",
    "workshop": "🔨 金子工坊",
    "parallel": "🌌 平行宇宙",
    "gene": "🧬 职业基因",
    "empathy": "🔗 人才共情链",
}

FEATURE_TILES = [
    {
        "name": "🧭 岗位方向探索",
        "desc": "不知道适合什么？让 AI 帮你看看，还能一键搜智联",
        "route": "gold",
        "size": "banner",
        "accent": "rose",
    },
    {
        "name": "情绪急救站",
        "desc": "焦虑的时候，有人听你说话",
        "route": "emotion",
        "size": "large",
        "emoji": "💙",
        "accent": "blue",
    },
    {
        "name": "金子探测器",
        "desc": "简历里藏着你自己不知道的优势",
        "route": "gold",
        "size": "large",
        "emoji": "✨",
        "accent": "gold",
    },
    {
        "name": "金子工坊",
        "desc": "让简历从还行变成真行",
        "route": "workshop",
        "size": "medium",
        "emoji": "🔨",
        "accent": "amber",
    },
    {
        "name": "平行宇宙",
        "desc": "如果当初选了另一条路，会怎样？",
        "route": "parallel",
        "size": "medium",
        "emoji": "🌌",
        "accent": "violet",
    },
    {
        "name": "职业基因",
        "desc": "你天生适合做什么，基因不会说谎",
        "route": "gene",
        "size": "medium",
        "emoji": "🧬",
        "accent": "mint",
    },
    {
        "name": "人才共情链",
        "desc": "和你一样的人，都在经历什么",
        "route": "empathy",
        "size": "medium",
        "emoji": "🔗",
        "accent": "teal",
    },
]


def _get_query_value(key: str):
    if hasattr(st, "query_params"):
        value = st.query_params.get(key)
    else:
        value = st.experimental_get_query_params().get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _consume_page_query() -> None:
    nav = _get_query_value("nav")
    mood = _get_query_value("mood")
    mode = _get_query_value("mode")
    if mood:
        st.session_state.mood_quick_check = mood
    if mode == "continuous":
        st.session_state.emotion_chat_mode = "continuous"
    if nav in ROUTE_TO_PAGE:
        st.session_state.current_page = ROUTE_TO_PAGE[nav]


def _inject_home_styles() -> None:
    st.markdown(
        """
<style>
/* ── 首页画布：氛围层填充两侧，内容居中不对称 ── */
.home-page-marker {
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
[data-testid="stMainBlockContainer"]:has(.home-page-marker) {
    position: relative;
    z-index: 1;
    padding-top: 0 !important;
    gap: 0.35rem !important;
}
[data-testid="stMainBlockContainer"]:has(.home-page-marker) .block-container,
.block-container:has(.home-page-marker) {
    padding-top: 6px !important;
}
[data-testid="stMainBlockContainer"]:has(.home-page-marker) [data-testid="stVerticalBlock"] > div {
    max-width: 960px;
    margin-left: auto !important;
    margin-right: auto !important;
}
[data-testid="stMainBlockContainer"]:has(.home-page-marker) [data-testid="stElementContainer"]:has(.home-hero),
[data-testid="stMainBlockContainer"]:has(.home-page-marker) [data-testid="stMarkdownContainer"]:has(.home-hero) {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
[data-testid="stElementContainer"]:has(.home-canvas-bg),
[data-testid="stMarkdownContainer"]:has(.home-canvas-bg),
[data-testid="stElementContainer"]:has(.home-page-marker),
[data-testid="stMarkdownContainer"]:has(.home-page-marker) {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
[data-testid="stElementContainer"]:has(.home-canvas-bg) .home-canvas-bg,
[data-testid="stMarkdownContainer"]:has(.home-canvas-bg) .home-canvas-bg {
    margin-top: 0 !important;
}
[data-testid="stMainBlockContainer"]:has(.home-page-marker) [data-testid="stHorizontalBlock"] {
    max-width: 960px;
    margin-left: auto !important;
    margin-right: auto !important;
}
.home-canvas-bg {
    position: fixed;
    inset: 0;
    left: 280px;
    width: auto !important;
    height: 0 !important;
    overflow: visible !important;
    pointer-events: none;
    z-index: 0;
}
@media (max-width: 768px) {
    .home-canvas-bg { left: 0; }
}
.home-ambient-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(72px);
    opacity: 0.42;
    will-change: transform;
}
.home-ambient-orb--1 {
    width: min(38vw, 420px);
    height: min(38vw, 420px);
    left: max(-8vw, -80px);
    top: 60px;
    background: radial-gradient(circle, rgba(232, 180, 184, 0.55) 0%, transparent 68%);
}
.home-ambient-orb--2 {
    width: min(32vw, 360px);
    height: min(32vw, 360px);
    right: max(-6vw, -60px);
    top: 280px;
    background: radial-gradient(circle, rgba(168, 213, 186, 0.45) 0%, transparent 68%);
}
.home-ambient-orb--3 {
    width: min(28vw, 300px);
    height: min(28vw, 300px);
    left: 12%;
    bottom: 120px;
    background: radial-gradient(circle, rgba(197, 185, 212, 0.35) 0%, transparent 70%);
    opacity: 0.28;
}
@media (prefers-reduced-motion: no-preference) {
    .home-ambient-orb--1 {
        animation: home-drift-a 22s ease-in-out infinite;
    }
    .home-ambient-orb--2 {
        animation: home-drift-b 26s ease-in-out infinite;
    }
    .home-ambient-orb--3 {
        animation: home-drift-c 30s ease-in-out infinite;
    }
}
@keyframes home-drift-a {
    0%, 100% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(24px, -18px) scale(1.04); }
}
@keyframes home-drift-b {
    0%, 100% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(-20px, 14px) scale(1.03); }
}
@keyframes home-drift-c {
    0%, 100% { transform: translate(0, 0); }
    50% { transform: translate(16px, -10px); }
}

.home-stage {
    position: relative;
    z-index: 1;
    width: 100%;
    max-width: 960px;
    margin: 0 auto;
    padding: 0 4px 40px;
}
.home-stage-block {
    width: 100%;
    max-width: 960px;
    margin: 0 auto;
    padding: 0 4px;
}

/* Hero：editorial 居中，字号放大 */
.home-hero {
    text-align: center;
    padding: 4px 16px 28px;
    max-width: 640px;
    margin: 0 auto 4px;
}
.home-greeting {
    display: inline-block;
    font-size: 12px;
    font-weight: 550;
    letter-spacing: 0.06em;
    color: #8C8279;
    margin-bottom: 14px;
    padding: 4px 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(184, 144, 138, 0.12);
}
.intro-main {
    font-size: clamp(1.65rem, 3.8vw, 2.35rem);
    color: #2C2420;
    font-weight: 650;
    line-height: 1.28;
    letter-spacing: -0.02em;
    text-wrap: balance;
    margin-bottom: 10px;
}
.intro-sub {
    font-size: clamp(0.9rem, 1.8vw, 1.05rem);
    color: #6B5B52;
    line-height: 1.6;
    text-wrap: pretty;
}

/* 双栏主区 — Streamlit columns 适配 */
[data-testid="stMainBlockContainer"]:has(.home-page-marker) [data-testid="column"] {
    background: transparent !important;
}
.home-col-aside-wrap {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

/* 5 秒了解 */
.home-guide-shell {
    margin: 0 0 16px;
    padding: 22px 24px;
    background: linear-gradient(145deg, rgba(255,252,249,0.88), rgba(234,243,236,0.72));
    border: 1px solid rgba(184, 144, 138, 0.12);
    border-radius: 18px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.8) inset, 0 8px 32px rgba(44, 36, 32, 0.04);
}
.home-guide-title {
    font-size: 16px;
    font-weight: 650;
    color: #2C2420;
    margin-bottom: 16px;
}
.home-guide-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 14px;
}
.home-guide-card {
    padding: 14px 14px 12px;
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.95);
    border-radius: 14px;
    box-shadow: 0 2px 10px rgba(44, 36, 32, 0.03);
    transition: box-shadow 0.25s ease, transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
@media (prefers-reduced-motion: no-preference) {
    .home-guide-card:hover {
        box-shadow: 0 6px 20px rgba(44, 36, 32, 0.07);
        transform: translateY(-2px);
    }
}
.home-guide-card-emoji { font-size: 20px; margin-bottom: 6px; }
.home-guide-card-head {
    font-size: 13px;
    font-weight: 650;
    color: #2C2420;
    margin-bottom: 4px;
}
.home-guide-card-desc {
    font-size: 11px;
    color: #6B5B52;
    line-height: 1.5;
}
.home-guide-slogan {
    font-size: 12px;
    color: #8C8279;
    font-style: italic;
    text-align: center;
}

/* 流程时间线 */
.home-flow-shell {
    margin: 0 0 0;
    padding: 20px 22px 18px;
    background: rgba(255, 255, 255, 0.62);
    border: 1px solid rgba(61, 56, 51, 0.07);
    border-radius: 16px;
    box-shadow: 0 4px 24px rgba(44, 36, 32, 0.03);
}
.home-flow-title {
    font-size: 14px;
    font-weight: 650;
    color: #2C2420;
    margin-bottom: 14px;
}
.home-flow-track {
    display: flex;
    align-items: flex-start;
    gap: 0;
    position: relative;
}
.home-flow-track::before {
    content: '';
    position: absolute;
    top: 18px;
    left: 8%;
    right: 8%;
    height: 2px;
    background: linear-gradient(90deg, rgba(184,144,138,0.25), rgba(93,174,139,0.35), rgba(184,144,138,0.2));
    border-radius: 1px;
    z-index: 0;
}
.home-flow-step {
    flex: 1;
    text-align: center;
    padding: 0 4px;
    position: relative;
    z-index: 1;
}
.home-flow-dot {
    width: 36px;
    height: 36px;
    margin: 0 auto 8px;
    border-radius: 50%;
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(184, 144, 138, 0.18);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    box-shadow: 0 2px 8px rgba(44, 36, 32, 0.05);
}
.home-flow-name {
    font-size: 11px;
    font-weight: 600;
    color: #2C2420;
    margin-bottom: 2px;
}
.home-flow-desc {
    font-size: 10px;
    color: #9E8E83;
    line-height: 1.4;
}
.home-flow-foot {
    font-size: 11px;
    color: #9E8E83;
    text-align: center;
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid rgba(61, 56, 51, 0.06);
}

/* 情绪卡片 */
.home-emotion-card {
    margin: 0;
    padding: 0;
    background: transparent;
    border: none;
}
.home-emotion-title {
    color: #2C2420;
    font-size: 14px;
    font-weight: 650;
    margin-bottom: 2px;
}
.home-emotion-hint {
    color: #9E8E83;
    font-size: 12px;
    margin: 0 0 8px;
}
.home-emotion-card .stSlider [data-baseweb="slider"] > div > div,
.stSlider [data-baseweb="slider"] > div > div {
    background: linear-gradient(to right, #E8D5CF, #B8908A) !important;
}
.home-emotion-card .stSlider [data-baseweb="thumb"],
.stSlider [data-baseweb="thumb"] {
    background-color: #B8908A !important;
    border-color: #B8908A !important;
}
.st-key-home_emotion_go button[kind="primary"] {
    background-color: #B8908A !important;
    border-color: #B8908A !important;
    color: #FFF !important;
}
.st-key-home_emotion_go button[kind="primary"]:hover {
    background-color: #A07A74 !important;
    border-color: #A07A74 !important;
}

/* Bento 功能网格 */
.home-section-head--lite {
    justify-content: flex-end;
    margin-bottom: 12px;
}
.home-section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 16px;
    padding: 0 2px;
}
.home-section-title {
    font-size: 17px;
    font-weight: 650;
    color: #2C2420;
    letter-spacing: -0.01em;
}
.home-section-meta {
    font-size: 12px;
    color: #9E8E83;
}
.home-bento {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}
.home-bento-tile {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 112px;
    padding: 18px 18px 16px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid rgba(61, 56, 51, 0.07);
    color: #2C2420 !important;
    text-decoration: none !important;
    position: relative;
    overflow: hidden;
    transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
    box-shadow: 0 2px 12px rgba(44, 36, 32, 0.03);
}
.home-bento-tile::before {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
}
.home-bento-tile--rose::before { background: linear-gradient(135deg, rgba(232,180,184,0.12), transparent 60%); }
.home-bento-tile--blue::before { background: linear-gradient(135deg, rgba(168,197,217,0.14), transparent 60%); }
.home-bento-tile--gold::before { background: linear-gradient(135deg, rgba(245,195,150,0.16), transparent 60%); }
.home-bento-tile--amber::before { background: linear-gradient(135deg, rgba(232,168,124,0.12), transparent 60%); }
.home-bento-tile--violet::before { background: linear-gradient(135deg, rgba(197,185,212,0.14), transparent 60%); }
.home-bento-tile--mint::before { background: linear-gradient(135deg, rgba(168,213,186,0.14), transparent 60%); }
.home-bento-tile--teal::before { background: linear-gradient(135deg, rgba(93,174,139,0.12), transparent 60%); }
@media (prefers-reduced-motion: no-preference) {
    .home-bento-tile:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 28px rgba(44, 36, 32, 0.08);
        border-color: rgba(184, 144, 138, 0.22);
    }
    .home-bento-tile:hover::before { opacity: 1; }
}
.home-bento-tile--banner {
    grid-column: span 6;
    min-height: 88px;
    flex-direction: row;
    align-items: center;
    gap: 16px;
    padding: 20px 24px;
    background: linear-gradient(120deg, rgba(255,252,249,0.95), rgba(234,243,236,0.85));
    border-color: rgba(184, 144, 138, 0.15);
}
.home-bento-tile--large { grid-column: span 3; min-height: 130px; }
.home-bento-tile--medium { grid-column: span 2; min-height: 118px; }
.home-bento-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    position: relative;
    z-index: 1;
}
.home-bento-emoji {
    font-size: 22px;
    line-height: 1;
    flex-shrink: 0;
}
.home-bento-arrow {
    font-size: 18px;
    color: #C4AFA5;
    transition: transform 0.25s ease, color 0.25s ease;
    flex-shrink: 0;
}
.home-bento-tile:hover .home-bento-arrow {
    color: #B8908A;
    transform: translateX(3px);
}
.home-bento-body { position: relative; z-index: 1; flex: 1; min-width: 0; }
.home-bento-name {
    font-size: 15px;
    font-weight: 650;
    color: #2C2420;
    line-height: 1.35;
    margin-bottom: 4px;
}
.home-bento-desc {
    font-size: 12px;
    color: #6B5B52;
    line-height: 1.55;
}
.home-bento-tile--banner .home-bento-name { font-size: 16px; }
.home-bento-tile--banner .home-bento-desc { font-size: 13px; }

.home-privacy-note {
    color: #9E8E83;
    font-size: 12px;
    text-align: center;
    margin-top: 8px;
    padding-bottom: 8px;
}

/* 响应式 */
@media (max-width: 860px) {
    .home-guide-cards {
        grid-template-columns: 1fr;
    }
    .home-bento { grid-template-columns: repeat(2, 1fr); }
    .home-bento-tile--banner,
    .home-bento-tile--large,
    .home-bento-tile--medium { grid-column: span 2; }
    .home-flow-track::before { display: none; }
}
@media (max-width: 560px) {
    .home-bento { grid-template-columns: 1fr; }
    .home-bento-tile--banner,
    .home-bento-tile--large,
    .home-bento-tile--medium { grid-column: span 1; }
    .home-bento-tile--banner { flex-direction: column; align-items: flex-start; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_hero(greeting: str) -> None:
    st.markdown(
        f"""
<div class="home-page-marker" aria-hidden="true"></div>
<div class="home-canvas-bg" aria-hidden="true">
  <div class="home-ambient-orb home-ambient-orb--1"></div>
  <div class="home-ambient-orb home-ambient-orb--2"></div>
  <div class="home-ambient-orb home-ambient-orb--3"></div>
</div>
<div class="home-hero mirror-reveal">
  <div class="home-greeting">{greeting}</div>
  <div class="intro-main">求职这条路上，你不是一个人</div>
  <div class="intro-sub">职场镜子 · 陪你走过最难熬的求职路</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_five_second_guide() -> None:
    st.markdown(
        """
<div class="home-guide-shell mirror-reveal">
  <div class="home-guide-title">✨ 职场镜子，5 秒了解</div>
  <div class="home-guide-cards">
    <div class="home-guide-card mirror-reveal mirror-stagger-1">
      <div class="home-guide-card-emoji">🫂</div>
      <div class="home-guide-card-head">先接住情绪</div>
      <div class="home-guide-card-desc">投了两个月没回音的深夜，谁来接住你的焦虑？</div>
    </div>
    <div class="home-guide-card mirror-reveal mirror-stagger-2">
      <div class="home-guide-card-emoji">🔍</div>
      <div class="home-guide-card-head">再看见价值</div>
      <div class="home-guide-card-desc">你的简历里有多少金子，你自己可能没看见</div>
    </div>
    <div class="home-guide-card mirror-reveal mirror-stagger-3">
      <div class="home-guide-card-emoji">🔏</div>
      <div class="home-guide-card-head">然后翻案</div>
      <div class="home-guide-card-desc">逐条采纳 AI 建议，导出一份能投的简历</div>
    </div>
  </div>
  <div class="home-guide-slogan">帮你看见，不替你决定</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_product_flow() -> None:
    st.markdown(
        """
<div class="home-flow-shell mirror-reveal-slow">
  <div class="home-flow-title">你的求职全流程陪伴</div>
  <div class="home-flow-track">
    <div class="home-flow-step">
      <div class="home-flow-dot">💙</div>
      <div class="home-flow-name">情绪急救</div>
      <div class="home-flow-desc">先让心里舒服一点</div>
    </div>
    <div class="home-flow-step">
      <div class="home-flow-dot">✨</div>
      <div class="home-flow-name">金子探测</div>
      <div class="home-flow-desc">看见简历优势</div>
    </div>
    <div class="home-flow-step">
      <div class="home-flow-dot">🔨</div>
      <div class="home-flow-name">金子工坊</div>
      <div class="home-flow-desc">逐条优化到能投</div>
    </div>
    <div class="home-flow-step">
      <div class="home-flow-dot">📄</div>
      <div class="home-flow-name">导出投递</div>
      <div class="home-flow-desc">带走好简历</div>
    </div>
  </div>
  <div class="home-flow-foot">主链路之外，还有平行宇宙 · 职业基因 · 人才共情链等你探索</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_feature_bento() -> None:
    tiles_html = []
    size_class = {"banner": "banner", "large": "large", "medium": "medium"}
    for i, tile in enumerate(FEATURE_TILES):
        size = size_class.get(tile["size"], "medium")
        accent = tile.get("accent", "rose")
        emoji = tile.get("emoji", "")
        stagger = min(i + 1, 4)

        if size == "banner":
            inner = (
                f'<div class="home-bento-body">'
                f'<div class="home-bento-name">{tile["name"]}</div>'
                f'<div class="home-bento-desc">{tile["desc"]}</div></div>'
                f'<div class="home-bento-arrow">→</div>'
            )
        else:
            inner = (
                f'<div class="home-bento-top">'
                f'<span class="home-bento-emoji">{emoji}</span>'
                f'<span class="home-bento-arrow">→</span></div>'
                f'<div class="home-bento-body">'
                f'<div class="home-bento-name">{tile["name"]}</div>'
                f'<div class="home-bento-desc">{tile["desc"]}</div></div>'
            )

        tiles_html.append(
            f'<a class="home-bento-tile home-bento-tile--{size} home-bento-tile--{accent} '
            f'mirror-reveal mirror-stagger-{stagger}" href="?nav={tile["route"]}" target="_self">'
            f"{inner}</a>"
        )

    st.markdown(
        f"""
<div class="home-stage-block">
<div class="home-section-head home-section-head--lite mirror-reveal">
  <div class="home-section-meta">7 个模块 · 按需使用 · 点击即达</div>
</div>
<div class="home-bento">
{"".join(tiles_html)}
</div>
<div class="home-privacy-note">你的所有数据只存在你的浏览器里，关掉就没了 🔒</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _on_home_emotion_change() -> None:
    st.session_state.home_emotion_touched = True
    st.session_state.home_emotion_stay_on_home = False
    st.session_state.home_emotion_score = st.session_state.home_emotion_slider
    from utils.emotion_adapter import sync_emotion_to_session

    sync_emotion_to_session()


def _render_diary_entry() -> None:
    st.markdown(
        """
<div class="home-diary-card mirror-reveal">
  <div class="home-diary-title">📔 情绪日记</div>
  <div class="home-diary-desc">每天签个到，追踪求职心情曲线</div>
</div>
<style>
.home-diary-card {
  margin: 0 0 12px; padding: 14px 16px;
  background: linear-gradient(135deg, rgba(184,144,138,0.12), rgba(255,252,249,0.95));
  border: 1px solid rgba(184,144,138,0.2); border-radius: 12px;
}
.home-diary-title { font-size: 14px; font-weight: 650; color: #2C2420; }
.home-diary-desc { font-size: 12px; color: #8C8279; margin-top: 4px; }
</style>
""",
        unsafe_allow_html=True,
    )
    if st.button("去签到 →", key="home_go_diary", use_container_width=True):
        st.session_state.emotion_show_diary = True
        navigate_to_page("emotion")
        st.rerun()


def _render_emotion_entry() -> None:
    if "home_emotion_touched" not in st.session_state:
        st.session_state.home_emotion_touched = False
    if "home_emotion_score" not in st.session_state:
        st.session_state.home_emotion_score = None

    st.markdown('<div class="home-emotion-marker"></div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="home-emotion-card">
<div class="home-emotion-title">今天求职状态几度？</div>
<div class="home-emotion-hint">拖一拖，告诉我你的感受</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.slider(
        "今天求职状态几度？",
        min_value=1,
        max_value=10,
        value=5,
        label_visibility="collapsed",
        key="home_emotion_slider",
        on_change=_on_home_emotion_change,
    )

    if st.session_state.home_emotion_touched and not st.session_state.get(
        "home_emotion_stay_on_home"
    ):
        score = int(st.session_state.home_emotion_score or st.session_state.home_emotion_slider)
        st.session_state.home_emotion_score = score

        if score <= 4:
            st.info("🫂 今天可能不太好——需要聊聊的话，可以去情绪急救站")
            label = "去情绪急救站"
            target = "💙 情绪急救站"
        elif score <= 6:
            st.info("有点焦虑？金子探测器可以帮你重新看见简历里的闪光点")
            label = "去金子探测器"
            target = "✨ 金子探测器"
        else:
            st.info("状态不错！职业基因测序可以帮你看清适合的方向")
            label = "去职业基因"
            target = "🧬 职业基因"

        col_go, col_stay = st.columns(2)
        with col_go:
            if st.button(label, key="home_emotion_go", type="primary", use_container_width=True):
                st.session_state.current_page = target
                if target == "💙 情绪急救站":
                    st.session_state.emotion_start_score = score
                    st.session_state.emotion_start_touched = True
                from utils.emotion_adapter import sync_emotion_to_session

                sync_emotion_to_session()
                st.rerun()
        with col_stay:
            if st.button(
                "留在首页",
                key="home_emotion_stay",
                use_container_width=True,
            ):
                st.session_state.home_emotion_stay_on_home = True
                st.rerun()


def render():
    _consume_page_query()
    _inject_home_styles()

    hour = datetime.now().hour
    if hour < 6:
        greeting = "夜深了"
    elif hour < 12:
        greeting = "早上好"
    elif hour < 14:
        greeting = "中午好"
    elif hour < 18:
        greeting = "下午好"
    else:
        greeting = "晚上好"

    _render_hero(greeting)

    col_main, col_aside = st.columns([1.65, 1], gap="medium")
    with col_main:
        _render_five_second_guide()
        _render_product_flow()
        render_home_journey_bridge()
    with col_aside:
        st.markdown('<div class="home-col-aside-wrap">', unsafe_allow_html=True)
        with st.container():
            _render_emotion_entry()
        _render_diary_entry()
        render_progress_dashboard(compact=True, show_modules=True)
        st.markdown("</div>", unsafe_allow_html=True)

    render_section_connector()
    _render_feature_bento()
