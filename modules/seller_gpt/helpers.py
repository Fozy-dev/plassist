from __future__ import annotations

import re


def format_message(template: str, **kwargs) -> str:
    try:
        return str(template or "").format(**kwargs)
    except Exception:
        return str(template or "")


def mask_secret(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "не задан"
    if len(value) <= 8:
        return "задан"
    return f"{value[:4]}...{value[-4:]}"


def bool_text(value: bool) -> str:
    return "включено" if value else "выключено"


def prompt_text(text: str) -> str:
    return f"<b>Seller GPT</b>\n\n{text}"


def contains_url(text: str | None) -> bool:
    if not text:
        return False
    return bool(re.search(r"https?://|www\.", str(text), flags=re.IGNORECASE))


def parse_lot_id(url: str | None) -> int | None:
    if not url:
        return None
    match = re.search(r"[?&]id=(\d+)", str(url))
    return int(match.group(1)) if match else None
