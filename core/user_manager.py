from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


USERS_PATH = "bot_data/users.json"
SYSTEM_PATH = "bot_data/system.json"
ACTIONS_LOG_PATH = "bot_data/actions_log.json"

TARIFFS = {
    "week": {"title": "1 неделя", "price": 70.0, "days": 7},
    "month": {"title": "1 месяц", "price": 120.0, "days": 30},
    "year": {"title": "1 год", "price": 1290.0, "days": 365},
}
REMOVED_MODULES = {"auto_bonus"}


def tariff_title_ru(tariff_key: str | None) -> str:
    key = (tariff_key or "").strip().lower()
    if not key:
        return "Нету"
    tariff = TARIFFS.get(key)
    if tariff and tariff.get("title"):
        return str(tariff["title"])
    mapping = {
        "week": "1 неделя",
        "month": "1 месяц",
        "year": "1 год",
    }
    return mapping.get(key, key)


def _read_json(path: str, default):
    path = resolve_runtime_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        normalized = normalize_data(payload)
        if normalized != payload:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(normalized, file, ensure_ascii=False, indent=4)
        return normalized
    except Exception:
        normalized_default = normalize_data(default)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(normalized_default, file, ensure_ascii=False, indent=4)
        return normalized_default


def _write_json(path: str, payload):
    path = resolve_runtime_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    normalized_payload = normalize_data(payload)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(normalized_payload, file, ensure_ascii=False, indent=4)


class UserManager:
    def __init__(self):
        _read_json(USERS_PATH, {})
        _read_json(
            SYSTEM_PATH,
            {
                "maintenance_mode": False,
                "maintenance_text": (
                    "🔧 Технические работы\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Бот временно недоступен. Следите за обновлениями: @playerok_assist\n"
                    "По вопросам: @plassist_helpbot"
                ),
                "maintenance_started_at": None,
                "maintenance_resume_uuids": [],
            },
        )
        _read_json(ACTIONS_LOG_PATH, [])

    def all_users(self) -> dict:
        return _read_json(USERS_PATH, {})

    def get_user(self, tg_id: int) -> dict | None:
        user = self.all_users().get(str(tg_id))
        if not user:
            return None
        modules_owned = [item for item in (user.get("modules_owned") or []) if item not in REMOVED_MODULES]
        if modules_owned != (user.get("modules_owned") or []):
            user = self.update_user(tg_id, modules_owned=modules_owned)
        return user

    def ensure_user(self, tg_id: int, username: str | None, first_name: str | None) -> dict:
        users = self.all_users()
        key = str(tg_id)
        now = datetime.now().isoformat(timespec="seconds")
        if key not in users:
            users[key] = {
                "tg_id": tg_id,
                "username": f"@{username}" if username else "",
                "first_name": first_name or "",
                "balance": 0.0,
                "tariff": None,
                "tariff_expires": None,
                "is_banned": False,
                "trial_used": False,
                "registered_at": now,
                "last_active": now,
                "auto_renew": True,
                "admin_level": "full",
                "referred_partner_id": None,
                "referred_partner_slug": None,
                "referred_at": None,
                "modules_owned": [],
            }
        else:
            users[key]["username"] = f"@{username}" if username else users[key].get("username", "")
            users[key]["first_name"] = first_name or users[key].get("first_name", "")
            users[key]["last_active"] = now
            users[key].setdefault("trial_used", False)
            users[key].setdefault("admin_level", "full")
            users[key].setdefault("referred_partner_id", None)
            users[key].setdefault("referred_partner_slug", None)
            users[key].setdefault("referred_at", None)
            users[key]["modules_owned"] = [item for item in (users[key].get("modules_owned") or []) if item not in REMOVED_MODULES]
        _write_json(USERS_PATH, users)
        return users[key]

    def update_user(self, tg_id: int, **fields) -> dict:
        users = self.all_users()
        key = str(tg_id)
        if key not in users:
            raise KeyError(f"User {tg_id} not found")
        if "modules_owned" in fields:
            fields["modules_owned"] = [item for item in (fields.get("modules_owned") or []) if item not in REMOVED_MODULES]
        users[key].update(fields)
        _write_json(USERS_PATH, users)
        return users[key]

    def get_system(self) -> dict:
        return _read_json(SYSTEM_PATH, {})

    def set_system(self, **fields) -> dict:
        system = self.get_system()
        system.update(fields)
        _write_json(SYSTEM_PATH, system)
        return system

    def has_active_tariff(self, tg_id: int) -> bool:
        user = self.get_user(tg_id)
        if not user or not user.get("tariff") or not user.get("tariff_expires"):
            return False
        return datetime.fromisoformat(user["tariff_expires"]) > datetime.now()

    def can_create_bot(self, tg_id: int, bots_count: int) -> tuple[bool, str | None]:
        user = self.get_user(tg_id)
        if not user or not self.has_active_tariff(tg_id):
            return False, "no_tariff"
        return True, None

    def activate_tariff(self, tg_id: int, tariff_key: str, trial_days: int | None = None, charge: bool = True) -> dict:
        user = self.get_user(tg_id)
        tariff = TARIFFS[tariff_key]
        if charge:
            user["balance"] = round(float(user["balance"]) - tariff["price"], 2)
        days = trial_days or tariff["days"]
        now = datetime.now()
        start = now
        if user.get("tariff_expires"):
            current_expiry = datetime.fromisoformat(user["tariff_expires"])
            if current_expiry > now:
                start = current_expiry
        user["tariff"] = tariff_key
        user["tariff_expires"] = (start + timedelta(days=days)).isoformat(timespec="seconds")
        self.update_user(tg_id, **{k: v for k, v in user.items() if k != 'tg_id'})
        return user

    def add_balance(self, tg_id: int, amount: float) -> dict:
        user = self.get_user(tg_id)
        user["balance"] = round(float(user["balance"]) + float(amount), 2)
        self.update_user(tg_id, **{k: v for k, v in user.items() if k != 'tg_id'})
        return user

    def set_balance(self, tg_id: int, amount: float) -> dict:
        user = self.get_user(tg_id)
        user["balance"] = round(float(amount), 2)
        self.update_user(tg_id, **{k: v for k, v in user.items() if k != 'tg_id'})
        return user

    def log_action(self, actor: str, action: str, result: str):
        logs = _read_json(ACTIONS_LOG_PATH, [])
        logs.append(
            {
                "at": datetime.now().isoformat(timespec="seconds"),
                "actor": actor,
                "action": action,
                "result": result,
            }
        )
        _write_json(ACTIONS_LOG_PATH, logs[-200:])

    def get_actions(self, limit: int = 10) -> list[dict]:
        logs = _read_json(ACTIONS_LOG_PATH, [])
        if limit <= 0:
            return logs
        return logs[-limit:]

