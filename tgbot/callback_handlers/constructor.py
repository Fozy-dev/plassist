from __future__ import annotations

import csv
import io
import json
import math
import os
import secrets
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.admin_transfer_pay import AdminTransferLedger
from core.cryptobot_pay import CryptoBotClient, CryptoBotError, CryptoLedger
from core.cryptomus_pay import CryptomusClient, CryptomusError, CryptomusLedger
from core.freekassa import FreeKassaClient, FreeKassaError, PaymentLedger
from core.lava_pay import LavaClient, LavaError, LavaLedger
from core.telegram_stars_pay import TelegramStarsLedger
from messages import master as master_messages
from messages.master import LINK_CHANNEL_URL
from tgbot.callback_datas.constructor import ConfirmDelete, ManageBot, SelectBot, SkipStep
from tgbot.master_context import get_manager, get_partners_manager, get_user_manager
from tgbot.master_helpers import render_message
from tgbot.states.all import (
    AccountSettingsStates,
    AdminStates,
    CreateBotStates,
    CustomizationStates,
    PaymentStates,
    ProxyStates,
    UpdateTokenStates,
)
from tgbot.templates.constructor import (
    get_admin_panel_kb,
    get_admin_panel_text,
    get_analytics_menu_kb,
    get_cancel_kb,
    get_back_menu_kb,
    get_bot_card_kb,
    get_bot_card_text,
    get_create_bot_intro_kb,
    get_create_bot_intro_text,
    get_delete_confirm_kb,
    get_delete_confirm_text,
    get_help_text,
    get_info_menu_kb,
    get_feedback_text,
    get_main_menu_kb,
    get_main_menu_text,
    get_my_bots_kb,
    get_my_bots_text,
    get_need_tariff_kb,
    get_need_tariff_text,
    get_platforms_pick_kb,
    get_platforms_pick_text,
    get_stats_menu_text,
    get_step_text,
    get_success_kb,
    get_success_text,
    get_skip_kb,
    get_tariff_confirm_kb,
    get_tariff_confirm_text,
    get_tariff_menu_kb,
    get_tariff_menu_text,
)
from core.user_manager import TARIFFS, tariff_title_ru
from settings import Settings as sett


router = Router()
# Telegram Bot API does not support custom button styles for regular inline keyboards.
# Passing `style` causes `Bad Request: invalid button style specified`.
_BTN_STYLE_SUPPORTED = False
TRIAL_CHANNEL_ID = 3262370516
TRIAL_SUBSCRIBED_STATUSES = {"member", "administrator", "creator"}
ADMIN_GRANTABLE_MODULES = {
    "auto_refund": "AutoRefund",
    "auto_stars": "AutoStars",
    "auto_steam": "AutoSteam",
    "auto_smm": "AutoSMM",
    "gpt_review": "GPT Review",
    "seller_gpt": "Seller GPT",
}


def _master_msg(name: str, default: str = "") -> str:
    return str(getattr(master_messages, name, default))


def _master_render(name: str, default: str = "", **kwargs) -> str:
    template = _master_msg(name, default)
    try:
        return template.format(**kwargs) if kwargs else template
    except Exception:
        return template


def _kb_button(kb: InlineKeyboardBuilder, *, text: str, callback_data: str | None = None, url: str | None = None, style: str | None = None):
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style and _BTN_STYLE_SUPPORTED:
        kwargs["style"] = style
    kb.button(**kwargs)


def _admin_back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def _trial_subscribe_kb():
    kb = InlineKeyboardBuilder()
    _kb_button(kb, text="📢 Подписаться", url=LINK_CHANNEL_URL, style="primary")
    _kb_button(kb, text="⬅️ Главное меню", callback_data="back_to_main")
    kb.adjust(1)
    return kb.as_markup()


async def _is_trial_channel_subscribed(callback: CallbackQuery) -> bool:
    user_id = int(callback.from_user.id)
    channel_candidates = [TRIAL_CHANNEL_ID, int(f"-100{TRIAL_CHANNEL_ID}")]
    for channel_id in channel_candidates:
        try:
            member = await callback.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in TRIAL_SUBSCRIBED_STATUSES:
                return True
            if member.status in {"left", "kicked"}:
                return False
            return False
        except Exception:
            continue
    return False


def _generate_system_password() -> str:
    return secrets.token_urlsafe(18)


def _owned_bot(user_id: int, bot: dict | None) -> dict | None:
    if not bot or bot["owner_tg_id"] != user_id:
        return None
    return bot


def _child_root(uuid_value: str) -> str:
    return os.path.join("bot_data", "bots", uuid_value)


def _load_child_config(uuid_value: str) -> dict:
    path = os.path.join(_child_root(uuid_value), "bot_settings", "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_child_config(uuid_value: str, payload: dict):
    path = os.path.join(_child_root(uuid_value), "bot_settings", "config.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


def _load_child_messages(uuid_value: str) -> dict:
    path = os.path.join(_child_root(uuid_value), "messages.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_child_messages(uuid_value: str, payload: dict):
    path = os.path.join(_child_root(uuid_value), "messages.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


def _set_child_autobonus_enabled(uuid_value: str, enabled: bool):
    path = os.path.join(_child_root(uuid_value), "bot_data", "auto_bonus.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "enabled": False,
        "messages": {},
        "bonuses": [],
        "sent_deals": [],
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
            if isinstance(existing, dict):
                payload.update(existing)
    except Exception:
        pass
    payload["enabled"] = bool(enabled)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


async def _ensure_user_available(callback: CallbackQuery) -> bool:
    user_manager = get_user_manager()
    user = user_manager.ensure_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    system = user_manager.get_system()
    if user.get("is_banned"):
        await callback.answer(_master_msg("ALERT_ACCOUNT_BANNED", "Ваш аккаунт заблокирован."), show_alert=True)
        return False
    if system.get("maintenance_mode"):
        from settings import Settings as sett
        admins = sett.get("config")["telegram"]["master"].get("admins", [])
        if callback.from_user.id not in admins:
            await callback.answer(_master_msg("ALERT_MAINTENANCE", "Бот временно недоступен из-за техработ."), show_alert=True)
            return False
    return True


def _is_admin_user(tg_id: int) -> bool:
    from settings import Settings as sett
    admins = sett.get("config")["telegram"]["master"].get("admins", [])
    if tg_id in admins:
        return True
    try:
        for partner in get_partners_manager().all_partners():
            if int(partner.get("tg_id") or 0) == int(tg_id):
                config = sett.get("config")
                master = config.setdefault("telegram", {}).setdefault("master", {})
                new_admins = list(master.get("admins") or [])
                if int(tg_id) not in new_admins:
                    new_admins.append(int(tg_id))
                    master["admins"] = new_admins
                    sett.set("config", config)
                user = get_user_manager().get_user(int(tg_id))
                if user:
                    if (user.get("admin_level") or "").lower() != "full":
                        get_user_manager().update_user(int(tg_id), admin_level="limited")
                else:
                    get_user_manager().ensure_user(int(tg_id), (partner.get("username") or "").lstrip("@") or None, "")
                    get_user_manager().update_user(int(tg_id), admin_level="limited")
                return True
    except Exception:
        return False
    return False


async def _ensure_admin_callback(callback: CallbackQuery) -> bool:
    if not _is_admin_user(callback.from_user.id):
        await callback.answer(_master_msg("ALERT_ADMIN_ONLY", "Доступно только администратору."), show_alert=True)
        return False
    if _admin_level(callback.from_user.id) == "limited":
        allowed = {"admin_panel", "admin_stats", "admin_partner_my_stats", "back_to_main"}
        data = callback.data or ""
        if data not in allowed:
            # ???? ????????? ??????????? ???????? ??? limited ??? ???????????.
            await callback.answer()
            return False
    return True


async def _show_main(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    manager = get_manager()
    user_manager = get_user_manager()
    user = callback.from_user
    profile = user_manager.ensure_user(user.id, user.username, user.first_name)
    bots = manager.get_all(user.id)
    await render_message(callback, get_main_menu_text(user, bots, float(profile["balance"]), profile), get_main_menu_kb(profile))


def _master_modules_text(profile: dict, note: str = "") -> str:
    lines = _master_msg("MASTER_MODULES_TEXT", "🔌 Модули").split("\n")
    if note:
        lines.append(note)
    return "\n".join(lines)


def _master_modules_kb(profile: dict):
    kb = InlineKeyboardBuilder()
    _kb_button(kb, text="⬅️ Главное меню", callback_data="back_to_main")
    kb.adjust(1)
    return kb.as_markup()



def _freekassa_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("freekassa") or {})


def _cryptobot_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("cryptobot") or {})


def _cryptomus_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("cryptomus") or {})


def _lava_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("lava") or {})


def _telegram_stars_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("telegram_stars") or {})


def _topup_menu_text(balance: float) -> str:
    return (
        "\U0001F4B3 \u041F\u043E\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435 \u0431\u0430\u043B\u0430\u043D\u0441\u0430\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\u0422\u0435\u043A\u0443\u0449\u0438\u0439 \u0431\u0430\u043B\u0430\u043D\u0441: {balance:.2f} \u20BD\n\n"
        "\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u043F\u043E\u0441\u043E\u0431 \u043E\u043F\u043B\u0430\u0442\u044B."
    )


def _topup_methods_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="\U0001F4B0 FreeKassa", callback_data="topup_method:freekassa")
    kb.button(text="\U0001FA99 CryptoBot", callback_data="topup_method:cryptobot")
    kb.button(text="\U0001F30B LAVA", callback_data="topup_method:lava")
    kb.button(text="⭐ Telegram Stars", callback_data="topup_method:telegram_stars")
    kb.button(text="\u25C0\uFE0F \u0413\u043B\u0430\u0432\u043D\u043E\u0435 \u043C\u0435\u043D\u044E", callback_data="back_to_main")
    kb.adjust(1)
    return kb


def _topup_amounts_text(provider: str, balance: float) -> str:
    if provider == "freekassa":
        provider_label = "FreeKassa"
    elif provider == "cryptobot":
        provider_label = "CryptoBot"
    elif provider == "lava":
        provider_label = "LAVA"
    elif provider == "telegram_stars":
        provider_label = "Telegram Stars"
    elif provider == "admin_transfer":
        provider_label = "\u041F\u0435\u0440\u0435\u0432\u043E\u0434 \u0430\u0434\u043C\u0438\u043D\u0443"
    else:
        provider_label = "Cryptomus"
    return (
        f"\U0001F4B3 \u041F\u043E\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435 \u0447\u0435\u0440\u0435\u0437 {provider_label}\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\u0422\u0435\u043A\u0443\u0449\u0438\u0439 \u0431\u0430\u043B\u0430\u043D\u0441: {balance:.2f} \u20BD\n\n"
        "\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0443\u043C\u043C\u0443 \u0438\u043B\u0438 \u0432\u0432\u0435\u0434\u0438\u0442\u0435 \u0441\u0432\u043E\u044E."
    )


