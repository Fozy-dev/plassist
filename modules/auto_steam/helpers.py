from __future__ import annotations

import re


ORDER_ID_RE = re.compile(r"#([A-Z0-9]+)", flags=re.IGNORECASE)
STEAM_LOGIN_RE = re.compile(r"^[a-zA-Z0-9_\-]{2,64}$")


def format_message(template: str, **kwargs) -> str:
    try:
        return str(template or "").format(**kwargs)
    except Exception:
        return str(template or "")


def bool_text(value: bool) -> str:
    return "включено" if value else "выключено"


def mask_secret(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "не задан"
    if len(value) <= 8:
        return "задан"
    return f"{value[:3]}...{value[-3:]}"


def prompt_text(text: str) -> str:
    return f"<b>AutoSteam</b>\n\n{text}"


def extract_order_id_from_message(message_text: str | None) -> str | None:
    if not message_text:
        return None
    match = ORDER_ID_RE.search(str(message_text))
    return match.group(1) if match else None


def is_valid_steam_login(text: str | None) -> bool:
    if not text:
        return False
    return bool(STEAM_LOGIN_RE.fullmatch(str(text).strip()))


def extract_currency(order_html: str | None) -> str | None:
    if not order_html:
        return None
    text = str(order_html).upper()
    for currency in ("RUB", "UAH", "KZT"):
        if currency in text:
            return currency
    return None


def extract_quantity(order_html: str | None) -> float | None:
    if not order_html:
        return None
    text = str(order_html).replace(',', '.')
    patterns = [r'(\d+(?:\.\d+)?)\s*(RUB|UAH|KZT)', r'Сумма[^\d]*(\d+(?:\.\d+)?)', r'Amount[^\d]*(\d+(?:\.\d+)?)']
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                continue
    return None


def extract_steam_login(order_html: str | None) -> str | None:
    if not order_html:
        return None
    text = str(order_html)
    patterns = [r'Steam[^a-zA-Z0-9_\-]*([a-zA-Z0-9_\-]{2,64})', r'Логин[^a-zA-Z0-9_\-]*([a-zA-Z0-9_\-]{2,64})', r'Login[^a-zA-Z0-9_\-]*([a-zA-Z0-9_\-]{2,64})']
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            login = match.group(1)
            if is_valid_steam_login(login):
                return login
    return None
