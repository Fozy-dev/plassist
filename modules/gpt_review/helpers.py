from __future__ import annotations

import re


ORDER_ID_RE = re.compile(r"#(\d+)")


def format_message(template: str, **kwargs) -> str:
    try:
        return str(template or "").format(**kwargs)
    except Exception:
        return str(template or "")


def parse_order_id(text: str | None) -> str | None:
    if not text:
        return None
    match = ORDER_ID_RE.search(str(text))
    if match:
        return match.group(1)
    numbers = re.findall(r"\d+", str(text))
    return numbers[-1] if numbers else None


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
    return f"<b>GPT Review</b>\n\n{text}"


def build_prompt(prompt: str, order, review) -> str:
    replacements = {
        "{category}": str(getattr(getattr(order, "subcategory", None), "name", "") or ""),
        "{categoryfull}": str(getattr(getattr(order, "subcategory", None), "fullname", "") or ""),
        "{cost}": str(getattr(order, "sum", None) or getattr(order, "price", None) or ""),
        "{rating}": str(getattr(review, "stars", "") or ""),
        "{name}": str(getattr(order, "buyer_username", "") or getattr(review, "author", "") or ""),
        "{item}": str(getattr(order, "title", "") or getattr(order, "short_description", "") or getattr(order, "description", "") or ""),
        "{text}": str(getattr(review, "text", "") or ""),
    }
    result = str(prompt or "")
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result.strip()
