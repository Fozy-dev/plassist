from __future__ import annotations

import re
from urllib.parse import urlparse


URL_RE = re.compile(r"(https?://[^\s<>\"]+)", flags=re.IGNORECASE)
ORDER_ID_RE = re.compile(r"#([A-Z0-9]+)", flags=re.IGNORECASE)


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
    return f"{value[:4]}...{value[-4:]}"


def prompt_text(text: str) -> str:
    return f"<b>AutoSMM</b>\n\n{text}"


def extract_order_id_from_message(message_text: str | None) -> str | None:
    if not message_text:
        return None
    match = ORDER_ID_RE.search(str(message_text))
    return match.group(1) if match else None


def extract_first_url(text: str | None) -> str | None:
    if not text:
        return None
    match = URL_RE.search(str(text))
    return match.group(1).strip() if match else None


def normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower().strip()


def is_allowed_url(url: str, domains: list[str]) -> bool:
    domain = normalize_domain(url)
    return bool(domain and domain in {str(i).strip().lower() for i in domains})


def find_mapping(order_text: str, mappings: list[dict]) -> dict | None:
    haystack = str(order_text or "").lower()
    for mapping in mappings:
        phrase = str(mapping.get("phrase", "")).strip().lower()
        if phrase and phrase in haystack:
            return mapping
    return None
