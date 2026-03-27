from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aiogram import Bot

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data
from core.utils import is_proxy_valid, is_proxy_working
from settings import Settings as sett


CHILD_BOTS_PATH = "bot_data/child_bots.json"
BALANCES_PATH = "bot_data/balances.json"
REMOVED_MODULES = {"auto_bonus"}


def _read_json(path: str, default: Any):
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


def _write_json(path: str, payload: Any):
    path = resolve_runtime_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    normalized_payload = normalize_data(payload)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(normalized_payload, file, ensure_ascii=False, indent=4)


@dataclass
class ChildRuntime:
    uuid: str
    process: asyncio.subprocess.Process | None = None
    monitor_task: asyncio.Task | None = None
    started_at: datetime | None = None
    restart_attempts: int = 0


class ChildBotManager:
    def __init__(self, master_bot: Bot | None = None):
        self.master_bot = master_bot
        self._runtimes: dict[str, ChildRuntime] = {}
        _read_json(CHILD_BOTS_PATH, [])
        _read_json(BALANCES_PATH, {})

    def attach_master_bot(self, master_bot: Bot):
        self.master_bot = master_bot

    def load_all_bots(self) -> list[dict]:
        bots = _read_json(CHILD_BOTS_PATH, [])
        changed = False
        for bot in bots:
            modules_owned = [item for item in (bot.get("modules_owned") or []) if item not in REMOVED_MODULES]
            if modules_owned != (bot.get("modules_owned") or []):
                bot["modules_owned"] = modules_owned
                changed = True
            if "pl_tg_token" not in bot:
                bot["pl_tg_token"] = bot.get("tg_token", "")
                changed = True
            if "fp_tg_token" not in bot:
                bot["fp_tg_token"] = ""
                changed = True
            if "platforms" not in bot:
                bot["platforms"] = ["playerok"]
                changed = True
            if "fp_golden_key" not in bot:
                bot["fp_golden_key"] = ""
                changed = True
            if "fp_user_agent" not in bot:
                bot["fp_user_agent"] = ""
                changed = True
            if "fp_proxy" not in bot:
                bot["fp_proxy"] = ""
                changed = True
            if "fp_is_active" not in bot:
                bot["fp_is_active"] = False
                changed = True
            if "pl_is_active" not in bot:
                bot["pl_is_active"] = "playerok" in bot.get("platforms", [])
                changed = True

            # Compatibility with legacy key names from older TZ revisions.
            if "pl_user_agent" not in bot:
                bot["pl_user_agent"] = bot.get("user_agent", "")
                changed = True
            if "pl_proxy" not in bot:
                bot["pl_proxy"] = bot.get("proxy", "")
                changed = True
            if "authorized_ids" not in bot:
                bot["authorized_ids"] = [bot.get("owner_tg_id")] if bot.get("owner_tg_id") else []
                changed = True
            if "bot_description" not in bot:
                bot["bot_description"] = "Автоматизация магазина Playerok/FunPay."
                changed = True
            if "bot_short_description" not in bot:
                bot["bot_short_description"] = "Raidex Assist"
                changed = True
            if "link_buttons" not in bot:
                bot["link_buttons"] = [
                    {"text": "📢 Наш канал", "url": "https://t.me/alexeyproduction"},
                    {"text": "🤖 Наш бот", "url": "https://t.me/alexey_production_bot"},
                ]
                changed = True
            if "modules_owned" not in bot:
                bot["modules_owned"] = []
                changed = True

            # Keep old keys in sync for existing code paths.
            if bot.get("pl_user_agent", "") != bot.get("user_agent", ""):
                bot["user_agent"] = bot.get("pl_user_agent", "")
                changed = True
            if bot.get("pl_proxy", "") != bot.get("proxy", ""):
                bot["proxy"] = bot.get("pl_proxy", "")
                changed = True
        if changed:
            self._save(bots)
        return bots

    def _save(self, bots: list[dict]):
        _write_json(CHILD_BOTS_PATH, bots)

    def get(self, uuid_value: str) -> dict | None:
        return next((bot for bot in self.load_all_bots() if bot["uuid"] == uuid_value), None)

    def get_all(self, owner_id: int) -> list[dict]:
        return [bot for bot in self.load_all_bots() if bot["owner_tg_id"] == owner_id]

    @staticmethod
    def _preferred_tg_token(bot: dict) -> str:
        return (
            bot.get("pl_tg_token")
            or bot.get("fp_tg_token")
            or bot.get("tg_token")
            or ""
        ).strip()

    async def _fetch_tg_username(self, token: str) -> str:
        token = (token or "").strip()
        if not token:
            return ""
        bot: Bot | None = None
        try:
            bot = Bot(token=token)
            me = await bot.get_me()
            username = (me.username or "").strip()
            if username and not username.startswith("@"):
                username = f"@{username}"
            return username
        except Exception:
            return ""
        finally:
            if bot is not None:
                try:
                    await bot.session.close()
                except Exception:
                    pass

    async def refresh_usernames_for_owner(self, owner_id: int) -> int:
        bots = self.get_all(owner_id)
        updated = 0
        for bot in bots:
            token = self._preferred_tg_token(bot)
            if not token:
                continue
            if bot.get("tg_username"):
                continue
            username = await self._fetch_tg_username(token)
            if username:
                self.update(bot["uuid"], tg_username=username)
                updated += 1
        return updated

    def child_events_path(self, uuid_value: str) -> str:
        return resolve_runtime_path(os.path.join("bot_data", "bots", uuid_value, "bot_data", "events_log.json"))

    def get_balance(self, owner_id: int) -> float:
        balances = _read_json(BALANCES_PATH, {})
        return float(balances.get(str(owner_id), 0.0))

    def ensure_balance(self, owner_id: int):
        balances = _read_json(BALANCES_PATH, {})
        balances.setdefault(str(owner_id), 0.0)
        _write_json(BALANCES_PATH, balances)

    def create(
        self,
        owner_id: int,
        pl_tg_token: str,
        fp_tg_token: str,
        pl_token: str,
        ua: str,
        proxy: str,
        password: str,
        platforms: list[str] | None = None,
        fp_golden_key: str = "",
        fp_user_agent: str = "",
        fp_proxy: str = "",
        modules_owned: list[str] | None = None,
    ) -> dict:
        platforms = list(platforms or ["playerok"])
        if "playerok" not in platforms and pl_token:
            platforms.append("playerok")
        if "funpay" not in platforms and fp_golden_key:
            platforms.append("funpay")
        bot_uuid = str(uuid.uuid4())
        created_at = datetime.now().isoformat(timespec="seconds")
        config = {
            "uuid": bot_uuid,
            "owner_tg_id": owner_id,
            "tg_token": pl_tg_token or fp_tg_token,
            "pl_tg_token": pl_tg_token,
            "fp_tg_token": fp_tg_token,
            "pl_token": pl_token,
            "user_agent": ua,
            "proxy": proxy,
            "pl_user_agent": ua,
            "pl_proxy": proxy,
            "proxy_list": [proxy] if proxy else [],
            "proxy_index": 0,
            "password": password,
            "created_at": created_at,
            "is_active": True,
            "tg_username": "",
            "platforms": platforms,
            "fp_golden_key": fp_golden_key,
            "fp_user_agent": fp_user_agent,
            "fp_proxy": fp_proxy,
            "fp_is_active": "funpay" in platforms and bool(fp_golden_key),
            "pl_is_active": "playerok" in platforms and bool(pl_token),
            "authorized_ids": [owner_id],
            "modules_owned": [item for item in (modules_owned or []) if item not in REMOVED_MODULES],
            "bot_description": "Автоматизация магазина Playerok/FunPay.",
            "bot_short_description": "Raidex Assist",
            "link_buttons": [
                {"text": "📢 Наш канал", "url": "https://t.me/alexeyproduction"},
                {"text": "🤖 Наш бот", "url": "https://t.me/alexey_production_bot"},
            ],
        }
        bots = self.load_all_bots()
        bots.append(config)
        self._save(bots)
        self._prepare_child_root(config)
        return config

    def update(self, uuid_value: str, **fields) -> dict | None:
        if "pl_user_agent" in fields and "user_agent" not in fields:
            fields["user_agent"] = fields["pl_user_agent"]
        if "pl_proxy" in fields and "proxy" not in fields:
            fields["proxy"] = fields["pl_proxy"]
        if "user_agent" in fields and "pl_user_agent" not in fields:
            fields["pl_user_agent"] = fields["user_agent"]
        if "proxy" in fields and "pl_proxy" not in fields:
            fields["pl_proxy"] = fields["proxy"]
        if "pl_tg_token" in fields and "tg_token" not in fields and fields.get("pl_tg_token"):
            fields["tg_token"] = fields["pl_tg_token"]
        if "fp_tg_token" in fields and "tg_token" not in fields and fields.get("fp_tg_token"):
            fields["tg_token"] = fields["fp_tg_token"]
        bots = self.load_all_bots()
        updated = None
        for bot in bots:
            if bot["uuid"] == uuid_value:
                if "modules_owned" in fields:
                    fields["modules_owned"] = [item for item in (fields.get("modules_owned") or []) if item not in REMOVED_MODULES]
                bot.update(fields)
                updated = bot
                break
        if updated:
            self._save(bots)
            self._prepare_child_root(updated)
        return updated

    async def start(self, uuid_value: str, restart_attempts: int = 0) -> bool:
        config = self.get(uuid_value)
        if not config:
            return False
        runtime = self._runtimes.get(uuid_value)
        keep_pid = None
        if runtime and runtime.process and runtime.process.returncode is None:
            keep_pid = runtime.process.pid
        self._terminate_duplicate_child_processes(uuid_value, keep_pid=keep_pid)
        if runtime and runtime.process and runtime.process.returncode is None:
            return True

        child_root = self._child_root(config)
        self._prepare_child_root(config)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            os.path.join(os.getcwd(), "child_bot_runner.py"),
            "--uuid",
            uuid_value,
            "--root",
            child_root,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        runtime = ChildRuntime(
            uuid=uuid_value,
            process=process,
            started_at=datetime.now(),
            restart_attempts=restart_attempts,
        )
        runtime.monitor_task = asyncio.create_task(self._monitor_process(runtime))
        self._runtimes[uuid_value] = runtime
        fields = {"is_active": True}
        username = await self._fetch_tg_username(self._preferred_tg_token(config))
        if username:
            fields["tg_username"] = username
        self.update(uuid_value, **fields)
        return True

    def _terminate_duplicate_child_processes(self, uuid_value: str, keep_pid: int | None = None):
        if sys.platform != "win32":
            return

        escaped_uuid = uuid_value.replace("'", "''")
        cmd = (
            "$ErrorActionPreference='SilentlyContinue';"
            f"$u='{escaped_uuid}';"
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*child_bot_runner.py*' -and $_.CommandLine -like \"*$u*\" } | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        )
        try:
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10,
            ).strip()
        except Exception:
            return

        if not raw:
            return

        try:
            rows = json.loads(raw)
        except Exception:
            return

        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            return

        current_pid = os.getpid()
        for row in rows:
            try:
                pid = int(row.get("ProcessId"))
            except Exception:
                continue
            if pid == current_pid or (keep_pid is not None and pid == keep_pid):
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    def _terminate_unmanaged_child_processes(self, active_uuids: set[str]):
        if sys.platform != "win32":
            return

        cmd = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*child_bot_runner.py*' } | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        )
        try:
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10,
            ).strip()
        except Exception:
            return

        if not raw:
            return

        try:
            rows = json.loads(raw)
        except Exception:
            return

        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            return

        current_pid = os.getpid()
        for row in rows:
            try:
                pid = int(row.get("ProcessId"))
            except Exception:
                continue
            if pid == current_pid:
                continue

            cmdline = str(row.get("CommandLine") or "")
            marker = "--uuid"
            if marker not in cmdline:
                continue

            try:
                runner_uuid = cmdline.split(marker, 1)[1].strip().split()[0]
            except Exception:
                continue

            if runner_uuid in active_uuids:
                continue

            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    async def stop(self, uuid_value: str) -> bool:
        runtime = self._runtimes.get(uuid_value)
        if runtime and runtime.process and runtime.process.returncode is None:
            runtime.process.terminate()
            try:
                await asyncio.wait_for(runtime.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                runtime.process.kill()
                await runtime.process.wait()
        if runtime and runtime.monitor_task:
            runtime.monitor_task.cancel()
        self._runtimes.pop(uuid_value, None)
        self.update(uuid_value, is_active=False)
        return True

    async def restart(self, uuid_value: str) -> bool:
        await self.stop(uuid_value)
        return await self.start(uuid_value)

    async def delete(self, uuid_value: str) -> bool:
        await self.stop(uuid_value)
        bots = [bot for bot in self.load_all_bots() if bot["uuid"] != uuid_value]
        self._save(bots)
        return True

    async def autostart(self) -> int:
        bots = self.load_all_bots()
        active_uuids = {bot["uuid"] for bot in bots if bot.get("is_active")}
        self._terminate_unmanaged_child_processes(active_uuids)

        started = 0
        for bot in bots:
            if bot.get("is_active"):
                if await self.start(bot["uuid"]):
                    started += 1
        return started

    def get_runtime_stats(self, uuid_value: str) -> dict:
        runtime = self._runtimes.get(uuid_value)
        if not runtime or not runtime.started_at:
            return {"uptime": "-"}
        delta = datetime.now() - runtime.started_at
        minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(minutes, 60)
        return {"uptime": f"{hours}ч {minutes}м"}

    async def _monitor_process(self, runtime: ChildRuntime):
        try:
            code = await runtime.process.wait()
        except asyncio.CancelledError:
            return
        if code == 0:
            return
        config = self.get(runtime.uuid)
        if not config or not config.get("is_active"):
            return

        uptime_seconds = 0.0
        if runtime.started_at:
            uptime_seconds = max(0.0, (datetime.now() - runtime.started_at).total_seconds())
        consecutive_failures = runtime.restart_attempts + 1 if uptime_seconds < 120 else 1

        if consecutive_failures > 3:
            await self.update_and_notify(
                runtime.uuid,
                is_active=False,
                text="Остановлен после 3 подряд быстрых сбоев. Проверьте токен и не запущен ли бот где-то ещё.",
            )
            return

        switched_proxy = self.try_switch_proxy(runtime.uuid)
        if switched_proxy:
            await self.update_and_notify(runtime.uuid, text=f"Прокси переключен на {switched_proxy}")
        await asyncio.sleep(10)
        await self.start(runtime.uuid, restart_attempts=consecutive_failures)

    async def update_and_notify(self, uuid_value: str, text: str, **fields):
        bot = self.update(uuid_value, **fields)
        if not bot or not self.master_bot:
            return
        try:
            await self.master_bot.send_message(
                bot["owner_tg_id"],
                f"⚠️ Бот {bot.get('tg_username') or bot['uuid'][:8]}: {text}",
            )
        except Exception:
            pass

    def _child_root(self, config: dict) -> str:
        return resolve_runtime_path(os.path.join("bot_data", "bots", config["uuid"]))

    def _prepare_child_root(self, config: dict):
        root = self._child_root(config)
        os.makedirs(root, exist_ok=True)
        os.makedirs(os.path.join(root, "bot_settings"), exist_ok=True)
        os.makedirs(os.path.join(root, "bot_data"), exist_ok=True)
        os.makedirs(os.path.join(root, "logs"), exist_ok=True)

        config_path = os.path.join(root, "bot_settings", "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as file:
                    child_config = json.load(file)
            except Exception:
                child_config = sett.get("config")
        else:
            child_config = sett.get("config")
        child_config["playerok"]["api"]["token"] = config.get("pl_token", "")
        child_config["playerok"]["api"]["user_agent"] = config.get("pl_user_agent", config.get("user_agent", ""))
        child_config["playerok"]["api"]["proxy"] = config.get("pl_proxy", config.get("proxy", ""))
        runtime_platform = (os.environ.get("CHILD_PLATFORM") or "").strip().lower()
        if runtime_platform == "playerok":
            child_tg_token = config.get("pl_tg_token") or config.get("tg_token", "")
        elif runtime_platform == "funpay":
            child_tg_token = config.get("fp_tg_token") or config.get("tg_token", "")
        else:
            child_tg_token = config.get("pl_tg_token") or config.get("fp_tg_token") or config.get("tg_token", "")
        child_config["telegram"]["api"]["token"] = child_tg_token
        child_config["telegram"]["api"]["proxy"] = ""
        child_config["telegram"]["bot"]["password"] = config["password"]
        child_config["telegram"]["bot"]["signed_users"] = config.get("authorized_ids") or [config["owner_tg_id"]]
        child_config["telegram"]["master"]["token"] = ""
        child_config["telegram"]["master"]["owner_id"] = config["owner_tg_id"]
        child_config["telegram"]["master"]["modules_owned"] = [
            item for item in (config.get("modules_owned") or []) if item not in REMOVED_MODULES
        ]
        child_config["bot_description"] = config.get("bot_description", "Автоматизация магазина Playerok/FunPay.")
        child_config["bot_short_description"] = config.get("bot_short_description", "Raidex Assist")
        child_config["link_buttons"] = config.get("link_buttons", [])
        child_config["runtime"] = {
            "platforms": [p for p in config.get("platforms", []) if p in {"playerok", "funpay"}]
        }
        child_config["runtime"]["pl_tg_token"] = config.get("pl_tg_token", "")
        child_config["runtime"]["fp_tg_token"] = config.get("fp_tg_token", "")
        if "funpay" not in child_config:
            child_config["funpay"] = {"api": {"golden_key": "", "user_agent": "", "proxy": ""}}
        if "api" not in child_config["funpay"]:
            child_config["funpay"]["api"] = {"golden_key": "", "user_agent": "", "proxy": ""}
        child_config["funpay"]["api"].setdefault("requests_timeout", 30)
        child_config["funpay"]["api"].setdefault("runner_requests_delay", 4)
        child_config["funpay"]["api"]["golden_key"] = config.get("fp_golden_key", "")
        child_config["funpay"]["api"]["user_agent"] = config.get("fp_user_agent", "")
        child_config["funpay"]["api"]["proxy"] = config.get("fp_proxy", "")

        with open(config_path, "w", encoding="utf-8") as file:
            json.dump(child_config, file, ensure_ascii=False, indent=4)

        defaults = {
            "messages.json": sett.get("messages"),
            "custom_commands.json": sett.get("custom_commands"),
            "auto_deliveries.json": sett.get("auto_deliveries"),
            "auto_restore_items.json": sett.get("auto_restore_items"),
            "auto_bump_items.json": sett.get("auto_bump_items"),
            "initialized_users.json": [],
            "saved_items.json": [],
            "categories_raise_time.json": {},
            "latest_events_times.json": {"auto_bump_items": None, "auto_withdrawal": None, "create_tickets": None},
            "events_log.json": [],
        }
        for name, payload in defaults.items():
            settings_names = {"messages.json", "custom_commands.json", "auto_deliveries.json", "auto_restore_items.json", "auto_bump_items.json"}
            folder = "bot_settings" if name in settings_names else "bot_data"
            file_path = os.path.join(root, folder, name)
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(payload, file, ensure_ascii=False, indent=4)

        # Per-bot customizable messages file requested by master constructor UI.
        root_messages_path = os.path.join(root, "messages.json")
        if not os.path.exists(root_messages_path):
            with open(root_messages_path, "w", encoding="utf-8") as file:
                json.dump(sett.get("messages"), file, ensure_ascii=False, indent=4)

    def try_switch_proxy(self, uuid_value: str) -> str | None:
        bot = self.get(uuid_value)
        if not bot:
            return None
        proxy_list = [proxy for proxy in bot.get("proxy_list", []) if proxy]
        if not proxy_list:
            return None
        current_index = int(bot.get("proxy_index", 0))
        for step in range(1, len(proxy_list) + 1):
            next_index = (current_index + step) % len(proxy_list)
            candidate = proxy_list[next_index]
            if is_proxy_valid(candidate) and is_proxy_working(candidate):
                self.update(uuid_value, proxy=candidate, proxy_index=next_index)
                return candidate
        return None

    def add_proxy(self, uuid_value: str, proxy: str) -> bool:
        if not is_proxy_valid(proxy):
            return False
        bot = self.get(uuid_value)
        if not bot:
            return False
        proxy_list = [item for item in bot.get("proxy_list", []) if item]
        if proxy in proxy_list:
            return True
        proxy_list.append(proxy)
        if not bot.get("proxy"):
            self.update(uuid_value, proxy=proxy, proxy_list=proxy_list, proxy_index=0)
        else:
            self.update(uuid_value, proxy_list=proxy_list)
        return True

    def remove_proxy(self, uuid_value: str, index: int) -> bool:
        bot = self.get(uuid_value)
        if not bot:
            return False
        proxy_list = [item for item in bot.get("proxy_list", []) if item]
        if not (0 <= index < len(proxy_list)):
            return False
        removed = proxy_list.pop(index)
        proxy = bot.get("proxy", "")
        proxy_index = int(bot.get("proxy_index", 0))
        if removed == proxy:
            if proxy_list:
                proxy_index = min(proxy_index, len(proxy_list) - 1)
                proxy = proxy_list[proxy_index]
            else:
                proxy_index = 0
                proxy = ""
        self.update(uuid_value, proxy_list=proxy_list, proxy=proxy, proxy_index=proxy_index)
        return True

    def get_platforms(self, uuid_value: str) -> list[str]:
        bot = self.get(uuid_value)
        if not bot:
            return []
        return [item for item in bot.get("platforms", []) if item in {"playerok", "funpay"}]

    def attach_funpay(
        self,
        uuid_value: str,
        golden_key: str,
        fp_tg_token: str = "",
        ua: str = "",
        proxy: str = "",
    ) -> bool:
        bot = self.get(uuid_value)
        if not bot:
            return False
        platforms = self.get_platforms(uuid_value)
        if "funpay" not in platforms:
            platforms.append("funpay")
        self.update(
            uuid_value,
            platforms=platforms,
            fp_tg_token=fp_tg_token or bot.get("fp_tg_token", ""),
            fp_golden_key=golden_key,
            fp_user_agent=ua,
            fp_proxy=proxy,
            fp_is_active=bool(golden_key),
        )
        return True

    def detach_funpay(self, uuid_value: str) -> bool:
        bot = self.get(uuid_value)
        if not bot:
            return False
        platforms = [item for item in self.get_platforms(uuid_value) if item != "funpay"]
        self.update(
            uuid_value,
            platforms=platforms,
            fp_tg_token="",
            fp_golden_key="",
            fp_user_agent="",
            fp_proxy="",
            fp_is_active=False,
        )
        return True

    def attach_playerok(
        self,
        uuid_value: str,
        pl_token: str,
        pl_tg_token: str = "",
        ua: str = "",
        proxy: str = "",
    ) -> bool:
        bot = self.get(uuid_value)
        if not bot:
            return False
        platforms = self.get_platforms(uuid_value)
        if "playerok" not in platforms:
            platforms.append("playerok")
        self.update(
            uuid_value,
            platforms=platforms,
            pl_tg_token=pl_tg_token or bot.get("pl_tg_token", ""),
            pl_token=pl_token,
            pl_user_agent=ua,
            pl_proxy=proxy,
            pl_is_active=bool(pl_token),
        )
        return True

    def detach_playerok(self, uuid_value: str) -> bool:
        bot = self.get(uuid_value)
        if not bot:
            return False
        platforms = [item for item in self.get_platforms(uuid_value) if item != "playerok"]
        self.update(
            uuid_value,
            platforms=platforms,
            pl_tg_token="",
            pl_token="",
            pl_user_agent="",
            pl_proxy="",
            pl_is_active=False,
        )
        return True

    def load_events(self, uuid_value: str) -> list[dict]:
        return _read_json(self.child_events_path(uuid_value), [])

    def get_recent_events(self, uuid_value: str, limit: int = 20) -> list[dict]:
        events = self.load_events(uuid_value)
        return events[-limit:]

    def get_hourly_analytics(self, uuid_value: str, days: int = 1) -> dict[int, dict[str, int]]:
        events = self.load_events(uuid_value)
        border = datetime.now() - timedelta(days=days)
        stats = {hour: {"deals": 0, "messages": 0} for hour in range(24)}
        for event in events:
            try:
                ts = datetime.fromisoformat(event["at"])
            except Exception:
                continue
            if ts < border:
                continue
            if event.get("type") == "deal":
                stats[ts.hour]["deals"] += 1
            elif event.get("type") == "message":
                stats[ts.hour]["messages"] += 1
        return stats

    def get_top_items(self, uuid_value: str, days: int = 30, limit: int = 5) -> list[dict]:
        events = self.load_events(uuid_value)
        border = datetime.now() - timedelta(days=days)
        grouped: dict[str, dict] = {}
        for event in events:
            try:
                ts = datetime.fromisoformat(event["at"])
            except Exception:
                continue
            if ts < border or event.get("type") != "deal":
                continue
            item_name = event.get("item_name") or "-"
            row = grouped.setdefault(item_name, {"item_name": item_name, "deals": 0, "revenue": 0.0})
            row["deals"] += 1
            row["revenue"] += float(event.get("price") or 0)
        rows = sorted(grouped.values(), key=lambda item: item["deals"], reverse=True)
        return rows[:limit]

