from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, InlineKeyboardMarkup
from colorama import Fore

from core.handlers import call_bot_event
from core.modules import get_modules
from core.text_normalizer import install_aiogram_text_patches
from settings import Settings as sett

from . import router as main_router
from . import templates as templ


logger = logging.getLogger("universal.telegram")
_telegram_bot_instance: "TelegramBot | None" = None


def get_telegram_bot() -> "TelegramBot | None":
    return _telegram_bot_instance


def get_telegram_bot_loop() -> asyncio.AbstractEventLoop | None:
    bot = get_telegram_bot()
    return getattr(bot, "loop", None) if bot else None


class TelegramBot:
    def __init__(self, tokens: list[str] | None = None):
        global _telegram_bot_instance
        _telegram_bot_instance = self

        logging.getLogger("aiogram").setLevel(logging.CRITICAL)
        logging.getLogger("aiogram.event").setLevel(logging.CRITICAL)
        logging.getLogger("aiogram.dispatcher").setLevel(logging.CRITICAL)

        self.config = sett.get("config")
        self.proxy = self.config["telegram"]["api"]["proxy"]
        default_token = self.config["telegram"]["api"]["token"]

        if tokens is None:
            tokens = [default_token] if default_token else []
        self.tokens = [token for token in tokens if token]
        if not self.tokens and default_token:
            self.tokens = [default_token]
        if not self.tokens:
            raise ValueError("No Telegram bot token configured for child runtime")

        if self.proxy:
            session = AiohttpSession(proxy=f"http://{self.proxy}")
        else:
            session = None

        self.bots = [Bot(token=token, session=session) for token in self.tokens]
        install_aiogram_text_patches()
        # Keep backward compatibility for existing code paths.
        self.bot = self.bots[0]
        self.dp = Dispatcher()

        for module in get_modules():
            for router in module.telegram_bot_routers:
                main_router.include_router(router)
        self.dp.include_router(main_router)

    async def _set_main_menu(self, bot: Bot):
        try:
            main_menu_commands = [BotCommand(command="/start", description="🏠 Главное меню")]
            await bot.set_my_commands(main_menu_commands)
        except Exception:
            pass
    async def _set_description(self, bot: Bot):
        try:
            description = "Создано спомощью @RaidexAssist_bot"
            await bot.set_my_description(description=description)
        except Exception:
            pass

    async def run_bot(self):
        self.loop = asyncio.get_running_loop()

        for bot in self.bots:
            await self._set_main_menu(bot)
            await self._set_description(bot)

        await call_bot_event("ON_TELEGRAM_BOT_INIT", [self])

        logger.info("")
        for bot in self.bots:
            me = await bot.get_me()
            logger.info(f"{Fore.LIGHTBLUE_EX}Telegram бот {Fore.LIGHTWHITE_EX}@{me.username} {Fore.LIGHTBLUE_EX}запущен и активен")
        logger.info("")

        if self.proxy:
            if "@" in self.proxy:
                user, password = self.proxy.split("@")[0].split(":")
                ip, port = self.proxy.split("@")[1].split(":")
            else:
                user, password = None, None
                ip, port = self.proxy.split(":")

            ip = ".".join([("*" * len(nums)) if i >= 3 else nums for i, nums in enumerate(ip.split("."), start=1)])
            port = f"{port[:3]}**"
            user = f"{user[:3]}*****" if user else "-"
            password = f"{password[:3]}*****" if password else "-"

            logger.info(f"{Fore.LIGHTBLUE_EX}{'?' * 40}")
            logger.info(f"{Fore.LIGHTBLUE_EX}Информация о прокси:")
            logger.info(f" В· IP: {Fore.LIGHTWHITE_EX}{ip}:{port}")
            logger.info(f" · Юзер: {Fore.LIGHTWHITE_EX}{user}")
            logger.info(f" · Пароль: {Fore.LIGHTWHITE_EX}{password}")
            logger.info(f"{Fore.LIGHTBLUE_EX}{'?' * 40}")

        while True:
            try:
                await self.dp.start_polling(*self.bots, skip_updates=True, handle_signals=False)
            except Exception:
                pass

    async def call_seller(self, calling_name: str, chat_id: int | str):
        config = sett.get("config")
        for user_id in config["telegram"]["bot"]["signed_users"]:
            await self.bot.send_message(
                chat_id=user_id,
                text=templ.call_seller_text(calling_name, f"https://playerok.com/chats/{chat_id}"),
                reply_markup=templ.destroy_kb(),
                parse_mode="HTML",
            )

    async def log_event(self, text: str, kb: InlineKeyboardMarkup | None = None):
        config = sett.get("config")
        chat_id = config["playerok"]["tg_logging"]["chat_id"]
        if not chat_id:
            for user_id in config["telegram"]["bot"]["signed_users"]:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML",
                )
        else:
            await self.bot.send_message(
                chat_id=chat_id,
                text=f'{text}\n<span class="tg-spoiler">Переключите чат логов на чат с ботом, чтобы отображалось меню с действиями</span>',
                reply_markup=None,
                parse_mode="HTML",
            )


