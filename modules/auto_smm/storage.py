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


def get_api_url() -> str:
    return str(get_config().get("api_url", "https://optsmm.ru/api/v2") or "").strip()


def set_api_url(value: str):
    config = get_config()
    config["api_url"] = str(value).strip()
    save_config(config)


def get_api_key() -> str:
    return str(get_config().get("api_key", "") or "").strip()


def set_api_key(value: str):
    config = get_config()
    config["api_key"] = str(value).strip()
    save_config(config)


def is_auto_refund_enabled() -> bool:
    return bool(get_config().get("auto_refund_on_error", True))


def set_auto_refund(value: bool):
    config = get_config()
    config["auto_refund_on_error"] = bool(value)
    save_config(config)


def is_confirm_link_enabled() -> bool:
    return bool(get_config().get("confirm_link", True))


def set_confirm_link(value: bool):
    config = get_config()
    config["confirm_link"] = bool(value)
    save_config(config)


def get_allowed_domains() -> list[str]:
    return [str(i).strip().lower() for i in (get_config().get("allowed_domains", []) or []) if str(i).strip()]


def add_domain(value: str):
    config = get_config()
    items = [str(i).strip().lower() for i in (config.get("allowed_domains", []) or []) if str(i).strip()]
    value = str(value).strip().lower()
    if value and value not in items:
        items.append(value)
    config["allowed_domains"] = items
    save_config(config)


def remove_domain(value: str):
    config = get_config()
    value = str(value).strip().lower()
    config["allowed_domains"] = [str(i).strip().lower() for i in (config.get("allowed_domains", []) or []) if str(i).strip().lower() != value]
    save_config(config)


def get_mappings() -> list[dict]:
    mappings = list(get_config().get("mappings", []) or [])
    result = []
    for item in mappings:
        try:
            result.append(
                {
                    "name": str(item.get("name", "")).strip(),
                    "phrase": str(item.get("phrase", "")).strip(),
                    "service_id": int(item.get("service_id", 0)),
                    "quantity": int(item.get("quantity", 0)),
                }
            )
        except Exception:
            continue
    return result


def add_mapping(name: str, phrase: str, service_id: int, quantity: int):
    config = get_config()
    mappings = list(config.get("mappings", []) or [])
    mappings.append(
        {
            "name": str(name).strip() or f"Mapping {len(mappings) + 1}",
            "phrase": str(phrase).strip(),
            "service_id": int(service_id),
            "quantity": int(quantity),
        }
    )
    config["mappings"] = mappings
    save_config(config)


def remove_mapping(index: int):
    config = get_config()
    mappings = list(config.get("mappings", []) or [])
    if 0 <= index < len(mappings):
        mappings.pop(index)
    config["mappings"] = mappings
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
