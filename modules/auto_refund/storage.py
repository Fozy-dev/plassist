from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from settings import Settings as root_settings

from .meta import PREFIX
from .settings import Settings


def get_config() -> dict:
    return Settings.get("auto_refund") or {}


def save_config(config: dict) -> dict:
    Settings.set("auto_refund", config)
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
    return deepcopy(config.get("messages") or {})


def set_message(message_key: str, value: str) -> dict:
    config = get_config()
    messages = deepcopy(config.get("messages") or {})
    messages[message_key] = value
    config["messages"] = messages
    return save_config(config)


def get_ratings() -> dict[str, bool]:
    ratings = deepcopy(get_config().get("ratings") or {})
    for key in ("1", "2", "3", "4", "5"):
        ratings.setdefault(key, False)
    return ratings


def toggle_rating(stars: int) -> dict:
    key = str(stars)
    config = get_config()
    ratings = deepcopy(config.get("ratings") or {})
    ratings[key] = not bool(ratings.get(key))
    config["ratings"] = ratings
    return save_config(config)


def get_max_price() -> float:
    try:
        return float(get_config().get("max_price") or 0)
    except Exception:
        return 0.0


def set_max_price(value: float) -> dict:
    config = get_config()
    config["max_price"] = max(float(value), 0.0)
    return save_config(config)


def is_notify_buyer_enabled() -> bool:
    return bool(get_config().get("notify_buyer"))


def set_notify_buyer(value: bool) -> dict:
    config = get_config()
    config["notify_buyer"] = bool(value)
    return save_config(config)


def get_refunded_orders() -> list[dict]:
    return list(get_config().get("refunded_orders") or [])


def was_refunded(order_id: str | int) -> bool:
    target = str(order_id)
    return any(str(item.get("order_id")) == target for item in get_refunded_orders())


def mark_refunded(order_id: str | int, stars: int, price: float, author: str):
    config = get_config()
    refunded = list(config.get("refunded_orders") or [])
    refunded.append(
        {
            "order_id": str(order_id),
            "stars": int(stars),
            "price": float(price),
            "author": author,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    config["refunded_orders"] = refunded[-200:]
    return save_config(config)
