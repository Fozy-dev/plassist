from __future__ import annotations

from datetime import datetime

from aiogram.types import InlineKeyboardMarkup, User
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.user_manager import tariff_title_ru
from messages.master import *  # noqa: F403
from tgbot.callback_datas.constructor import ConfirmDelete, ManageBot, SelectBot, SkipStep


def _msg(name: str, default: str = "") -> str:
    return str(globals().get(name, default))


def _btn(name: str, fallback: str) -> str:
    return _msg(f"{name}_TEXT", _msg(name, fallback))


def _render(template: str, **context) -> str:
    if not template:
        return ""
    try:
        safe_globals = {"__builtins__": {}, "datetime": datetime}
        return eval(f"f{template!r}", safe_globals, context)
    except Exception:
        try:
            return template.format(**context)
        except Exception:
            return template


def _status_label(bot: dict) -> str:
    return "✅ Активен" if bot.get("is_active") else "⛔ Остановлен"


def _has_active_tariff(profile: dict | None) -> bool:
    if not profile:
        return False
    expires_raw = profile.get("tariff_expires")
    if not expires_raw:
        return False
    try:
        return datetime.fromisoformat(expires_raw) > datetime.now()
    except Exception:
        return False


def get_main_menu_text(user: User, bots: list[dict], balance: float, profile: dict | None = None) -> str:
    active = sum(1 for bot in bots if bot.get("is_active"))
    stopped = len(bots) - active
    username = f"@{user.username}" if user.username else "не задан"
    tariff = "Нету"
    if profile and profile.get("tariff"):
        tariff = tariff_title_ru(profile.get("tariff"))
        if profile.get("tariff_expires"):
            try:
                exp = datetime.fromisoformat(profile["tariff_expires"]).strftime("%d.%m.%Y")
                tariff = f"{tariff} до {exp}"
            except Exception:
                pass
    modules_owned = "нет"
    return _render(
        _msg("MAIN_MENU_TEXT", "Меню"),
        user_id=user.id,
        first_name=user.first_name,
        username=username,
        balance=f"{balance:.2f} ₽",
        tariff=tariff,
        bots_total=len(bots),
        active=active,
        stopped=stopped,
        bots=bots,
        profile=profile or {},
        modules_owned=modules_owned,
    )


