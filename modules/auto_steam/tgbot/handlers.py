from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from settings import Settings as sett
from tgbot.helpful import do_auth, throw_float_message

from ..helpers import prompt_text
from ..services import service
from ..states import AutoSteamStates
from ..storage import (
    add_blacklist_login,
    get_allowed_subcategory_ids,
    get_api_login,
    get_api_password,
    get_blacklist_logins,
    get_reminder_time_minutes,
    is_auto_refund_enabled,
    is_confirmation_reminder_enabled,
    is_enabled,
    is_order_verification_enabled,
    is_owned,
    remove_blacklist_login,
    set_allowed_subcategory_ids,
    set_api_login,
    set_api_password,
    set_auto_refund,
    set_confirmation_reminder,
    set_enabled,
    set_message,
    set_order_verification,
    set_reminder_time_minutes,
)
from ..templates import blacklist_kb, blacklist_text, edit_message_prompt, history_kb, history_text, menu_kb, menu_text, messages_kb, messages_text


router = Router()


async def _is_authorized(message: Message) -> bool:
    config = sett.get("config") or {}
    signed = config.get("telegram", {}).get("bot", {}).get("signed_users", [])
    return bool(message.from_user and message.from_user.id in signed)


async def _show_menu(message: Message, state: FSMContext):
    await state.set_state(None)
    balance = service.get_balance()
    balance_text = f"{balance:.2f}$" if balance is not None else "ошибка"
    await throw_float_message(state, message, menu_text(balance_text), menu_kb())


@router.message(Command("autosteam"))
async def command_autosteam(message: Message, state: FSMContext):
    if not await _is_authorized(message):
        return await do_auth(message, state)
    if not is_owned():
        return await message.answer("Модуль AutoSteam не подключён к этому боту.")
    await _show_menu(message, state)


@router.callback_query(F.data == "ast_back")
async def callback_ast_back(callback, state: FSMContext):
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "ast_toggle_enabled")
async def callback_ast_toggle_enabled(callback, state: FSMContext):
    set_enabled(not is_enabled())
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "ast_toggle_auto_refund")
async def callback_ast_toggle_auto_refund(callback, state: FSMContext):
    set_auto_refund(not is_auto_refund_enabled())
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "ast_toggle_verification")
async def callback_ast_toggle_verification(callback, state: FSMContext):
    set_order_verification(not is_order_verification_enabled())
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "ast_toggle_reminder")
async def callback_ast_toggle_reminder(callback, state: FSMContext):
    set_confirmation_reminder(not is_confirmation_reminder_enabled())
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "ast_edit_api_login")
async def callback_ast_edit_api_login(callback, state: FSMContext):
    await state.update_data(ast_field="api_login")
    await state.set_state(AutoSteamStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте API login NSGifts.\nТекущий: <code>{get_api_login() or 'не задан'}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "ast_edit_api_password")
async def callback_ast_edit_api_password(callback, state: FSMContext):
    await state.update_data(ast_field="api_password")
    await state.set_state(AutoSteamStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте API password NSGifts.\nТекущий: <code>{'задан' if get_api_password() else 'не задан'}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "ast_edit_reminder_time")
async def callback_ast_edit_reminder_time(callback, state: FSMContext):
    await state.set_state(AutoSteamStates.waiting_for_float)
    await state.update_data(ast_float_field="reminder_time_minutes")
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте время напоминания в минутах. Текущее: <b>{get_reminder_time_minutes()}</b>"), callback=callback, send=True)


@router.callback_query(F.data == "ast_edit_subcategories")
async def callback_ast_edit_subcategories(callback, state: FSMContext):
    await state.set_state(AutoSteamStates.waiting_for_text)
    await state.update_data(ast_field="allowed_subcategory_ids")
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте ID подкатегорий через запятую. Текущие: <code>{', '.join(map(str, get_allowed_subcategory_ids()))}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "ast_messages_menu")
async def callback_ast_messages_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, messages_text(), messages_kb(), callback)


