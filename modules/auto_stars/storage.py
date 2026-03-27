from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from settings import Settings as root_settings

from .meta import PREFIX
from .settings import Settings


def get_config() -> dict:
    return Settings.get("auto_stars") or {}


def save_config(config: dict) -> dict:
    Settings.set("auto_stars", config)
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


def get_fragment_config() -> dict:
    return deepcopy(get_config().get("fragment_api") or {})


def set_fragment_value(key: str, value):
    config = get_config()
    fragment = deepcopy(config.get("fragment_api") or {})
    fragment[key] = value
    config["fragment_api"] = fragment
    return save_config(config)


def get_ton_config() -> dict:
    return deepcopy(get_config().get("ton") or {})


def set_ton_value(key: str, value):
    config = get_config()
    ton = deepcopy(config.get("ton") or {})
    ton[key] = value
    config["ton"] = ton
    return save_config(config)


def set_allowed_quantities(values: list[int]):
    config = get_config()
    config["allowed_quantities"] = sorted({int(item) for item in values if int(item) > 0})
    return save_config(config)


def get_allowed_quantities() -> list[int]:
    values = get_config().get("allowed_quantities") or []
    return sorted({int(item) for item in values if str(item).isdigit() or isinstance(item, int)})


def set_auto_refund(value: bool):
    config = get_config()
    config["auto_refund"] = bool(value)
    return save_config(config)


def get_pending_orders() -> dict[str, list[dict]]:
    config = get_config()
    return deepcopy(config.get("pending_orders") or {})


def _save_pending_orders(payload: dict[str, list[dict]]):
    config = get_config()
    config["pending_orders"] = payload
    save_config(config)


def get_last_pending_order(chat_id: int | str) -> dict | None:
    key = str(chat_id)
    orders = get_pending_orders().get(key) or []
    for order in reversed(orders):
        if not order.get("completed") and not order.get("cancelled"):
            return order
    return None


def add_pending_order(chat_id: int | str, order_data: dict):
    key = str(chat_id)
    payload = get_pending_orders()
    payload.setdefault(key, [])
    payload[key].append(order_data)
    _save_pending_orders(payload)


def update_pending_order(chat_id: int | str, order_id: str | int, **fields) -> dict | None:
    key = str(chat_id)
    payload = get_pending_orders()
    orders = payload.get(key) or []
    for order in orders:
        if str(order.get("order_id")) == str(order_id):
            order.update(fields)
            order["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _save_pending_orders(payload)
            return order
    return None


def mark_completed(chat_id: int | str, order_id: str | int, *, completed: bool = True, cancelled: bool = False):
    return update_pending_order(
        chat_id,
        order_id,
        completed=completed,
        cancelled=cancelled,
    )


def update_stats(success: bool, quantity: int):
    config = get_config()
    stats = deepcopy(config.get("stats") or {})
    date_key = datetime.now().strftime("%Y-%m-%d")
    day = deepcopy(stats.get(date_key) or {})
    day.setdefault("successful_transactions", 0)
    day.setdefault("unsuccessful_transactions", 0)
    day.setdefault("quantities_sold", {})
    day.setdefault("transactions", [])
    if success:
        day["successful_transactions"] += 1
    else:
        day["unsuccessful_transactions"] += 1
    quantity_key = str(quantity)
    day["quantities_sold"][quantity_key] = int(day["quantities_sold"].get(quantity_key, 0)) + 1
    day["transactions"].append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "quantity": quantity,
            "status": "success" if success else "fail",
        }
    )
    stats[date_key] = day
    config["stats"] = stats
    save_config(config)


def get_today_stats() -> dict:
    stats = get_config().get("stats") or {}
    return deepcopy(stats.get(datetime.now().strftime("%Y-%m-%d")) or {})