def get_main_menu_kb(profile: dict | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_CREATE_BOT", "🛠 Создать бота"), callback_data="create_bot")
    builder.button(text=_btn("BTN_MY_BOTS", "🤖 Мои боты"), callback_data="my_bots")

    builder.button(text=_btn("BTN_TOPUP", "💰 Пополнить баланс"), callback_data="topup_menu")
    builder.button(text=_btn("BTN_TARIFFS", "💎 Тарифы"), callback_data="tariff_menu")

    builder.button(text="💎 Информация", callback_data="info_menu")
    builder.button(text=_btn("BTN_MODULES", "🔌 Модули"), callback_data="master_modules_menu")

    show_trial = not _has_active_tariff(profile) and not bool((profile or {}).get("trial_used"))
    if show_trial:
        builder.button(text="🎁 Пробный период", callback_data="trial_period")

    if show_trial:
        builder.adjust(2, 2, 2, 1)
    else:
        builder.adjust(2, 2, 2)
    return builder.as_markup()


def get_create_bot_intro_text() -> str:
    default_text = (
        "🏗️ Создание нового бота\n\n"
        "Сначала выберите платформы (Playerok и/или FunPay), затем пройдите шаги настройки."
    )
    return _msg("CREATE_BOT_INTRO_TEXT", default_text)


def get_create_bot_intro_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_START_CREATE", "▶️ Начать"), callback_data="start_create_bot")
    builder.button(text=_btn("BTN_CANCEL_CREATE", "❌ Отмена"), callback_data="cancel_create_bot")
    builder.adjust(2)
    return builder.as_markup()


def get_platforms_pick_text(chosen: list[str]) -> str:
    fp = "✓" if "funpay" in chosen else ""
    pl = "✓" if "playerok" in chosen else ""
    default_text = "Выберите платформы:\n\n{fp} FunPay\n{pl} Playerok"
    return _render(_msg("PLATFORMS_PICK_TEXT", default_text), fp=fp, pl=pl, chosen=chosen)


def get_platforms_pick_kb(chosen: list[str]) -> InlineKeyboardMarkup:
    fp = ("✓ " if "funpay" in chosen else " ") + "FunPay"
    pl = ("✓ " if "playerok" in chosen else " ") + "Playerok"
    builder = InlineKeyboardBuilder()
    builder.button(text=fp, callback_data="toggle_platform:funpay")
    builder.button(text=pl, callback_data="toggle_platform:playerok")
    builder.button(text=_btn("BTN_CONTINUE_PLATFORMS", "▶️ Продолжить"), callback_data="platforms_continue")
    builder.button(text=_btn("BTN_CANCEL_CREATE", "❌ Отмена"), callback_data="cancel_create_bot")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_step_text(step: int, total: int, title: str, desc: str, example: str | None = None) -> str:
    template = _msg("STEP_TEXT", "{title}\n\n{desc}\n\nПример:\n<code>{example}</code>")
    return _render(template, step=step, total=total, title=title, desc=desc, example=example or "")


def get_skip_kb(step_name: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_SKIP_STEP", "⏩ Пропустить"), callback_data=SkipStep(step=step_name).pack())
    builder.button(text=_btn("BTN_CANCEL_CREATE", "❌ Отмена"), callback_data="cancel_create_bot")
    builder.adjust(2)
    return builder.as_markup()


def get_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_CANCEL_CREATE", "❌ Отмена"), callback_data="cancel_create_bot")
    return builder.as_markup()


def get_success_text(config: dict) -> str:
    username = config.get("tg_username") or "будет получен при первом запуске"
    template = _msg("SUCCESS_TEXT", "✓ Бот успешно создан")
    return _render(template, config=config, username=username, _status_label=_status_label)


def get_success_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_MY_BOTS_SUCCESS", "🤖 Мои боты"), callback_data="my_bots")
    builder.button(text=_btn("BTN_CREATE_ANOTHER", "➕ Ещё"), callback_data="create_bot")
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "🏠 Меню"), callback_data="back_to_main")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_my_bots_text(bots: list[dict]) -> str:
    if not bots:
        return _msg("MY_BOTS_EMPTY_TEXT", "\U0001F916 \u041c\u043e\u0438 \u0431\u043e\u0442\u044b\n\n\u0423 \u0432\u0430\u0441 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0441\u043e\u0437\u0434\u0430\u043d\u043d\u044b\u0445 \u0431\u043e\u0442\u043e\u0432.")
    lines = ["\U0001F916 \u041c\u043e\u0438 \u0431\u043e\u0442\u044b", "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"]
    for index, bot in enumerate(bots, start=1):
        lines.append(f"{index}. {bot.get('tg_username') or bot['uuid'][:8]}  {_status_label(bot)}")
    return "\n".join(lines)


def get_my_bots_kb(bots: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for bot in bots:
        builder.button(
            text=f"{bot.get('tg_username') or bot['uuid'][:8]} {'🟢' if bot.get('is_active') else '🔴'}",
            callback_data=SelectBot(uuid=bot["uuid"]).pack(),
        )
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "⬅️ Главное меню"), callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_bot_card_text(bot: dict, stats: dict | None = None) -> str:
    stats = stats or {}
    created = bot.get("created_at", "-")
    runtime = stats.get("uptime", "-")
    platforms = bot.get("platforms", []) or ["playerok"]
    template = _msg("BOT_PAGE_TEXT", "🤖 Бот")
    return _render(
        template,
        bot=bot,
        stats=stats,
        created=created,
        runtime=runtime,
        platforms_title=", ".join(platforms),
        _status_label=_status_label,
    )


