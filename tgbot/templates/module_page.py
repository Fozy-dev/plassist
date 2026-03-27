import textwrap
from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.modules import Module, get_module_by_uuid
from settings import Settings as sett

from .. import callback_datas as calls

AUTO_BONUS_PREFIX = "auto_bonus"
AUTO_BONUS_NAME = "AutoBonus"
AUTO_BONUS_PRICE = 490.0


def _is_module_owned(prefix: str) -> bool:
    config = sett.get("config") or {}
    owned = config.get("telegram", {}).get("master", {}).get("modules_owned") or []
    return prefix in owned


def _master_bot_url() -> str:
    config = sett.get("config") or {}
    username = (config.get("telegram", {}).get("master", {}).get("username") or "RaidexAssist_bot").lstrip("@")
    return f"https://t.me/{username}?start=modules_shop"


def module_page_text(module_uuid: UUID):
    module: Module = get_module_by_uuid(module_uuid)
    if not module:
        raise Exception("Не удалось найти одуль")

    if module.meta.prefix == AUTO_BONUS_PREFIX:
        if _is_module_owned(AUTO_BONUS_PREFIX):
            txt = textwrap.dedent(
                f"""
                ⚡ {AUTO_BONUS_NAME}

                Модуль куплен и доступен для этого бота.
                Включайте/выключайте его кнопкой ниже.

                По уолчанию после покупки одуль выключен.
                """
            )
            return txt.strip()
        txt = textwrap.dedent(
            f"""
            ⚡ {AUTO_BONUS_NAME}

            Автоатически выдавай бонусы покупателя после
            подтверждения сделки или оставления отзыва.

            Привяжи любой бонус к любоу товару — ссылку,
            проокод, файл или любой текст.

            Работает на Playerok и FunPay.

            Цена: {AUTO_BONUS_PRICE:.0f} ₽
            """
        )
        return txt.strip()

    txt = textwrap.dedent(
        f"""
        <b>📄🔌 Страница одуля</b>

        <b>Модуль</b> <code>{module.meta.name}</code>:
        ・ UUID: <b>{module.uuid}</b>
        ・ Версия: <b>{module.meta.version}</b>
        ・ Описание: <blockquote>{module.meta.description}</blockquote>
        ・ Авторы: <b>{module.meta.authors}</b>
        ・ Ссылки: <b>{module.meta.links}</b>

        🔌 <b>Состояние:</b> {'🟢 Включен' if module.enabled else '🔴 Выключен'}
        """
    )
    return txt


def module_page_kb(module_uuid: UUID, page: int = 0):
    module: Module = get_module_by_uuid(module_uuid)
    if not module:
        raise Exception("Не удалось найти одуль")

    if module.meta.prefix == AUTO_BONUS_PREFIX:
        if not _is_module_owned(AUTO_BONUS_PREFIX):
            rows = [
                [InlineKeyboardButton(text="💳 Купить в астер-боте", url=_master_bot_url())],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=calls.ModulesPagination(page=page).pack())],
            ]
            return InlineKeyboardMarkup(inline_keyboard=rows)
        rows = [
            [InlineKeyboardButton(text="🔴 Выключить одуль" if module.enabled else "🟢 Включить одуль", callback_data="switch_module_enabled")],
            [InlineKeyboardButton(text="♻️ Перезагрузить", callback_data="reload_module")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=calls.ModulesPagination(page=page).pack())],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    rows = [
        [InlineKeyboardButton(text="🔴 Выключить одуль" if module.enabled else "🟢 Включить одуль", callback_data="switch_module_enabled")],
        [InlineKeyboardButton(text="♻️ Перезагрузить", callback_data="reload_module")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.ModulesPagination(page=page).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def module_page_float_text(placeholder: str):
    txt = textwrap.dedent(
        f"""
        <b>🔧 Управление одуле</b>

        {placeholder}
        """
    )
    return txt
