from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.types import BotCommand, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.child_manager import ChildBotManager
from core.partners_manager import PartnersManager
from core.modules import load_modules, set_modules
from core.text_normalizer import install_aiogram_text_patches
from core.user_manager import TARIFFS, UserManager
from settings import Settings as sett
from tgbot.callback_handlers.constructor import router as constructor_router
from tgbot.handlers.states_admin import router as admin_states_router
from tgbot.handlers.states_create_bot import router as create_bot_router
from tgbot.master_context import set_manager, set_partners_manager, set_user_manager
from tgbot.master_helpers import render_message
from tgbot.templates.constructor import (
    get_admin_panel_kb,
    get_admin_panel_text,
    get_main_menu_kb,
    get_main_menu_text,
)


logger = logging.getLogger("universal.master")


class MasterBot:
    def __init__(self, manager: ChildBotManager, user_manager: UserManager):
        config = sett.get("config")
        self.token = config["telegram"]["master"]["token"]
        self.manager = manager
        self.user_manager = user_manager
        self.partners_manager = PartnersManager()
        modules = load_modules()
        set_modules(modules)
        session = AiohttpSession()
        session._connector_init["family"] = socket.AF_INET
        self.bot = Bot(token=self.token, session=session)
        install_aiogram_text_patches()
        self.dp = Dispatcher()
        self.router = Router()
        self.router.include_router(constructor_router)
        self.router.include_router(admin_states_router)
        self.router.include_router(create_bot_router)
        self.router.message.register(self.handle_start, Command("start"))
        self.router.message.register(self.handle_start_system, F.text.casefold() == "start.bot")
        self.router.message.register(self.handle_admin, Command("admin"))
        self.router.message.register(self.handle_partner_link, F.text.startswith("/"))
        self.dp.include_router(self.router)
        set_manager(manager)
        set_user_manager(user_manager)
        set_partners_manager(self.partners_manager)
        self.manager.attach_master_bot(self.bot)

    async def _set_main_menu(self):
        try:
            await self.bot.set_my_commands([BotCommand(command="/start", description="Главное меню")])
        except Exception as e:
            logger.warning("Failed to set commands: %s", e)

    def _ensure_admin(self, message: Message) -> bool:
        config = sett.get("config")
        admins = config["telegram"]["master"].get("admins", [])
        if not admins:
            config["telegram"]["master"]["admins"] = [message.from_user.id]
            sett.set("config", config)
            return True
        if message.from_user.id in admins:
            return True

        partner = self._partner_by_tg_id(message.from_user.id)
        if partner:
            self._grant_partner_limited_admin(message.from_user.id, partner.get("username"))
            return True
        return False

    def _partner_by_tg_id(self, tg_id: int) -> dict | None:
        try:
            for partner in self.partners_manager.all_partners():
                if int(partner.get("tg_id") or 0) == int(tg_id):
                    return partner
        except Exception:
            return None
        return None

    def _admin_level(self, tg_id: int) -> str:
        # ??????? ?????? ???????? ???????????? ?????-??????.
        if self._partner_by_tg_id(tg_id):
            self._grant_partner_limited_admin(tg_id)
            return "limited"
        user = self.user_manager.get_user(tg_id) or {}
        return (user.get("admin_level") or "full").lower()


    def _grant_partner_limited_admin(self, tg_id: int, username: str | None = None):
        config = sett.get("config")
        master = config.setdefault("telegram", {}).setdefault("master", {})
        admins = list(master.get("admins") or [])
        if int(tg_id) not in admins:
            admins.append(int(tg_id))
            master["admins"] = admins
            sett.set("config", config)

        user = self.user_manager.get_user(int(tg_id))
        if not user:
            self.user_manager.ensure_user(int(tg_id), (username or "").lstrip("@") or None, "")
            user = self.user_manager.get_user(int(tg_id)) or {}
        # Явный full не понижаем автоматически.
        if (user.get("admin_level") or "").lower() != "full":
            self.user_manager.update_user(int(tg_id), admin_level="limited")

    def is_admin(self, tg_id: int) -> bool:
        config = sett.get("config")
        admins = config["telegram"]["master"].get("admins", [])
        if tg_id in admins:
            return True
        partner = self._partner_by_tg_id(tg_id)
        if partner:
            self._grant_partner_limited_admin(tg_id, partner.get("username"))
            return True
        return False

    async def _check_user_access(self, message: Message) -> bool:
        self._ensure_admin(message)
        user = self.user_manager.ensure_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        system = self.user_manager.get_system()
        if user.get("is_banned"):
            await message.answer(
                "Доступ ограничен.\n"
                "Ваш аккаунт заблокирован.\n"
                "По вопросам обращайтесь к администратору."
            )
            return False
        if system.get("maintenance_mode") and not self.is_admin(message.from_user.id):
            await message.answer(system.get("maintenance_text"))
            return False
        return True

    async def _register_referral(self, message: Message):
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return
        payload = parts[1].strip()
        await self._try_bind_referral(message, payload)

    async def _try_bind_referral(self, message: Message, payload: str):
        payload = (payload or "").strip()
        if not payload:
            return

        user = self.user_manager.get_user(message.from_user.id)
        if not user or user.get("referred_partner_id"):
            return

        # Реферал считается только при первой регистрации (первом входе).
        registered_at = user.get("registered_at")
        last_active = user.get("last_active")
        if not registered_at or not last_active or registered_at != last_active:
            return

        partner = self.partners_manager.get_by_slug(payload)
        if not partner:
            return

        # Запрет самореферала по TG ID и username.
        partner_tg_id = partner.get("tg_id")
        if partner_tg_id is not None and int(partner_tg_id) == int(message.from_user.id):
            return
        partner_username = (partner.get("username") or "").lstrip("@").lower()
        author_username = (message.from_user.username or "").lstrip("@").lower()
        if partner_username and author_username and partner_username == author_username:
            return

        bound = self.partners_manager.bind_user(payload, user)
        if not bound:
            return
        self.user_manager.update_user(
            message.from_user.id,
            referred_partner_id=bound["id"],
            referred_partner_slug=bound.get("slug"),
            referred_at=datetime.now().isoformat(timespec="seconds"),
        )

    async def handle_start(self, message: Message):
        if not await self._check_user_access(message):
            return
        await self._register_referral(message)
        # Для администратора /start также действует как мягкий запуск системы.
        if self.is_admin(message.from_user.id):
            try:
                await self.manager.autostart()
            except Exception as e:
                logger.warning("Autostart from /start failed: %s", e)
        user = self.user_manager.get_user(message.from_user.id)

        payload = ((message.text or "").split(maxsplit=1)[1].strip().lower() if " " in (message.text or "") else "")
        if payload == "modules_shop":
            text = (
                "🔌 Модули\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Платные модули временно недоступны.\n"
                "Вся информация по плагинам у поддержки: @RaidexHelp_bot"
            )
            kb = InlineKeyboardBuilder()
            kb.button(text="⬅️ Главное меню", callback_data="back_to_main")
            kb.adjust(1)
            return await render_message(message, text, kb.as_markup())

        bots = self.manager.get_all(message.from_user.id)
        await render_message(
            message,
            get_main_menu_text(message.from_user, bots, float(user["balance"]), user),
            get_main_menu_kb(user),
        )

    async def handle_partner_link(self, message: Message):
        command = ((message.text or "").strip().split(maxsplit=1)[0]).lstrip("/")
        if command in {"start", "admin", "start.bot"}:
            return
        if not await self._check_user_access(message):
            return
        await self._try_bind_referral(message, command)
        user = self.user_manager.get_user(message.from_user.id)
        bots = self.manager.get_all(message.from_user.id)
        await render_message(
            message,
            get_main_menu_text(message.from_user, bots, float(user["balance"]), user),
            get_main_menu_kb(user),
        )

    async def handle_start_system(self, message: Message):
        if not self._ensure_admin(message):
            return await message.answer("Команда доступна только администратору.")

        system = self.user_manager.get_system()
        if system.get("maintenance_mode"):
            self.user_manager.set_system(
                maintenance_mode=False,
                maintenance_started_at=None,
                maintenance_resume_uuids=[],
            )

        bots = self.manager.load_all_bots()
        started = 0
        for bot in bots:
            try:
                ok = await self.manager.start(bot["uuid"])
                if ok:
                    started += 1
            except Exception as e:
                logger.error("Failed to start child bot %s: %s", bot.get("uuid"), e)

        await message.answer(
            "SYSTEM START\n"
            f"Запущено дочерних ботов: {started}/{len(bots)}\n"
            "Мастер-бот активен."
        )
    async def handle_admin(self, message: Message):
        if not self._ensure_admin(message):
            return await message.answer("Команда доступна только администратору.")

        users = self.user_manager.all_users()
        admin_level = self._admin_level(message.from_user.id)
        active_tariffs = sum(1 for item in users.values() if self.user_manager.has_active_tariff(int(item["tg_id"])))
        bots_count = len(self.manager.load_all_bots())
        maintenance_mode = bool(self.user_manager.get_system().get("maintenance_mode"))

        await message.answer(
            get_admin_panel_text(
                users_count=len(users),
                active_tariffs=active_tariffs,
                bots_count=bots_count,
                maintenance_mode=maintenance_mode,
            ),
            reply_markup=get_admin_panel_kb(maintenance_mode, admin_level=admin_level),
            parse_mode="HTML",
        )


    async def _tariff_watchdog(self):
        while True:
            await asyncio.sleep(3600)
            users = self.user_manager.all_users()
            for user in users.values():
                tariff_key = user.get("tariff")
                expires = user.get("tariff_expires")
                if not tariff_key or not expires:
                    continue
                expires_dt = datetime.fromisoformat(expires)
                hours_left = (expires_dt - datetime.now()).total_seconds() / 3600
                if hours_left <= 0:
                    if user.get("auto_renew") and float(user.get("balance", 0)) >= TARIFFS[tariff_key]["price"]:
                        updated = self.user_manager.activate_tariff(int(user["tg_id"]), tariff_key, charge=True)
                        if updated.get("referred_partner_id"):
                            self.partners_manager.register_payment(
                                updated["referred_partner_id"],
                                updated,
                                TARIFFS[tariff_key]["price"],
                            )
                        await self.bot.send_message(
                            int(user["tg_id"]),
                            "Тариф продлён автоматически.\n"
                            f"Тариф: {TARIFFS[tariff_key]['title']}\n"
                            f"Списано: {TARIFFS[tariff_key]['price']:.0f} ₽\n"
                            f"Новый баланс: {updated['balance']:.2f} ₽",
                        )
                    else:
                        for bot in self.manager.get_all(int(user["tg_id"])):
                            await self.manager.stop(bot["uuid"])
                        self.user_manager.update_user(int(user["tg_id"]), tariff=None, tariff_expires=None)
                        await self.bot.send_message(
                            int(user["tg_id"]),
                            "Тариф истёк.\n"
                            "Все ваши боты остановлены. Активируйте тариф для возобновления работы.",
                        )
                elif hours_left <= 24 and user.get("auto_renew") and float(user.get("balance", 0)) < TARIFFS[tariff_key]["price"]:
                    await self.bot.send_message(
                        int(user["tg_id"]),
                        "Автопродление не выполнено: недостаточно баланса.\n"
                        f"Требуется: {TARIFFS[tariff_key]['price']:.0f} ₽",
                    )

    async def run(self):
        await self._set_main_menu()
        try:
            await self.bot.delete_webhook(drop_pending_updates=False)
        except Exception as e:
            logger.warning("Failed to delete webhook: %s", e)
        asyncio.create_task(self._tariff_watchdog())
        try:
            me = await self.bot.get_me()
            config = sett.get("config")
            config["telegram"]["master"]["username"] = me.username
            sett.set("config", config)
            logger.info("Master bot @%s started", me.username)
        except Exception as e:
            logger.warning("Failed to fetch bot profile before polling: %s", e)
            logger.info("Master bot started (profile unknown)")
        await self.dp.start_polling(self.bot, skip_updates=True, handle_signals=False)

