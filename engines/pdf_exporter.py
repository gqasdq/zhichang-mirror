"""绠€鍘?PDF 瀵煎嚭 鈥?缁忓吀 / 鐜颁唬 / ATS 涓夋ā鏉匡紙WeasyPrint + ReportLab 闄嶇骇锛夈€?
璁捐鏄犲皠锛? skill 缁煎悎锛夛細
- classic  鈫?Notion 缂栬緫椋庯細鏆栫伆搴曟爮銆佺帿鐟拌楗版潯銆佸眳涓紶缁熸帓鐗?- modern   鈫?Vercel 绉戞妧椋庯細宸︿晶娓愬彉绔栨潯銆佸乏瀵归綈銆佸ぇ鍐欑珷鑺傛爣绛?- ats      鈫?Ollama 鏂囨。椋庯細绾粦鐧姐€佹柟鎷彿绔犺妭鏍囩銆佹棤瑁呴グ
"""

from __future__ import annotations

import html
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SECTION_TITLES: dict[str, str | None] = {
    "basic_info": None,
    "objective": "姹傝亴鎰忓悜",
    "education": "鏁欒偛鑳屾櫙",
    "work_exp": "宸ヤ綔缁忓巻",
    "project_exp": "椤圭洰缁忓巻",
    "skills": "涓撲笟鎶€鑳?,
    "self_eval": "鑷垜璇勪环",
}

SECTION_ORDER_KEYS = (
    "basic_info",
    "objective",
    "education",
    "work_exp",
    "project_exp",
    "skills",
    "self_eval",
)

_ESTIMATE_PATTERN = re.compile(r"(\d+(?:\.\d+)?%?)鈿狅笍")

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

# --- 妯℃澘璁捐浠ょ墝 -----------------------------------------------------------

CLASSIC_THEME = {
    "name": "#5C3D2E",
    "contact": "#8C8279",
    "body": "#2C2420",
    "header_bg": "#F6F5F4",
    "accent": "#B8908A",
    "accent_soft": "#D4A5A5",
    "divider": "2px solid #B8908A",
    "title_font": '"CareerMirrorCN", "SimSun", "STSong", serif',
    "body_font": '"CareerMirrorCN", "Microsoft YaHei", sans-serif',
}

MODERN_THEME = {
    "name": "#171717",
    "contact": "#888888",
    "body": "#4D4D4D",
    "accent_start": "#007CF0",
    "accent_end": "#00DFD8",
    "hairline": "#EBEBEB",
    "link": "#0070F3",
    "title_font": '"CareerMirrorCN", "Microsoft YaHei", sans-serif',
    "body_font": '"CareerMirrorCN", "Microsoft YaHei", sans-serif',
}

ATS_THEME = {
    "ink": "#000000",
    "body": "#171717",
    "mute": "#525252",
    "hairline": "#E5E5E5",
}


