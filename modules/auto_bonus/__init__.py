from .meta import AUTHORS, DESCRIPTION, LINKS, NAME, PREFIX, PRICE, VERSION
from .settings import Settings
from .tgbot.handlers import BOT_EVENT_HANDLERS, router as telegram_router
from .plbot.handlers import PLAYEROK_EVENT_HANDLERS
from .fpbot.handlers import FUNPAY_EVENT_HANDLERS

TELEGRAM_BOT_ROUTERS = [telegram_router]

import os

if os.environ.get("PLAYEROK_BOT_ROOT"):
    Settings.get("auto_bonus")
