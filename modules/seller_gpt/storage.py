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


def get_history_limit() -> int:
    try:
        return min(20, max(1, int(get_config().get("history_limit", 8) or 8)))
    except Exception:
        return 8


def set_history_limit(value: int):
    config = get_config()
    config["history_limit"] = min(20, max(1, int(value)))
    save_config(config)


def is_ignore_links() -> bool:
    return bool(get_config().get("ignore_links", True))


def set_ignore_links(value: bool):
    config = get_config()
    config["ignore_links"] = bool(value)
    save_config(config)


def is_use_lot_context() -> bool:
    return bool(get_config().get("use_lot_context", True))


def set_use_lot_context(value: bool):
    config = get_config()
    config["use_lot_context"] = bool(value)
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


def get_handled_message_ids() -> list[str]:
    return [str(i) for i in (get_config().get("handled_message_ids", []) or [])]


def was_handled(message_id: str | int) -> bool:
    return str(message_id) in get_handled_message_ids()


def mark_handled(message_id: str | int):
    config = get_config()
    handled = [str(i) for i in (config.get("handled_message_ids", []) or [])]
    value = str(message_id)
    if value not in handled:
        handled.append(value)
    config["handled_message_ids"] = handled[-1000:]
    save_config(config)
