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


def get_api_login() -> str:
    return str(get_config().get("api_login", "") or "").strip()


def set_api_login(value: str):
    config = get_config()
    config["api_login"] = str(value).strip()
    save_config(config)


def get_api_password() -> str:
    return str(get_config().get("api_password", "") or "").strip()


def set_api_password(value: str):
    config = get_config()
    config["api_password"] = str(value).strip()
    save_config(config)


def is_auto_refund_enabled() -> bool:
    return bool(get_config().get("auto_refund_on_error", True))


def set_auto_refund(value: bool):
    config = get_config()
    config["auto_refund_on_error"] = bool(value)
    save_config(config)


def is_order_verification_enabled() -> bool:
    return bool(get_config().get("order_verification_enabled", True))


def set_order_verification(value: bool):
    config = get_config()
    config["order_verification_enabled"] = bool(value)
    save_config(config)


def is_confirmation_reminder_enabled() -> bool:
    return bool(get_config().get("confirmation_reminder", True))


def set_confirmation_reminder(value: bool):
    config = get_config()
    config["confirmation_reminder"] = bool(value)
    save_config(config)


def get_reminder_time_minutes() -> float:
    try:
        return max(0.5, float(get_config().get("reminder_time_minutes", 2.5) or 2.5))
    except Exception:
        return 2.5


def set_reminder_time_minutes(value: float):
    config = get_config()
    config["reminder_time_minutes"] = max(0.5, float(value))
    save_config(config)


def get_allowed_subcategory_ids() -> list[int]:
    values = get_config().get("allowed_subcategory_ids", [1086]) or [1086]
    result = []
    for value in values:
        try:
            result.append(int(value))
        except Exception:
            continue
    return result or [1086]


def set_allowed_subcategory_ids(values: list[int]):
    config = get_config()
    config["allowed_subcategory_ids"] = [int(v) for v in values]
    save_config(config)


def get_blacklist_logins() -> list[str]:
    return [str(i).lower() for i in (get_config().get("blacklist_logins", []) or []) if str(i).strip()]


def add_blacklist_login(login: str):
    config = get_config()
    values = [str(i).lower() for i in (config.get("blacklist_logins", []) or [])]
    login = str(login).strip().lower()
    if login and login not in values:
        values.append(login)
    config["blacklist_logins"] = values
    save_config(config)


def remove_blacklist_login(login: str):
    config = get_config()
    login = str(login).strip().lower()
    values = [str(i).lower() for i in (config.get("blacklist_logins", []) or []) if str(i).strip().lower() != login]
    config["blacklist_logins"] = values
    save_config(config)


def get_messages() -> dict:
    return dict(get_config().get("messages", {}) or {})


def set_message(message_key: str, value: str):
    config = get_config()
    messages = dict(config.get("messages", {}) or {})
    messages[message_key] = str(value)
    config["messages"] = messages
    save_config(config)


def add_history(item: dict):
    config = get_config()
    history = list(config.get("history", []) or [])
    history.append(item)
    config["history"] = history[-300:]
    save_config(config)


def get_history() -> list[dict]:
    return list(get_config().get("history", []) or [])
