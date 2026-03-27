from __future__ import annotations

import re
from typing import Iterable


def normalize(value: str | int | None) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^\w\d]+", " ", raw, flags=re.UNICODE)
    return " ".join(raw.split())


def format_message(template: str, **kwargs) -> str:
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def match_bonus(targets: Iterable[dict], item_id: str | int | None, item_name: str | None) -> dict | None:
    normalized_id = normalize(item_id)
    normalized_name = normalize(item_name)

    for entry in targets:
        target = normalize(entry.get("target"))
        if not target:
            continue
        if normalized_id and target == normalized_id:
            return entry
        if normalized_name and (target == normalized_name or target in normalized_name or normalized_name in target):
            return entry
    return None
