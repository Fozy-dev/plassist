from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import uuid4

from settings import Settings as root_settings

from .meta import PREFIX
from .settings import Settings


def get_config() -> dict:
    return Settings.get("auto_bonus") or {}


def save_config(config: dict) -> dict:
    Settings.set("auto_bonus", config)
    return config


def is_enabled() -> bool:
    return bool(get_config().get("enabled"))


def is_owned() -> bool:
    config = root_settings.get("config") or {}
    owned = config.get("telegram", {}).get("master", {}).get("modules_owned") or []
    return PREFIX in owned


def set_enabled(value: bool) -> dict:
    config = get_config()
    config["enabled"] = bool(value)
    return save_config(config)


def get_messages() -> dict:
    config = get_config()
    messages = deepcopy(config.get("messages") or {})
    messages.setdefault("new_deal", "Спасибо за покупку! Пожалуйста оставьте отзыв и после этого вы автоматически получите ваш подарок 🎁")
    messages.setdefault("bonus_sent", "🎁 Ваш бонус:\n{bonus}")
    messages.setdefault("bonus_not_found", "❌ Бонус для этого товара не найден.")
    return messages


def set_message(message_key: str, value: str) -> dict:
    config = get_config()
    messages = deepcopy(config.get("messages") or {})
    messages[message_key] = value
    config["messages"] = messages
    return save_config(config)


def get_bonuses() -> list[dict]:
    bonuses = list(get_config().get("bonuses") or [])
    bonuses.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return bonuses


def get_bonus(bonus_id: str) -> dict | None:
    return next((item for item in get_bonuses() if item.get("id") == bonus_id), None)


def _ensure_bonus_shape(item: dict) -> dict:
    item = dict(item)
    item.setdefault("id", str(uuid4()))
    item.setdefault("target", "")
    item.setdefault("bonus", "")
    item.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    item.setdefault("updated_at", item["created_at"])
    return item


def upsert_bonus(target: str, bonus: str, bonus_id: str | None = None) -> dict:
    config = get_config()
    bonuses = list(config.get("bonuses") or [])
    now = datetime.now().isoformat(timespec="seconds")
    normalized = []
    for item in bonuses:
        normalized.append(_ensure_bonus_shape(item))

    if bonus_id:
        for item in normalized:
            if item["id"] == bonus_id:
                item["target"] = target
                item["bonus"] = bonus
                item["updated_at"] = now
                config["bonuses"] = normalized
                save_config(config)
                return item

    item = _ensure_bonus_shape({"target": target, "bonus": bonus, "created_at": now, "updated_at": now})
    normalized.append(item)
    config["bonuses"] = normalized
    save_config(config)
    return item


def delete_bonus(bonus_id: str) -> bool:
    config = get_config()
    bonuses = [item for item in config.get("bonuses") or [] if item.get("id") != bonus_id]
    if len(bonuses) == len(config.get("bonuses") or []):
        return False
    config["bonuses"] = bonuses
    save_config(config)
    return True


def set_sent_deal(deal_key: str):
    config = get_config()
    sent = list(config.get("sent_deals") or [])
    if deal_key not in sent:
        sent.append(deal_key)
        config["sent_deals"] = sent
        save_config(config)


def was_sent(deal_key: str) -> bool:
    return deal_key in (get_config().get("sent_deals") or [])
