"""API 出站前的隐私脱敏（手机号/邮箱/身份证/银行卡等）。"""

from __future__ import annotations

import re
from typing import Callable

# 身份证校验位权重（GB 11643-1999）
_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CHARS = "10X98765432"

_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_ID_CANDIDATE_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
# 银行卡候选：16-19 位数字，前后不能紧邻更多数字
_BANK_CANDIDATE_RE = re.compile(r"(?<!\d)(\d{16,19})(?!\d)")
_NAME_LABEL_RE = re.compile(r"姓\s*名[：:]\s*\S+")
_ADDRESS_LABEL_RE = re.compile(r"(?:住|地)址[：:]\s*\S+")
_COMPANY_LABEL_RE = re.compile(r"(?:公司|单位|企业)[：:]\s*\S+")


def _id_card_valid(number: str) -> bool:
    """18 位居民身份证校验（含校验位）。"""
    raw = number.upper()
    if len(raw) != 18 or not raw[:17].isdigit():
        return False
    if raw[-1] not in _ID_CHECK_CHARS:
        return False
    try:
        total = sum(int(raw[i]) * _ID_WEIGHTS[i] for i in range(17))
    except ValueError:
        return False
    return _ID_CHECK_CHARS[total % 11] == raw[-1]


def _luhn_valid(number: str) -> bool:
    """Luhn 校验（银行卡号）。"""
    if not number.isdigit() or len(number) < 16 or len(number) > 19:
        return False
    digits = [int(ch) for ch in number]
    checksum = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _replace_id_cards(text: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        candidate = match.group(1)
        return "[身份证号]" if _id_card_valid(candidate) else match.group(0)

    return _ID_CANDIDATE_RE.sub(_sub, text)


def _replace_bank_cards(text: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        candidate = match.group(1)
        return "[银行卡号]" if _luhn_valid(candidate) else match.group(0)

    return _BANK_CANDIDATE_RE.sub(_sub, text)


def sanitize_for_api(text: str, remove_company: bool = False) -> str:
    if not text:
        return text
    sanitized = text
    sanitized = _PHONE_RE.sub("[手机号]", sanitized)
    sanitized = _EMAIL_RE.sub("[邮箱]", sanitized)
    sanitized = _replace_id_cards(sanitized)
    sanitized = _replace_bank_cards(sanitized)
    sanitized = _NAME_LABEL_RE.sub("姓名：[已隐藏]", sanitized)
    sanitized = _ADDRESS_LABEL_RE.sub("地址：[已隐藏]", sanitized)
    if remove_company:
        sanitized = _COMPANY_LABEL_RE.sub("公司：[已隐藏]", sanitized)
    return sanitized


def sanitize_resume_for_api(resume_text: str) -> str:
    return sanitize_for_api(resume_text, remove_company=False)


def sanitize_chat_for_api(chat_text: str) -> str:
    return sanitize_for_api(chat_text, remove_company=False)