def get_bot_card_kb(bot: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    action = "stop" if bot.get("is_active") else "start"
    action_text = _btn("BTN_STOP_BOT", "⛔ Остановить") if bot.get("is_active") else _btn("BTN_START_BOT", "▶️ Запустить")
    builder.button(text=action_text, callback_data=ManageBot(action=action, uuid=bot["uuid"]).pack())
    builder.button(text=_btn("BTN_RESTART_BOT", "🔄 Перезапустить"), callback_data=ManageBot(action="restart", uuid=bot["uuid"]).pack())
    builder.button(text=_btn("BTN_SETTINGS_ACCOUNTS", "⚙️ Настройки аккаунтов"), callback_data=f"acc_settings:{bot['uuid']}")
    builder.button(text=_btn("BTN_CUSTOMIZE", "🖊️ Кастомизация"), callback_data=f"customize:{bot['uuid']}")
    builder.button(text=_btn("BTN_PROXY_SETTINGS", "🔗 Прокси"), callback_data=f"proxy_settings:{bot['uuid']}")
    builder.button(text=_btn("BTN_EVENTS_BOT", "🗂 стория событий"), callback_data=f"events_bot:{bot['uuid']}")
    builder.button(text=_btn("BTN_DELETE_BOT", "🗑 Удалить"), callback_data=ManageBot(action="delete", uuid=bot["uuid"]).pack())
    builder.button(text=_btn("BTN_BACK_TO_LIST", "⬅️ К списку"), callback_data="my_bots")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def get_delete_confirm_text(bot: dict) -> str:
    template = _msg("DELETE_CONFIRM_TEXT", "🗑 Подтверждение удаления\n\nУдалить бота?")
    return _render(template, bot=bot)


def get_delete_confirm_kb(uuid: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_CONFIRM_DELETE", "✓ Да"), callback_data=ConfirmDelete(uuid=uuid, confirmed=True).pack())
    builder.button(text=_btn("BTN_CANCEL_DELETE", "❌ Нет"), callback_data=ConfirmDelete(uuid=uuid, confirmed=False).pack())
    builder.adjust(2)
    return builder.as_markup()


def get_help_text() -> str:
    default_text = (
        "💡 Помощь и контакты\n\n"
        "Если есть вопросы — пишите @RaidexHelp_bot\n\n"
        "🔒 Политика конфиденциальности\n"
        "📜 Пользовательское соглашение"
    )
    return _msg("HELP_TEXT", default_text)


def get_info_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Написать в поддержку", url="https://t.me/RaidexHelp_bot")
    builder.button(text="📄 Публичная оферта", url="https://telegra.ph/Publichnaya-oferta-03-27-7")
    builder.button(text="🔒 Политика персональных данных", url="https://telegra.ph/Politika-obrabotki-personalnyh-dannyh-03-27-3")
    builder.button(text="💸 Возврат и отмена", url="https://telegra.ph/Usloviya-vozvrata-i-otmeny-platezha-03-27")
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "⬅️ Главное меню"), callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def get_tariff_menu_text(balance: float) -> str:
    return _render(_msg("TARIFF_MENU_TEXT", "Тарифы"), balance=balance)


def get_tariff_menu_kb(auto_renew: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_WEEK_TARIFF", "🗓 НЕДЕЛЯ • 70 ₽"), callback_data="tariff:week")
    builder.button(text=_btn("BTN_MONTH_TARIFF", "📅 МЕСЯЦ • 120 ₽"), callback_data="tariff:month")
    builder.button(text=_btn("BTN_YEAR_TARIFF", "🏆 ГОД • 1 290 ₽"), callback_data="tariff:year")
    state = _msg("TARIFF_AUTO_RENEW_ENABLED", "включено") if auto_renew else _msg("TARIFF_AUTO_RENEW_DISABLED", "выключено")
    builder.button(
        text=_render(_msg("TARIFF_AUTO_RENEW_TEXT", "🔄 Автопродление: {state}"), state=state),
        callback_data="auto_renew_toggle",
    )
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "⬅️ Главное меню"), callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_tariff_confirm_text(name: str, days: int, price: float, balance: float) -> str:
    return _render(_msg("TARIFF_CONFIRM_TEXT", "{name}"), name=name, days=days, price=price, balance=balance)


def get_tariff_confirm_kb(tariff_key: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_CONFIRM_TARIFF", "✅ Подтвердить"), callback_data=f"tariff_confirm:{tariff_key}")
    builder.button(text=_btn("BTN_CANCEL_TARIFF", "❌ Отмена"), callback_data="tariff_menu")
    builder.adjust(2)
    return builder.as_markup()


def get_need_tariff_text() -> str:
    return _msg("TARIFF_REQUIRED_TEXT", "💎 Требуется тариф")


def get_need_tariff_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_SELECT_TARIFF", "💎 Выбрать тариф"), callback_data="tariff_menu")
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "⬅️ Главное меню"), callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()


def get_limit_reached_text() -> str:
    return _msg("BOTS_LIMIT_TEXT", "🤖 Лимит ботов достигнут")


def get_feedback_text() -> str:
    return _msg("FEEDBACK_TEXT", "По всем вопросам: @RaidexHelp_bot")


def get_back_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "⬅️ Главное меню"), callback_data="back_to_main")
    return builder.as_markup()


