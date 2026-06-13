"""职业基因进化 — 潜力培养路径。"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

# 基因编码 → 培养建议
EVOLUTION_HINTS: dict[str, str] = {
    "SPATIAL": "多参与空间分析项目，积累可视化作品集",
    "DATA": "用真实数据集做分析案例，输出可量化结论",
    "VERBAL": "练习结构化表达，把经历讲成 30 秒电梯演讲",
    "LOGIC": "拆解复杂问题为步骤，在项目中写清决策链",
    "CREATIVE": "保留 1–2 个差异化作品，展示独特视角",
    "EXEC": "主动承担小组协调，记录可量化的推进成果",
    "EMPATHY": "在协作中收集他人反馈，证明共情带来结果",
    "RESIL": "记录克服困难的具体事件，STAR 化表述",
}


def _potential_level(current: int) -> int:
    """当前等级 → 6 个月内可达潜力等级（+0~2，上限 5）。"""
    return min(5, max(current, current + (1 if current < 4 else 0)))


def build_evolution_plans(gene_result: dict[str, Any]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    genes = gene_result.get("显性基因") or []
    if not isinstance(genes, list):
        return plans
    for gene in genes:
        if not isinstance(gene, dict):
            continue
        name = str(gene.get("基因名称", ""))
        code = str(gene.get("基因编码", "GENE")).upper()
        current = int(gene.get("等级", 3) or 3)
        current = max(1, min(5, current))
        target = _potential_level(current)
        if target <= current:
            target = min(5, current + 1)
        hint = EVOLUTION_HINTS.get(code, "通过项目实践 + 反馈迭代，逐步强化该基因表达")
        plans.append({
            "name": name,
            "code": code,
            "current": current,
            "target": target,
            "hint": hint,
        })
    return plans[:5]


def render_gene_evolution(gene_result: dict[str, Any]) -> None:
    """渲染基因进化卡片。"""
    plans = build_evolution_plans(gene_result)
    if not plans:
        return

    if st.session_state.get("_gene_evo_styles"):
        pass
    else:
        st.session_state["_gene_evo_styles"] = True
        st.markdown(
            """
<style>
.gene-evo-shell {
  margin: 20px 0; padding: 20px 22px;
  background: linear-gradient(145deg, rgba(255,252,249,0.96), rgba(234,243,236,0.5));
  border: 1px solid rgba(126, 168, 142, 0.2); border-radius: 14px;
}
.gene-evo-title { font-size: 15px; font-weight: 650; color: #2C2420; margin-bottom: 14px; }
.gene-evo-item {
  padding: 12px 14px; margin-bottom: 10px;
  background: rgba(255,255,255,0.7); border-radius: 10px;
  border: 1px solid rgba(61,56,51,0.06);
  animation: mirror-rise 0.45s cubic-bezier(0.22,1,0.36,1) both;
}
.gene-evo-name { font-size: 14px; font-weight: 600; color: #2C2420; }
.gene-evo-levels { font-size: 13px; color: #5DAE8B; margin: 4px 0; font-weight: 600; }
.gene-evo-hint { font-size: 12px; color: #8C8279; line-height: 1.5; }
</style>
""",
            unsafe_allow_html=True,
        )

    items = []
    for i, p in enumerate(plans):
        items.append(
            f"""
<div class="gene-evo-item mirror-stagger-{min(i+1,4)}" style="animation-delay:{i*0.08}s;">
  <div class="gene-evo-name">{html.escape(p['name'])}</div>
  <div class="gene-evo-levels">Lv.{p['current']} → 潜力 Lv.{p['target']}（6 个月）</div>
  <div class="gene-evo-hint">{html.escape(p['hint'])}</div>
</div>"""
        )

    st.markdown(
        f"""
<div class="gene-evo-shell mirror-reveal">
  <div class="gene-evo-title">🌱 基因进化 · 优势是可以培养的</div>
  {"".join(items)}
</div>
""",
        unsafe_allow_html=True,
    )
