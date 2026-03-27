import importlib
import math
import textwrap

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.modules import get_modules
from settings import Settings as sett

from .. import callback_datas as calls


def _resolve_platform(current_bot_token: str | None = None) -> str:
    cfg = sett.get("config")
    runtime = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    pl_token = runtime.get("pl_tg_token") or ""
    fp_token = runtime.get("fp_tg_token") or ""

    token = current_bot_token or ""
    if token and fp_token and token == fp_token:
        return "funpay"
    if token and pl_token and token == pl_token:
        return "playerok"

    has_pl = bool(cfg.get("playerok", {}).get("api", {}).get("token"))
    has_fp = bool(cfg.get("funpay", {}).get("api", {}).get("golden_key"))
    if has_fp and not has_pl:
        return "funpay"
    return "playerok"


def _load_messages_module(current_bot_token: str | None = None):
    platform = _resolve_platform(current_bot_token)
    module = importlib.import_module(f"messages.{platform}")
    return importlib.reload(module)


def modules_text(current_bot_token: str | None = None):
    modules = get_modules()
    return textwrap.dedent(
        """
        🔌 Магазин модулей Raidex

        Расширяй возможности своих ботов с помощью модулей.
        Каждый модуль подключается ко всем твоим ботам сразу
        и настраивается прямо через Telegram.

        Выбери модуль для подробной информации:
        """
    ).strip()


def modules_kb(page: int = 0, current_bot_token: str | None = None):
    modules = get_modules()
    module = _load_messages_module(current_bot_token)
    back_text = getattr(module, "BTN_BACK_MODULES_TEXT", "⬅️ Назад")

    rows = []
    items_per_page = 7
    total_pages = math.ceil(len(modules) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page

    for mod in list(modules)[start_offset:end_offset]:
        rows.append([InlineKeyboardButton(text=f"⚡ {mod.meta.name}" if mod.meta.name == "AutoBonus" else mod.meta.name, callback_data=calls.ModulePage(uuid=mod.uuid).pack())])

    if total_pages > 1:
        buttons_row = []
        btn_back = (
            InlineKeyboardButton(text="←", callback_data=calls.ModulesPagination(page=page - 1).pack())
            if page > 0
            else InlineKeyboardButton(text="🛑", callback_data="123")
        )
        buttons_row.append(btn_back)

        btn_pages = InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="enter_modules_page")
        buttons_row.append(btn_pages)

        btn_next = (
            InlineKeyboardButton(text="→", callback_data=calls.ModulesPagination(page=page + 1).pack())
            if page < total_pages - 1
            else InlineKeyboardButton(text="🛑", callback_data="123")
        )
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([InlineKeyboardButton(text=back_text, callback_data=calls.MenuNavigation(to="default").pack())])

    return InlineKeyboardMarkup(inline_keyboard=rows)
