"""求职进度看板 — 全流程追踪。"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import streamlit as st

from core.session_manager import SessionManager

# 求职主链路：简历 → 分析 → 优化 → 投递 → 面试准备
JOURNEY_STEPS = [
    ("resume", "📄", "简历上传", "resume_done"),
    ("analysis", "🔍", "优势分析", "analysis_done"),
    ("optimize", "🔨", "简历优化", "optimize_done"),
    ("apply", "📤", "导出投递", "apply_done"),
    ("interview", "💼", "面试准备", "interview_done"),
]

MODULE_STEPS = [
    ("emotion", "💙", "情绪急救", "emotion_done"),
    ("gold", "✨", "金子探测", "gold_done"),
    ("workshop", "🔨", "简历优化", "workshop_done"),
    ("parallel", "🌌", "平行宇宙", "parallel_done"),
    ("gene", "🧬", "职业基因", "gene_done"),
    ("empathy", "🔗", "共情链", "empathy_done"),
]


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _history_has_entries(*relative_parts: str) -> bool:
    data = _load_json(SessionManager.user_file_path(*relative_parts))
    return isinstance(data, list) and len(data) > 0


def _probes_have_resume() -> bool:
    data = _load_json(SessionManager.user_file_path("gold_probes.json"))
    if not isinstance(data, list):
        return False
    return any((p.get("resume_snippet") or "").strip() for p in data if isinstance(p, dict))


def _probes_have_analysis() -> bool:
    data = _load_json(SessionManager.user_file_path("gold_probes.json"))
    if not isinstance(data, list):
        return False
    for probe in data:
        if not isinstance(probe, dict):
            continue
        result = probe.get("result") or {}
        if result.get("analysis") or result.get("match_results"):
            return True
    return False


def _detect_journey_progress() -> dict[str, bool]:
    """检测求职主链路五步进度（会话状态 + 持久化文件）。"""
    ss = st.session_state

    resume_done = bool(
        (ss.get("gold_resume_text") or "").strip()
        or (ss.get("workshop_resume_text") or "").strip()
        or ss.get("gold_upload_name")
        or _probes_have_resume()
    )

    gold_convs = ss.get("gold_conversations") or []
    analysis_done = bool(
        ss.get("gold_current_result")
        or (isinstance(gold_convs, list) and len(gold_convs) > 0)
        or _probes_have_analysis()
    )

    adopted = ss.get("workshop_adopted") or {}
    optimize_done = isinstance(adopted, dict) and any(
        v == "optimized" for v in adopted.values()
    )

    apply_done = bool(ss.get("workshop_pdf_bytes")) or SessionManager.user_file_path(
        "workshop", "exported.json"
    ).exists()

    interview_done = bool(ss.get("parallel_result") or ss.get("gene_result")) or (
        _history_has_entries("parallel", "history.json")
        or _history_has_entries("gene", "history.json")
    )

    return {
        "resume_done": resume_done,
        "analysis_done": analysis_done,
        "optimize_done": optimize_done,
        "apply_done": apply_done,
        "interview_done": interview_done,
    }


def _detect_module_progress() -> dict[str, bool]:
    ss = st.session_state
    journey = _detect_journey_progress()
    return {
        "emotion_done": bool(ss.get("emotion_chat_history") or ss.get("chat_started"))
        or _history_has_entries("emotion", "history.json"),
        "gold_done": journey["analysis_done"],
        "workshop_done": journey["optimize_done"],
        "parallel_done": bool(ss.get("parallel_result"))
        or _history_has_entries("parallel", "history.json"),
        "gene_done": bool(ss.get("gene_result"))
        or _history_has_entries("gene", "history.json"),
        "empathy_done": bool(ss.get("empathy_result"))
        or _history_has_entries("empathy", "history.json"),
    }


def _next_journey_hint(progress: dict[str, bool]) -> str:
    hints = {
        "resume_done": "上传简历，开始看见自己的优势",
        "analysis_done": "去金子探测器，看看简历里藏着什么",
        "optimize_done": "去金子工坊，逐条优化到能投",
        "apply_done": "导出 PDF，带着好简历去投递",
        "interview_done": "用平行宇宙 / 职业基因，为面试做准备",
    }
    for _key, _emoji, _label, flag in JOURNEY_STEPS:
        if not progress.get(flag, False):
            return hints.get(flag, "继续下一步吧")
    return "全流程已完成，祝你求职顺利 🎉"


_STEP_ROUTES = {
    "resume_done": "gold",
    "analysis_done": "gold",
    "optimize_done": "workshop",
    "apply_done": "workshop",
    "interview_done": "parallel",
}


def get_journey_snapshot() -> dict[str, Any]:
    """供首页等外部组件使用的进度快照。"""
    journey = _detect_journey_progress()
    done = sum(1 for v in journey.values() if v)
    total = len(JOURNEY_STEPS)
    next_action: dict[str, str] = {
        "emoji": "🎉",
        "label": "全流程已完成",
        "hint": _next_journey_hint(journey),
        "route": "gold",
    }
    for _key, emoji, label, flag in JOURNEY_STEPS:
        if not journey.get(flag, False):
            next_action = {
                "emoji": emoji,
                "label": label,
                "hint": _next_journey_hint(journey),
                "route": _STEP_ROUTES.get(flag, "gold"),
            }
            break
    return {
        "journey": journey,
        "done": done,
        "total": total,
        "pct": int(done / total * 100) if total else 0,
        "next": next_action,
    }


def render_progress_dashboard(compact: bool = False, show_modules: bool = True) -> None:
    """渲染求职进度看板。"""
    journey = _detect_journey_progress()
    modules = _detect_module_progress()

    journey_done = sum(1 for v in journey.values() if v)
    journey_total = len(JOURNEY_STEPS)
    journey_pct = int(journey_done / journey_total * 100) if journey_total else 0

    module_done = sum(1 for v in modules.values() if v)
    module_total = len(MODULE_STEPS)
    module_pct = int(module_done / module_total * 100) if module_total else 0

    if not st.session_state.get("_progress_dash_styles"):
        st.session_state["_progress_dash_styles"] = True
        st.markdown(
            """