def get_topup_text(balance: float) -> str:
    return _render(_msg("TOPUP_TEXT", "💳 Пополнение баланса"), balance=balance)


def get_stats_menu_text(bots: list[dict]) -> str:
    active = sum(1 for bot in bots if bot.get("is_active"))
    return _render(_msg("STATS_MENU_TEXT", "📊 Аналитика"), bots=bots, bots_total=len(bots), active=active, stopped=len(bots) - active, generated_at=datetime.now().strftime("%d.%m.%Y %H:%M:%S"))


def get_analytics_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_btn("BTN_HOURLY_CHART", "📈 График по часам"), callback_data="analytics_hourly_menu")
    builder.button(text=_btn("BTN_TOP_ITEMS", "🏆 Топ товаров"), callback_data="analytics_top_menu")
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "⬅️ Главное меню"), callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_panel_text(users_count: int, active_tariffs: int, bots_count: int, maintenance_mode: bool) -> str:
    return _render(
        _msg("ADMIN_PANEL_TEXT", "🔒 ADMIN"),
        users_count=users_count,
        active_tariffs=active_tariffs,
        bots_count=bots_count,
        maintenance_mode=maintenance_mode,
    )


def get_admin_panel_kb(maintenance_mode: bool, admin_level: str = "full") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    is_limited = (admin_level or "").lower() == "limited"
    builder.button(text=_btn("BTN_ADMIN_STATS", "\U0001F4C8 \u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430"), callback_data="admin_stats")
    builder.button(text=_btn("BTN_ADMIN_USERS", "\U0001F465 \u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438"), callback_data="admin_users")
    if is_limited:
        builder.button(text="\U0001F4CA \u041C\u043E\u044F \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430", callback_data="admin_partner_my_stats")
    else:
        builder.button(text="\U0001F91D \u041F\u0430\u0440\u0442\u043D\u0451\u0440\u044B", callback_data="admin_partners")
    builder.button(text=_btn("BTN_ADMIN_SESSIONS", "\U0001F4DF \u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0435 \u0441\u0435\u0441\u0441\u0438\u0438"), callback_data="admin_sessions")
    builder.button(text=_btn("BTN_ADMIN_BROADCAST", "\U0001F4E3 \u0420\u0430\u0441\u0441\u044B\u043B\u043A\u0430"), callback_data="admin_broadcast")
    if not is_limited:
        builder.button(text=_btn("BTN_ADMIN_LOGS", "\U0001F4CB \u041B\u043E\u0433\u0438 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0439"), callback_data="admin_logs")
        builder.button(text=_btn("BTN_ADMIN_EXPORT_CSV", "\U0001F4E4 \u042D\u043A\u0441\u043F\u043E\u0440\u0442 CSV"), callback_data="admin_export_csv")
        if maintenance_mode:
            builder.button(text=_btn("BTN_ADMIN_MAINTENANCE_OFF", "\u2705 \u0412\u044B\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u0442\u0435\u0445\u0440\u0435\u0436\u0438\u043C"), callback_data="admin_maintenance_off")
        else:
            builder.button(text=_btn("BTN_ADMIN_MAINTENANCE_ON", "\U0001F527 \u0412\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u0442\u0435\u0445\u0440\u0435\u0436\u0438\u043C"), callback_data="admin_maintenance_on")
    builder.button(text=_btn("BTN_BACK_TO_MAIN", "\u2B05\uFE0F \u0413\u043B\u0430\u0432\u043D\u043E\u0435 \u043C\u0435\u043D\u044E"), callback_data="back_to_main")
    if is_limited:
        builder.adjust(2, 2, 1, 1)
    else:
        builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()

