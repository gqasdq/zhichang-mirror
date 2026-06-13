"""基本信息格式检查 — 纯本地逻辑，不调 AI。"""

from __future__ import annotations

import re


def check_basic_info_format(content: str) -> tuple[list[dict], list[dict]]:
    """检查基本信息的格式规范性。"""
    text = (content or "").strip()
    issues: list[dict] = []
    passes: list[dict] = []

    if re.search(r"1[3-9]\d{9}", text):
        passes.append({"field": "手机号", "message": "手机号格式正确"})
    else:
        issues.append(
            {
                "type": "format",
                "field": "手机号",
                "status": "warning",
                "message": "手机号格式可能有误，建议检查",
            }
        )

    if re.search(r"[\w.-]+@[\w.-]+\.\w+", text):
        passes.append({"field": "邮箱", "message": "邮箱格式正确"})
    else:
        issues.append(
            {
                "type": "format",
                "field": "邮箱",
                "status": "warning",
                "message": "未检测到邮箱地址，建议补充",
            }
        )

    has_name = (
        "姓名" in text
        or re.search(r"名[：:]\s*\S", text)
        or re.search(r"^[\u4e00-\u9fa5]{2,4}\s", text, re.M)
    )
    if has_name:
        passes.append({"field": "姓名", "message": "姓名已填写"})
    else:
        issues.append(
            {
                "type": "missing",
                "field": "姓名",
                "status": "error",
                "message": "缺少姓名",
            }
        )

    has_edu = any(k in text for k in ("院校", "学校", "大学", "学院", "专业"))
    if has_edu:
        passes.append({"field": "教育信息", "message": "教育信息完整"})
    else:
        issues.append(
            {
                "type": "missing",
                "field": "教育信息",
                "status": "warning",
                "message": "未检测到院校信息，建议补充院校和专业",
            }
        )

    return issues, passes


def format_check_summary(issues: list[dict], passes: list[dict]) -> str:
    """生成底部提示语。"""
    if not issues:
        return "基本信息格式规范，无需 AI 优化。把精力放在经历和技能的打磨上。"
    fields = "、".join(item.get("field", "") for item in issues if item.get("field"))
    return f"基本信息缺少或需完善：{fields}，补充后简历完整度更高。"
