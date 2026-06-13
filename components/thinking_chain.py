"""AI 思考链路可视化 — 分步卡片替代 st.spinner。"""

from __future__ import annotations

import html
import threading
import time
from typing import Any, Callable, Optional

import streamlit as st

from core.model_router import model_router

MIN_DISPLAY_SEC = 1.5
MAX_DISPLAY_SEC = 3.0

# 预定义步骤模板
RESUME_ANALYSIS_STEPS = [
    {"title": "解析简历结构", "desc": "识别教育、经历、技能等板块布局"},
    {"title": "提取能力关键词", "desc": "从描述中挖掘可迁移的核心能力"},
    {"title": "STAR 结构检测", "desc": "检查情境-任务-行动-结果是否完整"},
    {"title": "量化表达评估", "desc": "扫描成果描述中的数字与规模"},
    {"title": "XAI 证据提取", "desc": "引用原文片段，构建可解释评分依据"},
    {"title": "综合评分计算", "desc": "加权汇总各维度质量得分"},
]

JD_MATCH_STEPS = [
    {"title": "解析岗位 JD", "desc": "提取岗位职责与任职要求"},
    {"title": "提取岗位关键要求", "desc": "识别硬性技能与软性能力关键词"},
    {"title": "语义匹配计算", "desc": "对比简历能力与岗位需求的契合度"},
    {"title": "三维加权评分", "desc": "关键词 × STAR × 量化 综合匹配分"},
]

GENE_ANALYSIS_STEPS = [
    {"title": "简历语义解析", "desc": "理解经历背后的能力模式"},
    {"title": "能力特征提取", "desc": "识别显性优势与潜在特质"},
    {"title": "6 维激活度计算", "desc": "空间思维、数据敏感等维度评级"},
    {"title": "潜力推导", "desc": "推断隐藏基因与发展方向"},
    {"title": "生成基因图谱", "desc": "整合报告与岗位推荐"},
]

WORKSHOP_STEPS: dict[str, list[dict[str, str]]] = {
    "work_exp": [
        {"title": "提取经历要素", "desc": "拆解职责、行动与成果"},
        {"title": "STAR 结构诊断", "desc": "定位缺失的情境或结果"},
        {"title": "量化数据扫描", "desc": "寻找可补充的数字与规模"},
        {"title": "JD 关键词匹配", "desc": "对齐目标岗位核心要求"},
        {"title": "生成优化方案", "desc": "输出改写建议与对比"},
    ],
    "project_exp": [
        {"title": "提取经历要素", "desc": "拆解职责、行动与成果"},
        {"title": "STAR 结构诊断", "desc": "定位缺失的情境或结果"},
        {"title": "量化数据扫描", "desc": "寻找可补充的数字与规模"},
        {"title": "JD 关键词匹配", "desc": "对齐目标岗位核心要求"},
        {"title": "生成优化方案", "desc": "输出改写建议与对比"},
    ],
    "self_eval": [
        {"title": "空话套话检测", "desc": "识别缺乏证据的泛泛表述"},
        {"title": "能力证据关联", "desc": "将自我评价与经历挂钩"},
        {"title": "生成优化方案", "desc": "输出更有说服力的版本"},
    ],
    "skills": [
        {"title": "技能分类", "desc": "按工具、语言、领域整理"},
        {"title": "JD 关键词对比", "desc": "找出缺失的关键技能"},
        {"title": "补全建议", "desc": "推荐可补充的技能项"},
        {"title": "生成优化方案", "desc": "输出结构化技能清单"},
    ],
    "default": [
        {"title": "解析板块内容", "desc": "理解当前表述与结构"},
        {"title": "专业度评估", "desc": "检查用词与逻辑规范"},
        {"title": "生成优化方案", "desc": "输出改进后的版本"},
    ],
}

_STATUS_ICON = {
    "done": ("✅", "#5DAE8B"),
    "doing": ("🔄", "#D4956A"),
    "pending": ("⏳", "#C4B5AD"),
}


