"""GSAP 风格动效 — Streamlit 内用 CSS 实现，兼容 prefers-reduced-motion。"""

import streamlit as st


def inject_mirror_motion() -> None:
    """注入全局入场动画（由 styles.py 调用，无需 GSAP CDN）。"""
    st.markdown(
        """
<style>
@keyframes mirror-rise {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes mirror-fade {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@media (prefers-reduced-motion: no-preference) {
  .mirror-reveal {
    animation: mirror-rise 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
  }
  .mirror-reveal-slow {
    animation: mirror-rise 0.65s cubic-bezier(0.22, 1, 0.36, 1) both;
  }
  .mirror-fade-in {
    animation: mirror-fade 0.4s ease both;
  }
  .mirror-stagger-1 { animation-delay: 0.05s; }
  .mirror-stagger-2 { animation-delay: 0.10s; }
  .mirror-stagger-3 { animation-delay: 0.15s; }
  .mirror-stagger-4 { animation-delay: 0.20s; }
  .feature-item {
    transition: background 0.22s cubic-bezier(0.22, 1, 0.36, 1),
                transform 0.22s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .feature-item:hover {
    transform: translateX(4px);
  }
  .home-bento-tile {
    transition: border-color 0.25s ease, box-shadow 0.25s ease,
                transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .sidebar-nav-item {
    transition: background 0.2s ease, color 0.2s ease;
  }
  .mirror-insight-card,
  .story-card,
  .gene-card {
    transition: box-shadow 0.25s ease, border-color 0.25s ease;
  }
  .mirror-insight-card:hover,
  .story-card:hover,
  .gene-card:hover {
    box-shadow: 0 4px 18px rgba(44, 36, 32, 0.06) !important;
  }
}
@media (prefers-reduced-motion: reduce) {
  .mirror-reveal, .mirror-reveal-slow, .mirror-fade-in {
    animation: none !important;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )
