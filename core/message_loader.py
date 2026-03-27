"""
Загрузчик сообщений из Python модулей.
Использует модули из директории messages/ как источник сообщений.
"""

import importlib
import os
import sys
from typing import Dict, Any

# Добавляем корень проекта в путь для импорта messages
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _get_platform_messages_module(platform: str):
    """
    Возвращает модуль с сообщениями для указанной платформы.
    platform: 'master', 'playerok', 'funpay'
    """
    try:
        module = importlib.import_module(f"messages.{platform}")
        return module
    except ImportError as e:
        print(f"Не удалось загрузить модуль messages.{platform}: {e}")
        return None


def _convert_to_old_format(module) -> Dict[str, Any]:
    """
    Конвертирует константы из Python модуля в старый JSON формат.
    Старый формат: {
        "first_message": {"enabled": True, "text": [...]},
        "cmd_error": {"enabled": True, "text": [...]},
        ...
    }
    """
    result = {}

    # Маппинг старых ключей к новым константам
    # Для чатовых сообщений (сообщения для конечных пользователей)
    chat_messages_mapping = {
        "first_message": {
            "enabled": True,
            "text": getattr(module, "FIRST_MESSAGE", "👋 Привет, {username}").split("\n")
        },
        "cmd_error": {
            "enabled": True,
            "text": [getattr(module, "CMD_ERROR", "❌ Ошибка: {error}")]
        },
        "cmd_commands": {
            "enabled": True,
            "text": getattr(module, "CMD_COMMANDS", "⌨️ Команды\n\n!команды — список команд").split("\n")
        },
        "cmd_seller": {
            "enabled": True,
            "text": [getattr(module, "CMD_SELLER", "💬 Продавец был вызван в этот чат. Ожидайте...")]
        },
        "new_deal": {
            "enabled": False,
            "text": getattr(module, "NEW_DEAL", "📋 Спасибо за покупку!").split("\n")
        },
        "deal_pending": {
            "enabled": False,
            "text": [getattr(module, "DEAL_PENDING", "⌛ Ожидание данных...")]
        },
        "deal_sent": {
            "enabled": False,
            "text": [getattr(module, "DEAL_SENT", "✅ Заказ подтверждён!")]
        },
        "deal_confirmed": {
            "enabled": False,
            "text": [getattr(module, "DEAL_CONFIRMED", "🌟 Сделка завершена успешно!")]
        },
        "deal_refunded": {
            "enabled": False,
            "text": [getattr(module, "DEAL_REFUNDED", "📦 Заказ возвращён.")]
        },
        "new_review": {
            "enabled": False,
            "text": getattr(module, "NEW_REVIEW", "✨ Спасибо за отзыв!").split("\n")
        }
    }

    # Для UI сообщений (меню, кнопки и т.д.) - они будут доступны как отдельные ключи
    ui_messages = {
        # Основные тексты
        "main_menu_text": getattr(module, "MAIN_MENU_TEXT", ""),
        "settings_text": getattr(module, "SETTINGS_TEXT", ""),
        "profile_text": getattr(module, "PROFILE_TEXT", ""),
        "stats_text": getattr(module, "STATS_TEXT", ""),
        "modules_text": getattr(module, "MODULES_TEXT", ""),
        "module_page_text": getattr(module, "MODULE_PAGE_TEXT", ""),
        "logs_text": getattr(module, "LOGS_TEXT", ""),
        "instruction_text": getattr(module, "INSTRUCTION_TEXT", ""),
        "instruction_comms_text": getattr(module, "INSTRUCTION_COMMS_TEXT", ""),
        "events_text": getattr(module, "EVENTS_TEXT", ""),
        "error_text": getattr(module, "ERROR_TEXT", ""),
        "do_action_text": getattr(module, "DO_ACTION_TEXT", ""),
        "log_text": getattr(module, "LOG_TEXT", ""),
        "sign_text": getattr(module, "SIGN_TEXT", ""),
        "call_seller_text": getattr(module, "CALL_SELLER_TEXT", ""),

        # Тексты для конструктора (master bot)
        "platforms_pick_text": getattr(module, "PLATFORMS_PICK_TEXT", ""),
        "step_text": getattr(module, "STEP_TEXT", ""),
        "success_text": getattr(module, "SUCCESS_TEXT", ""),
        "my_bots_empty_text": getattr(module, "MY_BOTS_EMPTY_TEXT", ""),
        "bot_page_text": getattr(module, "BOT_PAGE_TEXT", ""),
        "delete_confirm_text": getattr(module, "DELETE_CONFIRM_TEXT", ""),
        "help_text": getattr(module, "HELP_TEXT", ""),
        "tariff_menu_text": getattr(module, "TARIFF_MENU_TEXT", ""),
        "tariff_confirm_text": getattr(module, "TARIFF_CONFIRM_TEXT", ""),
        "tariff_required_text": getattr(module, "TARIFF_REQUIRED_TEXT", ""),
        "bots_limit_text": getattr(module, "BOTS_LIMIT_TEXT", ""),
        "feedback_text": getattr(module, "FEEDBACK_TEXT", ""),
        "topup_text": getattr(module, "TOPUP_TEXT", ""),
        "stats_menu_text": getattr(module, "STATS_MENU_TEXT", ""),
        "admin_panel_text": getattr(module, "ADMIN_PANEL_TEXT", ""),

        # Кнопки
        "btn_settings": getattr(module, "BTN_SETTINGS", "⚙️ Настройки"),
        "btn_profile": getattr(module, "BTN_PROFILE", "👤 Профиль"),
        "btn_events": getattr(module, "BTN_EVENTS", "🚩 Ивенты"),
        "btn_logs": getattr(module, "BTN_LOGS", "🗒️ Логи"),
        "btn_stats": getattr(module, "BTN_STATS", "📊 Статистика"),
        "btn_modules": getattr(module, "BTN_MODULES", "🔌 Модули"),
        "btn_instruction": getattr(module, "BTN_INSTRUCTION", "📖 Инструкция"),
        "btn_back": getattr(module, "BTN_BACK", "⬅️ Назад"),
        "btn_create_bot": getattr(module, "BTN_CREATE_BOT", "➕ Создать бота"),
        "btn_topup": getattr(module, "BTN_TOPUP", "💳 Пополнить баланс"),
        "btn_tariffs": getattr(module, "BTN_TARIFFS", "💎 Тарифы"),
        "btn_my_bots": getattr(module, "BTN_MY_BOTS", "🤖 Мои боты"),
        "btn_analytics": getattr(module, "BTN_ANALYTICS", "📊 Аналитика"),
        "btn_help": getattr(module, "BTN_HELP", "❗️ Помощь"),
        "btn_feedback": getattr(module, "BTN_FEEDBACK", "✉️ Обратная связь"),
        "btn_start_create": getattr(module, "BTN_START_CREATE", "▶️ Начать"),
        "btn_cancel_create": getattr(module, "BTN_CANCEL_CREATE", "🙅 Отмена"),
        "btn_continue_platforms": getattr(module, "BTN_CONTINUE_PLATFORMS", "▶️ Продолжить"),
        "btn_funpay_platform": getattr(module, "BTN_FUNPAY_PLATFORM", "● FunPay"),
        "btn_playerok_platform": getattr(module, "BTN_PLAYEROK_PLATFORM", "● Playerok"),
        "btn_skip_step": getattr(module, "BTN_SKIP_STEP", "▶️ Пропустить"),
        "btn_my_bots_success": getattr(module, "BTN_MY_BOTS_SUCCESS", "🤖 Мои боты"),
        "btn_create_another": getattr(module, "BTN_CREATE_ANOTHER", "➕ Ещё"),
        "btn_back_to_main": getattr(module, "BTN_BACK_TO_MAIN", "🏠 Меню"),
        "btn_start_bot": getattr(module, "BTN_START_BOT", "▶️ Запустить"),
        "btn_stop_bot": getattr(module, "BTN_STOP_BOT", "⛔ Остановить"),
        "btn_restart_bot": getattr(module, "BTN_RESTART_BOT", "🔄 Перезапустить"),
        "btn_settings_accounts": getattr(module, "BTN_SETTINGS_ACCOUNTS", "⚙️ Настройки аккаунтов"),
        "btn_customize": getattr(module, "BTN_CUSTOMIZE", "🖌️ Кастомизация"),
        "btn_proxy_settings": getattr(module, "BTN_PROXY_SETTINGS", "🔗 Прокси"),
        "btn_events_bot": getattr(module, "BTN_EVENTS_BOT", "📜 История"),
        "btn_delete_bot": getattr(module, "BTN_DELETE_BOT", "🗑 Удалить"),
        "btn_back_to_list": getattr(module, "BTN_BACK_TO_LIST", "◀️ К списку"),
        "btn_confirm_delete": getattr(module, "BTN_CONFIRM_DELETE", "✅ Да"),
        "btn_cancel_delete": getattr(module, "BTN_CANCEL_DELETE", "❌ Нет"),
        "btn_week_tariff": getattr(module, "BTN_WEEK_TARIFF", "🗓️ Неделя — 70 ₽"),
        "btn_month_tariff": getattr(module, "BTN_MONTH_TARIFF", "📅 Месяц — 120 ₽"),
        "btn_year_tariff": getattr(module, "BTN_YEAR_TARIFF", "🏆 Год — 1 290 ₽"),
        "btn_auto_renew": getattr(module, "BTN_AUTO_RENEW", "🔄 Автопродление: вкл"),
        "btn_select_tariff": getattr(module, "BTN_SELECT_TARIFF", "💎 Выбрать тариф"),
        "btn_confirm_tariff": getattr(module, "BTN_CONFIRM_TARIFF", "✅ Подтвердить"),
        "btn_cancel_tariff": getattr(module, "BTN_CANCEL_TARIFF", "❌ Отмена"),
        "btn_hourly_chart": getattr(module, "BTN_HOURLY_CHART", "📈 График по часам"),
        "btn_top_items": getattr(module, "BTN_TOP_ITEMS", "🏆 Топ товаров"),
        "btn_admin_stats": getattr(module, "BTN_ADMIN_STATS", "📈 Статистика"),
        "btn_admin_users": getattr(module, "BTN_ADMIN_USERS", "👥 Пользователи"),
        "btn_admin_sessions": getattr(module, "BTN_ADMIN_SESSIONS", "📟 Активные сессии"),
        "btn_admin_logs": getattr(module, "BTN_ADMIN_LOGS", "📋 Логи действий"),
        "btn_admin_broadcast": getattr(module, "BTN_ADMIN_BROADCAST", "📢 Рассылка"),
        "btn_admin_export_csv": getattr(module, "BTN_ADMIN_EXPORT_CSV", "📤 Экспорт CSV"),
        "btn_admin_maintenance_on": getattr(module, "BTN_ADMIN_MAINTENANCE_ON", "🔧 Включить техрежим"),
        "btn_admin_maintenance_off": getattr(module, "BTN_ADMIN_MAINTENANCE_OFF", "✅ Выключить техрежим"),

        # Кнопки действий в логах
        "btn_send_message": getattr(module, "BTN_SEND_MESSAGE", "💬 Написать"),
        "btn_complete_deal": getattr(module, "BTN_COMPLETE_DEAL", "☑️ Выполнил"),
        "btn_refund_deal": getattr(module, "BTN_REFUND_DEAL", "📦 Возврат"),
        "btn_answer_review": getattr(module, "BTN_ANSWER_REVIEW", "🌟 Ответить на отзыв"),
        "btn_destroy": getattr(module, "BTN_DESTROY", "❌ Закрыть"),

        # Кнопки логов
        "btn_select_logs": getattr(module, "BTN_SELECT_LOGS", "📔 Получить логи"),
        "btn_last_100": getattr(module, "BTN_LAST_100", "📗 Последние 100 строк"),
        "btn_last_250": getattr(module, "BTN_LAST_250", "📘 Последние 250 строк"),
        "btn_last_1000": getattr(module, "BTN_LAST_1000", "📕 Последние 1000 строк"),
        "btn_all_file": getattr(module, "BTN_ALL_FILE", "📖 Весь файл"),

        # Кнопки инструкции
        "btn_commands": getattr(module, "BTN_COMMANDS", "⌨️ Команды"),

        # Кнопки ивентов
        "btn_bump_items": getattr(module, "BTN_BUMP_ITEMS", "⬆️ Поднять предметы"),
        "btn_withdrawal": getattr(module, "BTN_WITHDRAWAL", "💸 Вывести средства"),

        # Ссылки
        "link_channel": getattr(module, "LINK_CHANNEL", "https://t.me/RaidexAssist"),
        "link_bot": getattr(module, "LINK_BOT", "@RaidexAssist_bot"),
        "link_modules": getattr(module, "LINK_MODULES", "@RaidexAssist_plugins"),
        "link_support": getattr(module, "LINK_SUPPORT", "@RaidexHelp_bot"),
        "link_assist": getattr(module, "LINK_ASSIST", "https://t.me/RaidexAssist"),
    }

    # Объединяем все
    result.update(chat_messages_mapping)
    result.update(ui_messages)

    return result