@router.callback_query(F.data == "ast_blacklist_menu")
async def callback_ast_blacklist_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, blacklist_text(), blacklist_kb(), callback)


@router.callback_query(F.data == "ast_blacklist_add")
async def callback_ast_blacklist_add(callback, state: FSMContext):
    await state.set_state(AutoSteamStates.waiting_for_text)
    await state.update_data(ast_field="blacklist_add")
    await throw_float_message(state, callback.message, prompt_text("Отправьте Steam login для добавления в blacklist."), callback=callback, send=True)


@router.callback_query(F.data == "ast_blacklist_remove")
async def callback_ast_blacklist_remove(callback, state: FSMContext):
    await state.set_state(AutoSteamStates.waiting_for_text)
    await state.update_data(ast_field="blacklist_remove")
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте Steam login для удаления из blacklist.\nСейчас: <code>{', '.join(get_blacklist_logins()) or 'пусто'}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "ast_history_menu")
async def callback_ast_history_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, history_text(), history_kb(), callback)


@router.callback_query(F.data.startswith("ast_message:"))
async def callback_ast_message(callback, state: FSMContext):
    message_key = callback.data.split(":", 1)[1]
    await state.update_data(ast_message_key=message_key)
    await state.set_state(AutoSteamStates.waiting_for_message_text)
    await throw_float_message(state, callback.message, edit_message_prompt(message_key), callback=callback, send=True)


@router.message(AutoSteamStates.waiting_for_text, F.text)
async def message_ast_text(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("ast_field")
    text = (message.text or "").strip()
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    if field == "api_login":
        set_api_login(text)
        await state.clear()
        return await _show_menu(message, state)
    if field == "api_password":
        set_api_password(text)
        await state.clear()
        return await _show_menu(message, state)
    if field == "allowed_subcategory_ids":
        try:
            values = [int(item.strip()) for item in text.split(',') if item.strip()]
        except ValueError:
            return await message.answer("ID должны быть числами через запятую.")
        set_allowed_subcategory_ids(values)
        await state.clear()
        return await _show_menu(message, state)
    if field == "blacklist_add":
        add_blacklist_login(text)
        await state.clear()
        return await message.answer(blacklist_text(), reply_markup=blacklist_kb(), parse_mode="HTML")
    if field == "blacklist_remove":
        remove_blacklist_login(text)
        await state.clear()
        return await message.answer(blacklist_text(), reply_markup=blacklist_kb(), parse_mode="HTML")
    await state.clear()
    await message.answer("Поле не найдено.")


@router.message(AutoSteamStates.waiting_for_float, F.text)
async def message_ast_float(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("ast_float_field")
    text = (message.text or "").strip().replace(',', '.')
    try:
        value = float(text)
    except ValueError:
        return await message.answer("Введите число.")
    if field == "reminder_time_minutes":
        set_reminder_time_minutes(value)
        await state.clear()
        return await _show_menu(message, state)
    await state.clear()
    await message.answer("Поле не найдено.")


@router.message(AutoSteamStates.waiting_for_message_text, F.text)
async def message_ast_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    message_key = data.get("ast_message_key")
    text = (message.text or "").strip()
    if not message_key:
        await state.clear()
        return await message.answer("Ключ сообщения не найден.")
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    set_message(message_key, text)
    await state.clear()
    await message.answer(messages_text(), reply_markup=messages_kb(), parse_mode="HTML")


async def on_telegram_bot_init(telegram_bot):
    for bot in getattr(telegram_bot, "bots", []):
        try:
            await bot.set_my_commands([
                BotCommand(command="/start", description="Главное меню"),
                BotCommand(command="/autosteam", description="Настройки AutoSteam"),
            ])
        except Exception:
            pass


BOT_EVENT_HANDLERS = {"ON_TELEGRAM_BOT_INIT": [on_telegram_bot_init]}
