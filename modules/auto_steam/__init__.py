from .fpbot.handlers import FUNPAY_EVENT_HANDLERS
from .meta import AUTHORS, DESCRIPTION, LINKS, NAME, PREFIX, PRICE, VERSION
from .settings import Settings
from .tgbot.handlers import BOT_EVENT_HANDLERS, router as telegram_router

PLAYEROK_EVENT_HANDLERS = {}
TELEGRAM_BOT_ROUTERS = [telegram_router]

import os

if os.environ.get("PLAYEROK_BOT_ROOT"):
    Settings.get("auto_steam")

__all__ = ["AUTHORS", "BOT_EVENT_HANDLERS", "DESCRIPTION", "FUNPAY_EVENT_HANDLERS", "LINKS", "NAME", "PLAYEROK_EVENT_HANDLERS", "PREFIX", "PRICE", "TELEGRAM_BOT_ROUTERS", "VERSION"]
