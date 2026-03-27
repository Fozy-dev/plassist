from __future__ import annotations

import textwrap


def format_message(template: str, **kwargs) -> str:
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def parse_order_id(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.replace(".", " ").split()
    for part in reversed(parts):
        cleaned = part.replace("#", "").strip()
        if cleaned.isdigit():
            return cleaned
    return None


def status_text(enabled: bool) -> str:
    return "Включен" if enabled else "Выключен"


def max_price_text(value: float) -> str:
    return "без лимита" if value <= 0 else f"{value:.2f} ₽"


def ratings_summary(ratings: dict[str, bool]) -> str:
    parts = []
    for key in ("1", "2", "3", "4", "5"):
        parts.append(f"{key}⭐ {'ON' if ratings.get(key) else 'OFF'}")
    return ", ".join(parts)


def prompt_text(message: str) -> str:
    return textwrap.dedent(
        f"""
        <b>AutoRefund</b>

        {message}
        """
    ).strip()
