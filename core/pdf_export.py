"""PDF 报告导出（reportlab + 系统中文字体，避免 fpdf 中文乱码）。"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROSE_GOLD = HexColor("#B4908A")
TEXT_DARK = HexColor("#2C2420")
TEXT_BODY = HexColor("#3C3428")
TEXT_MUTED = HexColor("#A09A94")

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]

_REGISTERED_FONT: Optional[str] = None


def _register_chinese_font() -> str:
    global _REGISTERED_FONT
    if _REGISTERED_FONT:
        return _REGISTERED_FONT

    font_name = "CareerMirrorCN"
    for font_path in _FONT_CANDIDATES:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                _REGISTERED_FONT = font_name
                return font_name
            except Exception:
                continue

    _REGISTERED_FONT = "Helvetica"
    return _REGISTERED_FONT


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("#"):
        return True
    return bool(re.match(r"^\d+\.\s", stripped))


def _draw_page_frame(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(ROSE_GOLD)
    canvas.setFillColor(ROSE_GOLD)
    canvas.line(40, A4[1] - 28 * mm, A4[0] - 40, A4[1] - 28 * mm)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawRightString(A4[0] - 40, A4[1] - 22 * mm, "Career Mirror")
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica-Oblique", 8)
    canvas.drawCentredString(A4[0] / 2, 18 * mm, "职场镜子 - 陪你走过最难熬的求职路")
    canvas.restoreState()


def export_report_pdf(title: str, report_text: str) -> bytes:
    """将报告导出为 PDF 字节数据。"""
    font = _register_chinese_font()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=36 * mm,
        bottomMargin=28 * mm,
        leftMargin=40,
        rightMargin=40,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font,
        fontSize=18,
        textColor=TEXT_DARK,
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName=font,
        fontSize=12,
        textColor=TEXT_DARK,
        spaceAfter=6,
        spaceBefore=4,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName=font,
        fontSize=11,
        textColor=TEXT_BODY,
        leading=16,
        spaceAfter=4,
    )
    privacy_style = ParagraphStyle(
        "ReportPrivacy",
        parent=styles["Normal"],
        fontName=font,
        fontSize=9,
        textColor=TEXT_MUTED,
        leading=12,
        spaceBefore=12,
    )

    elements: List[Any] = []
    elements.append(Paragraph(_escape_xml(title), title_style))
    elements.append(Spacer(1, 8))

    for line in (report_text or "").split("\n"):
        stripped = line.strip()
        if _is_heading_line(line):
            heading_text = stripped.lstrip("#").strip()
            if heading_text:
                elements.append(Paragraph(_escape_xml(heading_text), heading_style))
        elif stripped:
            elements.append(Paragraph(_escape_xml(stripped), body_style))
        else:
            elements.append(Spacer(1, 6))

    elements.append(
        Paragraph(
            _escape_xml(
                "Privacy: This report was generated locally. "
                "No personal data is stored on our servers."
            ),
            privacy_style,
        )
    )

    doc.build(elements, onFirstPage=_draw_page_frame, onLaterPages=_draw_page_frame)
    return buf.getvalue()


def format_gene_report_text(result: Dict[str, Any]) -> str:
    """将职业基因结果格式化为可导出文本。"""
    if not isinstance(result, dict):
        return ""

    lines: List[str] = ["# 职业基因测序报告", ""]

    combo = result.get("基因组合分析", {})
    if isinstance(combo, dict) and any(combo.values()):
        lines.extend(
            [
                "## 基因组合分析",
                f"组合名称：{combo.get('组合名称', '')}",
                f"核心基因型：{combo.get('核心基因型', '')}",
                f"组合优势：{combo.get('组合优势', '')}",
                f"组合短板：{combo.get('组合短板', '')}",
                "",
            ]
        )

    genes = result.get("显性基因", [])
    if isinstance(genes, list) and genes:
        lines.append("## 显性基因")
        for gene in genes:
            if not isinstance(gene, dict):
                continue
            lines.append(
                f"- {gene.get('基因名称', '')} (Lv.{gene.get('等级', '')}) "
                f"{gene.get('等级判定理由', '')}"
            )
        lines.append("")

    jobs = result.get("推荐岗位方向", [])
    if isinstance(jobs, list) and jobs:
        lines.append("## 推荐岗位方向")
        for job in jobs:
            if not isinstance(job, dict):
                continue
            lines.extend(
                [
                    f"### {job.get('岗位名称', '')}",
                    f"方向类型：{job.get('方向类型', '')}",
                    f"为什么适合你：{job.get('为什么适合你', '')}",
                    f"入门第一步：{job.get('入门第一步', '')}",
                    f"三年后画面：{job.get('三年后画面', '')}",
                    f"风险提示：{job.get('风险提示', '')}",
                    "",
                ]
            )

    hidden = result.get("隐藏基因", [])
    if isinstance(hidden, list) and hidden:
        lines.append("## 隐藏基因")
        for item in hidden:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('基因名称', '')}：{item.get('推断逻辑', '')}"
            )
        lines.append("")

    traps = result.get("基因陷阱预警", [])
    if isinstance(traps, list) and traps:
        lines.append("## 基因陷阱预警")
        for trap in traps:
            if not isinstance(trap, dict):
                continue
            lines.append(f"- {trap.get('陷阱名称', '')}：{trap.get('触发场景', '')}")
        lines.append("")

    return "\n".join(lines).strip()


def format_parallel_report_text(result: Dict[str, Any]) -> str:
    """将平行宇宙推演结果格式化为可导出文本。"""
    if not isinstance(result, dict):
        return ""

    lines: List[str] = ["# 平行宇宙推演报告", ""]

    insight = str(result.get("insight", "")).strip()
    if insight:
        lines.extend(["## 镜语者说", insight, ""])

    labels = {
        "mirror_a": "镜面A：深耕当下",
        "mirror_b": "镜面B：拐弯之路",
        "mirror_c": "镜面C：意外可能",
    }
    for key, label in labels.items():
        mirror = result.get(key, {})
        if not isinstance(mirror, dict) or not mirror:
            continue
        lines.append(f"## {label} · {mirror.get('title', '')}")
        lines.append(str(mirror.get("summary", "")))
        year5 = mirror.get("year5", {}) if isinstance(mirror.get("year5"), dict) else {}
        year10 = mirror.get("year10", {}) if isinstance(mirror.get("year10"), dict) else {}
        lines.append(
            f"5年后：{year5.get('position', '')} · {year5.get('salary', '')} — "
            f"{year5.get('description', '')}"
        )
        lines.append(
            f"10年后：{year10.get('position', '')} · {year10.get('salary', '')} — "
            f"{year10.get('description', '')}"
        )
        for tp in mirror.get("turning_points", [])[:6]:
            if isinstance(tp, dict):
                lines.append(f"- {tp.get('year', '')}：{tp.get('event', '')}")
        for risk in mirror.get("risks", [])[:6]:
            lines.append(f"- 风险：{risk}")
        lines.append("")

    return "\n".join(lines).strip()


def export_gold_report_pdf(report_text: str) -> bytes:
    return export_report_pdf("金子探测器分析报告", report_text)


def export_gene_report_pdf(report_text: str) -> bytes:
    return export_report_pdf("职业基因测序报告", report_text)


def export_parallel_report_pdf(report_text: str) -> bytes:
    return export_report_pdf("平行宇宙推演报告", report_text)
