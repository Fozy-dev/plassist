from __future__ import annotations

from settings import Settings as root_settings

from .meta import PREFIX
from .settings import Settings


def get_config() -> dict:
    return Settings.get(PREFIX) or {}


def save_config(config: dict):
    Settings.set(PREFIX, config)


def is_owned() -> bool:
    config = root_settings.get("config") or {}
    owned = config.get("telegram", {}).get("master", {}).get("modules_owned") or []
    return PREFIX in owned


def is_enabled() -> bool:
    return bool(get_config().get("enabled", False))


def set_enabled(value: bool):
    config = get_config()
    config["enabled"] = bool(value)
    save_config(config)


def get_api_base_url() -> str:
    return str(get_config().get("api_base_url", "") or "").strip()


def set_api_base_url(value: str):
    config = get_config()
    config["api_base_url"] = str(value).strip()
    save_config(config)


def get_api_key() -> str:
    return str(get_config().get("api_key", "") or "").strip()


def set_api_key(value: str):
    config = get_config()
    config["api_key"] = str(value).strip()
    save_config(config)


def get_model() -> str:
    return str(get_config().get("model", "") or "").strip()


def set_model(value: str):
    config = get_config()
    config["model"] = str(value).strip()
    save_config(config)


def get_timeout_sec() -> int:
    try:
        return max(5, int(get_config().get("timeout_sec", 45) or 45))
    except Exception:
        return 45


def set_timeout_sec(value: int):
    config = get_config()
    config["timeout_sec"] = max(5, int(value))
    save_config(config)


def get_min_stars() -> int:
    try:
        return min(5, max(1, int(get_config().get("min_stars", 5) or 5)))
    except Exception:
        return 5


def set_min_stars(value: int):
    config = get_config()
    config["min_stars"] = min(5, max(1, int(value)))
    save_config(config)


def is_only_without_reply() -> bool:
    return bool(get_config().get("only_without_reply", True))


def set_only_without_reply(value: bool):
    config = get_config()
    config["only_without_reply"] = bool(value)
    save_config(config)


def get_prompt() -> str:
    return str(get_config().get("prompt", "") or "").strip()


def set_prompt(value: str):
    config = get_config()
    config["prompt"] = str(value).strip()
    save_config(config)


def get_messages() -> dict:
    return dict(get_config().get("messages", {}) or {})


def set_message(message_key: str, value: str):
    config = get_config()
    messages = dict(config.get("messages", {}) or {})
    messages[message_key] = str(value)
    config["messages"] = messages
    save_config(config)


def get_replied_orders() -> list[str]:
    return [str(i) for i in (get_config().get("replied_orders", []) or [])]


def was_replied(order_id: str) -> bool:
    return str(order_id) in get_replied_orders()


def mark_replied(order_id: str):
    config = get_config()
    replied = [str(i) for i in (config.get("replied_orders", []) or [])]
    value = str(order_id)
    if value not in replied:
        replied.append(value)
    config["replied_orders"] = replied[-500:]
    save_config(config)