def _inject_thinking_styles() -> None:
    if st.session_state.get("_thinking_chain_styles"):
        return
    st.session_state["_thinking_chain_styles"] = True
    st.markdown(
        """
<style>
@keyframes tc-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.thinking-chain-shell {
  margin: 16px 0 20px;
  padding: 20px 22px;
  background: linear-gradient(135deg, rgba(255,250,245,0.95), rgba(247,243,239,0.88));
  border: 1px solid rgba(184, 144, 138, 0.16);
  border-radius: 14px;
}
.thinking-chain-head {
  font-size: 14px;
  font-weight: 650;
  color: #2C2420;
  margin-bottom: 14px;
}
.thinking-chain-step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(61, 56, 51, 0.06);
  border-radius: 10px;
  animation: tc-fade-in 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.thinking-chain-step:last-of-type { margin-bottom: 0; }
.thinking-chain-icon {
  flex: 0 0 22px;
  font-size: 15px;
  line-height: 1.4;
}
.thinking-chain-body { flex: 1; min-width: 0; }
.thinking-chain-title {
  font-size: 13px;
  font-weight: 600;
  color: #2C2420;
  line-height: 1.35;
}
.thinking-chain-desc {
  font-size: 12px;
  color: #8C8279;
  margin-top: 2px;
  line-height: 1.5;
}
.thinking-chain-foot {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed rgba(184, 144, 138, 0.22);
  font-size: 11px;
  color: #9E8E83;
  letter-spacing: 0.02em;
}
@media (prefers-reduced-motion: reduce) {
  .thinking-chain-step { animation: none !important; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_thinking_chain(steps: list[dict], model_name: str) -> None:
    """渲染思考链路卡片。steps 每项含 status/title/desc。"""
    _inject_thinking_styles()
    from components.ai_surface import inject_ai_surface_styles
    inject_ai_surface_styles()
    cards: list[str] = []
    for idx, step in enumerate(steps):
        status = str(step.get("status", "pending"))
        icon, _ = _STATUS_ICON.get(status, _STATUS_ICON["pending"])
        title = html.escape(str(step.get("title", "")))
        desc = html.escape(str(step.get("desc", "")))
        delay = idx * 0.3
        cards.append(
            f"""
<div class="thinking-chain-step" style="animation-delay:{delay:.1f}s;">
  <div class="thinking-chain-icon">{icon}</div>
  <div class="thinking-chain-body">
    <div class="thinking-chain-title">{title}</div>
    <div class="thinking-chain-desc">{desc}</div>
  </div>
</div>"""
        )
    model_label = html.escape(model_name)
    routing = model_router.get_last_routing()
    route_html = ""
    if routing:
        selected = html.escape(str(routing.get("selected", "")))
        reason = html.escape(str(routing.get("reason", "")))
        route_html = (
            f'<div class="ai-route-foot">'
            f'成本感知路由 → <span class="ai-surface-badge">{selected}</span>'
            f'{f" · {reason}" if reason else ""}'
            f"</div>"
        )
    st.markdown(
        f"""
<div class="thinking-chain-shell mirror-fade-in">
  <div class="thinking-chain-head">AI 正在分析</div>
  {"".join(cards)}
  <div class="thinking-chain-foot">{model_label}</div>
  {route_html}
</div>
""",
        unsafe_allow_html=True,
    )
    if routing:
        inject_ai_surface_styles()


def _build_steps_with_status(
    templates: list[dict[str, str]],
    active_index: int,
) -> list[dict]:
    steps: list[dict] = []
    for i, tmpl in enumerate(templates):
        if i < active_index:
            status = "done"
        elif i == active_index:
            status = "doing"
        else:
            status = "pending"
        steps.append({**tmpl, "status": status})
    return steps


def run_with_thinking_chain(
    step_templates: list[dict[str, str]],
    work_fn: Callable[[], Any],
    model_name: str = "DeepSeek V3 · 分析推理",
    placeholder: Optional[Any] = None,
) -> Any:
    """
    在后台执行 work_fn，同时动画展示思考步骤。
    完成后清除占位容器；保证最少展示 MIN_DISPLAY_SEC，最多 MAX_DISPLAY_SEC。
    """
    slot = placeholder if placeholder is not None else st.empty()
    start = time.time()
    holder: dict[str, Any] = {"value": None, "error": None, "done": False}

    def _worker() -> None:
        try:
            holder["value"] = work_fn()
        except Exception as exc:
            holder["error"] = exc
        finally:
            holder["done"] = True

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    active = 0
    n = max(len(step_templates), 1)
    while not holder["done"]:
        steps = _build_steps_with_status(step_templates, min(active, n - 1))
        with slot.container():
            render_thinking_chain(steps, model_name)
        time.sleep(0.35)
        if active < n - 1:
            active += 1
        if time.time() - start > MAX_DISPLAY_SEC:
            break

    thread.join(timeout=180)

    if not holder["done"]:
        raise TimeoutError("分析超时，请稍后重试")

    done_steps = [{**t, "status": "done"} for t in step_templates]
    with slot.container():
        render_thinking_chain(done_steps, model_name)

    elapsed = time.time() - start
    if elapsed < MIN_DISPLAY_SEC:
        time.sleep(MIN_DISPLAY_SEC - elapsed)

    slot.empty()

    if holder["error"] is not None:
        raise holder["error"]
    if holder["value"] is None:
        raise RuntimeError("分析未返回结果，请重试")
    return holder["value"]


def get_workshop_steps(section_key: str) -> list[dict[str, str]]:
    if section_key in ("work_exp", "project_exp"):
        return list(WORKSHOP_STEPS["work_exp"])
    if section_key in WORKSHOP_STEPS:
        return list(WORKSHOP_STEPS[section_key])
    return list(WORKSHOP_STEPS["default"])
