"""从 PDF 字节流提取纯文本（优先 pypdf，回退 pdfplumber）。"""

from __future__ import annotations

import io
import logging
import re
from typing import Callable

logger = logging.getLogger(__name__)

_PDFMINER_LOGGERS = ("pdfminer", "pdfminer.pdffont", "pdfminer.pdfinterp")
_pdfminer_noise_suppressed = False


def _suppress_pdfminer_noise() -> None:
    global _pdfminer_noise_suppressed
    if _pdfminer_noise_suppressed:
        return
    for name in _PDFMINER_LOGGERS:
        logging.getLogger(name).setLevel(logging.ERROR)
    _pdfminer_noise_suppressed = True


def _clean_pdf_text(text: str) -> str:
    cleaned = re.sub(r"(.)\1+", r"\1", text or "")
    return cleaned.strip()


def _extract_with_pypdf(raw_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw_bytes))
    parts = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n".join(part for part in parts if part).strip()


def _extract_with_pdfplumber(raw_bytes: bytes) -> str:
    _suppress_pdfminer_noise()
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page in pdf.pages:
            text = (page.extract_text(layout=False) or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def extract_text_from_pdf_bytes(raw_bytes: bytes) -> str:
    """提取 PDF 文本；pypdf 通常更快，失败或为空时回退 pdfplumber。"""
    if not raw_bytes:
        return ""

    extractors: list[tuple[str, Callable[[bytes], str]]] = [
        ("pypdf", _extract_with_pypdf),
        ("pdfplumber", _extract_with_pdfplumber),
    ]
    for name, extractor in extractors:
        try:
            text = _clean_pdf_text(extractor(raw_bytes))
            if text:
                return text
        except Exception as exc:
            logger.debug("PDF extract via %s failed: %s", name, exc)
    return ""
