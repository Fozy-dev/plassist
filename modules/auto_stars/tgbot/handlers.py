from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from settings import Settings as sett
from tgbot.helpful import do_auth, throw_float_message

from ..services import service
from ..states import AutoStarsStates
from ..storage import (
    get_config,
    is_owned,
    set_allowed_quantities,
    set_auto_refund,
    set_enabled,
    set_fragment_value,
    set_message,
    set_ton_value,
)
from ..templates import (
    edit_message_prompt,
    edit_setting_prompt,
    menu_kb,
    menu_text,
    messages_kb,
    messages_text,
    settings_kb,
    settings_text,
)


router = Router()


async def _is_authorized(message: Message) -> bool:
    config = sett.get("config") or {}
    signed = config.get("telegram", {}).get("bot", {}).get("signed_users", [])
    return bool(message.from_user and message.from_user.id in signed)


async def _show_menu(message: Message, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, message, menu_text(), menu_kb())


@router.message(Command("stars"))
async def command_stars(message: Message, state: FSMContext):
    if not await _is_authorized(message):
        return await do_auth(message, state)
    if not is_owned():
        return await message.answer("Модуль AutoStars не подключён к этому боту.")
    service.start()
    await _show_menu(message, state)


@router.callback_query(F.data == "as_back")
async def callback_as_back(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "as_toggle_enabled")
async def callback_as_toggle_enabled(callback, state: FSMContext):
    set_enabled(not bool(get_config().get("enabled")))
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "as_messages_menu")
async def callback_as_messages_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, messages_text(), messages_kb(), callback)


@router.callback_query(F.data == "as_settings_menu")
async def callback_as_settings_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, settings_text(), settings_kb(), callback)


@router.callback_query(F.data.startswith("as_message:"))
async def callback_as_message(callback, state: FSMContext):
    message_key = callback.data.split(":", 1)[1]
    await state.update_data(as_mode="message", as_message_key=message_key)
    await state.set_state(AutoStarsStates.waiting_for_message_text)
    await throw_float_message(
        state,
        callback.message,
        edit_message_prompt(message_key),
        callback=callback,
        send=True,
    )


@router.callback_query(F.data.startswith("as_setting:"))
async def callback_as_setting(callback, state: FSMContext):
    setting_key = callback.data.split(":", 1)[1]
    await state.update_data(as_mode="setting", as_setting_key=setting_key)
    await state.set_state(AutoStarsStates.waiting_for_setting_value)
    await throw_float_message(
        state,
        callback.message,
        edit_setting_prompt(setting_key),
        callback=callback,
        send=True,
    )


@router.callback_query(F.data == "as_toggle_refund")
async def callback_as_toggle_refund(callback, state: FSMContext):
    set_auto_refund(not bool(get_config().get("auto_refund")))
    await throw_float_message(state, callback.message, settings_text(), settings_kb(), callback)


@router.message(AutoStarsStates.waiting_for_message_text, F.text)
async def message_as_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    message_key = data.get("as_message_key")
    text = (message.text or "").strip()
    if not message_key:
        await state.clear()
        return await message.answer("Ключ сообщения не найден.")
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    set_message(message_key, text)
    await state.clear()
    await message.answer(messages_text(), reply_markup=messages_kb(), parse_mode="HTML")


@router.message(AutoStarsStates.waiting_for_setting_value, F.text)
async def message_as_setting_value(message: Message, state: FSMContext):
    data = await state.get_data()
    setting_key = data.get("as_setting_key")
    text = (message.text or "").strip()
    if not setting_key:
        await state.clear()
        return await message.answer("Ключ настройки не найден.")
    if not text:
        return await message.answer("Значение не должно быть пустым.")

    if setting_key == "fragment_hash":
        set_fragment_value("hash", text)
    elif setting_key == "fragment_cookie":
        set_fragment_value("cookie", text)
    elif setting_key == "ton_api_key":
        set_ton_value("api_key", text)
    elif setting_key == "ton_destination":
        set_ton_value("destination_address", text)
    elif setting_key == "ton_mnemonic":
        words = [item for item in text.split() if item]
        if len(words) != 24:
            return await message.answer("Нужно отправить ровно 24 слова мнемоники.")
        set_ton_value("mnemonic", words)
    elif setting_key == "allowed_quantities":
        try:
            values = [int(item.strip()) for item in text.split(",") if item.strip()]
        except ValueError:
            return await message.answer("Количество должно быть списком чисел через запятую.")
        set_allowed_quantities(values)

    await state.clear()
    await message.answer(settings_text(), reply_markup=settings_kb(), parse_mode="HTML")


async def on_telegram_bot_init(telegram_bot):
    service.start()
    for bot in getattr(telegram_bot, "bots", []):
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="/start", description="Главное меню"),
                    BotCommand(command="/stars", description="Настройки AutoStars"),
                ]
            )
        except Exception:
            pass


async def on_funpay_bot_init(*_):
    service.start()


BOT_EVENT_HANDLERS = {
    "ON_TELEGRAM_BOT_INIT": [on_telegram_bot_init],
    "ON_FUNPAY_BOT_INIT": [on_funpay_bot_init],
}
