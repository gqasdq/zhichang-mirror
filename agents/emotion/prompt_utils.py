"""情绪 Agent Prompt 工具。"""

from __future__ import annotations


def inject_few_shot_examples(prompt: str, few_shot_text: str) -> str:
    """将 Few-Shot 样例注入 Prompt，替换 {few_shot_examples} 占位符。"""
    replacement = (few_shot_text or "").strip() or "（暂无相似优质回复样例）"
    if "{few_shot_examples}" in prompt:
        return prompt.replace("{few_shot_examples}", replacement)
    if few_shot_text.strip():
        return f"{prompt}\n\n{few_shot_text.strip()}"
    return prompt