def _topup_amounts_kb(provider: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for amount in (100, 300, 500, 1000, 3000, 5000):
        kb.button(text=f"{amount} \u20BD", callback_data=f"topup_create:{provider}:{amount}")
    kb.button(text="\u270D\uFE0F \u0414\u0440\u0443\u0433\u0430\u044F \u0441\u0443\u043C\u043C\u0430", callback_data=f"topup_custom_amount:{provider}")
    kb.button(text="\u25C0\uFE0F \u0421\u043F\u043E\u0441\u043E\u0431\u044B \u043E\u043F\u043B\u0430\u0442\u044B", callback_data="topup_menu")
    kb.adjust(3, 3, 1, 1)
    return kb


def _topup_invoice_kb(pay_url: str, payment_id: str, provider: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    _kb_button(kb, text="\U0001F4B3 \u041E\u043F\u043B\u0430\u0442\u0438\u0442\u044C", url=pay_url, style="success")
    if provider == "freekassa":
        _kb_button(kb, text="\U0001F504 \u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u043E\u043F\u043B\u0430\u0442\u0443", callback_data=f"topup_fk_check:{payment_id}", style="primary")
    elif provider == "cryptobot":
        _kb_button(kb, text="\U0001F504 \u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u043E\u043F\u043B\u0430\u0442\u0443", callback_data=f"topup_cb_check:{payment_id}", style="primary")
    elif provider == "lava":
        _kb_button(kb, text="\U0001F504 \u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u043E\u043F\u043B\u0430\u0442\u0443", callback_data=f"topup_lv_check:{payment_id}", style="primary")
    else:
        _kb_button(kb, text="\U0001F504 \u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u043E\u043F\u043B\u0430\u0442\u0443", callback_data=f"topup_cm_check:{payment_id}", style="primary")
    _kb_button(kb, text="\u2716\uFE0F \u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C \u0441\u0447\u0451\u0442", callback_data="topup_menu")
    _kb_button(kb, text="\u25C0\uFE0F \u0413\u043B\u0430\u0432\u043D\u043E\u0435 \u043C\u0435\u043D\u044E", callback_data="back_to_main", style="danger")
    kb.adjust(1)
    return kb


def _topup_admin_transfer_kb(order_id: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    _kb_button(kb, text="✓ Я оплатил", callback_data=f"topup_admin_paid:{order_id}", style="success")
    _kb_button(kb, text="⬆️ Главное меню", callback_data="back_to_main", style="danger")
    kb.adjust(1)
    return kb


def _admin_level(tg_id: int) -> str:
    # ???????? ?????? limited, ???? ???? ????? ???-?? ?????????? full.
    try:
        for partner in get_partners_manager().all_partners():
            if int(partner.get("tg_id") or 0) == int(tg_id):
                user = get_user_manager().get_user(int(tg_id))
                if user and (user.get("admin_level") or "").lower() != "limited":
                    get_user_manager().update_user(int(tg_id), admin_level="limited")
                return "limited"
    except Exception:
        pass

    user = get_user_manager().get_user(tg_id) or {}
    return (user.get("admin_level") or "full").lower()


async def _sync_user_modules_to_bots(user_id: int, modules_owned: list[str]):
    manager = get_manager()
    normalized = [item for item in modules_owned if item in ADMIN_GRANTABLE_MODULES]
    for bot in manager.get_all(user_id):
        manager.update(bot["uuid"], modules_owned=normalized)
        if bot.get("is_active"):
            await manager.restart(bot["uuid"])


async def _render_admin_user_modules(callback: CallbackQuery, user_id: int):
    user = get_user_manager().get_user(user_id)
    if not user:
        return await callback.answer(_master_msg("ALERT_USER_NOT_FOUND", "Пользователь не найден"), show_alert=True)

    owned = set(user.get("modules_owned") or [])
    kb = InlineKeyboardBuilder()
    lines = [
        "🔌 ADMIN | Модули пользователя",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"ID: {user_id}",
        f"Username: {user.get('username') or '-'}",
        "",
        "Выдача модулей доступна только администраторам.",
        "",
    ]
    for module_key, module_name in ADMIN_GRANTABLE_MODULES.items():
        enabled = module_key in owned
        lines.append(f"{'✅' if enabled else '❌'} {module_name}")
        kb.button(
            text=f"{'➖ Забрать' if enabled else '➕ Выдать'} {module_name}",
            callback_data=f"admin_toggle_module:{user_id}:{module_key}",
        )
    kb.button(text="◀️ Профиль", callback_data=f"admin_user_profile:{user_id}")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


def _partner_by_tg_id(tg_id: int) -> dict | None:
    try:
        for partner in get_partners_manager().all_partners():
            if int(partner.get("tg_id") or 0) == int(tg_id):
                return partner
    except Exception:
        return None
    return None


async def _notify_full_admins_topup(
    *,
    bot,
    user_id: int,
    username: str | None,
    amount_rub: float,
    provider: str,
    payment_id: str | None = None,
    stars_amount: int | None = None,
):
    cfg = sett.get("config") or {}
    admin_ids = (((cfg.get("telegram") or {}).get("master") or {}).get("admins") or [])
    if not admin_ids:
        return

    provider_labels = {
        "freekassa": "FreeKassa",
        "cryptobot": "CryptoBot",
        "cryptomus": "Cryptomus",
        "lava": "LAVA",
        "telegram_stars": "Telegram Stars",
        "admin_transfer": "Ручное подтверждение",
        "admin_topup": "Пополнение админом",
    }
    provider_label = provider_labels.get(provider, provider)
    uname = f"@{username}" if username else "-"

    user_manager = get_user_manager()
    full_admin_ids: list[int] = []
    for raw_admin_id in admin_ids:
        try:
            admin_id = int(raw_admin_id)
        except Exception:
            continue
        admin_user = user_manager.get_user(admin_id) or {}
        if (admin_user.get("admin_level") or "full").lower() == "full":
            full_admin_ids.append(admin_id)

    if not full_admin_ids:
        return

    lines = [
        "💰 Новое пополнение баланса",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Пользователь ID: {int(user_id)}",
        f"Username: {uname}",
        f"Сумма: +{float(amount_rub):.2f} ₽",
        f"Метод: {provider_label}",
    ]
    if stars_amount is not None:
        lines.append(f"Оплачено: {int(stars_amount)} ⭐")
    if payment_id:
        lines.append(f"Платёж: {payment_id}")
    text = "\n".join(lines)

    for admin_id in set(full_admin_ids):
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            pass


async def _render_admin_limited(callback: CallbackQuery):
    manager = get_manager()
    user_manager = get_user_manager()
    users = user_manager.all_users()
    active_tariffs = sum(1 for user in users.values() if user_manager.has_active_tariff(int(user["tg_id"])))

    text = (
        "\U0001F4C8 ADMIN | \u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001F465 \u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0435\u0439: {len(users)}\n"
        f"\U0001F48E \u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0445 \u0442\u0430\u0440\u0438\u0444\u043E\u0432: {active_tariffs}\n"
        f"\U0001F916 \u0412\u0441\u0435\u0433\u043E \u0434\u043E\u0447\u0435\u0440\u043D\u0438\u0445 \u0431\u043E\u0442\u043E\u0432: {len(manager.load_all_bots())}"
    )
    await render_message(callback, text, _admin_back_kb())


async def _render_admin_panel(callback: CallbackQuery):
    manager = get_manager()
    user_manager = get_user_manager()
    users = user_manager.all_users()
    active_tariffs = sum(1 for user in users.values() if user_manager.has_active_tariff(int(user["tg_id"])))
    maintenance_mode = bool(user_manager.get_system().get("maintenance_mode"))
    admin_level = _admin_level(callback.from_user.id)

    await render_message(
        callback,
        get_admin_panel_text(
            users_count=len(users),
            active_tariffs=active_tariffs,
            bots_count=len(manager.load_all_bots()),
            maintenance_mode=maintenance_mode,
        ),
        get_admin_panel_kb(maintenance_mode, admin_level=admin_level),
    )


async def _render_admin_user_profile(callback: CallbackQuery, user_id: int):
    user = get_user_manager().get_user(user_id)
    if not user:
        return await callback.answer(_master_msg("ALERT_USER_NOT_FOUND", "Пользователь не найден"), show_alert=True)

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    if user.get("is_banned"):
        kb.button(text="\u2705 \u0420\u0430\u0437\u0431\u0430\u043d\u0438\u0442\u044c", callback_data=f"admin_user_unban:{user_id}")
    else:
        kb.button(text="\U0001F6AB \u0417\u0430\u0431\u0430\u043d\u0438\u0442\u044c", callback_data=f"admin_user_ban:{user_id}")
    kb.button(text="\U0001F381 \u041F\u0440\u043E\u0431\u043D\u044B\u0439 \u043F\u0435\u0440\u0438\u043E\u0434", callback_data=f"admin_user_trial:{user_id}")
    kb.button(text="\U0001F4B0 \u0423\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C \u0431\u0430\u043B\u0430\u043D\u0441", callback_data=f"admin_topup:{user_id}")
    kb.button(text="🔌 Модули", callback_data=f"admin_user_modules:{user_id}")
    kb.button(text="\U0001F916 \u0421\u043F\u0438\u0441\u043E\u043A \u0431\u043E\u0442\u043E\u0432", callback_data=f"admin_user_bots:{user_id}")
    kb.button(text="\u25c0\ufe0f \u041a \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f\u043c", callback_data="admin_users")
    kb.adjust(2, 2, 2)

    text = (
        "\U0001F464 ADMIN | \u041f\u0440\u043e\u0444\u0438\u043b\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"ID: {user['tg_id']}\n"
        f"Username: {user.get('username') or '-'}\n"
        f"\u0418\u043c\u044f: {user.get('first_name') or '-'}\n"
        f"\u0411\u0430\u043b\u0430\u043d\u0441: {float(user.get('balance', 0)):.2f} \u20bd\n"
        f"\u0422\u0430\u0440\u0438\u0444: {tariff_title_ru(user.get('tariff'))}\n"
        f"\u0414\u043e: {user.get('tariff_expires') or '-'}\n"
        f"\u0411\u0430\u043d: {'\u0434\u0430' if user.get('is_banned') else '\u043d\u0435\u0442'}\n"
        f"\u041f\u0440\u043e\u0431\u043d\u044b\u0439: {'\u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d' if user.get('trial_used') else '\u043d\u0435\u0442'}"
    )
    await render_message(callback, text, kb.as_markup())


async def _render_admin_user_bots(callback: CallbackQuery, user_id: int):
    manager = get_manager()
    bots = manager.get_all(user_id)
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    lines = [f"🤖 Боты пользователя {user_id}", "━━━━━━━━━━━━━━━━━━━━━━━━\n"]
    if not bots:
        lines.append("Ботов нет.")
    else:
        for idx, bot in enumerate(bots, start=1):
            name = bot.get("tg_username") or bot["uuid"][:8]
            status = "\U0001F7E2" if bot.get("is_active") else "\U0001F534"
            lines.append(f"{idx}. {name} {status}")
            kb.button(text=f"⛔ Остановить {name}", callback_data=f"admin_force_stop:{bot['uuid']}:{user_id}")
    kb.button(text="◀️ Профиль", callback_data=f"admin_user_profile:{user_id}")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


async def _render_proxy_settings(callback: CallbackQuery, bot: dict):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    proxy_list = [item for item in bot.get("proxy_list", []) if item]
    current_proxy = bot.get("proxy") or "?? ?????"
    lines = [
        f"?? ?????? ??? {bot.get('tg_username') or bot['uuid'][:8]}",
        "????????????????????????",
        f"???????: <code>{current_proxy}</code>",
        "",
    ]
    if not proxy_list:
        lines.append("?????? ?????? ????.")
    else:
        lines.append("Доступные прокси:")
        for idx, proxy in enumerate(proxy_list, start=1):
            marker = " ?" if proxy == bot.get("proxy") else ""
            lines.append(f"{idx}. <code>{proxy}</code>{marker}")

    kb = InlineKeyboardBuilder()
    kb.button(text="\u2795 \u0414\u043E\u0431\u0430\u0432\u0438\u0442\u044C \u043F\u0440\u043E\u043A\u0441\u0438", callback_data=f"proxy_add:{bot['uuid']}")
    kb.button(text="\U0001F9F9 \u041E\u0447\u0438\u0441\u0442\u0438\u0442\u044C \u0441\u043F\u0438\u0441\u043E\u043A", callback_data=f"proxy_clear:{bot['uuid']}")
    kb.button(text="\u25C0\uFE0F \u041D\u0430\u0437\u0430\u0434", callback_data=f"settings_main:{bot['uuid']}")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


async def _render_account_settings(callback: CallbackQuery, bot: dict):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    has_pl = bool(bot.get("pl_token"))
    has_fp = bool(bot.get("fp_golden_key"))
    lines = [
        f"⚙️ Настройки аккаунтов — {bot.get('tg_username') or bot['uuid'][:8]}",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        f"🟦 Playerok: {'подключён ✓' if has_pl else 'не подключён ❌'}",
        f"🟠 FunPay: {'подключён ✓' if has_fp else 'не подключён ❌'}",
    ]
    kb = InlineKeyboardBuilder()
    kb.button(text="🟦 Настройки Playerok", callback_data=f"acc_playerok:{bot['uuid']}")
    kb.button(text="🟠 Настройки FunPay", callback_data=f"acc_funpay:{bot['uuid']}")
    kb.button(text="⬆️ Назад", callback_data=SelectBot(uuid=bot["uuid"]).pack())
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


async def _render_playerok_settings(callback: CallbackQuery, bot: dict):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Обновить токен", callback_data=f"acc_pl_token:{bot['uuid']}")
    kb.button(text="✏️ Обновить User Agent", callback_data=f"acc_pl_ua:{bot['uuid']}")
    kb.button(text="✏️ Обновить прокси", callback_data=f"acc_pl_proxy:{bot['uuid']}")
    kb.button(text="❌ Убрать прокси", callback_data=f"acc_pl_proxy_clear:{bot['uuid']}")
    kb.button(text="🗑️ Отвязать Playerok", callback_data=f"acc_pl_detach:{bot['uuid']}")
    kb.button(text="⬆️ Назад", callback_data=f"acc_settings:{bot['uuid']}")
    kb.adjust(1)
    await render_message(callback, "🟦 Настройки Playerok", kb.as_markup())


async def _render_funpay_settings(callback: CallbackQuery, bot: dict):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    has_fp = bool(bot.get("fp_golden_key"))
    kb = InlineKeyboardBuilder()
    if has_fp:
        kb.button(text="✏️ Обновить Golden Key", callback_data=f"acc_fp_key:{bot['uuid']}")
        kb.button(text="✏️ Обновить User Agent", callback_data=f"acc_fp_ua:{bot['uuid']}")
        kb.button(text="✏️ Обновить прокси", callback_data=f"acc_fp_proxy:{bot['uuid']}")
        kb.button(text="❌ Убрать прокси", callback_data=f"acc_fp_proxy_clear:{bot['uuid']}")
        kb.button(text="🗑️ Отвязать FunPay", callback_data=f"acc_fp_detach:{bot['uuid']}")
    else:
        kb.button(text="🟠 Подключить FunPay", callback_data=f"acc_fp_attach:{bot['uuid']}")
    kb.button(text="⬆️ Назад", callback_data=f"acc_settings:{bot['uuid']}")
    kb.adjust(1)
    await render_message(callback, "🟠 Настройки FunPay", kb.as_markup())


async def _finalize_create_from_state(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or ["playerok"])
    manager = get_manager()
    config = manager.create(
        owner_id=callback.from_user.id,
        pl_tg_token=data.get("pl_tg_token", ""),
        fp_tg_token=data.get("fp_tg_token", ""),
        pl_token=data.get("pl_token", ""),
        ua=data.get("pl_user_agent", data.get("user_agent", "")),
        proxy=data.get("pl_proxy", data.get("proxy", "")),
        password=data["password"],
        platforms=chosen,
        fp_golden_key=data.get("fp_golden_key", ""),
        fp_user_agent=data.get("fp_user_agent", ""),
        fp_proxy=data.get("fp_proxy", ""),
    )
    await manager.start(config["uuid"])
    # Reload persisted config after start(): tg_username is resolved there via getMe.
    config = manager.get(config["uuid"]) or config
    get_user_manager().log_action(callback.from_user.username or str(callback.from_user.id), "create_bot", config["uuid"])
    await state.clear()
    await render_message(callback, get_success_text(config), get_success_kb())


async def _ask_password_step_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = 1 + (4 if "playerok" in chosen else 0) + (4 if "funpay" in chosen else 0)
    await state.set_state(CreateBotStates.WAITING_PASSWORD)
    await render_message(
        callback,
        get_step_text(
            total,
            total,
            f"🔐 Шаг {total} из {total} — Пароль дочернего бота",
            "Введите пароль (6-64 символа). Для владельца он не требуется, для остальных обязателен.",
            "MyBot_2026!",
        ),
        get_cancel_kb(),
    )


@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_main(callback)


@router.callback_query(F.data == "master_modules_menu")
async def cb_master_modules_menu(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_user_available(callback):
        return
    await state.clear()
    profile = get_user_manager().ensure_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    await render_message(callback, _master_modules_text(profile), _master_modules_kb(profile))


@router.callback_query(F.data == "master_module_buy:auto_bonus")
async def cb_master_module_buy_autobonus(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_user_available(callback):
        return
    await state.clear()
    profile = get_user_manager().ensure_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    await render_message(
        callback,
        _master_modules_text(
            profile,
            _master_msg(
                "MASTER_MODULES_PURCHASE_DISABLED_TEXT",
                "Покупка модулей временно отключена. Напишите в поддержку: @RaidexHelp_bot",
            ),
        ),
        _master_modules_kb(profile),
    )


@router.callback_query(F.data == "create_bot")
async def cmd_create_bot_start(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_user_available(callback):
        return
    manager = get_manager()
    user_manager = get_user_manager()
    allowed, reason = user_manager.can_create_bot(callback.from_user.id, len(manager.get_all(callback.from_user.id)))
    if not allowed and reason == "no_tariff":
        return await render_message(callback, get_need_tariff_text(), get_need_tariff_kb())
    chosen = []
    await state.set_state(CreateBotStates.CHOOSING_PLATFORM)
    await state.update_data(chosen_platforms=chosen)
    await render_message(callback, get_platforms_pick_text(chosen), get_platforms_pick_kb(chosen))


@router.callback_query(F.data == "start_create_bot")
async def cb_start_create_flow(callback: CallbackQuery, state: FSMContext):
    chosen = []
    await state.set_state(CreateBotStates.CHOOSING_PLATFORM)
    await state.update_data(chosen_platforms=chosen)
    await render_message(callback, get_platforms_pick_text(chosen), get_platforms_pick_kb(chosen))


@router.callback_query(F.data.startswith("toggle_platform:"))
async def cb_toggle_platform(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    platform = callback.data.split(":", 1)[1]
    if platform not in {"funpay", "playerok"}:
        return await callback.answer(_master_msg("ALERT_UNKNOWN_PLATFORM", "Неизвестная платформа"), show_alert=True)
    if platform in chosen:
        chosen.remove(platform)
    else:
        chosen.append(platform)
    await state.update_data(chosen_platforms=chosen)
    await render_message(callback, get_platforms_pick_text(chosen), get_platforms_pick_kb(chosen))


@router.callback_query(F.data == "platforms_continue")
async def cb_platforms_continue(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    if not chosen:
        return await callback.answer(_master_msg("ALERT_SELECT_PLATFORM", "Выберите хотя бы одну платформу."), show_alert=True)
    await state.update_data(chosen_platforms=chosen)
    total = 1 + (4 if "playerok" in chosen else 0) + (4 if "funpay" in chosen else 0)
    if "playerok" in chosen:
        await state.set_state(CreateBotStates.WAITING_PL_TG_TOKEN)
        return await render_message(
            callback,
            get_step_text(
                1,
                total,
                _master_render("CREATE_STEP_PL_TG_TITLE", "🟦 Шаг {step} из {total} — Telegram-токен для Playerok-бота", step=1, total=total),
                _master_msg("CREATE_STEP_PL_TG_DESC", "Отправьте токен Telegram-бота для управления Playerok-аккаунтом."),
                "7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM",
            ),
            get_cancel_kb(),
        )
    await state.set_state(CreateBotStates.WAITING_FP_TG_TOKEN)
    await render_message(
        callback,
        get_step_text(
            1,
            total,
            _master_render("CREATE_STEP_FP_TG_TITLE", "🟠 Шаг {step} из {total} — Telegram-токен для FunPay-бота", step=1, total=total),
            _master_msg("CREATE_STEP_FP_TG_DESC", "Отправьте токен Telegram-бота для управления FunPay-аккаунтом. Это должен быть отдельный бот от Playerok."),
            "7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM",
        ),
        get_cancel_kb(),
    )


@router.callback_query(F.data == "cancel_create_bot")
async def cb_cancel_create(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_main(callback)


@router.callback_query(SkipStep.filter(F.step == "user_agent"))
async def cb_skip_user_agent(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pl_user_agent="", user_agent="")
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = 1 + (4 if "playerok" in chosen else 0) + (4 if "funpay" in chosen else 0)
    await state.set_state(CreateBotStates.WAITING_PL_PROXY)
    await render_message(
        callback,
        get_step_text(
            4,
            total,
            _master_render("CREATE_STEP_PL_PROXY_TITLE", "🌐 Шаг {step} из {total} — Прокси Playerok", step=4, total=total),
            _master_msg("CREATE_STEP_PL_PROXY_DESC", "Отправьте HTTP IPv4 прокси для Playerok или пропустите этот шаг."),
            "DRjcQTm3Yc:m8GnUN8Q9L@46.161.30.187:8000",
        ),
        get_skip_kb("pl_proxy"),
    )
    return
    await state.update_data(user_agent="")
    await state.set_state(CreateBotStates.WAITING_PROXY)
    await render_message(
        callback,
        get_step_text(
            4,
            4,
            "🌐 Шаг 4 из 5 — Прокси",
            "Отправьте HTTP IPv4 прокси или пропустите этот шаг.",
            "DRjcQTm3Yc:m8GnUN8Q9L@46.161.30.187:8000",
        ),
        get_skip_kb("proxy"),
    )


@router.callback_query(SkipStep.filter(F.step == "proxy"))
async def cb_skip_proxy(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pl_proxy="", proxy="")
    await _ask_password_step_callback(callback, state)


@router.callback_query(SkipStep.filter(F.step == "fp_user_agent"))
async def cb_skip_fp_user_agent(callback: CallbackQuery, state: FSMContext):
    await state.update_data(fp_user_agent="")
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = 1 + (4 if "playerok" in chosen else 0) + (4 if "funpay" in chosen else 0)
    step = 4 if "playerok" not in chosen else 8
    await state.set_state(CreateBotStates.WAITING_FP_PROXY)
    await render_message(
        callback,
        get_step_text(
            step,
            total,
            _master_render("CREATE_STEP_FP_PROXY_TITLE", "🌐 Шаг {step} из {total} — Прокси FunPay", step=step, total=total),
            _master_msg("CREATE_STEP_FP_PROXY_DESC", "Отправьте HTTP IPv4 прокси для FunPay или пропустите этот шаг."),
            "DRjcQTm3Yc:m8GnUN8Q9L@46.161.30.187:8000",
        ),
        get_skip_kb("fp_proxy"),
    )


@router.callback_query(SkipStep.filter(F.step == "fp_proxy"))
async def cb_skip_fp_proxy(callback: CallbackQuery, state: FSMContext):
    await state.update_data(fp_proxy="")
    await _ask_password_step_callback(callback, state)


@router.callback_query(SkipStep.filter(F.step == "pl_user_agent"))
async def cb_skip_pl_user_agent(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pl_user_agent="", user_agent="")
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = 1 + (4 if "playerok" in chosen else 0) + (4 if "funpay" in chosen else 0)
    await state.set_state(CreateBotStates.WAITING_PL_PROXY)
    await render_message(
        callback,
        get_step_text(
            4,
            total,
            _master_render("CREATE_STEP_PL_PROXY_TITLE", "🌐 Шаг {step} из {total} — Прокси Playerok", step=4, total=total),
            _master_msg("CREATE_STEP_PL_PROXY_DESC", "Отправьте HTTP IPv4 прокси для Playerok или пропустите этот шаг."),
            "DRjcQTm3Yc:m8GnUN8Q9L@46.161.30.187:8000",
        ),
        get_skip_kb("pl_proxy"),
    )


@router.callback_query(SkipStep.filter(F.step == "pl_proxy"))
async def cb_skip_pl_proxy(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pl_proxy="", proxy="")
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    if "funpay" in chosen:
        total = 1 + (4 if "playerok" in chosen else 0) + (4 if "funpay" in chosen else 0)
        await state.set_state(CreateBotStates.WAITING_FP_TG_TOKEN)
        return await render_message(
            callback,
            get_step_text(
                5,
                total,
                _master_render("CREATE_STEP_FP_TG_TITLE", "🟠 Шаг {step} из {total} — Telegram-токен для FunPay-бота", step=5, total=total),
                _master_msg("CREATE_STEP_FP_TG_DESC", "Отправьте токен Telegram-бота для управления FunPay-аккаунтом. Это должен быть отдельный бот от Playerok."),
                "7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM",
            ),
            get_cancel_kb(),
        )
    await _ask_password_step_callback(callback, state)
@router.callback_query(F.data == "my_bots")
async def cb_my_bots(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    manager = get_manager()
    await manager.refresh_usernames_for_owner(callback.from_user.id)
    bots = manager.get_all(callback.from_user.id)
    await render_message(callback, get_my_bots_text(bots), get_my_bots_kb(bots))


@router.callback_query(SelectBot.filter())
async def cb_select_bot(callback: CallbackQuery, callback_data: SelectBot):
    if not await _ensure_user_available(callback):
        return
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await render_message(callback, get_bot_card_text(bot, manager.get_runtime_stats(bot["uuid"])), get_bot_card_kb(bot))


@router.callback_query(F.data.startswith("acc_settings:"))
async def cb_account_settings(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await _render_account_settings(callback, bot)


@router.callback_query(F.data.startswith("acc_playerok:"))
async def cb_account_playerok(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await _render_playerok_settings(callback, bot)


@router.callback_query(F.data.startswith("acc_funpay:"))
async def cb_account_funpay(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await _render_funpay_settings(callback, bot)


@router.callback_query(F.data.startswith("acc_pl_token:"))
async def cb_account_pl_token(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(AccountSettingsStates.WAITING_PL_TOKEN)
    await state.update_data(uuid=uuid_value)
    await render_message(callback, _master_msg("PROMPT_PL_TOKEN", "✏️ Отправьте новый токен Playerok"), get_cancel_kb())


@router.callback_query(F.data.startswith("acc_pl_ua:"))
async def cb_account_pl_ua(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(AccountSettingsStates.WAITING_PL_USER_AGENT)
    await state.update_data(uuid=uuid_value)
    await render_message(callback, _master_msg("PROMPT_PL_UA", "✏️ Отправьте новый User Agent Playerok"), get_cancel_kb())


@router.callback_query(F.data.startswith("acc_pl_proxy:"))
async def cb_account_pl_proxy(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(AccountSettingsStates.WAITING_PL_PROXY)
    await state.update_data(uuid=uuid_value)
    await render_message(callback, _master_msg("PROMPT_PL_PROXY", "✏️ Отправьте новый прокси Playerok"), get_cancel_kb())


@router.callback_query(F.data.startswith("acc_pl_proxy_clear:"))
async def cb_account_pl_proxy_clear(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    manager.update(uuid_value, pl_proxy="", proxy="")
    await manager.restart(uuid_value)
    await _render_playerok_settings(callback, manager.get(uuid_value))


@router.callback_query(F.data.startswith("acc_pl_detach:"))
async def cb_account_pl_detach(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    manager.detach_playerok(uuid_value)
    await manager.restart(uuid_value)
    await _render_account_settings(callback, manager.get(uuid_value))


@router.callback_query(F.data.startswith("acc_fp_attach:"))
async def cb_account_fp_attach(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(AccountSettingsStates.WAITING_FP_TG_TOKEN)
    await state.update_data(uuid=uuid_value, fp_flow="attach")
    await render_message(
        callback,
        _master_msg(
            "ACCOUNT_FP_ATTACH_TEXT",
            "🟠 Подключение FunPay — Шаг 1 из 4\n\nОтправьте токен Telegram-бота для управления\nFunPay-аккаунтом.\n\nЭто должен быть отдельный бот от Playerok-бота.\nСоздайте его у @BotFather командой /newbot.\n\nПример: 7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM",
        ),
        get_cancel_kb(),
    )


@router.callback_query(F.data.startswith("acc_fp_key:"))
async def cb_account_fp_key(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(AccountSettingsStates.WAITING_FP_GOLDEN_KEY)
    await state.update_data(uuid=uuid_value, fp_flow="update_key")
    await render_message(callback, _master_msg("PROMPT_FP_KEY", "✏️ Введите новый Golden Key FunPay"), get_cancel_kb())


@router.callback_query(F.data.startswith("acc_fp_ua:"))
async def cb_account_fp_ua(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    bot = get_manager().get(uuid_value) or {}
    await state.set_state(AccountSettingsStates.WAITING_FP_USER_AGENT)
    await state.update_data(uuid=uuid_value, fp_golden_key=bot.get("fp_golden_key", ""))
    await render_message(callback, _master_msg("PROMPT_FP_UA", "✏️ Введите новый User Agent FunPay"), get_cancel_kb())


@router.callback_query(F.data.startswith("acc_fp_proxy:"))
async def cb_account_fp_proxy(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    bot = get_manager().get(uuid_value) or {}
    await state.set_state(AccountSettingsStates.WAITING_FP_PROXY)
    await state.update_data(
        uuid=uuid_value,
        fp_golden_key=bot.get("fp_golden_key", ""),
        fp_user_agent=bot.get("fp_user_agent", ""),
    )
    await render_message(callback, _master_msg("PROMPT_FP_PROXY", "✏️ Введите новый прокси FunPay"), get_cancel_kb())


@router.callback_query(F.data.startswith("acc_fp_proxy_clear:"))
async def cb_account_fp_proxy_clear(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    manager.update(uuid_value, fp_proxy="")
    await manager.restart(uuid_value)
    await _render_funpay_settings(callback, manager.get(uuid_value))


@router.callback_query(F.data.startswith("acc_fp_detach:"))
async def cb_account_fp_detach(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    manager.detach_funpay(uuid_value)
    await manager.restart(uuid_value)
    await _render_account_settings(callback, manager.get(uuid_value))


@router.callback_query(F.data.startswith("customize:"))
async def cb_customize_menu(callback: CallbackQuery):
    manager = get_manager()
    uuid_value = callback.data.split(":", 1)[1]
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Описание бота", callback_data=f"customize_desc:{uuid_value}")
    kb.button(text="📌 Короткое описание", callback_data=f"customize_short:{uuid_value}")
    kb.button(text="🔗 Кнопки-ссылки", callback_data=f"customize_links:{uuid_value}")
    kb.button(text="💬 Сообщения", callback_data=f"customize_messages:{uuid_value}")
    kb.button(text="⬆️ Назад", callback_data=SelectBot(uuid=uuid_value).pack())
    kb.adjust(1)
    await render_message(callback, _master_msg("PROMPT_CUSTOMIZE", "🖌️ Кастомизация"), kb.as_markup())


@router.callback_query(F.data.startswith("customize_desc:"))
async def cb_customize_desc(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(CustomizationStates.WAITING_BOT_DESCRIPTION)
    await state.update_data(uuid=uuid_value)
    await render_message(callback, _master_msg("PROMPT_FULL_DESCRIPTION", "📝 Отправьте новый текст полного описания бота."), get_cancel_kb())


@router.callback_query(F.data.startswith("customize_short:"))
async def cb_customize_short(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(CustomizationStates.WAITING_BOT_SHORT_DESCRIPTION)
    await state.update_data(uuid=uuid_value)
    await render_message(callback, _master_msg("PROMPT_SHORT_DESCRIPTION", "📌 Отправьте новый текст короткого описания бота."), get_cancel_kb())


@router.callback_query(F.data.startswith("customize_links:"))
async def cb_customize_links(callback: CallbackQuery):
    uuid_value = callback.data.split(":", 1)[1]
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    buttons = list(bot.get("link_buttons") or [])
    lines = ["🔗 Кнопки-ссылки"]
    for i, item in enumerate(buttons, 1):
        lines.append(f"{i}. {item.get('text')} -> {item.get('url')}")
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить кнопку", callback_data=f"customize_link_add:{uuid_value}")
    kb.button(text="➖ Удалить последнюю", callback_data=f"customize_link_del:{uuid_value}")
    kb.button(text="⬆️ Назад", callback_data=f"customize:{uuid_value}")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


@router.callback_query(F.data.startswith("customize_link_add:"))
async def cb_customize_link_add(callback: CallbackQuery, state: FSMContext):
    uuid_value = callback.data.split(":", 1)[1]
    await state.set_state(CustomizationStates.WAITING_LINK_TEXT)
    await state.update_data(uuid=uuid_value)
    await render_message(callback, _master_msg("PROMPT_LINK_BUTTON_TEXT", "➕ Отправьте текст кнопки."), get_cancel_kb())


@router.callback_query(F.data.startswith("customize_link_del:"))
async def cb_customize_link_del(callback: CallbackQuery):
    uuid_value = callback.data.split(":", 1)[1]
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    buttons = list(bot.get("link_buttons") or [])
    if buttons:
        buttons.pop()
        manager.update(uuid_value, link_buttons=buttons)
        await manager.restart(uuid_value)
    await cb_customize_links(callback)


@router.callback_query(F.data.startswith("customize_messages:"))
async def cb_customize_messages(callback: CallbackQuery):
    uuid_value = callback.data.split(":", 1)[1]
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    message_keys = [
        "first_message",
        "new_order",
        "order_confirmed",
        "order_refunded",
        "order_review_reply",
        "cmd_seller",
        "cmd_commands",
    ]
    kb = InlineKeyboardBuilder()
    for key in message_keys:
        kb.button(text=key, callback_data=f"customize_msg:{uuid_value}:{key}")
    kb.button(text="⬆️ Назад", callback_data=f"customize:{uuid_value}")
    kb.adjust(1)
    await render_message(callback, _master_msg("PROMPT_SELECT_MESSAGE", "💬 Выберите сообщение для редактирования."), kb.as_markup())


@router.callback_query(F.data.startswith("customize_msg:"))
async def cb_customize_msg(callback: CallbackQuery, state: FSMContext):
    _, uuid_value, key = callback.data.split(":", 2)
    await state.set_state(CustomizationStates.WAITING_MESSAGE_TEXT)
    await state.update_data(uuid=uuid_value, message_key=key)
    await render_message(callback, f"💬 Отправьте новый текст для `{key}`.", get_cancel_kb())


@router.callback_query(ManageBot.filter(F.action == "start"))
async def cb_start_bot(callback: CallbackQuery, callback_data: ManageBot):
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await manager.start(callback_data.uuid)
    bot = manager.get(callback_data.uuid)
    await render_message(callback, get_bot_card_text(bot, manager.get_runtime_stats(bot["uuid"])), get_bot_card_kb(bot))


@router.callback_query(ManageBot.filter(F.action == "stop"))
async def cb_stop_bot(callback: CallbackQuery, callback_data: ManageBot):
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await manager.stop(callback_data.uuid)
    bot = manager.get(callback_data.uuid)
    await render_message(callback, get_bot_card_text(bot, manager.get_runtime_stats(bot["uuid"])), get_bot_card_kb(bot))


@router.callback_query(ManageBot.filter(F.action == "restart"))
async def cb_restart_bot(callback: CallbackQuery, callback_data: ManageBot):
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await manager.restart(callback_data.uuid)
    bot = manager.get(callback_data.uuid)
    await render_message(callback, get_bot_card_text(bot, manager.get_runtime_stats(bot["uuid"])), get_bot_card_kb(bot))


@router.callback_query(ManageBot.filter(F.action == "delete"))
async def cb_delete_bot_confirm(callback: CallbackQuery, callback_data: ManageBot):
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await render_message(callback, get_delete_confirm_text(bot), get_delete_confirm_kb(bot["uuid"]))


@router.callback_query(ConfirmDelete.filter(F.confirmed == True))
async def cb_delete_bot_execute(callback: CallbackQuery, callback_data: ConfirmDelete):
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await manager.delete(callback_data.uuid)
    await cb_my_bots(callback)


@router.callback_query(ConfirmDelete.filter(F.confirmed == False))
async def cb_delete_bot_cancel(callback: CallbackQuery, callback_data: ConfirmDelete):
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await render_message(callback, get_bot_card_text(bot, manager.get_runtime_stats(bot["uuid"])), get_bot_card_kb(bot))


@router.callback_query(ManageBot.filter(F.action == "settings"))
async def cb_update_bot_token(callback: CallbackQuery, callback_data: ManageBot, state: FSMContext):
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(callback_data.uuid))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await state.set_state(UpdateTokenStates.WAITING_TOKEN)
    await state.update_data(uuid=bot["uuid"])
    await render_message(
        callback,
        f"🔑 Обновление токена Playerok\n━━━━━━━━━━━━━━━━━━━━━━━━\nОтправьте новый токен Playerok для бота {bot.get('tg_username') or bot['uuid'][:8]}.",
        get_cancel_kb(),
    )


@router.callback_query(F.data == "help_menu")
async def cb_help_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    await render_message(callback, get_help_text(), get_back_menu_kb())


@router.callback_query(F.data == "topup_menu")
async def cb_topup_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    user_manager = get_user_manager()
    user = user_manager.get_user(callback.from_user.id)
    await render_message(
        callback,
        _topup_menu_text(float(user["balance"])),
        _topup_methods_kb().as_markup(),
    )


@router.callback_query(F.data.startswith("topup_method:"))
async def cb_topup_method(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    provider = callback.data.split(":", 1)[1]
    if provider not in {"freekassa", "cryptobot", "cryptomus", "lava", "telegram_stars", "admin_transfer"}:
        return await callback.answer(_master_msg("ALERT_UNKNOWN_PAYMENT_METHOD", "Неизвестный способ оплаты."), show_alert=True)
    user = get_user_manager().get_user(callback.from_user.id)
    await render_message(
        callback,
        _topup_amounts_text(provider, float(user["balance"])),
        _topup_amounts_kb(provider).as_markup(),
    )


@router.callback_query(F.data.startswith("topup_create:"))
async def cb_topup_create(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return

    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3:
        return await callback.answer(_master_msg("ALERT_INVALID_DATA", "Некорректные данные."), show_alert=True)
    _, provider, amount_raw = parts
    try:
        amount = float(amount_raw)
    except ValueError:
        return await callback.answer(_master_msg("ALERT_INVALID_SUM", "Некорректная сумма."), show_alert=True)
    if amount < 80:
        return await callback.answer(_master_msg("ALERT_MIN_TOPUP_AMOUNT", "Минимальная сумма пополнения: 80 ₽"), show_alert=True)

    if provider == "telegram_stars":
        stars_cfg = _telegram_stars_config()
        if stars_cfg and not stars_cfg.get("enabled", True):
            return await render_message(
                callback,
                _master_msg("TOPUP_STARS_DISABLED_TEXT", "⭐ Оплата Telegram Stars сейчас выключена администратором."),
                get_back_menu_kb(),
            )
        rate = float(stars_cfg.get("stars_per_rub") or stars_cfg.get("rub_per_star") or 1.9)
        if rate <= 0:
            rate = 1.9
        stars_amount = max(1, int(math.ceil(amount * rate)))
        credited_rub = round(float(amount), 2)
        payment_id = TelegramStarsLedger.make_payment_id(callback.from_user.id)
        payload = f"stars_topup:{payment_id}"
        TelegramStarsLedger.create(
            payment_id=payment_id,
            user_id=callback.from_user.id,
            amount_rub=credited_rub,
            requested_amount_rub=amount,
            stars_amount=stars_amount,
            rate=rate,
        )
        try:
            await callback.bot.send_invoice(
                chat_id=callback.from_user.id,
                title=_master_msg("TOPUP_INVOICE_TITLE", "Пополнение баланса"),
                description=_master_render(
                    "TOPUP_STARS_INVOICE_DESCRIPTION",
                    "К зачислению: {credited_rub:.2f} ₽\nК оплате: {stars_amount} ⭐\nКурс: 1 ₽ = {rate:.2f} ⭐",
                    credited_rub=credited_rub,
                    stars_amount=stars_amount,
                    rate=rate,
                ),
                payload=payload,
                currency="XTR",
                prices=[LabeledPrice(label=_master_render("TOPUP_STARS_INVOICE_LABEL", "Пополнение баланса ({stars_amount} ⭐)", stars_amount=stars_amount), amount=stars_amount)],
            )
        except Exception as e:
            return await render_message(
                callback,
                _master_render("TOPUP_STARS_CREATE_ERROR_TEXT", "❌ Не удалось создать счёт Telegram Stars\n━━━━━━━━━━━━━━━━━━━━━━━━\n{error}", error=e),
                get_back_menu_kb(),
            )
        get_user_manager().log_action(
            callback.from_user.username or str(callback.from_user.id),
            "topup_invoice_stars",
            payment_id,
        )
        return await render_message(
            callback,
            _master_render(
                "TOPUP_STARS_CREATED_TEXT",
                "🧾 Счёт создан (Telegram Stars)\n━━━━━━━━━━━━━━━━━━━━━━━━\nК оплате: {stars_amount} ⭐\nБудет зачислено: +{credited_rub:.2f} ₽\nНомер платежа: <code>{payment_id}</code>\n\nОплатите счёт во всплывающем окне Telegram.",
                stars_amount=stars_amount,
                credited_rub=credited_rub,
                payment_id=payment_id,
            ),
            get_back_menu_kb(),
        )

    if provider == "admin_transfer":
        order = AdminTransferLedger.create(user_id=callback.from_user.id, amount=amount)
        order_id = str(order["order_id"])
        get_user_manager().log_action(callback.from_user.username or str(callback.from_user.id), "topup_invoice_admin_transfer", order_id)
        return await render_message(
            callback,
            _master_render(
                "TOPUP_ADMIN_TRANSFER_TEXT",
                "Отправьте сумму на:\n+79964091244 (Альфа-Банк)\n\nВ комментариях укажите номер заказа: <code>{order_id}</code>\n\nПосле оплаты:\n- нажмите на \"Я оплатил\"\n- следуйте инструкции в чате",
                order_id=order_id,
            ),
            _topup_admin_transfer_kb(order_id).as_markup(),
        )

    if provider == "freekassa":
        fk_cfg = _freekassa_config()
        if not fk_cfg.get("enabled"):
            return await render_message(
                callback,
                _master_msg("TOPUP_FK_DISABLED_TEXT", "💳 Пополнение баланса\n━━━━━━━━━━━━━━━━━━━━━━━━\nFreeKassa сейчас выключена администратором."),
                get_back_menu_kb(),
            )
        api_key = (fk_cfg.get("api_key") or "").strip()
        if not api_key:
            return await render_message(
                callback,
                _master_msg("TOPUP_FK_API_MISSING_TEXT", "💳 Пополнение баланса\n━━━━━━━━━━━━━━━━━━━━━━━━\nНе задан API-ключ FreeKassa.\nОбратитесь к администратору."),
                get_back_menu_kb(),
            )
        client = FreeKassaClient(
            api_key=api_key,
            shop_id=int(fk_cfg.get("shop_id") or 0),
            timeout=int(fk_cfg.get("timeout") or 20),
        )
        payment_id = PaymentLedger.make_payment_id(callback.from_user.id)
        try:
            checkout_mode = str(fk_cfg.get("checkout_mode") or "auto").strip().lower()
            secret_word_1 = str(fk_cfg.get("secret_word_1") or "").strip()
            if checkout_mode == "sci" and not secret_word_1:
                raise FreeKassaError("Для SCI-оплаты нужно заполнить payments.freekassa.secret_word_1")
            use_sci = checkout_mode == "sci" or (checkout_mode == "auto" and bool(secret_word_1))
            if use_sci:
                email_local = f"tg{int(callback.from_user.id)}_{int(datetime.now().timestamp())}"
                email_safe = "".join(ch for ch in email_local if ch.isalnum()).lower()[:32] or "user"
                pay_url = FreeKassaClient.build_sci_url(
                    shop_id=int(fk_cfg.get("shop_id") or 0),
                    secret_word_1=secret_word_1,
                    payment_id=payment_id,
                    amount=amount,
                    currency=(fk_cfg.get("currency") or "RUB"),
                    method_id=(
                        int(fk_cfg.get("payment_system_id"))
                        if str(fk_cfg.get("payment_system_id") or "").strip()
                        and int(fk_cfg.get("payment_system_id") or 0) > 0
                        else None
                    ),
                    email=f"{email_safe}@example.com",
                    lang="ru",
                    base_url=str(fk_cfg.get("sci_url") or "https://pay.freekassa.net/"),
                )
                order = {"location": pay_url, "orderId": None}
            else:
                order = await client.create_order(
                    payment_id=payment_id,
                    amount=amount,
                    currency=(fk_cfg.get("currency") or "RUB"),
                    payment_system_id=42,
                )
        except FreeKassaError as e:
            extra_hint = ""
            if "Merchant API KEY not exist" in str(e):
                extra_hint = (
                    "\n\n\u041F\u043E\u0434\u0441\u043A\u0430\u0437\u043A\u0430: \u0443\u043A\u0430\u0436\u0438\u0442\u0435 API-\u043A\u043B\u044E\u0447 \u0438\u0437 \u0440\u0430\u0437\u0434\u0435\u043B\u0430 API \u0432 \u043A\u0430\u0431\u0438\u043D\u0435\u0442\u0435 FreeKassa "
                    "(\u043D\u0435 \u0441\u0435\u043A\u0440\u0435\u0442\u043D\u043E\u0435 \u0441\u043B\u043E\u0432\u043E SCI \u0438 \u043D\u0435 shop_id)."
                )
            return await render_message(
                callback,
                "\u274C \u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0441\u043E\u0437\u0434\u0430\u0442\u044C \u0441\u0447\u0451\u0442 FreeKassa\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                f"{e}\n\n"
                f"\u0422\u0435\u043A\u0443\u0449\u0438\u0439 shop_id: <code>{int(fk_cfg.get('shop_id') or 0)}</code>\n"
                "\u041F\u0440\u043E\u0432\u0435\u0440\u044C\u0442\u0435 \u043D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 API-\u043A\u043B\u044E\u0447\u0430/shop_id \u0438 \u043F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u0435 \u0431\u043E\u0442\u0430 \u043F\u043E\u0441\u043B\u0435 \u043F\u0440\u0430\u0432\u043E\u043A."
                f"{extra_hint}",
                get_back_menu_kb(),
            )

        pay_url = order.get("location")
        PaymentLedger.create(
            payment_id=payment_id,
            user_id=callback.from_user.id,
            amount=amount,
            currency=(fk_cfg.get("currency") or "RUB"),
            pay_url=pay_url,
            fk_order_id=order.get("orderId"),
        )
        get_user_manager().log_action(callback.from_user.username or str(callback.from_user.id), "topup_invoice_fk", payment_id)
        return await render_message(
            callback,
            _master_render(
                "TOPUP_FK_CREATED_TEXT",
                "🧾 Счёт создан (FreeKassa)\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nНомер платежа: <code>{payment_id}</code>\n\n1) Нажмите «Оплатить»\n2) После оплаты нажмите «Проверить оплату»",
                amount=amount,
                payment_id=payment_id,
            ),
            _topup_invoice_kb(pay_url, payment_id, "freekassa").as_markup(),
        )

    if provider == "cryptomus":
        cm_cfg = _cryptomus_config()
        if not cm_cfg.get("enabled"):
            return await render_message(
                callback,
                _master_msg("TOPUP_CRYPTOMUS_DISABLED_TEXT", "💳 Пополнение баланса\n━━━━━━━━━━━━━━━━━━━━━━━━\nCryptomus сейчас выключен администратором."),
                get_back_menu_kb(),
            )
        merchant_id = (cm_cfg.get("merchant_id") or "").strip()
        api_key = (cm_cfg.get("api_key") or "").strip()
        if not merchant_id:
            return await render_message(
                callback,
                _master_msg("TOPUP_CRYPTOMUS_MERCHANT_MISSING_TEXT", "❌ Не задан merchant_id Cryptomus\n━━━━━━━━━━━━━━━━━━━━━━━━\nОткройте bot_settings/config.json и заполните:\n<code>payments.cryptomus.merchant_id</code>"),
                get_back_menu_kb(),
            )
        if not api_key:
            return await render_message(
                callback,
                _master_msg("TOPUP_CRYPTOMUS_API_MISSING_TEXT", "❌ Не задан API key Cryptomus\n━━━━━━━━━━━━━━━━━━━━━━━━\nОткройте bot_settings/config.json и заполните:\n<code>payments.cryptomus.api_key</code>"),
                get_back_menu_kb(),
            )
        client = CryptomusClient(
            merchant_id=merchant_id,
            api_key=api_key,
            timeout=int(cm_cfg.get("timeout") or 20),
        )
        payment_id = PaymentLedger.make_payment_id(callback.from_user.id)
        order_id = f"tg_{callback.from_user.id}_{payment_id[-8:]}"
        try:
            invoice = await client.create_invoice(amount_rub=amount, order_id=order_id)
        except CryptomusError as e:
            return await render_message(
                callback,
                _master_render("TOPUP_CRYPTOMUS_CREATE_ERROR_TEXT", "❌ Не удалось создать счёт Cryptomus\n━━━━━━━━━━━━━━━━━━━━━━━━\n{error}", error=e),
                get_back_menu_kb(),
            )

        pay_url = invoice.get("url") or ""
        CryptomusLedger.create(
            payment_id=payment_id,
            user_id=callback.from_user.id,
            amount=amount,
            order_id=order_id,
            invoice_uuid=invoice.get("uuid"),
            pay_url=pay_url,
        )
        get_user_manager().log_action(callback.from_user.username or str(callback.from_user.id), "topup_invoice_cm", payment_id)
        return await render_message(
            callback,
            _master_render(
                "TOPUP_CRYPTOMUS_CREATED_TEXT",
                "🧾 Счёт создан (Cryptomus)\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nНомер платежа: <code>{payment_id}</code>\n\n1) Нажмите «Оплатить»\n2) После оплаты нажмите «Проверить оплату»",
                amount=amount,
                payment_id=payment_id,
            ),
            _topup_invoice_kb(pay_url, payment_id, "cryptomus").as_markup(),
        )

    if provider == "lava":
        lv_cfg = _lava_config()
        if not lv_cfg.get("enabled"):
            return await render_message(
                callback,
                _master_msg("TOPUP_LAVA_DISABLED_TEXT", "LAVA сейчас выключена администратором."),
                get_back_menu_kb(),
            )
        signature = (lv_cfg.get("api_token") or "").strip()
        shop_id = str(lv_cfg.get("shop_id") or "").strip()
        if not signature:
            return await render_message(
                callback,
                _master_msg("TOPUP_LAVA_TOKEN_MISSING_TEXT", "Не задан токен/подпись LAVA.\nЗаполните <code>payments.lava.api_token</code>."),
                get_back_menu_kb(),
            )
        if not shop_id:
            return await render_message(
                callback,
                _master_msg("TOPUP_LAVA_SHOP_ID_MISSING_TEXT", "Не задан shop_id LAVA.\nЗаполните <code>payments.lava.shop_id</code>."),
                get_back_menu_kb(),
            )

        client = LavaClient(signature=signature, timeout=int(lv_cfg.get("timeout") or 20))
        payment_id = LavaLedger.make_payment_id(callback.from_user.id)
        order_id = f"tg_{callback.from_user.id}_{payment_id[-8:]}"
        try:
            response = await client.create_invoice(
                amount_rub=amount,
                order_id=order_id,
                shop_id=shop_id,
                comment=f"Пополнение баланса {callback.from_user.id}",
            )
        except LavaError as e:
            return await render_message(
                callback,
                _master_render("TOPUP_LAVA_CREATE_ERROR_TEXT", "❌ Не удалось создать счёт LAVA\n━━━━━━━━━━━━━━━━━━━━━━━━\n{error}", error=e),
                get_back_menu_kb(),
            )

        invoice = (response or {}).get("data") or {}
        pay_url = str(invoice.get("url") or "")
        invoice_id = invoice.get("id")
        if not pay_url:
            return await render_message(
                callback,
                _master_msg("TOPUP_LAVA_NO_URL_TEXT", "❌ LAVA не вернула ссылку на оплату."),
                get_back_menu_kb(),
            )

        LavaLedger.create(
            payment_id=payment_id,
            user_id=callback.from_user.id,
            amount=amount,
            shop_id=shop_id,
            order_id=order_id,
            invoice_id=str(invoice_id) if invoice_id else None,
            pay_url=pay_url,
        )
        get_user_manager().log_action(callback.from_user.username or str(callback.from_user.id), "topup_invoice_lava", payment_id)
        return await render_message(
            callback,
            _master_render(
                "TOPUP_LAVA_CREATED_TEXT",
                "🧾 Счёт создан (LAVA)\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nНомер платежа: <code>{payment_id}</code>\n\n1) Нажмите «Оплатить»\n2) После оплаты нажмите «Проверить оплату»",
                amount=amount,
                payment_id=payment_id,
            ),
            _topup_invoice_kb(pay_url, payment_id, "lava").as_markup(),
        )

    if provider != "cryptobot":
        return await callback.answer(_master_msg("ALERT_UNKNOWN_PAYMENT_METHOD", "Неизвестный способ оплаты."), show_alert=True)

    cb_cfg = _cryptobot_config()
    if not cb_cfg.get("enabled"):
        return await render_message(
            callback,
            _master_msg("TOPUP_CRYPTOBOT_DISABLED_TEXT", "💳 Пополнение баланса\n━━━━━━━━━━━━━━━━━━━━━━━━\nCryptoBot сейчас выключен администратором."),
            get_back_menu_kb(),
        )
    api_token = (cb_cfg.get("api_token") or "").strip()
    if not api_token:
        return await render_message(
            callback,
            _master_msg("TOPUP_CRYPTOBOT_API_MISSING_TEXT", "💳 Пополнение баланса\n━━━━━━━━━━━━━━━━━━━━━━━━\nНе задан API-токен CryptoBot.\nОбратитесь к администратору."),
            get_back_menu_kb(),
        )

    client = CryptoBotClient(api_token=api_token, timeout=int(cb_cfg.get("timeout") or 20))
    payment_id = PaymentLedger.make_payment_id(callback.from_user.id)
    try:
        invoice = await client.create_invoice(
            amount_rub=amount,
            description=f"Пополнение баланса {callback.from_user.id}",
        )
    except CryptoBotError as e:
        return await render_message(
            callback,
            _master_render("TOPUP_CRYPTOBOT_CREATE_ERROR_TEXT", "❌ Не удалось создать счёт CryptoBot\n━━━━━━━━━━━━━━━━━━━━━━━━\n{error}", error=e),
            get_back_menu_kb(),
        )

    invoice_id = int(invoice.get("invoice_id"))
    pay_url = invoice.get("bot_invoice_url") or invoice.get("pay_url")
    CryptoLedger.create(
        payment_id=payment_id,
        user_id=callback.from_user.id,
        amount=amount,
        invoice_id=invoice_id,
        pay_url=pay_url,
    )
    get_user_manager().log_action(callback.from_user.username or str(callback.from_user.id), "topup_invoice_cb", payment_id)
    await render_message(
        callback,
        _master_render(
            "TOPUP_CRYPTOBOT_CREATED_TEXT",
            "🧾 Счёт создан (CryptoBot)\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nНомер платежа: <code>{payment_id}</code>\n\n1) Нажмите «Оплатить»\n2) После оплаты нажмите «Проверить оплату»",
            amount=amount,
            payment_id=payment_id,
        ),
        _topup_invoice_kb(pay_url, payment_id, "cryptobot").as_markup(),
    )


@router.callback_query(F.data.startswith("topup_custom_amount:"))
async def cb_topup_custom_amount(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_user_available(callback):
        return
    provider = callback.data.split(":", 1)[1]
    if provider not in {"freekassa", "cryptobot", "cryptomus", "lava", "telegram_stars", "admin_transfer"}:
        return await callback.answer(_master_msg("ALERT_UNKNOWN_PAYMENT_METHOD", "Неизвестный способ оплаты."), show_alert=True)
    await state.set_state(PaymentStates.WAITING_TOPUP_CUSTOM_AMOUNT)
    await state.update_data(payment_provider=provider)
    provider_label = (
        "FreeKassa"
        if provider == "freekassa"
        else (
            "CryptoBot"
            if provider == "cryptobot"
            else (
                "LAVA"
                if provider == "lava"
                else ("Telegram Stars" if provider == "telegram_stars" else ("Ручное подтверждение" if provider == "admin_transfer" else "Cryptomus"))
            )
        )
    )
    await render_message(
        callback,
        _master_render(
            "TOPUP_CUSTOM_AMOUNT_TEXT",
            "💳 Пополнение баланса\n━━━━━━━━━━━━━━━━━━━━━━━━\nСпособ: {provider_label}\nВведите сумму пополнения (в рублях).\nМинимальная сумма: 80 ₽\n\nПример: <code>250</code>",
            provider_label=provider_label,
        ),
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("topup_admin_paid:"))
async def cb_topup_admin_paid(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_user_available(callback):
        return
    order_id = callback.data.split(":", 1)[1]
    order = AdminTransferLedger.get(order_id)
    if not order:
        return await callback.answer(_master_msg("ALERT_ORDER_NOT_FOUND", "Заказ не найден."), show_alert=True)
    if int(order.get("user_id", 0)) != int(callback.from_user.id):
        return await callback.answer(_master_msg("ALERT_ORDER_NOT_OWNED", "Этот заказ принадлежит другому пользователю."), show_alert=True)
    if str(order.get("status")) in {"успешно", "отклонён"}:
        return await callback.answer(_master_msg("ALERT_ORDER_ALREADY_PROCESSED", "Этот заказ уже обработан."), show_alert=True)
    await state.set_state(PaymentStates.WAITING_ADMIN_TRANSFER_RECEIPT)
    await state.update_data(admin_transfer_order_id=order_id)
    await render_message(
        callback,
        _master_msg("ALERT_ADMIN_RECEIPT_REQUIRED", "Отправьте PDF чек об оплате"),
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("topup_admin_reject:"))
async def cb_topup_admin_reject(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    order_id = callback.data.split(":", 1)[1]
    order = AdminTransferLedger.get(order_id)
    if not order:
        return await callback.answer(_master_msg("ALERT_ORDER_NOT_FOUND", "Заказ не найден."), show_alert=True)
    if str(order.get("status")) in {"успешно", "отклонён"}:
        return await callback.answer(_master_msg("ALERT_ORDER_ALREADY_PROCESSED_SHORT", "Заказ уже обработан."), show_alert=True)
    await state.set_state(AdminStates.WAITING_TRANSFER_REJECT_REASON)
    await state.update_data(admin_transfer_order_id=order_id)
    await render_message(
        callback,
        _master_msg("ALERT_ADMIN_REJECT_REASON", "Укажите причину отклонения заказа <code>{order_id}</code>:").format(order_id=order_id),
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("topup_admin_confirm:"))
async def cb_topup_admin_confirm(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    order_id = callback.data.split(":", 1)[1]
    order = AdminTransferLedger.get(order_id)
    if not order:
        return await callback.answer(_master_msg("ALERT_ORDER_NOT_FOUND", "Заказ не найден."), show_alert=True)
    if str(order.get("status")) in {"успешно", "отклонён"}:
        return await callback.answer(_master_msg("ALERT_ORDER_ALREADY_PROCESSED_SHORT", "Заказ уже обработан."), show_alert=True)
    await state.set_state(AdminStates.WAITING_TRANSFER_CONFIRM_AMOUNT)
    await state.update_data(admin_transfer_order_id=order_id)
    await render_message(
        callback,
        _master_msg("ALERT_ADMIN_CONFIRM_AMOUNT", "Введите сумму для начисления"),
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("topup_fk_check:"))
async def cb_topup_fk_check(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    payment_id = callback.data.split(":", 1)[1]
    row = PaymentLedger.get(payment_id)
    if not row:
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_FOUND", "Счёт не найден."), show_alert=True)
    if int(row.get("user_id", 0)) != int(callback.from_user.id):
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_OWNED", "Этот счёт принадлежит другому пользователю."), show_alert=True)

    if row.get("credited"):
        user = get_user_manager().get_user(callback.from_user.id)
        return await render_message(
            callback,
            _master_msg(
                "ALERT_PAYMENT_ALREADY_CREDITED",
                "✅ Платёж уже зачислен\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nБаланс: {balance:.2f} ₽",
            ).format(
                amount=float(row.get("amount", 0)),
                balance=float((user or {}).get("balance", 0)),
            ),
            get_back_menu_kb(),
        )

    fk_cfg = _freekassa_config()
    api_key = (fk_cfg.get("api_key") or "").strip()
    if not api_key:
        return await callback.answer(_master_msg("ALERT_API_KEY_FK_MISSING", "API-ключ FreeKassa не задан."), show_alert=True)

    client = FreeKassaClient(
        api_key=api_key,
        shop_id=int(fk_cfg.get("shop_id") or 0),
        timeout=int(fk_cfg.get("timeout") or 20),
    )
    try:
        order = await client.find_order(payment_id=payment_id)
    except FreeKassaError as e:
        return await callback.answer(
            _master_msg("ALERT_PAYMENT_CHECK_ERROR", "Ошибка проверки: {error}").format(error=e),
            show_alert=True,
        )

    if not client.is_paid(order):
        return await callback.answer(_master_msg("ALERT_PAYMENT_NOT_CONFIRMED", "Платёж ещё не подтверждён."), show_alert=True)

    PaymentLedger.mark_paid(payment_id, order)
    row = PaymentLedger.get(payment_id) or row
    if not row.get("credited"):
        user = get_user_manager().add_balance(callback.from_user.id, float(row.get("amount", 0)))
        PaymentLedger.mark_credited(payment_id)
        get_user_manager().log_action(
            callback.from_user.username or str(callback.from_user.id),
            "topup",
            f"+{float(row.get('amount', 0)):.2f} ({payment_id})",
        )
        await _notify_full_admins_topup(
            bot=callback.bot,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            amount_rub=float(row.get("amount", 0)),
            provider="freekassa",
            payment_id=payment_id,
        )
    else:
        user = get_user_manager().get_user(callback.from_user.id)

    await render_message(
        callback,
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Зачислено: +{float(row.get('amount', 0)):.2f} ₽\n"
        f"\u0411\u0430\u043b\u0430\u043d\u0441: {float(user.get('balance', 0)):.2f} \u20BD\n",
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("topup_cb_check:"))
async def cb_topup_cb_check(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    payment_id = callback.data.split(":", 1)[1]
    row = CryptoLedger.get(payment_id)
    if not row:
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_FOUND", "Счёт не найден."), show_alert=True)
    if int(row.get("user_id", 0)) != int(callback.from_user.id):
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_OWNED", "Этот счёт принадлежит другому пользователю."), show_alert=True)
    if row.get("credited"):
        user = get_user_manager().get_user(callback.from_user.id)
        return await render_message(
            callback,
            _master_msg(
                "ALERT_PAYMENT_ALREADY_CREDITED",
                "✅ Платёж уже зачислен\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nБаланс: {balance:.2f} ₽",
            ).format(
                amount=float(row.get("amount", 0)),
                balance=float((user or {}).get("balance", 0)),
            ),
            get_back_menu_kb(),
        )

    cb_cfg = _cryptobot_config()
    token = (cb_cfg.get("api_token") or "").strip()
    if not token:
        return await callback.answer(_master_msg("ALERT_API_TOKEN_CRYPTOBOT_MISSING", "API-токен CryptoBot не задан."), show_alert=True)
    client = CryptoBotClient(api_token=token, timeout=int(cb_cfg.get("timeout") or 20))
    try:
        invoice = await client.get_invoice(invoice_id=int(row.get("invoice_id", 0)))
    except CryptoBotError as e:
        return await callback.answer(
            _master_msg("ALERT_PAYMENT_CHECK_ERROR", "Ошибка проверки: {error}").format(error=e),
            show_alert=True,
        )
    if not client.is_paid(invoice):
        return await callback.answer(_master_msg("ALERT_PAYMENT_NOT_CONFIRMED", "Платёж ещё не подтверждён."), show_alert=True)

    CryptoLedger.mark_paid(payment_id, invoice)
    row = CryptoLedger.get(payment_id) or row
    if not row.get("credited"):
        user = get_user_manager().add_balance(callback.from_user.id, float(row.get("amount", 0)))
        CryptoLedger.mark_credited(payment_id)
        get_user_manager().log_action(
            callback.from_user.username or str(callback.from_user.id),
            "topup",
            f"+{float(row.get('amount', 0)):.2f} ({payment_id}, cryptobot)",
        )
        await _notify_full_admins_topup(
            bot=callback.bot,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            amount_rub=float(row.get("amount", 0)),
            provider="cryptobot",
            payment_id=payment_id,
        )
    else:
        user = get_user_manager().get_user(callback.from_user.id)

    await render_message(
        callback,
        _master_msg(
            "ALERT_PAYMENT_CONFIRMED",
            "✅ Оплата подтверждена\n━━━━━━━━━━━━━━━━━━━━━━━━\nЗачислено: +{amount:.2f} ₽\nБаланс: {balance:.2f} ₽",
        ).format(
            amount=float(row.get("amount", 0)),
            balance=float((user or {}).get("balance", 0)),
        ),
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("topup_cm_check:"))
async def cb_topup_cm_check(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    payment_id = callback.data.split(":", 1)[1]
    row = CryptomusLedger.get(payment_id)
    if not row:
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_FOUND", "Счёт не найден."), show_alert=True)
    if int(row.get("user_id", 0)) != int(callback.from_user.id):
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_OWNED", "Этот счёт принадлежит другому пользователю."), show_alert=True)
    if row.get("credited"):
        user = get_user_manager().get_user(callback.from_user.id)
        return await render_message(
            callback,
            _master_msg(
                "ALERT_PAYMENT_ALREADY_CREDITED",
                "✅ Платёж уже зачислен\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nБаланс: {balance:.2f} ₽",
            ).format(
                amount=float(row.get("amount", 0)),
                balance=float((user or {}).get("balance", 0)),
            ),
            get_back_menu_kb(),
        )

    cm_cfg = _cryptomus_config()
    merchant_id = (cm_cfg.get("merchant_id") or "").strip()
    api_key = (cm_cfg.get("api_key") or "").strip()
    if not merchant_id:
        return await callback.answer(_master_msg("ALERT_CRYPTOMUS_MERCHANT_ID_MISSING", "Не задан merchant_id Cryptomus."), show_alert=True)
    if not api_key:
        return await callback.answer(_master_msg("ALERT_CRYPTOMUS_API_KEY_MISSING", "Не задан API key Cryptomus."), show_alert=True)
    client = CryptomusClient(
        merchant_id=merchant_id,
        api_key=api_key,
        timeout=int(cm_cfg.get("timeout") or 20),
    )
    try:
        payment = await client.payment_info(order_id=str(row.get("order_id")))
    except CryptomusError as e:
        return await callback.answer(
            _master_msg("ALERT_PAYMENT_CHECK_ERROR", "Ошибка проверки: {error}").format(error=e),
            show_alert=True,
        )
    if not client.is_paid(payment):
        return await callback.answer(_master_msg("ALERT_PAYMENT_NOT_CONFIRMED", "Платёж ещё не подтверждён."), show_alert=True)

    CryptomusLedger.mark_paid(payment_id, payment)
    row = CryptomusLedger.get(payment_id) or row
    if not row.get("credited"):
        user = get_user_manager().add_balance(callback.from_user.id, float(row.get("amount", 0)))
        CryptomusLedger.mark_credited(payment_id)
        get_user_manager().log_action(
            callback.from_user.username or str(callback.from_user.id),
            "topup",
            f"+{float(row.get('amount', 0)):.2f} ({payment_id}, cryptomus)",
        )
        await _notify_full_admins_topup(
            bot=callback.bot,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            amount_rub=float(row.get("amount", 0)),
            provider="cryptomus",
            payment_id=payment_id,
        )
    else:
        user = get_user_manager().get_user(callback.from_user.id)

    await render_message(
        callback,
        _master_msg(
            "ALERT_PAYMENT_CONFIRMED",
            "✅ Оплата подтверждена\n━━━━━━━━━━━━━━━━━━━━━━━━\nЗачислено: +{amount:.2f} ₽\nБаланс: {balance:.2f} ₽",
        ).format(
            amount=float(row.get("amount", 0)),
            balance=float((user or {}).get("balance", 0)),
        ),
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("topup_lv_check:"))
async def cb_topup_lv_check(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    payment_id = callback.data.split(":", 1)[1]
    row = LavaLedger.get(payment_id)
    if not row:
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_FOUND", "Счёт не найден."), show_alert=True)
    if int(row.get("user_id", 0)) != int(callback.from_user.id):
        return await callback.answer(_master_msg("ALERT_INVOICE_NOT_OWNED", "Этот счёт принадлежит другому пользователю."), show_alert=True)
    if row.get("credited"):
        user = get_user_manager().get_user(callback.from_user.id)
        return await render_message(
            callback,
            _master_msg(
                "ALERT_PAYMENT_ALREADY_CREDITED",
                "✅ Платёж уже зачислен\n━━━━━━━━━━━━━━━━━━━━━━━━\n💵 Сумма: {amount:.2f} ₽\nБаланс: {balance:.2f} ₽",
            ).format(
                amount=float(row.get("amount", 0)),
                balance=float((user or {}).get("balance", 0)),
            ),
            get_back_menu_kb(),
        )

    lv_cfg = _lava_config()
    signature = (lv_cfg.get("api_token") or "").strip()
    shop_id = str(lv_cfg.get("shop_id") or "").strip()
    if not signature:
        return await callback.answer(_master_msg("ALERT_LAVA_TOKEN_MISSING", "Токен/подпись LAVA не задан."), show_alert=True)
    if not shop_id:
        return await callback.answer(_master_msg("ALERT_LAVA_SHOP_ID_MISSING", "shop_id LAVA не задан."), show_alert=True)

    client = LavaClient(signature=signature, timeout=int(lv_cfg.get("timeout") or 20))
    try:
        result = await client.invoice_status(
            shop_id=shop_id,
            order_id=str(row.get("order_id") or ""),
            invoice_id=str(row.get("invoice_id") or "") or None,
        )
    except LavaError as e:
        return await callback.answer(
            _master_msg("ALERT_PAYMENT_CHECK_ERROR", "Ошибка проверки: {error}").format(error=e),
            show_alert=True,
        )

    invoice = (result or {}).get("data") or {}
    if not client.is_paid(invoice):
        return await callback.answer(_master_msg("ALERT_PAYMENT_NOT_CONFIRMED", "Платёж ещё не подтверждён."), show_alert=True)

    LavaLedger.mark_paid(payment_id, invoice)
    row = LavaLedger.get(payment_id) or row
    if not row.get("credited"):
        user = get_user_manager().add_balance(callback.from_user.id, float(row.get("amount", 0)))
        LavaLedger.mark_credited(payment_id)
        get_user_manager().log_action(
            callback.from_user.username or str(callback.from_user.id),
            "topup",
            f"+{float(row.get('amount', 0)):.2f} ({payment_id}, lava)",
        )
        await _notify_full_admins_topup(
            bot=callback.bot,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            amount_rub=float(row.get("amount", 0)),
            provider="lava",
            payment_id=payment_id,
        )
    else:
        user = get_user_manager().get_user(callback.from_user.id)

    await render_message(
        callback,
        _master_msg(
            "ALERT_PAYMENT_CONFIRMED",
            "✅ Оплата подтверждена\n━━━━━━━━━━━━━━━━━━━━━━━━\nЗачислено: +{amount:.2f} ₽\nБаланс: {balance:.2f} ₽",
        ).format(
            amount=float(row.get("amount", 0)),
            balance=float((user or {}).get("balance", 0)),
        ),
        get_back_menu_kb(),
    )


@router.pre_checkout_query()
async def pre_checkout_stars(pre_checkout_query: PreCheckoutQuery):
    payload = str(pre_checkout_query.invoice_payload or "")
    if not payload.startswith("stars_topup:"):
        return await pre_checkout_query.answer(ok=True)
    payment_id = payload.split(":", 1)[1]
    row = TelegramStarsLedger.get(payment_id)
    if not row:
        return await pre_checkout_query.answer(ok=False, error_message=_master_msg("ALERT_INVOICE_NOT_FOUND", "Счёт не найден."))
    if int(row.get("user_id", 0)) != int(pre_checkout_query.from_user.id):
        return await pre_checkout_query.answer(ok=False, error_message=_master_msg("ALERT_INVOICE_FOREIGN_OWNER", "Счёт принадлежит другому пользователю."))
    if pre_checkout_query.currency != "XTR":
        return await pre_checkout_query.answer(ok=False, error_message=_master_msg("ALERT_INVOICE_INVALID_CURRENCY", "Некорректная валюта счёта."))
    if int(pre_checkout_query.total_amount or 0) != int(row.get("stars_amount", 0)):
        return await pre_checkout_query.answer(ok=False, error_message=_master_msg("ALERT_INVOICE_AMOUNT_CHANGED", "Сумма счёта изменилась. Создайте новый счёт."))
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    payment = message.successful_payment
    if not payment:
        return
    payload = str(payment.invoice_payload or "")
    if not payload.startswith("stars_topup:"):
        return
    payment_id = payload.split(":", 1)[1]
    row = TelegramStarsLedger.get(payment_id)
    if not row:
        return
    if int(row.get("user_id", 0)) != int(message.from_user.id):
        return

    stars_paid = int(row.get("stars_amount") or payment.total_amount or 0)
    amount_rub = float(row.get("amount", 0))

    if row.get("credited"):
        user = get_user_manager().get_user(message.from_user.id) or {}
        return await message.answer(
            _master_msg(
                "ALERT_STARS_PAYMENT_ALREADY_CREDITED",
                "✅ Платёж уже зачислен\n━━━━━━━━━━━━━━━━━━━━━━━━\nОплачено: {stars_paid} ⭐\nЗачислено: +{amount:.2f} ₽\nБаланс: {balance:.2f} ₽\n",
            ).format(
                stars_paid=stars_paid,
                amount=amount_rub,
                balance=float(user.get("balance", 0)),
            )
        )

    TelegramStarsLedger.mark_paid(
        payment_id,
        {
            "currency": payment.currency,
            "total_amount": payment.total_amount,
            "telegram_payment_charge_id": payment.telegram_payment_charge_id,
            "provider_payment_charge_id": payment.provider_payment_charge_id,
        },
    )
    user = get_user_manager().add_balance(message.from_user.id, amount_rub)
    TelegramStarsLedger.mark_credited(payment_id)
    get_user_manager().log_action(
        message.from_user.username or str(message.from_user.id),
        "topup",
        f"+{amount_rub:.2f} ({payment_id}, telegram_stars, {stars_paid}⭐)",
    )
    await _notify_full_admins_topup(
        bot=message.bot,
        user_id=message.from_user.id,
        username=message.from_user.username,
        amount_rub=amount_rub,
        provider="telegram_stars",
        payment_id=payment_id,
        stars_amount=stars_paid,
    )
    await message.answer(
        _master_msg(
            "ALERT_STARS_PAYMENT_CONFIRMED",
            "✅ Оплата подтверждена\n━━━━━━━━━━━━━━━━━━━━━━━━\nОплачено: {stars_paid} ⭐\nЗачислено: +{amount:.2f} ₽\nБаланс: {balance:.2f} ₽\n",
        ).format(
            stars_paid=stars_paid,
            amount=amount_rub,
            balance=float(user.get("balance", 0)),
        )
    )


@router.callback_query((F.data == "stats_menu") | (F.data == "analytics_menu"))
async def cb_stats_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    manager = get_manager()
    await render_message(callback, get_stats_menu_text(manager.get_all(callback.from_user.id)), get_analytics_menu_kb())


@router.callback_query(F.data == "analytics_hourly_menu")
async def cb_analytics_hourly_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    manager = get_manager()
    bots = manager.get_all(callback.from_user.id)
    if not bots:
        return await render_message(
            callback,
            _master_msg("ANALYTICS_HOURLY_EMPTY", "📈 Почасовая аналитика\n━━━━━━━━━━━━━━━━━━━━━━━━\nУ вас пока нет ботов."),
            get_back_menu_kb(),
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    lines = _master_msg("ANALYTICS_HOURLY_MENU_TEXT", "📈 Почасовая аналитика\n━━━━━━━━━━━━━━━━━━━━━━━━\nВыберите бота и период:").splitlines()
    for bot in bots:
        title = bot.get("tg_username") or bot["uuid"][:8]
        kb.button(text=f"{title} · 24ч", callback_data=f"analytics_hourly:{bot['uuid']}:1")
        kb.button(text=f"{title} · 7д", callback_data=f"analytics_hourly:{bot['uuid']}:7")
    kb.button(text=_master_msg("ANALYTICS_BACK_TEXT", "⬆️ Назад"), callback_data="analytics_menu")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


@router.callback_query(F.data.startswith("analytics_hourly:"))
async def cb_analytics_hourly(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    _, uuid_value, days_raw = callback.data.split(":", 2)
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)

    try:
        days = int(days_raw)
    except ValueError:
        days = 1
    days = 7 if days == 7 else 1
    stats = manager.get_hourly_analytics(uuid_value, days=days)
    max_deals = max((row["deals"] for row in stats.values()), default=0)
    max_messages = max((row["messages"] for row in stats.values()), default=0)

    lines = [
        f"📈 Почасовая аналитика ({_master_msg('ANALYTICS_HOURLY_PERIOD_7D', '7 дней') if days == 7 else _master_msg('ANALYTICS_HOURLY_PERIOD_24H', '24 часа')})",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        f"Бот: {bot.get('tg_username') or bot['uuid'][:8]}",
        "",
    ]
    for hour in range(24):
        row = stats.get(hour, {"deals": 0, "messages": 0})
        deals = row["deals"]
        messages = row["messages"]
        deals_bar = "в–€" * int((deals / max_deals) * 8) if max_deals else ""
        msg_bar = "в–'" * int((messages / max_messages) * 8) if max_messages else ""
        lines.append(f"{hour:02d}:00 | D {deals:2d} {deals_bar:<8} | M {messages:2d} {msg_bar:<8}")

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    if days == 1:
        kb.button(text="Показать за 7 дней", callback_data=f"analytics_hourly:{uuid_value}:7")
    else:
        kb.button(text="Показать за 24ч", callback_data=f"analytics_hourly:{uuid_value}:1")
    kb.button(text="◀️ К списку", callback_data="analytics_hourly_menu")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


@router.callback_query(F.data == "analytics_top_menu")
async def cb_analytics_top_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    manager = get_manager()
    bots = manager.get_all(callback.from_user.id)
    if not bots:
        return await render_message(
            callback,
            _master_msg("ANALYTICS_TOP_EMPTY", "🏆 Топ товаров\n━━━━━━━━━━━━━━━━━━━━━━━━\nУ вас пока нет ботов."),
            get_back_menu_kb(),
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    lines = ["🏆 Топ товаров", "━━━━━━━━━━━━━━━━━━━━━━━━", "Выберите бота и период:"]
    for bot in bots:
        title = bot.get("tg_username") or bot["uuid"][:8]
        kb.button(text=f"{title} · 7д", callback_data=f"analytics_top:{bot['uuid']}:7")
        kb.button(text=f"{title} · 30д", callback_data=f"analytics_top:{bot['uuid']}:30")
    kb.button(text="⬆️ Назад", callback_data="analytics_menu")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


@router.callback_query(F.data.startswith("analytics_top:"))
async def cb_analytics_top(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    _, uuid_value, days_raw = callback.data.split(":", 2)
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)

    try:
        days = int(days_raw)
    except ValueError:
        days = 30
    days = 7 if days == 7 else 30

    rows = manager.get_top_items(uuid_value, days=days, limit=10)
    lines = [
        f"🏆 Топ товаров ({days} дней)",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        f"Бот: {bot.get('tg_username') or bot['uuid'][:8]}",
    ]
    if not rows:
        lines.append("Сделок за период нет.")
    else:
        for index, row in enumerate(rows, start=1):
            lines.append(
                f"{index}. {row['item_name']}\n"
                f"   Сделок: {row['deals']} | Выручка: {float(row['revenue']):.2f} ₽"
            )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    if days == 7:
        kb.button(text="Показать за 30д", callback_data=f"analytics_top:{uuid_value}:30")
    else:
        kb.button(text="Показать за 7д", callback_data=f"analytics_top:{uuid_value}:7")
    kb.button(text="◀️ К списку", callback_data="analytics_top_menu")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


@router.callback_query(F.data.startswith("events_bot:"))
async def cb_events_bot(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    uuid_value = callback.data.split(":", 1)[1]
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)

    events = manager.get_recent_events(uuid_value, limit=25)
    lines = [
        f"🤖 Название бота: {bot.get('tg_username') or bot['uuid'][:8]}",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
    ]
    if not events:
        lines.append("Событий пока нет.")
    else:
        for event in reversed(events):
            at = event.get("at", "-")
            event_type = event.get("type", "event")
            username = event.get("username") or "-"
            item_name = event.get("item_name")
            deal_id = event.get("deal_id")
            text = event.get("text")

            line = f"{at} | {event_type} | {username}"
            if deal_id:
                line += f" | deal {deal_id}"
            if item_name:
                line += f" | {item_name}"
            if text:
                line += f" | {(text or '').replace(chr(10), ' ')[:60]}"
            lines.append(line)

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data=f"events_bot:{uuid_value}")
    kb.button(text="◀️ К боту", callback_data=SelectBot(uuid=uuid_value).pack())
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


@router.callback_query(F.data.startswith("proxy_settings:"))
async def cb_proxy_settings(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    uuid_value = callback.data.split(":", 1)[1]
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await _render_proxy_settings(callback, bot)


@router.callback_query(F.data.startswith("proxy_add:"))
async def cb_proxy_add(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_user_available(callback):
        return
    uuid_value = callback.data.split(":", 1)[1]
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)

    await state.set_state(ProxyStates.WAITING_NEW_PROXY)
    await state.update_data(proxy_bot_uuid=uuid_value)
    await render_message(
        callback,
        _master_msg(
            "PROMPT_PROXY_ADD",
            "➕ Добавление прокси\n━━━━━━━━━━━━━━━━━━━━━━━━\nОтправьте прокси в формате:\n<code>user:pass@ip:port</code>\nили\n<code>ip:port</code>",
        ),
        get_back_menu_kb(),
    )


@router.callback_query(F.data.startswith("proxy_rotate:"))
async def cb_proxy_rotate(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    uuid_value = callback.data.split(":", 1)[1]
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)

    switched = manager.try_switch_proxy(uuid_value)
    if not switched:
        return await callback.answer(_master_msg("ALERT_WORKING_PROXY_NOT_FOUND", "Не удалось подобрать рабочий прокси."), show_alert=True)
    else:
        if bot.get("is_active"):
            await manager.restart(uuid_value)
    updated_bot = manager.get(uuid_value)
    if updated_bot:
        await _render_proxy_settings(callback, updated_bot)


@router.callback_query(F.data.startswith("proxy_del_last:"))
async def cb_proxy_del_last(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    uuid_value = callback.data.split(":", 1)[1]
    manager = get_manager()
    bot = _owned_bot(callback.from_user.id, manager.get(uuid_value))
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)

    proxy_list = [item for item in bot.get("proxy_list", []) if item]
    if not proxy_list:
        return await callback.answer(_master_msg("ALERT_PROXY_LIST_EMPTY", "Список прокси пуст."), show_alert=True)
    deleted_index = len(proxy_list) - 1
    deleted_proxy = proxy_list[deleted_index]
    manager.remove_proxy(uuid_value, deleted_index)

    updated_bot = manager.get(uuid_value)
    if bot.get("is_active") and updated_bot and deleted_proxy == bot.get("proxy"):
        await manager.restart(uuid_value)
        updated_bot = manager.get(uuid_value)
    if updated_bot:
        await _render_proxy_settings(callback, updated_bot)


@router.callback_query(F.data == "feedback_menu")
async def cb_feedback_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    await render_message(callback, get_feedback_text(), get_back_menu_kb())


@router.callback_query(F.data == "info_menu")
async def cb_info_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    await render_message(callback, get_help_text(), get_info_menu_kb())


@router.callback_query(F.data == "trial_period")
async def cb_trial_period(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    user_manager = get_user_manager()
    user = user_manager.ensure_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)

    if user_manager.has_active_tariff(callback.from_user.id) or bool(user.get("trial_used")):
        return await callback.answer(_master_msg("ALERT_TRIAL_UNAVAILABLE", "Пробный период недоступен."), show_alert=True)

    if not await _is_trial_channel_subscribed(callback):
        return await render_message(
            callback,
            "❌ Для получения пробного периода нужно подписаться на наш канал.\n\n"
            "После подписки нажмите кнопку снова.",
            _trial_subscribe_kb(),
        )

    updated = user_manager.activate_tariff(callback.from_user.id, "month", trial_days=1, charge=False)
    user_manager.update_user(
        callback.from_user.id,
        trial_used=True,
        auto_renew=False,
        tariff=updated["tariff"],
        tariff_expires=updated["tariff_expires"],
    )
    user_manager.log_action(callback.from_user.username or str(callback.from_user.id), "trial_act", "1_day")
    expires_at = datetime.fromisoformat(updated["tariff_expires"]).strftime("%d.%m.%Y %H:%M")
    await render_message(
        callback,
        "🎁 Пробный период активирован!\n\n"
        f"Тариф активен до: {expires_at}\n"
        "Срок: 1 день\n\n"
        "Попробуй все возможности Raidex бесплатно!",
        get_back_menu_kb(),
    )


@router.callback_query(F.data == "tariff_menu")
async def cb_tariff_menu(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    user_manager = get_user_manager()
    user = user_manager.get_user(callback.from_user.id)
    text = get_tariff_menu_text(float(user["balance"]))
    text += f"\n\n🔄 Автопродление: {'включено' if user.get('auto_renew', True) else 'выключено'}"
    await render_message(callback, text, get_tariff_menu_kb(bool(user.get("auto_renew", True))))


@router.callback_query(F.data == "auto_renew_toggle")
async def cb_auto_renew_toggle(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    user_manager = get_user_manager()
    user = user_manager.get_user(callback.from_user.id)
    new_state = not bool(user.get("auto_renew", True))
    user_manager.update_user(callback.from_user.id, auto_renew=new_state)
    user_manager.log_action(callback.from_user.username or str(callback.from_user.id), "auto_renew", str(new_state))
    text = get_tariff_menu_text(float(user.get("balance", 0)))
    text += f"\n\n🔄 Автопродление: {'включено' if new_state else 'выключено'}"
    await render_message(callback, text, get_tariff_menu_kb(new_state))


@router.callback_query(F.data.startswith("tariff:"))
async def cb_tariff_pick(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    tariff_key = callback.data.split(":", 1)[1]
    user_manager = get_user_manager()
    user = user_manager.get_user(callback.from_user.id)
    tariff = TARIFFS[tariff_key]
    if float(user["balance"]) < tariff["price"]:
        return await render_message(
            callback,
            "❌ Недостаточно средств\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Для активации тарифа нужно {tariff['price']:.0f} ₽.\n"
            f"Ваш баланс: {float(user['balance']):.2f} ₽",
            get_need_tariff_kb(),
        )
    await render_message(
        callback,
        get_tariff_confirm_text(
            tariff["title"],
            tariff["days"],
            tariff["price"],
            float(user["balance"]),
        ),
        get_tariff_confirm_kb(tariff_key),
    )


@router.callback_query(F.data.startswith("tariff_confirm:"))
async def cb_tariff_confirm(callback: CallbackQuery):
    if not await _ensure_user_available(callback):
        return
    tariff_key = callback.data.split(":", 1)[1]
    user_manager = get_user_manager()
    user = user_manager.activate_tariff(callback.from_user.id, tariff_key)
    tariff = TARIFFS[tariff_key]
    if user.get("referred_partner_id"):
        get_partners_manager().register_payment(
            user["referred_partner_id"],
            user,
            tariff["price"],
        )
    user_manager.log_action(callback.from_user.username or str(callback.from_user.id), "tariff_act", tariff_key)
    await render_message(
        callback,
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Тариф: {tariff['title']}\n"
        f"Активен до: {user['tariff_expires'][:10]}\n"
        f"Остаток: {float(user['balance']):.2f} ₽",
        get_back_menu_kb(),
    )


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    if _admin_level(callback.from_user.id) == "limited":
        return await _render_admin_limited(callback)
    from collections import Counter
    import re

    manager = get_manager()
    user_manager = get_user_manager()
    users = list(user_manager.all_users().values())
    bots = manager.load_all_bots()
    logs = user_manager.get_actions(limit=0)
    now = datetime.now()
    week_border = now - timedelta(days=7)
    day_border = now - timedelta(hours=24)

    def _safe_dt(value: str | None):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    new_week = sum(1 for user in users if (_safe_dt(user.get("registered_at")) or datetime.min) >= week_border)
    active_7d = sum(1 for user in users if (_safe_dt(user.get("last_active")) or datetime.min) >= week_border)
    users_with_balance = [user for user in users if float(user.get("balance", 0)) > 0]
    avg_balance = (
        sum(float(user.get("balance", 0)) for user in users_with_balance) / len(users_with_balance)
        if users_with_balance
        else 0.0
    )
    trials = sum(1 for user in users if user.get("trial_used"))
    banned = sum(1 for user in users if user.get("is_banned"))

    active_tariff_users = [user for user in users if user_manager.has_active_tariff(int(user["tg_id"]))]
    tariff_counts = Counter((user.get("tariff") or "none") for user in active_tariff_users)
    auto_renew_enabled = sum(1 for user in users if user.get("auto_renew", True))
    expires_7d = 0
    for user in active_tariff_users:
        dt = _safe_dt(user.get("tariff_expires"))
        if dt and now <= dt <= now + timedelta(days=7):
            expires_7d += 1

    active_bots = [bot for bot in bots if bot.get("is_active")]
    playerok_bots = sum(1 for bot in bots if "playerok" in (bot.get("platforms") or []))
    funpay_bots = sum(1 for bot in bots if "funpay" in (bot.get("platforms") or []))
    owners_count = len({bot.get("owner_tg_id") for bot in bots if bot.get("owner_tg_id")})

    earned = 0.0
    for row in logs:
        if row.get("action") != "tariff_act":
            continue
        key = row.get("result")
        if key in TARIFFS:
            earned += float(TARIFFS[key]["price"])

    topups = [row for row in logs if row.get("action") == "topup"]
    topup_sum = 0.0
    for row in topups:
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", row.get("result", ""))
        if match:
            topup_sum += float(match.group(1))

    refunds = sum(1 for row in logs if row.get("action") in {"refund", "tariff_refund"})
    admin_actions_24h = sum(
        1
        for row in logs
        if row.get("actor") == "admin"
        and (_safe_dt(row.get("at")) or datetime.min) >= day_border
    )
    broadcasts = sum(1 for row in logs if row.get("action") == "broadcast")

    timestamps = [_safe_dt(row.get("at")) for row in logs if row.get("at")]
    timestamps = [item for item in timestamps if item]
    uptime_days = (now - min(timestamps)).days if timestamps else 0

    await render_message(
        callback,
        "📈 ADMIN | Статистика\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: {len(users)} (🆕 +{new_week} за 7 дней)\n"
        f"🟢 Активных за 7 дней: {active_7d}\n"
        f"💳 С балансом: {len(users_with_balance)} (средний: {avg_balance:.0f}₽)\n"
        f"🧪 Пробных: {trials}\n"
        f"🚫 В бане: {banned}\n\n"
        f"💎 Активных тарифов: {len(active_tariff_users)}\n"
        f"🔁 Автопродление: {auto_renew_enabled}/{len(users)}\n"
        f"⏳ стекает за 7 дней: {expires_7d}\n\n"
        f"🤖 Дочерних ботов: {len(bots)}\n"
        f"✅ Активных ботов: {len(active_bots)}\n"
        f"🟦 PlayerOK: {playerok_bots} | 🟠 FunPay: {funpay_bots}\n"
        f"👤 Владельцев: {owners_count}/{len(users)}\n\n"
        f"💰 Заработано: {earned:.0f}₽\n"
        f"↩️ Возвратов: {refunds}\n"
        f"💳 Пополнения: {len(topups)} (+{topup_sum:.0f}₽)\n\n"
        f"🛠 Действий админа (24ч): {admin_actions_24h}\n"
        f"📣 Рассылки: {broadcasts}\n"
        f"🕒 Время работы: {uptime_days} дней",
        _admin_back_kb(),
    )


@router.callback_query(F.data == "admin_partner_my_stats")
async def cb_admin_partner_my_stats(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return

    partner = _partner_by_tg_id(callback.from_user.id)
    if not partner:
        return await render_message(
            callback,
            "\U0001F4CA \u041C\u043E\u044F \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "\u041F\u0430\u0440\u0442\u043D\u0451\u0440\u0441\u043A\u0438\u0439 \u043F\u0440\u043E\u0444\u0438\u043B\u044C \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D.",
            _admin_back_kb(),
        )

    stats = get_partners_manager().stats(partner)
    avg_income_per_ref = (float(stats["total_earned"]) / float(stats["total_users"])) if stats["total_users"] else 0.0
    top_ref = stats["top_ref_name"] or "-"
    waiting_payout = float(stats["available"])
    text = (
        "\U0001F4CA \u041C\u043E\u044F \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001F465 \u041F\u0440\u0438\u0433\u043B\u0430\u0448\u0435\u043D\u043E \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0435\u0439: {stats['total_users']}\n"
        f"\U0001F7E2 \u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0445 \u0440\u0435\u0444\u0435\u0440\u0430\u043B\u043E\u0432: {stats['paid_users']}\n"
        f"\U0001F4B3 \u041E\u043F\u043B\u0430\u0442\u0438\u0432\u0448\u0438\u0445 \u0440\u0435\u0444\u0435\u0440\u0430\u043B\u043E\u0432: {stats['paid_users']}\n"
        f"\U0001F4C8 \u041A\u043E\u043D\u0432\u0435\u0440\u0441\u0438\u044F \u0432 \u043E\u043F\u043B\u0430\u0442\u0443: {stats['conversion']:.2f}%\n"
        f"\U0001F4B0 \u0417\u0430\u0440\u0430\u0431\u043E\u0442\u0430\u043D\u043E: {stats['total_earned']:.2f}\u20BD\n"
        f"\U0001F4B8 \u0421\u0440\u0435\u0434\u043D\u0438\u0439 \u0434\u043E\u0445\u043E\u0434 \u0441 1 \u0440\u0435\u0444\u0435\u0440\u0430\u043B\u0430: {avg_income_per_ref:.2f}\u20BD\n"
        f"\U0001F4B8 \u0412\u0441\u0435\u0433\u043E \u0432\u044B\u043F\u043B\u0430\u0447\u0435\u043D\u043E \u043F\u0430\u0440\u0442\u043D\u0451\u0440\u0443: {stats['total_paid_out']:.2f}\u20BD\n"
        f"\u23F3 \u041E\u0436\u0438\u0434\u0430\u0435\u0442 \u0432\u044B\u043F\u043B\u0430\u0442\u044B: {waiting_payout:.2f}\u20BD\n"
        f"\U0001F3E6 \u0414\u043E\u0441\u0442\u0443\u043F\u043D\u043E \u043A \u0432\u044B\u0432\u043E\u0434\u0443: {stats['available']:.2f}\u20BD\n"
        f"\U0001F551 \u0414\u043E\u0445\u043E\u0434 \u0437\u0430 7 \u0434\u043D\u0435\u0439: {stats['revenue_7d']:.2f}\u20BD\n"
        f"\U0001F5D3 \u0414\u043E\u0445\u043E\u0434 \u0437\u0430 30 \u0434\u043D\u0435\u0439: {stats['revenue_30d']:.2f}\u20BD\n"
        f"\U0001F3C6 \u041B\u0443\u0447\u0448\u0438\u0439 \u0440\u0435\u0444\u0435\u0440\u0430\u043B: {top_ref}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="\u25C0\uFE0F \u041D\u0430\u0437\u0430\u0434", callback_data="admin_panel")
    kb.adjust(1)
    await render_message(callback, text, kb.as_markup())


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    users = list(get_user_manager().all_users().values())
    users.sort(key=lambda x: x.get("registered_at") or "", reverse=True)
    if not users:
        text = "\U0001F465 ADMIN | \u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442."
    else:
        lines = ["\U0001F465 ADMIN | \u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438", "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"]
        for idx, user in enumerate(users[:20], start=1):
            uname = user.get("username") or str(user["tg_id"])
            tariff = tariff_title_ru(user.get("tariff"))
            lines.append(f"{idx}. {uname} | {tariff} | {float(user.get('balance', 0)):.2f} \u20bd")
        if len(users) > 20:
            lines.append(f"... \u0438 \u0435\u0449\u0451 {len(users) - 20}")
        text = "\n".join(lines)
    if users:
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        kb = InlineKeyboardBuilder()
        for user in users[:20]:
            name = user.get("username") or str(user["tg_id"])
            kb.button(text=name[:28], callback_data=f"admin_user_profile:{user['tg_id']}")
        kb.button(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="admin_panel")
        kb.adjust(1)
        await render_message(callback, text, kb.as_markup())
    else:
        await render_message(callback, text, _admin_back_kb())


@router.callback_query(F.data == "admin_sessions")
async def cb_admin_sessions(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    users = list(get_user_manager().all_users().values())
    now = datetime.now()
    online = []
    for user in users:
        last_active = user.get("last_active")
        if not last_active:
            continue
        try:
            dt = datetime.fromisoformat(last_active)
        except Exception:
            continue
        if dt > now - timedelta(minutes=15):
            online.append(user)
    text = (
        "📟 ADMIN | Активные сессии\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Пользователей онлайн (15 мин): {len(online)}"
    )
    await render_message(callback, text, _admin_back_kb())


@router.callback_query(F.data == "admin_logs")
async def cb_admin_logs(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    logs = get_user_manager().get_actions(limit=10)
    if not logs:
        text = "📋 ADMIN | Логи действий\n━━━━━━━━━━━━━━━━━━━━━━━━\nЛоги пока пусты."
    else:
        lines = ["📋 ADMIN | Логи действий", "━━━━━━━━━━━━━━━━━━━━━━━━"]
        for row in logs[-10:][::-1]:
            lines.append(f"{row['at']} | {row['actor']} | {row['action']} | {row['result']}")
        text = "\n".join(lines)
    await render_message(callback, text, _admin_back_kb())


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    users = list(get_user_manager().all_users().values())
    active7 = 0
    tariff = 0
    no_tariff = 0
    border = datetime.now() - timedelta(days=7)
    user_manager = get_user_manager()
    for user in users:
        if user.get("last_active") and datetime.fromisoformat(user["last_active"]) >= border:
            active7 += 1
        if user_manager.has_active_tariff(int(user["tg_id"])):
            tariff += 1
        else:
            no_tariff += 1

    kb = InlineKeyboardBuilder()
    kb.button(text=f"👥 Всем ({len(users)})", callback_data="admin_broadcast_audience:all")
    kb.button(text=f"✓ Активным 7Рґ ({active7})", callback_data="admin_broadcast_audience:active7")
    kb.button(text=f"💎 С тарифом ({tariff})", callback_data="admin_broadcast_audience:tariff")
    kb.button(text=f"❌ Без тарифа ({no_tariff})", callback_data="admin_broadcast_audience:no_tariff")
    kb.button(text="⬆️ Назад", callback_data="admin_panel")
    kb.adjust(1)
    await render_message(
        callback,
        "📢 Рассылка\n━━━━━━━━━━━━━━━━━━━━━━━━\nВыберите аудиторию:",
        kb.as_markup(),
    )


@router.callback_query(F.data == "admin_export_csv")
async def cb_admin_export_csv(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    users = list(get_user_manager().all_users().values())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tg_id",
            "username",
            "first_name",
            "balance",
            "tariff",
            "tariff_expires",
            "is_banned",
            "registered_at",
            "last_active",
        ]
    )
    for user in users:
        writer.writerow(
            [
                user.get("tg_id"),
                user.get("username"),
                user.get("first_name"),
                user.get("balance"),
                user.get("tariff"),
                user.get("tariff_expires"),
                user.get("is_banned"),
                user.get("registered_at"),
                user.get("last_active"),
            ]
        )
    data = output.getvalue().encode("utf-8-sig")
    file = BufferedInputFile(data, filename=f"users_export_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv")
    await callback.message.answer_document(file, caption=f"📤 Экспорт готов\nЗаписей: {len(users)}")
    await callback.answer()


@router.callback_query(F.data == "admin_maintenance_on")
async def cb_admin_maintenance_on(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_manager = get_user_manager()
    user_manager.set_system(
        maintenance_mode=True,
        maintenance_started_at=datetime.now().isoformat(timespec="seconds"),
        maintenance_resume_uuids=[bot["uuid"] for bot in get_manager().load_all_bots() if bot.get("is_active")],
    )
    user_manager.log_action("admin", "maintenance", "on")
    manager = get_manager()
    bots = manager.load_all_bots()
    for bot in bots:
        await manager.stop(bot["uuid"])
    for user in user_manager.all_users().values():
        if int(user["tg_id"]) == callback.from_user.id:
            continue
        try:
            await callback.bot.send_message(
                int(user["tg_id"]),
                "🔧 Технические работы\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Мы временно приостанавливаем работу бота для обслуживания.",
            )
        except Exception:
            pass
    await _render_admin_panel(callback)


@router.callback_query(F.data == "admin_maintenance_off")
async def cb_admin_maintenance_off(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_manager = get_user_manager()
    system = user_manager.get_system()
    resume_uuids = list(system.get("maintenance_resume_uuids") or [])
    user_manager.set_system(
        maintenance_mode=False,
        maintenance_started_at=None,
        maintenance_resume_uuids=[],
    )
    user_manager.log_action("admin", "maintenance", "off")
    manager = get_manager()
    for uuid_value in resume_uuids:
        await manager.start(uuid_value)
    for user in user_manager.all_users().values():
        if int(user["tg_id"]) == callback.from_user.id:
            continue
        try:
            await callback.bot.send_message(
                int(user["tg_id"]),
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Бот снова доступен.",
            )
        except Exception:
            pass
    await _render_admin_panel(callback)


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    await _render_admin_panel(callback)


@router.callback_query(F.data.startswith("admin_user_profile:"))
async def cb_admin_user_profile(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_id = int(callback.data.split(":", 1)[1])
    await _render_admin_user_profile(callback, user_id)


@router.callback_query(F.data.startswith("admin_user_ban:"))
async def cb_admin_user_ban(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_id = int(callback.data.split(":", 1)[1])
    user_manager = get_user_manager()
    user = user_manager.get_user(user_id)
    if not user:
        return await callback.answer(_master_msg("ALERT_USER_NOT_FOUND", "Пользователь не найден"), show_alert=True)
    user_manager.update_user(user_id, is_banned=True)
    user_manager.log_action("admin", "ban", str(user_id))
    for bot in get_manager().get_all(user_id):
        await get_manager().stop(bot["uuid"])
    try:
        await callback.bot.send_message(
            user_id,
            "🚫 Доступ заблокирован\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Ваш аккаунт заблокирован администратором.",
        )
    except Exception:
        pass
    await _render_admin_user_profile(callback, user_id)


@router.callback_query(F.data.startswith("admin_user_unban:"))
async def cb_admin_user_unban(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_id = int(callback.data.split(":", 1)[1])
    user_manager = get_user_manager()
    if not user_manager.get_user(user_id):
        return await callback.answer(_master_msg("ALERT_USER_NOT_FOUND", "Пользователь не найден"), show_alert=True)
    user_manager.update_user(user_id, is_banned=False)
    user_manager.log_action("admin", "unban", str(user_id))
    try:
        await callback.bot.send_message(user_id, "✓ Ограничения сняты. Доступ Рє боту восстановлен.")
    except Exception:
        pass
    await _render_admin_user_profile(callback, user_id)


@router.callback_query(F.data.startswith("admin_user_trial:"))
async def cb_admin_user_trial(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_id = int(callback.data.split(":", 1)[1])
    user_manager = get_user_manager()
    user = user_manager.get_user(user_id)
    if not user:
        return await callback.answer(_master_msg("ALERT_USER_NOT_FOUND", "Пользователь не найден"), show_alert=True)
    if user.get("trial_used"):
        return await callback.answer(_master_msg("ALERT_TRIAL_ALREADY_USED", "Пробный период уже использован."), show_alert=True)
    updated = user_manager.activate_tariff(user_id, "month", trial_days=3, charge=False)
    user_manager.update_user(user_id, trial_used=True, tariff=updated["tariff"], tariff_expires=updated["tariff_expires"])
    user_manager.log_action("admin", "trial", str(user_id))
    try:
        await callback.bot.send_message(
            user_id,
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Тариф: {tariff_title_ru(updated.get('tariff'))}\n"
            f"До: {updated['tariff_expires']}",
        )
    except Exception:
        pass
    await _render_admin_user_profile(callback, user_id)


@router.callback_query(F.data.startswith("admin_topup:"))
async def cb_admin_topup(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    user_id = int(callback.data.split(":", 1)[1])
    user = get_user_manager().get_user(user_id)
    if not user:
        return await callback.answer(_master_msg("ALERT_USER_NOT_FOUND", "Пользователь не найден"), show_alert=True)

    await state.set_state(AdminStates.WAITING_TOPUP_AMOUNT)
    await state.update_data(admin_target_user_id=user_id)
    await render_message(
        callback,
        "💰 Установка баланса\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Пользователь: {user.get('username') or user_id}\n"
        f"Текущий баланс: {float(user.get('balance', 0)):.2f} ₽\n"
        "Введите новое значение баланса (например 1000):",
        _admin_back_kb(),
    )


@router.callback_query(F.data.startswith("admin_user_modules:"))
async def cb_admin_user_modules(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_id = int(callback.data.split(":", 1)[1])
    await _render_admin_user_modules(callback, user_id)


@router.callback_query(F.data.startswith("admin_toggle_module:"))
async def cb_admin_toggle_module(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    _, _, user_id_raw, module_key = callback.data.split(":", 3)
    user_id = int(user_id_raw)
    if module_key not in ADMIN_GRANTABLE_MODULES:
        return await callback.answer("Неизвестный модуль", show_alert=True)

    user_manager = get_user_manager()
    user = user_manager.get_user(user_id)
    if not user:
        return await callback.answer(_master_msg("ALERT_USER_NOT_FOUND", "Пользователь не найден"), show_alert=True)

    owned = list(user.get("modules_owned") or [])
    if module_key in owned:
        owned = [item for item in owned if item != module_key]
        action_name = "revoke_module"
        notify_text = f"Администратор забрал у вас модуль {ADMIN_GRANTABLE_MODULES[module_key]}."
    else:
        owned.append(module_key)
        owned = sorted(set(owned))
        action_name = "grant_module"
        notify_text = f"Администратор выдал вам модуль {ADMIN_GRANTABLE_MODULES[module_key]}."

    user_manager.update_user(user_id, modules_owned=owned)
    await _sync_user_modules_to_bots(user_id, owned)
    user_manager.log_action("admin", action_name, f"{user_id}:{module_key}")

    try:
        await callback.bot.send_message(
            user_id,
            "🔌 Обновлены права на модули\n━━━━━━━━━━━━━━━━━━━━━━━━\n" + notify_text,
        )
    except Exception:
        pass

    await _render_admin_user_modules(callback, user_id)


@router.callback_query(F.data.startswith("admin_user_bots:"))
async def cb_admin_user_bots(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    user_id = int(callback.data.split(":", 1)[1])
    await _render_admin_user_bots(callback, user_id)


@router.callback_query(F.data.startswith("admin_force_stop:"))
async def cb_admin_force_stop(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    _, payload = callback.data.split(":", 1)
    uuid_value, user_id = payload.split(":")
    user_id = int(user_id)
    bot = get_manager().get(uuid_value)
    if not bot:
        return await callback.answer(_master_msg("ALERT_BOT_NOT_FOUND", "Бот не найден"), show_alert=True)
    await get_manager().stop(uuid_value)
    get_user_manager().log_action("admin", "force_stop", uuid_value)
    try:
        await callback.bot.send_message(
            user_id,
            "⛔ Ваш бот остановлен администратором\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Бот {bot.get('tg_username') or bot['uuid'][:8]} остановлен.",
        )
    except Exception:
        pass
    await _render_admin_user_bots(callback, user_id)


@router.callback_query(F.data.startswith("admin_broadcast_audience:"))
async def cb_admin_broadcast_audience(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    audience = callback.data.split(":", 1)[1]
    await state.set_state(AdminStates.WAITING_BROADCAST_TEXT)
    await state.update_data(broadcast_audience=audience)
    await render_message(
        callback,
        "📢 Текст рассылки\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Отправьте текст сообщения для рассылки.\n"
        "Поддерживается HTML.",
        _admin_back_kb(),
    )
async def _render_admin_partners(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    partners = get_partners_manager().all_partners()
    kb = InlineKeyboardBuilder()
    lines = [
        "🤝 Партнёры",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if not partners:
        lines.append("Партнёров пока нет.")
    else:
        for index, partner in enumerate(partners, start=1):
            stats = get_partners_manager().stats(partner)
            lines.append(
                f"{index}. {partner['nickname']} | "
                f"{stats['total_users']} приведено | "
                f"{stats['total_earned']:.2f} ₽ заработано"
            )
            kb.button(text=partner["nickname"], callback_data=f"admin_partner_open:{partner['id']}")
    kb.button(text="➕ Создать реф ссылку", callback_data="admin_partner_create")
    kb.button(text="⬅️ Назад", callback_data="admin_panel")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


async def _render_partner_page(callback: CallbackQuery, partner_id: str):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    partners_manager = get_partners_manager()
    partner = partners_manager.get_by_id(partner_id)
    if not partner:
        return await callback.answer(_master_msg("ALERT_PARTNER_NOT_FOUND", "Партнёр не найден."), show_alert=True)
    stats = partners_manager.stats(partner)
    text = (
        f"🤝 Партнёр {partner['nickname']}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Ник: {partner['nickname']}\n"
        f"Username: {partner.get('username') or '-'}\n"
        f"Telegram ID: {partner.get('tg_id') or '-'}\n"
        f"Реферальная ссылка: {partner['referral_link']}\n"
        f"Привёл людей: {stats['total_users']}\n"
        f"Оплатили тариф: {stats['paid_users']}\n"
        f"Общая сумма оплат: {stats['total_revenue']:.2f} ₽\n"
        f"Заработал: {stats['total_earned']:.2f} ₽\n"
        f"Выплачено: {stats['total_paid_out']:.2f} ₽\n"
        f"Доступно к выплате: {stats['available']:.2f} ₽\n"
        f"Текущий процент: {stats['percent']}%"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Список рефералов", callback_data=f"admin_partner_refs:{partner['id']}")
    kb.button(text="Указать Telegram ID", callback_data=f"admin_partner_set_id:{partner['id']}")
    kb.button(text="зменить процент", callback_data=f"admin_partner_percent:{partner['id']}")
    kb.button(text="Выплатить вручную", callback_data=f"admin_partner_payout:{partner['id']}")
    kb.button(text="Удалить партнёра", callback_data=f"admin_partner_delete:{partner['id']}")
    kb.button(text="⬅️ Назад", callback_data="admin_partners")
    kb.adjust(1)
    await render_message(callback, text, kb.as_markup())


def _revoke_partner_admin_if_unused(partner_tg_id: int | None, deleted_partner_id: str):
    if partner_tg_id is None:
        return
    partners = get_partners_manager().all_partners()
    has_other = any(
        str(p.get("id")) != str(deleted_partner_id) and int(p.get("tg_id") or 0) == int(partner_tg_id)
        for p in partners
    )
    if has_other:
        return

    cfg = sett.get("config")
    master = cfg.setdefault("telegram", {}).setdefault("master", {})
    admins = list(master.get("admins") or [])
    if int(partner_tg_id) in admins:
        master["admins"] = [a for a in admins if int(a) != int(partner_tg_id)]
        sett.set("config", cfg)
    user = get_user_manager().get_user(int(partner_tg_id))
    if user:
        get_user_manager().update_user(int(partner_tg_id), admin_level="full")


@router.callback_query(F.data == "admin_partners")
async def cb_admin_partners(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    await _render_admin_partners(callback)


@router.callback_query(F.data == "admin_partner_create")
async def cb_admin_partner_create(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    await state.set_state(AdminStates.WAITING_PARTNER_NICK)
    await render_message(
        callback,
        "🤝 Создание партнёра — шаг 1 из 2\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        "Отправьте ник партнёра без @.\n\n"
        "Пример: TuPoLoBiK",
        _admin_back_kb(),
    )


@router.callback_query(F.data.startswith("admin_partner_open:"))
async def cb_admin_partner_open(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    partner_id = callback.data.split(":", 1)[1]
    await _render_partner_page(callback, partner_id)


@router.callback_query(F.data.startswith("admin_partner_refs:"))
async def cb_admin_partner_refs(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    partner_id = callback.data.split(":", 1)[1]
    partner = get_partners_manager().get_by_id(partner_id)
    if not partner:
        return await callback.answer(_master_msg("ALERT_PARTNER_NOT_FOUND", "Партнёр не найден."), show_alert=True)

    def _fmt_dt(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return value

    refs = list(partner.get("referred_users") or [])
    lines = [
        f"📊 Рефералы {partner['nickname']}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    if not refs:
        lines.append("Нет рефералов")
    else:
        for idx, ref in enumerate(refs, start=1):
            first_name = (ref.get("first_name") or "-").strip()
            username = (ref.get("username") or "").strip()
            if username and not username.startswith("@"):
                username = f"@{username}"
            user_title = f"{first_name} ({username})" if username else first_name
            lines.extend(
                [
                    f"{idx}. {user_title}",
                    f"\u2022 TG ID: {ref.get('tg_id') or '-'}",
                    f"├─ Присоединился: {_fmt_dt(ref.get('joined_at'))}",
                    f"├─ Платежей: {int(ref.get('payments_count', 0))}",
                    f"💸 Выплачено: {float(ref.get('total_paid', 0)):.2f} ₽",
                    f"💼 Заработано партнёром: {float(ref.get('total_earned', 0)):.2f} ₽",
                    "",
                ]
            )

    stats = get_partners_manager().stats(partner)
    lines.extend(
        [
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
            f"Всего рефералов: {stats['total_users']}",
            f"з них платящих: {stats['paid_users']}",
            f"Общий доход от рефералов: {stats['total_earned']:.2f} ₽",
        ]
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data=f"admin_partner_open:{partner_id}")
    kb.adjust(1)
    await render_message(callback, "\n".join(lines), kb.as_markup())


@router.callback_query(F.data.startswith("admin_partner_set_id:"))
async def cb_admin_partner_set_id(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    partner_id = callback.data.split(":", 1)[1]
    partner = get_partners_manager().get_by_id(partner_id)
    if not partner:
        return await callback.answer(_master_msg("ALERT_PARTNER_NOT_FOUND", "Партнёр не найден."), show_alert=True)
    await state.set_state(AdminStates.WAITING_PARTNER_TG_ID)
    await state.update_data(partner_id=partner_id)
    await render_message(
        callback,
        "Указать Telegram ID\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"Партнёр: {partner['nickname']}\n"
        f"Текущий ID: {partner.get('tg_id') or '-'}\n\n"
        "Введите ID числом.\n"
        "Чтобы очистить ID, отправьте: очистить",
        _admin_back_kb(),
    )


@router.callback_query(F.data.startswith("admin_partner_percent:"))
async def cb_admin_partner_percent(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    partner_id = callback.data.split(":", 1)[1]
    partner = get_partners_manager().get_by_id(partner_id)
    if not partner:
        return await callback.answer(_master_msg("ALERT_PARTNER_NOT_FOUND", "Партнёр не найден."), show_alert=True)
    await state.set_state(AdminStates.WAITING_PARTNER_PERCENT)
    await state.update_data(partner_id=partner_id)
    await render_message(
        callback,
        "зменить процент\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"Партнёр: {partner['nickname']}\n"
        f"Текущий процент: {int(partner.get('percent', 40))}%\n\n"
        "Введите новое число от 1 до 99.",
        _admin_back_kb(),
    )


@router.callback_query(F.data.startswith("admin_partner_payout:"))
async def cb_admin_partner_payout(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(callback):
        return
    partner_id = callback.data.split(":", 1)[1]
    partners_manager = get_partners_manager()
    partner = partners_manager.get_by_id(partner_id)
    if not partner:
        return await callback.answer(_master_msg("ALERT_PARTNER_NOT_FOUND", "Партнёр не найден."), show_alert=True)
    await state.set_state(AdminStates.WAITING_PARTNER_PAYOUT)
    await state.update_data(partner_id=partner_id)
    await render_message(
        callback,
        "Выплата партнёру\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"Партнёр: {partner['nickname']}\n"
        f"Доступно: {partners_manager.available_balance(partner):.2f} ₽\n\n"
        "Введите сумму выплаты.",
        _admin_back_kb(),
    )


@router.callback_query(F.data.startswith("admin_partner_delete:"))
async def cb_admin_partner_delete(callback: CallbackQuery):
    if not await _ensure_admin_callback(callback):
        return
    partner_id = callback.data.split(":", 1)[1]
    partners_manager = get_partners_manager()
    partner = partners_manager.get_by_id(partner_id)
    if not partner:
        return await callback.answer(_master_msg("ALERT_PARTNER_NOT_FOUND", "Партнёр не найден."), show_alert=True)
    partner_tg_id = partner.get("tg_id")
    user_manager = get_user_manager()
    for user in user_manager.all_users().values():
        if user.get("referred_partner_id") == partner_id:
            user_manager.update_user(
                int(user["tg_id"]),
                referred_partner_id=None,
                referred_partner_slug=None,
                referred_at=None,
            )
    partners_manager.delete_partner(partner_id)
    _revoke_partner_admin_if_unused(partner_tg_id, partner_id)
    user_manager.log_action("admin", "partner_delete", partner["nickname"])
    await _render_admin_partners(callback)




