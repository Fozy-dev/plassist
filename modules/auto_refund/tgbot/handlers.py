from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from settings import Settings as sett
from tgbot.helpful import do_auth, throw_float_message

from ..helpers import prompt_text
from ..states import AutoRefundStates
from ..storage import (
    get_config,
    is_notify_buyer_enabled,
    is_owned,
    set_enabled,
    set_max_price,
    set_message,
    set_notify_buyer,
    toggle_rating,
    is_enabled,
)
from ..templates import edit_message_prompt, menu_kb, menu_text, messages_kb, messages_text, ratings_kb, ratings_text


router = Router()


async def _is_authorized(message: Message) -> bool:
    config = sett.get("config") or {}
    signed = config.get("telegram", {}).get("bot", {}).get("signed_users", [])
    return bool(message.from_user and message.from_user.id in signed)


async def _show_menu(message: Message, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, message, menu_text(), menu_kb())


@router.message(Command("refundctl"))
async def command_refundctl(message: Message, state: FSMContext):
    if not await _is_authorized(message):
        return await do_auth(message, state)
    if not is_owned():
        return await message.answer("Модуль AutoRefund не подключён к этому боту.")
    await _show_menu(message, state)


@router.callback_query(F.data == "ar_back")
async def callback_ar_back(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "ar_toggle_enabled")
async def callback_ar_toggle_enabled(callback, state: FSMContext):
    set_enabled(not is_enabled())
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "ar_ratings_menu")
async def callback_ar_ratings_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, ratings_text(), ratings_kb(), callback)


@router.callback_query(F.data.startswith("ar_toggle_rating:"))
async def callback_ar_toggle_rating(callback, state: FSMContext):
    stars = int(callback.data.split(":", 1)[1])
    toggle_rating(stars)
    await throw_float_message(state, callback.message, ratings_text(), ratings_kb(), callback)


@router.callback_query(F.data == "ar_edit_max_price")
async def callback_ar_edit_max_price(callback, state: FSMContext):
    await state.set_state(AutoRefundStates.waiting_for_max_price)
    await throw_float_message(
        state,
        callback.message,
        prompt_text("Отправьте максимальную сумму заказа для автовозврата. 0 = без лимита."),
        callback=callback,
        send=True,
    )


@router.callback_query(F.data == "ar_toggle_notify")
async def callback_ar_toggle_notify(callback, state: FSMContext):
    set_notify_buyer(not is_notify_buyer_enabled())
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "ar_messages_menu")
async def callback_ar_messages_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, messages_text(), messages_kb(), callback)


@router.callback_query(F.data.startswith("ar_message:"))
async def callback_ar_message(callback, state: FSMContext):
    message_key = callback.data.split(":", 1)[1]
    await state.update_data(ar_message_key=message_key)
    await state.set_state(AutoRefundStates.waiting_for_message_text)
    await throw_float_message(state, callback.message, edit_message_prompt(message_key), callback=callback, send=True)


@router.message(AutoRefundStates.waiting_for_max_price, F.text)
async def message_ar_max_price(message: Message, state: FSMContext):
    text = (message.text or "").strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return await message.answer("Введите число. Пример: 100 или 0")
    set_max_price(value)
    await state.clear()
    await message.answer(menu_text(), reply_markup=menu_kb(), parse_mode="HTML")


@router.message(AutoRefundStates.waiting_for_message_text, F.text)
async def message_ar_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    message_key = data.get("ar_message_key")
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
            await bot.set_my_commands(
                [
                    BotCommand(command="/start", description="Главное меню"),
                    BotCommand(command="/refundctl", description="Настройки AutoRefund"),
                ]
            )
        except Exception:
            pass


BOT_EVENT_HANDLERS = {
    "ON_TELEGRAM_BOT_INIT": [on_telegram_bot_init],
}
