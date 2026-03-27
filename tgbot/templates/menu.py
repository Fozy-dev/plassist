import textwrap

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from __init__ import VERSION
from settings import Settings as sett

from .. import callback_datas as calls

DEFAULT_CHANNEL_URL = "https://t.me/RaidexAssist"
DEFAULT_BOT_URL = "https://t.me/RaidexAssist_bot"


def _normalize_tg_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        return ""
    if url.startswith("@"):
        return f"https://t.me/{url[1:]}"
    if url.startswith("t.me/"):
        return f"https://{url}"
    return url


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
    if has_pl and not has_fp:
        return "playerok"
    return "mixed"


def menu_text(current_bot_token: str | None = None):
    platform = _resolve_platform(current_bot_token)
    if platform == "funpay":
        title = "FunPay Universal"
    elif platform == "playerok":
        title = "Playerok Universal"
    else:
        title = "Raidex Universal"

    txt = textwrap.dedent(
        f"""
        <b>🏠 Главное меню</b>

        <b>{title}</b> v{VERSION}
        Бот-помощник для магазина
        """
    )
    return txt


def menu_kb():
    cfg = sett.get("config")
    link_buttons = list(cfg.get("link_buttons") or [])
    if not link_buttons:
        link_buttons = [
            {"text": "📢 Наш канал", "url": DEFAULT_CHANNEL_URL},
            {"text": "🤖 Наш бот", "url": DEFAULT_BOT_URL},
        ]

    link_row = []
    for row in link_buttons[:3]:
        text = str(row.get("text") or "Ссылка")
        lowered = text.lower()
        if "наш бот" in lowered:
            url = DEFAULT_BOT_URL
        elif "наш канал" in lowered:
            url = DEFAULT_CHANNEL_URL
        else:
            url = _normalize_tg_url(str(row.get("url") or ""))
        if url:
            link_row.append(InlineKeyboardButton(text=text, url=url))

    rows = [
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=calls.SettingsNavigation(to="default").pack()),
            InlineKeyboardButton(text="👤 Профиль", callback_data=calls.MenuNavigation(to="profile").pack()),
        ],
        [
            InlineKeyboardButton(text="🚩 Ивенты", callback_data=calls.MenuNavigation(to="events").pack()),
            InlineKeyboardButton(text="🗒️ Логи", callback_data=calls.MenuNavigation(to="logs").pack()),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data=calls.MenuNavigation(to="stats").pack()),
            InlineKeyboardButton(text="🔌 Модули", callback_data=calls.ModulesPagination(page=0).pack()),
        ],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data=calls.InstructionNavigation(to="default").pack())],
    ]
    if link_row:
        rows.append(link_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