<style>
.progress-dash-shell {
  margin: 0; padding: 16px 18px;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(61,56,51,0.08); border-radius: 14px;
  box-shadow: 0 4px 24px rgba(44, 36, 32, 0.03);
}
.progress-dash-shell--compact { padding: 14px 16px; }
.progress-dash-title { font-size: 13px; font-weight: 650; color: #2C2420; margin-bottom: 10px; }
.progress-dash-subtitle {
  font-size: 11px; color: #8C8279; margin: -6px 0 10px; line-height: 1.45;
}
.progress-dash-bar {
  height: 6px; background: rgba(61,56,51,0.08); border-radius: 3px; overflow: hidden; margin-bottom: 14px;
}
.progress-dash-fill {
  height: 100%; background: linear-gradient(90deg, #B8908A, #5DAE8B);
  border-radius: 3px; transition: width 0.5s ease;
}
.progress-steps { display: flex; flex-wrap: wrap; gap: 6px; }
.progress-step {
  text-align: center;
  padding: 7px 4px; border-radius: 10px; font-size: 10px;
  border: 1px solid rgba(61,56,51,0.06);
  flex: 1 1 56px; min-width: 52px;
}
.progress-dash-shell:not(.progress-dash-shell--compact) .progress-step {
  flex: 1 1 72px; min-width: 64px; font-size: 11px; padding: 8px 6px;
}
.progress-step--done { background: rgba(93,174,139,0.12); color: #3D8A6A; }
.progress-step--pending { background: rgba(255,255,255,0.5); color: #9E8E83; }
.progress-step--current {
  background: rgba(184,144,138,0.14); color: #6B5B52;
  border-color: rgba(184,144,138,0.35);
}
.progress-step-emoji { font-size: 16px; display: block; margin-bottom: 2px; }
.progress-modules-divider {
  margin: 12px 0 10px; border-top: 1px dashed rgba(61,56,51,0.1);
}
.progress-modules-label {
  font-size: 10px; color: #9E8E83; margin-bottom: 8px;
}
</style>
""",
            unsafe_allow_html=True,
        )

    def _build_steps_html(steps: list, progress: dict[str, bool], mark_current: bool = False) -> str:
        html_parts = ""
        current_flag = None
        if mark_current:
            for _k, _e, _l, flag in steps:
                if not progress.get(flag, False):
                    current_flag = flag
                    break
        for _key, emoji, label, flag in steps:
            done = progress.get(flag, False)
            if done:
                cls = "progress-step--done"
            elif mark_current and flag == current_flag:
                cls = "progress-step--current"
            else:
                cls = "progress-step--pending"
            mark = "✓" if done else ("→" if flag == current_flag else "·")
            html_parts += (
                f'<div class="progress-step {cls} mirror-reveal">'
                f'<span class="progress-step-emoji">{emoji}</span>{html.escape(label)} {mark}</div>'
            )
        return html_parts

    title = "求职进度" if compact else "🧭 你的求职全流程进度"
    compact_cls = " progress-dash-shell--compact" if compact else ""
    hint = _next_journey_hint(journey)

    modules_block = ""
    if show_modules:
        modules_block = f"""
  <div class="progress-modules-divider"></div>
  <div class="progress-modules-label">模块探索 · {module_done}/{module_total}</div>
  <div class="progress-dash-bar"><div class="progress-dash-fill" style="width:{module_pct}%;opacity:0.65;"></div></div>
  <div class="progress-steps">{_build_steps_html(MODULE_STEPS, modules, mark_current=False)}</div>"""

    st.markdown(
        f"""
<div class="progress-dash-shell{compact_cls} mirror-reveal">
  <div class="progress-dash-title">{title} · {journey_done}/{journey_total}</div>
  <div class="progress-dash-subtitle">{html.escape(hint)}</div>
  <div class="progress-dash-bar"><div class="progress-dash-fill" style="width:{journey_pct}%;"></div></div>
  <div class="progress-steps">{_build_steps_html(JOURNEY_STEPS, journey, mark_current=True)}</div>
  {modules_block}
</div>
""",
        unsafe_allow_html=True,
    )
