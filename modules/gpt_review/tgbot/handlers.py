from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from settings import Settings as sett
from tgbot.helpful import do_auth, throw_float_message

from ..helpers import prompt_text
from ..states import GPTReviewStates
from ..storage import (
    get_api_base_url,
    get_model,
    get_timeout_sec,
    is_enabled,
    is_only_without_reply,
    is_owned,
    set_api_base_url,
    set_api_key,
    set_enabled,
    set_message,
    set_min_stars,
    set_model,
    set_only_without_reply,
    set_prompt,
    set_timeout_sec,
)
from ..templates import edit_message_prompt, menu_kb, menu_text, messages_kb, messages_text


router = Router()


async def _is_authorized(message: Message) -> bool:
    config = sett.get("config") or {}
    signed = config.get("telegram", {}).get("bot", {}).get("signed_users", [])
    return bool(message.from_user and message.from_user.id in signed)


async def _show_menu(message: Message, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, message, menu_text(), menu_kb())


@router.message(Command("gptreview"))
async def command_gptreview(message: Message, state: FSMContext):
    if not await _is_authorized(message):
        return await do_auth(message, state)
    if not is_owned():
        return await message.answer("Модуль GPT Review не подключён к этому боту.")
    await _show_menu(message, state)


@router.callback_query(F.data == "gr_back")
async def callback_gr_back(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "gr_toggle_enabled")
async def callback_gr_toggle_enabled(callback, state: FSMContext):
    set_enabled(not is_enabled())
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "gr_toggle_only_without_reply")
async def callback_gr_toggle_only_without_reply(callback, state: FSMContext):
    set_only_without_reply(not is_only_without_reply())
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "gr_edit_api_base_url")
async def callback_gr_edit_api_base_url(callback, state: FSMContext):
    await state.update_data(gr_field="api_base_url")
    await state.set_state(GPTReviewStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте новый API URL.\nТекущий: <code>{get_api_base_url() or 'не задан'}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "gr_edit_api_key")
async def callback_gr_edit_api_key(callback, state: FSMContext):
    await state.update_data(gr_field="api_key")
    await state.set_state(GPTReviewStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text("Отправьте новый API key."), callback=callback, send=True)


@router.callback_query(F.data == "gr_edit_model")
async def callback_gr_edit_model(callback, state: FSMContext):
    await state.update_data(gr_field="model")
    await state.set_state(GPTReviewStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте модель.\nТекущая: <code>{get_model() or 'не задана'}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "gr_edit_prompt")
async def callback_gr_edit_prompt(callback, state: FSMContext):
    await state.update_data(gr_field="prompt")
    await state.set_state(GPTReviewStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text("Отправьте новый prompt для генерации ответа на отзыв."), callback=callback, send=True)


@router.callback_query(F.data == "gr_edit_min_stars")
async def callback_gr_edit_min_stars(callback, state: FSMContext):
    await state.update_data(gr_int_field="min_stars")
    await state.set_state(GPTReviewStates.waiting_for_int)
    await throw_float_message(state, callback.message, prompt_text("Отправьте минимальную оценку от 1 до 5."), callback=callback, send=True)


@router.callback_query(F.data == "gr_edit_timeout")
async def callback_gr_edit_timeout(callback, state: FSMContext):
    await state.update_data(gr_int_field="timeout_sec")
    await state.set_state(GPTReviewStates.waiting_for_int)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте таймаут в секундах. Текущий: <b>{get_timeout_sec()}</b>"), callback=callback, send=True)


@router.callback_query(F.data == "gr_messages_menu")
async def callback_gr_messages_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, messages_text(), messages_kb(), callback)


@router.callback_query(F.data.startswith("gr_message:"))
async def callback_gr_message(callback, state: FSMContext):
    message_key = callback.data.split(":", 1)[1]
    await state.update_data(gr_message_key=message_key)
    await state.set_state(GPTReviewStates.waiting_for_message_text)
    await throw_float_message(state, callback.message, edit_message_prompt(message_key), callback=callback, send=True)


@router.message(GPTReviewStates.waiting_for_text, F.text)
async def message_gr_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    data = await state.get_data()
    field = data.get("gr_field")
    if field == "api_base_url":
        set_api_base_url(text)
    elif field == "api_key":
        set_api_key(text)
    elif field == "model":
        set_model(text)
    elif field == "prompt":
        set_prompt(text)
    else:
        await state.clear()
        return await message.answer("Поле не найдено.")
    await state.clear()
    await message.answer(menu_text(), reply_markup=menu_kb(), parse_mode="HTML")


@router.message(GPTReviewStates.waiting_for_int, F.text)
async def message_gr_int(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        return await message.answer("Введите целое число.")
    value = int(text)
    data = await state.get_data()
    field = data.get("gr_int_field")
    if field == "min_stars":
        if value < 1 or value > 5:
            return await message.answer("Оценка должна быть от 1 до 5.")
        set_min_stars(value)
    elif field == "timeout_sec":
        set_timeout_sec(value)
    else:
        await state.clear()
        return await message.answer("Поле не найдено.")
    await state.clear()
    await message.answer(menu_text(), reply_markup=menu_kb(), parse_mode="HTML")


@router.message(GPTReviewStates.waiting_for_message_text, F.text)
async def message_gr_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    message_key = data.get("gr_message_key")
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
                    BotCommand(command="/gptreview", description="Настройки GPT Review"),
                ]
            )
        except Exception:
            pass


BOT_EVENT_HANDLERS = {
    "ON_TELEGRAM_BOT_INIT": [on_telegram_bot_init],
}
