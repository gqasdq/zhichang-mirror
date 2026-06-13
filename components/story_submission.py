"""人才共情链 — 用户故事投稿。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from core.session_manager import SessionManager


def _submissions_path() -> Path:
    return SessionManager.user_file_path("empathy/submissions.json")


def load_submissions() -> list[dict]:
    path = _submissions_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_submission(story: str, tags: str = "") -> None:
    path = _submissions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    items = load_submissions()
    items.append({
        "story": story.strip(),
        "tags": tags.strip(),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "pending_review",
    })
    path.write_text(json.dumps(items[-20:], ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        from vectorstore.incremental import IncrementalVectorStore

        store = IncrementalVectorStore()
        store.queue_add(story, {"type": "user_story", "tags": tags, "source": "submission"})
    except Exception:
        pass


def render_story_submission() -> None:
    """渲染故事投稿表单。"""
    if not st.session_state.get("_story_submit_styles"):
        st.session_state["_story_submit_styles"] = True
        st.markdown(
            """
<style>
.story-submit-shell {
  margin: 24px 0; padding: 20px 22px;
  background: rgba(255,255,255,0.72);
  border: 1px dashed rgba(184, 144, 138, 0.35);
  border-radius: 14px;
}
.story-submit-title { font-size: 15px; font-weight: 650; color: #2C2420; }
.story-submit-sub { font-size: 12px; color: #8C8279; margin: 4px 0 12px; }
</style>
""",
            unsafe_allow_html=True,
        )

    st.markdown(
        """
<div class="story-submit-shell mirror-reveal">
  <div class="story-submit-title">✍️ 分享你的故事</div>
  <div class="story-submit-sub">匿名投稿，经脱敏后可能帮助更多同行者（不会展示联系方式）</div>
</div>
""",
        unsafe_allow_html=True,
    )

    story = st.text_area(
        "你的故事",
        placeholder="比如：投了三个月没回音，后来调整了方向，找到了更合适的岗位...",
        height=100,
        key="empathy_submit_story",
        label_visibility="collapsed",
    )
    tags = st.text_input("标签（可选）", placeholder="焦虑 · 转行 · 逆袭", key="empathy_submit_tags")
    if st.button("投稿", key="empathy_submit_btn", type="primary"):
        text = (story or "").strip()
        if len(text) < 20:
            st.warning("至少写 20 个字，帮后来者感受到真实。")
            return
        save_submission(text, tags or "")
        st.success("感谢分享！你的故事已收录，会帮助更多同行者。")
        st.session_state["empathy_submit_story"] = ""
        st.rerun()

    subs = load_submissions()
    if subs:
        st.caption(f"你已投稿 {len(subs)} 条故事")
