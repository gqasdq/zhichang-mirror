import streamlit as st

from ui.motion import inject_mirror_motion


def inject_styles():
    inject_mirror_motion()
    st.markdown(
        """
    <style>
    :root {
        --mirror-bg: #F7F3EF;
        --mirror-bg-sidebar: #F0EBE3;
        --mirror-surface: rgba(255, 255, 255, 0.78);
        --mirror-ink: #2C2420;
        --mirror-ink-secondary: #5C4F47;
        --mirror-muted: #6B5B52;
        --mirror-muted-light: #8C8279;
        --mirror-accent: #B8908A;
        --mirror-accent-hover: #A07A74;
        --mirror-border: rgba(61, 56, 51, 0.08);
        --mirror-border-accent: rgba(184, 144, 138, 0.18);
        --mirror-radius-md: 12px;
        --mirror-radius-lg: 16px;
        --mirror-content-max: 1080px;
    }

    header { visibility: hidden; height: 0 !important; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    div[data-testid="stToolbar"] { display: none !important; }
    [data-testid="stSidebarHeader"] { display: none !important; height: 0 !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    .stApp {
        background: radial-gradient(ellipse at 20% 0%, rgba(255,252,249,0.9) 0%, var(--mirror-bg) 55%);
        color: var(--mirror-ink);
    }

    /* 主内容区：更宽、更充实 */
    [data-testid="stSidebar"] + div > div > div {
        max-width: 100% !important;
        width: 100% !important;
        margin: 0 !important;
    }
    .block-container {
        max-width: var(--mirror-content-max) !important;
        width: 100% !important;
        padding: 0 2rem 2rem !important;
        margin: 0 auto !important;
    }
    [data-testid="stAppViewContainer"] > .main .block-container {
        padding-top: 6px !important;
    }
    [data-testid="stMainBlockContainer"] {
        padding-top: 6px !important;
        padding-bottom: 1.25rem !important;
        gap: 0.45rem !important;
    }
    [data-testid="stAppViewContainer"] > .main {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    header { margin-bottom: 0 !important; }

    /* 侧边栏 */
    [data-testid="stSidebarContent"] {
        padding: 0 !important;
        margin: 0 !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
    }
    [data-testid="stSidebar"],
    section[data-testid="stSidebar"] {
        background-color: var(--mirror-bg-sidebar) !important;
        border-right: 1px solid #E0D8CF;
        min-width: 280px !important;
        max-width: 280px !important;
        width: 280px !important;
        transform: none !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
    }
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"][aria-expanded="false"],
    section[data-testid="stSidebar"][aria-expanded="false"] > div:first-child {
        width: 280px !important;
        min-width: 280px !important;
        max-width: 280px !important;
        transform: none !important;
        margin-left: 0 !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding: 1.25rem 1rem !important;
        max-width: 100% !important;
    }
    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] .stButton button {
        font-size: 14px !important;
        padding: 8px 12px !important;
        min-height: 38px !important;
        border-radius: var(--mirror-radius-md) !important;
    }
    section[data-testid="stSidebar"] ::-webkit-scrollbar {
        display: none !important;
    }

    .stApp, .stMarkdown, p, a, div {
        font-family: "PingFang SC", "Noto Sans SC", "Source Han Sans SC", system-ui, sans-serif;
    }
    a, a:visited, a:hover, a:active {
        color: inherit !important;
        text-decoration: none !important;
    }

    /* 统一页面标题 */
    .mirror-page-header {
        margin-top: 0;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--mirror-border);
    }
    .mirror-page-eyebrow {
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.04em;
        color: var(--mirror-accent);
        margin-bottom: 6px;
    }
    .mirror-page-title {
        font-size: 24px;
        font-weight: 650;
        color: var(--mirror-ink);
        line-height: 1.35;
        text-wrap: balance;
    }
    .mirror-page-subtitle {
        margin-top: 6px;
        font-size: 14px;
        color: var(--mirror-muted);
        line-height: 1.55;
    }
    .mirror-section-title {
        font-size: 15px;
        font-weight: 650;
        color: var(--mirror-ink);
        margin: 20px 0 12px;
    }

    /* 洞察卡片 */
    .mirror-insight-card {
        background: rgba(184, 144, 138, 0.06);
        border: 1px solid var(--mirror-border-accent);
        border-radius: var(--mirror-radius-md);
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .mirror-insight-title {
        font-size: 14px;
        font-weight: 650;
        color: var(--mirror-ink);
        margin-bottom: 4px;
    }
    .mirror-insight-body {
        font-size: 13px;
        line-height: 1.65;
        color: var(--mirror-ink-secondary);
    }
    .mirror-insight-tag {
        margin-top: 6px;
        font-size: 12px;
        color: var(--mirror-muted-light);
    }

    /* 全局按钮 */
    .stButton > button[kind="primary"],
    button[kind="primary"] {
        background-color: var(--mirror-accent) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--mirror-accent) !important;
        border-radius: 10px !important;
        font-weight: 550 !important;
        min-height: 40px !important;
        transition: background 0.2s ease, border-color 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[kind="primary"]:hover {
        background-color: var(--mirror-accent-hover) !important;
        border-color: var(--mirror-accent-hover) !important;
    }
    .stButton > button:not([kind="primary"]) {
        background: var(--mirror-surface) !important;
        color: var(--mirror-ink) !important;
        border: 1px solid var(--mirror-border-accent) !important;
        border-radius: 10px !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        border-color: var(--mirror-accent) !important;
        background: rgba(184, 144, 138, 0.06) !important;
    }

    /* 全局输入框 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stTextarea > div > div > textarea {
        background: rgba(255, 255, 255, 0.85) !important;
        border: 1px solid rgba(184, 144, 138, 0.2) !important;
        border-radius: 10px !important;
        color: var(--mirror-ink) !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--mirror-accent) !important;
        box-shadow: 0 0 0 1px rgba(184, 144, 138, 0.35) !important;
    }

    /* 折叠面板 */
    [data-testid="stExpander"] details {
        border: 1px solid var(--mirror-border) !important;
        border-radius: var(--mirror-radius-md) !important;
        background: var(--mirror-surface) !important;
    }
    [data-testid="stExpander"] summary {
        color: var(--mirror-muted) !important;
        font-size: 13px !important;
    }

    /* 首页：由 home.py 内联样式驱动 bento 布局，此处仅保留 Streamlit 容器适配 */
    .home-layout {
        width: 100%;
        max-width: 960px;
        margin: 0 auto;
        padding-top: 4px;
    }
    .mood-title { color: var(--mirror-muted-light); font-size: 14px; font-weight: 500; margin-bottom: 8px; }
    .mood-row { display: flex; flex-wrap: nowrap; gap: 10px; margin-bottom: 12px; }
    .mood-btn {
        display: inline-block;
        height: 41px;
        line-height: 41px;
        padding: 0 18px;
        border-radius: 20.5px;
        border: 1px solid #D5CBBF;
        background-color: #F3EEE8;
        color: var(--mirror-ink) !important;
        font-size: 14px;
        font-weight: 500;
        white-space: nowrap;
    }
    .mood-btn:hover, .mood-btn.active {
        background-color: var(--mirror-accent);
        color: #FFFFFF !important;
        border-color: var(--mirror-accent);
    }
    .section-divider {
        border-top: 1px solid var(--mirror-border);
        width: 100%;
        margin: 0;
    }
    .feature-list { width: 100%; }
    .feature-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 88px;
        padding: 20px 4px;
        border-bottom: 1px solid var(--mirror-border);
        color: var(--mirror-ink) !important;
        border-radius: 8px;
    }
    .feature-item:hover {
        background: rgba(184, 144, 138, 0.04);
    }
    .feature-left { display: flex; flex-direction: column; justify-content: center; min-height: 48px; }
    .feature-name { font-size: 16px; color: var(--mirror-ink) !important; font-weight: 600; line-height: 1.35; }
    .feature-desc { font-size: 13px; color: var(--mirror-muted) !important; margin-top: 3px; line-height: 1.5; }
    .feature-arrow { font-size: 18px; color: #C4AFA5 !important; width: 20px; text-align: center; }
    .home-footer-text, .home-privacy-note {
        color: var(--mirror-muted-light);
        font-size: 12px;
        text-align: center;
        margin-top: 16px;
    }
    div[data-testid="stVerticalBlock"]:has(.home-emotion-marker) {
        background: rgba(255, 255, 255, 0.78) !important;
        border: 1px solid var(--mirror-border-accent) !important;
        border-radius: var(--mirror-radius-lg) !important;
        padding: 18px 20px 14px !important;
        margin: 0 0 0 !important;
        max-width: 100% !important;
        width: 100% !important;
        box-shadow: 0 4px 24px rgba(44, 36, 32, 0.04) !important;
    }
    div[data-testid="stVerticalBlock"]:has(.progress-dash-shell) {
        margin: 0 !important;
        max-width: 100% !important;
    }

    /* 侧边栏导航 */
    .sidebar-shell { width: 100%; box-sizing: border-box; }
    .sidebar-top { padding: 8px 0 10px; }
    .sidebar-brand-title { color: var(--mirror-ink); font-size: 19px; font-weight: 650; line-height: 1.35; }
    .sidebar-brand-subtitle { color: var(--mirror-muted-light); font-size: 12px; margin-top: 2px; }
    .sidebar-divider { border-top: 1px solid #E0D8CF; margin: 8px 0; }
    .sidebar-nav-list { padding-top: 6px; }
    .sidebar-nav-item {
        display: flex;
        align-items: center;
        min-height: 38px;
        padding: 7px 12px;
        margin-bottom: 3px;
        border-radius: 10px;
        color: var(--mirror-muted) !important;
        font-size: 14px;
        font-weight: 500;
    }
    .sidebar-nav-item.active {
        background: rgba(184, 144, 138, 0.14);
        color: var(--mirror-ink) !important;
        font-weight: 600;
    }
    .sidebar-footer { color: var(--mirror-muted-light); font-size: 12px; line-height: 1.55; padding-top: 8px; }

    .stButton, [data-testid="stHorizontalBlock"], [data-testid="stVerticalBlock"] {
        margin: 0 !important;
        padding: 0 !important;
    }

    /* ── 情绪界面呼吸（全局，由 JS bridge 设置 .stApp[data-emotion]） ── */
    .emotion-transition, .emotion-transition * {
        transition: background-color 1.5s ease, border-color 1.2s ease, color 0.8s ease, box-shadow 1.5s ease !important;
    }
    .stApp.emotion-active,
    .stApp.emotion-active section[data-testid="stSidebar"],
    .stApp.emotion-active .gold-report-shell,
    .stApp.emotion-active .jd-match-report,
    .stApp.emotion-active button[kind="primary"] {
        transition: background 1.5s ease, background-color 1.5s ease,
                    border-color 1.2s ease, color 0.8s ease, box-shadow 1.5s ease !important;
    }
    @keyframes emotionBadgeIn {
        from { opacity: 0; transform: translateY(-6px) scale(0.98); }
        to   { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes emotionFadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes emotionBreatheAnxious {
        0%, 100% { box-shadow: 0 2px 14px rgba(196,168,130,0.14); transform: scale(1); }
        50%      { box-shadow: 0 10px 32px rgba(196,168,130,0.30); transform: scale(1.003); }
    }
    @keyframes emotionBreatheFrustrated {
        0%, 100% { box-shadow: 0 2px 14px rgba(93,174,139,0.12); }
        50%      { box-shadow: 0 8px 26px rgba(93,174,139,0.24); }
    }
    @keyframes emotionBreatheConfused {
        0%, 100% { box-shadow: 0 2px 12px rgba(168,146,126,0.12); }
        50%      { box-shadow: 0 8px 24px rgba(168,146,126,0.22); }
    }
    @keyframes emotionSlideIn {
        from { opacity: 0; transform: translateX(-12px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes emotionGlow {
        0%, 100% { border-color: rgba(93,174,139,0.30); }
        50%      { border-color: rgba(93,174,139,0.60); }
    }
    @keyframes emotionAmbientPulse {
        0%, 100% { opacity: 0.55; }
        50%      { opacity: 0.85; }
    }
    .emotion-encourage { animation: emotionFadeIn 0.8s cubic-bezier(0.22, 1, 0.36, 1) both; }
    .breathe-card { animation: emotionBreatheAnxious 5s ease-in-out infinite; }
    .highlight-done {
        background: rgba(93,174,139,0.14) !important;
        border-left: 3px solid #5DAE8B !important;
        border-radius: 0 8px 8px 0 !important;
        animation: emotionGlow 3s ease-in-out infinite;
    }
    .step-guide { animation: emotionSlideIn 0.55s cubic-bezier(0.22, 1, 0.36, 1) forwards; }
    .step-guide-2 { animation-delay: 0.12s; opacity: 0; }
    .step-guide-3 { animation-delay: 0.24s; opacity: 0; }
    .stApp[data-emotion="anxious"],
    .stApp:has(#emotion-root[data-emotion="anxious"]) {
        --mirror-accent: #C4A882 !important;
        --mirror-accent-hover: #8B7355 !important;
        background: radial-gradient(ellipse 140% 95% at 50% -5%,
            rgba(196,168,130,0.38) 0%, #F3E8DC 40%, #F7F3EF 68%) !important;
    }
    .stApp[data-emotion="anxious"] section[data-testid="stSidebar"],
    .stApp:has(#emotion-root[data-emotion="anxious"]) section[data-testid="stSidebar"] {
        background-color: #E8DDD0 !important;
    }
    .stApp[data-emotion="anxious"] .gold-report-shell,
    .stApp[data-emotion="anxious"] .jd-match-report.emotion-surface,
    .stApp:has(#emotion-root[data-emotion="anxious"]) .gold-report-shell,
    .stApp:has(#emotion-root[data-emotion="anxious"]) .jd-match-report.emotion-surface {
        animation: emotionBreatheAnxious 5s ease-in-out infinite !important;
        background: rgba(255,250,245,0.94) !important;
        border: 1px solid rgba(196,168,130,0.38) !important;
        border-radius: 16px !important;
        padding: 20px 24px !important;
    }
    .stApp[data-emotion="anxious"] button[kind="primary"],
    .stApp[data-emotion="anxious"] .stButton > button[kind="primary"],
    .stApp:has(#emotion-root[data-emotion="anxious"]) button[kind="primary"],
    .stApp:has(#emotion-root[data-emotion="anxious"]) .stButton > button[kind="primary"] {
        background-color: #C4A882 !important;
        border-color: #8B7355 !important;
    }
    .stApp[data-emotion="frustrated"],
    .stApp:has(#emotion-root[data-emotion="frustrated"]) {
        --mirror-accent: #7EA88E !important;
        background: radial-gradient(ellipse 140% 95% at 50% -5%,
            rgba(126,168,142,0.32) 0%, #EAF3EC 40%, #F7F3EF 68%) !important;
    }
    .stApp[data-emotion="frustrated"] section[data-testid="stSidebar"],
    .stApp:has(#emotion-root[data-emotion="frustrated"]) section[data-testid="stSidebar"] {
        background-color: #DFEBE3 !important;
    }
    .stApp[data-emotion="frustrated"] .gold-report-shell,
    .stApp[data-emotion="frustrated"] .jd-match-report.emotion-surface,
    .stApp:has(#emotion-root[data-emotion="frustrated"]) .gold-report-shell,
    .stApp:has(#emotion-root[data-emotion="frustrated"]) .jd-match-report.emotion-surface {
        animation: emotionBreatheFrustrated 5.5s ease-in-out infinite !important;
        background: rgba(248,252,249,0.94) !important;
        border: 1px solid rgba(93,174,139,0.30) !important;
        border-radius: 16px !important;
    }
    .stApp[data-emotion="frustrated"] button[kind="primary"],
    .stApp:has(#emotion-root[data-emotion="frustrated"]) button[kind="primary"] {
        background-color: #7EA88E !important;
        border-color: #5DAE8B !important;
    }
    .stApp[data-emotion="confused"],
    .stApp:has(#emotion-root[data-emotion="confused"]) {
        --mirror-accent: #A8927E !important;
        background: radial-gradient(ellipse 140% 95% at 50% -5%,
            rgba(168,146,126,0.30) 0%, #F0EAE4 40%, #F7F3EF 68%) !important;
    }
    .stApp[data-emotion="confused"] section[data-testid="stSidebar"],
    .stApp:has(#emotion-root[data-emotion="confused"]) section[data-testid="stSidebar"] {
        background-color: #E5DDD5 !important;
    }
    .stApp[data-emotion="confused"] .gold-report-shell,
    .stApp[data-emotion="confused"] .jd-match-report.emotion-surface,
    .stApp:has(#emotion-root[data-emotion="confused"]) .gold-report-shell,
    .stApp:has(#emotion-root[data-emotion="confused"]) .jd-match-report.emotion-surface {
        animation: emotionBreatheConfused 5s ease-in-out infinite !important;
        border: 1px solid rgba(168,146,126,0.32) !important;
        border-radius: 16px !important;
    }
    .stApp[data-emotion="anxious"] .ws-diff-panel--ai,
    .stApp[data-emotion="anxious"] .ws-nav-shell {
        animation: emotionBreatheAnxious 5s ease-in-out infinite !important;
    }
    @media (prefers-reduced-motion: reduce) {
        .stApp[data-emotion] .gold-report-shell,
        .stApp[data-emotion] .jd-match-report,
        .breathe-card { animation: none !important; }
    }

    /* 情绪注入占位：不占垂直空间（保留 DOM 供 :has 选择器匹配） */
    #emotion-root,
    .emotion-bridge-anchor {
        position: absolute !important;
        width: 0 !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
    /* 零高 components iframe 兜底（若仍使用 components.html） */
    [data-testid="stElementContainer"]:has(iframe[title*="streamlit_components"]) {
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    iframe[title*="streamlit_components"] {
        height: 0 !important;
        min-height: 0 !important;
        border: none !important;
        display: block !important;
        visibility: hidden !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
