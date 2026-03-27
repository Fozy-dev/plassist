from __future__ import annotations

import re


def normalize_username(value: str | None) -> str:
    return (value or "").strip()


def is_valid_username(value: str | None) -> bool:
    return bool(re.fullmatch(r"@\w{4,}", normalize_username(value)))


def parse_stars_quantity(text: str | None) -> int | None:
    if not text:
        return None
    patterns = [
        r"(\d+)\s*(?:stars?|старс(?:ов|ы)?|зв[её]зд(?:ы)?)",
        r"(?:stars?|старс(?:ов|ы)?|зв[её]зд(?:ы)?)\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
    return None


def blur_name(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "Не найдено"
    return "".join(ch if index % 2 == 0 else "*" for index, ch in enumerate(raw))


def format_message(template: str, **kwargs) -> str:
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except Exception:
        return template