def _find_unconfirmed_estimates(
    sections: dict[str, str],
    estimate_confirmations: dict[str, dict[int, str]] | None = None,
) -> list[str]:
    """缁熻鏈‘璁ょ殑 AI 浼扮畻鏁版嵁銆?""
    confirmations = estimate_confirmations or {}
    unconfirmed: list[str] = []
    for section_key, content in sections.items():
        text = str(content or "")
        matches = _ESTIMATE_PATTERN.findall(text)
        confirmed = confirmations.get(section_key) or {}
        for idx, value in enumerate(matches):
            if idx not in confirmed or not str(confirmed.get(idx, "")).strip():
                unconfirmed.append(value)
    return unconfirmed


def pre_export_check(
    sections: dict[str, str],
    section_status: dict[str, str],
    estimate_confirmations: dict[str, dict[int, str]] | None = None,
) -> list[dict[str, Any]]:
    """瀵煎嚭鍓嶈嚜鍔ㄦ鏌ワ紝杩斿洖妫€鏌ラ」鍒楄〃銆?""
    checks: list[dict[str, Any]] = []
    basic = sections.get("basic_info", "") or ""

    has_phone = bool(re.search(r"1[3-9]\d{9}", basic))
    has_email = bool(re.search(r"@", basic))
    if has_phone and has_email:
        contact_status = "pass"
        contact_detail = ""
    else:
        contact_status = "warn"
        missing: list[str] = []
        if not has_phone:
            missing.append("鎵嬫満鍙?)
        if not has_email:
            missing.append("閭")
        contact_detail = "缂哄皯" + "銆?.join(missing)
    checks.append(
        {
            "item": "鑱旂郴鏂瑰紡瀹屾暣鎬?,
            "status": contact_status,
            "detail": contact_detail,
        }
    )

    unconfirmed = _find_unconfirmed_estimates(sections, estimate_confirmations)
    if unconfirmed:
        preview = ", ".join(unconfirmed[:3])
        suffix = "..." if len(unconfirmed) > 3 else ""
        estimate_detail = f"鏈墈len(unconfirmed)}澶凙I浼扮畻鏁版嵁鏈‘璁わ細{preview}{suffix}"
        estimate_status = "warn"
    else:
        estimate_detail = ""
        estimate_status = "pass"
    checks.append(
        {
            "item": "AI浼扮畻鏁版嵁纭",
            "status": estimate_status,
            "detail": estimate_detail,
        }
    )

    char_count = sum(len(str(v)) for v in sections.values())
    if char_count >= 1500:
        length_status = "warn"
        length_detail = f"绾char_count}瀛楋紝寤鸿鎺у埗鍦?00-1200瀛楋紙1椤礎4锛?
    else:
        length_status = "pass"
        length_detail = f"绾char_count}瀛楋紝闀垮害鍚堥€?
    checks.append(
        {
            "item": "绠€鍘嗛暱搴?,
            "status": length_status,
            "detail": length_detail,
        }
    )

    has_exp = bool(
        str(sections.get("work_exp", "")).strip()
        or str(sections.get("project_exp", "")).strip()
    )
    checks.append(
        {
            "item": "缁忓巻鎻忚堪",
            "status": "pass" if has_exp else "warn",
            "detail": "" if has_exp else "宸ヤ綔缁忓巻鍜岄」鐩粡鍘嗛兘涓虹┖锛屽缓璁ˉ鍏?,
        }
    )

    optimized_count = sum(1 for v in section_status.values() if v == "optimized")
    if optimized_count >= 3:
        opt_status = "pass"
        opt_detail = f"{optimized_count}/7鏉垮潡宸蹭紭鍖?
    else:
        opt_status = "info"
        opt_detail = f"{optimized_count}/7鏉垮潡宸蹭紭鍖栵紝寤鸿鑷冲皯浼樺寲缁忓巻鐩稿叧鏉垮潡"
    checks.append(
        {
            "item": "浼樺寲杩涘害",
            "status": opt_status,
            "detail": opt_detail,
        }
    )

    return checks


def _find_font_path() -> str | None:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _font_face_css() -> str:
    font_path = _find_font_path()
    if not font_path:
        return ""
    uri = Path(font_path).as_uri()
    return f"""
@font-face {{
    font-family: "CareerMirrorCN";
    src: url("{uri}");
}}
"""


def _typography_vars(char_count: int, template: str) -> dict[str, str]:
    if char_count >= 2200:
        base = {
            "body_size": "9.5pt",
            "content_size": "9pt",
            "title_size": "12pt",
            "name_size": "20pt",
            "line_height": "1.45",
            "section_margin": "10pt",
        }
    elif char_count >= 1500:
        base = {
            "body_size": "10pt",
            "content_size": "9.5pt",
            "title_size": "12.5pt",
            "name_size": "21pt",
            "line_height": "1.5",
            "section_margin": "12pt",
        }
    else:
        base = {
            "body_size": "11pt",
            "content_size": "10.5pt",
            "title_size": "13pt",
            "name_size": "22pt",
            "line_height": "1.6",
            "section_margin": "14pt",
        }
    if template == PDFExporter.TEMPLATE_MODERN:
        base["name_size"] = "22pt"
        base["title_size"] = "10pt"
        base["line_height"] = "1.45"
    elif template == PDFExporter.TEMPLATE_CLASSIC:
        base["name_size"] = "24pt"
        base["title_size"] = "13pt"
    return base


def _extract_name(basic: str) -> str:
    text = basic.strip()
    if not text:
        return "涓汉绠€鍘?

    match = re.search(r"濮撳悕[锛?\s]*([^\s\n锛?|锝?]+)", text)
    if match:
        return match.group(1).strip()

    first_line = text.split("\n")[0].strip()
    first_line = re.sub(r"^(涓汉绠€鍘唡绠€鍘唡涓汉淇℃伅|涓汉璧勬枡)\s*", "", first_line)
    if first_line and len(first_line) <= 24:
        inline_name = re.search(r"濮撳悕[锛?\s]*([^\s锛?|锝?]+)", first_line)
        if inline_name:
            return inline_name.group(1).strip()
        if "锛? not in first_line and ":" not in first_line and "鎵嬫満" not in first_line:
            return first_line[:20]

    return "涓汉绠€鍘?


def _extract_contact_line(basic: str, name: str, separator: str = "  |  ") -> str:
    parts: list[str] = []
    patterns = [
        (r"1[3-9]\d{9}", None),
        (r"[\w.\-+]+@[\w.\-]+\.\w+", None),
        (r"闄㈡牎[锛?\s]*([^\n锛?|锝淽+)", 1),
        (r"瀛︽牎[锛?\s]*([^\n锛?|锝淽+)", 1),
        (r"涓撲笟[锛?\s]*([^\n锛?|锝淽+)", 1),
        (r"瀛﹀巻[锛?\s]*([^\n锛?|锝淽+)", 1),
        (r"骞撮緞[锛?\s]*([^\n锛?|锝淽+)", 1),
    ]
    seen: set[str] = set()
    for pattern, group in patterns:
        match = re.search(pattern, basic)
        if not match:
            continue
        value = match.group(group) if group else match.group(0)
        value = value.strip()
        if not value or value == name or value in seen:
            continue
        seen.add(value)
        parts.append(value)

    if parts:
        return separator.join(parts)

    lines = [ln.strip() for ln in basic.split("\n") if ln.strip()]
    fallback = [ln for ln in lines if ln != name and "濮撳悕" not in ln][:3]
    return separator.join(fallback)


def _format_estimate_html(number: str) -> str:
    return (
        f'<span style="border-bottom: 1px dashed #F57F17; padding-bottom: 1px;">'
        f"{html.escape(number)}"
        f'<span style="font-size:7pt; color:#F57F17; vertical-align:super;">浼扮畻</span>'
        f"</span>"
    )


def _format_content(
    text: str,
    *,
    include_star: bool = True,
    include_estimates: bool = True,
) -> str:
    if not text:
        return ""
    escaped = html.escape(text)
    if include_star:
        escaped = escaped.replace("銆怱銆?, '<span class="star-tag star-S">S</span>')
        escaped = escaped.replace("銆怲銆?, '<span class="star-tag star-T">T</span>')
        escaped = escaped.replace("銆怉銆?, '<span class="star-tag star-A">A</span>')
        escaped = escaped.replace("銆怰銆?, '<span class="star-tag star-R">R</span>')
    if include_estimates:
        escaped = _ESTIMATE_PATTERN.sub(
            lambda m: _format_estimate_html(m.group(1)),
            escaped,
        )
    return escaped


def _format_content_reportlab(
    text: str,
    *,
    include_star: bool = True,
    include_estimates: bool = True,
    star_palette: dict[str, str] | None = None,
) -> str:
    """ReportLab Paragraph 鍏煎 markup銆?""
    if not text:
        return ""
    palette = star_palette or {
        "S": "#1a73e8",
        "T": "#1e8e3e",
        "A": "#e37400",
        "R": "#9c27b0",
    }
    escaped = html.escape(text)
    if include_star:
        for tag, color in palette.items():
            escaped = escaped.replace(
                f"銆恵tag}銆?,
                f'<font color="{color}"><b>{tag}</b></font>',
            )
    if include_estimates:
        escaped = _ESTIMATE_PATTERN.sub(
            lambda m: (
                f'<u><font color="#F57F17"><b>{html.escape(m.group(1))}</b></font></u>'
                f'<font color="#F57F17" size="7">浼扮畻</font>'
            ),
            escaped,
        )
    return escaped.replace("\n", "<br/>")


def _strip_for_ats(text: str) -> str:
    """ATS 妯℃澘锛氬幓闄?STAR 鏍囩涓?鈿狅笍 鏍囪銆?""
    cleaned = re.sub(r"銆怺STAR]銆?, "", text)
    cleaned = _ESTIMATE_PATTERN.sub(r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _register_pdf_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_name = "CareerMirrorCN"
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, path))
                return font_name
            except Exception:
                continue
    for fallback in (
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ):
        if Path(fallback).exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, fallback))
                return font_name
            except Exception:
                continue
    return "Helvetica"


def _iter_content_sections(sections: dict[str, str]) -> list[tuple[str, str, str]]:
    """杩斿洖 (key, title, content) 鍒楄〃锛岃烦杩?basic_info 涓庣┖鍐呭銆?""
    items: list[tuple[str, str, str]] = []
    for key in SECTION_ORDER_KEYS:
        if key == "basic_info":
            continue
        content = str(sections.get(key, "") or "").strip()
        if not content:
            continue
        title = SECTION_TITLES.get(key) or ""
        items.append((key, title, content))
    return items


def _header_context(sections: dict[str, str], filename: str, template: str) -> dict[str, str]:
    basic = str(sections.get("basic_info", "") or "").strip()
    name = _extract_name(basic) if basic else filename
    if template == PDFExporter.TEMPLATE_MODERN:
        contact_sep = " 路 "
    elif template == PDFExporter.TEMPLATE_ATS:
        contact_sep = " | "
    else:
        contact_sep = "  |  "
    contact = _extract_contact_line(basic, name, separator=contact_sep) if basic else ""
    return {"name": name, "contact": contact, "basic": basic}


class PDFExporter:
    """灏嗗悇鏉垮潡鍐呭娓叉煋涓?A4 PDF銆?""

    TEMPLATE_CLASSIC = "classic"
    TEMPLATE_MODERN = "modern"
    TEMPLATE_ATS = "ats"

    VALID_TEMPLATES = frozenset({TEMPLATE_CLASSIC, TEMPLATE_MODERN, TEMPLATE_ATS})

    def export(
        self,
        sections: dict[str, str],
        template: str = "classic",
        filename: str = "绠€鍘?,
    ) -> bytes:
        template = template if template in self.VALID_TEMPLATES else self.TEMPLATE_CLASSIC

        if template == self.TEMPLATE_ATS:
            return self._export_ats(sections, filename)

        html_doc = self._render_html_template(sections, template=template, filename=filename)
        try:
            from weasyprint import HTML  # type: ignore[import-untyped]

            return HTML(string=html_doc).write_pdf()
        except (ImportError, OSError) as exc:
            logger.warning("[pdf_exporter] weasyprint unavailable, fallback to reportlab: %s", exc)
            return self._export_reportlab_fallback(sections, filename, template=template)
        except Exception as exc:
            logger.warning("[pdf_exporter] weasyprint failed, fallback to reportlab: %s", exc)
            return self._export_reportlab_fallback(sections, filename, template=template)

    def _render_html_template(
        self,
        sections: dict[str, str],
        *,
        template: str,
        filename: str,
    ) -> str:
        if template == self.TEMPLATE_MODERN:
            return self._render_html_modern(sections, filename=filename)
        return self._render_html_classic(sections, filename=filename)

    def _render_html_classic(self, sections: dict[str, str], *, filename: str) -> str:
        """Notion 缂栬緫椋庯細鏆栬壊椤舵爮銆佸眳涓帓鐗堛€佺帿鐟拌楗版潯銆佺矖鍒嗛殧绾裤€?""
        char_count = sum(len(str(v)) for v in sections.values())
        typo = _typography_vars(char_count, self.TEMPLATE_CLASSIC)
        ctx = _header_context(sections, filename, self.TEMPLATE_CLASSIC)
        theme = CLASSIC_THEME
        font_face = _font_face_css()

        body_parts: list[str] = [
            '<div class="header-band">',
            f'  <div class="resume-name">{html.escape(ctx["name"])}</div>',
        ]
        if ctx["contact"]:
            body_parts.append(
                f'  <div class="resume-contact">{_format_content(ctx["contact"])}</div>'
            )
        body_parts.append("</div>")

        for _key, title, content in _iter_content_sections(sections):
            body_parts.append('<hr class="section-divider" />')
            body_parts.append(
                f'<div class="section-title">'
                f'<span class="section-bar"></span>{html.escape(title)}'
                f"</div>"
            )
            body_parts.append(f'<div class="section-content">{_format_content(content)}</div>')

        body_html = "\n".join(body_parts)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<style>
{font_face}
@page {{ size: A4; margin: 16mm; }}
body {{
    font-family: {theme["body_font"]};
    font-size: {typo["body_size"]};
    color: {theme["body"]};
    line-height: {typo["line_height"]};
}}
.header-band {{
    background: {theme["header_bg"]};
    border: 1px solid #E5E3DF;
    border-bottom: 3px double {theme["accent"]};
    border-radius: 4pt;
    padding: 18pt 14pt 14pt;
    margin-bottom: {typo["section_margin"]};
    text-align: center;
}}
.resume-name {{
    font-family: {theme["title_font"]};
    font-size: {typo["name_size"]};
    font-weight: 700;
    color: {theme["name"]};
    letter-spacing: 0.06em;
    margin-bottom: 6pt;
}}
.resume-contact {{
    font-size: 9.5pt;
    color: {theme["contact"]};
}}
.section-divider {{
    border: none;
    border-top: {theme["divider"]};
    margin: {typo["section_margin"]} 0 8pt;
}}
.section-title {{
    display: flex;
    align-items: center;
    font-family: {theme["title_font"]};
    font-size: {typo["title_size"]};
    font-weight: 700;
    color: {theme["name"]};
    margin-bottom: 6pt;
}}
.section-bar {{
    display: inline-block;
    width: 4pt;
    height: 13pt;
    background: {theme["accent_soft"]};
    margin-right: 8pt;
    border-radius: 1pt;
}}
.section-content {{
    font-size: {typo["content_size"]};
    white-space: pre-line;
    word-break: break-word;
    padding-left: 12pt;
}}
.star-tag {{
    display: inline-block;
    font-size: 8pt;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 2px;
    margin-right: 2px;
}}
.star-S {{ background: #E8F0FE; color: #1a73e8; }}
.star-T {{ background: #E6F4EA; color: #1e8e3e; }}
.star-A {{ background: #FEF7E0; color: #e37400; }}
.star-R {{ background: #F3E8FD; color: #9c27b0; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

    def _render_html_modern(self, sections: dict[str, str], *, filename: str) -> str:
        """Vercel 绉戞妧椋庯細宸︿晶娓愬彉绔栨潯銆佸乏瀵归綈銆佸ぇ鍐欑珷鑺傛爣绛俱€佺粏绾垮垎闅斻€?""
        char_count = sum(len(str(v)) for v in sections.values())
        typo = _typography_vars(char_count, self.TEMPLATE_MODERN)
        ctx = _header_context(sections, filename, self.TEMPLATE_MODERN)
        theme = MODERN_THEME
        font_face = _font_face_css()

        body_parts: list[str] = [
            '<div class="modern-shell">',
            '<div class="accent-rail"></div>',
            '<div class="modern-main">',
            f'  <div class="resume-name">{html.escape(ctx["name"])}</div>',
        ]
        if ctx["contact"]:
            body_parts.append(
                f'  <div class="resume-contact">{_format_content(ctx["contact"])}</div>'
            )
        body_parts.append('  <div class="header-rule"></div>')

        for _key, title, content in _iter_content_sections(sections):
            upper_title = html.escape(title.upper())
            body_parts.append(f'  <div class="section-title">{upper_title}</div>')
            body_parts.append(f'  <div class="section-content">{_format_content(content)}</div>')

        body_parts.extend(["</div>", "</div>"])
        body_html = "\n".join(body_parts)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<style>
{font_face}
@page {{ size: A4; margin: 14mm 14mm 14mm 18mm; }}
body {{
    font-family: {theme["body_font"]};
    font-size: {typo["body_size"]};
    color: {theme["body"]};
    line-height: {typo["line_height"]};
    margin: 0;
}}
.modern-shell {{
    display: flex;
    min-height: 100%;
}}
.accent-rail {{
    width: 5pt;
    min-height: 240mm;
    background: linear-gradient(180deg, {theme["accent_start"]} 0%, {theme["accent_end"]} 100%);
    border-radius: 3pt;
    margin-right: 14pt;
    flex-shrink: 0;
}}
.modern-main {{ flex: 1; }}
.resume-name {{
    font-family: {theme["title_font"]};
    font-size: {typo["name_size"]};
    font-weight: 600;
    color: {theme["name"]};
    letter-spacing: -0.03em;
    margin-bottom: 4pt;
}}
.resume-contact {{
    font-size: 9pt;
    color: {theme["contact"]};
    letter-spacing: 0.04em;
    margin-bottom: 10pt;
}}
.header-rule {{
    height: 1px;
    background: linear-gradient(90deg, {theme["accent_start"]}, {theme["accent_end"]}, transparent);
    margin-bottom: 12pt;
}}
.section-title {{
    font-family: {theme["title_font"]};
    font-size: {typo["title_size"]};
    font-weight: 600;
    color: {theme["name"]};
    letter-spacing: 0.18em;
    text-transform: uppercase;
    border-bottom: 1px solid {theme["hairline"]};
    padding-bottom: 4pt;
    margin-top: {typo["section_margin"]};
    margin-bottom: 6pt;
}}
.section-content {{
    font-size: {typo["content_size"]};
    white-space: pre-line;
    word-break: break-word;
    color: {theme["body"]};
}}
.star-tag {{
    display: inline-block;
    font-size: 7.5pt;
    font-weight: 700;
    padding: 1px 3px;
    border-radius: 2px;
    margin-right: 2px;
    border: 1px solid {theme["hairline"]};
}}
.star-S {{ color: {theme["link"]}; background: #EEF6FF; }}
.star-T {{ color: #0E7A43; background: #EAF7EF; }}
.star-A {{ color: #AB570A; background: #FFF6E8; }}
.star-R {{ color: #7928CA; background: #F3EBFF; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

    def _export_ats(self, sections: dict[str, str], filename: str) -> bytes:
        """Ollama 鏂囨。椋庯細绾粦鐧姐€佹柟鎷彿绔犺妭鏍囩銆佺粨鏋勫寲绾枃鏈€?""
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

        font_name = _register_pdf_font()
        theme = ATS_THEME

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
        )
        styles = getSampleStyleSheet()

        name_style = ParagraphStyle(
            "ATSName",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=14,
            leading=18,
            textColor=HexColor(theme["ink"]),
            spaceAfter=2,
        )
        contact_style = ParagraphStyle(
            "ATSContact",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=9,
            leading=12,
            textColor=HexColor(theme["mute"]),
            spaceAfter=10,
        )
        label_style = ParagraphStyle(
            "ATSLabel",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=10,
            leading=14,
            textColor=HexColor(theme["ink"]),
            spaceBefore=14,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "ATSBody",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=10,
            leading=14,
            textColor=HexColor(theme["body"]),
            spaceAfter=2,
        )

        ctx = _header_context(sections, filename, self.TEMPLATE_ATS)
        elements: list[Any] = []

        elements.append(Paragraph(f"<b>{html.escape(ctx['name'])}</b>", name_style))
        if ctx["contact"]:
            elements.append(Paragraph(html.escape(ctx["contact"]), contact_style))
        elements.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=HexColor(theme["hairline"]),
                spaceAfter=8,
            )
        )

        for _key, title, content in _iter_content_sections(sections):
            stripped = _strip_for_ats(content)
            if not stripped:
                continue
            label = f"[ {title} ]"
            elements.append(Paragraph(f"<b>{html.escape(label)}</b>", label_style))
            elements.append(
                Paragraph(html.escape(stripped).replace("\n", "<br/>"), body_style)
            )

        if len(elements) <= 3:
            fallback = _strip_for_ats(str(sections.get("basic_info", "") or filename))
            elements.append(Paragraph(html.escape(fallback).replace("\n", "<br/>"), body_style))

        doc.build(elements)
        return buf.getvalue()

    def _export_reportlab_fallback(
        self,
        sections: dict[str, str],
        filename: str,
        *,
        template: str,
    ) -> bytes:
        """WeasyPrint 涓嶅彲鐢ㄦ椂鐨勪笁妯℃澘闄嶇骇锛坈lassic / modern / ats 鍚勮嚜鐙珛甯冨眬锛夈€?""
        if template == self.TEMPLATE_ATS:
            return self._export_ats(sections, filename)
        if template == self.TEMPLATE_MODERN:
            return self._reportlab_modern(sections, filename)
        return self._reportlab_classic(sections, filename)

    def _reportlab_classic(self, sections: dict[str, str], filename: str) -> bytes:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        font_name = _register_pdf_font()
        theme = CLASSIC_THEME
        ctx = _header_context(sections, filename, self.TEMPLATE_CLASSIC)

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
        )
        styles = getSampleStyleSheet()

        name_style = ParagraphStyle(
            "ClassicName",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=26,
            textColor=HexColor(theme["name"]),
            alignment=1,
            spaceAfter=6,
            leading=32,
        )
        contact_style = ParagraphStyle(
            "ClassicContact",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=9,
            textColor=HexColor(theme["contact"]),
            alignment=1,
            spaceAfter=0,
        )
        section_style = ParagraphStyle(
            "ClassicSection",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=14,
            textColor=HexColor(theme["name"]),
            spaceBefore=6,
            spaceAfter=6,
            leading=20,
            alignment=1,
        )
        body_style = ParagraphStyle(
            "ClassicBody",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=11,
            textColor=HexColor(theme["body"]),
            leading=17,
            spaceAfter=6,
            leftIndent=14,
            rightIndent=14,
        )

        header_rows = [[Paragraph(html.escape(ctx["name"]), name_style)]]
        if ctx["contact"]:
            header_rows.append([Paragraph(_format_content_reportlab(ctx["contact"]), contact_style)])

        header_table = Table(header_rows, colWidths=[doc.width])
        header_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor(theme["header_bg"])),
                    ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E5E3DF")),
                    ("LINEBELOW", (0, -1), (-1, -1), 3, HexColor(theme["accent"])),
                    ("ROUNDRECT", (0, 0), (-1, -1), 6, 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 14),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
                ]
            )
        )

        elements: list[Any] = [header_table, Spacer(1, 8)]

        for _key, title, content in _iter_content_sections(sections):
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=HexColor(theme["accent"]),
                    spaceBefore=10,
                    spaceAfter=5,
                )
            )
            bar_title = (
                f'<font color="{theme["accent_soft"]}">鈻?/font> '
                f"{html.escape(title)}"
            )
            elements.append(Paragraph(bar_title, section_style))
            elements.append(Paragraph(_format_content_reportlab(content), body_style))

        doc.build(elements)
        return buf.getvalue()

    def _reportlab_modern(self, sections: dict[str, str], filename: str) -> bytes:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        font_name = _register_pdf_font()
        theme = MODERN_THEME
        ctx = _header_context(sections, filename, self.TEMPLATE_MODERN)

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
        )
        styles = getSampleStyleSheet()
        rail_width = 8 * mm
        content_width = doc.width - rail_width - 6 * mm

        name_style = ParagraphStyle(
            "ModernName",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=24,
            textColor=HexColor(theme["name"]),
            alignment=0,
            spaceAfter=3,
            leading=28,
        )
        contact_style = ParagraphStyle(
            "ModernContact",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=9,
            textColor=HexColor(theme["contact"]),
            alignment=0,
            spaceAfter=8,
        )
        section_style = ParagraphStyle(
            "ModernSection",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=9,
            textColor=HexColor(theme["accent_start"]),
            spaceBefore=14,
            spaceAfter=3,
            leading=12,
            letterSpacing=2.2,
        )
        body_style = ParagraphStyle(
            "ModernBody",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=10,
            textColor=HexColor(theme["body"]),
            leading=14,
            spaceAfter=3,
        )

        content_parts: list[Any] = [
            Paragraph(html.escape(ctx["name"]), name_style),
        ]
        if ctx["contact"]:
            content_parts.append(Paragraph(_format_content_reportlab(ctx["contact"]), contact_style))
        content_parts.append(
            HRFlowable(
                width=content_width,
                thickness=1,
                color=HexColor(theme["accent_start"]),
                spaceAfter=10,
            )
        )

        for _key, title, content in _iter_content_sections(sections):
            content_parts.append(Spacer(1, 2))
            content_parts.append(Paragraph(html.escape(title.upper()), section_style))
            content_parts.append(
                HRFlowable(
                    width=content_width,
                    thickness=0.5,
                    color=HexColor(theme["hairline"]),
                    spaceAfter=4,
                )
            )
            content_parts.append(
                Paragraph(
                    _format_content_reportlab(
                        content,
                        star_palette={
                            "S": theme["link"],
                            "T": "#0E7A43",
                            "A": "#AB570A",
                            "R": "#7928CA",
                        },
                    ),
                    body_style,
                )
            )

        content_table = Table([[content_parts]], colWidths=[content_width])
        content_table.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]))

        rail_table = Table([[""]], colWidths=[rail_width], rowHeights=[230 * mm])
        rail_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor(theme["accent_start"])),
                    ("LINERIGHT", (0, 0), (-1, -1), 1.5, HexColor(theme["accent_end"])),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )

        shell = Table([[rail_table, content_table]], colWidths=[rail_width, content_width + 4 * mm])
        shell.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

        doc.build([shell])
        return buf.getvalue()