def load_messages(platform: str = "playerok", use_fallback: bool = True) -> Dict[str, Any]:
    """
    Загружает сообщения для указанной платформы из Python модуля.

    :param platform: 'master', 'playerok', 'funpay'
    :param use_fallback: если True, при ошибке загрузки Python модуля возвращает пустой словарь
    :return: словарь с сообщениями в старом формате
    """
    module = _get_platform_messages_module(platform)
    if module is None:
        if use_fallback:
            print(f"Используется пустой набор сообщений для платформы {platform}")
            return {}
        else:
            raise ImportError(f"Не удалось загрузить модуль messages.{platform}")

    return _convert_to_old_format(module)


def get_message(messages: Dict[str, Any], message_name: str, **kwargs) -> str | None:
    """
    Получает сообщение из загруженного словаря сообщений.

    :param messages: загруженный словарь сообщений
    :param message_name: ключ сообщения (например, 'first_message', 'error_text')
    :param kwargs: параметры для форматирования
    :return: отформатированная строка или None если сообщение отключено
    """
    mess = messages.get(message_name, {})
    if not mess.get("enabled", True):
        return None

    # Если это просто строка (UI текст), возвращаем её
    if isinstance(mess, str):
        try:
            return mess.format(**kwargs) if kwargs else mess
        except:
            return mess

    # Если это старый формат с text array
    message_lines: list = mess.get("text", [])
    if not message_lines:
        return f"Сообщение {message_name} пустое"

    try:
        # Собираем строки и форматируем
        if kwargs:
            formatted_lines = [line.format(**kwargs) for line in message_lines]
        else:
            formatted_lines = message_lines
        return "\n".join(formatted_lines)
    except Exception as e:
        return f"Не удалось отформатировать сообщение {message_name}: {e}"
